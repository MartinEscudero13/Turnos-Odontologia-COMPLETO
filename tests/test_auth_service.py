"""AuthService login/refresh/logout/2FA/audit tests."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

import pyotp
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.security import encrypt_totp_secret, hash_password
from app.auth.service import AuthError, AuthService
from app.core.settings import Settings
from app.models.auditoria import Auditoria
from app.models.base import Base
from app.models.refresh_token import RefreshToken
from app.models.tenant import Tenant
from app.models.usuario import Usuario

SECRET = "test-secret-that-is-long-enough-for-local-dev-1234567890"
TENANT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
USER_ID = uuid.UUID("b0000000-0000-4000-8000-000000000001")


def make_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
        REDIS_URL="redis://localhost:6379/0",
        JWT_SECRET=SECRET,
        APP_URL="http://localhost:5173",
    )


@pytest.fixture
def service_and_factory() -> Iterator[tuple[AuthService, sessionmaker[Session]]]:
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
    service = AuthService(make_settings(), factory)
    with factory() as session:
        session.add(Tenant(id=TENANT_ID, nombre="Consultorio Demo", slug="demo"))
        session.add(
            Usuario(
                id=USER_ID,
                tenant_id=TENANT_ID,
                nombre="Admin Demo",
                email="admin@demo.test",
                password_hash=hash_password("correct-password"),
                rol="ADMIN",
                two_factor=False,
            )
        )
        session.commit()
    yield service, factory


def login(service: AuthService, email: str = "admin@demo.test", password: str = "correct-password"):
    return service.login(
        tenant_slug="demo",
        email=email,
        password=password,
        two_factor_code=None,
        ip="127.0.0.1",
    )


def test_login_creates_tokens_and_audit(service_and_factory) -> None:
    service, factory = service_and_factory
    tokens = login(service)
    assert tokens.access_token
    assert tokens.refresh_token
    assert service.current_user(tokens.access_token).rol == "ADMIN"
    with factory() as session:
        entries = session.scalars(select(Auditoria)).all()
        assert len(entries) == 1
        assert entries[0].accion == "LOGIN"
        assert "correct-password" not in str(entries[0].despues)


def test_bad_password_is_generic(service_and_factory) -> None:
    service, _ = service_and_factory
    with pytest.raises(AuthError) as exc:
        login(service, password="wrong")
    assert exc.value.status_code == 401
    assert exc.value.message == "Credenciales inválidas"


def test_refresh_rotates_and_revokes_old(service_and_factory) -> None:
    service, factory = service_and_factory
    first = login(service)
    second = service.refresh(tenant_slug="demo", raw_refresh_token=first.refresh_token)
    assert second.refresh_token != first.refresh_token
    with pytest.raises(AuthError):
        service.refresh(tenant_slug="demo", raw_refresh_token=first.refresh_token)
    with factory() as session:
        tokens = session.scalars(select(RefreshToken)).all()
        assert len(tokens) == 2
        assert sum(1 for token in tokens if token.revocado_en is not None) == 1


def test_logout_revokes_refresh(service_and_factory) -> None:
    service, _ = service_and_factory
    tokens = login(service)
    service.logout(tenant_slug="demo", raw_refresh_token=tokens.refresh_token)
    with pytest.raises(AuthError):
        service.refresh(tenant_slug="demo", raw_refresh_token=tokens.refresh_token)


def test_inactive_user_cannot_login(service_and_factory) -> None:
    service, factory = service_and_factory
    with factory() as session:
        user = session.get(Usuario, USER_ID)
        assert user is not None
        user.activo = False
        session.commit()
    with pytest.raises(AuthError) as exc:
        login(service)
    assert exc.value.status_code == 403


def test_totp_is_required_when_enabled(service_and_factory) -> None:
    service, factory = service_and_factory
    secret = pyotp.random_base32()
    with factory() as session:
        user = session.get(Usuario, USER_ID)
        assert user is not None
        user.two_factor = True
        user.two_factor_secret = encrypt_totp_secret(secret, SECRET)
        session.commit()
    with pytest.raises(AuthError) as exc:
        login(service)
    assert exc.value.status_code == 401
    tokens = service.login(
        tenant_slug="demo",
        email="admin@demo.test",
        password="correct-password",
        two_factor_code=pyotp.TOTP(secret).now(),
        ip="127.0.0.1",
    )
    assert tokens.access_token


def test_second_login_with_wrong_password_is_rate_limited_after_five(service_and_factory) -> None:
    service, _ = service_and_factory
    for _ in range(5):
        with pytest.raises(AuthError) as exc:
            login(service, password="wrong")
        assert exc.value.status_code == 401
    with pytest.raises(AuthError) as exc:
        login(service, password="wrong")
    assert exc.value.status_code == 429
    assert exc.value.retry_after is not None
