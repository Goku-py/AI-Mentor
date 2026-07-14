"""
Tests for debug/diagnostics endpoints.
"""

import json
import urllib.error
from io import BytesIO
from unittest.mock import patch

import pytest


class TestDebugGeminiStatus:
    """Tests for /api/v1/debug/gemini-status."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "API has not been used in project 123 before or it is disabled.",
            "Generative Language API has not been used in project before or it is disabled.",
            "The API is disabled for this project.",
        ],
    )
    def test_gemini_status_api_disabled(self, client, monkeypatch, error_message):
        """Should report api_disabled when the error body indicates the API is disabled."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake-api-key")

        body = json.dumps({"error": {"message": error_message, "code": 403}}).encode("utf-8")
        fake_fp = BytesIO(body)
        http_error = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/test:generateContent",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=fake_fp,
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            response = client.get("/api/v1/debug/gemini-status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "api_disabled"

    def test_gemini_status_forbidden_when_not_disabled(self, client, monkeypatch):
        """Should report forbidden for a generic 403 without disabled wording."""
        monkeypatch.setenv("GEMINI_API_KEY", "fake-api-key")

        body = json.dumps({"error": {"message": "Permission denied", "code": 403}}).encode(
            "utf-8"
        )
        fake_fp = BytesIO(body)
        http_error = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com/v1beta/models/test:generateContent",
            code=403,
            msg="Forbidden",
            hdrs={},
            fp=fake_fp,
        )

        with patch("urllib.request.urlopen", side_effect=http_error):
            response = client.get("/api/v1/debug/gemini-status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "forbidden"


class TestDebugSandboxStatus:
    """Tests for /api/v1/debug/sandbox-status."""

    def test_sandbox_status_includes_host_fallback_allowed(self, client):
        """Sandbox status response should include host_fallback_allowed."""
        response = client.get("/api/v1/debug/sandbox-status")
        assert response.status_code == 200
        data = response.get_json()
        assert "host_fallback_allowed" in data
        assert isinstance(data["host_fallback_allowed"], bool)
