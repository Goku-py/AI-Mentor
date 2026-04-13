"""
tests/conftest.py — Shared pytest fixtures for the AI Code Mentor test suite.

Uses the create_app() Application Factory with TestingConfig, so every test
gets a clean in-memory database without touching the live database.
"""

import os
import pytest
from unittest.mock import patch

from app_pkg import create_app
from app_pkg.extensions import limiter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_ai_mentorship():
    """Patch _get_ai_mentorship so tests never make real Gemini HTTP calls.
    Opt out: set ENABLE_LIVE_AI=1 in environment.
    """
    if os.environ.get("ENABLE_LIVE_AI") == "1":
        yield
        return
    with patch("analyzer._get_ai_mentorship", return_value="LOOKS_GOOD"):
        yield


@pytest.fixture
def client():
    """Flask test client backed by a fresh in-memory DB for each test."""
    app = create_app("testing")
    with app.app_context():
        # Reset rate-limit counters between tests (harmless if storage not configured)
        try:
            limiter.reset()
        except Exception:
            pass
        with app.test_client() as c:
            yield c


@pytest.fixture
def auth_headers(client):
    """Register + login a throwaway user; return the Authorization header.

    Usage:
        def test_something(self, client, auth_headers):
            r = client.get('/api/v1/auth/me', headers=auth_headers)
    """
    _EMAIL = "fixture@example.local"
    _PASS = "Fixture1!"

    client.post("/api/v1/auth/register", json={"email": _EMAIL, "password": _PASS})
    resp = client.post("/api/v1/auth/login", json={"email": _EMAIL, "password": _PASS})
    token = resp.get_json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
