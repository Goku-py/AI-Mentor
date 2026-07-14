"""tests/test_circuit.py — Gemini circuit breaker state transitions."""

from __future__ import annotations

import os
import time

import fakeredis
import pytest

from app_pkg.gemini_circuit import CircuitState, GeminiCircuitBreaker


@pytest.fixture
def fake_redis():
    """Provide a fresh fakeredis client for each test."""
    return fakeredis.FakeRedis()


@pytest.fixture
def breaker(fake_redis, monkeypatch):
    """Circuit breaker configured for fast state transitions in tests."""
    monkeypatch.setenv("GEMINI_CIRCUIT_FAILURE_THRESHOLD", "3")
    monkeypatch.setenv("GEMINI_CIRCUIT_COOLDOWN_SECONDS", "1")
    monkeypatch.setenv("GEMINI_CIRCUIT_HALF_OPEN_MAX", "2")
    return GeminiCircuitBreaker(fake_redis)


class TestGeminiCircuitBreaker:
    """State-machine coverage for the Redis-backed circuit breaker."""

    def test_starts_closed(self, breaker):
        assert breaker.state() == CircuitState.CLOSED
        assert breaker.can_call() is True

    def test_records_success_resets_failures(self, breaker):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_success()
        assert breaker.state() == CircuitState.CLOSED
        assert breaker.can_call() is True

    def test_opens_after_threshold_failures(self, breaker):
        breaker.record_failure()
        assert breaker.state() == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state() == CircuitState.CLOSED
        breaker.record_failure()
        assert breaker.state() == CircuitState.OPEN
        assert breaker.can_call() is False

    def test_half_open_after_cooldown(self, breaker):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state() == CircuitState.OPEN
        assert breaker.can_call() is False

        time.sleep(1.1)
        assert breaker.can_call() is True
        assert breaker.state() == CircuitState.HALF_OPEN

    def test_half_open_failure_reopens(self, breaker):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(1.1)
        assert breaker.can_call() is True

        breaker.record_failure()
        assert breaker.state() == CircuitState.OPEN
        assert breaker.can_call() is False

    def test_half_open_success_closes(self, breaker):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(1.1)
        assert breaker.can_call() is True

        breaker.record_success()
        assert breaker.state() == CircuitState.CLOSED
        assert breaker.can_call() is True

    def test_half_open_allows_limited_probes(self, breaker):
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        time.sleep(1.1)
        # HALF_OPEN_MAX is 2, so two calls are allowed.
        assert breaker.can_call() is True
        breaker.record_success()
        assert breaker.can_call() is True
        breaker.record_success()
        # After two successes the breaker should close.
        assert breaker.state() == CircuitState.CLOSED
        assert breaker.can_call() is True

    def test_without_redis_is_always_closed(self, monkeypatch):
        monkeypatch.setenv("GEMINI_CIRCUIT_FAILURE_THRESHOLD", "1")
        breaker = GeminiCircuitBreaker(redis_client=None)
        assert breaker.can_call() is True
        breaker.record_failure()
        assert breaker.can_call() is True

    def test_environment_defaults(self, fake_redis, monkeypatch):
        monkeypatch.delenv("GEMINI_CIRCUIT_FAILURE_THRESHOLD", raising=False)
        monkeypatch.delenv("GEMINI_CIRCUIT_COOLDOWN_SECONDS", raising=False)
        monkeypatch.delenv("GEMINI_CIRCUIT_HALF_OPEN_MAX", raising=False)
        breaker = GeminiCircuitBreaker(fake_redis)
        assert breaker._failure_threshold == 5  # noqa: SLF001
        assert breaker._cooldown_seconds == 60  # noqa: SLF001
        assert breaker._half_open_max == 2  # noqa: SLF001
