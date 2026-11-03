"""C-04 catalog and patient API tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.app import create_app
from app.auth.deps import get_current_user
from app.auth.service import CurrentUser
from app.core.settings import Settings
from app.models.auditoria import Auditoria
from app.models.base import Base
from app.models.catalogos import (
    Bloqueo,
    HorarioSemanal,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalPrestacion,
    Sillon,
)
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.usuario import Usuario

TENANT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
ADMIN_ID = uuid.UUID("b0000000-0000-4000-8000-000000000001")

TABLES = [
    Tenant.__table__,
    Usuario.__table__,
    Sillon.__table__,
    Prestacion.__table__,
    Profesional.__table__,
    ProfesionalPrestacion.__table__,
    HorarioSemanal.__table__,
    Bloqueo.__table__,
    Paciente.__table__,
    Auditoria.__table__,
    RefreshToken.__table__,
]


def app_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
        APP_URL="http://localhost:5173",
    )


@pytest.fixture
def client_and_factory() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=TABLES)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session:
        session.add(Tenant(id=TENANT_ID, nombre="Consultorio Demo", slug="demo"))
        session.commit()
    app = create_app(app_settings(), session_factory_override=factory)
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=ADMIN_ID,
        tenant_id=TENANT_ID,
        nombre="Admin Demo",
        email="admin@demo.test",
        rol="ADMIN",
        two_factor=False,
    )
    yield TestClient(app), factory


def test_admin_can_create_and_list_catalogs(client_and_factory) -> None:
    client, factory = client_and_factory
    sillon = client.post("/api/sillones", json={"nombre": "Sillón 1"})
    assert sillon.status_code == 201
    assert sillon.json()["nombre"] == "Sillón 1"

    prestacion = client.post(
        "/api/prestaciones",
        json={"nombre": "Limpieza", "duracion_min": 30, "precio_base": 0},
    )
    assert prestacion.status_code == 201
    assert client.get("/api/prestaciones").status_code == 200

    profesional = client.post(
        "/api/profesionales",
        json={"nombre": "Dra. Demo", "especialidad": "Odontología"},
    )
    assert profesional.status_code == 201
    with factory() as session:
        assert len(session.scalars(select(Sillon)).all()) == 1
        assert session.scalar(select(Auditoria).where(Auditoria.entidad == "sillon")) is not None


def test_patient_phone_is_normalized_and_duplicate_returns_same_record(client_and_factory) -> None:
    client, factory = client_and_factory
    first = client.post(
        "/api/pacientes",
        json={"nombre": "Paciente Demo", "telefono": "+54 9 11 3055 1234"},
    )
    assert first.status_code == 201
    assert first.json()["telefono"] == "+5491130551234"
    second = client.post(
        "/api/pacientes",
        json={"nombre": "Otro Paciente Demo", "telefono": "+5491130551234"},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    with factory() as session:
        assert len(session.scalars(select(Paciente)).all()) == 1


def test_invalid_phone_and_reception_catalog_write_are_rejected(client_and_factory) -> None:
    client, _ = client_and_factory
    invalid = client.post(
        "/api/pacientes",
        json={"nombre": "Paciente Demo", "telefono": "123"},
    )
    assert invalid.status_code == 422

    app = client.app
    app.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uuid.uuid4(),
        tenant_id=TENANT_ID,
        nombre="Recepción Demo",
        email="recep@demo.test",
        rol="RECEPCION",
        two_factor=False,
    )
    forbidden = client.post("/api/sillones", json={"nombre": "Sillón prohibido"})
    assert forbidden.status_code == 403
