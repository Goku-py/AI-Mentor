"""app_pkg/gemini_circuit.py — Redis-backed circuit breaker for Gemini API calls.

The breaker protects the app from hammering the Gemini API when it is
unhealthy or rate-limiting us. It is intentionally simple and stateless so
that it works correctly across multiple Gunicorn workers backed by Redis.
"""

from __future__ import annotations

import os
import time
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class GeminiCircuitBreaker:
    """Redis-backed circuit breaker for the Gemini API.

    Configuration (via environment variables):
      GEMINI_CIRCUIT_FAILURE_THRESHOLD — consecutive failures before opening.
      GEMINI_CIRCUIT_COOLDOWN_SECONDS  — seconds to wait before half-open.
      GEMINI_CIRCUIT_HALF_OPEN_MAX     — max probe calls in half-open state.
    """

    _KEY_PREFIX = "gemini_circuit:"

    def __init__(self, redis_client: Any | None = None) -> None:
        self._client = redis_client
        self._failure_threshold = int(
            os.environ.get("GEMINI_CIRCUIT_FAILURE_THRESHOLD", "5")
        )
        self._cooldown_seconds = int(
            os.environ.get("GEMINI_CIRCUIT_COOLDOWN_SECONDS", "60")
        )
        self._half_open_max = int(
            os.environ.get("GEMINI_CIRCUIT_HALF_OPEN_MAX", "2")
        )

    def _redis(self) -> Any | None:
        """Return the Redis client, lazily resolving it if not provided."""
        if self._client is not None:
            return self._client
        try:
            from app_pkg.extensions import require_redis_client  # noqa: PLC0415
            self._client = require_redis_client()
        except Exception:  # noqa: BLE001
            self._client = None
        return self._client

    def _key(self, name: str) -> str:
        return f"{self._KEY_PREFIX}{name}"

    def can_call(self) -> bool:
        """Return True if the API call is allowed under the current state."""
        client = self._redis()
        if client is None:
            # Without Redis we fall back to an always-closed breaker.
            return True

        state_bytes = client.get(self._key("state"))
        state = (
            CircuitState(state_bytes.decode("utf-8"))
            if state_bytes
            else CircuitState.CLOSED
        )

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            opened_at_bytes = client.get(self._key("opened_at"))
            opened_at = float(opened_at_bytes or 0)
            if time.time() - opened_at >= self._cooldown_seconds:
                client.set(self._key("state"), CircuitState.HALF_OPEN.value)
                client.set(self._key("probes"), 0)
                return True
            return False

        # HALF_OPEN: allow a bounded number of probe calls.
        probes = int(client.get(self._key("probes")) or 0)
        return probes < self._half_open_max

    def record_success(self) -> None:
        """Record a successful Gemini API call."""
        client = self._redis()
        if client is None:
            return

        state_bytes = client.get(self._key("state"))
        state = (
            CircuitState(state_bytes.decode("utf-8"))
            if state_bytes
            else CircuitState.CLOSED
        )

        pipe = client.pipeline()
        if state == CircuitState.HALF_OPEN:
            # Any success during probing closes the circuit immediately.
            pipe.set(self._key("state"), CircuitState.CLOSED.value)
            pipe.set(self._key("failures"), 0)
            pipe.delete(self._key("opened_at"))
            pipe.delete(self._key("probes"))
        else:
            pipe.set(self._key("state"), CircuitState.CLOSED.value)
            pipe.set(self._key("failures"), 0)
            pipe.delete(self._key("opened_at"))
            pipe.delete(self._key("probes"))
        pipe.execute()

    def record_failure(self) -> None:
        """Record a failed Gemini API call and open the breaker if needed."""
        client = self._redis()
        if client is None:
            return

        state_bytes = client.get(self._key("state"))
        state = (
            CircuitState(state_bytes.decode("utf-8"))
            if state_bytes
            else CircuitState.CLOSED
        )

        pipe = client.pipeline()
        if state == CircuitState.HALF_OPEN:
            # A single failure while probing re-opens the circuit immediately.
            pipe.set(self._key("state"), CircuitState.OPEN.value)
            pipe.set(self._key("opened_at"), time.time())
            pipe.set(self._key("failures"), 1)
            pipe.delete(self._key("probes"))
        else:
            failures = int(client.get(self._key("failures")) or 0) + 1
            pipe.set(self._key("failures"), failures)
            if failures >= self._failure_threshold:
                pipe.set(self._key("state"), CircuitState.OPEN.value)
                pipe.set(self._key("opened_at"), time.time())
        pipe.execute()

    def state(self) -> CircuitState:
        """Return the current circuit state (mainly for tests/observability)."""
        client = self._redis()
        if client is None:
            return CircuitState.CLOSED
        state_bytes = client.get(self._key("state"))
        if not state_bytes:
            return CircuitState.CLOSED
        return CircuitState(state_bytes.decode("utf-8"))
