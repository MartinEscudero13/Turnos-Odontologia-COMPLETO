"""Seed demo idempotente para probar el frontend.

Crea tenant, usuarios, profesionales, sillones, prestaciones y pacientes
ficticios. Se ejecuta con el rol owner después de las migraciones:

    DATABASE_OWNER_URL=postgresql+psycopg://... DEMO_PASSWORD=... python seed_demo.py

Credenciales demo (el password se define en la variable DEMO_PASSWORD, nunca en el repo):
    tenant: demo
    admin@demo.test
    recepcion@demo.test
    odontologo@demo.test
"""
from __future__ import annotations

import os
import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.models.catalogos import Paciente, Prestacion, Profesional, Sillon
from app.models.usuario import Usuario
from app.seed import (
    DEMO_ADMIN_ID,
    DEMO_ODONTOLOGO_ID,
    DEMO_PACIENTE_1,
    DEMO_PACIENTE_2,
    DEMO_PRESTACION_CONSULTA,
    DEMO_PRESTACION_LIMPIEZA,
    DEMO_PROFESIONAL_1,
    DEMO_PROFESIONAL_2,
    DEMO_RECEPCION_ID,
    DEMO_SILLON_1,
    DEMO_SILLON_2,
    DEMO_TENANT_ID,
    DEMO_TENANT_NAME,
    DEMO_TENANT_SLUG,
    seed_tenant,
)


def _password() -> str:
    password = os.environ.get("DEMO_PASSWORD", "").strip()
    if len(password) < 8:
        raise SystemExit("Definí DEMO_PASSWORD (mínimo 8 caracteres) para sembrar la demo")
    return password


def _usuario(
    session: Session, *, nombre: str, email: str, rol: str, usuario_id: str, password: str
) -> None:
    tenant_id = uuid.UUID(DEMO_TENANT_ID)
    existente = session.scalar(
        select(Usuario).where(
            Usuario.tenant_id == tenant_id, Usuario.email == email
        )
    )
    if existente is None:
        session.add(
            Usuario(
                id=uuid.UUID(usuario_id),
                tenant_id=tenant_id,
                nombre=nombre,
                email=email,
                password_hash=hash_password(password),
                rol=rol,
                two_factor=False,
                activo=True,
            )
        )


def _profesional(
    session: Session, *, profesional_id: str, nombre: str, usuario_id: str | None
) -> None:
    tenant_id = uuid.UUID(DEMO_TENANT_ID)
    if session.get(Profesional, uuid.UUID(profesional_id)) is None:
        session.add(
            Profesional(
                id=uuid.UUID(profesional_id),
                tenant_id=tenant_id,
                usuario_id=None if usuario_id is None else uuid.UUID(usuario_id),
                nombre=nombre,
                especialidad="Odontología",
                matricula=None,
                color_agenda="#0f766e",
                activo=True,
            )
        )


def _sillon(session: Session, *, sillon_id: str, nombre: str) -> None:
    if session.get(Sillon, uuid.UUID(sillon_id)) is None:
        session.add(
            Sillon(
                id=uuid.UUID(sillon_id),
                tenant_id=uuid.UUID(DEMO_TENANT_ID),
                nombre=nombre,
                activo=True,
            )
        )


def _prestacion(
    session: Session,
    *,
    prestacion_id: str,
    nombre: str,
    duracion_min: int,
    precio_base: int,
) -> None:
    if session.get(Prestacion, uuid.UUID(prestacion_id)) is None:
        session.add(
            Prestacion(
                id=uuid.UUID(prestacion_id),
                tenant_id=uuid.UUID(DEMO_TENANT_ID),
                nombre=nombre,
                duracion_min=duracion_min,
                precio_base=precio_base,
                requiere_sena=False,
                monto_sena=None,
                activa=True,
                sena_modo="PORCENTAJE" if nombre == "Consulta" else "SIN_SENA",
                sena_valor=30 if nombre == "Consulta" else None,
            )
        )


def _paciente(
    session: Session, *, paciente_id: str, nombre: str, telefono: str, email: str
) -> None:
    if session.get(Paciente, uuid.UUID(paciente_id)) is None:
        session.add(
            Paciente(
                id=uuid.UUID(paciente_id),
                tenant_id=uuid.UUID(DEMO_TENANT_ID),
                nombre=nombre,
                telefono=telefono,
                email=email,
                nro_afiliado=None,
                consentimiento_ok=True,
            )
        )


def aplicar(engine_url: str, password: str) -> None:
    engine = create_engine(engine_url, future=True)
    try:
        with Session(engine) as session:
            seed_tenant(
                session,
                tenant_id=DEMO_TENANT_ID,
                slug=DEMO_TENANT_SLUG,
                nombre=DEMO_TENANT_NAME,
            )
            _usuario(
                session,
                nombre="Admin Demo",
                email="admin@demo.test",
                rol="ADMIN",
                usuario_id=DEMO_ADMIN_ID,
                password=password,
            )
            _usuario(
                session,
                nombre="Recepción Demo",
                email="recepcion@demo.test",
                rol="RECEPCION",
                usuario_id=DEMO_RECEPCION_ID,
                password=password,
            )
            _usuario(
                session,
                nombre="Odontólogo Demo",
                email="odontologo@demo.test",
                rol="ODONTOLOGO",
                usuario_id=DEMO_ODONTOLOGO_ID,
                password=password,
            )
            _profesional(
                session,
                profesional_id=DEMO_PROFESIONAL_1,
                nombre="Dra. Demo Uno",
                usuario_id=DEMO_ODONTOLOGO_ID,
            )
            _profesional(
                session,
                profesional_id=DEMO_PROFESIONAL_2,
                nombre="Dr. Demo Dos",
                usuario_id=None,
            )
            _sillon(session, sillon_id=DEMO_SILLON_1, nombre="Sillón 1")
            _sillon(session, sillon_id=DEMO_SILLON_2, nombre="Sillón 2")
            _prestacion(
                session,
                prestacion_id=DEMO_PRESTACION_CONSULTA,
                nombre="Consulta",
                duracion_min=30,
                precio_base=10000,
            )
            _prestacion(
                session,
                prestacion_id=DEMO_PRESTACION_LIMPIEZA,
                nombre="Limpieza",
                duracion_min=45,
                precio_base=15000,
            )
            _paciente(
                session,
                paciente_id=DEMO_PACIENTE_1,
                nombre="Paciente Demo Uno",
                telefono="+5491130551001",
                email="paciente1@demo.test",
            )
            _paciente(
                session,
                paciente_id=DEMO_PACIENTE_2,
                nombre="Paciente Demo Dos",
                telefono="+5491130551002",
                email="paciente2@demo.test",
            )
            session.commit()
    finally:
        engine.dispose()


def main() -> None:
    url = os.environ.get("DATABASE_OWNER_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("Definí DATABASE_OWNER_URL para sembrar la demo")
    aplicar(url, _password())
    print("Seed demo listo: tenant 'demo' (password definido por DEMO_PASSWORD)")


if __name__ == "__main__":
    main()
