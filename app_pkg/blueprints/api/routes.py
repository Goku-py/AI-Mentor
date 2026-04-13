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
import time
import threading

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_limiter.util import get_remote_address
from sqlalchemy import text

from analyzer import analyze_code, analyze_repository, sandbox_runtime_status, verify_tools
from app_pkg.extensions import csrf, db, limiter
from app_pkg.security.middleware import SECURITY_METRICS, contains_abuse_pattern
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
    global AVAILABLE_TOOLS
    AVAILABLE_TOOLS = verify_tools()


# ---------------------------------------------------------------------------
# Rate-limit key: per user ID when logged in, else per IP
# ---------------------------------------------------------------------------
def _analyze_rate_limit_key() -> str:
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            return f"user:{user_id}"
    except Exception:
        pass
    return f"ip:{get_remote_address()}"


# ---------------------------------------------------------------------------
# Audit log helper
# ---------------------------------------------------------------------------
def _write_audit_log(
    user_id: int | None, language: str, code: str, had_error: bool
) -> None:
    """Persist one analyze call (first 200 chars only — GDPR hygiene)."""
    from flask import current_app

    try:
        entry = AuditLog(
            user_id=user_id,
            language=str(language or "python").lower(),
            had_error=bool(had_error),
            code_snippet=(code or "")[:200],
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as exc:  # pragma: no cover
        current_app.logger.warning("Failed to write audit log: %s", exc)
        db.session.rollback()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_bp.route("/health")
def health():
    from app_pkg.observability import APP_START_TIME, APP_VERSION

    # DB connectivity check
    db_ok = False
    db_latency_ms = None
    try:
        t0 = time.monotonic()
        db.session.execute(text("SELECT 1"))
        db_latency_ms = round((time.monotonic() - t0) * 1000, 2)
        db_ok = True
    except Exception as exc:  # pragma: no cover
        from flask import current_app

        current_app.logger.error("health_db_check_failed", extra={"error": str(exc)})

    sandbox_status = sandbox_runtime_status()
    uptime_seconds = round(time.monotonic() - APP_START_TIME, 1)

    return jsonify(
        {
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
            "metrics": SECURITY_METRICS,
        }
    )


@api_bp.route("/metrics")
def metrics():
    """Prometheus-compatible plain text metrics.

    Scrape with: curl localhost:5000/api/v1/metrics
    Or point a Prometheus server at this endpoint.
    """
    from app_pkg.observability import APP_START_TIME

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
        f"ai_mentor_blocked_automated_clients_total {SECURITY_METRICS['blocked_automated_clients']}",
        "",
        "# HELP ai_mentor_auth_failures_total Total API key auth failures",
        "# TYPE ai_mentor_auth_failures_total counter",
        f"ai_mentor_auth_failures_total {SECURITY_METRICS['auth_failures']}",
        "",
        "# HELP ai_mentor_concurrency_rejections_total Total requests rejected due to concurrency limit",
        "# TYPE ai_mentor_concurrency_rejections_total counter",
        f"ai_mentor_concurrency_rejections_total {SECURITY_METRICS['concurrency_rejections']}",
        "",
        "# HELP ai_mentor_sandbox_failures_total Total sandbox unavailable events",
        "# TYPE ai_mentor_sandbox_failures_total counter",
        f"ai_mentor_sandbox_failures_total {SECURITY_METRICS['sandbox_failures']}",
        "",
    ]
    return Response(
        "\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8"
    )


@api_bp.route("/tools", methods=["GET"])
def tools():
    return jsonify(
        {
            "available": AVAILABLE_TOOLS,
            "message": "Tools marked as 'false' are not installed. See README for setup instructions.",
        }
    )


@api_bp.route("/csrf-token", methods=["GET"])
@csrf.exempt
def get_csrf_token():
    from flask_wtf.csrf import generate_csrf

    _is_prod = (
        os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or ""
    ).strip().lower() in {"prod", "production"}
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
    user_id = int(get_jwt_identity())
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
@jwt_required(optional=True)
@limiter.limit("10 per minute; 100 per day", key_func=_analyze_rate_limit_key)
def analyze():
    from flask import current_app

    payload = request.get_json(silent=True) or {}
    _raw_identity = get_jwt_identity()
    current_user_id = int(_raw_identity) if _raw_identity else None

    required_api_key = (os.environ.get("ANALYZE_API_KEY") or "").strip()
    provided_api_key = request.headers.get("X-API-Key", "").strip()
    if required_api_key and provided_api_key != required_api_key:
        SECURITY_METRICS["auth_failures"] += 1
        return jsonify(
            {"ok": False, "error": "Unauthorized. Missing or invalid API key."}
        ), 401

    code = payload.get("code")
    language = payload.get("language", "python")
    difficulty = payload.get("difficulty", "beginner")
    code_for_history = code if isinstance(code, str) else ""
    language_for_history = language if isinstance(language, str) else "python"

    if not isinstance(language, str) or language.lower() not in ALLOWED_LANGUAGES:
        _write_audit_log(
            current_user_id, language_for_history, code_for_history, had_error=True
        )
        return jsonify(
            {
                "ok": False,
                "error": "Invalid language. Supported values: python, javascript, java, c, cpp.",
            }
        ), 400
    language = language.lower()

    if (
        not isinstance(difficulty, str)
        or difficulty.lower() not in ALLOWED_DIFFICULTIES
    ):
        _write_audit_log(
            current_user_id, language_for_history, code_for_history, had_error=True
        )
        return jsonify(
            {
                "ok": False,
                "error": "Invalid difficulty. Supported values: beginner, intermediate, advanced.",
            }
        ), 400
    difficulty = difficulty.lower()

    if not isinstance(code, str) or not code.strip():
        _write_audit_log(current_user_id, language, code_for_history, had_error=True)
        return jsonify(
            {"ok": False, "error": "Invalid or missing 'code' field in request body."}
        ), 400

    abuse_hit = contains_abuse_pattern(code)
    if abuse_hit:
        SECURITY_METRICS["abuse_pattern_rejections"] += 1
        current_app.logger.warning(
            "Blocked analyze request due to abuse pattern: %s", abuse_hit
        )
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {"ok": False, "error": "Request blocked by security policy."}
        ), 400

    if len(code) > 102400:
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {"ok": False, "error": "Code exceeds maximum size limit of 100KB."}
        ), 400

    if language in AVAILABLE_TOOLS and not AVAILABLE_TOOLS[language]:
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {
                "ok": False,
                "error": f"Tools for language '{language}' are not installed on this server.",
                "suggestion": "Check the /tools endpoint for available languages or see README for setup.",
            }
        ), 422

    acquired = _ANALYZE_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        SECURITY_METRICS["concurrency_rejections"] += 1
        return jsonify(
            {"ok": False, "error": "Server is busy. Please retry shortly."}
        ), 503
    try:
        result = asyncio.run(
            analyze_code(code=code, language=language, difficulty=difficulty)
        )
        issues = result.get("issues", []) if isinstance(result, dict) else []
        execution = result.get("execution", {}) if isinstance(result, dict) else {}
        had_issue_error = any(
            isinstance(i, dict) and i.get("severity") == "error" for i in issues
        )
        had_execution_error = isinstance(execution, dict) and (
            bool(execution.get("error"))
            or int(execution.get("returncode", 0) or 0) != 0
        )
        if (
            isinstance(execution, dict)
            and isinstance(execution.get("error"), dict)
            and execution["error"].get("type") == "SandboxUnavailable"
        ):
            SECURITY_METRICS["sandbox_failures"] += 1
        _write_audit_log(
            current_user_id,
            language,
            code,
            had_error=(had_issue_error or had_execution_error),
        )
        return jsonify(result), 200
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Error during code analysis: %s", exc)
        _write_audit_log(current_user_id, language, code, had_error=True)
        return jsonify(
            {"ok": False, "error": "Internal server error during analysis."}
        ), 500
    finally:
        _ANALYZE_SEMAPHORE.release()


@api_bp.route("/analyze/github", methods=["POST"])
@jwt_required(optional=True)
@limiter.limit("5 per minute; 50 per day", key_func=_analyze_rate_limit_key)
def analyze_github():
    from flask import current_app

    payload = request.get_json(silent=True) or {}
    _raw_identity = get_jwt_identity()
    current_user_id = int(_raw_identity) if _raw_identity else None

    repo_url = payload.get("repo_url")
    if not isinstance(repo_url, str) or not repo_url.startswith("https://github.com/"):
        return jsonify({"ok": False, "error": "Invalid GitHub repository URL."}), 400

    acquired = _ANALYZE_SEMAPHORE.acquire(blocking=False)
    if not acquired:
        SECURITY_METRICS["concurrency_rejections"] += 1
        return jsonify({"ok": False, "error": "Server is busy. Please retry shortly."}), 503
        
    try:
        result = asyncio.run(analyze_repository(repo_url))
        
        # Log to audit (shallow)
        _write_audit_log(
            current_user_id,
            "github_repo",
            repo_url,
            had_error=not result.get("ok", False)
        )
        
        if not result.get("ok"):
            return jsonify(result), 400
            
        return jsonify(result), 200
    except Exception as exc:  # pragma: no cover
        current_app.logger.exception("Error during github repo analysis: %s", exc)
        return jsonify({"ok": False, "error": "Internal server error during analysis."}), 500
    finally:
        _ANALYZE_SEMAPHORE.release()
