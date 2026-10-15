"""
Unit tests for the code analyzer module.

Run with: python -m pytest tests/test_analyzer.py -v
"""

import ast
import json
from unittest.mock import MagicMock

import flask
import pytest
import requests.exceptions

import analyzer
from analyzer import (
    _ai_cache_key,
    _analyze_python,
    _check_syntax,
    _detect_language_mismatch,
    _line_based_checks,
    _parse_gcc_output,
    _parse_java_compile_output,
    _parse_python_traceback,
    _python_error_help,
    _run_gcc,
    _sandbox_image,
    analyze_code,
    core,
    run_in_sandbox,
    sandbox_runtime_status,
    verify_tools,
)

VALID_JS = 'function main() {\n    console.log("hi");\n}\nmain();'
VALID_JAVA = (
    "public class Main {\n"
    "    public static void main(String[] args) {\n"
    '        System.out.println("hi");\n'
    "    }\n"
    "}"
)
VALID_C = '#include <stdio.h>\nint main(void) {\n    printf("hi\\n");\n    return 0;\n}'
PINNED_PYTHON_IMAGE = "python:3.11-slim@sha256:" + "a" * 64
VALID_CPP = '#include <iostream>\nint main() { std::cout << "hello"; return 0; }'
RUNNER_SNIPPETS = {
    "python": "print('hello')",
    "javascript": VALID_JS,
    "java": VALID_JAVA,
    "c": VALID_C,
    "cpp": VALID_CPP,
}
# language -> (expected sandbox image key, token that must appear in cmd)
RUNNER_EXPECTED = {
    "python": ("python", "python"),
    "javascript": ("javascript", "node"),
    "java": ("java", "javac"),
    "c": ("gcc", "gcc"),
    "cpp": ("gcc", "g++"),
}

# conftest's autouse mock_ai_mentorship replaces analyzer.mentorship._get_ai_mentorship
# with a stub for the duration of every test, so grab the real coroutine at import
# time (collection happens before fixtures are applied).
_REAL_GET_AI_MENTORSHIP = analyzer.mentorship._get_ai_mentorship  # noqa: SLF001


class TestToolVerification:
    """Test tool detection functionality."""

    def test_verify_tools_returns_dict(self):
        """verify_tools should return a dictionary."""
        tools = verify_tools()
        assert isinstance(tools, dict)
        assert "python" in tools
        assert "javascript" in tools

    def test_verify_tools_values_are_booleans(self):
        """All tool values should be booleans."""
        tools = verify_tools()
        for tool, available in tools.items():
            assert isinstance(available, bool), f"{tool} should have boolean value"

    def test_python_tool_is_available(self):
        """Python should always be available (we're running tests with it)."""
        tools = verify_tools()
        assert tools["python"] is True

    def test_sandbox_status_shape(self):
        """Sandbox status should include expected security keys."""
        status = sandbox_runtime_status()
        assert "ok" in status
        assert "mode" in status

    def test_sandbox_status_reports_remote_mode(self, monkeypatch):
        """Runner URL configured -> mode is remote, ok pings the runner."""
        monkeypatch.setenv("EXECUTION_RUNNER_URL", "http://runner:5001")
        calls = {}

        class _Resp:
            def raise_for_status(self):
                return None

        def fake_get(url, timeout):
            calls["url"] = url
            calls["timeout"] = timeout
            return _Resp()

        monkeypatch.setattr(core.requests, "get", fake_get)
        status = core.sandbox_runtime_status()
        assert status["ok"] is True
        assert status["mode"] == "remote"
        assert calls["url"] == "http://runner:5001/healthz"

    def test_sandbox_status_remote_unreachable(self, monkeypatch):
        """A dead runner must report ok=False, not fall back to local Docker."""
        monkeypatch.setenv("EXECUTION_RUNNER_URL", "http://runner:5001")

        def boom(url, timeout):
            raise OSError("connection refused")  # noqa: TRY003

        monkeypatch.setattr(core.requests, "get", boom)
        status = core.sandbox_runtime_status()
        assert status["ok"] is False
        assert status["mode"] == "remote"
        assert "unreachable" in status["reason"]

    def test_execution_is_remote_follows_env(self, monkeypatch):
        monkeypatch.delenv("EXECUTION_RUNNER_URL", raising=False)
        assert core.execution_is_remote() is False
        monkeypatch.setenv("EXECUTION_RUNNER_URL", "  ")
        assert core.execution_is_remote() is False
        monkeypatch.setenv("EXECUTION_RUNNER_URL", "http://runner:5001")
        assert core.execution_is_remote() is True

    def test_sandbox_unavailable_returns_safe_error(self, monkeypatch):
        """Missing Docker should fail closed with SandboxUnavailable."""
        monkeypatch.setattr(analyzer, "docker", None)
        execution = run_in_sandbox(
            "print('x')",
            "python",
            "python:3.11-slim",
            ["python", "{source}"],
            timeout=2,
        )
        assert execution["error"] is not None
        assert execution["error"]["type"] == "SandboxUnavailable"


class TestSyntaxChecking:
    """Test Python syntax checking."""

    def test_valid_python_syntax(self):
        """Valid Python code should not raise syntax errors."""
        code = "print('hello')\nx = 10"
        issues, exc = _check_syntax(code)
        assert len(issues) == 0
        assert exc is None

    def test_invalid_python_syntax(self):
        """Invalid Python code should be detected."""
        code = "print('hello'\nx = 10"  # Missing closing paren
        issues, exc = _check_syntax(code)
        assert len(issues) > 0
        assert exc is not None
        assert issues[0].code == "SYNTAX_ERROR"

    def test_syntax_error_has_line_number(self):
        """Syntax errors should include line number."""
        code = "x = 1\nprint('hello'\ny = 2"
        issues, _exc = _check_syntax(code)
        assert issues[0].line > 0


class TestLineLevelChecks:
    """Test line-based code quality checks."""

    def test_long_line_detection(self):
        """Lines exceeding 79 characters should be detected."""
        code = "x = " + "y" * 100  # Way over 79 chars
        issues = _line_based_checks(code)
        assert any(i.code == "LONG_LINE" for i in issues)

    def test_todo_comment_detection(self):
        """TODO/FIXME comments should be detected."""
        code = "# TODO: fix this later\nx = 10"
        issues = _line_based_checks(code)
        assert any(i.code == "TODO_COMMENT" for i in issues)

    def test_trailing_whitespace_detection(self):
        """Trailing whitespace should be detected."""
        code = "x = 10   \ny = 20"
        issues = _line_based_checks(code)
        assert any(i.code == "TRAILING_WHITESPACE" for i in issues)

    def test_tab_indentation_detection(self):
        """Tab indentation should be detected (should use spaces)."""
        code = "\tfor i in range(10):\n\t\tprint(i)"
        issues = _line_based_checks(code)
        assert any(i.code == "TABS_INDENT" for i in issues)


class TestErrorHelp:
    """Test error explanation generation."""

    def test_zero_division_error_help(self):
        """ZeroDivisionError should provide specific help."""
        help_text = _python_error_help("ZeroDivisionError", "division by zero")
        assert "divide by zero" in help_text["explanation"].lower()
        assert len(help_text["suggestions"]) > 0

    def test_name_error_help(self):
        """NameError should provide specific help."""
        help_text = _python_error_help("NameError", "name 'x' is not defined")
        assert "not been defined" in help_text["explanation"].lower()

    def test_unknown_error_generic_help(self):
        """Unknown errors should get generic help."""
        help_text = _python_error_help("UnknownError", "something broke")
        assert "runtime error" in help_text["explanation"].lower()

    def test_traceback_parsing_message_less_exception(self):
        """Exceptions raised without a message should not grab 'Traceback' as type."""
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "test.py", line 1, in <module>\n'
            "ValueError\n"
        )
        result = _parse_python_traceback(stderr)
        assert result["type"] == "ValueError"
        assert result["message"] == ""


class TestAnalyzeCode:
    """Integration tests for the analyze_code function."""

    @pytest.mark.asyncio
    async def test_analyze_valid_python(self):
        """analyze_code should successfully analyze valid Python."""
        code = "x = 10\nprint(x)"
        result = await analyze_code(code, "python")
        assert result["ok"] is True
        assert result["language"] == "python"
        if result["execution"].get("error", {}).get("type") == "SandboxUnavailable":
            assert result["execution"]["returncode"] == -1
        else:
            assert result["execution"]["returncode"] == 0

    @pytest.mark.asyncio
    async def test_analyze_python_with_error(self):
        """analyze_code should detect runtime errors."""
        code = "x = 10 / 0"  # ZeroDivisionError
        result = await analyze_code(code, "python")
        assert result["ok"] is True  # ok=True, but execution has error
        assert result["execution"]["returncode"] != 0 or result["execution"]["error"] is not None

    @pytest.mark.asyncio
    async def test_analyze_invalid_language(self):
        """Unsupported languages should be marked as such."""
        code = 'print("hello")'
        result = await analyze_code(code, "ruby")  # Not supported
        assert (
            "unsupported" in result["ai_mentor_feedback"].lower()
            or result.get("mismatch") is True
            or any(i["code"] == "LANGUAGE_UNSUPPORTED" for i in result["issues"])
        )

    @pytest.mark.asyncio
    async def test_analyze_empty_code(self):
        """analyze_code should handle empty code."""
        result = await analyze_code("", "python")
        assert result["summary"]["line_count"] == 0

    @pytest.mark.asyncio
    async def test_analyze_result_structure(self):
        """analyze_code result should have correct structure."""
        code = 'print("test")'
        result = await analyze_code(code, "python")

        assert "ok" in result
        assert "language" in result
        assert "summary" in result
        assert "issues" in result
        assert "execution" in result
        assert "ai_mentor_feedback" in result
        assert "ai_mentor_status" in result

        assert "line_count" in result["summary"]
        assert "issue_count" in result["summary"]

        assert isinstance(result["issues"], list)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("feedback", "status"),
        [
            ("AI_MENTOR_DISABLED", "disabled"),
            ("AI_MENTOR_API_DISABLED", "disabled"),
            ("AI_MENTOR_API_ERROR", "api_error"),
            ("AI_MENTOR_QUOTA_EXCEEDED", "quota_exceeded"),
            ("AI_MENTOR_BAD_RESPONSE", "bad_response"),
            ("AI_MENTOR_UNKNOWN_FUTURE", "unknown"),
        ],
    )
    async def test_ai_mentor_status_maps_stable_failure_states(self, monkeypatch, feedback, status):
        """Analyze response should expose stable AI status metadata."""

        async def fake_mentorship(*_args, **_kwargs):
            return feedback

        monkeypatch.setattr(analyzer.mentorship, "_get_ai_mentorship", fake_mentorship)
        result = await analyze_code("print('x')", "python")
        assert result["ai_mentor_feedback"] == feedback
        assert result["ai_mentor_status"] == status


class TestLanguageMismatchDetection:
    """Tests for language mismatch heuristics."""

    def test_c_code_detected_as_c_not_cpp(self):
        """C code with stdio/printf markers should detect C."""
        code = '#include <stdio.h>\nint main(void) {\n    printf("hi\\n");\n    return 0;\n}'
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "c"

    def test_cpp_code_detected_as_cpp(self):
        """C++ exclusive markers should detect C++."""
        code = '#include <iostream>\nint main() {\n    std::cout << "hi";\n    return 0;\n}'
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "cpp"

    def test_java_code_detected_as_java_not_cpp(self):
        """Java code should not be mistaken for C++ just because it uses class syntax."""
        code = (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            '        System.out.println("hi");\n'
            "    }\n"
            "}"
        )
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "java"

    def test_java_code_with_new_keyword_detected_as_java(self):
        """Java object construction should not be treated as a C++ signal."""
        code = (
            "public class Main {\n"
            "    public static void main(String[] args) {\n"
            "        Main obj = new Main();\n"
            "        System.out.println(obj);\n"
            "    }\n"
            "}"
        )
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "java"

    def test_java_sample_with_import_and_missing_semicolons_detected_as_java(self):
        """The sample Java snippet should stay classified as Java even with syntax errors."""
        code = (
            "import java.util.Scanner\n"
            "\n"
            "class MistakeProgram {\n"
            "    public static void main(String args[]) {\n"
            "        int a = 10\n"
            "        int b = 0;\n"
            '        System.out.println("A is 10")\n'
            "        MistakeProgram obj = new MistakeProgram();\n"
            "    }\n"
            "}\n"
        )
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "java"

    def test_javascript_code_detected_as_javascript(self):
        """JavaScript markers should still be recognized correctly."""
        code = 'function main() {\n    console.log("hi");\n}'
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "javascript"

    def test_python_code_detected_as_python(self):
        """Python markers should still be recognized correctly."""
        code = 'def main():\n    print("hi")'
        mismatch = _detect_language_mismatch(code, "javascript")
        assert mismatch is not None
        assert mismatch["detected"] == "python"

    def test_c_code_detected_as_c(self):
        """C code with stdio/printf markers should detect C."""
        code = '#include <stdio.h>\nint main(void) {\n    printf("hi\\n");\n    return 0;\n}'
        mismatch = _detect_language_mismatch(code, "python")
        assert mismatch is not None
        assert mismatch["detected"] == "c"

    @pytest.mark.asyncio
    async def test_c_code_submitted_as_cpp_reports_mismatch(self):
        """C code under cpp selection should mismatch as C."""
        code = '#include <stdio.h>\nint main(void) {\n    printf("hi\\n");\n    return 0;\n}'
        result = await analyze_code(code, "cpp")
        assert result["ok"] is False
        assert result["mismatch"] is True
        assert result["detected_language"] == "c"
        assert result["language"] == "cpp"


class TestPythonExecution:
    """Test Python code execution."""

    @pytest.mark.asyncio
    async def test_python_stdout_capture(self):
        """Python stdout should be captured."""
        code = 'print("hello world")'
        result = await analyze_code(code, "python")
        if result["execution"].get("error", {}).get("type") == "SandboxUnavailable":
            assert result["execution"]["returncode"] == -1
        else:
            assert "hello world" in result["execution"]["stdout"]

    @pytest.mark.asyncio
    async def test_python_timeout_detection(self):
        """Infinite loops should timeout (with 1 second limit)."""
        code = "while True: pass"
        result = await analyze_code(code, "python")
        # The _run_python function has a 3.0 second default timeout
        # For this test, we just check that either timeout happened or error occurred
        assert result["execution"]["timed_out"] is True or result["execution"]["error"] is not None

    @pytest.mark.asyncio
    async def test_python_error_parsing(self):
        """RuntimeError should be parsed correctly."""
        code = "x = undefined_variable"
        result = await analyze_code(code, "python")
        assert result["execution"]["error"] is not None


class TestSandboxDeadline:
    """Test the monotonic deadline watchdog for Docker container execution."""

    def test_container_watchdog_kills_on_deadline_exceeded(self, monkeypatch):
        """A container that never completes should be killed by the watchdog."""
        container_mock = MagicMock()
        container_mock.wait.side_effect = requests.exceptions.ReadTimeout("timed out")
        container_mock.logs.return_value = b""
        container_mock.kill = MagicMock()

        client_mock = MagicMock()
        client_mock.containers.run.return_value = container_mock

        mock_docker = MagicMock()
        mock_docker.from_env.return_value = client_mock
        monkeypatch.setattr(analyzer.core, "docker", mock_docker)

        execution = run_in_sandbox(
            "print('x')",
            "python",
            "python:3.11-slim",
            ["python", "{source}"],
            timeout=5,
        )
        assert execution["timed_out"] is True
        assert execution["returncode"] == -1
        assert execution["error"]["type"] == "Timeout"
        container_mock.kill.assert_called_once()


class TestNonPythonSyntaxChecking:
    """Regression guard: Python's parser must not judge other languages.

    ast.parse() rejects valid JavaScript/Java/C source, which used to fabricate
    a SYNTAX_ERROR issue for every non-Python submission.
    """

    def test_valid_javascript_reports_no_syntax_error(self):
        issues, exc = _check_syntax(VALID_JS, "javascript")
        assert issues == []
        assert exc is None

    def test_valid_java_reports_no_syntax_error(self):
        issues, exc = _check_syntax(VALID_JAVA, "java")
        assert issues == []
        assert exc is None

    def test_valid_c_reports_no_syntax_error(self):
        issues, exc = _check_syntax(VALID_C, "c")
        assert issues == []
        assert exc is None

    def test_js_alias_also_skips_python_parser(self):
        issues, exc = _check_syntax(VALID_JS, "js")
        assert issues == []
        assert exc is None

    def test_non_python_source_is_actually_rejected_by_python_parser(self):
        """Sanity check that the samples above really do fail ast.parse()."""
        with pytest.raises(SyntaxError):
            ast.parse(VALID_JS)
        with pytest.raises(SyntaxError):
            ast.parse(VALID_JAVA)
        with pytest.raises(SyntaxError):
            ast.parse(VALID_C)

    def test_python_syntax_error_still_suppresses_execution(self, monkeypatch):
        """_analyze_python must still skip execution when Python fails to parse."""
        executed = []

        def _fake_run_python(code):
            executed.append(code)

        monkeypatch.setattr(analyzer.core, "_run_python", _fake_run_python)

        issues, execution = _analyze_python("def broken(")

        assert executed == []
        assert [i.code for i in issues] == ["SYNTAX_ERROR"]
        assert execution["returncode"] == 1
        assert execution["error"]["type"] == "SyntaxError"


class TestSandboxImagePinning:
    """An unreachable/unconfigured image map must fail closed, never unpinned."""

    def test_no_app_context_means_unavailable(self):
        assert _sandbox_image("python") is None

    def test_configured_image_is_returned(self):
        app = flask.Flask(__name__)
        app.config["SANDBOX_IMAGES"] = {"python": PINNED_PYTHON_IMAGE}
        with app.app_context():
            assert _sandbox_image("python") == PINNED_PYTHON_IMAGE

    def test_unconfigured_language_means_unavailable(self):
        app = flask.Flask(__name__)
        app.config["SANDBOX_IMAGES"] = {"python": PINNED_PYTHON_IMAGE}
        with app.app_context():
            assert _sandbox_image("java") is None

    def test_missing_config_key_means_unavailable(self):
        app = flask.Flask(__name__)
        with app.app_context():
            assert _sandbox_image("python") is None

    def test_never_returns_an_unpinned_tag(self):
        app = flask.Flask(__name__)
        app.config["SANDBOX_IMAGES"] = {"python": PINNED_PYTHON_IMAGE}
        with app.app_context():
            for language in ("python", "javascript", "gcc", "java"):
                image = _sandbox_image(language)
                assert image is None or "@sha256:" in image, language


class TestUnavailableToolPaths:
    """With no pinned image every language reports SandboxUnavailable."""

    @pytest.fixture
    def no_images(self):
        app = flask.Flask(__name__)
        app.config["SANDBOX_IMAGES"] = {}
        with app.app_context():
            yield

    @pytest.mark.usefixtures("no_images")
    def test_run_gcc_reports_unavailable(self):
        issues, execution = _run_gcc(VALID_C, "c", "gcc", "main.c")
        assert issues == []
        assert execution["tool_missing"] is True
        assert execution["returncode"] == -1
        assert execution["error"]["type"] == "SandboxUnavailable"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("no_images")
    async def test_javascript_reports_unavailable(self):
        result = await analyze_code(VALID_JS, "javascript")
        assert result["execution"]["tool_missing"] is True
        assert result["execution"]["returncode"] == -1
        assert result["execution"]["error"]["type"] == "SandboxUnavailable"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("no_images")
    async def test_java_reports_unavailable(self):
        result = await analyze_code(VALID_JAVA, "java")
        assert result["execution"]["error"]["type"] == "SandboxUnavailable"
        assert not any(i["code"] == "SYNTAX_ERROR" for i in result["issues"])

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("no_images")
    async def test_c_reports_unavailable(self):
        result = await analyze_code(VALID_C, "c")
        assert result["execution"]["error"]["type"] == "SandboxUnavailable"


class TestRunnerDispatch:
    """With a runner configured, every language must be POSTed to it verbatim."""

    @pytest.fixture
    def dispatched(self, monkeypatch):
        monkeypatch.setenv("EXECUTION_RUNNER_URL", "http://runner:5001/")
        monkeypatch.setenv("EXECUTION_RUNNER_SECRET", "s3cret")
        app = flask.Flask(__name__)
        app.config["SANDBOX_IMAGES"] = {
            key: f"{key}:tag@sha256:{'a' * 64}" for key in ("python", "javascript", "gcc", "java")
        }
        calls = []

        class _Resp:
            def raise_for_status(self):
                return None

            def json(self):
                return {"stdout": "hello", "stderr": "", "returncode": 0}

        def fake_post(url, json=None, headers=None, timeout=None):
            calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
            return _Resp()

        monkeypatch.setattr(core.requests, "post", fake_post)
        with app.app_context():
            yield calls

    @pytest.mark.parametrize("language", sorted(RUNNER_SNIPPETS))
    @pytest.mark.asyncio
    @pytest.mark.usefixtures("dispatched")
    async def test_language_reaches_runner(self, dispatched, language):
        image_key, token = RUNNER_EXPECTED[language]
        await analyze_code(RUNNER_SNIPPETS[language], language)

        assert len(dispatched) == 1, language
        call = dispatched[0]
        assert call["url"] == "http://runner:5001/execute"
        assert call["headers"]["Authorization"] == "Bearer s3cret"
        assert call["json"]["image"].startswith(f"{image_key}:")
        assert token in " ".join(call["json"]["cmd"])
        assert call["json"]["language"] == language


class TestCompilerOutputParsing:
    """GCC and javac diagnostic parsing."""

    def test_gcc_output_maps_lines_severity_and_codes(self):
        issues = _parse_gcc_output(
            "main.c:10:5: error: expected ';' before 'return'\n"
            "main.c:12:1: warning: unused variable 'x'",
            "c",
        )
        assert [(i.line, i.severity, i.code) for i in issues] == [
            (10, "error", "C_ERROR"),
            (12, "warning", "C_WARNING"),
        ]
        assert issues[0].message == "expected ';' before 'return'"

    def test_gcc_output_honours_language_label(self):
        issues = _parse_gcc_output("main.cpp:3:2: error: bad", "cpp")
        assert [i.code for i in issues] == ["CPP_ERROR"]

    def test_gcc_output_ignores_unstructured_lines(self):
        assert _parse_gcc_output("", "c") == []
        assert _parse_gcc_output("ld: cannot find -lm", "c") == []
        # non-numeric line number must not be coerced into an issue
        assert _parse_gcc_output("main.c:unknown: error: bad", "c") == []

    def test_java_compile_output_maps_line_and_code(self):
        issues = _parse_java_compile_output(
            "Main.java:4: error: ';' expected\nMain.java:9: warning: deprecation",
        )
        assert [(i.line, i.severity, i.code) for i in issues] == [
            (4, "error", "JAVA_ERROR"),
            (9, "warning", "JAVA_WARNING"),
        ]
        assert issues[0].message == "';' expected"

    def test_java_compile_output_ignores_unstructured_lines(self):
        assert _parse_java_compile_output("") == []
        assert _parse_java_compile_output("1 error") == []
        assert _parse_java_compile_output("Note: uses unchecked or unsafe operations.") == []


class TestAiMentorCache:
    """Cache key is (code, language, error_context) — there is no difficulty level."""

    def test_cache_key_is_stable_for_identical_input(self):
        ctx = "Line 1: ZeroDivisionError"
        assert _ai_cache_key("x = 1/0", "python", ctx) == _ai_cache_key(
            "x = 1/0", "python", ctx,
        )

    def test_cache_key_separates_language_and_context(self):
        code = "x = 1/0"
        keys = {
            _ai_cache_key(code, "python", "Line 1: A"),
            _ai_cache_key(code, "java", "Line 1: A"),
            _ai_cache_key(code, "python", "Line 1: B"),
        }
        assert len(keys) == 3

    @pytest.mark.asyncio
    async def test_identical_request_is_served_from_cache(self, monkeypatch):
        """End-to-end: a repeat of the same code+language+context makes no second API call."""
        mentorship = analyzer.mentorship
        monkeypatch.setattr(mentorship, "_check_ai_quota", lambda: False)
        monkeypatch.setattr(mentorship, "_get_valid_gemini_api_key", lambda: "test-key")
        monkeypatch.setattr(mentorship, "_increment_ai_quota", lambda: None)

        calls: list[int] = []

        class _FakeResponse:
            def __init__(self):
                self.status_code = 200
                self.text = json.dumps(
                    {"candidates": [{"content": {"parts": [{"text": f"hint-{len(calls)}"}]}}]},
                )

        class _FakeClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *_exc):
                return False

            async def post(self, *_args, **_kwargs):
                calls.append(1)
                return _FakeResponse()

        monkeypatch.setattr(mentorship.httpx, "AsyncClient", lambda *a, **k: _FakeClient())

        code = "x = 1/0"
        execution = {
            "error": {"type": "ZeroDivisionError", "message": "division by zero", "line": 1},
        }
        issues = [{"line": 1, "severity": "error", "code": "ZERO_DIV", "message": "boom"}]

        cache = mentorship._AI_MENTOR_CACHE  # noqa: SLF001
        cache.clear()
        try:
            first = await _REAL_GET_AI_MENTORSHIP(code, "python", execution, issues)
            assert first == "hint-1"

            cached = await _REAL_GET_AI_MENTORSHIP(code, "python", execution, issues)
            assert cached == "hint-1"
            assert len(calls) == 1, "same code+language+context should hit the cache"

            fresh = await _REAL_GET_AI_MENTORSHIP(code, "java", execution, issues)
            assert len(calls) == 2, "a different language must not reuse the cache entry"
            assert fresh == "hint-2"
        finally:
            cache.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
