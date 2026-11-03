"""Health and app factory tests."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings


def make_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://db:6379/0",
        JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-12345",  # noqa: S105
        APP_URL="http://localhost:3000",
        APP_NAME="turnos-api",
    )


def client() -> TestClient:
    return TestClient(create_app(make_settings()))


def test_health_returns_up() -> None:
    response = client().get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "UP", "service": "turnos-api", "version": "0.1.0"}


def test_correlation_id_is_round_tripped() -> None:
    response = client().get("/api/health", headers={"X-Correlation-ID": "corr-fixed-1"})
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-fixed-1"
