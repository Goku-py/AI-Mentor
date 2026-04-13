"""
app_pkg/observability.py — Structured logging, request tracing, and timing.

Provides:
  - JSON-formatted log output (machine-readable for Datadog, CloudWatch, etc.)
  - Unique X-Request-ID on every request (stored in flask.g, injected into response)
  - Per-request timing logged at INFO level after every response
  - APP_START_TIME for uptime calculation in /health

Wire into create_app():
    from app_pkg.observability import init_observability
    init_observability(app)
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from datetime import datetime, timezone

from flask import Flask, g, request

try:
    from pythonjsonlogger import json as jsonlogger  # v3 path

    _HAS_JSON_LOGGER = True
except ImportError:
    try:
        from pythonjsonlogger import jsonlogger  # v2 fallback

        _HAS_JSON_LOGGER = True
    except ImportError:  # pragma: no cover
        _HAS_JSON_LOGGER = False

# Set at app startup — used by /health to compute uptime_seconds
APP_START_TIME: float = time.monotonic()

# App version — override with APP_VERSION env var in CI/CD
APP_VERSION: str = os.environ.get("APP_VERSION", "1.0.0")


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
class _RequestContextFilter(logging.Filter):
    """Inject request_id into every log record emitted inside a request context."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.request_id = g.get("request_id", "-")  # type: ignore[union-attr]
        except RuntimeError:
            # Outside an application context (e.g. startup logs)
            record.request_id = "-"
        return True


def _configure_json_logging(app: Flask) -> None:
    """Replace the default Flask/Werkzeug log handlers with a JSON formatter."""
    if not _HAS_JSON_LOGGER:
        app.logger.warning(
            "python-json-logger not installed — falling back to plain text logs"
        )
        return

    fmt = "%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s"
    formatter = jsonlogger.JsonFormatter(
        fmt=fmt,
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )

    context_filter = _RequestContextFilter()

    # Apply to Flask app logger
    if not app.logger.handlers:
        handler = logging.StreamHandler()
        app.logger.addHandler(handler)

    for handler in app.logger.handlers:
        handler.setFormatter(formatter)
        handler.addFilter(context_filter)

    # Silence noisy Werkzeug access log (we emit our own structured log)
    werkzeug_logger = logging.getLogger("werkzeug")
    werkzeug_logger.setLevel(logging.ERROR)

    app.logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Request lifecycle hooks
# ---------------------------------------------------------------------------
def _register_request_hooks(app: Flask) -> None:
    """Register before/after request hooks for ID generation and timing."""

    @app.before_request
    def _start_request():
        g.request_id = secrets.token_hex(8)
        g.start_time = time.monotonic()

    @app.after_request
    def _finish_request(response):
        duration_ms = round(
            (time.monotonic() - g.get("start_time", time.monotonic())) * 1000, 1
        )
        request_id = g.get("request_id", "-")

        # Inject request ID into response header so clients can reference it
        response.headers["X-Request-ID"] = request_id

        # Skip logging static assets (reduce noise)
        path = request.path
        if not path.startswith("/api/"):
            return response

        app.logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "ip": request.remote_addr,
                "user_agent": request.user_agent.string[:120]
                if request.user_agent.string
                else "-",
            },
        )
        return response


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def init_observability(app: Flask) -> None:
    """Configure structured logging and request tracing on the Flask app."""
    global APP_START_TIME
    APP_START_TIME = time.monotonic()
    _configure_json_logging(app)
    _register_request_hooks(app)
    app.logger.info(
        "server_start",
        extra={
            "version": APP_VERSION,
            "env": os.environ.get("FLASK_ENV", "development"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
