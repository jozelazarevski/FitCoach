"""Tests for backend.models — recipe helpers and search."""

import json
import sqlite3

from tests.conftest import _insert_recipe


def test_recipe_to_dict_parses_json_fields(tmp_db):
    """recipe_to_dict should deserialise JSON string fields into lists."""
    from backend.db import use_db
    from backend.models import recipe_to_dict

    with use_db() as db:
        db.execute(
            """INSERT INTO recipes
               (name, calories, protein, carbs, fat,
                ingredients, steps, equipment, allergens, diet)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "Test",
                400,
                30,
                40,
                10,
                json.dumps(["rice", "chicken"]),
                json.dumps(["cook it"]),
                json.dumps(["pan"]),
                json.dumps(["gluten"]),
                json.dumps(["high_protein"]),
            ),
        )
        db.commit()
        row = db.execute("SELECT * FROM recipes WHERE name = 'Test'").fetchone()

    result = recipe_to_dict(row)
    assert isinstance(result["ingredients"], list)
    assert result["ingredients"] == ["rice", "chicken"]
    assert result["steps"] == ["cook it"]
    assert result["equipment"] == ["pan"]
    assert result["allergens"] == ["gluten"]
    assert result["diet"] == ["high_protein"]


def test_recipe_to_dict_handles_malformed_json(tmp_db):
    """Malformed JSON fields should fall back to empty list."""
    from backend.db import use_db
    from backend.models import recipe_to_dict

    with use_db() as db:
        db.execute(
            """INSERT INTO recipes
               (name, calories, protein, carbs, fat,
                ingredients, steps, equipment, allergens, diet)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("Bad", 100, 10, 10, 5, "NOT JSON{{{", "also bad", "nope", "[]", "[]"),
        )
        db.commit()
        row = db.execute("SELECT * FROM recipes WHERE name = 'Bad'").fetchone()

    result = recipe_to_dict(row)
    assert result["ingredients"] == []
    assert result["steps"] == []
    assert result["equipment"] == []


def test_search_recipes_no_filters(tmp_db, sample_recipe_data):
    """search_recipes with no filters returns all active recipes."""
    from backend.db import use_db
    from backend.models import search_recipes

    with use_db() as db:
        _insert_recipe(db, sample_recipe_data)

    result = search_recipes()
    assert result["total"] >= 1
    assert len(result["recipes"]) >= 1
    assert result["page"] == 1


def test_search_recipes_meal_type_filter(tmp_db, sample_recipe_data):
    """search_recipes filters by meal_type correctly."""
    from backend.db import use_db
    from backend.models import search_recipes

    with use_db() as db:
        _insert_recipe(db, sample_recipe_data)

    result = search_recipes(filters={"meal_type": "lunch"})
    assert result["total"] >= 1
    for r in result["recipes"]:
        assert r["meal_type"] == "lunch"

    result_empty = search_recipes(filters={"meal_type": "breakfast"})
    assert result_empty["total"] == 0


def test_search_recipes_calorie_filter(tmp_db, sample_recipe_data):
    """search_recipes filters by max_calories."""
    from backend.db import use_db
    from backend.models import search_recipes

    with use_db() as db:
        _insert_recipe(db, sample_recipe_data)  # 450 cal

    result = search_recipes(filters={"max_calories": 500})
    assert result["total"] >= 1

    result_low = search_recipes(filters={"max_calories": 100})
    assert result_low["total"] == 0
