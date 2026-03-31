"""Shared pytest fixtures for FitCoach test suite."""

import json
import os
import tempfile

import pytest


@pytest.fixture()
def tmp_db(monkeypatch):
    """Create a temporary SQLite database and patch config.DB_PATH before any
    backend module reads it."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Patch config.DB_PATH *before* importing anything that reads it at
    # module level (backend.db imports DB_PATH from config on load).
    import config
    monkeypatch.setattr(config, "DB_PATH", path)

    # Also patch backend.db.DB_PATH since it was already imported from config
    import backend.db
    monkeypatch.setattr(backend.db, "DB_PATH", path)

    from backend.db import init_db
    init_db()

    yield path

    # Cleanup
    for suffix in ("", "-wal", "-shm"):
        try:
            os.unlink(path + suffix)
        except FileNotFoundError:
            pass


@pytest.fixture()
def client(tmp_db):
    """Flask test client backed by the temporary database."""
    from app import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def sample_recipe_data():
    """A complete recipe dict suitable for DB insertion."""
    return {
        "name": "Test Chicken Bowl",
        "description": "A simple test recipe",
        "category": "chicken",
        "cuisine": "American",
        "country_of_origin": "USA",
        "region": "North America",
        "meal_type": "lunch",
        "difficulty": "easy",
        "prep_time_min": 10,
        "cook_time_min": 20,
        "total_time_min": 30,
        "servings": 2,
        "calories": 450,
        "protein": 35,
        "carbs": 40,
        "fat": 15,
        "fiber": 5,
        "sugar": 3,
        "ingredients": json.dumps([
            {"item": "chicken breast", "amount": "200g", "grams": 200},
            {"item": "rice", "amount": "150g", "grams": 150},
            {"item": "broccoli", "amount": "100g", "grams": 100},
        ]),
        "steps": json.dumps([
            "Cook the rice.",
            "Grill the chicken.",
            "Steam the broccoli.",
            "Combine and serve.",
        ]),
        "tips": "Season generously.",
        "equipment": json.dumps(["grill pan", "pot"]),
        "allergens": json.dumps([]),
        "diet": json.dumps([]),
        "meal_prep_friendly": 1,
        "source": "test",
        "status": "active",
    }


def _insert_recipe(db, data):
    """Helper: insert a recipe dict into the DB and return its id."""
    cols = list(data.keys())
    placeholders = ", ".join(["?"] * len(cols))
    col_names = ", ".join(cols)
    cur = db.execute(
        f"INSERT INTO recipes ({col_names}) VALUES ({placeholders})",
        [data[c] for c in cols],
    )
    db.commit()
    return cur.lastrowid
