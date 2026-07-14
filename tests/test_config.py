"""
tests/test_config.py — Tests for environment-specific configuration validation.
"""

from flask import Flask
import pytest

from app_pkg.config import ProductionConfig


def _production_app():
    app = Flask(__name__)
    app.config.from_object(ProductionConfig)
    return app


class TestProductionConfig:
    """ProductionConfig validation requires Redis-backed shared state."""

    def _setup_valid_production_env(self, monkeypatch):
        """Set the minimum env vars required for ProductionConfig.validate()."""
        monkeypatch.setenv("SECRET_KEY", "test-secret-32-chars-min-for-prod!!")
        monkeypatch.setenv("JWT_SECRET_KEY", "test-jwt-secret-32-chars-min-for-pro")
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "redis://localhost:6379/0")
        monkeypatch.setenv("JWT_BLACKLIST_STORAGE_URI", "redis://localhost:6379/1")

    def test_production_requires_redis_url(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        monkeypatch.setenv("REDIS_URL", "")
        with _production_app().app_context():
            with pytest.raises(RuntimeError, match="REDIS_URL"):
                ProductionConfig.validate()

    def test_production_rejects_memory_rate_limit_storage(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "memory://")
        with _production_app().app_context():
            with pytest.raises(RuntimeError, match="RATELIMIT_STORAGE_URI"):
                ProductionConfig.validate()

    def test_production_rejects_memory_blacklist_storage(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        monkeypatch.setenv("JWT_BLACKLIST_STORAGE_URI", "memory://")
        with _production_app().app_context():
            with pytest.raises(RuntimeError, match="JWT_BLACKLIST_STORAGE_URI"):
                ProductionConfig.validate()

    def test_production_accepts_redis_storage_uris(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        with _production_app().app_context():
            # validate() runs storage URI checks and warnings; it should not raise.
            ProductionConfig.validate()

    def test_production_accepts_rediss_rate_limit_storage(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        monkeypatch.setenv("RATE_LIMIT_STORAGE_URI", "rediss://localhost:6379/0")
        with _production_app().app_context():
            ProductionConfig.validate()

    def test_production_accepts_redis_plus_ssl_blacklist_storage(self, monkeypatch):
        self._setup_valid_production_env(monkeypatch)
        monkeypatch.setenv("JWT_BLACKLIST_STORAGE_URI", "redis+ssl://localhost:6379/1")
        with _production_app().app_context():
            ProductionConfig.validate()
