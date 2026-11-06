"""C-08 ficha clínica — modelos SQLAlchemy.

`Ficha` es el ancla 1—1 mínima con el paciente (UNIQUE(tenant_id, paciente_id));
`Evolucion` y `Consentimiento` son append-only a nivel DB (fuente de verdad:
migración 006, `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE`). `Adjunto`
guarda una referencia opaca a almacenamiento (sin PHI). Todas las tablas están
bajo RLS por tenant.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["Adjunto", "Consentimiento", "Evolucion", "Ficha"]


class Ficha(Base):
    """Ficha clínica mínima 1—1 con el paciente, scoped por tenant."""

    __tablename__ = "fichas"
    __table_args__ = (
        UniqueConstraint("tenant_id", "paciente_id", name="fichas_tenant_paciente_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Evolucion(Base):
    """Evolución fechada/firmada append-only; corrección = nueva evolución (RN-CL-03)."""

    __tablename__ = "evoluciones"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="RESTRICT"), nullable=False
    )
    fecha: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    firma_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Adjunto(Base):
    """Adjunto Rx/foto con referencia opaca a almacenamiento (sin PHI, RN-CL-04)."""

    __tablename__ = "adjuntos"
    __table_args__ = (
        CheckConstraint("tipo IN ('RX','FOTO')", name="adjuntos_tipo_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ficha_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("fichas.id", ondelete="CASCADE"), nullable=False
    )
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    storage_ref: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Consentimiento(Base):
    """Consentimiento informado append-only; `timestamp NOT NULL` es la fuente del gate."""

    __tablename__ = "consentimientos"
    __table_args__ = (
        CheckConstraint("canal <> ''", name="consentimientos_canal_no_vacio"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    canal: Mapped[str] = mapped_column(Text, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
