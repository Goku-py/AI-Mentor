"""
models_pkg/extensions.py — Single SQLAlchemy instance for the models package.

Imported by user.py and audit_log.py so they don't need to know about
the Flask app at import time (avoids circular imports).
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
