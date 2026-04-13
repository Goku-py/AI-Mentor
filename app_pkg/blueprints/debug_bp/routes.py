"""app_pkg/blueprints/debug_bp/routes.py — Debug/diagnostics blueprint.

Endpoints:
  GET /api/v1/debug/gemini-status
  GET /api/v1/debug/sandbox-status
"""

from __future__ import annotations
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, jsonify

from analyzer import sandbox_runtime_status
from app_pkg.extensions import limiter

debug_bp = Blueprint("debug", __name__, url_prefix="/api/v1")


@debug_bp.route("/debug/gemini-status", methods=["GET"])
@limiter.limit("3 per minute; 20 per day")
def debug_gemini_status():
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1].strip()

    if not api_key or api_key in ("YOUR_API_KEY_HERE", "YOUR_NEW_API_KEY_HERE"):
        return jsonify(
            {
                "status": "key_missing",
                "message": "GEMINI_API_KEY is not configured in environment.",
                "resolution": "Set a valid API key in your .env file and restart the server.",
            }
        ), 200

    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-flash-preview-04-17:generateContent?key={urllib.parse.quote_plus(api_key)}"
    )
    payload = {"contents": [{"parts": [{"text": "Say 'test' only."}]}]}

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            status_code = resp.getcode()
            raw_body = resp.read().decode("utf-8", errors="replace")

        if status_code == 200:
            try:
                parsed = json.loads(raw_body)
                if parsed.get("candidates"):
                    return jsonify(
                        {
                            "status": "enabled",
                            "message": "Gemini API is active and responding correctly.",
                            "api_key_prefix": f"{api_key[:8]}...",
                        }
                    ), 200
                return jsonify(
                    {
                        "status": "bad_response",
                        "message": "API returned 200 but response structure is unexpected.",
                        "resolution": "Check that gemini-2.5-flash model is available.",
                    }
                ), 200
            except json.JSONDecodeError:
                return jsonify(
                    {
                        "status": "bad_response",
                        "message": "API returned 200 but body is not valid JSON.",
                        "resolution": "Possible upstream gateway/proxy issue.",
                    }
                ), 200
        return jsonify(
            {
                "status": "unexpected_status",
                "message": f"API returned HTTP {status_code}.",
                "resolution": "Check Google Cloud Console for API status.",
            }
        ), 200

    except urllib.error.HTTPError as http_err:
        status_code = http_err.code
        try:
            error_body = (http_err.read() or b"").decode("utf-8", errors="replace")
            error_json = json.loads(error_body) if error_body else {}
            error_message = error_json.get("error", {}).get("message", "")
        except Exception:
            error_message = ""
        haystack = (
            f"{error_message} {error_body}".lower() if "error_body" in dir() else ""
        )
        if status_code == 403:
            if "api has not been used" in haystack or "disabled" in haystack:
                return jsonify(
                    {
                        "status": "api_disabled",
                        "message": "Gemini API is not enabled for this project.",
                        "resolution": "Enable the Generative Language API in Google Cloud Console.",
                    }
                ), 200
            return jsonify(
                {
                    "status": "forbidden",
                    "message": f"HTTP 403: {error_message or 'Access forbidden'}",
                    "resolution": "Check API key permissions.",
                }
            ), 200
        if status_code == 400:
            return jsonify(
                {
                    "status": "invalid_key",
                    "message": "API key appears to be invalid or malformed.",
                    "resolution": "Generate a new API key at https://aistudio.google.com/app/apikey",
                }
            ), 200
        if status_code == 429:
            return jsonify(
                {
                    "status": "quota_exceeded",
                    "message": "API quota or rate limit exceeded.",
                    "resolution": "Wait and retry, or check quota limits.",
                }
            ), 200
        return jsonify(
            {
                "status": "api_error",
                "message": f"HTTP {status_code}: {error_message or 'Unknown error'}",
                "resolution": "Check API status and logs.",
            }
        ), 200

    except urllib.error.URLError as url_err:
        return jsonify(
            {
                "status": "network_error",
                "message": f"Network error: {str(url_err)}",
                "resolution": "Check internet connectivity.",
            }
        ), 200
    except Exception as exc:
        return jsonify(
            {
                "status": "internal_error",
                "message": f"Internal check failed: {str(exc)}",
                "resolution": "Check server logs.",
            }
        ), 200


@debug_bp.route("/debug/sandbox-status", methods=["GET"])
@limiter.limit("5 per minute; 50 per day")
def debug_sandbox_status():
    status = sandbox_runtime_status()
    return jsonify(
        {
            "status": "ready" if status.get("ok") else "unavailable",
            "mode": status.get("mode"),
            "docker_sdk_installed": status.get("docker_sdk_installed"),
            "docker_daemon_available": status.get("docker_daemon_available"),
            "host_fallback_allowed": status.get("host_fallback_allowed"),
            "reason": status.get("reason"),
        }
    ), 200
