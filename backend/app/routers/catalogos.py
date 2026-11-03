"""C-04 catalog and patient endpoints."""
from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import require_roles
from app.auth.service import CurrentUser
from app.core.audit import record_audit
from app.models.catalogos import Paciente, Prestacion, Profesional, Sillon
from app.schemas.catalogos import (
    PacienteIn,
    PacienteOut,
    PrestacionIn,
    PrestacionOut,
    ProfesionalIn,
    ProfesionalOut,
    SillonIn,
    SillonOut,
)

router = APIRouter(prefix="/api", tags=["catalogos"])


def get_session(request: Request) -> Iterator[Session]:
    factory = request.app.state.session_factory
    with factory() as session:
        yield session


def _tenant(session: Session, user: CurrentUser) -> None:
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": str(user.tenant_id)},
        )


def _commit_or_409(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Registro duplicado") from exc


@router.get("/profesionales", response_model=list[ProfesionalOut])
def listar_profesionales(
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION", "ODONTOLOGO")),
    session: Session = Depends(get_session),
) -> list[Profesional]:
    _tenant(session, user)
    return list(session.scalars(select(Profesional).where(Profesional.tenant_id == user.tenant_id)))


@router.post("/profesionales", response_model=ProfesionalOut, status_code=status.HTTP_201_CREATED)
def crear_profesional(
    body: ProfesionalIn,
    user: CurrentUser = Depends(require_roles("ADMIN")),
    session: Session = Depends(get_session),
) -> Profesional:
    _tenant(session, user)
    item = Profesional(tenant_id=user.tenant_id, **body.model_dump())
    session.add(item)
    session.flush()
    record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=str(user.id),
        accion="CREADO",
        entidad="profesional",
        entidad_id=str(item.id),
        despues={"activo": item.activo},
    )
    _commit_or_409(session)
    return item


@router.get("/sillones", response_model=list[SillonOut])
def listar_sillones(
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION", "ODONTOLOGO")),
    session: Session = Depends(get_session),
) -> list[Sillon]:
    _tenant(session, user)
    return list(session.scalars(select(Sillon).where(Sillon.tenant_id == user.tenant_id)))


@router.post("/sillones", response_model=SillonOut, status_code=status.HTTP_201_CREATED)
def crear_sillon(
    body: SillonIn,
    user: CurrentUser = Depends(require_roles("ADMIN")),
    session: Session = Depends(get_session),
) -> Sillon:
    _tenant(session, user)
    item = Sillon(tenant_id=user.tenant_id, nombre=body.nombre)
    session.add(item)
    session.flush()
    record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=str(user.id),
        accion="CREADO",
        entidad="sillon",
        entidad_id=str(item.id),
    )
    _commit_or_409(session)
    return item


@router.get("/prestaciones", response_model=list[PrestacionOut])
def listar_prestaciones(
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION", "ODONTOLOGO")),
    session: Session = Depends(get_session),
) -> list[Prestacion]:
    _tenant(session, user)
    return list(session.scalars(select(Prestacion).where(Prestacion.tenant_id == user.tenant_id)))


@router.post("/prestaciones", response_model=PrestacionOut, status_code=status.HTTP_201_CREATED)
def crear_prestacion(
    body: PrestacionIn,
    user: CurrentUser = Depends(require_roles("ADMIN")),
    session: Session = Depends(get_session),
) -> Prestacion:
    _tenant(session, user)
    item = Prestacion(tenant_id=user.tenant_id, **body.model_dump())
    session.add(item)
    session.flush()
    record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=str(user.id),
        accion="CREADO",
        entidad="prestacion",
        entidad_id=str(item.id),
        despues={"duracion_min": item.duracion_min, "activa": item.activa},
    )
    _commit_or_409(session)
    return item


@router.get("/pacientes", response_model=list[PacienteOut])
def listar_pacientes(
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION", "ODONTOLOGO")),
    session: Session = Depends(get_session),
) -> list[Paciente]:
    _tenant(session, user)
    return list(session.scalars(select(Paciente).where(Paciente.tenant_id == user.tenant_id)))


@router.post("/pacientes", response_model=PacienteOut, status_code=status.HTTP_201_CREATED)
def crear_paciente(
    body: PacienteIn,
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION")),
    session: Session = Depends(get_session),
) -> Paciente:
    _tenant(session, user)
    existing = session.scalar(
        select(Paciente).where(
            Paciente.tenant_id == user.tenant_id,
            Paciente.telefono == body.telefono,
        )
    )
    if existing is not None:
        return existing
    item = Paciente(tenant_id=user.tenant_id, **body.model_dump())
    session.add(item)
    session.flush()
    record_audit(
        session,
        tenant_id=user.tenant_id,
        actor_id=str(user.id),
        accion="CREADO",
        entidad="paciente",
        entidad_id=str(item.id),
        despues={"consentimiento_ok": item.consentimiento_ok},
    )
    _commit_or_409(session)
    return item


@router.get("/pacientes/{paciente_id}", response_model=PacienteOut)
def obtener_paciente(
    paciente_id: uuid.UUID,
    user: CurrentUser = Depends(require_roles("ADMIN", "RECEPCION", "ODONTOLOGO")),
    session: Session = Depends(get_session),
) -> Paciente:
    _tenant(session, user)
    item = session.get(Paciente, paciente_id)
    if item is None or item.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado")
    return item
