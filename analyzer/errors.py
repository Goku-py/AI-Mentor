from __future__ import annotations

import contextlib
import re
from typing import Any

_ERROR_HELP: dict[str, tuple[str, list[str]]] = {
    "ZeroDivisionError": (
        "You attempted to divide by zero, which is not allowed in mathematics or Python.",
        [
            "Check the value of the denominator before dividing.",
            "Guard the division with an `if denominator != 0:` condition.",
        ],
    ),
    "NameError": (
        "Python tried to use a variable or name that has not been defined yet.",
        [
            "Make sure the variable is defined before you use it.",
            "Check for typos in the variable or function name.",
        ],
    ),
    "TypeError": (
        "An operation or function was applied to a value of an inappropriate type.",
        [
            "Check the types of the variables used on the failing line.",
            "Convert values to the expected type (for example, `int(...)` or `str(...)`).",
        ],
    ),
    "IndexError": (
        "You tried to access a list (or similar container) at a position that does not exist.",
        [
            "Check the length of the list before indexing.",
            "Remember that valid indices go from 0 up to `len(list) - 1`.",
        ],
    ),
    "KeyError": (
        "You tried to access a dictionary key that does not exist.",
        [
            "Use `in` to check whether a key exists before accessing it.",
            "Use `dict.get(key, default)` if the key might be missing.",
        ],
    ),
}

def _python_error_help(
    exc_type: str,
    message: str,
    line: int | None = None,
) -> dict[str, Any]:
    exc_type = exc_type or ""
    entry = _ERROR_HELP.get(exc_type)
    if entry is not None:
        explanation, suggestions = entry
    else:
        explanation = "Your program raised a runtime error."
        suggestions = [
            "Read the error message carefully and check the referenced line number.",
            "Print intermediate values to understand what the program is doing before it crashes.",
        ]
    if line:
        explanation += f" Review line {line}."
    return {
        "type": exc_type,
        "message": message,
        "explanation": explanation,
        "suggestions": suggestions,
    }

def _parse_python_traceback(stderr: str) -> dict[str, Any]:
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

    file_line_pattern = re.compile(r'File ".*", line (\d+)')
    for line in lines:
        match = file_line_pattern.search(line)
        if match:
            with contextlib.suppress(ValueError):
                line_number = int(match.group(1))

    for candidate in reversed(lines):
        if ":" in candidate:
            parts = candidate.split(":", 1)
            exc_type = parts[0].strip()
            exc_message = parts[1].strip()
            break

    help_data = _python_error_help(
        str(exc_type) if exc_type else "",
        exc_message,
        line=line_number,
    )
    help_data["line"] = line_number
    return help_data

def _javascript_error_help(
    error_name: str,
    message: str,
    line: int | None = None,
) -> dict[str, Any]:
    error_name = error_name or ""

    explanation = "Your JavaScript program raised a runtime error."
    suggestions: list[str] = [
        "Read the error message carefully and check the referenced line number.",
        "Use console.log to inspect values before the program crashes.",
    ]

    if error_name == "ReferenceError":
        explanation = "JavaScript tried to use a variable that does not exist in the current scope."
        if line:
            explanation += f" Look at line {line}."
        suggestions = [
            "Make sure the variable is declared before it is used.",
            "Check for typos in the variable or function name.",
        ]
    elif error_name == "TypeError":
        explanation = "An operation was performed on a value of an unexpected type."
        if line:
            explanation += f" Check line {line}."
        suggestions = [
            "Check that objects and functions are what you expect before using them.",
            "Guard property access with checks like `if (obj && obj.prop) { ... }`.",
        ]
    elif error_name == "SyntaxError":
        explanation = (
            "There is a mistake in the JavaScript syntax, so the engine cannot parse the code."
        )
        if line:
            explanation += f" Review line {line}."
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

def _parse_node_error(stderr: str) -> dict[str, Any]:
    if not stderr or not stderr.strip():
        return {
            "type": None,
            "message": "",
            "line": None,
            "explanation": "",
            "suggestions": [],
        }

    lines = stderr.strip().splitlines()

    first = lines[0]
    error_name = None
    message = ""
    if ":" in first:
        parts = first.split(":", 1)
        error_name = parts[0].strip()
        message = parts[1].strip()

    line_number: int | None = None
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
        line=line_number,
    )
    help_data["line"] = line_number
    return help_data
