"""Adaptadores de integración de C-10 con los puertos que define C-09.

`ServicioPresupuesto` no conoce la caja: acepta un `ImputacionPort`. Este adaptador
traduce la aceptación de una línea al movimiento o cobro pendiente que C-10 sabe
registrar, sin arrastrar PHI.
"""
from __future__ import annotations

from app.caja.puertos import MedioPago
from app.caja.servicio import ServicioCaja

__all__ = ["ImputacionCaja"]


class ImputacionCaja:
    """Implementa `app.presupuesto.puertos.ImputacionPort` sobre `ServicioCaja`."""

    def __init__(self, caja: ServicioCaja) -> None:
        self._caja = caja

    def imputar_agenda(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        prestacion_id: str,
        monto_centavos: int,
    ) -> None:
        # C-09 sólo registra la intención: no crea turnos (M10).
        del tenant_id, presupuesto_id, linea_id, paciente_id, prestacion_id, monto_centavos

    def imputar_caja(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        prestacion_id: str,
        monto_paciente_centavos: int,
        monto_os_centavos: int,
        actor_id: str,
        turno_id: str | None,
        medio: MedioPago | None,
    ) -> None:
        del prestacion_id, monto_os_centavos
        self._caja.imputar_tramo_paciente(
            tenant_id=tenant_id,
            presupuesto_id=presupuesto_id,
            linea_id=linea_id,
            paciente_id=paciente_id,
            monto_paciente_centavos=monto_paciente_centavos,
            actor_id=actor_id,
            medio=medio,
            turno_id=turno_id,
        )
