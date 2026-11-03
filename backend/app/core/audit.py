"""Append-only audit helper used by access and business operations."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.auditoria import Auditoria


def record_audit(
    session: Session,
    *,
    tenant_id: uuid.UUID | str,
    actor_id: str,
    accion: str,
    entidad: str,
    entidad_id: str,
    antes: dict[str, Any] | None = None,
    despues: dict[str, Any] | None = None,
    motivo: str | None = None,
) -> Auditoria:
    entry = Auditoria(
        tenant_id=uuid.UUID(str(tenant_id)),
        actor_id=actor_id,
        accion=accion,
        entidad=entidad,
        entidad_id=entidad_id,
        antes=antes,
        despues=despues,
        motivo=motivo,
    )
    session.add(entry)
    session.flush()
    return entry
