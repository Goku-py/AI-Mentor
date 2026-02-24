from __future__ import annotations

import ast
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class Issue:
    line: int
    severity: str
    code: str
    message: str


def _empty_execution() -> Dict[str, Any]:
    return {
        "stdout": "",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
        "tool_missing": False,
        "error": None,
    }


def _check_syntax(code: str) -> Tuple[List[Issue], Optional[SyntaxError]]:
    issues: List[Issue] = []
    syntax_exc: Optional[SyntaxError] = None
    try:
        ast.parse(code)
    except SyntaxError as exc:
        syntax_exc = exc
        issues.append(
            Issue(
                line=exc.lineno or 1,
                severity="error",
                code="SYNTAX_ERROR",
                message=str(exc),
            )
        )
    return issues, syntax_exc


def _line_based_checks(code: str) -> List[Issue]:
    issues: List[Issue] = []
    lines = code.splitlines()

    for idx, line in enumerate(lines, start=1):
        if len(line) > 79:
            issues.append(
                Issue(
                    line=idx,
                    severity="warning",
                    code="LONG_LINE",
                    message="Line exceeds 79 characters",
                )
            )

        normalized = line.lower()
        if "todo" in normalized or "fixme" in normalized:
            issues.append(
                Issue(
                    line=idx,
                    severity="info",
                    code="TODO_COMMENT",
                    message="Line contains TODO/FIXME comment",
                )
            )

        if line.rstrip() != line:
            issues.append(
                Issue(
                    line=idx,
                    severity="info",
                    code="TRAILING_WHITESPACE",
                    message="Line has trailing whitespace",
                )
            )

        if line.startswith("\t"):
            issues.append(
                Issue(
                    line=idx,
                    severity="warning",
                    code="TABS_INDENT",
                    message="Line uses tabs for indentation instead of spaces",
                )
            )

    return issues


def _python_error_help(exc_type: str, message: str) -> Dict[str, Any]:
    """Return explanation and suggestions for common Python runtime errors."""
    exc_type = exc_type or ""
    explanation = "Your program raised a runtime error."
    suggestions: List[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Print intermediate values to understand what the program is doing before it crashes.",
    ]

    if exc_type == "ZeroDivisionError":
        explanation = "You attempted to divide by zero, which is not allowed in mathematics or Python."
        suggestions = [
            "Check the value of the denominator before dividing.",
            "Guard the division with an `if denominator != 0:` condition.",
        ]
    elif exc_type == "NameError":
        explanation = "Python tried to use a variable or name that has not been defined yet."
        suggestions = [
            "Make sure the variable is defined before you use it.",
            "Check for typos in the variable or function name.",
        ]
    elif exc_type == "TypeError":
        explanation = "An operation or function was applied to a value of an inappropriate type."
        suggestions = [
            "Check the types of the variables used on the failing line.",
            "Convert values to the expected type (for example, `int(...)` or `str(...)`).",
        ]
    elif exc_type == "IndexError":
        explanation = "You tried to access a list (or similar container) at a position that does not exist."
        suggestions = [
            "Check the length of the list before indexing.",
            "Remember that valid indices go from 0 up to `len(list) - 1`.",
        ]
    elif exc_type == "KeyError":
        explanation = "You tried to access a dictionary key that does not exist."
        suggestions = [
            "Use `in` to check whether a key exists before accessing it.",
            "Use `dict.get(key, default)` if the key might be missing.",
        ]

    return {
        "type": exc_type,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _parse_python_traceback(stderr: str) -> Dict[str, Any]:
    """
    Extract error type, message and line number from a Python traceback.
    """
    if not stderr:
        return {"type": None, "message": "", "line": None, "explanation": "", "suggestions": []}

    lines = stderr.strip().splitlines()
    exc_type = None
    exc_message = ""
    line_number: Optional[int] = None

    # Try to find "File ..., line N" (the last one is usually the crashing line)
    file_line_pattern = re.compile(r'File ".*", line (\d+)')
    for line in lines:
        match = file_line_pattern.search(line)
        if match:
            try:
                line_number = int(match.group(1))
            except ValueError:
                pass

    # The last non-empty line typically looks like "ErrorType: message"
    for candidate in reversed(lines):
        if ":" in candidate:
            parts = candidate.split(":", 1)
            exc_type = parts[0].strip()
            exc_message = parts[1].strip()
            break

    help_data = _python_error_help(exc_type or "", exc_message)
    help_data["line"] = line_number
    return help_data


def _run_python(code: str, timeout: float = 3.0) -> Dict[str, Any]:
    execution = _empty_execution()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = f"{tmp_dir}/main.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            completed = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            execution["stdout"] = exc.stdout or ""
            execution["stderr"] = exc.stderr or ""
            execution["returncode"] = -1
            execution["timed_out"] = True
            execution["error"] = {
                "type": "Timeout",
                "message": "Program execution took too long and was stopped (possible infinite loop or heavy computation).",
                "line": None,
                "explanation": "The program did not finish within the allowed time limit.",
                "suggestions": [
                    "Check for infinite loops or very slow operations.",
                    "Try running a smaller piece of the program or simplifying the logic.",
                ],
            }
            return execution

        execution["stdout"] = completed.stdout or ""
        execution["stderr"] = completed.stderr or ""
        execution["returncode"] = completed.returncode

        if completed.returncode != 0:
            execution["error"] = _parse_python_traceback(execution["stderr"])

    return execution


def _javascript_error_help(error_name: str, message: str) -> Dict[str, Any]:
    """Return explanation and suggestions for common JavaScript runtime errors."""
    error_name = error_name or ""
    explanation = "Your JavaScript program raised a runtime error."
    suggestions: List[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Use console.log to inspect values before the program crashes.",
    ]

    if error_name == "ReferenceError":
        explanation = "JavaScript tried to use a variable that does not exist in the current scope."
        suggestions = [
            "Make sure the variable is declared before it is used.",
            "Check for typos in the variable or function name.",
        ]
    elif error_name == "TypeError":
        explanation = "An operation was performed on a value of an unexpected type."
        suggestions = [
            "Check that objects and functions are what you expect before using them.",
            "Guard property access with checks like `if (obj && obj.prop) { ... }`.",
        ]
    elif error_name == "SyntaxError":
        explanation = "There is a mistake in the JavaScript syntax, so the engine cannot parse the code."
        suggestions = [
            "Look for missing brackets, parentheses, or commas near the reported location.",
            "Use a code editor with syntax highlighting to spot the error more easily.",
        ]

    return {
        "type": error_name,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _parse_node_error(stderr: str) -> Dict[str, Any]:
    """
    Extract error type, message and (best-effort) line number from a Node.js error.
    """
    if not stderr:
        return {"type": None, "message": "", "line": None, "explanation": "", "suggestions": []}

    lines = stderr.strip().splitlines()

    # First line of the stack usually looks like "ErrorName: message"
    first = lines[0]
    error_name = None
    message = ""
    if ":" in first:
        parts = first.split(":", 1)
        error_name = parts[0].strip()
        message = parts[1].strip()

    line_number: Optional[int] = None
    # Search for "at <fn> (<file>:line:column)" patterns
    location_pattern = re.compile(r":(\d+):\d+\)?$")
    for line in lines:
        match = location_pattern.search(line)
        if match:
            try:
                line_number = int(match.group(1))
                break
            except ValueError:
                pass

    help_data = _javascript_error_help(error_name or "", message)
    help_data["line"] = line_number
    return help_data


def _run_node(code: str, timeout: float = 3.0) -> Dict[str, Any]:
    execution = _empty_execution()

    with tempfile.TemporaryDirectory() as tmp_dir:
        script_path = f"{tmp_dir}/main.js"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            completed = subprocess.run(
                ["node", script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            execution["tool_missing"] = True
            execution["error"] = {
                "type": "NodeNotFound",
                "message": "Node.js runtime ('node') was not found on the server.",
                "line": None,
                "explanation": "The server cannot execute JavaScript code because Node.js is not installed or not on PATH.",
                "suggestions": [
                    "Install Node.js and make sure the 'node' command is available in your terminal.",
                    "After installing, restart the server and try again.",
                ],
            }
            return execution
        except subprocess.TimeoutExpired as exc:
            execution["stdout"] = exc.stdout or ""
            execution["stderr"] = exc.stderr or ""
            execution["returncode"] = -1
            execution["timed_out"] = True
            execution["error"] = {
                "type": "Timeout",
                "message": "Program execution took too long and was stopped (possible infinite loop or heavy computation).",
                "line": None,
                "explanation": "The program did not finish within the allowed time limit.",
                "suggestions": [
                    "Check for infinite loops or very slow operations.",
                    "Try running a smaller piece of the program or simplifying the logic.",
                ],
            }
            return execution

        execution["stdout"] = completed.stdout or ""
        execution["stderr"] = completed.stderr or ""
        execution["returncode"] = completed.returncode

        if completed.returncode != 0:
            execution["error"] = _parse_node_error(execution["stderr"])

    return execution


def _analyze_python(code: str) -> Tuple[List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    syntax_issues, syntax_exc = _check_syntax(code)
    issues.extend(syntax_issues)
    issues.extend(_line_based_checks(code))

    execution = _empty_execution()
    if syntax_exc is None:
        execution = _run_python(code)
    else:
        # Mirror the syntax error into the execution block so the UI can show it
        execution["error"] = _python_error_help("SyntaxError", str(syntax_exc))
        execution["error"]["line"] = syntax_exc.lineno or 1
        execution["stderr"] = str(syntax_exc)
        execution["returncode"] = 1

    return issues, execution


def _analyze_javascript(code: str) -> Tuple[List[Issue], Dict[str, Any]]:
    # Reuse generic line-based checks for JavaScript as well
    issues = _line_based_checks(code)
    execution = _run_node(code)
    return issues, execution


def _analyze_language_not_yet_supported(language: str) -> Tuple[List[Issue], Dict[str, Any]]:
    issues: List[Issue] = [
        Issue(
            line=1,
            severity="info",
            code="LANGUAGE_UNSUPPORTED",
            message=(
                f"Language '{language}' is not yet fully supported for compilation/execution "
                "in this demo. Static checks may be limited."
            ),
        )
    ]
    execution = _empty_execution()
    execution["error"] = {
        "type": "LanguageUnsupported",
        "message": f"Execution for language '{language}' is not configured on this server.",
        "line": None,
        "explanation": "Only Python and JavaScript are currently executed. Other languages are reported statically.",
        "suggestions": [
            "Switch to Python or JavaScript to see full compiler-style execution and explanations.",
            "Extend the backend analyzer to integrate the compiler or runtime for this language.",
        ],
    }
    return issues, execution


def analyze_code(code: str, language: str = "python") -> Dict[str, Any]:
    """
    Analyze source code and return a structured result.

    For Python and JavaScript, this runs the code in a separate process to
    capture output and runtime errors, and combines that with rule-based
    static checks. Other languages currently return limited static feedback.
    """
    if not isinstance(code, str):
        raise TypeError("code must be a string")

    language = (language or "python").lower()
    lines = code.splitlines()

    if language == "python":
        issues, execution = _analyze_python(code)
    elif language in {"javascript", "js"}:
        language = "javascript"
        issues, execution = _analyze_javascript(code)
    else:
        issues, execution = _analyze_language_not_yet_supported(language)

    issues_dicts = [asdict(issue) for issue in issues]

    result: Dict[str, Any] = {
        "ok": True,
        "language": language,
        "summary": {
            "line_count": len(lines),
            "issue_count": len(issues_dicts),
        },
        "issues": issues_dicts,
        "execution": execution,
    }

    return result

