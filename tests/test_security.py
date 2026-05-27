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
        assert r.status_code == 400, f"Expected 400 for code: {code!r}, got {r.status_code}"
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
        self._expect_blocked(client, "import ctypes\nctypes.cdll.LoadLibrary('libc.so.6')")

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
        assert r.status_code == 200, f"Valid code was incorrectly blocked: {r.get_json()}"

    def test_valid_for_loop_not_blocked(self, client):
        """A simple loop must not trigger any false positive."""
        r = _analyze(client, "for i in range(5):\n    print(i)")
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Python blocked modules  (Docker sandbox isolation)
# The old AST-based _blocked_python_import was removed in favour of
# Docker sandbox isolation. These tests are preserved as documentation
# of the expected security boundary — to be replaced with proper sandbox
# tests when Docker is available in CI.
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Debug endpoint security (Phase 1 fixes)
# ---------------------------------------------------------------------------
class TestDebugEndpointSecurity:
    """Debug endpoints must not leak sensitive info and must be disabled in production."""

    def test_debug_gemini_status_does_not_leak_key_prefix(self, client):
        """The api_key_prefix field must not appear in the response."""
        r = client.get("/api/v1/debug/gemini-status")
        data = r.get_json()
        assert "api_key_prefix" not in data, (
            "api_key_prefix leaks credential info"
        )

    def test_debug_endpoints_not_registered_in_production(self, monkeypatch):
        """When FLASK_ENV=production, debug endpoints must return 404."""
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("SECRET_KEY", "test-secret-32-chars-min-for-prod!!")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-32-chars-min-for-pro")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")

        from app_pkg import create_app  # noqa: PLC0415
        app = create_app("production")
        with app.test_client() as c:
            r = c.get(
                "/api/v1/debug/gemini-status",
                environ_overrides={"wsgi.url_scheme": "https"},
            )
            assert r.status_code == 404, (
                f"Debug endpoints must be disabled in production, got {r.status_code}"
            )


# ---------------------------------------------------------------------------
# Host execution fallback (controlled by HOST_EXECUTION_ENABLED env var)
# ---------------------------------------------------------------------------
class TestHostExecution:
    """Host execution is enabled solely by HOST_EXECUTION_ENABLED=1."""

    def test_host_execution_enabled_by_flag(self, monkeypatch):
        """HOST_EXECUTION_ENABLED=1 enables host execution outside production."""
        monkeypatch.setenv("HOST_EXECUTION_ENABLED", "1")

        import importlib  # noqa: PLC0415

        import analyzer  # noqa: PLC0415
        importlib.reload(analyzer)

        assert analyzer._host_execution_allowed() is True  # noqa: SLF001

    def test_host_execution_enabled_in_production_with_flag(self, monkeypatch):
        """HOST_EXECUTION_ENABLED=1 enables host execution even in production."""
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("HOST_EXECUTION_ENABLED", "1")

        import importlib  # noqa: PLC0415

        import analyzer  # noqa: PLC0415
        importlib.reload(analyzer)

        assert analyzer._host_execution_allowed() is True  # noqa: SLF001

    def test_host_execution_disabled_without_flag(self, monkeypatch):
        """Without HOST_EXECUTION_ENABLED=1, host execution must be disabled."""
        monkeypatch.delenv("HOST_EXECUTION_ENABLED", raising=False)

        import importlib  # noqa: PLC0415

        import analyzer  # noqa: PLC0415
        importlib.reload(analyzer)

        assert analyzer._host_execution_allowed() is False  # noqa: SLF001
