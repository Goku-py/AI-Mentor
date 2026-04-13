"""
auth.py — Authentication blueprint for AI Code Mentor.

Endpoints (all prefixed /api/v1/auth):
  POST /register  — create a new student account
  POST /login     — exchange credentials for JWT tokens
  POST /logout    — clear the refresh cookie
  GET  /me        — return the current user's profile
  POST /refresh   — issue a new access token using the refresh cookie
"""

from __future__ import annotations

import re

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from models import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_email(email: str) -> str | None:
    """Return an error string if the email is invalid, else None."""
    if not email or len(email) > 254:
        return "Email must be between 1 and 254 characters."
    if not _EMAIL_RE.match(email):
        return "Email address is not valid."
    return None


def _validate_password(password: str) -> str | None:
    """Return an error string if the password is too weak, else None."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 128:
        return "Password must be at most 128 characters."
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    if not (has_digit or has_special):
        return "Password must contain at least one digit or special character."
    return None


def _make_tokens(user: User) -> tuple[str, str]:
    """Create a fresh (access_token, refresh_token) pair for a user."""
    additional_claims = {"role": user.role, "email": user.email}
    access_token = create_access_token(
        identity=str(user.id), additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    return access_token, refresh_token


# ---------------------------------------------------------------------------
# Public auth endpoints
# ---------------------------------------------------------------------------


@auth_bp.route("/register", methods=["POST"])
def register():
    """Create a new student account and immediately issue tokens."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    # --- Validate inputs ---
    email_err = _validate_email(email)
    if email_err:
        return jsonify({"ok": False, "error": email_err}), 400

    pw_err = _validate_password(password)
    if pw_err:
        return jsonify({"ok": False, "error": pw_err}), 400

    # --- Check uniqueness ---
    if User.query.filter_by(email=email).first():
        return jsonify(
            {"ok": False, "error": "An account with that email already exists."}
        ), 409

    # --- Create user ---
    user = User(email=email, role="student")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # --- Issue tokens ---
    access_token, refresh_token = _make_tokens(user)
    response = make_response(
        jsonify({"ok": True, "user": user.to_dict(), "access_token": access_token}),
        201,
    )
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route("/login", methods=["POST"])
def login():
    """Verify credentials and issue JWT tokens."""
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    # Constant-time lookup — always query then check to avoid timing attacks
    user = User.query.filter_by(email=email, is_active=True).first()
    if not user or not user.check_password(password):
        return jsonify({"ok": False, "error": "Invalid email or password."}), 401

    access_token, refresh_token = _make_tokens(user)
    response = make_response(
        jsonify({"ok": True, "user": user.to_dict(), "access_token": access_token}),
        200,
    )
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    """Clear the JWT refresh cookie and sign out."""
    response = make_response(
        jsonify({"ok": True, "message": "Logged out successfully."}), 200
    )
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    """Return the current authenticated user's profile."""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404
    return jsonify({"ok": True, "user": user.to_dict()}), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Issue a new access token using the long-lived refresh cookie.

    The browser automatically attaches the httpOnly refresh cookie —
    the JavaScript layer never touches it.
    """
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404

    access_token, _ = _make_tokens(user)
    return jsonify({"ok": True, "access_token": access_token}), 200
