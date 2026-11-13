"""Schemas Pydantic del borde de odontograma — C-09 (allow-list, sin tenant_id).

Los payloads de escritura son strict (`extra="forbid"`): `tenant_id` u otro campo
no documentado responde `422`. `pieza_fdi` y `monto` son enteros estrictos (un
string numérico o un decimal no se coerciona) y `fecha` exige offset
(`AwareDatetime`). Las respuestas exponen exactamente las claves del spec, sin
`tenant_id` ni PHI de terceros.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictInt


class DerivarIn(BaseModel):
    """Bloque `derivar` del POST /api/odontograma (derivación atómica, D3)."""

    model_config = ConfigDict(extra="forbid")

    prestacion_id: str = Field(min_length=1)
    monto: StrictInt | None = Field(default=None, ge=0)


class HallazgoIn(BaseModel):
    """POST /api/odontograma (registro simple o derivación con `derivar`)."""

    model_config = ConfigDict(extra="forbid")

    paciente_id: str = Field(min_length=1)
    pieza_fdi: StrictInt
    superficie: str | None = Field(default=None, min_length=1)
    hallazgo: str = Field(min_length=1)
    fecha: AwareDatetime
    profesional_id: str | None = None
    derivar: DerivarIn | None = None


class HallazgoOut(BaseModel):
    """Hallazgo serializado (allow-list: sin tenant_id)."""

    id: str
    paciente_id: str
    pieza_fdi: int
    superficie: str | None
    hallazgo: str
    fecha: datetime
    profesional_id: str
    resuelto: bool
    creado_en: datetime


class DerivacionOut(BaseModel):
    """Resultado de derivar: ids del hallazgo y de la línea (201 o 200 replay)."""

    hallazgo_id: str
    linea_id: str
    creada: bool
