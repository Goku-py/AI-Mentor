"""
tests/test_security.py — Tests for all security hardening layers.

Covers:
  - ABUSE_PATTERNS (13 patterns + whitespace normalisation bypass)
  - Python blocked modules  (socket, ctypes, pickle, … → SecurityError)
  - AST-level blocked built-ins (eval, exec)
  - Input validation (language allowlist, empty/whitespace-only code)
  - Security headers injected by Flask-Talisman

The 'client' fixture is provided by tests/conftest.py.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _analyze(client, code, language="python"):
    """POST to /api/v1/analyze and return the response."""
    return client.post(
        "/api/v1/analyze",
        json={"code": code, "language": language},
    )


# ---------------------------------------------------------------------------
# Abuse patterns (checked at the HTTP level before code is run)
# These must return 400 with an 'error' field mentioning 'security policy'.
# ---------------------------------------------------------------------------
class TestAbusePatterns:
    """ABUSE_PATTERNS block dangerous payloads before any analysis runs."""

    def _expect_blocked(self, client, code, language="python"):
        r = _analyze(client, code, language)
        assert r.status_code == 400, (
            f"Expected 400 for code: {code!r}, got {r.status_code}"
        )
        body = r.get_json()
        assert body is not None
        assert "security policy" in body.get("error", "").lower(), (
            f"Expected 'security policy' in error, got: {body.get('error')}"
        )

    def test_rm_rf_slash_blocked(self, client):
        """Classic shell delete command is blocked."""
        self._expect_blocked(client, "# rm -rf /\nprint('oops')")

    def test_rm_rf_extra_whitespace_normalised_and_blocked(self, client):
        """Extra spaces inside 'rm -rf /' are collapsed then matched."""
        # Two spaces between - and rf; normaliser collapses to one space
        self._expect_blocked(client, "# rm  -rf /")

    def test_shutil_rmtree_blocked(self, client):
        """shutil.rmtree() is blocked as a dangerous filesystem operation."""
        self._expect_blocked(client, "import shutil\nshutil.rmtree('/')")

    def test_etc_passwd_blocked(self, client):
        """/etc/passwd path access is blocked."""
        self._expect_blocked(client, "open('/etc/passwd')")

    def test_etc_shadow_blocked(self, client):
        """/etc/shadow path access is blocked."""
        self._expect_blocked(client, "open('/etc/shadow')")

    def test_raw_socket_creation_blocked(self, client):
        """socket.socket() call pattern is blocked."""
        self._expect_blocked(
            client,
            "import socket\ns = socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
        )

    def test_builtins_access_blocked(self, client):
        """Direct __builtins__ access is blocked."""
        self._expect_blocked(client, "x = __builtins__")

    def test_ctypes_cdll_blocked(self, client):
        """ctypes.cdll is blocked as native code access."""
        self._expect_blocked(
            client, "import ctypes\nctypes.cdll.LoadLibrary('libc.so.6')"
        )

    def test_fork_bomb_blocked(self, client):
        """Classic bash fork bomb is blocked."""
        self._expect_blocked(client, ":(){:|:&};:", language="python")

    def test_encoded_powershell_blocked(self, client):
        """Encoded powershell command is blocked."""
        self._expect_blocked(client, "powershell -enc aGVsbG8=", language="python")

    def test_base64_exec_chain_blocked(self, client):
        """base64.b64decode result fed into exec() is blocked.

        The ABUSE_PATTERN regex is: base64.b64decode.*exec
        base64.b64decode must appear BEFORE exec in the (normalised) string.
        """
        self._expect_blocked(client, "x = base64.b64decode('cHJpbnQoMSk='); exec(x)")

    def test_valid_python_code_not_blocked(self, client):
        """Clean, safe code must pass through without triggering any block."""
        r = _analyze(client, "x = 1 + 1\nprint(x)")
        assert r.status_code == 200, (
            f"Valid code was incorrectly blocked: {r.get_json()}"
        )

    def test_valid_for_loop_not_blocked(self, client):
        """A simple loop must not trigger any false positive."""
        r = _analyze(client, "for i in range(5):\n    print(i)")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Python blocked modules  (checked by _blocked_python_import in analyzer.py)
# These return 200 but the execution result contains a SecurityError.
# ---------------------------------------------------------------------------
class TestBlockedModules:
    """Dangerous imports are caught by AST analysis and blocked pre-execution."""

    def _expect_security_error(self, client, code):
        r = _analyze(client, code)
        assert r.status_code == 200, f"Unexpected HTTP error: {r.status_code}"
        data = r.get_json()
        execution = data.get("execution", {})
        err = execution.get("error", {})
        assert err.get("type") == "SecurityError", (
            f"Expected SecurityError, got execution={execution}"
        )
        assert execution["returncode"] == 1

    def test_import_socket_blocked(self, client):
        """'import socket' is blocked — network access not allowed."""
        self._expect_security_error(client, "import socket")

    def test_import_os_blocked(self, client):
        """'import os' is blocked — process/filesystem access not allowed."""
        self._expect_security_error(client, "import os")

    def test_import_subprocess_blocked(self, client):
        """'import subprocess' is blocked — shell execution not allowed."""
        self._expect_security_error(client, "import subprocess")

    def test_import_ctypes_blocked(self, client):
        """'import ctypes' is blocked — native memory access not allowed."""
        self._expect_security_error(client, "import ctypes")

    def test_import_pickle_blocked(self, client):
        """'import pickle' is blocked — arbitrary code deserialisation."""
        self._expect_security_error(client, "import pickle")

    def test_from_os_import_blocked(self, client):
        """'from os import ...' is also blocked via root-module check."""
        self._expect_security_error(client, "from os import path")

    def test_eval_call_blocked(self, client):
        """Direct eval() call is blocked at the AST level."""
        self._expect_security_error(client, "eval('1 + 1')")

    def test_exec_call_blocked(self, client):
        """Direct exec() call is blocked at the AST level."""
        self._expect_security_error(client, "exec('print(1)')")

    def test_safe_math_not_blocked(self, client):
        """Pure arithmetic must NOT be treated as a blocked import."""
        r = _analyze(client, "result = 2 ** 10\nprint(result)")
        assert r.status_code == 200
        execution = r.get_json().get("execution", {})
        err = execution.get("error", {})
        assert err.get("type") != "SecurityError", (
            "Safe code incorrectly flagged as SecurityError"
        )


# ---------------------------------------------------------------------------
# Input validation (language allowlist, empty code, etc.)
# ---------------------------------------------------------------------------
class TestInputValidation:
    """Bad inputs are rejected with 400 before any analysis occurs."""

    def test_invalid_language_returns_400(self, client):
        """An unlisted language returns 400 with a mention of 'language'."""
        r = _analyze(client, "print(1)", language="brainfuck")
        assert r.status_code == 400
        assert "language" in r.get_json().get("error", "").lower()

    def test_empty_code_returns_400(self, client):
        """Completely empty code string returns 400."""
        r = _analyze(client, "")
        assert r.status_code == 400

    def test_whitespace_only_code_returns_400(self, client):
        """Code made entirely of whitespace returns 400."""
        r = _analyze(client, "   \n\t   \n")
        assert r.status_code == 400

    def test_missing_code_key_returns_400(self, client):
        """Request body without a 'code' key returns 400."""
        r = client.post("/api/v1/analyze", json={"language": "python"})
        assert r.status_code == 400

    def test_javascript_language_accepted(self, client):
        """'javascript' is an accepted language value."""
        r = _analyze(client, "console.log('hi');", language="javascript")
        assert r.status_code == 200

    def test_java_language_accepted(self, client):
        """'java' is an accepted language value (may return 422 if JDK not installed)."""
        r = _analyze(client, 'System.out.println("hi");', language="java")
        # 200 = analyzed OK, 422 = language accepted but tool not installed on this server
        assert r.status_code in (200, 422)


# ---------------------------------------------------------------------------
# Security headers (injected by Flask-Talisman on every response)
# ---------------------------------------------------------------------------
class TestSecurityHeaders:
    """Flask-Talisman must inject standard security headers on every response."""

    def test_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options: nosniff prevents MIME sniffing attacks."""
        r = client.get("/api/v1/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_csp_or_x_frame_options_present(self, client):
        """Either X-Frame-Options or Content-Security-Policy must be present."""
        r = client.get("/api/v1/health")
        has_xfo = "X-Frame-Options" in r.headers
        has_csp = "Content-Security-Policy" in r.headers
        assert has_xfo or has_csp, (
            "Neither X-Frame-Options nor CSP header found — clickjacking protection missing"
        )
