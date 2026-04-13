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

from flask import Flask
from flask_cors import CORS
from flask_talisman import Talisman
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from app_pkg.config import DevelopmentConfig, config_map
from app_pkg.extensions import csrf, db, jwt, limiter, migrate
from app_pkg.observability import init_observability
from app_pkg.security.middleware import init_security
from app_pkg.cli import register_cli
from app_pkg.blueprints.api import api_bp, _refresh_tools
from app_pkg.blueprints.auth import auth_bp
from app_pkg.blueprints.debug_bp import debug_bp
from app_pkg.blueprints.static_files import static_bp

load_dotenv()


def create_app(config=None) -> Flask:
    """Create and return a fully configured Flask application.

    Args:
        config: A config class, a string key ("testing", "production"),
                or None (falls back to DevelopmentConfig).
    """
    app = Flask(__name__, static_folder="../dist", static_url_path="")

    # --- Resolve config ---
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

    # Validate configuration (fail-fast checks for production)
    if hasattr(config_obj, "validate") and callable(config_obj.validate):
        config_obj.validate()

    # --- Proxy fix (trust X-Forwarded-For on cloud platforms) ---
    _proxy_count = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
    if _proxy_count > 0:
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=_proxy_count,
            x_proto=_proxy_count,
            x_host=_proxy_count,
        )

    # --- Bind extensions to app ---
    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)  # Flask-Migrate (Alembic) — enables 'flask db' commands

    _rate_limit_storage = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")
    limiter.init_app(app)
    app.config.setdefault("RATELIMIT_STORAGE_URI", _rate_limit_storage)
    app.config.setdefault("RATELIMIT_DEFAULT", ["200 per day", "50 per hour"])

    csrf.init_app(app)

    # CORS
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
        allow_headers=["Content-Type", "X-API-Key", "X-CSRFToken"],
        supports_credentials=True,
        max_age=600,
    )

    # Talisman (security headers)
    _is_prod = app.config.get("ENV") == "production" or (
        (os.environ.get("FLASK_ENV") or os.environ.get("APP_ENV") or "").strip().lower()
        in {"prod", "production"}
    )
    Talisman(
        app,
        force_https=_is_prod,
        strict_transport_security=_is_prod,
        strict_transport_security_max_age=31536000,
        content_security_policy={
            "default-src": "'self'",
            "script-src": ["'self'", "'unsafe-inline'"],
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": ["'self'", "data:"],
            "font-src": "'self'",
            "connect-src": "'self'",
            "frame-ancestors": "'none'",
        },
        content_security_policy_nonce_in=[],
        referrer_policy="strict-origin-when-cross-origin",
        x_content_type_options=True,
        x_xss_protection=True,
        feature_policy={
            "geolocation": "'none'",
            "microphone": "'none'",
            "camera": "'none'",
        },
    )

    # --- Security middleware (bot blocker, 429 handler) ---
    init_security(app)

    # --- Observability (structured logging, request ID, timing) ---
    init_observability(app)

    # --- Blueprints ---
    app.register_blueprint(api_bp)
    app.register_blueprint(auth_bp)
    csrf.exempt(auth_bp)
    app.register_blueprint(debug_bp)
    app.register_blueprint(static_bp)

    # --- CLI management commands ---
    register_cli(app)

    # --- DB tables + tool cache ---
    with app.app_context():
        if app.config.get("TESTING"):
            # Tests use in-memory SQLite — skip migrations, create tables directly
            db.create_all()
        # In dev/prod: run 'flask db upgrade' to apply migrations
        _refresh_tools()

    return app
