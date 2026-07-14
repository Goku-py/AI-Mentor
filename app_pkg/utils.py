"""
app_pkg/utils.py — Shared utility functions used across blueprints.
"""

from __future__ import annotations

import os


def coerce_jwt_identity(raw_identity: object) -> int | None:
    try:
        return int(raw_identity)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def is_production() -> bool:
    """Return True if the app is running in production.

    Checks the active Flask app config first, then falls back to env vars.
    This avoids accidental production-gate bypass when `create_app('production')`
    is called without setting FLASK_ENV=production.
    """
    try:
        from flask import current_app  # noqa: PLC0415

        if current_app:
            config_env = str(current_app.config.get("ENV") or "").strip().lower()
            if config_env in {"prod", "production"}:
                return True
    except Exception:  # noqa: BLE001
        pass

    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower()
    return env in {"prod", "production"}


def allowed_origins() -> list[str] | str:
    """Parse ALLOWED_ORIGINS env var into a list or wildcard."""
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
    if raw == "*":
        return "*"
    return [o.strip() for o in raw.split(",") if o.strip()]
