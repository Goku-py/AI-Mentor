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
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus, urlparse

import requests
from flask import (
    Blueprint,
    current_app,
    jsonify,
    make_response,
    redirect,
    request,
    session,
)
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_refresh_cookies,
    unset_jwt_cookies,
)

from app_pkg.extensions import csrf, jwt_blacklist_add, limiter
from app_pkg.utils import coerce_jwt_identity
from models_pkg import User, db

auth_bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def _validate_email(email: str) -> str | None:
    if not email or len(email) > 254:  # noqa: PLR2004
        return "Email must be between 1 and 254 characters."
    if not _EMAIL_RE.match(email):
        return "Email address is not valid."
    return None


def _validate_password(password: str) -> str | None:
    if not password or len(password) < 8:  # noqa: PLR2004
        return "Password must be at least 8 characters."
    if len(password) > 128:  # noqa: PLR2004
        return "Password must be at most 128 characters."
    has_digit = any(c.isdigit() for c in password)
    has_special = any(not c.isalnum() for c in password)
    if not (has_digit or has_special):
        return "Password must contain at least one digit or special character."
    return None


def _make_tokens(user: User) -> tuple[str, str]:
    additional_claims = {"role": user.role, "email": user.email}
    access_token = create_access_token(identity=str(user.id), additional_claims=additional_claims)
    refresh_token = create_refresh_token(identity=str(user.id))
    return access_token, refresh_token


def _allowed_frontend_origin() -> str:
    raw_origins = os.environ.get("ALLOWED_ORIGINS", "").split(",")
    for origin in raw_origins:
        candidate = origin.strip()
        if not candidate or candidate == "*":
            continue
        parsed = urlparse(candidate)
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    return "http://localhost:5173"


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("5 per minute; 20 per day")
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
        return jsonify({"ok": False, "error": "An account with that email already exists."}), 409

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
@limiter.limit("10 per minute; 50 per day")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = str(data.get("password") or "")

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password are required."}), 400

    user = User.query.filter_by(email=email, is_active=True).first()

    # Account lockout check
    if user and user.is_locked():
        return jsonify({"ok": False, "error": "Account is temporarily locked due to too many failed login attempts. Try again later."}), 423  # noqa: E501

    if not user or not user.check_password(password):
        # Increment failed attempts if user exists
        if user:
            user.increment_login_attempts()
            max_attempts = int(os.environ.get("MAX_LOGIN_ATTEMPTS", "5"))
            if user.login_attempts >= max_attempts:
                lockout_minutes = int(os.environ.get("ACCOUNT_LOCKOUT_MINUTES", "15"))
                user.locked_until = datetime.now(UTC) + timedelta(minutes=lockout_minutes)
                current_app.logger.warning(
                    "Account locked due to failed logins",
                    extra={"email": email, "attempts": user.login_attempts},
                )
            db.session.commit()
        return jsonify({"ok": False, "error": "Invalid email or password."}), 401

    # Successful login — reset attempts
    user.reset_login_attempts()
    db.session.commit()

    access_token, refresh_token = _make_tokens(user)
    response = make_response(
        jsonify({"ok": True, "user": user.to_dict(), "access_token": access_token}),
        200,
    )
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route("/logout", methods=["POST"])
@csrf.exempt
@jwt_required()
def logout():
    # Blacklist the current JWT so it can't be reused
    jwt_payload = get_jwt()
    jti = jwt_payload.get("jti", "")
    exp = jwt_payload.get("exp", None)
    if jti:
        jwt_blacklist_add(jti, expires_at=exp)

    response = make_response(jsonify({"ok": True, "message": "Logged out successfully."}), 200)
    unset_jwt_cookies(response)
    return response


@auth_bp.route("/me", methods=["GET"])
@jwt_required()
@limiter.limit("30 per minute; 500 per day")
def me():
    user_id = coerce_jwt_identity(get_jwt_identity())
    if user_id is None:
        return jsonify({"ok": False, "error": "Invalid authentication token."}), 401
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404
    return jsonify({"ok": True, "user": user.to_dict()}), 200


@auth_bp.route("/refresh", methods=["POST"])
@csrf.exempt
@jwt_required(refresh=True)
@limiter.limit("10 per minute; 50 per day")
def refresh():
    user_id = coerce_jwt_identity(get_jwt_identity())
    if user_id is None:
        return jsonify({"ok": False, "error": "Invalid authentication token."}), 401
    user = db.session.get(User, user_id)
    if not user or not user.is_active:
        return jsonify({"ok": False, "error": "User not found or inactive."}), 404
    access_token, refresh_token = _make_tokens(user)
    response = make_response(jsonify({"ok": True, "access_token": access_token}), 200)
    set_refresh_cookies(response, refresh_token)
    return response


@auth_bp.route("/github/login", methods=["GET"])
@limiter.limit("5 per minute; 20 per hour")
def github_login():
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    if not client_id:
        return jsonify({"ok": False, "error": "GitHub OAuth not configured."}), 501

    state = secrets.token_urlsafe(32)
    session["github_oauth_state"] = state

    redirect_uri = request.host_url.rstrip("/") + "/api/v1/auth/github/callback"
    github_auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={quote_plus(client_id)}"
        f"&redirect_uri={quote_plus(redirect_uri)}"
        f"&scope=user:email"
        f"&state={quote_plus(state)}"
    )
    return redirect(github_auth_url)


def _exchange_github_token(code: str) -> str | None:
    resp = requests.post(
        "https://github.com/login/oauth/access_token",
        data={
            "client_id": os.environ["GITHUB_CLIENT_ID"],
            "client_secret": os.environ["GITHUB_CLIENT_SECRET"],
            "code": code,
        },
        headers={"Accept": "application/json"},
        timeout=10,
    )
    if not resp.ok:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    return data.get("access_token")


def _fetch_github_user(access_token: str) -> dict | None:
    headers = {"Authorization": f"token {access_token}"}
    try:
        resp = requests.get("https://api.github.com/user", headers=headers, timeout=10)
    except requests.RequestException as exc:
        current_app.logger.warning("GitHub user profile fetch failed: %s", exc)
        return None
    if not resp.ok:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _fetch_primary_email(access_token: str, fallback_email: str | None) -> str | None:
    headers = {"Authorization": f"token {access_token}"}
    try:
        resp = requests.get("https://api.github.com/user/emails", headers=headers, timeout=10)
    except requests.RequestException:
        return fallback_email
    if not resp.ok:
        return fallback_email
    try:
        entries = resp.json()
    except ValueError:
        return fallback_email
    for entry in entries:
        if entry.get("primary"):
            return entry.get("email")
    return fallback_email


def _find_or_create_github_user(github_id: str, email: str) -> User:
    user = User.query.filter_by(github_id=github_id).first()
    if user:
        return user
    user = User.query.filter_by(email=email).first()
    if user:
        user.github_id = github_id
        db.session.commit()
        return user
    user = User(email=email, github_id=github_id, role="student")
    db.session.add(user)
    db.session.commit()
    return user


@auth_bp.route("/github/callback", methods=["GET"])
@limiter.limit("10 per minute; 30 per hour")
def github_callback():  # noqa: PLR0911
    code = request.args.get("code")
    state = request.args.get("state")
    if not code:
        return jsonify({"ok": False, "error": "No code provided by GitHub."}), 400

    expected_state = session.pop("github_oauth_state", None)
    if not expected_state or not secrets.compare_digest(state or "", expected_state):
        return jsonify({"ok": False, "error": "Invalid OAuth state."}), 400

    if not os.environ.get("GITHUB_CLIENT_ID") or not os.environ.get("GITHUB_CLIENT_SECRET"):
        return jsonify({"ok": False, "error": "GitHub OAuth not configured."}), 501

    try:
        access_token = _exchange_github_token(code)
    except requests.RequestException as exc:
        current_app.logger.warning("GitHub token exchange failed: %s", exc)
        return jsonify({"ok": False, "error": "GitHub service unavailable."}), 503
    if not access_token:
        return jsonify({"ok": False, "error": "GitHub authentication failed."}), 401

    github_user = _fetch_github_user(access_token)
    if not github_user:
        return jsonify({"ok": False, "error": "GitHub service unavailable."}), 503

    github_id = str(github_user.get("id"))
    primary_email = _fetch_primary_email(access_token, github_user.get("email"))
    if not primary_email:
        return jsonify({"ok": False, "error": "GitHub account must have an email."}), 400

    user = _find_or_create_github_user(github_id, primary_email.strip().lower())
    if not user.is_active:
        return jsonify({"ok": False, "error": "Account is disabled."}), 403

    _, jwt_refresh = _make_tokens(user)
    frontend_url = _allowed_frontend_origin()
    response = make_response(redirect(frontend_url))
    set_refresh_cookies(response, jwt_refresh)
    return response
