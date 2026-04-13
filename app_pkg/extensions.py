"""
app_pkg/extensions.py — All Flask extensions instantiated without an app.

Extensions are bound to the app inside create_app() via init_app() calls.
This breaks the circular-import chain: blueprints import from here,
not from the app module.
"""

from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_talisman import Talisman
from flask_wtf.csrf import CSRFProtect

from models_pkg import db  # single db instance shared by models and app

jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
cors = CORS()
talisman = Talisman()
migrate = Migrate()

__all__ = ["db", "jwt", "limiter", "csrf", "cors", "talisman", "migrate"]
