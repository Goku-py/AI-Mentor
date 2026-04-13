"""models_pkg/audit_log.py — AuditLog model."""

from __future__ import annotations
from datetime import datetime, timezone
from .extensions import db


class AuditLog(db.Model):
    """One row per /api/v1/analyze call.

    Stores the first 200 chars of code only — never the full submission
    (storage efficiency + GDPR hygiene).
    """

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    language = db.Column(db.String(20), nullable=False)
    had_error = db.Column(db.Boolean, nullable=False, default=False)
    code_snippet = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    # Observability & Cost
    prompt_tokens = db.Column(db.Integer, default=0, nullable=False)
    completion_tokens = db.Column(db.Integer, default=0, nullable=False)
    total_tokens = db.Column(db.Integer, default=0, nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "language": self.language,
            "had_error": self.had_error,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "tokens": getattr(self, "total_tokens", 0),
        }
