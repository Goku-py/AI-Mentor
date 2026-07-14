"""tests/test_jobs.py — Background job serialization and execution."""

from __future__ import annotations

import os

import fakeredis
import pytest
from rq import Queue

from app_pkg import create_app
from app_pkg.jobs.analyze_job import run_analyze_job


@pytest.fixture
def fake_redis():
    return fakeredis.FakeRedis()


@pytest.fixture
def rq_queue(fake_redis):
    return Queue(connection=fake_redis, is_async=False)


@pytest.fixture
def test_app():
    """Shared Flask app used by the job under test."""
    from app_pkg import create_app  # noqa: PLC0415
    return create_app("testing")


class TestAnalyzeJob:
    """Job execution and audit logging."""

    def test_job_serializes_and_runs(self, rq_queue, test_app, monkeypatch):
        """A job can be enqueued and executed synchronously with the test queue."""
        monkeypatch.setenv("FLASK_ENV", "testing")
        monkeypatch.setattr(
            "app_pkg.jobs.analyze_job._bootstrap_app", lambda: test_app
        )

        with test_app.app_context():
            job = rq_queue.enqueue(
                run_analyze_job,
                'print("hello")',
                "python",
                "beginner",
                None,
            )
        assert job.id is not None
        assert job.get_status() == "finished"
        result = job.result
        assert isinstance(result, dict)
        assert result.get("language") == "python"

    def test_job_writes_audit_log(self, rq_queue, test_app, monkeypatch):
        """A successful job writes an AuditLog row inside the app context."""
        monkeypatch.setenv("FLASK_ENV", "testing")
        monkeypatch.setattr(
            "app_pkg.jobs.analyze_job._bootstrap_app", lambda: test_app
        )

        from models_pkg import AuditLog, db  # noqa: PLC0415

        with test_app.app_context():
            db.create_all()
            before = AuditLog.query.count()
            job = rq_queue.enqueue(
                run_analyze_job,
                'print("hello")',
                "python",
                "beginner",
                123,
            )
            assert job.get_status() == "finished"
            after = AuditLog.query.count()
            assert after == before + 1
            entry = AuditLog.query.order_by(AuditLog.id.desc()).first()
            assert entry.user_id == 123
            assert entry.language == "python"

    def test_job_session_removed_after_run(self, rq_queue, test_app, monkeypatch):
        """db.session.remove() is always called after a job runs."""
        monkeypatch.setenv("FLASK_ENV", "testing")
        monkeypatch.setattr(
            "app_pkg.jobs.analyze_job._bootstrap_app", lambda: test_app
        )

        from models_pkg import db  # noqa: PLC0415

        removed = []
        original_remove = db.session.remove

        def tracking_remove():
            removed.append(True)
            return original_remove()

        monkeypatch.setattr(db.session, "remove", tracking_remove)

        with test_app.app_context():
            db.create_all()
            rq_queue.enqueue(run_analyze_job, "x = 1", "python", "beginner", None)

        assert removed
