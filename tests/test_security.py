"""Tests for security features — rate limiting, headers, CORS, password hashing."""

import time


def test_rate_limiting_returns_429(client):
    """Exceeding the rate limit on /api/auth/register (5/60s) returns 429."""
    # The rate limit for register is 5 per 60 seconds
    # Clear any existing rate limit state by using a fresh approach
    from app import _rate_limit_store
    _rate_limit_store.clear()

    for i in range(5):
        client.post(
            "/api/auth/register",
            json={
                "email": f"ratelimit{i}@test.com",
                "password": "secret123",
                "name": "RL",
            },
            content_type="application/json",
        )

    # 6th request should be rate-limited
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "ratelimit_extra@test.com",
            "password": "secret123",
            "name": "RL",
        },
        content_type="application/json",
    )
    assert resp.status_code == 429
    assert "too many" in resp.get_json()["error"].lower()


def test_security_headers_present(client):
    """All required security headers should be set."""
    resp = client.get("/")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert "camera=()" in resp.headers.get("Permissions-Policy", "")


def test_cors_headers_on_api(client):
    """API routes should include CORS headers."""
    resp = client.get("/api/health")
    # In dev mode CORS_ORIGINS='*' so Access-Control-Allow-Origin should be present
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    assert "Content-Type" in resp.headers.get("Access-Control-Allow-Headers", "")


def test_password_hashing():
    """Password hashing and verification should work correctly."""
    from backend.api.auth import _hash_password, _verify_password

    hashed = _hash_password("mysecret")
    assert ":" in hashed  # salt:hash format
    assert _verify_password("mysecret", hashed) is True
    assert _verify_password("wrongpassword", hashed) is False


def test_password_hashing_unique_salts():
    """Two hashes of the same password should differ (random salt)."""
    from backend.api.auth import _hash_password

    h1 = _hash_password("samepassword")
    h2 = _hash_password("samepassword")
    assert h1 != h2  # different salts
