"""Schemas Pydantic del borde público — C-06 (allow-list, sin TurnoOut).

Regla dura D8: nunca se serializa `TurnoOut` (que incluye `tenant_id` y
`paciente_id`). Cada respuesta expone exactamente las claves del spec; el payload
de reserva es strict (extras → 422) y el servidor deriva `fin` y elige el sillón.
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

AccionIn = Literal["reservar", "cancelar", "reprogramar"]


class PrestacionPublicaOut(BaseModel):
    """Prestación del catálogo público (allow-list: sin tenant_id ni precio_base)."""

    id: str
    nombre: str
    duracion_min: int


class ProfesionalPublicoOut(BaseModel):
    """Profesional activo del catálogo público (sin tenant_id ni datos de contacto)."""

    id: str
    nombre: str


class CatalogoPublicoOut(BaseModel):
    """GET /catalogo: solo prestaciones y profesionales del tenant."""

    prestaciones: list[PrestacionPublicaOut]
    profesionales: list[ProfesionalPublicoOut]


class DisponibilidadOut(BaseModel):
    """Hueco libre (claves exactas: sin pacientes ni PHI)."""

    inicio: datetime
    fin: datetime
    profesional_id: str
    sillon_id: str


class ReservaIn(BaseModel):
    """POST /reservas: sólo estos campos; `fin`/`sobreturno`/`tenant_id` → 422."""

    model_config = ConfigDict(extra="forbid")

    prestacion: str = Field(min_length=1)
    profesional: str = Field(min_length=1)
    inicio: AwareDatetime
    nombre: str = Field(min_length=1, max_length=160)
    telefono: str = Field(min_length=8, max_length=20)
    verificacion_id: str = Field(min_length=1)


class ReservaOut(BaseModel):
    """Turno propio devuelto por el 201 (sin tenant_id ni paciente_id)."""

    turno_id: str
    estado: str
    inicio: datetime
    fin: datetime
    origen: str
    prestacion: str
    sillon_id: str
    token_publico: str


class ReservaConsultaOut(BaseModel):
    """Consulta del turno propio por token (allow-list reducida)."""

    turno_id: str
    estado: str
    inicio: datetime
    fin: datetime
    prestacion: str
    token_publico: str


class VerificacionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accion: AccionIn


class VerificacionOut(BaseModel):
    verificacion_id: str
    expira_at: datetime
    canal: str


class CancelarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verificacion_id: str = Field(min_length=1)


class ReprogramarIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nuevo_inicio: AwareDatetime
    verificacion_id: str = Field(min_length=1)


class AlternativaPublicaOut(BaseModel):
    inicio: datetime
    fin: datetime


class ErrorPublicoOut(BaseModel):
    """Body de error del dominio público (409 trae hasta 3 alternativas)."""

    detalle: str
    alternativas: list[AlternativaPublicaOut] = []
