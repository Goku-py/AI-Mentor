from __future__ import annotations

import ast
import asyncio
import contextlib
import hashlib
import json
import logging
import os
import re
import subprocess  # nosec B404
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import httpx
from flask import current_app

from app_pkg.security.middleware import SECURITY_METRICS

_logger = logging.getLogger(__name__)


class SafeResult(dict):
    pass


try:
    import docker
    from docker.errors import APIError, ContainerError, DockerException
except ImportError:
    docker = None
    APIError = ContainerError = DockerException = Exception


@dataclass
class Issue:
    line: int
    severity: str
    code: str
    message: str


def verify_tools() -> dict[str, bool]:
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
            subprocess.run(  # nosec B603  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            tools[lang] = True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            tools[lang] = False

    return tools


def _sandbox_image(language: str, fallback: str) -> str:
    """Resolve sandbox image from Flask config (pinned by SHA256 digest).

    Falls back to the provided *fallback* when outside an app context
    (e.g. during import-time tool verification).
    """
    try:
        images = current_app.config.get("SANDBOX_IMAGES", {})
    except RuntimeError:
        return fallback
    return images.get(language, fallback)


def _empty_execution() -> dict[str, Any]:
    return {
        "stdout": "",
        "stderr": "",
        "returncode": 0,
        "timed_out": False,
        "tool_missing": False,
        "error": {},
    }


def _sandbox_env() -> dict[str, str]:
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
        },
    )
    return env


def _limit_resources_linux() -> None:
    if not sys.platform.startswith("linux"):
        return
    import os as _os  # noqa: PLC0415
    import resource  # noqa: PLC0415

    _os.nice(19)
    _os.setpgrp()
    memory_limit = 256 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))


def sandbox_runtime_status() -> dict[str, Any]:
    """Return runtime sandbox readiness for startup checks."""
    status = {
        "ok": False,
        "docker_sdk_installed": docker is not None,
        "docker_daemon_available": False,
        "mode": "unavailable",
        "reason": "",
    }
    if docker is None:
        status["reason"] = "Docker SDK not installed. Sandbox required."
        return status
    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:  # noqa: BLE001
        status["reason"] = f"Docker daemon unavailable: {exc}"
        return status
    status["ok"] = True
    status["docker_daemon_available"] = True
    status["mode"] = "docker"
    return status


def _sandbox_unavailable_execution(message: str, explanation: str) -> dict[str, Any]:
    execution = _empty_execution()
    execution["tool_missing"] = True
    execution["returncode"] = -1
    execution["stderr"] = message
    execution["error"] = {
        "type": "SandboxUnavailable",
        "message": message,
        "line": None,
        "explanation": explanation,
        "suggestions": [
            "Enable Docker daemon access on this server.",
        ],
    }
    return execution


def _host_execution_allowed() -> bool:
    return os.environ.get("HOST_EXECUTION_ENABLED", "").strip() == "1"


def _run_host_sandboxed(
    host_cmd: list[str],
    timeout: int,
    cwd: str | None = None,
) -> dict[str, Any]:
    execution = _empty_execution()
    execution["returncode"] = -1

    try:
        preexec = None
        if sys.platform.startswith("linux"):
            preexec = _limit_resources_linux

        proc = subprocess.run(  # nosec B603  # noqa: S603
            host_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout,
            env=_sandbox_env(),
            preexec_fn=preexec,
            cwd=cwd,
        )
        execution["stdout"] = proc.stdout or ""
        execution["stderr"] = proc.stderr or ""
        execution["returncode"] = proc.returncode
    except subprocess.TimeoutExpired:
        execution["returncode"] = -1
        execution["timed_out"] = True
        execution["error"] = {
            "type": "Timeout",
            "message": "Program execution took too long and was stopped (possible infinite loop or heavy computation).",  # noqa: E501
            "line": None,
            "explanation": "The program did not finish within the allowed time limit.",
            "suggestions": [
                "Check for infinite loops or very slow operations.",
                "Try running a smaller piece of the program or simplifying the logic.",
            ],
        }
    except FileNotFoundError:
        execution["tool_missing"] = True
        execution["returncode"] = -1
        execution["error"] = {
            "type": "ToolNotFound",
            "message": f"Required tool not found: {host_cmd[0] if host_cmd else 'unknown'}",
            "line": None,
            "explanation": "The required compiler or interpreter is not installed on this server.",
            "suggestions": [
                "Install the missing tool or use a different language.",
            ],
        }
    except Exception as exc:  # noqa: BLE001
        execution["returncode"] = -1
        execution["stderr"] = str(exc)

    return execution


def _format_host_cmd(
    cmd: list[str],
    source_path: str,
    tmp_dir: str,
    main_class: str,
) -> list[str]:
    output = os.path.join(tmp_dir, "program")  # noqa: PTH118
    classes = os.path.join(tmp_dir, "classes")  # noqa: PTH118
    os.makedirs(classes, exist_ok=True)  # noqa: PTH103
    return [
        part.format(source=source_path, output=output, classes=classes, main_class=main_class)
        for part in cmd
    ]


def run_in_sandbox(  # noqa: C901, PLR0911, PLR0912, PLR0915
    code: str,
    language: str,
    image: str,
    cmd: Any,
    timeout: int = 10,
) -> dict[str, Any]:
    execution = _empty_execution()
    execution["returncode"] = -1

    language_key = (language or "").strip().lower()
    source_names = {
        "python": "main.py",
        "javascript": "main.js",
        "node": "main.js",
        "c": "main.c",
        "cpp": "main.cpp",
    }
    main_class = "Main"
    if language_key == "java":
        match = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", code)
        if match:
            main_class = match.group(1)
    source_name = source_names.get(
        language_key,
        f"{main_class}.java" if language_key == "java" else "main.txt",
    )

    timeout_seconds = max(1, int(timeout))
    command = cmd
    if isinstance(cmd, (list, tuple)):
        command = [
            part.format(
                source=f"/workspace/{source_name}",
                output="/tmp/program",  # noqa: S108
                classes="/tmp",  # noqa: S108
                main_class=main_class,
            )
            for part in cmd
        ]

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_path = os.path.join(tmp_dir, source_name)  # noqa: PTH118
            with open(source_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                f.write(code)

            if docker is None:
                if _host_execution_allowed():
                    host_cmd = _format_host_cmd(cmd, source_path, tmp_dir, main_class)
                    return _run_host_sandboxed(host_cmd, timeout_seconds, tmp_dir)
                execution = _sandbox_unavailable_execution(
                    "Docker SDK is not installed on this server. Fallback execution is disabled.",
                    "Untrusted code execution requires a sandbox. Host fallback is disabled.",
                )
                run_in_sandbox.last_result = execution
                return execution

            try:
                client = docker.from_env()
            except Exception as docker_err:  # noqa: BLE001
                if _host_execution_allowed():
                    host_cmd = _format_host_cmd(cmd, source_path, tmp_dir, main_class)
                    return _run_host_sandboxed(host_cmd, timeout_seconds, tmp_dir)
                execution = _sandbox_unavailable_execution(
                    f"Docker daemon unavailable: {docker_err}",
                    "Sandbox runtime is required for untrusted code execution.",
                )
                run_in_sandbox.last_result = execution
                return execution
            container = None
            try:
                container = client.containers.run(
                    image=image,
                    command=command,
                    working_dir="/workspace",
                    volumes={tmp_dir: {"bind": "/workspace", "mode": "ro"}},
                    network_disabled=True,
                    mem_limit="256m",
                    cpu_quota=50000,
                    read_only=True,
                    user="65534:65534",
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges:true"],
                    pids_limit=128,
                    remove=False,
                    stdout=True,
                    stderr=True,
                    detach=True,
                    tmpfs={"/tmp": "rw,nosuid,size=128m"},  # noqa: S108
                )
                try:
                    deadline = time.monotonic() + timeout_seconds
                    timed_out = False
                    while True:
                        container.reload()
                        state = (
                            container.attrs.get("State", {})
                            if isinstance(container.attrs, dict)
                            else {}
                        )
                        if not state.get("Running", False):
                            execution["returncode"] = int(state.get("ExitCode", 0) or 0)
                            break
                        if time.monotonic() >= deadline:
                            timed_out = True
                            with contextlib.suppress(APIError):
                                container.kill()
                            container.reload()
                            state = (
                                container.attrs.get("State", {})
                                if isinstance(container.attrs, dict)
                                else {}
                            )
                            execution["returncode"] = int(state.get("ExitCode", -1) or -1)
                            execution["timed_out"] = True
                            execution["error"] = {
                                "type": "Timeout",
                                "message": "Program execution took too long and was stopped (possible infinite loop or heavy computation).",  # noqa: E501
                                "line": None,
                                "explanation": "The program did not finish within the allowed time limit.",  # noqa: E501
                                "suggestions": [
                                    "Check for infinite loops or very slow operations.",
                                    "Try running a smaller piece of the program or simplifying the logic.",  # noqa: E501
                                ],
                            }
                            break
                        time.sleep(0.1)

                    try:
                        stdout_bytes = container.logs(stdout=True, stderr=False)
                    except APIError:
                        stdout_bytes = b""
                    try:
                        stderr_bytes = container.logs(stdout=False, stderr=True)
                    except APIError:
                        stderr_bytes = b""

                    stdout_text = (
                        stdout_bytes.decode("utf-8", errors="replace")
                        if isinstance(stdout_bytes, bytes)
                        else str(stdout_bytes or "")
                    )
                    stderr_text = (
                        stderr_bytes.decode("utf-8", errors="replace")
                        if isinstance(stderr_bytes, bytes)
                        else str(stderr_bytes or "")
                    )

                    execution["stdout"] = stdout_text
                    execution["stderr"] = stderr_text
                    if execution["returncode"] == -1 and not timed_out:
                        execution["returncode"] = 0

                    return execution
                finally:
                    with contextlib.suppress(Exception):
                        container.remove(force=True)
            except ContainerError as exc:
                stdout_text = ""
                stderr_text = ""
                if getattr(exc, "stdout", None) is not None:
                    stdout_value = exc.stdout
                    stdout_text = (
                        stdout_value.decode("utf-8", errors="replace")
                        if isinstance(stdout_value, bytes)
                        else str(stdout_value)
                    )
                if getattr(exc, "stderr", None) is not None:
                    stderr_value = exc.stderr
                    stderr_text = (
                        stderr_value.decode("utf-8", errors="replace")
                        if isinstance(stderr_value, bytes)
                        else str(stderr_value)
                    )
                execution["stdout"] = stdout_text
                execution["stderr"] = stderr_text or stdout_text or str(exc)
                execution["returncode"] = int(getattr(exc, "exit_status", -1) or -1)
                execution["error"] = {
                    "type": "DockerContainerError",
                    "message": execution["stderr"] or "Docker container execution failed.",
                    "line": None,
                    "explanation": "The Docker container returned an execution error.",
                    "suggestions": [
                        "Review the container stderr for the first failing command.",
                        "Check that the requested Docker image is available and runnable.",
                    ],
                }
                return execution
            except (APIError, DockerException) as exc:
                return _sandbox_unavailable_execution(
                    str(exc),
                    "Sandbox startup failed.",
                )
    except (APIError, DockerException) as exc:
        execution["stderr"] = str(exc)
        execution["error"] = {
            "type": "DockerAPIError",
            "message": str(exc),
            "line": None,
            "explanation": "The Docker daemon or client returned an API error while starting the sandbox.",  # noqa: E501
            "suggestions": [
                "Verify that Docker is running on the host machine.",
                "Check whether the requested image can be pulled and started.",
            ],
        }
        run_in_sandbox.last_result = execution
        return execution


# Comprehensive list of modules that allow sandbox escape:
#   - os, sys, subprocess: process/system access
#   - socket, ssl, http, urllib3, ftplib, smtplib, telnetlib: network access
#   - shutil, pathlib, glob, fnmatch, tempfile: broad filesystem access
#   - ctypes, cffi, mmap, resource: native/memory access
#   - importlib, pkgutil, zipimport: dynamic import escape
#   - pty, signal, fcntl, termios: terminal/process control
#   - pickle, shelve, marshal: arbitrary code deserialisation
def _check_syntax(code: str) -> tuple[list[Issue], SyntaxError | None]:
    issues: list[Issue] = []
    syntax_exc: SyntaxError | None = None
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
            ),
        )
    return issues, syntax_exc


def _line_based_checks(code: str) -> list[Issue]:
    issues: list[Issue] = []
    lines = code.splitlines()

    for idx, line in enumerate(lines, start=1):
        if len(line) > 79:  # noqa: PLR2004
            issues.append(
                Issue(
                    line=idx,
                    severity="warning",
                    code="LONG_LINE",
                    message="Line exceeds 79 characters",
                ),
            )

        normalized = line.lower()
        if "todo" in normalized or "fixme" in normalized:
            issues.append(
                Issue(
                    line=idx,
                    severity="info",
                    code="TODO_COMMENT",
                    message="Line contains TODO/FIXME comment",
                ),
            )

        if line.rstrip() != line:
            issues.append(
                Issue(
                    line=idx,
                    severity="info",
                    code="TRAILING_WHITESPACE",
                    message="Line has trailing whitespace",
                ),
            )

        if line.startswith("\t"):
            issues.append(
                Issue(
                    line=idx,
                    severity="warning",
                    code="TABS_INDENT",
                    message="Line uses tabs for indentation instead of spaces",
                ),
            )

    return issues


def _detect_language_mismatch(code: str, selected_language: str) -> dict[str, str] | None:  # noqa: C901
    """Detect likely language mismatch using marker-score heuristics."""
    selected = (selected_language or "python").strip().lower()
    if selected == "js":
        selected = "javascript"
    if selected == "c++":
        selected = "cpp"

    non_empty_lines = [line for line in code.splitlines() if re.search(r"\S", line)]

    def rx(pattern: str) -> re.Pattern[str]:
        return re.compile(pattern, re.IGNORECASE)

    def semicolons_on_every_line(lines: list[str]) -> bool:
        if not lines:
            return False
        pattern = rx(r"^\s*[^#].*;\s*(?://.*)?$")
        return all(pattern.search(line) for line in lines)

    def mismatch(detected: str, confidence: str = "high") -> dict[str, str]:
        return {
            "detected": detected,
            "selected": selected,
            "confidence": confidence,
        }

    language_markers: dict[str, list[re.Pattern[str]]] = {
        "python": [
            rx(r"\bdef\s+[A-Za-z_][A-Za-z0-9_]*\s*\("),
            rx(r"\bprint\s*\("),
            rx(r"\bimport\s+numpy\b"),
            rx(r"\belif\b"),
        ],
        "javascript": [
            rx(r"\bconsole\.log\s*\("),
            rx(r"\bfunction\b"),
            rx(r"\b(?:var|let|const)\s+[A-Za-z_$][\w$]*"),
            rx(r"=>"),
        ],
        "java": [
            rx(r"\bpublic\s+class\b"),
            rx(r"\bSystem\.out\.println\s*\("),
            rx(r"\bimport\s+java\."),
        ],
        "c": [
            rx(r"#include\s*<stdio\.h>"),
            rx(r"#include\s*<stdlib\.h>"),
            rx(r"\bprintf\s*\("),
            rx(r"\bscanf\s*\("),
            rx(r"\bint\s+main\s*\(\s*(?:void|int\s+argc)?"),
        ],
        "cpp": [
            rx(r"\bcout\s*<<"),
            rx(r"\bcin\s*>>"),
            rx(r"\bstd::"),
            rx(r"\bnullptr\b"),
            rx(r"\btemplate\b"),
            rx(r"#include\s*<iostream>"),
            rx(r"#include\s*<string>"),
            rx(r"\busing\s+namespace\s+std\s*;"),
        ],
    }

    marker_count: dict[str, int] = {
        language: sum(1 for pattern in patterns if pattern.search(code))
        for language, patterns in language_markers.items()
    }

    if semicolons_on_every_line(non_empty_lines):
        marker_count["javascript"] += 1

    cpp_markers = marker_count["cpp"]
    c_markers = marker_count["c"]

    if selected in {"c", "cpp"} and cpp_markers == 0 and c_markers == 0:
        return None

    if cpp_markers > 0:
        detected = "cpp"
    elif c_markers > 0:
        detected = "c"
    else:
        non_c_family = {
            "python": marker_count["python"],
            "javascript": marker_count["javascript"],
            "java": marker_count["java"],
        }
        detected = max(non_c_family, key=non_c_family.get)

        if non_c_family[detected] == 0:
            if selected in {"c", "cpp"}:
                return None
            if selected == "java":
                return mismatch("unknown")
            return None

    if detected == selected:
        return None

    return mismatch(detected)


_ERROR_HELP: dict[str, dict[str, tuple[str, list[str]]]] = {
    "ZeroDivisionError": {
        "beginner": (
            "You attempted to divide by zero, which is not allowed in mathematics or Python.",
            [
                "Check the value of the denominator before dividing.",
                "Guard the division with an `if denominator != 0:` condition.",
            ],
        ),
        "intermediate": (
            "The code is attempting a division operation where the divisor equals zero.",
            [
                "Review the mathematical operation that's failing.",
                "Add a conditional check before division operations.",
            ],
        ),
        "advanced": ("Division by zero", []),
    },
    "NameError": {
        "beginner": (
            "Python tried to use a variable or name that has not been defined yet.",
            [
                "Make sure the variable is defined before you use it.",
                "Check for typos in the variable or function name.",
            ],
        ),
        "intermediate": (
            "A variable or function is being referenced that hasn't been defined in the current scope.",  # noqa: E501
            [
                "Ensure all names are defined before use.",
                "Check for scope issues.",
            ],
        ),
        "advanced": ("Undefined name reference", []),
    },
    "TypeError": {
        "beginner": (
            "An operation or function was applied to a value of an inappropriate type.",
            [
                "Check the types of the variables used on the failing line.",
                "Convert values to the expected type (for example, `int(...)` or `str(...)`).",
            ],
        ),
        "intermediate": (
            "An operation was performed on incompatible data types.",
            [
                "Review type compatibility for the operation being performed.",
                "Consider type conversion if needed.",
            ],
        ),
        "advanced": ("Type mismatch", []),
    },
    "IndexError": {
        "beginner": (
            "You tried to access a list (or similar container) at a position that does not exist.",
            [
                "Check the length of the list before indexing.",
                "Remember that valid indices go from 0 up to `len(list) - 1`.",
            ],
        ),
        "intermediate": (
            "An index is out of bounds for the container being accessed.",
            [
                "Verify the container's size before indexing.",
                "Check boundary conditions in loops.",
            ],
        ),
        "advanced": ("Index out of bounds", []),
    },
    "KeyError": {
        "beginner": (
            "You tried to access a dictionary key that does not exist.",
            [
                "Use `in` to check whether a key exists before accessing it.",
                "Use `dict.get(key, default)` if the key might be missing.",
            ],
        ),
        "intermediate": (
            "The code attempts to access a dictionary with a key that isn't present.",
            [
                "Check key existence before access.",
                "Use defensive dictionary access methods.",
            ],
        ),
        "advanced": ("Missing dictionary key", []),
    },
}


def _python_error_help(
    exc_type: str,
    message: str,
    difficulty: str = "beginner",
    line: int | None = None,
) -> dict[str, Any]:
    exc_type = exc_type or ""
    entry = _ERROR_HELP.get(exc_type, {}).get(difficulty)
    if entry is not None:
        explanation, suggestions = entry
    else:
        explanation = "Your program raised a runtime error."
        suggestions = [
            "Read the error message carefully and check the referenced line number.",
            "Print intermediate values to understand what the program is doing before it crashes.",
        ]
    if line and difficulty == "beginner":
        explanation += f" Review line {line}."
    return {
        "type": exc_type,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }


def _parse_python_traceback(stderr: str, difficulty: str = "beginner") -> dict[str, Any]:
    """
    Extract error type, message and line number from a Python traceback.
    """
    if not stderr:
        return {
            "type": None,
            "message": "",
            "line": None,
            "explanation": "",
            "suggestions": [],
        }

    lines = stderr.strip().splitlines()
    exc_type = None
    exc_message = ""
    line_number: int | None = None

    # Try to find "File ..., line N" (the last one is usually the crashing line)
    file_line_pattern = re.compile(r'File ".*", line (\d+)')
    for line in lines:
        match = file_line_pattern.search(line)
        if match:
            with contextlib.suppress(ValueError):
                line_number = int(match.group(1))

    # The last non-empty line typically looks like "ErrorType: message"
    for candidate in reversed(lines):
        if ":" in candidate:
            parts = candidate.split(":", 1)
            exc_type = parts[0].strip()
            exc_message = parts[1].strip()
            break

    help_data = _python_error_help(
        str(exc_type) if exc_type else "",
        exc_message,
        difficulty=difficulty,
        line=line_number,
    )
    help_data["line"] = line_number
    return help_data


def _run_python(code: str, _timeout: float = 3.0, difficulty: str = "beginner") -> dict[str, Any]:
    execution = _empty_execution()

    execution = run_in_sandbox(
        code,
        "python",
        _sandbox_image("python", "python:3.11-slim"),
        ["python", "{source}"],
        timeout=10,
    )

    if execution["returncode"] != 0 and not execution["error"] and execution["stderr"]:
        execution["error"] = _parse_python_traceback(execution["stderr"], difficulty=difficulty)

    return execution


def _javascript_error_help(  # noqa: C901, PLR0912
    error_name: str,
    message: str,
    difficulty: str = "beginner",
    line: int | None = None,
) -> dict[str, Any]:
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
    suggestions: list[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Use console.log to inspect values before the program crashes.",
    ]

    if error_name == "ReferenceError":
        if difficulty == "beginner":
            explanation = (
                "JavaScript tried to use a variable that does not exist in the current scope."
            )
            if line:
                explanation += f" Look at line {line}."
            suggestions = [
                "Make sure the variable is declared before it is used.",
                "Check for typos in the variable or function name.",
            ]
        elif difficulty == "intermediate":
            explanation = "A variable or function is being referenced that hasn't been defined in the current scope."  # noqa: E501
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
            explanation = (
                "There is a mistake in the JavaScript syntax, so the engine cannot parse the code."
            )
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


def _parse_node_error(stderr: str, difficulty: str = "beginner") -> dict[str, Any]:
    """
    Extract error type, message and (best-effort) line number from a Node.js error.
    """
    if not stderr:
        return {
            "type": None,
            "message": "",
            "line": None,
            "explanation": "",
            "suggestions": [],
        }

    lines = stderr.strip().splitlines()

    # First line of the stack usually looks like "ErrorName: message"
    first = lines[0]
    error_name = None
    message = ""
    if ":" in first:
        parts = first.split(":", 1)
        error_name = parts[0].strip()
        message = parts[1].strip()

    line_number: int | None = None
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

    help_data = _javascript_error_help(
        str(error_name) if error_name else "",
        message,
        difficulty=difficulty,
        line=line_number,
    )
    help_data["line"] = line_number
    return help_data


def _run_node(code: str, _timeout: float = 3.0, difficulty: str = "beginner") -> dict[str, Any]:
    execution = _empty_execution()

    execution = run_in_sandbox(
        code,
        "javascript",
        _sandbox_image("javascript", "node:18-slim"),
        ["node", "{source}"],
        timeout=10,
    )

    if execution["returncode"] != 0 and not execution["error"] and execution["stderr"]:
        execution["error"] = _parse_node_error(execution["stderr"], difficulty=difficulty)

    return execution


def _analyze_python(code: str, difficulty: str = "beginner") -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = []
    syntax_issues, syntax_exc = _check_syntax(code)
    issues.extend(syntax_issues)
    issues.extend(_line_based_checks(code))

    execution = _empty_execution()
    if syntax_exc is None:
        execution = _run_python(code, difficulty=difficulty)
    else:
        # Mirror the syntax error into the execution block so the UI can show it
        execution["error"] = _python_error_help(
            "SyntaxError",
            str(syntax_exc),
            difficulty=difficulty,
            line=syntax_exc.lineno or 1,
        )
        execution["error"]["line"] = syntax_exc.lineno or 1
        execution["stderr"] = str(syntax_exc)
        execution["returncode"] = 1

    return issues, execution


def _analyze_javascript(
    code: str,
    difficulty: str = "beginner",
) -> tuple[list[Issue], dict[str, Any]]:
    # Reuse generic line-based checks for JavaScript as well
    issues = _line_based_checks(code)
    execution = _run_node(code, difficulty=difficulty)
    return issues, execution


def _parse_gcc_output(output: str, language_label: str) -> list[Issue]:
    """
    Parse GCC / G++ style diagnostics into Issue objects.
    Example line: main.c:10:5: error: expected ';' before 'return'
    """
    issues: list[Issue] = []
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


def _parse_java_compile_output(output: str) -> list[Issue]:
    """
    Parse javac diagnostics like:
      Main.java:10: error: ';' expected
    """
    issues: list[Issue] = []
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


def _parse_java_runtime_error(stderr: str) -> dict[str, Any]:
    """
    Best-effort extraction of Java runtime exception information.
    """
    if not stderr:
        return {
            "type": None,
            "message": "",
            "line": None,
            "explanation": "",
            "suggestions": [],
        }

    lines = stderr.strip().splitlines()
    exc_type: str | None = None
    message = ""
    line_number: int | None = None

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
    suggestions: list[str] = [
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


def _run_gcc(
    source_code: str,
    language_label: str,
    compiler: str,
    _source_name: str,
    _timeout: float = 3.0,
) -> tuple[list[Issue], dict[str, Any]]:
    compile_issues: list[Issue] = []
    execution = run_in_sandbox(
        source_code,
        language_label,
        _sandbox_image("gcc", "gcc:12"),
        ["sh", "-c", f"{compiler} {{source}} -o {{output}} && {{output}}"],
        timeout=10,
    )

    if execution["returncode"] != 0 and not execution["error"] and execution.get("stderr"):
            parsed = _parse_gcc_output(execution["stderr"], language_label)
            if parsed:
                compile_issues.extend(parsed)
                execution["error"] = {
                    "type": "CompileError",
                    "message": "Compilation failed. See errors below.",
                    "line": None,
                    "explanation": f"The {language_label.upper()} compiler reported one or more errors.",  # noqa: E501
                    "suggestions": [
                        "Read each compiler error from top to bottom; often the first message is the most important.",  # noqa: E501
                        "Fix the earliest error, then recompile to see if later errors disappear.",
                    ],
                }
            elif not execution.get("error"):
                execution["error"] = {
                    "type": "RuntimeError",
                    "message": "The program exited with a non-zero status code.",
                    "line": None,
                    "explanation": (
                        "A non-zero exit code usually means the program hit a runtime error such"
                        " as division by zero, invalid memory access, or an explicit `return 1`."
                    ),
                    "suggestions": [
                        "Add print statements before the suspected failing line to see which values are being used.",  # noqa: E501
                        "Check for invalid array indices, null pointers, or divisions where the denominator may be zero.",  # noqa: E501
                    ],
                }

    return compile_issues, execution


def _analyze_c(code: str) -> tuple[list[Issue], dict[str, Any]]:
    style_issues = _line_based_checks(code)
    compile_issues, execution = _run_gcc(code, "c", "gcc", "main.c")
    issues = style_issues + compile_issues
    return issues, execution


def _analyze_cpp(code: str) -> tuple[list[Issue], dict[str, Any]]:
    style_issues = _line_based_checks(code)
    compile_issues, execution = _run_gcc(code, "cpp", "g++", "main.cpp")
    issues = style_issues + compile_issues
    return issues, execution


def _analyze_java(code: str, _timeout: float = 3.0) -> tuple[list[Issue], dict[str, Any]]:
    style_issues = _line_based_checks(code)
    compile_issues: list[Issue] = []

    match = re.search(r"public\s+(?:final\s+)?class\s+(\w+)", code)
    _class_name = match.group(1) if match else "Main"

    execution = run_in_sandbox(
        code,
        "java",
        _sandbox_image("java", "openjdk:17-slim"),
        ["sh", "-c", "javac -d {classes} {source} && java -cp {classes} {main_class}"],
        timeout=10,
    )

    if execution["returncode"] != 0:
        stderr = execution.get("stderr", "")
        if not execution["error"] and stderr:
            parsed = _parse_java_compile_output(stderr)
            if parsed:
                compile_issues.extend(parsed)
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
            elif not execution.get("error"):
                execution["error"] = _parse_java_runtime_error(stderr)

    issues = style_issues + compile_issues
    return issues, execution


def _analyze_language_not_yet_supported(
    language: str,
) -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = [
        Issue(
            line=1,
            severity="info",
            code="LANGUAGE_UNSUPPORTED",
            message=(
                f"Language '{language}' is not yet fully supported for compilation/execution "
                "in this demo. Static checks may be limited."
            ),
        ),
    ]
    execution = _empty_execution()
    execution["error"] = {
        "type": "LanguageUnsupported",
        "message": f"Execution for language '{language}' is not configured on this server.",
        "line": None,
        "explanation": "Only Python and JavaScript are currently executed. Other languages are reported statically.",  # noqa: E501
        "suggestions": [
            "Switch to Python or JavaScript to see full compiler-style execution and explanations.",
            "Extend the backend analyzer to integrate the compiler or runtime for this language.",
        ],
    }
    return issues, execution


def _get_valid_gemini_api_key() -> str | None:
    """Read and validate GEMINI_API_KEY from environment."""
    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()

    # Guard against accidentally quoted values from environment providers.
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1].strip()

    if not api_key or api_key == "YOUR_API_KEY_HERE":
        return None

    return api_key


def _extract_gemini_text(response_json: dict[str, Any]) -> str | None:
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
            if (
                isinstance(part, dict)
                and isinstance(part.get("text"), str)
                and part["text"].strip()
            ):
                return part["text"].strip()
    return None


def _map_gemini_http_error(status_code: int, body_text: str, error_message: str) -> str:
    """Map Gemini API failures to stable app-level status codes."""
    haystack = f"{error_message}\n{body_text}".lower()

    if status_code == 403 and (  # noqa: PLR2004
        "api has not been used" in haystack
        or "service disabled" in haystack
        or "is disabled" in haystack
    ):
        return "AI_MENTOR_API_DISABLED"

    if status_code == 429 or "quota" in haystack or "rate limit" in haystack:  # noqa: PLR2004
        return "AI_MENTOR_QUOTA_EXCEEDED"

    return "AI_MENTOR_API_ERROR"


def _ai_mentor_status_from_feedback(feedback: str) -> str:
    """Map legacy feedback sentinels to a small stable API status."""
    if feedback == "AI_MENTOR_DISABLED":
        return "disabled"
    if feedback == "AI_MENTOR_QUOTA_EXCEEDED":
        return "quota_exceeded"
    if feedback == "AI_MENTOR_BAD_RESPONSE":
        return "bad_response"
    if feedback == "AI_MENTOR_API_ERROR":
        return "api_error"
    return "ok"


MAX_GLOBAL_AI_CALLS_PER_DAY = int(os.environ.get("MAX_GLOBAL_AI_CALLS_PER_DAY", "5000"))

_AI_QUOTA_REDIS_PREFIX = "ai_quota:"


def _ai_quota_redis_key() -> str:
    return f"{_AI_QUOTA_REDIS_PREFIX}{time.strftime('%Y-%m-%d')}"


def _check_ai_quota() -> bool:
    """Return True if the global daily AI quota has been reached."""
    client = None
    try:
        from app_pkg.extensions import get_redis_client  # noqa: PLC0415
        client = get_redis_client()
    except ImportError:
        client = None

    if client is not None:
        key = _ai_quota_redis_key()
        value = client.get(key)
        return value is not None and int(value) >= MAX_GLOBAL_AI_CALLS_PER_DAY

    return SECURITY_METRICS.get("ai_mentor_calls_made", 0) >= MAX_GLOBAL_AI_CALLS_PER_DAY


def _increment_ai_quota() -> None:
    """Increment the daily AI call counter. Uses Redis when available."""
    client = None
    try:
        from app_pkg.extensions import get_redis_client  # noqa: PLC0415
        client = get_redis_client()
    except ImportError:
        client = None

    if client is not None:
        key = _ai_quota_redis_key()
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        pipe.execute()
    else:
        SECURITY_METRICS["ai_mentor_calls_made"] = (
            SECURITY_METRICS.get("ai_mentor_calls_made", 0) + 1
        )


_AI_MENTOR_CACHE: OrderedDict = OrderedDict()
_AI_MENTOR_CACHE_SIZE = 500

_logger = logging.getLogger("app_pkg")


MAX_AI_CODE_CHARS = 10000

_MENTOR_PROMPTS: dict[str, str] = {
    "beginner": (
        "You are a strict coding instructor helping a beginner."
        " A student submitted code that has errors.\n"
        "RULES YOU MUST FOLLOW:\n"
        "- For EVERY issue you mention, you MUST reference the exact line number.\n"
        "- Use simple, plain language that a beginner can understand.\n"
        "- Explain what is wrong in simple terms.\n"
        "- Give a HINT toward the exact line or concept that needs fixing.\n"
        "- Do NOT give the corrected code.\n"
        "- Be VERY BRIEF — max 3 sentences per error.\n"
        "- Focus ONLY on errors that prevent the code from running."
        " Do NOT comment on style issues (line length, indentation, trailing whitespace, TODO comments).\n\n"  # noqa: E501
        "Detected issues:\n{error_context}\n\n"
        "Student code ({language}) with line numbers:\n"
        "```\n{numbered_lines}\n```"
    ),
    "intermediate": (
        "You are a coding instructor helping an intermediate student."
        " A student submitted code that has errors.\n"
        "RULES YOU MUST FOLLOW:\n"
        "- Explain the CONCEPT or PRINCIPLE behind each error, not the specific line details.\n"
        "- Do NOT reference line numbers directly.\n"
        "- Help the student understand the underlying concept that needs to be applied.\n"
        "- Give a hint that guides without referencing specific lines.\n"
        "- Do NOT give the corrected code.\n"
        "- Be BRIEF and focused on conceptual understanding.\n"
        "- Focus ONLY on errors that prevent the code from running."
        " Do NOT comment on style issues (line length, indentation, trailing whitespace, TODO comments).\n\n"  # noqa: E501
        "Detected issues:\n{error_context}\n\n"
        "Student code ({language}) with line numbers:\n"
        "```\n{numbered_lines}\n```"
    ),
    "advanced": (
        "You are a coding mentor for an advanced student."
        " A student submitted code that has errors.\n"
        "RULES YOU MUST FOLLOW:\n"
        "- Identify ONLY the core concepts or principles that are wrong.\n"
        "- Do NOT provide line references, code quotes, or detailed explanations.\n"
        "- Be VERY TERSE — list only the concept names or brief concept descriptions.\n"
        "- Do NOT explain or give hints.\n"
        "- Do NOT reference specific code.\n"
        "- Focus ONLY on errors that prevent the code from running."
        " Do NOT comment on style issues (line length, indentation, trailing whitespace, TODO comments).\n\n"  # noqa: E501
        "Detected issues:\n{error_context}\n\n"
        "Student code ({language}) with line numbers:\n"
        "```\n{numbered_lines}\n```"
    ),
}


def _build_mentor_prompt(code: str, language: str, difficulty: str, error_context: str) -> str:
    safe = code[:MAX_AI_CODE_CHARS]
    if len(code) > MAX_AI_CODE_CHARS:
        safe += "\n... [TRUNCATED DUE TO LENGTH BUDGET]"
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(safe.splitlines(), start=1))
    tmpl = _MENTOR_PROMPTS.get(difficulty, _MENTOR_PROMPTS["advanced"])
    return tmpl.format(error_context=error_context, numbered_lines=numbered, language=language)


_STYLE_ISSUE_CODES: set[str] = {
    "LONG_LINE",
    "TODO_COMMENT",
    "TRAILING_WHITESPACE",
    "TABS_INDENT",
}


def _build_error_context(execution: dict, issues: list[dict]) -> tuple[str, list[dict]]:
    ctx = ""
    all_errors: list[dict] = []

    for iss in issues:
        if iss.get("severity") == "error" and iss.get("code") not in _STYLE_ISSUE_CODES:
            all_errors.append(
                {
                    "line": iss.get("line"),
                    "type": iss.get("code", "ERROR"),
                    "message": iss.get("message"),
                    "severity": "error",
                }
            )
            ctx += f"Line {iss.get('line')}: {iss.get('message')}\n"

    if execution.get("error"):
        ee = execution["error"]
        ln = ee.get("line", "?")
        all_errors.append(
            {
                "line": ln,
                "type": ee.get("type", "RuntimeError"),
                "message": ee.get("message", ""),
                "explanation": ee.get("explanation", ""),
                "severity": "error",
            }
        )
        ctx += f"Line {ln}: {ee.get('type')} - {ee.get('message')}\n"

    if not all_errors:
        for warn in issues:
            if warn.get("severity") == "warning" and warn.get("code") not in _STYLE_ISSUE_CODES:
                ctx += f"Line {warn.get('line')}: {warn.get('message')}\n"

    return ctx, all_errors


async def _get_ai_mentorship(  # noqa: C901, PLR0911, PLR0912, PLR0915
    code: str,
    language: str,
    execution: dict,
    issues: list[dict],
    difficulty: str = "beginner",
) -> str:
    if _check_ai_quota():
        return "AI_MENTOR_QUOTA_EXCEEDED"

    api_key = _get_valid_gemini_api_key()
    if not api_key:
        return "AI_MENTOR_DISABLED"

    try:
        error_context, all_errors = _build_error_context(execution, issues)

        if all_errors or error_context:
            cache_key_str = f"{code[:MAX_AI_CODE_CHARS]}:{language}:{difficulty}:{error_context}"
            cache_key = hashlib.sha256(cache_key_str.encode("utf-8")).hexdigest()
            if cache_key in _AI_MENTOR_CACHE:
                res = _AI_MENTOR_CACHE.pop(cache_key)
                _AI_MENTOR_CACHE[cache_key] = res
                return res

            prompt = _build_mentor_prompt(code, language, difficulty, error_context)

            gemini_model = (os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash").strip()
            endpoint = (
                "https://generativelanguage.googleapis.com/v1beta/"
                f"models/{urllib.parse.quote_plus(gemini_model)}:generateContent"
            )
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt,
                            },
                        ],
                    },
                ],
            }

            _increment_ai_quota()

            _max_retries = 3
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
                for _attempt in range(_max_retries):
                    try:
                        response = await client.post(
                            endpoint, json=payload, headers={"X-Goog-Api-Key": api_key},
                        )
                        status_code = response.status_code
                        raw_body = response.text
                        if status_code == 429 and _attempt < _max_retries - 1:  # noqa: PLR2004
                            backoff = 2**_attempt
                            _logger.warning(
                                "Gemini rate limited (429). Retrying in %ds...", backoff
                            )
                            await asyncio.sleep(backoff)
                            continue
                        break
                    except httpx.RequestError:
                        _logger.exception("Gemini network error")
                        return "AI_MENTOR_API_ERROR"

            if status_code < 200 or status_code >= 300:  # noqa: PLR2004
                _logger.error("Gemini unexpected status: %s", status_code)
                return _map_gemini_http_error(status_code, raw_body, "")

            try:
                parsed = json.loads(raw_body)
            except json.JSONDecodeError:
                preview = raw_body[:180].replace("\n", " ")
                _logger.exception("Gemini JSON decode failed. body_preview=%s", preview)
                return "AI_MENTOR_BAD_RESPONSE"

            feedback_text = _extract_gemini_text(parsed)

            # Usage tracking (Quota Management)
            try:
                usage = parsed.get("usageMetadata", {})
                if usage:
                    total_tokens = int(usage.get("totalTokenCount", 0))
                    SECURITY_METRICS["ai_mentor_tokens_used"] = (
                        SECURITY_METRICS.get("ai_mentor_tokens_used", 0) + total_tokens
                    )
                    _logger.info(
                        "gemini_api_usage",
                        extra={
                            "prompt_tokens": usage.get("promptTokenCount", 0),
                            "candidates_tokens": usage.get("candidatesTokenCount", 0),
                            "total_tokens": total_tokens,
                        },
                    )
            except (KeyError, TypeError, AttributeError) as e:
                _logger.warning("Failed to parse usageMetadata", exc_info=e)

            if feedback_text:
                # Store in LRU cache
                _AI_MENTOR_CACHE[cache_key] = feedback_text
                if len(_AI_MENTOR_CACHE) > _AI_MENTOR_CACHE_SIZE:
                    _AI_MENTOR_CACHE.popitem(last=False)
                return feedback_text

            return "AI_MENTOR_BAD_RESPONSE"
    except Exception as exc:
        _logger.exception(
            "Unexpected Gemini error type=%s", type(exc).__name__
        )
        return "AI_MENTOR_API_ERROR"
    return "LOOKS_GOOD"


async def analyze_code(  # noqa: C901
    code: str,
    language: str = "python",
    difficulty: str = "beginner",
) -> dict[str, Any]:
    """
    Analyze source code and return a structured result.
    Runs subprocess execute functions in an isolated thread.

    Args:
        code: The source code to analyze
        language: Programming language (python, javascript, java, c, cpp)
        difficulty: "beginner", "intermediate", or "advanced"
    """
    if not isinstance(code, str):
        msg = "code must be a string"
        raise TypeError(msg)

    language = (language or "python").lower()
    if language == "js":
        language = "javascript"
    if language == "c++":
        language = "cpp"

    mismatch = _detect_language_mismatch(code, language)
    if mismatch:
        detected = mismatch["detected"]
        selected = mismatch["selected"]
        return {
            "ok": False,
            "language": selected,
            "mismatch": True,
            "detected_language": detected,
            "output": "",
            "error": {
                "type": "LanguageMismatch",
                "message": f"You selected {selected} but your code looks like {detected}.",
                "line": 1,
                "explanation": "The code you wrote does not match the selected language.",
                "suggestions": [
                    f"Switch the language dropdown to {detected}",
                    f"Or rewrite your code in {selected}.",
                ],
            },
            "ai_mentor_feedback": (
                "Language mismatch detected. "
                f"You selected {selected} but your code appears to be written in {detected}. "
                "Please switch the language dropdown or rewrite your code in the correct language."
            ),
            "ai_mentor_status": "ok",
            "issues": [],
            "execution": _empty_execution(),
        }

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

    # Ensure `execution` is always a dict before calling AI mentorship
    if execution is None:
        execution = _empty_execution()

    ai_mentor_feedback = await _get_ai_mentorship(
        code,
        language,
        execution,
        issues_dicts,
        difficulty=difficulty,
    )
    ai_mentor_status = _ai_mentor_status_from_feedback(ai_mentor_feedback)

    result: dict[str, Any] = {
        "ok": True,
        "language": language,
        "summary": {
            "line_count": len(lines),
            "issue_count": len(issues_dicts),
        },
        "issues": issues_dicts,
        "execution": execution,
        "ai_mentor_feedback": ai_mentor_feedback,
        "ai_mentor_status": ai_mentor_status,
    }
    # Ensure 'execution' key always exists and is a dict (not None)
    if result.get("execution") is None:
        result["execution"] = _empty_execution()

    # Return a plain dict (no wrapper) to avoid surprises for callers
    return dict(result)
