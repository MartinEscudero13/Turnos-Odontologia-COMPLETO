"""Auth HTTP contract tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.app import create_app
from app.auth.security import hash_password
from app.core.settings import Settings
from app.models.auditoria import Auditoria
from app.models.base import Base
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.usuario import Usuario

SECRET = "test-secret-that-is-long-enough-for-local-dev-1234567890"
TENANT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
ADMIN_ID = uuid.UUID("b0000000-0000-4000-8000-000000000001")
RECEP_ID = uuid.UUID("b0000000-0000-4000-8000-000000000002")


def settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET=SECRET,
        APP_URL="http://localhost:5173",
    )


@pytest.fixture
def client_and_factory() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[Tenant.__table__, Usuario.__table__, RefreshToken.__table__, Auditoria.__table__],
    )
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        session.add(Tenant(id=TENANT_ID, nombre="Consultorio Demo", slug="demo"))
        session.add_all(
            [
                Usuario(
                    id=ADMIN_ID,
                    tenant_id=TENANT_ID,
                    nombre="Admin Demo",
                    email="admin@demo.test",
                    password_hash=hash_password("correct-password"),
                    rol="ADMIN",
                ),
                Usuario(
                    id=RECEP_ID,
                    tenant_id=TENANT_ID,
                    nombre="Recepción Demo",
                    email="recep@demo.test",
                    password_hash=hash_password("correct-password"),
                    rol="RECEPCION",
                ),
            ]
        )
        session.commit()
    app = create_app(settings(), session_factory_override=factory)
    yield TestClient(app), factory


def login(client: TestClient, email: str = "admin@demo.test", password: str = "correct-password"):
    return client.post(
        "/api/auth/login",
        json={
            "tenant_slug": "demo",
            "email": email,
            "password": password,
        },
    )


def test_login_me_and_no_secrets_in_response(client_and_factory) -> None:
    client, factory = client_and_factory
    response = login(client)
    assert response.status_code == 200
    tokens = response.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    assert "correct-password" not in response.text
    assert "password_hash" not in response.text

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "admin@demo.test"
    assert "password_hash" not in body
    with factory() as session:
        entries = session.query(Auditoria).all()
        assert any(entry.accion == "LOGIN" for entry in entries)


def test_refresh_and_logout_contract(client_and_factory) -> None:
    client, _ = client_and_factory
    tokens = login(client).json()
    refreshed = client.post(
        "/api/auth/refresh",
        json={"tenant_slug": "demo", "refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]

    logout = client.post(
        "/api/auth/logout",
        json={"tenant_slug": "demo", "refresh_token": refreshed.json()["refresh_token"]},
    )
    assert logout.status_code == 204
    reused = client.post(
        "/api/auth/refresh",
        json={"tenant_slug": "demo", "refresh_token": refreshed.json()["refresh_token"]},
    )
    assert reused.status_code == 401


def test_rbac_rejects_reception_from_admin_route(client_and_factory) -> None:
    client, _ = client_and_factory
    tokens = login(client, email="recep@demo.test").json()
    response = client.get(
        "/api/auth/admin-check",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert response.status_code == 403


def test_missing_and_tampered_tokens_are_401(client_and_factory) -> None:
    client, _ = client_and_factory
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.get(
            "/api/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        ).status_code
        == 401
    )


def test_login_rate_limit_returns_429(client_and_factory) -> None:
    client, _ = client_and_factory
    for _ in range(5):
        assert login(client, password="wrong").status_code == 401
    response = login(client, password="wrong")
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
