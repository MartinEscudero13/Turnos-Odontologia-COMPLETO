"""C-04 catálogos base: profesionales, sillones, prestaciones, horarios y pacientes."""
import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Sillon(Base):
    __tablename__ = "sillones"
    __table_args__ = (UniqueConstraint("tenant_id", "nombre", name="sillones_tenant_nombre_unique"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Prestacion(Base):
    __tablename__ = "prestaciones"
    __table_args__ = (
        UniqueConstraint("tenant_id", "nombre", name="prestaciones_tenant_nombre_unique"),
        CheckConstraint("duracion_min > 0", name="prestaciones_duracion_positiva"),
        CheckConstraint("precio_base >= 0", name="prestaciones_precio_no_negativo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    duracion_min: Mapped[int] = mapped_column(Integer, nullable=False)
    precio_base: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requiere_sena: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    monto_sena: Mapped[int] = mapped_column(Integer, nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Profesional(Base):
    __tablename__ = "profesionales"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    especialidad: Mapped[str] = mapped_column(Text, nullable=False)
    matricula: Mapped[str] = mapped_column(Text, nullable=True)
    color_agenda: Mapped[str] = mapped_column(Text, nullable=False, default="#3b82f6")
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProfesionalPrestacion(Base):
    __tablename__ = "profesional_prestacion"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="CASCADE"), primary_key=True
    )
    prestacion_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("prestaciones.id", ondelete="CASCADE"), primary_key=True
    )


class HorarioSemanal(Base):
    __tablename__ = "horarios_semanales"
    __table_args__ = (
        CheckConstraint("dia BETWEEN 1 AND 7", name="horarios_dia_valido"),
        CheckConstraint("hasta > desde", name="horarios_rango_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="CASCADE"), nullable=False
    )
    dia: Mapped[int] = mapped_column(Integer, nullable=False)
    desde: Mapped[time] = mapped_column(Time, nullable=False)
    hasta: Mapped[time] = mapped_column(Time, nullable=False)


class Bloqueo(Base):
    __tablename__ = "bloqueos"
    __table_args__ = (
        CheckConstraint("hasta > desde", name="bloqueos_rango_valido"),
        CheckConstraint(
            "profesional_id IS NOT NULL OR sillon_id IS NOT NULL",
            name="bloqueos_destino_requerido",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="CASCADE"), nullable=True
    )
    sillon_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sillones.id", ondelete="CASCADE"), nullable=True
    )
    desde: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hasta: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    motivo: Mapped[str] = mapped_column(Text, nullable=False)


class Paciente(Base):
    __tablename__ = "pacientes"
    __table_args__ = (
        UniqueConstraint("tenant_id", "telefono", name="pacientes_tenant_telefono_unique"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    dni_cifrado: Mapped[str] = mapped_column(Text, nullable=True)
    telefono: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=True)
    obra_social_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=True)
    nro_afiliado: Mapped[str] = mapped_column(Text, nullable=True)
    consentimiento_ok: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
