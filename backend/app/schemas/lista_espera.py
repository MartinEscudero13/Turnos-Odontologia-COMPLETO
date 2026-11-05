"""Schemas Pydantic del borde de lista de espera — C-07 (allow-list, sin PHI).

Los payloads de escritura son strict (`extra="forbid"`): `tenant_id`, `fin` u otro
campo no documentado responde 422. Las respuestas exponen exactamente las claves
del spec, sin `tenant_id` ni datos de contacto del paciente (RN-AU-02/privacidad).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class AltaListaEsperaIn(BaseModel):
    """POST /api/lista-espera (strict; ventana y preferencia opcionales)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)
    prestacion_id: str = Field(min_length=1)
    profesional_pref: str | None = None
    ventana_desde: AwareDatetime | None = None
    ventana_hasta: AwareDatetime | None = None


class EntradaListaEsperaOut(BaseModel):
    """Entrada de lista de espera (sin tenant_id ni PHI del paciente)."""

    id: str
    paciente_id: str
    prestacion_id: str
    profesional_pref: str | None = None
    ventana_desde: datetime | None = None
    ventana_hasta: datetime | None = None
    estado: str
    creado_en: datetime


class OfertaAceptadaOut(BaseModel):
    """Turno creado por aceptación de oferta (allow-list pública reducida)."""

    turno_id: str
    estado: str
    inicio: datetime
    fin: datetime
    origen: str
    prestacion: str
    sillon_id: str
