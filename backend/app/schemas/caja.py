"""Schemas Pydantic del borde de caja — C-10 (§9, allow-list estricta).

Los payloads son `strict` (`extra="forbid"`) y `monto` es un entero estricto:
`1000.5` y `"1000"` son `422`. `fecha` es un día operativo (`date`) en las
entradas y en las consultas, nunca un instante. Las salidas no incluyen
`tenant_id` ni datos personales: sólo ids, fechas, medios y montos (RN-CL-04).

`totales_vigentes` usa las claves de respuesta `efectivo`, `transferencia`, `mp`
y `os`; `totales_cierre` devuelve los nombres persistidos (`total_efectivo`, …)
tal como fija el design (D3).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator

MedioOut = Literal["EFECTIVO", "TRANSFERENCIA", "MP", "OS"]
TipoOut = Literal["INGRESO", "EGRESO"]
OrigenOut = Literal["MANUAL", "IMPUTACION", "COMPENSACION"]
TramoOut = Literal["PACIENTE", "OS"]
TipoAjusteOut = Literal["AJUSTE_ANULACION", "COBRO_PENDIENTE"]
EstadoDiaOut = Literal["abierto", "cerrado"]


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


class AnulacionEntrada(BaseModel):
    """POST /api/caja/movimientos/{id}/anular (motivo obligatorio, RN-CJ-03)."""

    model_config = ConfigDict(extra="forbid")

    motivo: str


class CobroEntrada(BaseModel):
    """POST /api/caja/pendientes/{id}/cobrar (el medio completa el pendiente)."""

    model_config = ConfigDict(extra="forbid")

    medio: MedioOut


class CierreEntrada(BaseModel):
    """POST /api/caja/cierre (el cliente sólo envía lo contado, D4).

    Los totales por medio y el devengado OS se calculan en el servidor; el
    responsable es obligatorio y debe pertenecer al tenant. `fecha` es el día
    operativo a cerrar (necesario para el cierre atrasado de C10-OQ-3); sin
    `fecha` se cierra el día del reloj del servidor.
    """

    model_config = ConfigDict(extra="forbid")

    efectivo_contado: StrictInt
    responsable_id: str
    motivo_diferencia: str | None = None
    observacion: str | None = None
    fecha: date | None = None

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
    tramo: TramoOut | None
    turno_id: str | None
    usuario_id: str
    anulado: bool
    motivo_anulacion: str | None
    anulado_por: str | None
    anulado_en: datetime | None
    origen: OrigenOut
    creado_en: datetime


class PendienteSalida(BaseModel):
    """Cobro pendiente serializado (sin `paciente_id`, sin PHI)."""

    id: str
    fecha: date
    presupuesto_id: str
    linea_id: str
    monto_centavos: int
    actor_id: str
    turno_id: str | None
    creado_en: datetime
    resuelto_en: datetime | None
    movimiento_id: str | None


class AjusteSalida(BaseModel):
    """Ajuste post-cierre serializado (ledger, sin PHI, D1/D11)."""

    id: str
    cierre_id: str
    tipo: TipoAjusteOut
    movimiento_original_id: str | None
    cobro_pendiente_id: str | None
    monto: int
    medio: MedioOut
    motivo: str | None
    actor_id: str
    compensatorio_id: str
    creado_en: datetime


class CobroSalida(BaseModel):
    """Resultado del cobro: pendiente resuelto, movimiento creado y ajuste."""

    pendiente: PendienteSalida
    movimiento: MovimientoSalida
    ajuste: AjusteSalida | None


class TotalesVigentesSalida(BaseModel):
    """Totales netos del día sobre movimientos vigentes (claves de respuesta)."""

    efectivo: int
    transferencia: int
    mp: int
    os: int


class TotalesCierreSalida(BaseModel):
    """Totales persistidos del snapshot de cierre (nombres de la tabla)."""

    total_efectivo: int
    total_transferencia: int
    total_mp: int
    total_os_cobrado: int
    total_os: int


class CierreSalida(BaseModel):
    """Cierre serializado (inmutable; sin `tenant_id`)."""

    id: str
    fecha: date
    totales: TotalesCierreSalida
    efectivo_contado: int
    diferencia: int
    responsable_id: str
    motivo_diferencia: str | None
    observacion: str | None
    cerrado_at: datetime


class EstadoDiaSalida(BaseModel):
    """Estado `abierto`/`cerrado` del día con totales vigentes y su cierre."""

    fecha: date
    estado: EstadoDiaOut
    totales: TotalesVigentesSalida
    cierre: CierreSalida | None


class ConsultaDiaSalida(BaseModel):
    """Consulta diaria: movimientos, pendientes, ajustes y ambas cifras (H6)."""

    fecha: date
    estado: EstadoDiaOut
    movimientos: list[MovimientoSalida]
    pendientes: list[PendienteSalida]
    ajustes: list[AjusteSalida]
    totales_vigentes: TotalesVigentesSalida
    totales_cierre: TotalesCierreSalida | None
    difieren_del_cierre: bool


class DiaReporteSalida(BaseModel):
    """Facturación neta de un día del período."""

    fecha: date
    efectivo: int
    transferencia: int
    mp: int
    os: int
    movimientos: int
    anulados: int


class ReporteSalida(BaseModel):
    """Reporte base de caja por rango (fuente declarada, sin datos personales)."""

    desde: date
    hasta: date
    fuente: Literal["movimientos_vigentes"]
    totales: TotalesVigentesSalida
    por_dia: list[DiaReporteSalida]
    cierres: int
    movimientos_anulados: int


class ErrorCajaOut(BaseModel):
    """Body de error de caja: mensaje de dominio y código cuando lo tiene."""

    detalle: str
    codigo: str | None = None
