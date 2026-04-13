"""app_pkg/blueprints/auth/routes.py — Authentication blueprint.

Endpoints (all prefixed /api/v1/auth):
  POST /register  — create a new student account
  POST /login     — exchange credentials for JWT tokens
  POST /logout    — clear the refresh cookie
  GET  /me        — return the current user's profile
  POST /refresh   — issue a new access token using the refresh cookie
"""

from __future__ import annotations
import os
import re
import requests

from flask import Blueprint, jsonify, make_response, request, redirect
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from models_pkg import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_email(email: str) -> str | None:
    if not email or len(email) > 254:
        return "Email must be between 1 and 254 characters."
    if not _EMAIL_RE.match(email):
        return "Email address is not valid."
    return None


def _validate_password(password: str) -> str | None:
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
    additional_claims = {"role": user.role, "email": user.email}
    access_token = create_access_token(
        identity=str(user.id), additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    return access_token, refresh_token


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    email_err = _validate_email(email)
    if email_err:
        return jsonify({"ok": False, "error": email_err}), 400

    pw_err = _validate_password(password)
    if pw_err:
        return jsonify({"ok": False, "error": pw_err}), 400

    if User.query.filter_by(email=email).first():
        return jsonify(
            {"ok": False, "error": "An account with that email already exists."}
        ), 409

    user = User(email=email, role="student")
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    access_token, refresh_token = _make_tokens(user)
    response = make_response(
        jsonify({"ok": True, "user": user.to_dict(), "access_token": access_token}),
        201,
    )
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

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
    response = make_response(
        jsonify({"ok": True, "message": "Logged out successfully."}), 200
    )
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404
    return jsonify({"ok": True, "user": user.to_dict()}), 200


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404
    access_token, _ = _make_tokens(user)
    return jsonify({"ok": True, "access_token": access_token}), 200


@auth_bp.route("/github/login", methods=["GET"])
def github_login():
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    if not client_id:
        return jsonify({"ok": False, "error": "GitHub OAuth not configured."}), 501
    
    redirect_uri = request.host_url.rstrip("/") + "/api/v1/auth/github/callback"
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&scope=user:email"
    )
    return redirect(github_auth_url)


@auth_bp.route("/github/callback", methods=["GET"])
def github_callback():
    code = request.args.get("code")
    if not code:
        return jsonify({"ok": False, "error": "No code provided by GitHub."}), 400

    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
    
    # 1. Exchange code for access token
    token_resp = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    if not token_resp.ok:
        return jsonify({"ok": False, "error": "Failed to authenticate with GitHub."}), 401
        
    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    if not access_token:
        return jsonify({"ok": False, "error": "No access token from GitHub."}), 401

    # 2. Get user info
    api_headers = {"Authorization": f"token {access_token}"}
    user_resp = requests.get("https://api.github.com/user", headers=api_headers, timeout=10)
    if not user_resp.ok:
        return jsonify({"ok": False, "error": "Failed to fetch user profile."}), 401
    
    github_user = user_resp.json()
    github_id = str(github_user.get("id"))
    
    # 3. Get primary email
    emails_resp = requests.get("https://api.github.com/user/emails", headers=api_headers, timeout=10)
    primary_email = None
    if emails_resp.ok:
        for email_info in emails_resp.json():
            if email_info.get("primary"):
                primary_email = email_info.get("email")
                break
    
    if not primary_email:
        primary_email = github_user.get("email")
        
    if not primary_email:
        return jsonify({"ok": False, "error": "GitHub account must have an email."}), 400

    primary_email = primary_email.strip().lower()

    # 4. Find or create user
    user = User.query.filter_by(github_id=github_id).first()
    if not user:
        # Check if email exists
        user = User.query.filter_by(email=primary_email).first()
        if user:
            # Link github account
            user.github_id = github_id
            db.session.commit()
        else:
            # Create new user
            user = User(email=primary_email, github_id=github_id, role="student")
            db.session.add(user)
            db.session.commit()
            
    if not user.is_active:
        return jsonify({"ok": False, "error": "Account is disabled."}), 403

    # 5. Login
    jwt_access, jwt_refresh = _make_tokens(user)
    
    # Redirect to frontend dashboard (assume root handles it)
    frontend_url = os.environ.get("ALLOWED_ORIGINS", "").split(",")[0] or "/"
    if frontend_url == "*":
        frontend_url = "http://localhost:5173"
        
    response = make_response(redirect(frontend_url))
    set_refresh_cookies(response, jwt_refresh)
    # Give the frontend a way to know the token immediately via query string
    response.location = f"{frontend_url}?token={jwt_access}"
    return response
