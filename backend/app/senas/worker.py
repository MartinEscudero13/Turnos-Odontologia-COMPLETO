"""Expiración de la seña y liberación del turno — C-11 §7 (RN-SE-01 / RN-RE-04).

`procesar_expiraciones(tenant_id, ahora)` es un barrido **puro** (espejo de
`ServicioAutoOferta` de C-07): no lee el reloj del sistema, no duerme y exige el
tenant, así que el barrido de T1 no puede tocar las señas de T2 (F-20).

Por cada seña `PENDIENTE` del tenant con `expira_at <= ahora`:

1. `SELECT … FOR UPDATE` sobre la seña y **revalidación** del estado y del
   vencimiento dentro del lock (D11: gana la primera transacción que commitea).
2. `LIBERADA` con `liberada_en` y `motivo_liberacion='EXPIRACION'`.
3. Turno `PENDIENTE → CANCELADO` con motivo `SENA_NO_ACREDITADA`. Si el turno ya
   no está `PENDIENTE` (cancelado/reprogramado por otro canal) la seña se libera
   igual y el turno no se toca.
4. `HuecoLiberadoPort.emitir(tenant_id, turno_id)`: **el mismo** evento de C-06,
   idempotente por `auto_oferta:{turno_id}`. C-11 no reimplementa la oferta.
5. Auditoría `SENA_LIBERADA` con `auto_oferta_emitida`.

Todo el bloque corre en **una sola transacción por seña**: si la emisión del
hueco falla, se hace rollback completo y la seña sigue `PENDIENTE` para el
próximo barrido (F-14). Nunca queda un turno cancelado sin evento de hueco, ni
una seña liberada con el turno vivo.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.core.logging import get_logger
from app.lista_espera.puertos import HuecoLiberadoPort
from app.senas.puertos import (
    AuditoriaPort,
    Reloj,
    Sena,
    SenaRepositorio,
    TransaccionNula,
    TurnoPort,
    UnidadDeTrabajoPort,
)

__all__ = [
    "MOTIVO_EXPIRACION",
    "MOTIVO_SENA_NO_ACREDITADA",
    "ServicioSenasExpulsion",
]

logger = get_logger("app.senas.worker")

MOTIVO_EXPIRACION = "EXPIRACION"
MOTIVO_SENA_NO_ACREDITADA = "SENA_NO_ACREDITADA"
ACTOR_WORKER = "worker-senas"


class ServicioSenasExpulsion:
    """Libera las señas vencidas del tenant y dispara la auto-oferta de C-07."""

    def __init__(
        self,
        senas: SenaRepositorio,
        turnos: TurnoPort,
        huecos: HuecoLiberadoPort,
        auditoria: AuditoriaPort,
        *,
        reloj: Reloj | None = None,
        uow_factory: Callable[[], UnidadDeTrabajoPort] | None = None,
    ) -> None:
        self._senas = senas
        self._turnos = turnos
        self._huecos = huecos
        self._auditoria = auditoria
        self._reloj = reloj
        self._uow_factory: Callable[[], UnidadDeTrabajoPort] = (
            uow_factory if uow_factory is not None else TransaccionNula
        )

    def procesar_expiraciones(
        self, *, tenant_id: str, ahora: datetime | None = None
    ) -> list[Sena]:
        """Libera las señas vencidas **del tenant**; nunca barre otro tenant."""
        momento = self._momento(ahora)
        liberadas: list[Sena] = []
        for vencida in self._senas.vencidas(tenant_id=tenant_id, ahora=momento):
            with self._uow_factory():
                liberada = self._liberar(vencida=vencida, momento=momento)
                if liberada is not None:
                    liberadas.append(liberada)
        return liberadas

    def _liberar(self, *, vencida: Sena, momento: datetime) -> Sena | None:
        # Punto único de serialización: la fila de la seña (D11).
        sena = self._senas.bloquear(tenant_id=vencida.tenant_id, sena_id=vencida.id)
        if sena.estado != "PENDIENTE" or sena.expira_at > momento:
            # Perdió la carrera o la lista venía de una lectura vieja: no escribe.
            return None

        liberada = self._senas.transicionar(
            tenant_id=sena.tenant_id,
            sena_id=sena.id,
            desde="PENDIENTE",
            hacia="LIBERADA",
            campos={"liberada_en": momento, "motivo_liberacion": MOTIVO_EXPIRACION},
        )
        if liberada is None:
            return None

        turno = self._turnos.turno_de(
            tenant_id=sena.tenant_id, turno_id=sena.turno_id
        )
        auto_oferta_emitida = False
        if turno is not None and turno.estado == "PENDIENTE":
            self._turnos.cancelar_por_sena(
                tenant_id=sena.tenant_id,
                turno_id=sena.turno_id,
                motivo=MOTIVO_SENA_NO_ACREDITADA,
                ahora=momento,
            )
            # Mismo puerto que C-06: idempotente por `auto_oferta:{turno_id}`.
            self._huecos.emitir(tenant_id=sena.tenant_id, turno_id=sena.turno_id)
            auto_oferta_emitida = True

        self._auditoria.registrar(
            tenant_id=liberada.tenant_id,
            accion="SENA_LIBERADA",
            actor=ACTOR_WORKER,
            entidad="sena",
            entidad_id=liberada.id,
            antes={"estado": "PENDIENTE", "expira_at": sena.expira_at.isoformat()},
            despues={
                "estado": "LIBERADA",
                "motivo_liberacion": MOTIVO_EXPIRACION,
                "turno_id": liberada.turno_id,
                "monto_centavos": liberada.monto_centavos,
                # La transición del turno queda en la misma entrada (spec
                # `turnos-anti-solape`), con antes/después observable.
                "turno_antes": turno.estado if turno is not None else None,
                "turno_despues": (
                    "CANCELADO"
                    if auto_oferta_emitida
                    else (turno.estado if turno is not None else None)
                ),
                "auto_oferta_emitida": auto_oferta_emitida,
            },
        )
        logger.info(
            "sena_liberada tenant_id=%s sena_id=%s turno_id=%s auto_oferta=%s",
            liberada.tenant_id,
            liberada.id,
            liberada.turno_id,
            auto_oferta_emitida,
        )
        return liberada

    def _momento(self, ahora: datetime | None) -> datetime:
        if ahora is not None:
            return ahora
        if self._reloj is not None:
            return self._reloj()
        raise RuntimeError("ServicioSenasExpulsion requiere un reloj inyectado o `ahora`")
