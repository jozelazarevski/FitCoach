"""Tests for Flask API endpoints."""

import json

from tests.conftest import _insert_recipe


def test_index_returns_200(client):
    """GET / should serve the frontend."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_health_endpoint(client):
    """GET /api/health returns 200 with status field."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")


def test_register_success(client):
    """POST /api/auth/register creates a new user and returns a token."""
    from app import _rate_limit_store
    _rate_limit_store.clear()

    resp = client.post(
        "/api/auth/register",
        json={"email": "new@test.com", "password": "secret123", "name": "Tester"},
        content_type="application/json",
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert "token" in data
    assert data["user"]["email"] == "new@test.com"


def test_register_duplicate_email(client):
    """Registering the same email twice returns 409."""
    payload = {"email": "dup@test.com", "password": "secret123", "name": "Dup"}
    client.post("/api/auth/register", json=payload, content_type="application/json")
    resp = client.post(
        "/api/auth/register", json=payload, content_type="application/json"
    )
    assert resp.status_code == 409
    assert "already" in resp.get_json()["error"].lower()


def test_login_valid(client):
    """Login with correct credentials returns a token."""
    client.post(
        "/api/auth/register",
        json={"email": "login@test.com", "password": "secret123"},
        content_type="application/json",
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "login@test.com", "password": "secret123"},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()


def test_login_invalid(client):
    """Login with wrong password returns 401."""
    client.post(
        "/api/auth/register",
        json={"email": "bad@test.com", "password": "secret123"},
        content_type="application/json",
    )
    resp = client.post(
        "/api/auth/login",
        json={"email": "bad@test.com", "password": "wrongpass"},
        content_type="application/json",
    )
    assert resp.status_code == 401


def test_me_without_token(client):
    """GET /api/auth/me without token returns 401."""
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_me_with_token(client):
    """GET /api/auth/me with valid token returns user info."""
    from app import _rate_limit_store
    _rate_limit_store.clear()

    reg = client.post(
        "/api/auth/register",
        json={"email": "me@test.com", "password": "secret123", "name": "Me"},
        content_type="application/json",
    )
    assert reg.status_code == 201, f"Registration failed: {reg.get_json()}"
    token = reg.get_json()["token"]
    resp = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["email"] == "me@test.com"


def test_recipes_paginated(client, sample_recipe_data):
    """GET /api/recipes returns paginated results."""
    from backend.db import use_db

    with use_db() as db:
        _insert_recipe(db, sample_recipe_data)

    resp = client.get("/api/recipes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "recipes" in data
    assert "total" in data
    assert "page" in data


def test_404_handler(client):
    """Unknown routes return JSON 404."""
    resp = client.get("/nonexistent-route-xyz")
    assert resp.status_code == 404
    data = resp.get_json()
    assert "error" in data
