"""
tests/test_extensions.py — Tests for Redis extension helpers.
"""

import pytest

import app_pkg.extensions as extensions


class TestRequireRedisClient:
    """require_redis_client() fails loudly in production when Redis is unavailable."""

    def test_require_redis_client_returns_none_in_dev_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(extensions, "get_redis_client", lambda: None)
        monkeypatch.setattr(extensions, "is_production", lambda: False)
        assert extensions.require_redis_client() is None

    def test_require_redis_client_raises_in_production_when_unavailable(self, monkeypatch):
        monkeypatch.setattr(extensions, "get_redis_client", lambda: None)
        monkeypatch.setattr(extensions, "is_production", lambda: True)
        with pytest.raises(RuntimeError, match="Redis is required in production"):
            extensions.require_redis_client()

    def test_require_redis_client_returns_client_when_available(self, monkeypatch):
        fake_client = object()
        monkeypatch.setattr(extensions, "get_redis_client", lambda: fake_client)
        assert extensions.require_redis_client() is fake_client


class TestGetRedisClientCacheInvalidation:
    """Cached Redis client must be invalidated when PING fails."""

    def test_get_redis_client_resets_cached_pool_on_ping_failure(self, monkeypatch):
        class FailingClient:
            def ping(self):
                raise ConnectionError("Redis down")

        # Seed the cached pool with a broken client.
        extensions._redis_pool = FailingClient()
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")

        # Ensure the reconnect attempt also fails so we can assert the cache
        # was cleared rather than getting a real connection.
        monkeypatch.setattr(extensions, "_resolve_redis_uri", lambda: "redis://localhost:6379")

        try:
            import redis as _redis  # noqa: PLC0415
        except ImportError:
            _redis = None

        if _redis is not None:
            monkeypatch.setattr(_redis, "from_url", lambda *_args, **_kwargs: FailingClient())

        assert extensions.get_redis_client() is None
        assert extensions._redis_pool is None
