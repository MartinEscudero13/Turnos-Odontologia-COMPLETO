"""Adaptadores de composición de la demo entre catálogos y dominios clínicos."""
from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.catalogos import Paciente

__all__ = [
    "PacienteCatalogoFicha",
    "PacienteCatalogoPresupuesto",
    "PacienteSQL",
]


class _PacientesCatalogo(Protocol):
    def paciente(self, tenant_id: str, paciente_id: str) -> object | None: ...


class PacienteCatalogoFicha:
    """`PacientePort` de ficha/odontograma sobre el catálogo compartido."""

    def __init__(self, pacientes: _PacientesCatalogo) -> None:
        self._pacientes = pacientes

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        return self._pacientes.paciente(tenant_id, paciente_id) is not None


class PacienteCatalogoPresupuesto:
    """`PacientePort` de presupuesto: existencia en catálogo + OS configurada."""

    def __init__(
        self,
        pacientes: _PacientesCatalogo,
        obras_sociales: dict[tuple[str, str], str | None] | None = None,
    ) -> None:
        self._pacientes = pacientes
        self._obras = obras_sociales or {}

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        return self._pacientes.paciente(tenant_id, paciente_id) is not None

    def obra_social_id(self, *, tenant_id: str, paciente_id: str) -> str | None:
        return self._obras.get((tenant_id, paciente_id))


class PacienteSQL:
    """`PacientePort` clínico sobre la tabla SQL de pacientes (runtime real).

    La demo interna crea pacientes por el router SQL de catálogos; los dominios
    clínicos necesitan verlos. Mantiene el mapa de OS de la demo para no perder
    la cobertura de los dos pacientes sembrados.
    """

    def __init__(
        self,
        session_factory: Callable[[], Session],
        obras_sociales: dict[tuple[str, str], str | None] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._obras = obras_sociales or {}

    def _obra_sql(self, tenant_id: str, paciente_id: str) -> uuid.UUID | None:
        try:
            tenant = uuid.UUID(tenant_id)
            paciente = uuid.UUID(paciente_id)
        except ValueError:
            return None
        with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": tenant_id},
                )
            return session.scalar(
                select(Paciente.obra_social_id).where(
                    Paciente.id == paciente, Paciente.tenant_id == tenant
                )
            )

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        try:
            tenant = uuid.UUID(tenant_id)
            paciente = uuid.UUID(paciente_id)
        except ValueError:
            return False
        with self._session_factory() as session:
            if session.get_bind().dialect.name == "postgresql":
                session.execute(
                    text("SELECT set_config('app.tenant_id', :tenant, true)"),
                    {"tenant": tenant_id},
                )
            return (
                session.scalar(
                    select(Paciente.id).where(
                        Paciente.id == paciente, Paciente.tenant_id == tenant
                    )
                )
                is not None
            )

    def obra_social_id(self, *, tenant_id: str, paciente_id: str) -> str | None:
        mapa = self._obras.get((tenant_id, paciente_id))
        if mapa is not None:
            return mapa
        obra = self._obra_sql(tenant_id, paciente_id)
        return None if obra is None else str(obra)
