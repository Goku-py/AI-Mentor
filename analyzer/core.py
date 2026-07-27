from __future__ import annotations

import ast
import asyncio
import contextlib
import logging
import os
import re
import signal
import subprocess  # nosec B404
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any

import requests.exceptions
from flask import current_app

from analyzer import errors as _errors
from analyzer import mentorship as _mentorship

_logger = logging.getLogger(__name__)


def _raise_deadline_exceeded():
    raise requests.exceptions.ReadTimeout


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


def _limit_resources_linux() -> None:
    if not sys.platform.startswith("linux"):
        return
    import os as _os
    import resource

    _os.nice(19)
    _os.setpgrp()
    memory_limit = 256 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_NPROC, (256, 256))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))


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
    """True when HOST_EXECUTION_ENABLED=1 env var is set.

    Runs code natively (no Docker) — acceptable for authenticated users
    in an educational tool when Docker is unavailable.  See
    _run_host_sandboxed for the env, resource, and fd hardening applied.

    Host execution does NOT provide network isolation — the child can
    open sockets despite the cleared proxy vars (defense-in-depth only).
    Accepted risk: authenticated users, Railway egress restrictions limit
    blast radius.
    """
    return os.environ.get("HOST_EXECUTION_ENABLED", "").strip() == "1"


def _run_host_sandboxed(
    host_cmd: list[str],
    timeout: int,
    cwd: str | None = None,
) -> dict[str, Any]:
    """Run code natively with resource limits and env isolation.

    Fallback when Docker is unavailable.  The child process gets:
    * A minimal environment (no secrets from the parent)
    * Resource limits (AS=256MB, CPU=3s, FSIZE=10MB, NPROC=256)
    * No inherited file descriptors
    * Process-group isolation for reliable cleanup on timeout

    .. warning::
       Does NOT provide network isolation.  The child can open sockets
       despite the cleared proxy vars (defense-in-depth only).
       Accepted risk: authenticated users, Railway egress restrictions.
    """
    _logger.warning(
        "Host execution fallback — code runs natively without container isolation."
    )

    execution = _empty_execution()
    execution["returncode"] = -1

    preexec = None
    if sys.platform.startswith("linux"):
        preexec = _limit_resources_linux

    # Minimal environment — no secrets from parent process.
    host_env: dict[str, str] = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", "/tmp"),  # noqa: S108
        "TMPDIR": cwd or "/tmp",  # noqa: S108
        "LC_ALL": "C.UTF-8",
        # Best-effort network disabling (defense-in-depth, not a guarantee).
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

    try:
        proc = subprocess.Popen(  # noqa: S603
            host_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=host_env,
            preexec_fn=preexec,  # noqa: PLW1509
            cwd=cwd,
            close_fds=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Kill the entire process group (created by setpgrp in preexec_fn).
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGKILL)
            stdout, stderr = proc.communicate()
            execution["timed_out"] = True
            execution["returncode"] = -1
            execution["stdout"] = stdout or ""
            execution["stderr"] = stderr or ""
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
            return execution

        execution["stdout"] = stdout or ""
        execution["stderr"] = stderr or ""
        execution["returncode"] = proc.returncode
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
    output = os.path.join(tmp_dir, "program")
    classes = os.path.join(tmp_dir, "classes")
    return [
        part.format(source=source_path, output=output, classes=classes, main_class=main_class)
        for part in cmd
    ]


def run_in_sandbox(
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
            source_path = os.path.join(tmp_dir, source_name)
            with open(source_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                f.write(code)
            # Classes dir used by Java compilation (javac -d).
            os.makedirs(os.path.join(tmp_dir, "classes"), exist_ok=True)  # noqa: PTH103

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
                    try:
                        deadline = time.monotonic() + timeout_seconds
                        result = container.wait(timeout=timeout_seconds)
                        if time.monotonic() > deadline:
                            _raise_deadline_exceeded()
                        execution["returncode"] = result.get("StatusCode", 0) or 0
                    except (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
                        with contextlib.suppress(APIError):
                            container.kill()
                        execution["timed_out"] = True
                        execution["returncode"] = -1
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
                    except Exception:  # noqa: BLE001
                        with contextlib.suppress(APIError):
                            container.kill()
                        execution["error"] = {
                            "type": "DockerError",
                            "message": "Container execution failed unexpectedly.",
                            "line": None,
                            "explanation": "The Docker container encountered an error during execution.",  # noqa: E501
                            "suggestions": [
                                "Try running the code again.",
                            ],
                        }

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
        if len(line) > 79:
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


def _detect_language_mismatch(code: str, selected_language: str) -> dict[str, str] | None:
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


def _run_python(code: str, _timeout: float = 3.0) -> dict[str, Any]:
    execution = _empty_execution()

    execution = run_in_sandbox(
        code,
        "python",
        _sandbox_image("python", "python:3.11-slim"),
        ["python", "{source}"],
        timeout=10,
    )

    if execution["returncode"] != 0 and not execution["error"] and execution["stderr"]:
        execution["error"] = _errors._parse_python_traceback(execution["stderr"])

    return execution


def _run_node(code: str, _timeout: float = 3.0) -> dict[str, Any]:
    execution = _empty_execution()

    execution = run_in_sandbox(
        code,
        "javascript",
        _sandbox_image("javascript", "node:18-slim"),
        ["node", "{source}"],
        timeout=10,
    )

    if execution["returncode"] != 0 and not execution["error"] and execution["stderr"]:
        execution["error"] = _errors._parse_node_error(execution["stderr"])

    return execution


def _analyze_python(code: str) -> tuple[list[Issue], dict[str, Any]]:
    issues: list[Issue] = []
    syntax_issues, syntax_exc = _check_syntax(code)
    issues.extend(syntax_issues)
    issues.extend(_line_based_checks(code))

    execution = _empty_execution()
    if syntax_exc is None:
        execution = _run_python(code)
    else:
        # Mirror the syntax error into the execution block so the UI can show it
        execution["error"] = _errors._python_error_help(
            "SyntaxError",
            str(syntax_exc),
            line=syntax_exc.lineno or 1,
        )
        execution["error"]["line"] = syntax_exc.lineno or 1
        execution["stderr"] = str(syntax_exc)
        execution["returncode"] = 1

    return issues, execution


def _analyze_javascript(
    code: str,
) -> tuple[list[Issue], dict[str, Any]]:
    # Reuse generic line-based checks for JavaScript as well
    issues = _line_based_checks(code)
    execution = _run_node(code)
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
        "explanation": (
            "Only Python and JavaScript are currently executed. "
            "Other languages are reported statically."
        ),
        "suggestions": [
            "Switch to Python or JavaScript to see full compiler-style execution and explanations.",
            "Extend the backend analyzer to integrate the compiler or runtime for this language.",
        ],
    }
    return issues, execution


async def analyze_code(
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
        issues, execution = await asyncio.to_thread(_analyze_python, code)
    elif language in {"javascript", "js"}:
        language = "javascript"
        issues, execution = await asyncio.to_thread(_analyze_javascript, code)
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

    ai_mentor_feedback = await _mentorship._get_ai_mentorship(
        code,
        language,
        execution,
        issues_dicts,
        difficulty,
    )
    ai_mentor_status = _mentorship._ai_mentor_status_from_feedback(ai_mentor_feedback)

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
    if result.get("execution") is None:
        result["execution"] = _empty_execution()

    return dict(result)
