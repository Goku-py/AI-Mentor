"""
models_pkg/__init__.py — Public API for the models package.

Usage anywhere in the app:
    from models_pkg import db, User, AuditLog
"""

from .audit_log import AuditLog
from .extensions import db
from .user import VALID_ROLES, User

__all__ = ["VALID_ROLES", "AuditLog", "User", "db"]
