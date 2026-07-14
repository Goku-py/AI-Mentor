"""app_pkg/jobs/analyze_job.py — RQ job that runs code analysis.

This module is intentionally self-contained: it bootstraps its own Flask app
context because RQ workers run in a separate process from the web server.
"""

from __future__ import annotations

import os
from typing import Any

from app_pkg.blueprints.api.routes import _write_audit_log


def _bootstrap_app():
    """Create a Flask app suitable for the worker environment."""
    from app_pkg import create_app  # noqa: PLC0415

    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "production").strip().lower()
    return create_app(env)


def _had_error_from_result(result: dict[str, Any] | None) -> bool:
    """Return True if the analyze result indicates any error."""
    if not isinstance(result, dict):
        return True
    issues = result.get("issues", []) if isinstance(result.get("issues"), list) else []
    execution = result.get("execution", {}) if isinstance(result.get("execution"), dict) else {}
    had_issue_error = any(
        isinstance(i, dict) and i.get("severity") == "error" for i in issues
    )
    had_execution_error = isinstance(execution, dict) and (
        bool(execution.get("error")) or int(execution.get("returncode", 0) or 0) != 0
    )
    return had_issue_error or had_execution_error


def run_analyze_job(
    code: str,
    language: str,
    difficulty: str,
    user_id: int | None,
) -> dict[str, Any]:
    """Run analyze_code inside an RQ worker and persist an audit log row.

    Args:
        code: Source code submitted by the user.
        language: Normalized language identifier.
        difficulty: Selected difficulty level.
        user_id: Authenticated user id, if any.

    Returns:
        The raw dict returned by analyzer.analyze_code().
    """
    from analyzer import analyze_code  # noqa: PLC0415
    from models_pkg import db  # noqa: PLC0415

    app = _bootstrap_app()
    with app.app_context():
        try:
            result = analyze_code(code=code, language=language, difficulty=difficulty)
            _write_audit_log(user_id, language, code, had_error=_had_error_from_result(result))
            return result
        except Exception as exc:  # noqa: BLE001
            app.logger.exception("Error during background analysis")
            _write_audit_log(user_id, language, code, had_error=True)
            raise
        finally:
            db.session.remove()
