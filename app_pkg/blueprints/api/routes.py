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

import os
import secrets
import threading
import time

from flask import Blueprint, Response, current_app, jsonify, request, url_for
from flask_jwt_extended import get_jwt_identity, jwt_required, verify_jwt_in_request
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import generate_csrf
from sqlalchemy import text

from analyzer import analyze_code, sandbox_runtime_status, verify_tools
from app_pkg.extensions import csrf, db, get_rq_queue, limiter
from app_pkg.observability import APP_START_TIME, APP_VERSION
from app_pkg.security.middleware import (
    contains_abuse_pattern,
    get_security_metric,
    increment_security_metric,
)
from app_pkg.utils import coerce_jwt_identity, is_production
from models_pkg import AuditLog

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.after_request
def _add_version_header(response: Response) -> Response:
    response.headers["X-API-Version"] = APP_VERSION
    return response


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
ALLOWED_LANGUAGES = {"python", "javascript", "js", "java", "c", "cpp", "c++"}
ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced"}
SESSION_HISTORY_MAX_RETURNED = 10
_DEFAULT_MAX_ANALYZE_CONCURRENCY = max(4, (os.cpu_count() or 2) * 2)
MAX_ANALYZE_CONCURRENCY = max(
    1,
    int(os.environ.get("MAX_ANALYZE_CONCURRENCY", str(_DEFAULT_MAX_ANALYZE_CONCURRENCY))),
)
_ANALYZE_SEMAPHORE = threading.BoundedSemaphore(value=MAX_ANALYZE_CONCURRENCY)


def _async_analyze_enabled() -> bool:
    """Return True when background-job analysis is enabled via env var."""
    return os.environ.get("ASYNC_ANALYZE_ENABLED", "").strip().lower() in ("1", "true", "yes")

# Cache available tools on startup (avoid repeated subprocess checks)
AVAILABLE_TOOLS: dict = {}

# TTL cache for tool availability checks.
_TOOLS_CACHE: dict[str, bool] | None = None
_TOOLS_CACHE_TIME: float = 0.0
_TOOLS_CACHE_TTL_SECONDS: float = 60.0
_TOOLS_CACHE_LOCK = threading.Lock()


def _get_available_tools() -> dict[str, bool]:
    """Return cached tools if fresh, otherwise refresh via verify_tools()."""
    global _TOOLS_CACHE, _TOOLS_CACHE_TIME  # noqa: PLW0603

    now = time.monotonic()
    with _TOOLS_CACHE_LOCK:
        if (
            _TOOLS_CACHE is not None
            and now - _TOOLS_CACHE_TIME < _TOOLS_CACHE_TTL_SECONDS
        ):
            return dict(_TOOLS_CACHE)

    tools = verify_tools()
    with _TOOLS_CACHE_LOCK:
        _TOOLS_CACHE = dict(tools)
        _TOOLS_CACHE_TIME = now
    return tools


def _refresh_tools() -> None:
    """Force-refresh the tool availability cache immediately."""
    global AVAILABLE_TOOLS  # noqa: PLW0603
    tools = verify_tools()
    AVAILABLE_TOOLS = tools
    with _TOOLS_CACHE_LOCK:
        global _TOOLS_CACHE, _TOOLS_CACHE_TIME  # noqa: PLW0603
        _TOOLS_CACHE = dict(tools)
        _TOOLS_CACHE_TIME = time.monotonic()


def _metrics_access_allowed() -> bool:
    key = (os.environ.get("METRICS_API_KEY") or "").strip()
    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower()
    if key:
        provided = (request.headers.get("X-API-Key") or "").strip()
        return secrets.compare_digest(key, provided)
    return env not in {"prod", "production"}


# ---------------------------------------------------------------------------
# Rate-limit key + tiered limits: per user ID when logged in, else per IP
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


def _analyze_rate_limit() -> str:
    """Return stricter limits for unauthenticated requests."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:  # noqa: BLE001
        return "5 per minute; 50 per day"
    user_id = get_jwt_identity()
    if user_id:
        return "10 per minute; 200 per day"
    return "5 per minute; 50 per day"


# ---------------------------------------------------------------------------
# Audit log helpers
# ---------------------------------------------------------------------------
def _write_audit_log_sync(
    user_id: int | None, language: str, code: str, *, had_error: bool
) -> None:
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


def _write_audit_log_async(
    user_id: int | None, language: str, code: str, *, had_error: bool
) -> None:
    """Spawn a background thread to write the audit log without blocking the response."""
    app = current_app._get_current_object()  # noqa: SLF001

    def _target() -> None:
        with app.app_context():
            _write_audit_log_sync(user_id, language, code, had_error=had_error)

    threading.Thread(target=_target, daemon=True).start()


def _write_audit_log(user_id: int | None, language: str, code: str, *, had_error: bool) -> None:
    """Async entry point for audit logging.

    In tests the write is performed synchronously for deterministic history
    assertions; production/development use a background thread.
    """
    if current_app.config.get("TESTING"):
        _write_audit_log_sync(user_id, language, code, had_error=had_error)
    else:
        _write_audit_log_async(user_id, language, code, had_error=had_error)


def _build_analyze_response(result: dict, language: str, execution_time_ms: int) -> tuple[dict, int]:
    """Convert the raw analyze_code result into the public API response."""
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
        increment_security_metric("sandbox_failures")

    if not result.get("ok", True) and result.get("error"):
        return (
            {
                "success": False,
                "output": "",
                "error": result.get("error"),
                "meta": {"language": language},
            },
            200,
        )

    success = not (had_issue_error or had_execution_error)
    output = execution.get("stdout", "")
    error_str = ""

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

    if result.get("mismatch"):
        output = result.get("output", output)
        success = False
        error_str = "Language mismatch detected."

    return {"success": success, "output": output, "error": error_str, "meta": meta_info}, 200


def _run_analyze_sync(code: str, language: str, difficulty: str, user_id: int | None) -> tuple[dict, int]:
    """Synchronous analysis path with per-process concurrency limiting."""
    acquired = _ANALYZE_SEMAPHORE.acquire(blocking=True, timeout=5)
    if not acquired:
        increment_security_metric("concurrency_rejections")
        return (
            {
                "success": False,
                "output": "",
                "error": "Server is busy. Please retry shortly.",
                "meta": {"language": language},
            },
            503,
        )
    try:
        t0 = time.monotonic()
        result = analyze_code(code=code, language=language, difficulty=difficulty)
        execution_time_ms = int((time.monotonic() - t0) * 1000)

        issues = result.get("issues", []) if isinstance(result, dict) else []
        execution = result.get("execution", {}) if isinstance(result, dict) else {}
        had_issue_error = any(isinstance(i, dict) and i.get("severity") == "error" for i in issues)
        had_execution_error = isinstance(execution, dict) and (
            bool(execution.get("error")) or int(execution.get("returncode", 0) or 0) != 0
        )
        _write_audit_log(
            user_id,
            language,
            code,
            had_error=(had_issue_error or had_execution_error),
        )

        return _build_analyze_response(result, language, execution_time_ms)
    except Exception:  # pragma: no cover
        current_app.logger.exception("Error during code analysis")
        _write_audit_log(user_id, language, code, had_error=True)
        return (
            {
                "success": False,
                "output": "",
                "error": "Internal server error during analysis.",
                "meta": {"language": language},
            },
            500,
        )
    finally:
        _ANALYZE_SEMAPHORE.release()


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
        "available_tools": _get_available_tools(),
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
        f"ai_mentor_abuse_pattern_rejections_total"
        f" {get_security_metric('abuse_pattern_rejections')}",
        "",
        "# HELP ai_mentor_blocked_automated_clients_total Total bot/scraper requests blocked",
        "# TYPE ai_mentor_blocked_automated_clients_total counter",
        f"ai_mentor_blocked_automated_clients_total"
        f" {get_security_metric('blocked_automated_clients')}",
        "",
        "# HELP ai_mentor_auth_failures_total Total API key auth failures",
        "# TYPE ai_mentor_auth_failures_total counter",
        f"ai_mentor_auth_failures_total {get_security_metric('auth_failures')}",
        "",
        "# HELP ai_mentor_concurrency_rejections_total Total requests rejected due to concurrency limit",  # noqa: E501
        "# TYPE ai_mentor_concurrency_rejections_total counter",
        f"ai_mentor_concurrency_rejections_total"
        f" {get_security_metric('concurrency_rejections')}",
        "",
        "# HELP ai_mentor_sandbox_failures_total Total sandbox unavailable events",
        "# TYPE ai_mentor_sandbox_failures_total counter",
        f"ai_mentor_sandbox_failures_total {get_security_metric('sandbox_failures')}",
        "",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4; charset=utf-8")


@api_bp.route("/tools", methods=["GET"])
def tools():
    return jsonify(
        {
            "available": _get_available_tools(),
            "message": "Tools marked as 'false' are not installed. See README for setup instructions.",  # noqa: E501
        },
    )


@api_bp.route("/csrf-token", methods=["GET"])
@csrf.exempt
def get_csrf_token():
    token = generate_csrf()
    response = jsonify({"csrf_token": token})
    response.set_cookie(
        "csrftoken",
        token,
        httponly=False,
        samesite="Lax",
        secure=is_production(),
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
@limiter.limit(_analyze_rate_limit, key_func=_analyze_rate_limit_key)
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
        increment_security_metric("auth_failures")
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
        increment_security_metric("abuse_pattern_rejections")
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

    available_tools = _get_available_tools()
    if language in available_tools and not available_tools[language]:
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

    if _async_analyze_enabled():
        from app_pkg.jobs.analyze_job import run_analyze_job  # noqa: PLC0415

        queue = get_rq_queue()
        job = queue.enqueue(
            run_analyze_job,
            code,
            language,
            difficulty,
            current_user_id,
            job_timeout=int(os.environ.get("RQ_WORKER_TIMEOUT", "300")),
        )
        poll_url = url_for("api.analyze_status", job_id=job.id, _external=False)
        return jsonify(
            {
                "ok": True,
                "job_id": job.id,
                "status": "queued",
                "poll_url": poll_url,
            },
        ), 202

    response_payload, status_code = _run_analyze_sync(
        code=code, language=language, difficulty=difficulty, user_id=current_user_id
    )
    return jsonify(response_payload), status_code


@api_bp.route("/analyze/status/<job_id>", methods=["GET"])
def analyze_status(job_id: str):
    """Return the status and result of an asynchronous /analyze job."""
    queue = get_rq_queue()
    if queue is None:
        return jsonify({"ok": False, "error": "Async processing is unavailable."}), 503

    try:
        from rq.job import Job  # noqa: PLC0415
        job = Job.fetch(job_id, connection=queue.connection)
    except Exception:  # noqa: BLE001
        return jsonify({"ok": False, "error": "Job not found."}), 404

    status = job.get_status()
    payload: dict = {
        "ok": True,
        "job_id": job_id,
        "status": status,
    }
    if status == "finished":
        result = job.result
        if isinstance(result, dict):
            payload["result"] = result
        else:
            payload["result"] = {"success": False, "error": "Invalid job result."}
    elif status == "failed":
        payload["error"] = "Job failed."
    return jsonify(payload), 200
