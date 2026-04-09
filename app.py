import os
import re
import sys
import asyncio
from flask import Blueprint, Flask, jsonify, redirect, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

from analyzer import analyze_code, verify_tools

load_dotenv()

app = Flask(__name__, static_folder='dist', static_url_path='')

# ProxyFix: trust exactly TRUSTED_PROXY_COUNT upstream reverse-proxy hops.
# Set TRUSTED_PROXY_COUNT=1 on Railway / Render / Heroku so that
# X-Forwarded-For is used for per-IP rate limiting rather than the
# shared proxy address (which would make all clients share one bucket).
# Leave at 0 (default) for local / direct-to-internet deployments.
_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))
if _PROXY_COUNT > 0:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=_PROXY_COUNT,
        x_proto=_PROXY_COUNT,
        x_host=_PROXY_COUNT,
    )

# Configure rate limiting
# Use Redis in production for shared state across workers; falls back to in-memory
RATE_LIMIT_STORAGE = os.environ.get("RATE_LIMIT_STORAGE_URI", "memory://")
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=RATE_LIMIT_STORAGE
)

# Configure CORS - restrict in production
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")
CORS(app, origins=ALLOWED_ORIGINS.split(",") if ALLOWED_ORIGINS != "*" else "*")

AVAILABLE_TOOLS = verify_tools()

# Strictly allowlisted set of accepted language values.
# Any value outside this set is rejected with a 400 before it can reach
# error messages or the Gemini AI prompt (prevents prompt injection).
ALLOWED_LANGUAGES = {"python", "javascript", "js", "java", "c", "cpp", "c++"}

# Strictly allowlisted set of accepted difficulty values.
ALLOWED_DIFFICULTIES = {"beginner", "intermediate", "advanced"}

# ---------------------------------------------------------------------------
# API v1 Blueprint
# All public API endpoints live under /api/v1/. Static file serving and the
# legacy redirect routes remain on the root app.
# ---------------------------------------------------------------------------
v1_bp = Blueprint('v1', __name__, url_prefix='/api/v1')

# ---------------------------------------------------------------------------
# Bot / scraper defense
# ---------------------------------------------------------------------------
# User-agent substrings associated with automated HTTP clients, scanners, and
# scraping frameworks.  Matched case-insensitively on the two AI-backed routes
# only; static assets and health checks are intentionally excluded.
_BOT_UA_RE = re.compile(
    r"(python-requests|httpx|aiohttp|curl/|wget/|scrapy|go-http-client|"
    r"libwww|zgrab|masscan|nuclei|sqlmap|nmap|nikto|bot|crawler|spider)",
    re.IGNORECASE,
)
_PROTECTED_PATHS = {"/api/v1/analyze", "/api/v1/debug/gemini-status"}


@app.before_request
def block_automated_clients():
    """Reject obviously automated clients on AI-backed endpoints."""
    if request.path not in _PROTECTED_PATHS:
        return
    ua = request.headers.get("User-Agent", "").strip()
    if not ua or _BOT_UA_RE.search(ua):
        app.logger.warning(
            "Blocked automated client: UA=%r path=%s addr=%s",
            ua, request.path, request.remote_addr,
        )
        return jsonify({"ok": False, "error": "Automated requests are not permitted on this endpoint."}), 403


@app.errorhandler(429)
def ratelimit_exceeded(e):
    """Return a structured JSON 429 with a Retry-After header."""
    retry_after = getattr(e, "retry_after", None)
    retry_seconds = None
    if retry_after is not None:
        try:
            retry_seconds = int(retry_after.total_seconds())
        except AttributeError:
            try:
                retry_seconds = int(retry_after)
            except (TypeError, ValueError):
                retry_seconds = None
    response = jsonify({
        "ok": False,
        "error": "Too many requests. Please wait before retrying.",
        "retry_after_seconds": retry_seconds,
    })
    response.status_code = 429
    if retry_seconds is not None:
        response.headers["Retry-After"] = str(retry_seconds)
    return response


def validate_environment():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "YOUR_API_KEY_HERE":
        print("WARNING: GEMINI_API_KEY not found or not set in .env file", file=sys.stderr)
        print("    AI Mentor feedback will be disabled. Set GEMINI_API_KEY to enable.", file=sys.stderr)


# ---------------------------------------------------------------------------
# Legacy redirects — permanent redirects from the old bare paths so that
# any existing external clients continue to work during transition.
# GET routes use 301 (Moved Permanently); POST /analyze uses 308 so that
# the method and body are preserved through the redirect.
# ---------------------------------------------------------------------------
@app.route("/health")
def legacy_health():
    return redirect("/api/v1/health", code=301)


@app.route("/tools")
def legacy_tools():
    return redirect("/api/v1/tools", code=301)


@app.route("/debug/gemini-status")
def legacy_debug_gemini_status():
    return redirect("/api/v1/debug/gemini-status", code=301)


@app.route("/analyze", methods=["POST"])
def legacy_analyze():
    return redirect("/api/v1/analyze", code=308)


# ---------------------------------------------------------------------------
# Frontend SPA serving
# ---------------------------------------------------------------------------
@app.route("/")
def index():
    dist_path = app.static_folder or 'dist'
    return send_from_directory(dist_path, 'index.html')


@app.route("/<path:filename>")
def serve_static(filename):
    dist_path = app.static_folder or 'dist'
    return send_from_directory(dist_path, filename)


@v1_bp.route("/health")
def health():
    return jsonify({
        "status": "Server is running!",
        "available_tools": AVAILABLE_TOOLS,
        "ai_mentor_enabled": bool(os.environ.get("GEMINI_API_KEY"))
    })


@v1_bp.route("/tools", methods=["GET"])
def tools():
    """Return available compilation/execution tools."""
    return jsonify({
        "available": AVAILABLE_TOOLS,
        "message": "Tools marked as 'false' are not installed. See README for setup instructions."
    })


@v1_bp.route("/debug/gemini-status", methods=["GET"])
@limiter.limit("3 per minute; 20 per day")
def debug_gemini_status():
    """
    Perform a minimal health check on the Gemini API integration.
    Returns sanitized diagnosis without exposing secrets.
    """
    import json
    import urllib.error
    import urllib.parse
    import urllib.request
    
    # Check API key first
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1].strip()
    
    if not api_key or api_key in ("YOUR_API_KEY_HERE", "YOUR_NEW_API_KEY_HERE"):
        return jsonify({
            "status": "key_missing",
            "message": "GEMINI_API_KEY is not configured in environment.",
            "resolution": "Set a valid API key in your .env file and restart the server."
        }), 200
    
    # Minimal test request
    endpoint = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/gemini-2.5-flash:generateContent?key={urllib.parse.quote_plus(api_key)}"
    )
    payload = {
        "contents": [{"parts": [{"text": "Say 'test' only."}]}]
    }
    
    try:
        request_body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            raw_body = response.read().decode("utf-8", errors="replace")
        
        if status_code == 200:
            try:
                parsed = json.loads(raw_body)
                candidates = parsed.get("candidates", [])
                if candidates:
                    return jsonify({
                        "status": "enabled",
                        "message": "Gemini API is active and responding correctly.",
                        "api_key_prefix": f"{api_key[:8]}..."
                    }), 200
                else:
                    return jsonify({
                        "status": "bad_response",
                        "message": "API returned 200 but response structure is unexpected.",
                        "resolution": "Check that gemini-2.5-flash model is available."
                    }), 200
            except json.JSONDecodeError:
                return jsonify({
                    "status": "bad_response",
                    "message": "API returned 200 but body is not valid JSON.",
                    "resolution": "Possible upstream gateway/proxy issue."
                }), 200
        else:
            return jsonify({
                "status": "unexpected_status",
                "message": f"API returned HTTP {status_code}.",
                "resolution": "Check Google Cloud Console for API status."
            }), 200
            
    except urllib.error.HTTPError as http_err:
        status_code = http_err.code
        try:
            error_body = (http_err.read() or b"").decode("utf-8", errors="replace")
            error_json = json.loads(error_body) if error_body else {}
            error_message = error_json.get("error", {}).get("message", "")
        except Exception:
            error_message = ""
        
        haystack = f"{error_message} {error_body}".lower()
        
        if status_code == 403:
            if "api has not been used" in haystack or "disabled" in haystack:
                return jsonify({
                    "status": "api_disabled",
                    "message": "Gemini API is not enabled for this project.",
                    "resolution": "Enable the Generative Language API in Google Cloud Console: https://console.cloud.google.com/apis/library/generativelanguage.googleapis.com"
                }), 200
            else:
                return jsonify({
                    "status": "forbidden",
                    "message": f"HTTP 403: {error_message or 'Access forbidden'}",
                    "resolution": "Check API key permissions and project configuration."
                }), 200
        
        elif status_code == 400:
            return jsonify({
                "status": "invalid_key",
                "message": "API key appears to be invalid or malformed.",
                "resolution": "Generate a new API key at https://aistudio.google.com/app/apikey"
            }), 200
        
        elif status_code == 429:
            return jsonify({
                "status": "quota_exceeded",
                "message": "API quota or rate limit exceeded.",
                "resolution": "Wait and retry, or check quota limits in Google Cloud Console."
            }), 200
        
        else:
            return jsonify({
                "status": "api_error",
                "message": f"HTTP {status_code}: {error_message or 'Unknown error'}",
                "resolution": "Check API status and logs."
            }), 200
    
    except urllib.error.URLError as url_err:
        return jsonify({
            "status": "network_error",
            "message": f"Network error: {str(url_err)}",
            "resolution": "Check internet connectivity and firewall settings."
        }), 200
    
    except Exception as exc:
        return jsonify({
            "status": "internal_error",
            "message": f"Internal check failed: {str(exc)}",
            "resolution": "Check server logs for details."
        }), 200


@v1_bp.route("/analyze", methods=["POST"])
@limiter.limit("10 per minute; 100 per day")
def analyze():
    payload = request.get_json(silent=True) or {}

    code = payload.get("code")
    language = payload.get("language", "python")
    difficulty = payload.get("difficulty", "beginner")

    if not isinstance(language, str) or language.lower() not in ALLOWED_LANGUAGES:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Invalid language. Supported values: python, javascript, java, c, cpp.",
                }
            ),
            400,
        )
    language = language.lower()

    if not isinstance(difficulty, str) or difficulty.lower() not in ALLOWED_DIFFICULTIES:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Invalid difficulty. Supported values: beginner, intermediate, advanced.",
                }
            ),
            400,
        )
    difficulty = difficulty.lower()

    if not isinstance(code, str) or not code.strip():
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Invalid or missing 'code' field in request body.",
                }
            ),
            400,
        )

    # Limit code size to prevent abuse (100KB limit)
    if len(code) > 102400:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Code exceeds maximum size limit of 100KB.",
                }
            ),
            400,
        )

    # Check if language tools are available
    if language in AVAILABLE_TOOLS and not AVAILABLE_TOOLS[language]:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": f"Tools for language '{language}' are not installed on this server.",
                    "suggestion": "Check the /tools endpoint for available languages or see README for setup."
                }
            ),
            422,
        )

    try:
        result = asyncio.run(analyze_code(code=code, language=language, difficulty=difficulty))
        return jsonify(result), 200
    except Exception as exc:  # pragma: no cover - defensive
        app.logger.exception("Error during code analysis: %s", exc)
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "Internal server error during analysis.",
                }
            ),
            500,
        )


app.register_blueprint(v1_bp)

if __name__ == "__main__":
    # Validate environment
    validate_environment()
    
    # Use PORT env var (set by Railway, Render, etc.) or default to 5000
    port = int(os.environ.get("PORT", 5000))
    is_production = os.environ.get("FLASK_ENV", "development") == "production"
    
    print("\nServer Starting with Configuration:")
    print(f"   Environment: {'production' if is_production else 'development'}")
    print(f"   Port: {port}")
    print(f"   Available Tools: {AVAILABLE_TOOLS}")
    print(f"   AI Mentor Enabled: {bool(os.environ.get('GEMINI_API_KEY'))}")
    print(f"   CORS Enabled: Yes (Origins: {ALLOWED_ORIGINS})")
    print(f"   Rate Limiting: /api/v1/analyze → 10/min, 100/day | /api/v1/debug/gemini-status → 3/min, 20/day")
    print(f"   Rate Limit Storage: {RATE_LIMIT_STORAGE}")
    print(f"   Proxy Hops Trusted: {_PROXY_COUNT} (set TRUSTED_PROXY_COUNT for cloud deploys)")
    print(f"\nFlask app running on http://0.0.0.0:{port}")
    print(f"   API Documentation: http://0.0.0.0:{port}/ \n")
    
    app.run(host="0.0.0.0", port=port, debug=not is_production)

