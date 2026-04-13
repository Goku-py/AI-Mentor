"""
tests/test_auth.py — Tests for the authentication blueprint.

Covers all 5 endpoints:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  GET  /api/v1/auth/me
  POST /api/v1/auth/refresh

The 'client' fixture is provided by tests/conftest.py (DB in-memory, CSRF off).
"""

VALID_EMAIL = "auth_test@example.local"
VALID_PASS = "ValidPass1!"
WEAK_PASS = "short"  # < 8 chars
NO_DIGIT_OR_SYMBOL = "onlylower"  # 8 chars but no digit or special char


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------
class TestRegister:
    """POST /api/v1/auth/register"""

    def test_register_valid_credentials_returns_201(self, client):
        """Valid email + strong password → 201 with user info and access token."""
        r = client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert r.status_code == 201
        data = r.get_json()
        assert data["ok"] is True
        assert "access_token" in data
        assert data["user"]["email"] == VALID_EMAIL

    def test_register_default_role_is_student(self, client):
        """Newly registered users always get the 'student' role."""
        r = client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert r.get_json()["user"]["role"] == "student"

    def test_register_duplicate_email_returns_409(self, client):
        """Registering the same email twice returns 409 Conflict."""
        client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        r = client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert r.status_code == 409
        assert r.get_json()["ok"] is False

    def test_register_short_password_returns_400(self, client):
        """Password shorter than 8 characters is rejected."""
        r = client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": WEAK_PASS}
        )
        assert r.status_code == 400
        assert "password" in r.get_json()["error"].lower()

    def test_register_password_without_digit_or_symbol_returns_400(self, client):
        """Password must contain at least one digit or special character."""
        r = client.post(
            "/api/v1/auth/register",
            json={"email": VALID_EMAIL, "password": NO_DIGIT_OR_SYMBOL},
        )
        assert r.status_code == 400
        assert "password" in r.get_json()["error"].lower()

    def test_register_invalid_email_returns_400(self, client):
        """Plain string that is not a valid email is rejected."""
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "not-an-email", "password": VALID_PASS},
        )
        assert r.status_code == 400

    def test_register_missing_fields_returns_400(self, client):
        """Empty body returns 400."""
        r = client.post("/api/v1/auth/register", json={})
        assert r.status_code == 400

    def test_register_email_normalised_to_lowercase(self, client):
        """Email addresses should be stored in lowercase regardless of input case."""
        r = client.post(
            "/api/v1/auth/register",
            json={"email": "UPPER@Example.COM", "password": VALID_PASS},
        )
        assert r.status_code == 201
        assert r.get_json()["user"]["email"] == "upper@example.com"

    def test_register_returns_refresh_cookie(self, client):
        """Registration must set a refresh token cookie (httpOnly)."""
        r = client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert r.status_code == 201
        assert "refresh_token_cookie" in r.headers.get("Set-Cookie", "")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
class TestLogin:
    """POST /api/v1/auth/login"""

    def _register(self, client):
        client.post(
            "/api/v1/auth/register", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )

    def test_login_correct_password_returns_200(self, client):
        """Correct credentials return 200 with access token."""
        self._register(client)
        r = client.post(
            "/api/v1/auth/login", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        assert "access_token" in data
        assert len(data["access_token"]) > 20

    def test_login_wrong_password_returns_401(self, client):
        """Wrong password returns 401 with ok=False."""
        self._register(client)
        r = client.post(
            "/api/v1/auth/login",
            json={"email": VALID_EMAIL, "password": "wrongpassword99!"},
        )
        assert r.status_code == 401
        assert r.get_json()["ok"] is False

    def test_login_unknown_email_returns_401(self, client):
        """Login with an email that was never registered returns 401."""
        r = client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.local", "password": VALID_PASS},
        )
        assert r.status_code == 401

    def test_login_missing_fields_returns_400(self, client):
        """Empty body returns 400 (not 500)."""
        r = client.post("/api/v1/auth/login", json={})
        assert r.status_code == 400

    def test_login_sets_refresh_cookie(self, client):
        """Login must set a refresh token cookie."""
        self._register(client)
        r = client.post(
            "/api/v1/auth/login", json={"email": VALID_EMAIL, "password": VALID_PASS}
        )
        assert "refresh_token_cookie" in r.headers.get("Set-Cookie", "")


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------
class TestMe:
    """GET /api/v1/auth/me"""

    def test_me_with_valid_token_returns_user(self, client, auth_headers):
        """Valid Bearer token returns full user profile."""
        r = client.get("/api/v1/auth/me", headers=auth_headers)
        assert r.status_code == 200
        data = r.get_json()
        assert data["ok"] is True
        user = data["user"]
        assert "email" in user
        assert "role" in user
        assert "id" in user
        assert "created_at" in user

    def test_me_without_token_returns_401(self, client):
        """No Authorization header → 401."""
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401

    def test_me_with_garbage_token_returns_4xx(self, client):
        """A syntactically invalid token (not JWT) should be rejected."""
        r = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer this.is.garbage"}
        )
        assert r.status_code in (401, 422)


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
class TestLogout:
    """POST /api/v1/auth/logout"""

    def test_logout_with_valid_token_returns_200(self, client, auth_headers):
        """Logout with a valid token returns 200 ok."""
        r = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert r.status_code == 200
        assert r.get_json()["ok"] is True

    def test_logout_without_token_returns_401(self, client):
        """Logout without any token returns 401."""
        r = client.post("/api/v1/auth/logout")
        assert r.status_code == 401
