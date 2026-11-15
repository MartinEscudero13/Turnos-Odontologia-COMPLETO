"""C-14 Google Calendar — modelos SQLAlchemy (link, eventos y cola de envíos)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["CalendarEnvio", "CalendarEvento", "CalendarLink"]

_ESTADOS_LINK = "estado IN ('CONECTADO','DESCONECTADO','TOKEN_REVOCADO')"
_ESTADOS_EVENTO = (
    "estado IN ('PENDIENTE','SINCRONIZADO','BLOQUEADO','CONFLICTO_SISTEMA','CANCELADO')"
)
_ORIGENES = "origen IN ('SISTEMA','EXTERNO')"
_ACCIONES = "accion IN ('PUSH','DELETE')"
_ESTADOS_ENVIO = "estado IN ('PENDIENTE','PROCESADO','AGOTADO')"


class CalendarLink(Base):
    """Vínculo OAuth por profesional; guarda una referencia, nunca el token."""

    __tablename__ = "calendar_links"
    __table_args__ = (
        UniqueConstraint("tenant_id", "profesional_id", name="calendar_links_tenant_prof_unique"),
        CheckConstraint(_ESTADOS_LINK, name="calendar_links_estado_valido"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    profesional_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("profesionales.id", ondelete="CASCADE"), nullable=False
    )
    gcal_calendar_id: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_ref: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="CONECTADO")
    ultima_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CalendarEvento(Base):
    """Mapeo turno↔evento o bloqueo externo informativo."""

    __tablename__ = "calendar_eventos"
    __table_args__ = (
        CheckConstraint(_ORIGENES, name="calendar_eventos_origen_valido"),
        CheckConstraint(_ESTADOS_EVENTO, name="calendar_eventos_estado_valido"),
        Index(
            "calendar_eventos_tenant_link_gcal_unique",
            "tenant_id",
            "link_id",
            "gcal_event_id",
            unique=True,
            postgresql_where=text("gcal_event_id IS NOT NULL"),
        ),
        Index("calendar_eventos_tenant_link_turno_idx", "tenant_id", "link_id", "turno_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calendar_links.id", ondelete="CASCADE"), nullable=False
    )
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="SET NULL"), nullable=True
    )
    gcal_event_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    origen: Mapped[str] = mapped_column(Text, nullable=False, default="SISTEMA")
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fin: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    resumen: Mapped[str] = mapped_column(Text, nullable=False, default="Turno")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CalendarEnvio(Base):
    """Cola de reintentos con backoff (RN-IN-03)."""

    __tablename__ = "calendar_envios"
    __table_args__ = (
        CheckConstraint(_ACCIONES, name="calendar_envios_accion_valida"),
        CheckConstraint(_ESTADOS_ENVIO, name="calendar_envios_estado_valido"),
        CheckConstraint("intentos >= 0", name="calendar_envios_intentos_no_negativos"),
        Index("calendar_envios_tenant_estado_idx", "tenant_id", "estado", "proximo_intento"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    link_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calendar_links.id", ondelete="CASCADE"), nullable=False
    )
    evento_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("calendar_eventos.id", ondelete="SET NULL"), nullable=True
    )
    accion: Mapped[str] = mapped_column(Text, nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proximo_intento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
