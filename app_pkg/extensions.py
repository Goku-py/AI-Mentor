"""
app_pkg/extensions.py — All Flask extensions instantiated without an app.

Extensions are bound to the app inside create_app() via init_app() calls.
This breaks the circular-import chain: blueprints import from here,
not from the app module.
"""

from __future__ import annotations

import os
import time
from typing import Any

from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from models_pkg import db  # single db instance shared by models and app

jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
migrate = Migrate()

# ---------------------------------------------------------------------------
# Redis connection pool (lazy — created on first use)
# ---------------------------------------------------------------------------
_redis_pool: Any = None


def get_redis_client():
    global _redis_pool  # noqa: PLW0603
    if _redis_pool is not None:
        return _redis_pool

    uri = os.environ.get("JWT_BLACKLIST_STORAGE_URI", "memory://")
    if not uri.startswith("redis"):
        return None

    try:
        import redis as _redis  # noqa: PLC0415
    except ImportError:
        return None

    _redis_pool = _redis.from_url(uri, decode_responses=True)
    return _redis_pool


# ---------------------------------------------------------------------------
# JWT token blacklist helpers
# ---------------------------------------------------------------------------
# In-memory fallback: {jti: expiry_timestamp}
_jwt_blacklist: dict[str, float] = {}


def jwt_blacklist_add(jti: str, expires_at: float | None = None) -> None:
    """Add a JWT's jti to the blacklist.

    Uses Redis when JWT_BLACKLIST_STORAGE_URI=redis://...,
    otherwise falls back to an in-memory dict (process-local only).
    """
    ttl = 900 if expires_at is None else max(1, int(expires_at - time.time()))
    client = get_redis_client()
    if client is not None:
        client.setex(f"jwt_blacklist:{jti}", ttl, "1")
    else:
        _jwt_blacklist[jti] = time.time() + ttl


def jwt_blacklist_check(jti: str) -> bool:
    """Return True if the JWT's jti has been blacklisted."""
    client = get_redis_client()
    if client is not None:
        return bool(client.get(f"jwt_blacklist:{jti}"))
    expiry = _jwt_blacklist.get(jti, 0)
    return time.time() < expiry


# ---------------------------------------------------------------------------
# Register JWT blacklist callback with flask-jwt-extended
# ---------------------------------------------------------------------------
@jwt.token_in_blocklist_loader
def _check_if_token_revoked(_jwt_header: dict, jwt_payload: dict) -> bool:
    jti = jwt_payload.get("jti", "")
    return jwt_blacklist_check(jti)


__all__ = [
    "csrf",
    "db",
    "get_redis_client",
    "jwt",
    "jwt_blacklist_add",
    "jwt_blacklist_check",
    "limiter",
    "migrate",
]
