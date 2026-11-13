"""Adaptador real del puerto de imputación de C-09 — C-10 §5 (D6).

`AdaptadorCaja` implementa `ImputacionPort.imputar_caja` con la **firma exacta**
de `backend/app/presupuesto/puertos.py` (todos keyword-only, `medio` opcional) y
reutiliza `MedioPago` importado de `app.presupuesto.puertos` (M11). C-09 no se
toca: su servicio sigue invocando el puerto y traduciendo cualquier excepción a
`503` (H5/D2).

Mapeo de los dos tramos (D6):

| Campo del puerto | Destino |
|---|---|
| `tenant_id`, `presupuesto_id`, `linea_id`, `paciente_id` | `movimientos_caja` (trazabilidad, sin PHI) |
| `prestacion_id` | **no se persiste**: derivable por `linea_id` |
| `monto_paciente_centavos` | `INGRESO(medio, tramo=PACIENTE)` o `cobros_pendientes` si `medio IS NULL` |
| `monto_os_centavos` | `cuentas_por_cobrar_os` (devengado informativo, **nunca** un `INGRESO`) |
| `actor_id` | `usuario_id` del movimiento / `actor_id` del pendiente |
| `turno_id` | `turno_id` (FK nullable) |
| `medio` | medio del **tramo del paciente**, no del tramo OS |

Reglas:
- Un tramo en 0 no genera nada; `medio='OS'` en el tramo del paciente es
  `422 MEDIO_OS_RESERVADO` (C10-OQ-5) y no escribe nada.
- El tramo OS se registra una sola vez por línea (`UNIQUE (tenant_id, linea_id)`):
  un replay idéntico es no-op y uno con otro monto es `409 IMPUTACION_DUPLICADA`.
- La línea debe pertenecer al tenant y al presupuesto: si no, `404` sin escribir.
- Todo ocurre dentro de una unidad de trabajo que toma el advisory lock del día
  (D14) antes de escribir; el tramo del paciente delega en
  `ServicioCaja.imputar_tramo_paciente`, que ya aplica H1 (UNIQUE por tramo) y
  `CIERRE_CERRADO`.
- `imputar_agenda` sigue siendo no-op (M10): C-10 no crea turnos.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime
from typing import cast, get_args

from app.caja.puertos import (
    CuentaPorCobrarDuplicada,
    CuentaPorCobrarOSRepositorio,
    LineaPresupuestoPort,
    MedioPago,
    Reloj,
    UnidadDeTrabajo,
)
from app.caja.servicio import (
    TZ_OPERATIVA,
    ConflictoCaja,
    InvalidoCaja,
    ServicioCaja,
    dia_operativo,
)
from app.turnos.servicio import NoEncontrado

__all__ = ["AdaptadorCaja", "AdaptadorImputacionCaja"]

# Los medios válidos se derivan del tipo importado: no se redeclara el enum.
_MEDIOS: frozenset[str] = frozenset(get_args(MedioPago))


def _entero_no_negativo(monto: object, *, campo: str) -> int:
    """Los montos del puerto son enteros en centavos; `<= 0` no genera hecho."""
    # `bool` es subclase de `int`: `True` no es un monto.
    if isinstance(monto, bool) or not isinstance(monto, int):
        raise InvalidoCaja("MONTO_INVALIDO", f"{campo} inválido: debe ser un entero en centavos")
    return monto if monto > 0 else 0


class AdaptadorCaja:
    """Adaptador de C-10 para el puerto de imputación que define C-09."""

    def __init__(
        self,
        *,
        servicio: ServicioCaja,
        cuentas: CuentaPorCobrarOSRepositorio,
        lineas: LineaPresupuestoPort,
        uow_factory: Callable[[], UnidadDeTrabajo],
        reloj: Reloj | None = None,
    ) -> None:
        self._servicio = servicio
        self._cuentas = cuentas
        self._lineas = lineas
        self._uow_factory = uow_factory
        self._reloj: Reloj = (
            reloj if reloj is not None else (lambda: datetime.now(TZ_OPERATIVA))
        )

    # ------------------------------------------------------------------
    # Puerto de C-09
    # ------------------------------------------------------------------

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
        """C-09 M10 / C-05: C-10 no crea turnos; la intención es un no-op."""
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
        """Imputa los dos tramos de la línea aceptada (D6).

        Punto de observación (H5/D2): invocado directo expone `422`, `409` y
        `404`; a través de `POST /api/presupuestos/{id}/aceptar` C-09 traduce
        cualquier excepción a `503` y no persiste la aceptación.
        """
        del prestacion_id  # D6: derivable por `linea_id`; no se persiste.
        medio_validado = self._validar_medio(medio)
        paciente_centavos = _entero_no_negativo(
            monto_paciente_centavos, campo="monto_paciente_centavos"
        )
        os_centavos = _entero_no_negativo(monto_os_centavos, campo="monto_os_centavos")
        # C10-OQ-5: el medio OS queda reservado al tramo de la obra social.
        if medio_validado == "OS" and paciente_centavos > 0:
            raise InvalidoCaja(
                "MEDIO_OS_RESERVADO",
                "el medio OS no se acepta en el tramo del paciente",
            )

        momento = self._reloj()
        fecha = dia_operativo(momento)
        with self._uow_factory() as uow:
            # D14: el lock del día se toma antes de escribir cualquiera de los dos tramos.
            uow.bloquear_dia(tenant_id=tenant_id, fecha=fecha)
            if not self._lineas.pertenece(
                tenant_id=tenant_id, presupuesto_id=presupuesto_id, linea_id=linea_id
            ):
                # D6.8: un id de otro tenant nunca resuelve acá. La consulta va
                # dentro de la unidad de trabajo para no abrir una transacción
                # implícita antes de reclamar la del adaptador.
                raise NoEncontrado("línea de presupuesto no encontrada")
            if os_centavos > 0:
                self._registrar_devengado_os(
                    tenant_id=tenant_id,
                    fecha=fecha,
                    presupuesto_id=presupuesto_id,
                    linea_id=linea_id,
                    paciente_id=paciente_id,
                    monto_centavos=os_centavos,
                    ahora=momento,
                )
            if paciente_centavos > 0:
                self._servicio.imputar_tramo_paciente(
                    tenant_id=tenant_id,
                    presupuesto_id=presupuesto_id,
                    linea_id=linea_id,
                    paciente_id=paciente_id,
                    monto_paciente_centavos=paciente_centavos,
                    actor_id=actor_id,
                    medio=medio_validado,
                    turno_id=turno_id,
                    fecha=fecha,
                )

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    @staticmethod
    def _validar_medio(medio: object) -> MedioPago | None:
        """C-09 ya valida; C-10 no confía (D6.4)."""
        if medio is None:
            return None
        if not isinstance(medio, str) or medio not in _MEDIOS:
            raise InvalidoCaja("MEDIO_INVALIDO", "medio inválido")
        return cast(MedioPago, medio)

    def _registrar_devengado_os(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        ahora: datetime,
    ) -> None:
        """Devengado informativo: uno por línea, nunca un `INGRESO` (D4/M12)."""
        existente = self._cuentas.buscar_por_linea(tenant_id=tenant_id, linea_id=linea_id)
        if existente is not None:
            self._exigir_mismo_monto(existente.monto_centavos, monto_centavos, linea_id)
            return
        try:
            self._cuentas.registrar(
                tenant_id=tenant_id,
                fecha=fecha,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                monto_centavos=monto_centavos,
                ahora=ahora,
            )
        except CuentaPorCobrarDuplicada:
            # Carrera perdida contra el UNIQUE `(tenant_id, linea_id)`: sólo es
            # no-op si el devengado existente es el mismo hecho.
            otra = self._cuentas.buscar_por_linea(tenant_id=tenant_id, linea_id=linea_id)
            if otra is None:
                raise
            self._exigir_mismo_monto(otra.monto_centavos, monto_centavos, linea_id)

    @staticmethod
    def _exigir_mismo_monto(existente: int, recibido: int, linea_id: str) -> None:
        if existente != recibido:
            raise ConflictoCaja(
                "IMPUTACION_DUPLICADA",
                f"la línea {linea_id} ya tiene un devengado OS de otro monto",
            )


# Alias explícito del rol del adaptador en el design (§Seams).
AdaptadorImputacionCaja = AdaptadorCaja
