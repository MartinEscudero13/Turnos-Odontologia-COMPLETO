"""Modelos SQLAlchemy — C-05 (tasks 2.1–2.3).

`tenant_id` NOT NULL everywhere + RLS en la migración 003 (regla dura:
toda query filtra por tenant). `timestamptz` vía DateTime(timezone=True).
FKs a C-04 (profesionales/sillones/pacientes/prestaciones) llegan en su
change (expand-contract); acá van IDs escalares como en el contrato TS.
Sin queries crudas: el SQL vive solo en `backend/alembic/versions/`.

Nota: sin `from __future__ import annotations` a propósito — SQLAlchemy
2.0.35 resuelve anotaciones string con `typing.Union` de un modo
incompatible con Python 3.14; con anotaciones reales el mapeo funciona.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base declarativa del bounded context (C-01 la unifica)."""


class Turno(Base):
    """Turno de agenda. Fuente anti-solape: EXCLUDE 003 (no solo app)."""

    __tablename__ = "turnos"
    __table_args__ = (
        CheckConstraint("fin > inicio", name="turnos_fin_posterior"),
        CheckConstraint(
            "sobreturno = false OR motivo_sobreturno IS NOT NULL",
            name="turnos_sobreturno_motivo",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    profesional_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    sillon_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    paciente_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    prestacion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    sobreturno: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    motivo_sobreturno: Mapped[str] = mapped_column(Text, nullable=True)
    origen: Mapped[str] = mapped_column(Text, nullable=False, default="RECEPCION")
    token_publico: Mapped[str] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Auditoria(Base):
    """Log append-only (UPDATE/DELETE revocados en la migración de C-02)."""

    __tablename__ = "auditoria"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    turno_id: Mapped[str] = mapped_column(Text, nullable=False)
    actor: Mapped[str] = mapped_column(Text, nullable=False)
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=True)
    antes: Mapped[str] = mapped_column(Text, nullable=True)
    despues: Mapped[str] = mapped_column(Text, nullable=False)
    registrado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

