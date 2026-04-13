"""app_pkg/security/middleware.py — Security middleware: bot blocking + abuse patterns.

Pure functions — no Flask app dependency at import time.
Registered into the app by create_app() via init_security(app).
"""

from __future__ import annotations

import re
import unicodedata

from flask import jsonify, request


# ---------------------------------------------------------------------------
# Bot / scraper UA blocking
# ---------------------------------------------------------------------------
_BOT_UA_RE = re.compile(
    r"(python-requests|httpx|aiohttp|curl/|wget/|scrapy|go-http-client|"
    r"libwww|zgrab|masscan|nuclei|sqlmap|nmap|nikto|bot|crawler|spider)",
    re.IGNORECASE,
)
_PROTECTED_PATHS = {"/api/v1/analyze", "/api/v1/debug/gemini-status"}

# Security event counters (in-process; reset on restart)
SECURITY_METRICS: dict = {
    "blocked_automated_clients": 0,
    "auth_failures": 0,
    "abuse_pattern_rejections": 0,
    "concurrency_rejections": 0,
    "sandbox_failures": 0,
    "ai_mentor_calls_made": 0,
    "ai_mentor_tokens_used": 0,
}


# ---------------------------------------------------------------------------
# Abuse pattern matching
# ---------------------------------------------------------------------------
def _normalise_for_abuse_check(text: str) -> str:
    """Normalise unicode and collapse all whitespace for pattern matching."""
    normalised = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", normalised)


ABUSE_PATTERNS = [
    # Shell / filesystem destruction
    (re.compile(r"rm -rf /"), "dangerous_shell_delete"),
    (re.compile(r"shutil\.rmtree\s*\("), "python_rmtree"),
    # Fork bomb
    (re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\};\s*:"), "fork_bomb"),
    # Sensitive paths
    (re.compile(r"/etc/passwd"), "sensitive_path_access"),
    (re.compile(r"/etc/shadow"), "sensitive_path_shadow"),
    # Encoded / obfuscated execution
    (re.compile(r"powershell -enc"), "encoded_powershell"),
    (re.compile(r"base64\.b64decode.*exec", re.DOTALL), "base64_exec_chain"),
    # Python execution escape
    (re.compile(r"__import__\( *['\"]os['\"] *\)\.system"), "python_system_exec"),
    (re.compile(r"__builtins__"), "builtins_access"),
    (re.compile(r"ctypes\.cdll"), "ctypes_cdll"),
    (re.compile(r"ctypes\.CDLL"), "ctypes_CDLL"),
    # Network exfiltration
    (re.compile(r"socket\.socket\s*\("), "raw_socket"),
    (re.compile(r"curl .* \| .*sh"), "curl_pipe_shell"),
    (re.compile(r"wget .* -O- .* \| .*sh"), "wget_pipe_shell"),
]


def contains_abuse_pattern(code: str) -> str | None:
    """Return the label of the first matched abuse pattern, or None."""
    if not isinstance(code, str):
        return None
    normalised = _normalise_for_abuse_check(code)
    for pattern, label in ABUSE_PATTERNS:
        if pattern.search(normalised):
            return label
    return None


# ---------------------------------------------------------------------------
# App registration
# ---------------------------------------------------------------------------
def init_security(app) -> None:
    """Register security hooks onto the Flask app."""

    @app.before_request
    def block_automated_clients():
        if request.path not in _PROTECTED_PATHS:
            return
        ua = request.headers.get("User-Agent", "").strip()
        if not ua or _BOT_UA_RE.search(ua):
            SECURITY_METRICS["blocked_automated_clients"] += 1
            app.logger.warning(
                "Blocked automated client: UA=%r path=%s addr=%s",
                ua,
                request.path,
                request.remote_addr,
            )
            return jsonify(
                {
                    "ok": False,
                    "error": "Automated requests are not permitted on this endpoint.",
                }
            ), 403

    @app.errorhandler(429)
    def ratelimit_exceeded(e):
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
        response = jsonify(
            {
                "ok": False,
                "error": "Too many requests. Please wait before retrying.",
                "retry_after_seconds": retry_seconds,
            }
        )
        response.status_code = 429
        if retry_seconds is not None:
            response.headers["Retry-After"] = str(retry_seconds)
        return response
