"""Schemas Pydantic del borde de ficha clínica — C-08 (allow-list, sin tenant_id).

Los payloads de escritura son strict (`extra="forbid"`): `tenant_id` u otro campo
no documentado responde 422. Las respuestas exponen exactamente las claves del
spec (id, ids de relación, fecha, texto, …) sin `tenant_id` ni PHI de terceros.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class FichaOut(BaseModel):
    """Ficha 1—1 serializada (sin tenant_id)."""

    id: str
    paciente_id: str
    creado_en: datetime


class EvolucionIn(BaseModel):
    """POST /api/evoluciones (strict)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)
    profesional_id: str = Field(min_length=1)
    fecha: AwareDatetime
    texto: str = Field(min_length=1)
    firma_hash: str | None = None


class EvolucionOut(BaseModel):
    """Evolución serializada (allow-list: sin tenant_id ni datos ajenos)."""

    id: str
    paciente_id: str
    profesional_id: str
    fecha: datetime
    texto: str
    firma_hash: str | None = None
    creado_en: datetime


class AdjuntoIn(BaseModel):
    """POST /api/adjuntos (strict; tipo enum RX/FOTO)."""

    model_config = ConfigDict(extra="forbid")

    ficha_id: str = Field(min_length=1)
    tipo: Literal["RX", "FOTO"]
    storage_ref: str = Field(min_length=1)


class AdjuntoOut(BaseModel):
    """Adjunto serializado (referencia opaca, sin PHI)."""

    id: str
    ficha_id: str
    tipo: str
    storage_ref: str
    creado_en: datetime


class ConsentimientoIn(BaseModel):
    """POST /api/consentimientos (strict; timestamp aware obligatorio)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)
    timestamp: AwareDatetime
    canal: str = Field(min_length=1)


class ConsentimientoOut(BaseModel):
    """Consentimiento serializado (sin tenant_id)."""

    id: str
    paciente_id: str
    timestamp: datetime
    canal: str
    creado_en: datetime
