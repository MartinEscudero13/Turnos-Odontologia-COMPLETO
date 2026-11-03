"""Modelos SQLAlchemy — Turno y compatibilidad de auditoría.

`tenant_id` es UUID en todas las tablas de negocio (C-02). La fuente de
anti-solapamiento sigue siendo la migración 003 (`EXCLUDE` en PostgreSQL),
no el código de aplicación.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auditoria import Auditoria
from app.models.base import Base

__all__ = ["Auditoria", "Base", "Turno"]


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
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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

