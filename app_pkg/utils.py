"""
app_pkg/utils.py — Shared utility functions used across blueprints.
"""

from __future__ import annotations


def coerce_jwt_identity(raw_identity: object) -> int | None:
    """Convert a JWT subject claim to an integer user ID, or None if invalid."""
    try:
        return int(raw_identity)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
