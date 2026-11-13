"""Aplicación al cobro y devolución de la seña — C-11 §9–§10 (RN-SE-04).

**Aplicación (D9, C10-OQ-6).** La plata de una seña `ACREDITADA` es caja: el
`INGRESO` lo crea C-11 **a través del alta de C-10**
(`ServicioCaja.registrar_movimiento`), nunca escribiendo `movimientos_caja`. El
adaptador vive en `app/senas/adaptadores.py` y comparte la transacción de la
seña (`TransaccionSQL` es anidable, C-10 §5).

Orden de la operación (no negociable):

1. Actor interno y rol (`RECEPCION`/`ADMIN`); `CANCELACION_TARDIA` sólo `ADMIN`
   (`F-29`). Un paciente en una ruta interna es `401`, no `403`.
2. `SELECT … FOR UPDATE` sobre la seña y guard `estado='ACREDITADA'`.
3. Guard de presupuesto aceptado vigente de C-09 (`C11-OQ-13`): `409
   PRESUPUESTO_CON_SENA` sin movimiento (el descuento automático no existe en
   v1 y aplicar cobraría dos veces el mismo tramo).
4. Alta del `INGRESO MP` con **`fecha` = día operativo de la aplicación** en
   `-03:00` (`F-13`), con `turno_id` de la seña. C-10 toma el advisory lock del
   día y rechaza `409 CIERRE_CERRADO`; C-11 no reimplementa nada de eso.
5. Seña `APLICADA` con `aplicada_en`, `movimiento_caja_id` y
   `concepto_aplicacion`, en la **misma transacción** que el movimiento.

Orden de locks: **siempre seña → día**. Ningún camino toma el día antes de la
seña, así que no hay ciclo con las altas manuales de caja (que sólo toman el
día).

**Devolución (D12, C11-OQ-09).** `DEVUELTA` es un estado **contable**: registra
la obligación de reintegro y **no** llama a la API de reembolsos de Mercado Pago.
Sólo `ADMIN` devuelve, con motivo no vacío; una seña `APLICADA` no se devuelve
(después del cobro la corrección es una anulación de C-10). La devolución
automática por política de cancelación se ejecuta sin actor (`devuelta_por`
nulo), porque la ordena la promesa visible al reservar y no una persona.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.caja.servicio import dia_operativo
from app.core.logging import get_logger
from app.senas.puertos import (
    AccionSena,
    AplicacionCajaPort,
    AuditoriaPort,
    ConceptoAplicacion,
    PresupuestosPort,
    Reloj,
    Sena,
    SenaInvalida,
    SenaRepositorio,
    TransaccionNula,
    TurnoPort,
    UnidadDeTrabajoPort,
)
from app.senas.servicio import (
    CODIGO_ESTADO_INVALIDO,
    ConflictoSena,
)
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

__all__ = [
    "CODIGO_PRESUPUESTO_CON_SENA",
    "CODIGO_SENA_NO_DEVOLUBLE",
    "CODIGO_SENA_YA_APLICADA",
    "ServicioSenasAplicacion",
]

logger = get_logger("app.senas.aplicacion")

CODIGO_SENA_YA_APLICADA = "SENA_YA_APLICADA"
CODIGO_SENA_NO_DEVOLUBLE = "SENA_NO_DEVOLUBLE"
CODIGO_PRESUPUESTO_CON_SENA = "PRESUPUESTO_CON_SENA"

_APLICA: frozenset[str] = frozenset({"RECEPCION", "ADMIN"})
_DEVUELVE: frozenset[str] = frozenset({"ADMIN"})


class ServicioSenasAplicacion:
    """Aplicación al cobro de C-10 y devolución explícita de la seña."""

    def __init__(
        self,
        senas: SenaRepositorio,
        turnos: TurnoPort,
        caja: AplicacionCajaPort,
        presupuestos: PresupuestosPort,
        auditoria: AuditoriaPort,
        *,
        reloj: Reloj | None = None,
        uow_factory: Callable[[], UnidadDeTrabajoPort] | None = None,
    ) -> None:
        self._senas = senas
        self._turnos = turnos
        self._caja = caja
        self._presupuestos = presupuestos
        self._auditoria = auditoria
        self._reloj = reloj
        self._uow_factory: Callable[[], UnidadDeTrabajoPort] = (
            uow_factory if uow_factory is not None else TransaccionNula
        )

    # ------------------------------------------------------------------
    # §9 — aplicar al cobro
    # ------------------------------------------------------------------

    def aplicar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        actor: Actor,
        concepto: ConceptoAplicacion = "TRATAMIENTO",
        ahora: datetime | None = None,
    ) -> Sena:
        """Crea el `INGRESO MP` del turno y deja la seña `APLICADA`."""
        self._exigir_aplicacion(actor, concepto=concepto)
        momento = self._momento(ahora)
        fecha = dia_operativo(momento)

        with self._uow_factory():
            sena = self._bloquear(tenant_id=tenant_id, sena_id=sena_id)
            self._exigir_acreditada(sena)
            self._exigir_sin_presupuesto(sena=sena, momento=momento)

            movimiento = self._caja.registrar_ingreso_mp(
                tenant_id=tenant_id,
                turno_id=sena.turno_id,
                monto_centavos=sena.monto_centavos,
                fecha=fecha,
                actor_id=actor.user_id,
                concepto=concepto,
            )
            aplicada = self._senas.transicionar(
                tenant_id=tenant_id,
                sena_id=sena.id,
                desde="ACREDITADA",
                hacia="APLICADA",
                campos={
                    "aplicada_en": momento,
                    "movimiento_caja_id": movimiento.id,
                    "concepto_aplicacion": concepto,
                },
            )
            if aplicada is None:
                # Otra transacción aplicó primero (D11): no se crea otro ingreso.
                raise ConflictoSena(
                    CODIGO_SENA_YA_APLICADA, "la seña ya fue aplicada"
                )
            self._auditar(
                sena=aplicada,
                accion="SENA_APLICADA",
                actor=actor.user_id,
                antes={"estado": "ACREDITADA"},
                despues={
                    "estado": "APLICADA",
                    "movimiento_caja_id": movimiento.id,
                    "monto_centavos": aplicada.monto_centavos,
                    "concepto_aplicacion": concepto,
                    "fecha": fecha.isoformat(),
                },
            )

        logger.info(
            "sena_aplicada tenant_id=%s sena_id=%s movimiento_id=%s monto=%s fecha=%s",
            tenant_id,
            aplicada.id,
            movimiento.id,
            aplicada.monto_centavos,
            fecha.isoformat(),
        )
        return aplicada

    # ------------------------------------------------------------------
    # §10 — devolver
    # ------------------------------------------------------------------

    def devolver(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        actor: Actor,
        motivo: str,
        ahora: datetime | None = None,
    ) -> Sena:
        """Devolución manual: obligación de reintegro, sin API de reembolsos."""
        self._exigir_rol(actor=actor, permitidos=_DEVUELVE)
        motivo_validado = _validar_motivo(motivo)
        momento = self._momento(ahora)

        with self._uow_factory():
            sena = self._bloquear(tenant_id=tenant_id, sena_id=sena_id)
            self._exigir_devoluble(sena)
            devuelta = self._senas.transicionar(
                tenant_id=tenant_id,
                sena_id=sena.id,
                desde="ACREDITADA",
                hacia="DEVUELTA",
                campos={
                    "devuelta_en": momento,
                    "motivo_devolucion": motivo_validado,
                    "devuelta_por": actor.user_id,
                },
            )
            if devuelta is None:
                raise ConflictoSena(
                    CODIGO_SENA_NO_DEVOLUBLE, "la seña ya no es devolvible"
                )
            self._auditar(
                sena=devuelta,
                accion="SENA_DEVUELTA",
                actor=actor.user_id,
                antes={"estado": "ACREDITADA"},
                despues={
                    "estado": "DEVUELTA",
                    "motivo_devolucion": motivo_validado,
                    "devuelta_por": actor.user_id,
                },
            )

        logger.info(
            "sena_devuelta tenant_id=%s sena_id=%s actor=%s motivo=%s",
            tenant_id,
            devuelta.id,
            actor.user_id,
            motivo_validado,
        )
        return devuelta

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    def _exigir_aplicacion(self, actor: Actor, *, concepto: ConceptoAplicacion) -> None:
        if concepto not in ("TRATAMIENTO", "CANCELACION_TARDIA"):
            raise Invalido("concepto de aplicación inválido")
        self._exigir_rol(actor=actor, permitidos=_APLICA)
        if concepto == "CANCELACION_TARDIA" and actor.rol != "ADMIN":
            # F-29: convertir una cancelación tardía en ingreso es una decisión
            # de anulación, igual que devolver.
            raise Prohibido("sólo ADMIN aplica una cancelación tardía")

    def _exigir_rol(self, *, actor: Actor, permitidos: frozenset[str]) -> None:
        if actor.rol == "PACIENTE":
            # v1 no tiene sesión de paciente en rutas internas (DD-06/DD-07).
            raise NoAutenticado("la seña requiere una sesión interna")
        if actor.rol not in permitidos:
            raise Prohibido("el rol no puede ejecutar esta acción sobre la seña")

    def _bloquear(self, *, tenant_id: str, sena_id: str) -> Sena:
        try:
            return self._senas.bloquear(tenant_id=tenant_id, sena_id=sena_id)
        except (NoEncontrado, SenaInvalida) as exc:
            raise NoEncontrado("seña no encontrada") from exc

    @staticmethod
    def _exigir_acreditada(sena: Sena) -> None:
        if sena.estado == "APLICADA":
            raise ConflictoSena(CODIGO_SENA_YA_APLICADA, "la seña ya fue aplicada")
        if sena.estado != "ACREDITADA":
            raise ConflictoSena(
                CODIGO_ESTADO_INVALIDO, f"la seña está {sena.estado}"
            )

    @staticmethod
    def _exigir_devoluble(sena: Sena) -> None:
        if sena.estado == "APLICADA":
            raise ConflictoSena(
                CODIGO_SENA_NO_DEVOLUBLE,
                "la seña aplicada se corrige con una anulación de caja",
            )
        if sena.estado != "ACREDITADA":
            raise ConflictoSena(
                CODIGO_SENA_NO_DEVOLUBLE, f"la seña está {sena.estado}"
            )

    def _exigir_sin_presupuesto(self, *, sena: Sena, momento: datetime) -> None:
        turno = self._turnos.turno_de(
            tenant_id=sena.tenant_id, turno_id=sena.turno_id
        )
        paciente_id = turno.paciente_id if turno is not None else None
        if paciente_id is None:
            return
        if self._presupuestos.aceptado_vigente(
            tenant_id=sena.tenant_id, paciente_id=paciente_id, ahora=momento
        ):
            # C11-OQ-13: sin descuento automático, aplicar cobraría dos veces.
            raise ConflictoSena(
                CODIGO_PRESUPUESTO_CON_SENA,
                "el paciente tiene un presupuesto aceptado vigente",
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _momento(self, ahora: datetime | None) -> datetime:
        if ahora is not None:
            return ahora
        if self._reloj is not None:
            return self._reloj()
        raise RuntimeError(
            "ServicioSenasAplicacion requiere un reloj inyectado o `ahora`"
        )

    def _auditar(
        self,
        *,
        sena: Sena,
        accion: AccionSena,
        actor: str,
        antes: dict[str, object] | None,
        despues: dict[str, object] | None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=sena.tenant_id,
            accion=accion,
            actor=actor,
            entidad="sena",
            entidad_id=sena.id,
            antes=antes,
            despues=despues,
        )


def _validar_motivo(motivo: object) -> str:
    """`RN-SE-04`: devolver exige un motivo no vacío (`422`)."""
    if not isinstance(motivo, str) or not motivo.strip():
        raise Invalido("motivo de devolución inválido: no puede estar vacío")
    return motivo.strip()
