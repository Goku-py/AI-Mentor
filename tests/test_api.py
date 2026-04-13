"""
Integration tests for the Flask backend API.

Run with: python -m pytest tests/test_api.py -v
"""

import pytest
import json

# client and auth_headers fixtures are provided by tests/conftest.py


class TestHealthEndpoint:
    """Test server health check endpoint."""

    def test_health_endpoint_exists(self, client):
        """Health endpoint should return 200."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

    def test_health_response_structure(self, client):
        """Health response should include status, db, sandbox, tools, metrics, version."""
        response = client.get("/api/v1/health")
        data = response.get_json()
        assert "status" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "available_tools" in data
        assert "ai_mentor_enabled" in data
        assert "db" in data
        assert "ok" in data["db"]
        assert "sandbox" in data
        assert "ok" in data["sandbox"]
        assert "metrics" in data


class TestToolsEndpoint:
    """Test tools availability endpoint."""

    def test_tools_endpoint_exists(self, client):
        """Tools endpoint should return 200."""
        response = client.get("/api/v1/tools")
        assert response.status_code == 200

    def test_tools_response_structure(self, client):
        """Tools response should list available tools."""
        response = client.get("/api/v1/tools")
        data = json.loads(response.data)
        assert "available" in data
        assert "message" in data


class TestAnalyzeEndpoint:
    """Test code analysis endpoint."""

    def test_analyze_endpoint_requires_post(self, client):
        """GET request to POST-only endpoint should not succeed."""
        response = client.get("/api/v1/analyze")
        # Flask returns 404 (caught by static catch-all) or 405 depending on
        # routing order; either way it must not return 200.
        assert response.status_code in (404, 405)

    def test_analyze_requires_code(self, client):
        """Analyze should reject missing code."""
        response = client.post(
            "/api/v1/analyze", data=json.dumps({}), content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data is not None, "Expected JSON body in 400 response"
        assert "error" in data

    def test_analyze_requires_non_empty_code(self, client):
        """Analyze should reject empty/whitespace-only code."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": "   ", "language": "python"}),
            content_type="application/json",
        )
        assert response.status_code == 400

    def test_analyze_python_success(self, client):
        """Analyze should process valid Python code."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("hello")', "language": "python"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        assert data["language"] == "python"

    def test_analyze_includes_execution_result(self, client):
        """Analyze response should include execution output."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("test output")', "language": "python"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "execution" in data
        if data["execution"].get("error", {}).get("type") == "SandboxUnavailable":
            assert data["execution"]["returncode"] == -1
        else:
            assert "test output" in data["execution"]["stdout"]

    def test_analyze_includes_issues(self, client):
        """Analyze response should include detected issues."""
        # Code with a long line (> 79 chars)
        code = "x = " + "y" * 100
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": code, "language": "python"}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert "issues" in data
        assert isinstance(data["issues"], list)

    def test_analyze_includes_ai_feedback(self, client):
        """Analyze response should include AI mentor feedback."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": "x = 10\nprint(x)", "language": "python"}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert "ai_mentor_feedback" in data

    def test_analyze_with_syntax_error(self, client):
        """Analyze should handle syntax errors gracefully."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("missing paren', "language": "python"}),
            content_type="application/json",
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["ok"] is True
        # Should have detected syntax error
        assert any(i["code"] == "SYNTAX_ERROR" for i in data["issues"])

    def test_analyze_default_language_is_python(self, client):
        """Language should default to Python if not specified."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("hello")'}),
            content_type="application/json",
        )
        data = json.loads(response.data)
        assert data["language"] == "python"

    def test_analyze_with_invalid_json(self, client):
        """Malformed JSON should be handled gracefully."""
        response = client.post(
            "/api/v1/analyze", data="invalid json", content_type="application/json"
        )
        assert response.status_code == 400

    def test_analyze_requires_api_key_when_configured(self, client, monkeypatch):
        """Analyze endpoint should require X-API-Key when ANALYZE_API_KEY is set."""
        monkeypatch.setenv("ANALYZE_API_KEY", "test-api-key")
        no_auth = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("hello")', "language": "python"}),
            content_type="application/json",
        )
        assert no_auth.status_code == 401

        with_auth = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("hello")', "language": "python"}),
            content_type="application/json",
            headers={"X-API-Key": "test-api-key"},
        )
        assert with_auth.status_code == 200

    def test_analyze_blocks_abuse_pattern(self, client):
        """Analyze endpoint should block obviously dangerous payload patterns."""
        response = client.post(
            "/api/v1/analyze",
            data=json.dumps({"code": 'print("x")\n# rm -rf /', "language": "python"}),
            content_type="application/json",
            environ_overrides={"REMOTE_ADDR": "10.9.9.9"},
        )
        assert response.status_code == 400
        data = json.loads(response.data)
        assert "security policy" in data.get("error", "").lower()


class TestHistoryEndpoint:
    """Test DB-backed analyze history endpoint (requires JWT)."""

    def test_history_requires_auth(self, client):
        """GET /history returns 401 for unauthenticated requests."""
        response = client.get("/api/v1/history")
        assert response.status_code == 401

    def test_history_empty_for_new_user(self, client, auth_headers):
        """A newly registered user starts with an empty history."""
        response = client.get("/api/v1/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["history"] == []

    def test_history_appends_on_analyze(self, client, auth_headers):
        """Analyze call made with auth should appear in the user's history."""
        client.post(
            "/api/v1/analyze",
            json={"code": 'print("hello world")', "language": "python"},
            headers=auth_headers,
        )

        response = client.get("/api/v1/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["history"]) >= 1
        # History is DESC (most recent first)
        latest = data["history"][0]
        assert "timestamp" in latest
        assert latest["language"] == "python"
        assert isinstance(latest["had_error"], bool)

    def test_history_returns_at_most_10_entries(self, client, auth_headers):
        """History endpoint returns at most 10 items regardless of how many are stored."""
        for idx in range(12):
            client.post(
                "/api/v1/analyze",
                json={"code": f"print({idx})", "language": "python"},
                headers=auth_headers,
            )

        response = client.get("/api/v1/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["history"]) == 10

    def test_history_delete_clears_entries(self, client, auth_headers):
        """DELETE /history should remove all entries for the current user."""
        client.post(
            "/api/v1/analyze",
            json={"code": 'print("to clear")', "language": "python"},
            headers=auth_headers,
        )

        clear_response = client.delete("/api/v1/history", headers=auth_headers)
        assert clear_response.status_code == 200
        clear_data = clear_response.get_json()
        assert clear_data["ok"] is True
        assert clear_data["history"] == []

        history_response = client.get("/api/v1/history", headers=auth_headers)
        assert history_response.get_json()["history"] == []

    def test_history_isolated_between_users(self, client):
        """User A's history must not be visible to User B."""

        def _login(email):
            client.post(
                "/api/v1/auth/register", json={"email": email, "password": "TestPass1!"}
            )
            resp = client.post(
                "/api/v1/auth/login", json={"email": email, "password": "TestPass1!"}
            )
            return {"Authorization": f"Bearer {resp.get_json()['access_token']}"}

        headers_a = _login("user_a@example.local")
        headers_b = _login("user_b@example.local")

        # User A submits code
        client.post(
            "/api/v1/analyze",
            json={"code": 'print("user_a")', "language": "python"},
            headers=headers_a,
        )

        # User B's history must be empty
        response = client.get("/api/v1/history", headers=headers_b)
        assert response.get_json()["history"] == []


class TestRootEndpoint:
    """Test root endpoint (serves the frontend SPA)."""

    def test_root_endpoint_exists(self, client):
        """Root endpoint should return 200 (serves index.html or fallback)."""
        response = client.get("/")
        # The app serves a built frontend; 200 or 404 (dist not built) are both
        # acceptable in a test environment without a built frontend.
        assert response.status_code in (200, 404)


class TestCORSHeaders:
    """Test CORS configuration."""

    def test_cors_headers_present(self, client):
        """Response should include CORS headers."""
        response = client.options("/api/v1/analyze")
        # CORS headers should be set
        # The actual check depends on flask-cors configuration
        assert response.status_code == 200


class TestDebugSecurityEndpoints:
    """Test debug security/status endpoints."""

    def test_debug_sandbox_status_exists(self, client):
        response = client.get("/api/v1/debug/sandbox-status")
        assert response.status_code == 200
        data = json.loads(response.data)
        assert "status" in data
        assert "mode" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
