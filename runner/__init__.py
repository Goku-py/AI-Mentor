"""Sandbox execution runner.

Owns the Docker daemon so untrusted student code never executes on the API host.
Talks to the Flask app over private HTTP with a shared secret.
"""

from .server import create_runner_app

__all__ = ["create_runner_app"]
