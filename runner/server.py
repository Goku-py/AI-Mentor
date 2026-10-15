"""HTTP front end for the sandbox execution runner.

Exposes exactly two endpoints:
  GET  /healthz  - liveness plus whether the Docker daemon is usable
  POST /execute  - run one snippet and return the standard execution dict

Binds to a private interface; every /execute call must present the shared secret.
"""

from __future__ import annotations

import logging
import os
import secrets

from flask import Flask, jsonify, request

from analyzer.core import run_in_sandbox_local, sandbox_runtime_status

logger = logging.getLogger("runner")

MAX_CODE_CHARS = 102_400
MAX_TIMEOUT_SECONDS = 30


def _secret() -> str:
    return os.environ.get("EXECUTION_RUNNER_SECRET") or ""


def create_runner_app() -> Flask:
    app = Flask(__name__)

    if not _secret():
        # Refuse to start rather than serving an unauthenticated code-execution
        # endpoint to whatever can reach the port.
        raise RuntimeError("EXECUTION_RUNNER_SECRET must be set")  # noqa: TRY003

    @app.get("/healthz")
    def healthz() -> tuple:
        return jsonify(sandbox_runtime_status()), 200

    @app.post("/execute")
    def execute() -> tuple:  # noqa: PLR0911 - each branch is a distinct validation failure
        provided = request.headers.get("Authorization", "")
        expected = f"Bearer {_secret()}"
        if not secrets.compare_digest(provided, expected):
            return jsonify({"error": "unauthorized"}), 401

        body = request.get_json(silent=True) or {}
        code = body.get("code")
        language = body.get("language")
        image = body.get("image")
        cmd = body.get("cmd")
        timeout = body.get("timeout", 10)

        if not isinstance(code, str) or not code.strip():
            return jsonify({"error": "code is required"}), 400
        if len(code) > MAX_CODE_CHARS:
            return jsonify({"error": "code exceeds maximum size"}), 400
        if not isinstance(language, str) or not isinstance(image, str) or not isinstance(cmd, list):
            return jsonify({"error": "language, image and cmd are required"}), 400

        try:
            timeout = max(1, min(int(timeout), MAX_TIMEOUT_SECONDS))
        except (TypeError, ValueError):
            return jsonify({"error": "timeout must be an integer"}), 400

        try:
            result = run_in_sandbox_local(code, language, image, cmd, timeout)
        except Exception:
            logger.exception("runner execution failed")
            return jsonify({"error": "execution failed"}), 500

        return jsonify(result), 200

    return app
