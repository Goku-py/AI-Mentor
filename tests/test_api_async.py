"""tests/test_api_async.py — Async /analyze endpoints (202 + status polling)."""

from __future__ import annotations

import pytest
from rq import Queue

from app_pkg import create_app


@pytest.fixture
def fake_redis_connection():
    import fakeredis  # noqa: PLC0415
    return fakeredis.FakeRedis()


@pytest.fixture
def async_client(monkeypatch, fake_redis_connection):
    """Flask test client with async analyze enabled and a fake RQ queue."""
    monkeypatch.setenv("ASYNC_ANALYZE_ENABLED", "1")
    monkeypatch.setenv("FLASK_ENV", "testing")

    test_queue = Queue(connection=fake_redis_connection, is_async=False)
    monkeypatch.setattr("app_pkg.blueprints.api.routes.get_rq_queue", lambda: test_queue)

    app = create_app("testing")
    with app.app_context():
        with app.test_client() as client:
            yield client


class TestAsyncAnalyze:
    """Async analyze acceptance and polling."""

    def test_async_analyze_returns_202(self, async_client):
        response = async_client.post(
            "/api/v1/analyze",
            json={"code": 'print("hello")', "language": "python"},
        )
        assert response.status_code == 202
        data = response.get_json()
        assert data["ok"] is True
        assert data["status"] == "queued"
        assert "job_id" in data
        assert "poll_url" in data
        assert data["poll_url"].startswith("/api/v1/analyze/status/")

    def test_async_analyze_still_validates_input(self, async_client):
        response = async_client.post(
            "/api/v1/analyze",
            json={"language": "not-a-language"},
        )
        assert response.status_code == 400

    def test_analyze_status_returns_finished_result(self, async_client):
        post_response = async_client.post(
            "/api/v1/analyze",
            json={"code": 'print("hello")', "language": "python"},
        )
        job_id = post_response.get_json()["job_id"]

        status_response = async_client.get(f"/api/v1/analyze/status/{job_id}")
        assert status_response.status_code == 200
        data = status_response.get_json()
        assert data["ok"] is True
        assert data["status"] == "finished"
        assert "result" in data
        assert data["result"]["language"] == "python"

    def test_analyze_status_missing_job_returns_404(self, async_client):
        response = async_client.get("/api/v1/analyze/status/does-not-exist")
        assert response.status_code == 404

    def test_sync_path_unchanged_when_async_disabled(self, client, monkeypatch):
        monkeypatch.setenv("ASYNC_ANALYZE_ENABLED", "0")
        response = client.post(
            "/api/v1/analyze",
            json={"code": 'print("hello")', "language": "python"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert "success" in data
        assert "meta" in data
