"""
models.py — SQLAlchemy database models for AI Code Mentor.

Tables:
  users      — registered user accounts (student / teacher / admin)
  audit_logs — one row per /analyze call, linked to the user who made it
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# All accepted role values
VALID_ROLES: frozenset = frozenset({"student", "teacher", "admin"})


class User(db.Model):
    """A registered user account."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student")
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Relationship — lazy=dynamic lets us call .filter() on audit_logs
    audit_logs = db.relationship("AuditLog", backref="user", lazy="dynamic")

    # ------------------------------------------------------------------
    # Password helpers
    # ------------------------------------------------------------------
    def set_password(self, password: str) -> None:
        """Hash and store a plain-text password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plain-text password against the stored hash."""
        return check_password_hash(self.password_hash, password)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------
    def to_dict(self) -> dict:
        """Return a safe public dict (no password hash)."""
        return {
            "id": self.id,
            "email": self.email,
            "role": self.role,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AuditLog(db.Model):
    """One row per /api/v1/analyze invocation.

    Stores the first 200 chars of code as a lightweight breadcrumb;
    NOT the full code — that would be a GDPR / storage liability.
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    # Nullable so we can log unauthenticated requests in the future
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    language = db.Column(db.String(20), nullable=False)
    had_error = db.Column(db.Boolean, nullable=False, default=False)
    # Snippet only — do NOT store full code
    code_snippet = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "language": self.language,
            "had_error": self.had_error,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
