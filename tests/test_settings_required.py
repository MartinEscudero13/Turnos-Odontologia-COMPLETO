"""Environment contract tests for backend settings."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.settings import Settings


def test_settings_require_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "REDIS_URL", "JWT_SECRET", "APP_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None)
    assert "database_url" in str(exc.value).lower()


def test_production_rejects_placeholder_secret() -> None:
    with pytest.raises(ValidationError):
        Settings(
            APP_ENV="production",
            DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
            REDIS_URL="redis://db:6379/0",
            JWT_SECRET="jwt-change-me",
            APP_URL="https://turnos.example.com",
        )


def test_development_accepts_valid_environment() -> None:
    settings = Settings(
        APP_ENV="development",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://db:6379/0",
        JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-12345",  # noqa: S105
        APP_URL="http://localhost:3000",
    )
    assert settings.app_name == "turnos-api"
    assert settings.is_production is False
