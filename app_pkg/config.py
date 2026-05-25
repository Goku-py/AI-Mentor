"""
app_pkg/config.py — Configuration classes for every environment.

Usage in create_app():
    app.config.from_object(DevelopmentConfig)   # dev
    app.config.from_object(ProductionConfig)    # prod
    app.config.from_object(TestingConfig)       # pytest
"""

import os
import secrets
from datetime import timedelta
from typing import ClassVar

from sqlalchemy.pool import NullPool, StaticPool


def _bool_env(key: str, *, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).strip().lower() in ("1", "true", "yes")


def _is_prod() -> bool:
    return (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower() in {
        "prod",
        "production",
    }


def _db_engine_options(db_url: str) -> dict:
    """Return sensible SQLAlchemy engine options based on the DB type."""
    if "sqlite" in db_url:
        # SQLite is file-based — no connection pooling needed
        return {"poolclass": NullPool}
    # PostgreSQL / MySQL — use connection pool with health checks
    return {
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "10")),
        "pool_timeout": 30,
        "pool_recycle": 1800,  # recycle connections every 30 min (prevents stale conn)
        "pool_pre_ping": True,  # test connection before use (prevents "server closed" crashes)
    }


class BaseConfig:
    # Secret key
    SECRET_KEY: str = (os.environ.get("SECRET_KEY") or "").strip() or secrets.token_hex(32)

    # CSRF
    WTF_CSRF_SECRET_KEY: str = (
        os.environ.get("WTF_CSRF_SECRET_KEY") or ""
    ).strip() or secrets.token_hex(32)
    WTF_CSRF_TIME_LIMIT: int = 3600
    WTF_CSRF_HEADERS: ClassVar[list] = ["X-CSRFToken"]

    # JWT
    JWT_SECRET_KEY: str = (os.environ.get("JWT_SECRET_KEY") or "").strip() or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION: ClassVar[list] = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT: bool = True
    JWT_COOKIE_SAMESITE: str = "Lax"

    # Database
    _raw_db_url: str = (os.environ.get("DATABASE_URL") or "sqlite:///app.db").strip()
    SQLALCHEMY_DATABASE_URI: str = (
        _raw_db_url.replace("postgres://", "postgresql://", 1)
        if _raw_db_url.startswith("postgres://")
        else _raw_db_url
    )
    if "sqlite" not in _raw_db_url and "sslmode" not in _raw_db_url:
        if "?" in SQLALCHEMY_DATABASE_URI:
            SQLALCHEMY_DATABASE_URI += "&sslmode=require"
        else:
            SQLALCHEMY_DATABASE_URI += "?sslmode=require"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Rate limiting
    RATELIMIT_STORAGE_URI: str = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED: bool = True

    # ------------------------------------------------------------------
    # Sandbox Docker images (pinned by SHA256 digest for supply-chain security)
    #   Regenerate digests with:
    #     docker buildx imagetools inspect <image>:<tag> --format '{{.Manifest.Digest}}'
    #   Update all digests simultaneously after testing the new images.
    # ------------------------------------------------------------------
    SANDBOX_IMAGES: ClassVar[dict[str, str]] = {
        "python": os.environ.get(
            "SANDBOX_IMAGE_PYTHON",
            "python:3.11-slim@sha256:b5d546c4bec684141f6eeb38593911c1ef56ca14f481a14c8a45c89c822a2857",
        ),
        "javascript": os.environ.get(
            "SANDBOX_IMAGE_NODE",
            "node:18-slim@sha256:ddb3a1b4a81ee454c147b0e9f87baa9eee8468c11ed5fca1c33204f73d48f1ef",
        ),
        "gcc": os.environ.get(
            "SANDBOX_IMAGE_GCC",
            "gcc:12@sha256:2f73c112972f5cb109ef3d5281cd64be78576e3cc97b662cd156694a85ae1284",
        ),
        "java": os.environ.get(
            "SANDBOX_IMAGE_JAVA",
            "openjdk:17-slim@sha256:d78b76268a76f7f4d872faf78fdfff71e207cfd474f960572c3ab146e2640506",
        ),
    }

    # ------------------------------------------------------------------
    # Account lockout (auth hardening)
    # ------------------------------------------------------------------
    MAX_LOGIN_ATTEMPTS: int = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
    ACCOUNT_LOCKOUT_MINUTES: int = int(os.environ.get("ACCOUNT_LOCKOUT_MINUTES", "15"))

    # ------------------------------------------------------------------
    # JWT token blacklist (in-memory for dev, Redis for prod)
    # ------------------------------------------------------------------
    JWT_BLACKLIST_ENABLED: bool = _bool_env("JWT_BLACKLIST_ENABLED", default=False)
    JWT_BLACKLIST_STORAGE_URI: str = os.environ.get(
        "JWT_BLACKLIST_STORAGE_URI", "memory://"
    )


# Set pool options AFTER class definition so _db_engine_options() can be called cleanly
BaseConfig.SQLALCHEMY_ENGINE_OPTIONS = _db_engine_options(BaseConfig._raw_db_url)  # noqa: SLF001


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    JWT_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    MAX_CONTENT_LENGTH: int = 512 * 1024
    JWT_COOKIE_SECURE: bool = True
    SESSION_COOKIE_SECURE: bool = True
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"

    @classmethod
    def validate(cls):
        # Fail-fast in Production if critical secrets are not explicitly provided.
        # Otherwise, the BaseConfig fallback (secrets.token_hex) will silently
        # regenerate keys on every restart, logging all users out instantly.
        if not os.environ.get("SECRET_KEY"):
            msg = "CRITICAL ERROR: SECRET_KEY environment variable MUST be set in Production!"
            raise RuntimeError(msg)
        if not os.environ.get("JWT_SECRET_KEY"):
            msg = "CRITICAL ERROR: JWT_SECRET_KEY environment variable MUST be set in Production!"
            raise RuntimeError(msg)

        _flask_debug = os.environ.get("FLASK_DEBUG", "").strip().lower()
        if _flask_debug and _flask_debug not in {"0", "false", ""}:
            msg = (
                "CRITICAL ERROR: FLASK_DEBUG env var is set to a truthy value in Production. "
                "This enables the Werkzeug debugger, which allows arbitrary code execution. "
                "Delete the FLASK_DEBUG env var from Railway dashboard."
            )
            raise RuntimeError(msg)

        _db_url = (os.environ.get("DATABASE_URL") or "").strip()
        if "sqlite" in _db_url:
            msg = (
                "CRITICAL ERROR: DATABASE_URL points to SQLite in Production. "
                "SQLite does not support concurrent Gunicorn workers. "
                "Set DATABASE_URL to a PostgreSQL connection string."
            )
            raise RuntimeError(msg)

        allowed_origins = (os.environ.get("ALLOWED_ORIGINS") or "").strip()
        if allowed_origins == "*" or any(
            origin.strip() == "*" for origin in allowed_origins.split(",")
        ):
            msg = "CRITICAL ERROR: ALLOWED_ORIGINS must not be '*' in Production. Set an explicit allowlist."  # noqa: E501
            raise RuntimeError(msg)

        # Ensure sandbox images are pinned by SHA256 digest
        from flask import current_app  # noqa: PLC0415
        _images = current_app.config.get("SANDBOX_IMAGES", {})
        for lang, img in _images.items():
            if "@sha256:" not in img:
                msg = (
                    f"CRITICAL ERROR: Sandbox image for '{lang}' ({img}) "
                    "is not pinned by SHA256 digest. Append @sha256:<digest>."
                )
                raise RuntimeError(msg)

        cls._warn_redis_config()

    @classmethod
    def _warn_redis_config(cls):
        from flask import current_app  # noqa: PLC0415

        _rate_limit_uri = (os.environ.get("RATE_LIMIT_STORAGE_URI") or "memory://").strip()
        if "memory" in _rate_limit_uri:
            current_app.logger.warning(
                "RATE_LIMIT_STORAGE_URI is set to in-memory storage in Production. "
                "Each Gunicorn worker tracks rate limits independently, making limits "
                "per-worker instead of global. Add a Redis plugin in Railway dashboard "
                "and set RATE_LIMIT_STORAGE_URI to a Redis URL."
            )

        _blacklist_enabled = os.environ.get("JWT_BLACKLIST_ENABLED", "0").strip()
        if _blacklist_enabled not in {"1", "true", "yes"}:
            current_app.logger.warning(
                "JWT_BLACKLIST_ENABLED is not set to 1 in Production. "
                "Logout does not invalidate JWT tokens. Add a Redis plugin in Railway "
                "dashboard, set JWT_BLACKLIST_STORAGE_URI to a Redis URL, "
                "and set JWT_BLACKLIST_ENABLED=1."
            )
        elif "memory" in (os.environ.get("JWT_BLACKLIST_STORAGE_URI") or "memory://"):
            current_app.logger.warning(
                "JWT_BLACKLIST_STORAGE_URI is set to in-memory storage in Production. "
                "JWT blacklist is process-local and lost on restart. "
                "Set JWT_BLACKLIST_STORAGE_URI to a Redis URL."
            )


class TestingConfig(BaseConfig):
    """Used by pytest. Overrides point to an in-memory SQLite DB."""

    TESTING: bool = True
    DEBUG: bool = False

    # In-memory SQLite: StaticPool keeps all connections on the same DB
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: ClassVar[dict] = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    WTF_CSRF_ENABLED: bool = False  # no CSRF token needed in test client
    RATELIMIT_ENABLED: bool = False  # disable per-test rate-limit pollution
    JWT_COOKIE_SECURE: bool = False  # allow cookies over HTTP in tests


# Map name → class for create_app(config_name="testing") style
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
