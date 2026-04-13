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
from sqlalchemy.pool import NullPool, StaticPool


def _bool_env(key: str, default: bool = False) -> bool:
    return os.environ.get(key, str(default)).strip().lower() in ("1", "true", "yes")


def _is_prod() -> bool:
    return (
        os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or ""
    ).strip().lower() in {"prod", "production"}


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
    SECRET_KEY: str = (os.environ.get("SECRET_KEY") or "").strip() or secrets.token_hex(
        32
    )

    # CSRF
    WTF_CSRF_SECRET_KEY: str = (
        os.environ.get("WTF_CSRF_SECRET_KEY") or ""
    ).strip() or secrets.token_hex(32)
    WTF_CSRF_TIME_LIMIT: int = 3600
    WTF_CSRF_HEADERS: list = ["X-CSRFToken"]

    # JWT
    JWT_SECRET_KEY: str = (
        os.environ.get("JWT_SECRET_KEY") or ""
    ).strip() or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION: list = ["headers", "cookies"]
    JWT_COOKIE_CSRF_PROTECT: bool = False  # handled by Flask-WTF
    JWT_COOKIE_SAMESITE: str = "Lax"

    # Database
    _raw_db_url: str = (os.environ.get("DATABASE_URL") or "sqlite:///app.db").strip()
    SQLALCHEMY_DATABASE_URI: str = (
        _raw_db_url.replace("postgres://", "postgresql://", 1)
        if _raw_db_url.startswith("postgres://")
        else _raw_db_url
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # Rate limiting
    RATELIMIT_STORAGE_URI: str = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")


# Set pool options AFTER class definition so _db_engine_options() can be called cleanly
BaseConfig.SQLALCHEMY_ENGINE_OPTIONS = _db_engine_options(BaseConfig._raw_db_url)


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True
    JWT_COOKIE_SECURE: bool = False
    SESSION_COOKIE_SECURE: bool = False
    SESSION_COOKIE_HTTPONLY: bool = True
    SESSION_COOKIE_SAMESITE: str = "Lax"


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
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
            raise RuntimeError(
                "CRITICAL ERROR: SECRET_KEY environment variable MUST be set in Production!"
            )
        if not os.environ.get("JWT_SECRET_KEY"):
            raise RuntimeError(
                "CRITICAL ERROR: JWT_SECRET_KEY environment variable MUST be set in Production!"
            )


class TestingConfig(BaseConfig):
    """Used by pytest. Overrides point to an in-memory SQLite DB."""

    TESTING: bool = True
    DEBUG: bool = False

    # In-memory SQLite: StaticPool keeps all connections on the same DB
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
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
