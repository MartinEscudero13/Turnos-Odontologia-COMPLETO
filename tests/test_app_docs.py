"""Documentation and OpenAPI contract for the foundation app."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings


def authenticate_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://db:6379/0",
        JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-12345",  # noqa: S105
        APP_URL="http://localhost:3000",
    )


def test_openapi_describes_foundation_slice() -> None:
    response = TestClient(create_app(authenticate_settings())).get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "turnos-api API"
    assert "/api/health" in spec["paths"]


def test_docs_route_is_available_with_correlation_header() -> None:
    response = TestClient(create_app(authenticate_settings())).get(
        "/docs", headers={"X-Correlation-ID": "corr-docs"}
    )
    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "corr-docs"
