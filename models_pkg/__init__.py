"""
models_pkg/__init__.py — Public API for the models package.

Usage anywhere in the app:
    from models_pkg import db, User, AuditLog
"""

from .extensions import db
from .user import User, VALID_ROLES
from .audit_log import AuditLog

__all__ = ["db", "User", "AuditLog", "VALID_ROLES"]
