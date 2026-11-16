"""Schemas Pydantic del borde WhatsApp — C-13."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PlantillaOut = Literal["RECORDATORIO", "CONFIRMACION", "CANCELACION", "RECALL"]
CanalOut = Literal["WA", "EMAIL"]
EstadoMensajeOut = Literal["PENDIENTE", "ENVIADO", "ENTREGADO", "LEIDO", "FALLIDO"]


class MensajeOut(BaseModel):
    id: str
    paciente_id: str
    turno_id: str | None
    plantilla: PlantillaOut
    canal: CanalOut
    estado: EstadoMensajeOut
    provider_message_id: str | None
    intentos: int
    proximo_intento: datetime
    cuerpo: str
    respuesta: str | None
    creado_en: datetime


class EnvioOut(BaseModel):
    enviados: int
    fallidos: int
    mensajes: list[MensajeOut] = Field(default_factory=list)


class RecallIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)
    motivo: str = Field(min_length=1)
    fecha_objetivo: date


class WebhookOut(BaseModel):
    estado: EstadoMensajeOut | None = None
    respuesta: str | None = None
    turno_id: str | None = None
    link_confirmacion: str | None = None


class ErrorOut(BaseModel):
    detalle: str
    codigo: str | None = None
