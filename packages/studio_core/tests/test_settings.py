"""Tests for Studio Settings and Configuration."""

import pytest

from studio_core.settings import Settings


def test_settings_default_values() -> None:
    settings = Settings(
        supabase_url="http://localhost:54321",
        database_url="postgresql://test:test@localhost:5432/test",
    )
    assert settings.supabase_url == "http://localhost:54321"
    assert settings.database_url == "postgresql://test:test@localhost:5432/test"
    assert settings.storage_bucket == "media"
    assert settings.max_active_jobs_per_workspace == 5
    assert settings.environment == "local"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BUCKET", "custom-bucket")
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("MAX_ACTIVE_JOBS_PER_WORKSPACE", "10")

    settings = Settings()
    assert settings.storage_bucket == "custom-bucket"
    assert settings.environment == "staging"
    assert settings.max_active_jobs_per_workspace == 10


def test_settings_regex_web_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REGEX_WEB_ORIGINS", r"^https://.*\.vercel\.app$")

    settings = Settings()
    assert settings.regex_web_origins == r"^https://.*\.vercel\.app$"
