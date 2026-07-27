"""
app_pkg/blueprints/api/routes.py — Core API blueprint.

Endpoints (all prefixed /api/v1):
  GET  /health
  GET  /tools
  GET  /csrf-token
  GET|DELETE /history
  POST /analyze
"""

from __future__ import annotations

import asyncio
import os
import secrets
import threading
import time

from flask import Blueprint, Response, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text

from analyzer import analyze_code, sandbox_runtime_status, verify_tools
from app_pkg.extensions import csrf, db, limiter
from app_pkg.observability import APP_START_TIME, APP_VERSION
from app_pkg.security.middleware import SECURITY_METRICS, _add_metric, contains_abuse_pattern
from app_pkg.utils import coerce_jwt_identity
from models_pkg import AuditLog

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_LANGUAGES = {"python", "javascript", "js", "java", "c", "cpp", "c++"}
ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
SESSION_HISTORY_MAX_RETURNED = 10
MAX_ANALYZE_CONCURRENCY = max(1, int(os.environ.get("MAX_ANALYZE_CONCURRENCY", "4")))
_ANALYZE_SEMAPHORE = threading.BoundedSemaphore(value=MAX_ANALYZE_CONCURRENCY)

# Cache available tools on startup (avoid repeated subprocess checks)
AVAILABLE_TOOLS: dict = {}


def _refresh_tools() -> None:
    global AVAILABLE_TOOLS  # noqa: PLW0603
    AVAILABLE_TOOLS = verify_tools()


def _metrics_access_allowed() -> bool:
    key = (os.environ.get("METRICS_API_KEY") or "").strip()
    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower()
    if key:
        provided = (request.headers.get("X-API-Key") or "").strip()
        return secrets.compare_digest(key, provided)
    return env not in {"prod", "production"}


# ---------------------------------------------------------------------------
# Rate-limit key: per user ID when logged in, else per IP
# ---------------------------------------------------------------------------
def _analyze_rate_limit_key() -> str:
    try:
        verify_jwt_in_request(optional=True)
    except Exception:  # noqa: BLE001
        return f"ip:{get_remote_address()}"
    user_id = get_jwt_identity()
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_remote_address()}"


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------
def _write_audit_log(user_id: int | None, language: str, code: str, *, had_error: bool) -> None:
    """Persist one analyze call (first 200 chars only — GDPR hygiene)."""
    try:
        entry = AuditLog(
            user_id=user_id,
            language=str(language or "python").lower(),
            had_error=bool(had_error),
            code_snippet=(code or "")[:200],
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:  # noqa: BLE001
        current_app.logger.warning("Failed to write audit log: %s", exc)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_bp.route("/health")
def health():
    # DB connectivity check
    db_ok = False
    db_latency_ms = None
    try:
        t0 = time.monotonic()
        db.session.execute(text("SELECT 1"))
        db_latency_ms = round((time.monotonic() - t0) * 1000, 2)
        db_ok = True
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("health_db_check_failed", extra={"error": str(exc)})

    sandbox_status = sandbox_runtime_status()
    uptime_seconds = round(time.monotonic() - APP_START_TIME, 1)
    payload = {
        "status": "healthy" if db_ok else "degraded",
        "version": APP_VERSION,
        "uptime_seconds": uptime_seconds,
        "db": {
            "ok": db_ok,
            "latency_ms": db_latency_ms,
        },
        "sandbox": {
            "ok": bool(sandbox_status.get("ok")),
            "mode": sandbox_status.get("mode"),
        },
        "available_tools": AVAILABLE_TOOLS,
        "ai_mentor_enabled": bool(os.environ.get("GEMINI_API_KEY")),
    }
    return jsonify(payload)


@api_bp.route("/metrics")
def metrics():
    """Prometheus-compatible plain text metrics.

    Scrape with: curl localhost:5000/api/v1/metrics
    Or point a Prometheus server at this endpoint.
    """
    if not _metrics_access_allowed():
        return jsonify({"ok": False, "error": "Not found."}), 404

    uptime = round(time.monotonic() - APP_START_TIME, 1)
    lines = [
        "# HELP ai_mentor_uptime_seconds Seconds since server start",
        "# TYPE ai_mentor_uptime_seconds gauge",
        f"ai_mentor_uptime_seconds {uptime}",
        "",
        "# HELP ai_mentor_abuse_pattern_rejections_total Total requests blocked by abuse pattern",
        "# TYPE ai_mentor_abuse_pattern_rejections_total counter",
        f"ai_mentor_abuse_pattern_rejections_total {SECURITY_METRICS['abuse_pattern_rejections']}",
        "",
        "# HELP ai_mentor_blocked_automated_clients_total Total bot/scraper requests blocked",
        "# TYPE ai_mentor_blocked_automated_clients_total counter",
        (
            f"ai_mentor_blocked_automated_clients_total"
            f" {SECURITY_METRICS['blocked_automated_clients']}"
        ),
        "",
        "# HELP ai_mentor_auth_failures_total Total API key auth failures",
        "# TYPE ai_mentor_auth_failures_total counter",
        f"ai_mentor_auth_failures_total {SECURITY_METRICS['auth_failures']}",
        "",
        "# HELP ai_mentor_concurrency_rejections_total Total requests rejected due to concurrency limit",  # noqa: E501
        "# TYPE ai_mentor_concurrency_rejections_total counter",
        f"ai_mentor_concurrency_rejections_total {SECURITY_METRICS['concurrency_rejections']}",
        "",
        "# HELP ai_mentor_sandbox_failures_total Total sandbox unavailable events",
        "# TYPE ai_mentor_sandbox_failures_total counter",
        f"ai_mentor_sandbox_failures_total {SECURITY_METRICS['sandbox_failures']}",
        "",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")


@api_bp.route("/tools", methods=["GET"])
def tools():
    return jsonify(
        {
            "available": AVAILABLE_TOOLS,
            "message": "Tools marked as 'false' are not installed. See README for setup instructions.",  # noqa: E501
        },
    )


@api_bp.route("/csrf-token", methods=["GET"])
@csrf.exempt
def get_csrf_token():
    _is_prod = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower() in {
        "prod",
        "production",
    }
    token = generate_csrf()
    response = jsonify({"csrf_token": token})
    response.set_cookie(
        "csrftoken",
        token,
        httponly=False,
        samesite="Lax",
        secure=_is_prod,
    )
    return response, 200


@api_bp.route("/history", methods=["GET", "DELETE"])
@jwt_required()
def history():
    user_id = coerce_jwt_identity(get_jwt_identity())
    if user_id is None:
        return jsonify({"ok": False, "error": "Invalid authentication token."}), 401

    if request.method == "DELETE":
        AuditLog.query.filter_by(user_id=user_id).delete()
        db.session.commit()
        return jsonify({"ok": True, "history": []}), 200

    logs = (
        AuditLog.query.filter_by(user_id=user_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(SESSION_HISTORY_MAX_RETURNED)
        .all()
    )
    return jsonify({"ok": True, "history": [log.to_dict() for log in logs]}), 200


@api_bp.route("/analyze", methods=["POST"])
@csrf.exempt
@jwt_required(optional=True)
@limiter.limit("10 per minute; 100 per day", key_func=_analyze_rate_limit_key)
def analyze():  # noqa: C901, PLR0911, PLR0912, PLR0915
    payload = request.get_json(silent=True) or {}
    _raw_identity = get_jwt_identity()
    current_user_id = None
    if _raw_identity is not None:
        current_user_id = coerce_jwt_identity(_raw_identity)
        if current_user_id is None:
            return jsonify({"ok": False, "error": "Invalid authentication token."}), 401

    required_api_key = (os.environ.get("ANALYZE_API_KEY") or "").strip()
    provided_api_key = request.headers.get("X-API-Key", "").strip()
    if required_api_key and not secrets.compare_digest(required_api_key, provided_api_key):
        _add_metric("auth_failures")
        return jsonify({"ok": False, "error": "Unauthorized. Missing or invalid API key."}), 401

    code = payload.get("code")
    language = payload.get("language", "python")
    difficulty = payload.get("difficulty", "beginner")
    code_for_history = code if isinstance(code, str) else ""
    language_for_history = language if isinstance(language, str) else "python"

    if not isinstance(language, str) or language.lower() not in ALLOWED_LANGUAGES:
        _write_audit_log(current_user_id, language_for_history, code_for_history, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Invalid language. Supported values: python, javascript, java, c, cpp.",
                "meta": {"language": language_for_history},
            },
        ), 400
    language = language.lower()

    if not isinstance(difficulty, str) or difficulty.lower() not in ALLOWED_DIFFICULTIES:
        _write_audit_log(current_user_id, language_for_history, code_for_history, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Invalid difficulty. Supported values: beginner, intermediate, advanced.",
                "meta": {"language": language},
            },
        ), 400
    difficulty = difficulty.lower()

    if not isinstance(code, str) or not code.strip():
        _write_audit_log(current_user_id, language, code_for_history, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Invalid or missing 'code' field in request body.",
                "meta": {"language": language},
            },
        ), 400

    abuse_hit = contains_abuse_pattern(code)
    if abuse_hit:
        _add_metric("abuse_pattern_rejections")
        current_app.logger.warning("Blocked analyze request due to abuse pattern: %s", abuse_hit)
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Request blocked by security policy.",
                "meta": {"language": language},
            },
        ), 400

    if len(code) > 102400:  # noqa: PLR2004
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Code exceeds maximum size limit of 100KB.",
                "meta": {"language": language},
            },
        ), 400

    if language in AVAILABLE_TOOLS and not AVAILABLE_TOOLS[language]:
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": f"Tools for language '{language}' are not installed on this server.",
                "meta": {
                    "language": language,
                    "suggestion": "Check the /tools endpoint for available languages or see README for setup.",  # noqa: E501
                },
            },
        ), 422

    acquired = _ANALYZE_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        _add_metric("concurrency_rejections")
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Server is busy. Please retry shortly.",
                "meta": {"language": language},
            },
        ), 503
    try:
        t0 = time.monotonic()
        result = asyncio.run(analyze_code(code=code, language=language, difficulty=difficulty))
        execution_time_ms = int((time.monotonic() - t0) * 1000)

        issues = result.get("issues", []) if isinstance(result, dict) else []
        execution = result.get("execution", {}) if isinstance(result, dict) else {}
        had_issue_error = any(isinstance(i, dict) and i.get("severity") == "error" for i in issues)
        had_execution_error = isinstance(execution, dict) and (
            bool(execution.get("error")) or int(execution.get("returncode", 0) or 0) != 0
        )
        if (
            isinstance(execution, dict)
            and isinstance(execution.get("error"), dict)
            and execution["error"].get("type") == "SandboxUnavailable"
        ):
            _add_metric("sandbox_failures")
        _write_audit_log(
            current_user_id,
            language,
            code,
            had_error=(had_issue_error or had_execution_error),
        )

        if not result.get("ok", True) and result.get("error"):
            return jsonify(
                {
                    "success": False,
                    "output": "",
                    "error": result.get("error"),
                    "meta": {"language": language},
                },
            ), 200

        success = not (had_issue_error or had_execution_error)
        output = execution.get("stdout", "")
        error_str = ""

        # Determine standard error format
        if had_execution_error:
            error_obj = execution.get("error")
            if isinstance(error_obj, dict) and error_obj.get("message"):
                error_str = error_obj.get("message")
            elif execution.get("stderr"):
                error_str = execution.get("stderr")
            else:
                error_str = "Execution failed."

        meta_info = {
            "language": language,
            "executionTimeMs": execution_time_ms,
            "issues": issues,
            "ai_mentor_feedback": result.get("ai_mentor_feedback", ""),
            "ai_mentor_status": result.get("ai_mentor_status", "ok"),
            "mismatch": result.get("mismatch"),
            "execution": execution,
        }

        # Language mismatch overrides
        if result.get("mismatch"):
            output = result.get("output", output)
            success = False
            error_str = "Language mismatch detected."

        return jsonify(
            {"success": success, "output": output, "error": error_str, "meta": meta_info},
        ), 200

    except Exception:  # pragma: no cover
        current_app.logger.exception("Error during code analysis")
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {
                "success": False,
                "output": "",
                "error": "Internal server error during analysis.",
                "meta": {"language": language},
            },
        ), 500
    finally:
        _ANALYZE_SEMAPHORE.release()
