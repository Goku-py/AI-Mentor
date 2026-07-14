"""
app_pkg/__init__.py — Application Factory.

Usage:
    from app_pkg import create_app
    app = create_app()           # DevelopmentConfig (default)
    app = create_app("testing")  # TestingConfig (pytest)
    app = create_app("production")
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from dotenv import load_dotenv

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    _HAS_SENTRY = True
except ImportError:
    _HAS_SENTRY = False

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from app_pkg.blueprints.api import _refresh_tools, api_bp
from app_pkg.blueprints.auth import auth_bp
from app_pkg.blueprints.debug_bp import debug_bp
from app_pkg.blueprints.static_files import static_bp
from app_pkg.cli import register_cli
from app_pkg.config import DevelopmentConfig, config_map
from app_pkg.extensions import (
    cors,
    csrf,
    db,
    get_redis_client,
    jwt,
    limiter,
    migrate,
    ping_redis,
    talisman,
)
from app_pkg.observability import init_observability
from app_pkg.security.middleware import init_security
from app_pkg.utils import allowed_origins, is_production

load_dotenv()


def _build_config_obj(config):
    """Resolve the config class from a string, class, or None."""
    if config is None:
        env = (
            (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "development")
            .strip()
            .lower()
        )
        return config_map.get(env, DevelopmentConfig)
    if isinstance(config, str):
        return config_map.get(config.lower(), DevelopmentConfig)
    return config


def _redis_storage_uri(db_num: int) -> str | None:
    _redis_url = (os.environ.get("REDIS_URL") or "").rstrip("/")
    if not _redis_url:
        return None

    parsed = urlparse(_redis_url)
    path = f"/{db_num}"
    query = f"?{parsed.query}" if parsed.query else ""
    if parsed.path:
        # Replace existing DB/path while preserving query string.
        return f"{parsed.scheme}://{parsed.netloc}{path}{query}"
    return f"{_redis_url}/{db_num}{query}"


def _init_extensions(app):
    """Bind Flask extensions and apply app-level config."""
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    _rate_limit_storage = (
        os.environ.get("RATE_LIMIT_STORAGE_URI")
        or _redis_storage_uri(0)
        or "memory://"
    )
    app.config.setdefault("RATELIMIT_STORAGE_URI", _rate_limit_storage)
    app.config.setdefault("RATELIMIT_DEFAULT", "200 per day; 50 per hour")
    limiter.init_app(app)

    _blacklist_storage = (
        os.environ.get("JWT_BLACKLIST_STORAGE_URI")
        or _redis_storage_uri(1)
        or "memory://"
    )
    app.config.setdefault("JWT_BLACKLIST_STORAGE_URI", _blacklist_storage)
    app.config.setdefault(
        "JWT_BLACKLIST_ENABLED",
        os.environ.get("JWT_BLACKLIST_ENABLED")
        or ("1" if _blacklist_storage.startswith("redis") else "0"),
    )
    if _blacklist_storage.startswith("redis"):
        get_redis_client()

    csrf.init_app(app)


def _configure_talisman(app, is_prod):
    """Apply security headers via Flask-Talisman."""
    talisman.init_app(
        app,
        force_https=is_prod,
        strict_transport_security=is_prod,
        strict_transport_security_max_age=31536000,
        content_security_policy={
            "default-src": "'self'",
            "base-uri": "'self'",
            "form-action": "'self'",
            "script-src": ["'self'"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:"],
            "font-src": "'self'",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
            "manifest-src": "'self'",
        },
        content_security_policy_nonce_in=[],
        referrer_policy="strict-origin-when-cross-origin",
        x_content_type_options=True,
        x_xss_protection=True,
        permissions_policy={
            "geolocation": "()",
            "microphone": "()",
            "camera": "()",
        },
    )


def _enforce_production_debug(app):
    """Force debug off in production and warn if FLASK_DEBUG env var is set."""
    if os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true"}:
        app.logger.warning(
            "FLASK_DEBUG env var is set but the app is in production mode. "
            "Forcing DEBUG=False. Delete FLASK_DEBUG from Railway dashboard."
        )
    app.debug = False
    app.env = "production"


def _verify_redis_connection(app):
    """In production, confirm Redis responds to PING before accepting traffic."""
    if not is_production():
        return
    if not ping_redis():
        msg = (
            "CRITICAL ERROR: Redis is unreachable in production. "
            "Verify REDIS_URL and ensure Redis is running."
        )
        app.logger.critical(msg)
        raise RuntimeError(msg)


def _configure_proxy_fix(app):
    """Apply ProxyFix middleware if TRUSTED_PROXY_COUNT is set."""
    _proxy_count = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    if _proxy_count > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=_proxy_count, x_proto=_proxy_count, x_host=_proxy_count,
        )


def _init_sentry():
    """Initialize Sentry SDK if configured."""
    if _HAS_SENTRY:
        dsn = os.environ.get("SENTRY_DSN")
        if dsn:
            sentry_sdk.init(
                dsn=dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.1,
                send_default_pii=False,
            )


def _configure_cors(app):
    cors.init_app(
        app,
        origins=allowed_origins(),
        methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-API-Key", "X-CSRFToken"],
        expose_headers=["X-CSRFToken"],
        supports_credentials=True,
        max_age=600,
    )


def _exempt_dev_csrf(app):
    """Exempt auth endpoints from CSRF in development."""
    for rule in app.url_map.iter_rules():
        if rule.endpoint and rule.endpoint.startswith("auth."):
            view_func = app.view_functions.get(rule.endpoint)
            if view_func:
                csrf.exempt(view_func)


def create_app(config=None) -> Flask:
    """Create and return a fully configured Flask application."""
    app = Flask(__name__, static_folder="../dist", static_url_path="")

    config_obj = _build_config_obj(config)
    app.config.from_object(config_obj)

    if hasattr(config_obj, "validate") and callable(config_obj.validate):
        with app.app_context():
            config_obj.validate()

    if is_production():
        from analyzer import sandbox_runtime_status  # noqa: PLC0415

        status = sandbox_runtime_status()
        if not status["ok"]:
            msg = (
                "CRITICAL ERROR: Docker sandbox is required in production but is unavailable. "
                f"Reason: {status.get('reason', 'unknown')}. "
                "Ensure the Docker daemon is running and accessible to the app."
            )
            app.logger.critical(msg)
            raise RuntimeError(msg)

    if is_production():
        _enforce_production_debug(app)

    _configure_proxy_fix(app)

    if is_production():
        _init_sentry()

    _init_extensions(app)
    _verify_redis_connection(app)

    _configure_cors(app)

    _configure_talisman(app, app.config.get("ENV") == "production" or is_production())

    init_security(app)
    init_observability(app)

    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(static_bp)
    if not is_production():
        app.register_blueprint(debug_bp)

    if app.config.get("ENV") == "development":
        _exempt_dev_csrf(app)

    register_cli(app)

    with app.app_context():
        if app.config.get("TESTING"):
            db.create_all()
        _refresh_tools()

    return app
