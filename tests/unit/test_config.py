"""Tests for application configuration."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestSettings:
    """Tests for Settings validation."""

    def test_valid_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that valid settings are loaded correctly."""
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("RABBITMQ_HOST", "localhost")
        monkeypatch.setenv("RABBITMQ_PORT", "5672")
        monkeypatch.setenv("RABBITMQ_DEFAULT_USER", "guest")
        monkeypatch.setenv("RABBITMQ_DEFAULT_PASS", "guest")

        settings = Settings()
        assert settings.project_name == "PricePulse"
        assert settings.log_level == "INFO"

    def test_price_check_interval_validation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that price_check_interval must be at least 60 seconds."""
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("RABBITMQ_HOST", "localhost")
        monkeypatch.setenv("RABBITMQ_PORT", "5672")
        monkeypatch.setenv("RABBITMQ_DEFAULT_USER", "guest")
        monkeypatch.setenv("RABBITMQ_DEFAULT_PASS", "guest")
        monkeypatch.setenv("PRICE_CHECK_INTERVAL", "30")

        with pytest.raises(ValidationError):
            Settings()

    def test_log_level_validation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid log level raises ValidationError."""
        monkeypatch.setenv("POSTGRES_DB", "test_db")
        monkeypatch.setenv("POSTGRES_USER", "test_user")
        monkeypatch.setenv("POSTGRES_PASSWORD", "test_pass")
        monkeypatch.setenv("POSTGRES_HOST", "localhost")
        monkeypatch.setenv("POSTGRES_PORT", "5432")
        monkeypatch.setenv("REDIS_HOST", "localhost")
        monkeypatch.setenv("REDIS_PORT", "6379")
        monkeypatch.setenv("RABBITMQ_HOST", "localhost")
        monkeypatch.setenv("RABBITMQ_PORT", "5672")
        monkeypatch.setenv("RABBITMQ_DEFAULT_USER", "guest")
        monkeypatch.setenv("RABBITMQ_DEFAULT_PASS", "guest")
        monkeypatch.setenv("LOG_LEVEL", "INVALID")

        with pytest.raises(ValidationError):
            Settings()
