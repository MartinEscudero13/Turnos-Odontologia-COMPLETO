"""Schemas Pydantic del borde de caja — C-10 §2 (allow-list estricta).

Los payloads son `strict` (`extra="forbid"`) y `monto` es un entero estricto:
`1000.5` y `"1000"` son `422`. `fecha` es un día operativo (`date`), nunca un
instante. La salida no incluye `tenant_id` ni datos personales. El resto de los
schemas (anulación, cierre, pendientes, reportes) llega en §9.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

MedioOut = Literal["EFECTIVO", "TRANSFERENCIA", "MP", "OS"]
TipoOut = Literal["INGRESO", "EGRESO"]
OrigenOut = Literal["MANUAL", "IMPUTACION", "COMPENSACION"]


class MovimientoEntrada(BaseModel):
    """POST /api/caja/movimientos (sin `fecha` usa el reloj del servidor)."""

    model_config = ConfigDict(extra="forbid")

    monto: StrictInt = Field(gt=0)
    medio: MedioOut
    tipo: TipoOut = "INGRESO"
    fecha: date | None = None
    turno_id: str | None = None

    @field_validator("fecha", mode="before")
    @classmethod
    def _fecha_operativa(cls, valor: object) -> object:
        """La fecha es un día operativo `YYYY-MM-DD`, nunca un instante."""
        if isinstance(valor, str):
            try:
                return date.fromisoformat(valor)
            except ValueError:
                raise ValueError(
                    "fecha inválida: la fecha operativa es YYYY-MM-DD"
                ) from None
        return valor


class MovimientoSalida(BaseModel):
    """Movimiento serializado (sin `tenant_id`, sin PHI)."""

    id: str
    fecha: date
    medio: MedioOut
    monto: int
    tipo: TipoOut
    tramo: Literal["PACIENTE", "OS"] | None
    turno_id: str | None
    usuario_id: str
    anulado: bool
    motivo_anulacion: str | None
    anulado_por: str | None
    anulado_en: datetime | None
    origen: OrigenOut
    creado_en: datetime
