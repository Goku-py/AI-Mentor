from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple
import httpx
import asyncio


@dataclass
class Issue:
    line: int
    severity: str
    code: str
    message: str


def verify_tools() -> Dict[str, bool]:
    """Check which compilation/execution tools are available on the system."""
    tools = {
        "python": False,
        "javascript": False,
        "java": False,
        "c": False,
        "cpp": False,
    }
    
    tool_commands = {
        "python": [sys.executable, "--version"],
        "javascript": ["node", "--version"],
        "java": ["javac", "-version"],
        "c": ["gcc", "--version"],
        "cpp": ["g++", "--version"],
    }
    
    for lang, cmd in tool_commands.items():
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
            )
            tools[lang] = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools[lang] = False
    
    return tools



def _empty_execution() -> Dict[str, Any]:
    return {
        "stdout": "",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
        "tool_missing": False,
        "error": None,
    }


def _sandbox_env() -> Dict[str, str]:
    env = os.environ.copy()
    # Best-effort network disabling through subprocess environment overrides.
    env.update(
        {
            "NO_NETWORK": "1",
            "http_proxy": "",
            "https_proxy": "",
            "HTTP_PROXY": "",
            "HTTPS_PROXY": "",
            "all_proxy": "",
            "ALL_PROXY": "",
            "no_proxy": "*",
            "NO_PROXY": "*",
        }
    )
    return env


def _limit_resources_linux() -> None:
    if not sys.platform.startswith("linux"):
        return
    import resource

    memory_limit = 64 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))


def _blocked_python_import(code: str) -> Optional[str]:
    blocked_modules = {"os", "sys", "subprocess"}
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".", 1)[0]
                if root_module in blocked_modules:
                    return root_module
        elif isinstance(node, ast.ImportFrom) and node.module:
            root_module = node.module.split(".", 1)[0]
            if root_module in blocked_modules:
                return root_module
    return None


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


def _python_error_help(exc_type: str, message: str, difficulty: str = "beginner", line: Optional[int] = None) -> Dict[str, Any]:
    """Return explanation and suggestions for common Python runtime errors.
    
    Args:
        exc_type: The exception type name
        message: The error message
        difficulty: "beginner", "intermediate", or "advanced"
        line: The line number where error occurred (for beginner difficulty)
    """
    exc_type = exc_type or ""
    
    # Default beginner explanations
    explanation = "Your program raised a runtime error."
    suggestions: List[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Print intermediate values to understand what the program is doing before it crashes.",
    ]

    if exc_type == "ZeroDivisionError":
        if difficulty == "beginner":
            explanation = "You attempted to divide by zero, which is not allowed in mathematics or Python."
            if line:
                explanation += f" Check line {line}."
            suggestions = [
                "Check the value of the denominator before dividing.",
                "Guard the division with an `if denominator != 0:` condition.",
            ]
        elif difficulty == "intermediate":
            explanation = "The code is attempting a division operation where the divisor equals zero."
            suggestions = [
                "Review the mathematical operation that's failing.",
                "Add a conditional check before division operations.",
            ]
        else:  # advanced
            explanation = "Division by zero"
            suggestions = []
    elif exc_type == "NameError":
        if difficulty == "beginner":
            explanation = "Python tried to use a variable or name that has not been defined yet."
            if line:
                explanation += f" Look at line {line}."
            suggestions = [
                "Make sure the variable is defined before you use it.",
                "Check for typos in the variable or function name.",
            ]
        elif difficulty == "intermediate":
            explanation = "A variable or function is being referenced that hasn't been defined in the current scope."
            suggestions = [
                "Ensure all names are defined before use.",
                "Check for scope issues.",
            ]
        else:  # advanced
            explanation = "Undefined name reference"
            suggestions = []
    elif exc_type == "TypeError":
        if difficulty == "beginner":
            explanation = "An operation or function was applied to a value of an inappropriate type."
            if line:
                explanation += f" Check the types on line {line}."
            suggestions = [
                "Check the types of the variables used on the failing line.",
                "Convert values to the expected type (for example, `int(...)` or `str(...)`).",
            ]
        elif difficulty == "intermediate":
            explanation = "An operation was performed on incompatible data types."
            suggestions = [
                "Review type compatibility for the operation being performed.",
                "Consider type conversion if needed.",
            ]
        else:  # advanced
            explanation = "Type mismatch"
            suggestions = []
    elif exc_type == "IndexError":
        if difficulty == "beginner":
            explanation = "You tried to access a list (or similar container) at a position that does not exist."
            if line:
                explanation += f" Review line {line}."
            suggestions = [
                "Check the length of the list before indexing.",
                "Remember that valid indices go from 0 up to `len(list) - 1`.",
            ]
        elif difficulty == "intermediate":
            explanation = "An index is out of bounds for the container being accessed."
            suggestions = [
                "Verify the container's size before indexing.",
                "Check boundary conditions in loops.",
            ]
        else:  # advanced
            explanation = "Index out of bounds"
            suggestions = []
    elif exc_type == "KeyError":
        if difficulty == "beginner":
            explanation = "You tried to access a dictionary key that does not exist."
            if line:
                explanation += f" Check line {line}."
            suggestions = [
                "Use `in` to check whether a key exists before accessing it.",
                "Use `dict.get(key, default)` if the key might be missing.",
            ]
        elif difficulty == "intermediate":
            explanation = "The code attempts to access a dictionary with a key that isn't present."
            suggestions = [
                "Check key existence before access.",
                "Use defensive dictionary access methods.",
            ]
        else:  # advanced
            explanation = "Missing dictionary key"
            suggestions = []

    return {
        "type": exc_type,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _parse_python_traceback(stderr: str, difficulty: str = "beginner") -> Dict[str, Any]:
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

    help_data = _python_error_help(str(exc_type) if exc_type else "", exc_message, difficulty=difficulty, line=line_number)
    help_data["line"] = line_number
    return help_data


def _run_python(code: str, timeout: float = 3.0, difficulty: str = "beginner") -> Dict[str, Any]:
    execution = _empty_execution()

    blocked_module = _blocked_python_import(code)
    if blocked_module is not None:
        execution["returncode"] = 1
        execution["stderr"] = f"Blocked import: {blocked_module}"
        execution["error"] = {
            "type": "SecurityError",
            "message": f"Import '{blocked_module}' is not allowed in this execution environment.",
            "line": None,
            "explanation": "This sandbox blocks modules that allow process and system access.",
            "suggestions": [
                "Remove the blocked import and use safer alternatives.",
                "If you only need basic output, use print and pure-Python logic instead.",
            ],
        }
        return execution

    run_kwargs: Dict[str, Any] = {
        "input": code,
        "capture_output": True,
        "text": True,
        "timeout": timeout,
        "env": _sandbox_env(),
    }
    if sys.platform.startswith("linux"):
        run_kwargs["preexec_fn"] = _limit_resources_linux

    try:
        completed = subprocess.run(
            [sys.executable],
            **run_kwargs,
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
        execution["error"] = _parse_python_traceback(execution["stderr"], difficulty=difficulty)

    return execution


def _javascript_error_help(error_name: str, message: str, difficulty: str = "beginner", line: Optional[int] = None) -> Dict[str, Any]:
    """Return explanation and suggestions for common JavaScript runtime errors.
    
    Args:
        error_name: The error type name
        message: The error message
        difficulty: "beginner", "intermediate", or "advanced"
        line: The line number where error occurred (for beginner difficulty)
    """
    error_name = error_name or ""
    
    # Default beginner explanations
    explanation = "Your JavaScript program raised a runtime error."
    suggestions: List[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Use console.log to inspect values before the program crashes.",
    ]

    if error_name == "ReferenceError":
        if difficulty == "beginner":
            explanation = "JavaScript tried to use a variable that does not exist in the current scope."
            if line:
                explanation += f" Look at line {line}."
            suggestions = [
                "Make sure the variable is declared before it is used.",
                "Check for typos in the variable or function name.",
            ]
        elif difficulty == "intermediate":
            explanation = "A variable or function is being referenced that hasn't been defined in the current scope."
            suggestions = [
                "Ensure all names are declared before use.",
                "Check for scope issues.",
            ]
        else:  # advanced
            explanation = "Undefined identifier reference"
            suggestions = []
    elif error_name == "TypeError":
        if difficulty == "beginner":
            explanation = "An operation was performed on a value of an unexpected type."
            if line:
                explanation += f" Check line {line}."
            suggestions = [
                "Check that objects and functions are what you expect before using them.",
                "Guard property access with checks like `if (obj && obj.prop) { ... }`.",
            ]
        elif difficulty == "intermediate":
            explanation = "An operation was attempted on an incompatible type."
            suggestions = [
                "Verify type compatibility before operations.",
                "Use type checks or guards.",
            ]
        else:  # advanced
            explanation = "Type mismatch"
            suggestions = []
    elif error_name == "SyntaxError":
        if difficulty == "beginner":
            explanation = "There is a mistake in the JavaScript syntax, so the engine cannot parse the code."
            if line:
                explanation += f" Review line {line}."
            suggestions = [
                "Look for missing brackets, parentheses, or commas near the reported location.",
                "Use a code editor with syntax highlighting to spot the error more easily.",
            ]
        elif difficulty == "intermediate":
            explanation = "The code contains syntactic errors that prevent parsing."
            suggestions = [
                "Check bracket/paren/brace matching.",
                "Look for missing punctuation.",
            ]
        else:  # advanced
            explanation = "Syntax error"
            suggestions = []

    return {
        "type": error_name,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _parse_node_error(stderr: str, difficulty: str = "beginner") -> Dict[str, Any]:
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

    help_data = _javascript_error_help(str(error_name) if error_name else "", message, difficulty=difficulty, line=line_number)
    help_data["line"] = line_number
    return help_data


def _run_node(code: str, timeout: float = 3.0, difficulty: str = "beginner") -> Dict[str, Any]:
    execution = _empty_execution()

    try:
        completed = subprocess.run(
            ["node"],
            input=code,
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
        execution["error"] = _parse_node_error(execution["stderr"], difficulty=difficulty)

    return execution


def _analyze_python(code: str, difficulty: str = "beginner") -> Tuple[List[Issue], Dict[str, Any]]:
    issues: List[Issue] = []
    syntax_issues, syntax_exc = _check_syntax(code)
    issues.extend(syntax_issues)
    issues.extend(_line_based_checks(code))

    execution = _empty_execution()
    if syntax_exc is None:
        execution = _run_python(code, difficulty=difficulty)
    else:
        # Mirror the syntax error into the execution block so the UI can show it
        execution["error"] = _python_error_help("SyntaxError", str(syntax_exc), difficulty=difficulty, line=syntax_exc.lineno or 1)
        execution["error"]["line"] = syntax_exc.lineno or 1
        execution["stderr"] = str(syntax_exc)
        execution["returncode"] = 1

    return issues, execution


def _analyze_javascript(code: str, difficulty: str = "beginner") -> Tuple[List[Issue], Dict[str, Any]]:
    # Reuse generic line-based checks for JavaScript as well
    issues = _line_based_checks(code)
    execution = _run_node(code, difficulty=difficulty)
    return issues, execution


def _parse_gcc_output(output: str, language_label: str) -> List[Issue]:
    """
    Parse GCC / G++ style diagnostics into Issue objects.
    Example line: main.c:10:5: error: expected ';' before 'return'
    """
    issues: List[Issue] = []
    if not output:
        return issues

    pattern = re.compile(r"^(.*?):(\d+):\d*:\s*(warning|error):\s*(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        _file, line_str, level, msg = match.groups()
        try:
            line_no = int(line_str)
        except ValueError:
            line_no = 1
        severity = "warning" if level == "warning" else "error"
        code = f"{language_label.upper()}_{level.upper()}"
        issues.append(Issue(line=line_no, severity=severity, code=code, message=msg.strip()))
    return issues


def _parse_java_compile_output(output: str) -> List[Issue]:
    """
    Parse javac diagnostics like:
      Main.java:10: error: ';' expected
    """
    issues: List[Issue] = []
    if not output:
        return issues

    pattern = re.compile(r"^(.*?):(\d+):\s*(warning|error):\s*(.*)$")
    for line in output.splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        _file, line_str, level, msg = match.groups()
        try:
            line_no = int(line_str)
        except ValueError:
            line_no = 1
        severity = "warning" if level == "warning" else "error"
        code = f"JAVA_{level.upper()}"
        issues.append(Issue(line=line_no, severity=severity, code=code, message=msg.strip()))
    return issues


def _parse_java_runtime_error(stderr: str) -> Dict[str, Any]:
    """
    Best-effort extraction of Java runtime exception information.
    """
    if not stderr:
        return {"type": None, "message": "", "line": None, "explanation": "", "suggestions": []}

    lines = stderr.strip().splitlines()
    exc_type: Optional[str] = None
    message = ""
    line_number: Optional[int] = None

    # Look for line with "...Exception: message"
    for line in lines:
        if "Exception" in line and ":" in line:
            # e.g., Exception in thread "main" java.lang.NullPointerException: msg
            parts = line.split("Exception", 1)
            tail = "Exception" + parts[1]
            type_and_message = tail.split(":", 1)
            exc_type = type_and_message[0].strip()
            message = type_and_message[1].strip() if len(type_and_message) > 1 else ""
            break

    # Look for "(Main.java:line)"
    loc_pattern = re.compile(r"\((?:.*\.java):(\d+)\)")
    for line in lines:
        m = loc_pattern.search(line)
        if m:
            try:
                line_number = int(m.group(1))
                break
            except ValueError:
                pass

    explanation = "Your Java program threw a runtime exception."
    suggestions: List[str] = [
        "Check the line mentioned in the stack trace to see what values are being used.",
        "Add print statements or use a debugger to inspect variables before the crash.",
    ]

    if exc_type is not None and "NullPointerException" in str(exc_type):
        explanation = "You are trying to use an object reference that is null."
        suggestions = [
            "Ensure the object is initialized before you call methods or access fields on it.",
            "Check for null and handle it explicitly before using the variable.",
        ]

    return {
        "type": exc_type,
        "message": message,
        "line": line_number,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _run_gcc(source_code: str, language_label: str, compiler: str, source_name: str, timeout: float = 3.0) -> Tuple[List[Issue], Dict[str, Any]]:
    """
    Compile and run C or C++ code using gcc/g++.
    """
    compile_issues: List[Issue] = []
    execution = _empty_execution()

    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = os.path.join(tmp_dir, source_name)
        binary_path = os.path.join(tmp_dir, "program")

        with open(source_path, "w", encoding="utf-8") as f:
            f.write(source_code)

        compile_kwargs: Dict[str, Any] = {
            "cwd": tmp_dir,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "env": _sandbox_env(),
        }
        run_kwargs: Dict[str, Any] = {
            "cwd": tmp_dir,
            "capture_output": True,
            "text": True,
            "timeout": timeout,
            "env": _sandbox_env(),
        }
        if sys.platform.startswith("linux"):
            compile_kwargs["preexec_fn"] = _limit_resources_linux
            run_kwargs["preexec_fn"] = _limit_resources_linux

        try:
            compile_proc = subprocess.run(
                [compiler, source_path, "-o", binary_path],
                **compile_kwargs,
            )
        except FileNotFoundError:
            execution["tool_missing"] = True
            execution["error"] = {
                "type": f"{compiler}_NotFound",
                "message": f"Compiler '{compiler}' was not found on the server.",
                "line": None,
                "explanation": f"The server cannot compile {language_label.upper()} code because '{compiler}' is not installed or not on PATH.",
                "suggestions": [
                    f"Install {compiler} (for example via MSYS2/MinGW or TDM-GCC) and ensure it is on your PATH.",
                    "After installing, restart the server and try again.",
                ],
            }
            return compile_issues, execution
        except subprocess.TimeoutExpired as exc:
            execution["stdout"] = exc.stdout or ""
            execution["stderr"] = exc.stderr or ""
            execution["returncode"] = -1
            execution["timed_out"] = True
            execution["error"] = {
                "type": "Timeout",
                "message": "Compilation took too long and was stopped.",
                "line": None,
                "explanation": "The compiler did not finish within the allowed time limit.",
                "suggestions": [
                    "Check for extremely large source code or complex templates/macros.",
                    "Try simplifying the program or compiling a smaller piece.",
                ],
            }
            return compile_issues, execution

        if compile_proc.returncode != 0:
            execution["stderr"] = compile_proc.stderr or ""
            execution["returncode"] = compile_proc.returncode
            compile_issues.extend(_parse_gcc_output(compile_proc.stderr or "", language_label))
            if not execution["error"]:
                execution["error"] = {
                    "type": "CompileError",
                    "message": "Compilation failed. See errors below.",
                    "line": None,
                    "explanation": f"The {language_label.upper()} compiler reported one or more errors.",
                    "suggestions": [
                        "Read each compiler error from top to bottom; often the first message is the most important.",
                        "Fix the earliest error, then recompile to see if later errors disappear.",
                    ],
                }
            return compile_issues, execution

        # Run the compiled program
        try:
            run_proc = subprocess.run(
                [binary_path],
                **run_kwargs,
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
            return compile_issues, execution

        execution["stdout"] = run_proc.stdout or ""
        execution["stderr"] = run_proc.stderr or ""
        execution["returncode"] = run_proc.returncode

        if run_proc.returncode != 0 and not execution["error"]:
            execution["error"] = {
                "type": "RuntimeError",
                "message": "The program exited with a non-zero status code.",
                "line": None,
                "explanation": "A non-zero exit code usually means the program hit a runtime error such as division by zero, invalid memory access, or an explicit `return 1`.",
                "suggestions": [
                    "Add print statements before the suspected failing line to see which values are being used.",
                    "Check for invalid array indices, null pointers, or divisions where the denominator may be zero.",
                ],
            }

    return compile_issues, execution


def _analyze_c(code: str) -> Tuple[List[Issue], Dict[str, Any]]:
    style_issues = _line_based_checks(code)
    compile_issues, execution = _run_gcc(code, "c", "gcc", "main.c")
    issues = style_issues + compile_issues
    return issues, execution


def _analyze_cpp(code: str) -> Tuple[List[Issue], Dict[str, Any]]:
    style_issues = _line_based_checks(code)
    compile_issues, execution = _run_gcc(code, "cpp", "g++", "main.cpp")
    issues = style_issues + compile_issues
    return issues, execution


def _analyze_java(code: str, timeout: float = 3.0) -> Tuple[List[Issue], Dict[str, Any]]:
    style_issues = _line_based_checks(code)
    execution = _empty_execution()
    compile_issues: List[Issue] = []

    match = re.search(r'public\s+(?:final\s+)?class\s+(\w+)', code)
    class_name = match.group(1) if match else "Main"

    with tempfile.TemporaryDirectory() as tmp_dir:
        source_path = os.path.join(tmp_dir, f"{class_name}.java")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(code)

        try:
            compile_proc = subprocess.run(
                ["javac", source_path],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            execution["tool_missing"] = True
            execution["error"] = {
                "type": "JavacNotFound",
                "message": "Java compiler ('javac') was not found on the server.",
                "line": None,
                "explanation": "The server cannot compile Java code because the JDK tools are not installed or not on PATH.",
                "suggestions": [
                    "Install a JDK (for example Temurin or Oracle JDK) and ensure 'javac' is on your PATH.",
                    "After installing, restart the server and try again.",
                ],
            }
            return style_issues, execution
        except subprocess.TimeoutExpired as exc:
            execution["stdout"] = exc.stdout or ""
            execution["stderr"] = exc.stderr or ""
            execution["returncode"] = -1
            execution["timed_out"] = True
            execution["error"] = {
                "type": "Timeout",
                "message": "Java compilation took too long and was stopped.",
                "line": None,
                "explanation": "The Java compiler did not finish within the allowed time limit.",
                "suggestions": [
                    "Check for extremely large source files or complex generics.",
                    "Try simplifying the program or compiling a smaller piece.",
                ],
            }
            return style_issues, execution

        if compile_proc.returncode != 0:
            stderr = compile_proc.stderr or ""
            execution["stderr"] = stderr
            execution["returncode"] = compile_proc.returncode
            compile_issues.extend(_parse_java_compile_output(stderr))
            if not execution["error"]:
                execution["error"] = {
                    "type": "CompileError",
                    "message": "Java compilation failed. See errors below.",
                    "line": None,
                    "explanation": "The Java compiler reported one or more errors.",
                    "suggestions": [
                        "Fix the first error reported by javac; later errors may be side effects.",
                        "Ensure your public class name matches the file name (here: Main).",
                    ],
                }
            issues = style_issues + compile_issues
            return issues, execution

        # If compilation succeeded, try to run the program.
        try:
            run_proc = subprocess.run(
                ["java", class_name],
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError:
            execution["tool_missing"] = True
            execution["error"] = {
                "type": "JavaRuntimeNotFound",
                "message": "Java runtime ('java') was not found on the server.",
                "line": None,
                "explanation": "The server cannot run Java programs because the Java runtime is not installed or not on PATH.",
                "suggestions": [
                    "Install a JDK/JRE and ensure the 'java' command is available.",
                    "After installing, restart the server and try again.",
                ],
            }
            issues = style_issues + compile_issues
            return issues, execution
        except subprocess.TimeoutExpired as exc:
            execution["stdout"] = exc.stdout or ""
            execution["stderr"] = exc.stderr or ""
            execution["returncode"] = -1
            execution["timed_out"] = True
            execution["error"] = {
                "type": "Timeout",
                "message": "Java program execution took too long and was stopped (possible infinite loop or heavy computation).",
                "line": None,
                "explanation": "The program did not finish within the allowed time limit.",
                "suggestions": [
                    "Check for infinite loops or very slow operations.",
                    "Try running a smaller piece of the program or simplifying the logic.",
                ],
            }
            issues = style_issues + compile_issues
            return issues, execution

        execution["stdout"] = run_proc.stdout or ""
        execution["stderr"] = run_proc.stderr or ""
        execution["returncode"] = run_proc.returncode

        if run_proc.returncode != 0:
            execution["error"] = _parse_java_runtime_error(execution["stderr"])

    issues = style_issues + compile_issues
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


def _get_valid_gemini_api_key() -> Optional[str]:
    """Read and validate GEMINI_API_KEY from environment."""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()

    # Guard against accidentally quoted values from environment providers.
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1].strip()

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return None

    return api_key


def _extract_gemini_text(response_json: Dict[str, Any]) -> Optional[str]:
    """Extract model text from Gemini generateContent response."""
    candidates = response_json.get("candidates")
    if not isinstance(candidates, list):
        return None

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str) and part["text"].strip():
                return part["text"].strip()
    return None


def _map_gemini_http_error(status_code: int, body_text: str, error_message: str) -> str:
    """Map Gemini API failures to stable app-level status codes."""
    haystack = f"{error_message}\n{body_text}".lower()

    if status_code == 403 and (
        "api has not been used" in haystack
        or "service disabled" in haystack
        or "is disabled" in haystack
    ):
        return "AI_MENTOR_API_DISABLED"

    if status_code == 429 or "quota" in haystack or "rate limit" in haystack:
        return "AI_MENTOR_QUOTA_EXCEEDED"

    return "AI_MENTOR_API_ERROR"


async def _get_ai_mentorship(code: str, language: str, execution: dict, issues: List[dict], difficulty: str = "beginner") -> str:
    api_key = _get_valid_gemini_api_key()
    if not api_key:
        return "AI_MENTOR_DISABLED"

    try:
        # Build comprehensive error context including all issues and execution errors
        error_context = ""
        all_errors = []
        
        # Collect static issues (compilation, syntax errors, etc.)
        static_errors = [i for i in issues if i.get('severity') == 'error']
        for iss in static_errors:
            all_errors.append({
                'line': iss.get('line'),
                'type': iss.get('code', 'ERROR'),
                'message': iss.get('message'),
                'severity': 'error'
            })
            error_context += f"Line {iss.get('line')}: {iss.get('message')}\n"
        
        # Add execution/runtime errors
        if execution.get('error'):
            exec_error = execution['error']
            error_line = exec_error.get('line', '?')
            all_errors.append({
                'line': error_line,
                'type': exec_error.get('type', 'RuntimeError'),
                'message': exec_error.get('message', ''),
                'explanation': exec_error.get('explanation', ''),
                'severity': 'error'
            })
            error_context += f"Line {error_line}: {exec_error.get('type')} - {exec_error.get('message')}\n"
        
        # If no errors, check for warnings
        if not all_errors:
            warnings = [i for i in issues if i.get('severity') == 'warning']
            for warn in warnings:
                error_context += f"Line {warn.get('line')}: {warn.get('message')}\n"
        
        # If there are any issues/errors, generate AI feedback
        if all_errors or error_context:
            # Number each source line so the model can cite them precisely
            numbered_lines = "\n".join(
                f"{i}: {line}" for i, line in enumerate(code.splitlines(), start=1)
            )

            # Generate difficulty-specific prompt
            if difficulty == "beginner":
                prompt = (
                    "You are a strict coding instructor helping a beginner. A student submitted code that has errors.\n"
                    "RULES YOU MUST FOLLOW:\n"
                    "- For EVERY issue you mention, you MUST reference the exact line number.\n"
                    "- Use simple, plain language that a beginner can understand.\n"
                    "- Explain what is wrong in simple terms.\n"
                    "- Give a HINT toward the exact line or concept that needs fixing.\n"
                    "- Do NOT give the corrected code.\n"
                    "- Be VERY BRIEF — max 3 sentences per error.\n\n"
                    f"Detected issues:\n{error_context}\n\n"
                    f"Student code ({language}) with line numbers:\n"
                    f"```\n{numbered_lines}\n```"
                )
            elif difficulty == "intermediate":
                prompt = (
                    "You are a coding instructor helping an intermediate student. A student submitted code that has errors.\n"
                    "RULES YOU MUST FOLLOW:\n"
                    "- Explain the CONCEPT or PRINCIPLE behind each error, not the specific line details.\n"
                    "- Do NOT reference line numbers directly.\n"
                    "- Help the student understand the underlying concept that needs to be applied.\n"
                    "- Give a hint that guides without referencing specific lines.\n"
                    "- Do NOT give the corrected code.\n"
                    "- Be BRIEF and focused on conceptual understanding.\n\n"
                    f"Detected issues:\n{error_context}\n\n"
                    f"Student code ({language}) with line numbers:\n"
                    f"```\n{numbered_lines}\n```"
                )
            else:  # advanced
                prompt = (
                    "You are a coding mentor for an advanced student. A student submitted code that has errors.\n"
                    "RULES YOU MUST FOLLOW:\n"
                    "- Identify ONLY the core concepts or principles that are wrong.\n"
                    "- Do NOT provide line references, code quotes, or detailed explanations.\n"
                    "- Be VERY TERSE — list only the concept names or brief concept descriptions.\n"
                    "- Do NOT explain or give hints.\n"
                    "- Do NOT reference specific code.\n\n"
                    f"Detected issues:\n{error_context}\n\n"
                    f"Student code ({language}) with line numbers:\n"
                    f"```\n{numbered_lines}\n```"
                )

            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/gemini-2.5-flash:generateContent?key={urllib.parse.quote_plus(api_key)}"
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            }
                        ]
                    }
                ]
            }

            _MAX_RETRIES = 3
            async with httpx.AsyncClient(timeout=15.0) as client:
                for _attempt in range(_MAX_RETRIES):
                    try:
                        response = await client.post(endpoint, json=payload)
                        status_code = response.status_code
                        raw_body = response.text
                        if status_code == 429 and _attempt < _MAX_RETRIES - 1:
                            backoff = 2 ** _attempt
                            print(f"[Gemini] Rate limited (429). Retrying in {backoff}s...", file=sys.stderr)
                            await asyncio.sleep(backoff)
                            continue
                        break
                    except httpx.RequestError as exc:
                        print(f"[Gemini] Network error: {exc}", file=sys.stderr)
                        return "AI_MENTOR_API_ERROR"
                    
            if status_code < 200 or status_code >= 300:
                print(f"[Gemini] Unexpected status: {status_code}", file=sys.stderr)
                return "AI_MENTOR_API_ERROR"

            try:
                parsed = json.loads(raw_body)
            except json.JSONDecodeError as decode_err:
                preview = raw_body[:180].replace("\n", " ")
                print(
                    f"[Gemini] JSON decode failed on success response: {decode_err}. body_preview={preview}",
                    file=sys.stderr,
                )
                return "AI_MENTOR_BAD_RESPONSE"

            feedback_text = _extract_gemini_text(parsed)
            if feedback_text:
                return feedback_text

            return "LOOKS_GOOD"
        else:
            # No errors found
            return "LOOKS_GOOD"
    except Exception as e:
        err_msg = str(e)
        print(f"[Gemini] Error with AI Mentor: {err_msg}", file=sys.stderr)
        return "AI_MENTOR_DISABLED"

async def analyze_code(code: str, language: str = "python", difficulty: str = "beginner") -> Dict[str, Any]:
    """
    Analyze source code and return a structured result.
    Runs subprocess execute functions in an isolated thread.
    
    Args:
        code: The source code to analyze
        language: Programming language (python, javascript, java, c, cpp)
        difficulty: "beginner", "intermediate", or "advanced"
    """
    if not isinstance(code, str):
        raise TypeError("code must be a string")

    language = (language or "python").lower()
    lines = code.splitlines()

    if language == "python":
        issues, execution = await asyncio.to_thread(_analyze_python, code, difficulty)
    elif language in {"javascript", "js"}:
        language = "javascript"
        issues, execution = await asyncio.to_thread(_analyze_javascript, code, difficulty)
    elif language == "java":
        issues, execution = await asyncio.to_thread(_analyze_java, code)
    elif language == "c":
        issues, execution = await asyncio.to_thread(_analyze_c, code)
    elif language in {"cpp", "c++"}:
        language = "cpp"
        issues, execution = await asyncio.to_thread(_analyze_cpp, code)
    else:
        issues, execution = await asyncio.to_thread(_analyze_language_not_yet_supported, language)

    issues_dicts = [
        {"line": i.line, "severity": i.severity, "code": i.code, "message": i.message}
        for i in issues
    ]

    error_details = execution.get("error")
    errors_from_issues = [i for i in issues_dicts if i["severity"] == "error"]

    ai_mentor_feedback = await _get_ai_mentorship(code, language, execution, issues_dicts, difficulty=difficulty)

    result: Dict[str, Any] = {
        "ok": True,
        "language": language,
        "summary": {
            "line_count": len(lines),
            "issue_count": len(issues_dicts),
        },
        "issues": issues_dicts,
        "execution": execution,
        "ai_mentor_feedback": ai_mentor_feedback,
    }

    return result

