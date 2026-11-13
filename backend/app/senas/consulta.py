"""Consulta interna de señas — C-11 §11 (D13, C11-OQ-10).

La seña se ve en la agenda por un endpoint **propio** (`GET /api/senas`), sin
tocar el payload de `GET /api/turnos` de C-05. Este módulo es la única puerta de
lectura: resuelve el tenant **desde el actor** (nunca desde un parámetro), exige
un rol interno y arma la vista con la política visible y la obligación de
devolución cuando corresponde.

Reglas que se aplican acá:

- identidad de paciente en una ruta interna ⇒ `401` (`NoAutenticado`), nunca
  `403`: v1 no tiene sesión de paciente (DD-06/DD-07, D13);
- un rol interno sin permiso ⇒ `403` (`Prohibido`); `ODONTOLOGO` sólo lee;
- el rango se aplica sobre **`turno.inicio`** en `[desde, hasta)`; sin
  parámetros, el rango por defecto es el día operativo vigente en `-03:00`;
- cross-tenant y seña inexistente comparten el mismo `404` (`NoEncontrado`),
  sin revelar la existencia ni devolver un solo dato de la seña ajena;
- sin PHI: la vista lleva ids, estado, monto, instantes, política y
  obligaciones; nunca nombre, teléfono, DNI ni `paciente_id`.

La obligación de devolución (RN-SE-04) es explícita para que ninguna plata
quede invisible: una seña `DEVUELTA` por política o por `ADMIN` registra un
reintegro pendiente, y los pagos con `MONTO_DISTINTO`, `PAGO_EXCEDENTE` o
`REEMBOLSO_AJUSTE_CAJA` dejan su propia obligación (`C11-OQ-09`, D12).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal

from app.caja.servicio import TZ_OPERATIVA, dia_operativo
from app.senas.puertos import (
    PagoMP,
    PagoMPRepositorio,
    PoliticaSena,
    Reloj,
    Sena,
    SenaRepositorio,
)
from app.turnos.servicio import (
    Actor,
    Invalido,
    NoAutenticado,
    NoEncontrado,
    Prohibido,
)

__all__ = [
    "Obligacion",
    "ServicioSenasConsulta",
    "SenaInterna",
]

_ROLES_LECTURA: frozenset[str] = frozenset({"ODONTOLOGO", "RECEPCION", "ADMIN"})

OrigenObligacion = Literal["SENA", "PAGO"]
TipoObligacion = Literal["REINTEGRO", "AJUSTE_CAJA"]

# Resultados del pago que dejan plata retenida y por lo tanto una obligación
# visible en la cola de `GET /api/senas` (D3, F-11, F-18).
_OBLIGACION_POR_RESULTADO: dict[str, tuple[OrigenObligacion, TipoObligacion]] = {
    "MONTO_DISTINTO": ("PAGO", "REINTEGRO"),
    "PAGO_EXCEDENTE": ("PAGO", "REINTEGRO"),
    "REEMBOLSO_AJUSTE_CAJA": ("PAGO", "AJUSTE_CAJA"),
}

# `REEMBOLSO_MP` cierra la obligación por la API de Mercado Pago (D12).
_MOTIVO_OBLIGACION_CERRADA = "REEMBOLSO_MP"


@dataclass(frozen=True)
class Obligacion:
    """Obligación de devolución o ajuste que la operación no puede perder."""

    origen: OrigenObligacion
    tipo: TipoObligacion
    monto_centavos: int
    motivo: str | None = None
    mp_payment_id: str | None = None


@dataclass(frozen=True)
class SenaInterna:
    """Vista interna de una seña: sin PHI y con su política y obligaciones."""

    sena: Sena
    politica: PoliticaSena
    obligaciones: tuple[Obligacion, ...]


class ServicioSenasConsulta:
    """Lectura interna de señas, scoped por el tenant del actor."""

    def __init__(
        self,
        senas: SenaRepositorio,
        pagos: PagoMPRepositorio,
        *,
        reloj: Reloj | None = None,
    ) -> None:
        self._senas = senas
        self._pagos = pagos
        self._reloj = reloj

    # -- lectura --------------------------------------------------------

    def listar(
        self,
        *,
        actor: Actor,
        desde: date | None = None,
        hasta: date | None = None,
        ahora: datetime | None = None,
    ) -> list[SenaInterna]:
        """Señas del tenant con `turno.inicio` en `[desde, hasta)` (C11-OQ-10)."""
        tenant_id = self._tenant_lectura(actor)
        inicio, fin = self._ventana(desde=desde, hasta=hasta, ahora=ahora)
        senas = [
            sena
            for sena in self._senas.listar(
                tenant_id=tenant_id, desde=inicio, hasta=fin
            )
            if sena.tenant_id == tenant_id
        ]
        pagos = self._pagos.listar(tenant_id=tenant_id)
        return [self._vista(sena, pagos) for sena in senas]

    def obtener(
        self,
        *,
        actor: Actor,
        sena_id: str,
        ahora: datetime | None = None,
    ) -> SenaInterna:
        """Detalle por id; una seña de otro tenant responde el mismo `404`."""
        del ahora  # la vista interna no depende del reloj
        tenant_id = self._tenant_lectura(actor)
        sena = self._senas.obtener(tenant_id=tenant_id, sena_id=sena_id)
        if sena is None:
            raise NoEncontrado("seña no encontrada")
        pagos = self._pagos.listar(tenant_id=tenant_id, sena_id=sena.id)
        return self._vista(sena, pagos)

    # -- RBAC -----------------------------------------------------------

    @staticmethod
    def _tenant_lectura(actor: Actor) -> str:
        if actor.rol == "PACIENTE":
            # v1 no tiene sesión de paciente en rutas internas (DD-06/DD-07).
            raise NoAutenticado("la seña requiere una sesión interna")
        if actor.rol not in _ROLES_LECTURA:
            raise Prohibido("el rol no puede leer señas")
        return actor.tenant_id

    # -- ventana --------------------------------------------------------

    def _ventana(
        self,
        *,
        desde: date | None,
        hasta: date | None,
        ahora: datetime | None,
    ) -> tuple[datetime, datetime]:
        """Rango `[desde, hasta)` sobre `turno.inicio`; default = día operativo."""
        if desde is None and hasta is None:
            dia = dia_operativo(self._momento(ahora))
            inicio, fin = dia, dia + timedelta(days=1)
        elif desde is None:
            assert hasta is not None  # acotado por la condición anterior
            inicio, fin = hasta - timedelta(days=1), hasta
        elif hasta is None:
            inicio, fin = desde, desde + timedelta(days=1)
        else:
            inicio, fin = desde, hasta
        if fin <= inicio:
            raise Invalido("el rango de fechas es inválido")
        return self._inicio_del_dia(inicio), self._inicio_del_dia(fin)

    @staticmethod
    def _inicio_del_dia(dia: date) -> datetime:
        return datetime.combine(dia, time.min, tzinfo=TZ_OPERATIVA)

    def _momento(self, ahora: datetime | None) -> datetime:
        if ahora is not None:
            return ahora
        if self._reloj is not None:
            return self._reloj()
        raise RuntimeError(
            "ServicioSenasConsulta requiere un reloj inyectado o `ahora`"
        )

    # -- vista ----------------------------------------------------------

    @staticmethod
    def _politica(sena: Sena) -> PoliticaSena:
        return PoliticaSena(
            anticipacion_cancelacion_h=sena.anticipacion_cancelacion_h,
            # La promesa no depende del estado (D12/F-01).
            reembolsable=True,
            hay_pago_acreditado=sena.estado == "ACREDITADA",
        )

    def _vista(self, sena: Sena, pagos: list[PagoMP]) -> SenaInterna:
        return SenaInterna(
            sena=sena,
            politica=self._politica(sena),
            obligaciones=self._obligaciones(sena, pagos),
        )

    @staticmethod
    def _obligaciones(sena: Sena, pagos: list[PagoMP]) -> tuple[Obligacion, ...]:
        obligaciones: list[Obligacion] = []
        if (
            sena.estado == "DEVUELTA"
            and sena.motivo_devolucion != _MOTIVO_OBLIGACION_CERRADA
        ):
            obligaciones.append(
                Obligacion(
                    origen="SENA",
                    tipo="REINTEGRO",
                    monto_centavos=sena.monto_centavos,
                    motivo=sena.motivo_devolucion,
                )
            )
        for pago in pagos:
            destino = _OBLIGACION_POR_RESULTADO.get(pago.resultado)
            if destino is None:
                continue
            origen, tipo = destino
            obligaciones.append(
                Obligacion(
                    origen=origen,
                    tipo=tipo,
                    monto_centavos=pago.monto_centavos,
                    motivo=pago.resultado,
                    mp_payment_id=pago.mp_payment_id,
                )
            )
        return tuple(obligaciones)
