"""C-13 WhatsApp — modelo SQLAlchemy de mensajes."""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

__all__ = ["MensajeWA"]

_PLANTILLAS = "plantilla IN ('RECORDATORIO','CONFIRMACION','CANCELACION','RECALL')"
_CANALES = "canal IN ('WA','EMAIL')"
_ESTADOS = "estado IN ('PENDIENTE','ENVIADO','ENTREGADO','LEIDO','FALLIDO')"


class MensajeWA(Base):
    __tablename__ = "mensajes_wa"
    __table_args__ = (
        CheckConstraint(_PLANTILLAS, name="mensajes_wa_plantilla_valida"),
        CheckConstraint(_CANALES, name="mensajes_wa_canal_valido"),
        CheckConstraint(_ESTADOS, name="mensajes_wa_estado_valido"),
        CheckConstraint("intentos >= 0", name="mensajes_wa_intentos_no_negativos"),
        Index(
            "mensajes_wa_provider_message_id_unique",
            "provider_message_id",
            unique=True,
            postgresql_where=text("provider_message_id IS NOT NULL"),
        ),
        Index("mensajes_wa_tenant_estado_idx", "tenant_id", "estado", "proximo_intento"),
        Index("mensajes_wa_tenant_turno_idx", "tenant_id", "turno_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    paciente_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("pacientes.id", ondelete="CASCADE"), nullable=False
    )
    turno_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("turnos.id", ondelete="SET NULL"), nullable=True
    )
    plantilla: Mapped[str] = mapped_column(Text, nullable=False)
    canal: Mapped[str] = mapped_column(Text, nullable=False, default="WA")
    estado: Mapped[str] = mapped_column(Text, nullable=False, default="PENDIENTE")
    provider_message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    intentos: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    proximo_intento: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cuerpo: Mapped[str] = mapped_column(Text, nullable=False)
    respuesta: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
