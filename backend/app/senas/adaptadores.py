"""Adaptadores de C-11 hacia C-10 y C-09 — C-11 §9 (D9, C11-OQ-13).

Dos fronteras, ninguna de las cuales se reimplementa acá:

- **Caja (C-10)**: `AplicacionCajaServicio` implementa `AplicacionCajaPort`
  delegando en `ServicioCaja.registrar_movimiento`, el **único** alta válida de
  un hecho de caja. C-11 no escribe `movimientos_caja` ni duplica el cierre: el
  `409 CIERRE_CERRADO`, el advisory lock por `(tenant, día)` y la validación del
  turno son de C-10. La transacción compartida se logra construyendo
  `ServicioCaja` con `uow_factory=lambda: TransaccionSQL(session)`: la unidad
  externa de C-11 commitea y la de C-10 sólo hace `flush` (C-10 §5).
  `tramo` queda `NULL` porque `registrar_movimiento` no lo expone y C-11 no
  escribe el repositorio; el dueño del hecho es `usuario_id` + `turno_id`.
- **Presupuesto (C-09)**: `PresupuestosAceptadosSQL` responde sólo lectura
  `aceptado_vigente` (`estado='ACEPTADO'` y `vence_en` nulo o futuro) para el
  guard `409 PRESUPUESTO_CON_SENA` (C11-OQ-13). No modifica nada de C-09.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session

from app.caja.puertos import MedioPago
from app.caja.servicio import ServicioCaja
from app.models.presupuesto import Presupuesto as PresupuestoModel
from app.senas.puertos import ConceptoAplicacion, MedioPagoMP, MovimientoRef
from app.turnos.servicio import Actor, Rol

__all__ = ["AplicacionCajaServicio", "PresupuestosAceptadosSQL"]

# C-10 sólo permite `RECEPCION`/`ADMIN` en el alta; el dueño real del hecho es
# `actor_id`, que viaja al movimiento y a la auditoría de caja.
_ROL_CAJA: Rol = "RECEPCION"


class AplicacionCajaServicio:
    """`AplicacionCajaPort` sobre el alta real de C-10."""

    def __init__(self, servicio: ServicioCaja) -> None:
        self._servicio = servicio

    def registrar_ingreso_mp(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        monto_centavos: int,
        fecha: date,
        actor_id: str,
        concepto: str,
    ) -> MovimientoRef:
        actor = Actor(tenant_id=tenant_id, rol=_ROL_CAJA, user_id=actor_id)
        movimiento = self._servicio.registrar_movimiento(
            actor,
            monto=monto_centavos,
            medio="MP",
            tipo="INGRESO",
            fecha=fecha,
            turno_id=turno_id,
        )
        return MovimientoRef(
            id=movimiento.id,
            tenant_id=movimiento.tenant_id,
            turno_id=movimiento.turno_id or turno_id,
            monto_centavos=movimiento.monto,
            medio=_medio_mp(movimiento.medio),
            tipo="INGRESO",
            fecha=movimiento.fecha,
            actor_id=movimiento.usuario_id,
            concepto=_concepto(concepto),
        )


def _medio_mp(medio: MedioPago) -> MedioPagoMP:
    """El alta de C-11 siempre crea `MP`; un medio distinto sería un bug."""
    if medio != "MP":  # pragma: no cover - defensa del contrato
        raise ValueError(f"el ingreso de la seña debe ser MP, no {medio}")
    return "MP"


def _concepto(valor: str) -> ConceptoAplicacion:
    if valor not in ("TRATAMIENTO", "CANCELACION_TARDIA"):  # pragma: no cover
        raise ValueError(f"concepto inválido: {valor}")
    return valor  # type: ignore[return-value]  # acotado por la comparación


class PresupuestosAceptadosSQL:
    """Sólo lectura de C-09: ¿el paciente tiene un presupuesto ACEPTADO vigente?"""

    def __init__(self, session: Session) -> None:
        self._session = session

    def aceptado_vigente(
        self, *, tenant_id: str, paciente_id: str, ahora: datetime
    ) -> bool:
        tenant = uuid.UUID(tenant_id)
        self._session.execute(
            text("SELECT set_config('app.tenant_id', :tenant, true)"),
            {"tenant": tenant_id},
        )
        fila = self._session.scalars(
            select(PresupuestoModel.id)
            .where(
                PresupuestoModel.tenant_id == tenant,
                PresupuestoModel.paciente_id == uuid.UUID(paciente_id),
                PresupuestoModel.estado == "ACEPTADO",
                or_(
                    PresupuestoModel.vence_en.is_(None),
                    PresupuestoModel.vence_en > ahora,
                ),
            )
            .limit(1)
        ).first()
        return fila is not None
