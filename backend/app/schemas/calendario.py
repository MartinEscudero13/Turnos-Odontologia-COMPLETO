"""Schemas Pydantic de Google Calendar — C-14 (allow-list; nunca expone `oauth_ref`)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

EstadoLinkOut = Literal["CONECTADO", "DESCONECTADO", "TOKEN_REVOCADO"]
OrigenEventoOut = Literal["SISTEMA", "EXTERNO"]
EstadoEventoOut = Literal[
    "PENDIENTE", "SINCRONIZADO", "BLOQUEADO", "CONFLICTO_SISTEMA", "CANCELADO"
]


class LinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profesional_id: str = Field(min_length=1)
    gcal_calendar_id: str = Field(min_length=1)
    oauth_ref: str = Field(min_length=1)


class LinkOut(BaseModel):
    id: str
    profesional_id: str
    gcal_calendar_id: str
    estado: EstadoLinkOut
    ultima_sync: datetime | None
    creado_en: datetime


class EventoOut(BaseModel):
    id: str
    link_id: str
    turno_id: str | None
    gcal_event_id: str | None
    origen: OrigenEventoOut
    estado: EstadoEventoOut
    inicio: datetime
    fin: datetime
    resumen: str


class PushIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turno_id: str = Field(min_length=1)
    profesional_id: str = Field(min_length=1)
    inicio: AwareDatetime
    fin: AwareDatetime
    estado: str = Field(default="PENDIENTE", min_length=1)
    resumen: str = "Turno"


class PushOut(BaseModel):
    estado: Literal["SIN_LINK", "SINCRONIZADO", "PENDIENTE"]
    evento: EventoOut | None = None


class WebhookIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    link_id: str = Field(min_length=1)
    token: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    inicio: AwareDatetime
    fin: AwareDatetime
    resumen: str = "Evento externo"


class ColaOut(BaseModel):
    procesados: int
    pendientes: int
    agotados: int
    token_revocado: bool


class ErrorOut(BaseModel):
    detalle: str
    codigo: str | None = None
