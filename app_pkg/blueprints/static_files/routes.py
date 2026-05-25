"""app_pkg/blueprints/static_files/routes.py — Frontend SPA serving + legacy redirects."""

import re

from flask import Blueprint, current_app, redirect, send_from_directory

from app_pkg.extensions import csrf

static_bp = Blueprint("static_files", __name__)

# Vite emits content-hashed filenames like "index-DgRg5HQ0.js".
# Match an 8+ char hex hash between a dot and file extension.
_HASHED_FILE_RE = re.compile(r"\.[a-fA-F0-9]{8,}\.")


# ---------------------------------------------------------------------------
# Legacy redirects (permanent — external clients keep working)
# ---------------------------------------------------------------------------
@static_bp.route("/health")
def legacy_health():
    return redirect("/api/v1/health", code=301)


@static_bp.route("/tools")
def legacy_tools():
    return redirect("/api/v1/tools", code=301)


@static_bp.route("/debug/gemini-status")
def legacy_debug_gemini_status():
    return redirect("/api/v1/debug/gemini-status", code=301)


@static_bp.route("/analyze", methods=["POST"])
@csrf.exempt
def legacy_analyze():
    return redirect("/api/v1/analyze", code=308)


# ---------------------------------------------------------------------------
# SPA catch-all
# ---------------------------------------------------------------------------
@static_bp.route("/")
def index():
    dist_path = current_app.static_folder or "dist"
    resp = send_from_directory(dist_path, "index.html")
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@static_bp.route("/<path:filename>")
def serve_static(filename):
    dist_path = current_app.static_folder or "dist"
    resp = send_from_directory(dist_path, filename)
    if _HASHED_FILE_RE.search(filename):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "no-cache"
    return resp
