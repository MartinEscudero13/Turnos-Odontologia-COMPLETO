"""C-07 lista de espera y ofertas — modelos SQLAlchemy.

`ListaEspera` modela la entrada por (paciente, prestación) del tenant y `Oferta`
la cadena de ofertas sobre un hueco liberado (`hueco_turno_id`). Ambas tablas
están bajo RLS por tenant (fuente de verdad: migración 005).
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["ListaEspera", "Oferta"]


class ListaEspera(Base):
    """Entrada de lista de espera por paciente/prestación, scoped por tenant."""

    __tablename__ = "lista_espera"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE','OFRECIDO','CONVERTIDO','VENCIDO')",
            name="lista_espera_estado_valido",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prestaciones.id", ondelete="CASCADE"), nullable=False
    )
    profesional_pref: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="SET NULL"), nullable=True
    )
    ventana_desde: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ventana_hasta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Oferta(Base):
    """Oferta de un hueco liberado a una entrada; single-use por token uuid."""

    __tablename__ = "ofertas"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE','ACEPTADA','VENCIDA','CANCELADA')",
            name="ofertas_estado_valido",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lista_espera_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("lista_espera.id", ondelete="CASCADE"), nullable=False
    )
    hueco_turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="SET NULL"), nullable=True
    )
    expira_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    token: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, default=uuid.uuid4)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
