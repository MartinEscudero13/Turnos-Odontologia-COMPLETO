"""Schemas Pydantic del borde API — C-05 (validación en borde, regla dura).

Paridad con el contrato archivado: crear acepta el payload documentado;
actualizar / motivo / reprogramar son strict (extras → 422).
Todo datetime es timezone-aware (timestamptz, D3).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PositiveInt, field_validator

OrigenIn = Literal["RECEPCION", "RESERVA_ONLINE", "LISTA_ESPERA"]


class CrearTurnoIn(BaseModel):
    """POST /api/turnos (fin lo calcula el servidor; fin_cliente se valida)."""

    profesional_id: str = Field(min_length=1)
    sillon_id: str = Field(min_length=1)
    paciente_id: str = Field(min_length=1)
    prestacion_id: str = Field(min_length=1)
    duracion_min: PositiveInt
    inicio: AwareDatetime
    fin_cliente: AwareDatetime | None = None
    sobreturno: bool = False
    motivo_sobreturno: str | None = None
    origen: OrigenIn = "RECEPCION"


class ActualizarTurnoIn(BaseModel):
    """PATCH: solo pacienteId es actualizable (strict)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)


class MotivoIn(BaseModel):
    """Sobreturno explícito: motivo obligatorio no vacío (strict)."""

    model_config = ConfigDict(extra="forbid")

    motivo: str

    @field_validator("motivo")
    @classmethod
    def motivo_no_vacio(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("sobreturno exige motivo no vacío")
        return v


class ReprogramarIn(BaseModel):
    """POST /:id/reprogramar (strict)."""

    model_config = ConfigDict(extra="forbid")

    nuevo_inicio: AwareDatetime
    duracion_min: PositiveInt | None = None


class AlternativaOut(BaseModel):
    """Hueco libre en ISO UTC (persistencia timestamptz, D3)."""

    inicio: datetime
    fin: datetime


class TurnoOut(BaseModel):
    """Turno serializado (datetimes ISO con offset)."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tenant_id: str
    profesional_id: str
    sillon_id: str
    paciente_id: str
    prestacion_id: str
    inicio: datetime
    fin: datetime
    estado: str
    sobreturno: bool
    motivo_sobreturno: str | None = None
    origen: str


class ErrorOut(BaseModel):
    """Body de error del dominio (409 trae alternativas, RN-GL-02)."""

    detalle: str
    alternativas: list[AlternativaOut] = []
