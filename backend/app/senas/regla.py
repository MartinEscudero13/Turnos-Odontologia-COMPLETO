"""Regla efectiva de la seña — PO-01 / RN-SE-05 (C-11 §2).

`valor efectivo = prestacion.sena_modo ?? tenant_parametros['sena_modo']`, con
`SIN_SENA` como override válido. `tenant_parametros` es clave/valor (D1), así
que la regla del tenant se lee de un `Mapping`, no de columnas nuevas.

Semántica obligatoria (D1, `docs/decisiones-po.md` §PO-01):

1. `prestacion.sena_modo IS NOT NULL` gana, aunque sea `SIN_SENA`.
2. Si es `NULL`, gana la clave `sena_modo` de `tenant_parametros`.
3. Sin configuración en ningún nivel ⇒ `SIN_SENA` (nunca se cobra de más).
4. Configuración almacenada inválida (modo desconocido, `PORCENTAJE` fuera de
   1–100, `MONTO_FIJO <= 0`, valor faltante) ⇒ **fail-open a no cobrar** y
   `REGLA_SENA_INVALIDA` en el log estructurado, con `tenant_id` y
   `prestacion_id`. Un error de configuración no puede romper la reserva ni
   inventar un monto.
5. El monto se calcula sobre `precio_base` en centavos, truncando hacia abajo
   (`precio_base * valor // 100`, C11-OQ-01). Si da `0`, no se crea seña.

Sin PHI: la función sólo recibe ids, modo, valor y precio; el log no lleva
ningún dato del paciente (RN-CL-04).
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast

__all__ = [
    "CODIGO_REGLA_INVALIDA",
    "MODOS_SENA",
    "ModoSena",
    "PrestacionSena",
    "ReglaSena",
    "resolver_regla",
]

ModoSena = Literal["SIN_SENA", "PORCENTAJE", "MONTO_FIJO"]

MODOS_SENA: tuple[ModoSena, ...] = ("SIN_SENA", "PORCENTAJE", "MONTO_FIJO")

SIN_SENA: ModoSena = "SIN_SENA"
PORCENTAJE_MIN = 1
PORCENTAJE_MAX = 100
CODIGO_REGLA_INVALIDA = "REGLA_SENA_INVALIDA"

_LOGGER = logging.getLogger("app.senas.regla")


@dataclass(frozen=True)
class PrestacionSena:
    """Datos de la prestación que participan de la regla (sin PHI)."""

    id: str
    precio_base_centavos: int
    sena_modo: str | None = None
    sena_valor: int | None = None


@dataclass(frozen=True)
class ReglaSena:
    """Regla efectiva resuelta: modo, valor de la regla y monto a cobrar."""

    modo: ModoSena
    valor: int | None
    monto_centavos: int
    precio_base_centavos: int
    motivo_invalidez: str | None = None

    @property
    def exige_sena(self) -> bool:
        """`True` sólo si hay un monto positivo que cobrar."""
        return self.monto_centavos > 0

    @property
    def invalida(self) -> bool:
        return self.motivo_invalidez is not None


def resolver_regla(
    *,
    tenant_id: str,
    prestacion: PrestacionSena,
    parametros: Mapping[str, Any],
) -> ReglaSena:
    """Resuelve la regla efectiva; nunca lanza por configuración inválida."""
    modo_crudo, valor_crudo, origen = _elegir_modo(prestacion, parametros)

    if modo_crudo is None:
        # Sin configuración en ningún nivel: no se cobra (no es un error).
        return ReglaSena(
            modo=SIN_SENA,
            valor=None,
            monto_centavos=0,
            precio_base_centavos=prestacion.precio_base_centavos,
        )

    if modo_crudo not in MODOS_SENA:
        return _invalida(
            tenant_id=tenant_id,
            prestacion=prestacion,
            motivo="modo_desconocido",
            origen=origen,
        )

    modo: ModoSena = cast(ModoSena, modo_crudo)
    if modo == SIN_SENA:
        return ReglaSena(
            modo=SIN_SENA,
            valor=None,
            monto_centavos=0,
            precio_base_centavos=prestacion.precio_base_centavos,
        )

    valor = _valor_valido(modo, valor_crudo)
    if valor is None:
        motivo = "valor_faltante" if valor_crudo is None else "valor_fuera_de_rango"
        return _invalida(
            tenant_id=tenant_id,
            prestacion=prestacion,
            motivo=motivo,
            origen=origen,
        )

    monto = valor if modo == "MONTO_FIJO" else prestacion.precio_base_centavos * valor // 100
    return ReglaSena(
        modo=modo,
        valor=valor,
        monto_centavos=monto,
        precio_base_centavos=prestacion.precio_base_centavos,
    )


def _elegir_modo(
    prestacion: PrestacionSena,
    parametros: Mapping[str, Any],
) -> tuple[str | None, int | None, str]:
    """`(modo, valor, origen)`: gana el override de la prestación (D1)."""
    if prestacion.sena_modo is not None:
        return prestacion.sena_modo, prestacion.sena_valor, "prestacion"

    modo = parametros.get("sena_modo")
    if modo is None or (isinstance(modo, str) and modo.strip() == ""):
        return None, None, "sin_configuracion"
    return str(modo), _entero(parametros.get("sena_valor")), "tenant"


def _entero(valor: object) -> int | None:
    """Valor numérico entero; `bool` y strings no cuentan como configuración."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def _valor_valido(modo: ModoSena, valor: int | None) -> int | None:
    if valor is None:
        return None
    if modo == "PORCENTAJE":
        return valor if PORCENTAJE_MIN <= valor <= PORCENTAJE_MAX else None
    return valor if valor > 0 else None


def _invalida(
    *,
    tenant_id: str,
    prestacion: PrestacionSena,
    motivo: str,
    origen: str,
) -> ReglaSena:
    """Fail-open: se trata como `SIN_SENA` y se avisa sin datos del paciente."""
    _LOGGER.warning(
        "%s tenant_id=%s prestacion_id=%s origen=%s motivo=%s",
        CODIGO_REGLA_INVALIDA,
        tenant_id,
        prestacion.id,
        origen,
        motivo,
        extra={
            "codigo": CODIGO_REGLA_INVALIDA,
            "tenant_id": tenant_id,
            "prestacion_id": prestacion.id,
            "origen": origen,
            "motivo": motivo,
        },
    )
    return ReglaSena(
        modo=SIN_SENA,
        valor=None,
        monto_centavos=0,
        precio_base_centavos=prestacion.precio_base_centavos,
        motivo_invalidez=motivo,
    )
