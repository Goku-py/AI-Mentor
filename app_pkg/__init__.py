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

from dotenv import load_dotenv

try:
    import sentry_sdk
    from sentry_sdk.integrations.flask import FlaskIntegration

    _HAS_SENTRY = True
except ImportError:
    _HAS_SENTRY = False

from flask import Flask
from flask_cors import CORS
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix

from app_pkg.blueprints.api import _refresh_tools, api_bp
from app_pkg.blueprints.auth import auth_bp
from app_pkg.blueprints.debug_bp import debug_bp
from app_pkg.blueprints.static_files import static_bp
from app_pkg.cli import register_cli
from app_pkg.config import DevelopmentConfig, ProductionConfig, config_map
from app_pkg.extensions import (
    csrf,
    db,
    get_redis_client,
    jwt,
    limiter,
    migrate,
)
from app_pkg.observability import init_observability
from app_pkg.security.middleware import init_security

load_dotenv()


def _redis_storage_uri(db_num: int) -> str | None:
    _redis_url = (os.environ.get("REDIS_URL") or "").rstrip("/")
    if _redis_url:
        return f"{_redis_url}/{db_num}"
    return None


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
    app.config["RATELIMIT_STORAGE_URI"] = _rate_limit_storage
    app.config.setdefault("RATELIMIT_DEFAULT", "200 per day; 50 per hour")
    limiter.init_app(app)

    _blacklist_storage = (
        os.environ.get("JWT_BLACKLIST_STORAGE_URI")
        or _redis_storage_uri(1)
        or "memory://"
    )
    app.config["JWT_BLACKLIST_STORAGE_URI"] = _blacklist_storage
    _blacklist_env = os.environ.get("JWT_BLACKLIST_ENABLED", "").strip().lower()
    app.config["JWT_BLACKLIST_ENABLED"] = (
        _blacklist_env in ("1", "true", "yes")
        or ("1" if _redis_storage_uri(1) else "0")
    )
    if _blacklist_storage.startswith("redis"):
        get_redis_client()

    csrf.init_app(app)


def _configure_talisman(app, is_prod):
    """Apply security headers via Flask-Talisman."""
    Talisman(
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


def _is_production_env():
    env = (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower()
    return env in {"prod", "production"}


def _enforce_production_debug(app):
    """Force debug off in production and warn if FLASK_DEBUG env var is set."""
    if os.environ.get("FLASK_DEBUG", "").strip().lower() in {"1", "true"}:
        app.logger.warning(
            "FLASK_DEBUG env var is set but the app is in production mode. "
            "Forcing DEBUG=False. Delete FLASK_DEBUG from Railway dashboard."
        )
    app.debug = False
    app.env = "production"


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
    """Set up CORS from ALLOWED_ORIGINS env var."""
    _allowed_origins = os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173")
    _cors_origins = (
        [o.strip() for o in _allowed_origins.split(",") if o.strip()]
        if _allowed_origins != "*"
        else "*"
    )
    CORS(
        app,
        origins=_cors_origins,
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

    if config is None:
        env = (
            (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "development")
            .strip()
            .lower()
        )
        config_obj = config_map.get(env, DevelopmentConfig)
    elif isinstance(config, str):
        config_obj = config_map.get(config.lower(), DevelopmentConfig)
    else:
        config_obj = config
    app.config.from_object(config_obj)

    if hasattr(config_obj, "validate") and callable(config_obj.validate):
        with app.app_context():
            config_obj.validate()

    is_prod = _is_production_env() or isinstance(config_obj, ProductionConfig)

    if is_prod:
        _enforce_production_debug(app)

    _configure_proxy_fix(app)

    if is_prod:
        _init_sentry()

    _init_extensions(app)

    _configure_cors(app)
    _configure_talisman(app, is_prod)

    init_security(app)
    init_observability(app)

    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(static_bp)
    if not is_prod:
        app.register_blueprint(debug_bp)

    if app.config.get("ENV") == "development":
        _exempt_dev_csrf(app)

    register_cli(app)

    with app.app_context():
        if app.config.get("TESTING"):
            db.create_all()
        _refresh_tools()

    return app
