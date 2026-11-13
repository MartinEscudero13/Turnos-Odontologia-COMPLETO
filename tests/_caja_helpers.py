"""Harness de caja cableado en memoria — C-10 §2 (no recolectado por pytest).

Datos ficticios (regla dura RN-GL-03): usuarios U1 (RECEPCION), U2 (ADMIN),
U3 (ODONTOLOGO), turnos TUR-1 (T1) y TUR-9 (T2), montos en centavos y reloj
inyectado en `-03:00` (C10-OQ-8). La unidad de trabajo cubre movimientos,
cierres, pendientes, ajustes, cuentas por cobrar y auditoría: si el caso de uso
falla no queda ninguna escritura.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone

from conftest import T1, T2

from app.caja.adaptador_imputacion import AdaptadorCaja
from app.caja.puertos import (
    AjustePostCierreMemoria,
    AuditoriaMemoria,
    Cierre,
    CierreMemoria,
    CobroPendiente,
    CobroPendienteMemoria,
    CuentaPorCobrarOSMemoria,
    LineaPresupuestoMemoria,
    Movimiento,
    MovimientoMemoria,
    TurnoMemoria,
    UnidadDeTrabajo,
    UnidadDeTrabajoMemoria,
    UsuarioMemoria,
)
from app.caja.servicio import ResultadoCobro, ServicioCaja
from app.turnos.servicio import Actor

TZ = timezone(timedelta(hours=-3))

U1 = "usuario-1"
U2 = "usuario-2"
U3 = "usuario-3"
U9 = "usuario-9"
TUR1 = "turno-1"
TUR9 = "turno-9"
LINEA1 = "linea-1"
PRESU1 = "presupuesto-1"
PAC1 = "paciente-1"


def d3(dia: str = "2026-11-10", hora: int = 10, minuto: int = 0) -> datetime:
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, minuto, tzinfo=TZ)


def actor(
    rol: str = "RECEPCION",
    tenant: str = T1,
    user_id: str = U1,
) -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id)


class CierreMemoriaObservada(CierreMemoria):
    """CierreMemoria que cuenta cierres: prueba que un ajuste no lo recalcula."""

    def __init__(
        self,
        movimientos: MovimientoMemoria,
        cuentas: CuentaPorCobrarOSMemoria,
    ) -> None:
        super().__init__(movimientos, cuentas)
        self.llamadas_cerrar = 0

    def cerrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        efectivo_contado: int,
        responsable_id: str,
        motivo_diferencia: str | None = None,
        observacion: str | None = None,
        ahora: datetime | None = None,
    ) -> Cierre:
        self.llamadas_cerrar += 1
        return super().cerrar(
            tenant_id=tenant_id,
            fecha=fecha,
            efectivo_contado=efectivo_contado,
            responsable_id=responsable_id,
            motivo_diferencia=motivo_diferencia,
            observacion=observacion,
            ahora=ahora,
        )


class HarnessCaja:
    """Dominio de caja cableado en memoria, con semillas ficticias."""

    def __init__(self) -> None:
        self.movimientos = MovimientoMemoria()
        self.cuentas = CuentaPorCobrarOSMemoria()
        self.cierres = CierreMemoriaObservada(self.movimientos, self.cuentas)
        self.pendientes = CobroPendienteMemoria()
        self.ajustes = AjustePostCierreMemoria()
        self.turnos = TurnoMemoria()
        self.lineas_presupuesto = LineaPresupuestoMemoria()
        self.usuarios = UsuarioMemoria()
        self.auditoria = AuditoriaMemoria()
        self.ahora = d3()
        self.uow = self.nueva_uow()
        self.svc = self._servicio(self.nueva_uow)
        self.adaptador = self._adaptador(self.nueva_uow)
        self.turnos.agregar(T1, TUR1)
        self.turnos.agregar(T2, TUR9)
        self.lineas_presupuesto.agregar(T1, PRESU1, LINEA1)
        # D4: el responsable del cierre tiene que ser un usuario del tenant.
        self.usuarios.agregar(T1, U1)
        self.usuarios.agregar(T1, U2)
        self.usuarios.agregar(T1, U3)
        self.usuarios.agregar(T2, U9)

    # -- cableado -------------------------------------------------------

    def nueva_uow(self) -> UnidadDeTrabajoMemoria:
        uow = UnidadDeTrabajoMemoria(
            [
                self.movimientos,
                self.cierres,
                self.pendientes,
                self.ajustes,
                self.cuentas,
                self.auditoria,
            ],
            self.movimientos,
        )
        # La última unidad de trabajo usada queda accesible para inspeccionar
        # los locks simulados (D14).
        self.uow = uow
        return uow

    def _servicio(self, factory: Callable[[], UnidadDeTrabajo]) -> ServicioCaja:
        def factory_con_registro() -> UnidadDeTrabajo:
            # La última unidad de trabajo usada queda accesible para inspeccionar
            # los locks simulados (D14).
            uow = factory()
            self.uow = uow if isinstance(uow, UnidadDeTrabajoMemoria) else self.uow
            return uow

        return ServicioCaja(
            self.movimientos,
            self.cierres,
            self.pendientes,
            self.ajustes,
            self.cuentas,
            self.turnos,
            self.auditoria,
            usuarios=self.usuarios,
            uow_factory=factory_con_registro,
            reloj=lambda: self.ahora,
        )

    def cablear_uow(self, factory: Callable[[], UnidadDeTrabajo]) -> None:
        self.svc = self._servicio(factory)
        self.adaptador = self._adaptador(factory)

    def _adaptador(self, factory: Callable[[], UnidadDeTrabajo]) -> AdaptadorCaja:
        """Adaptador real del puerto de C-09 sobre el mismo cableado (§5)."""
        return AdaptadorCaja(
            servicio=self.svc,
            cierres=self.cierres,
            cuentas=self.cuentas,
            lineas=self.lineas_presupuesto,
            uow_factory=factory,
            reloj=lambda: self.ahora,
        )

    # -- casos de uso ---------------------------------------------------

    def registrar(
        self,
        *,
        monto: object = 150000,
        medio: object = "EFECTIVO",
        tipo: object = "INGRESO",
        fecha: object = None,
        turno_id: str | None = None,
        actor_: Actor | None = None,
    ) -> Movimiento:
        return self.svc.registrar_movimiento(
            actor() if actor_ is None else actor_,
            monto=monto,  # type: ignore[arg-type]  # los tests pasan valores inválidos a propósito
            medio=medio,  # type: ignore[arg-type]
            tipo=tipo,  # type: ignore[arg-type]
            fecha=fecha,  # type: ignore[arg-type]
            turno_id=turno_id,
        )

    def anular(
        self,
        movimiento_id: str,
        *,
        motivo: object = "cobro duplicado",
        actor_: Actor | None = None,
    ) -> Movimiento:
        # Anular es exclusivo de ADMIN (D10/C10-OQ-9); el actor por defecto es U2.
        return self.svc.anular_movimiento(
            actor("ADMIN", user_id=U2) if actor_ is None else actor_,
            movimiento_id=movimiento_id,
            motivo=motivo,  # type: ignore[arg-type]
        )

    def cerrar(
        self,
        *,
        fecha: object = "2026-11-10",
        efectivo_contado: int = 150000,
        responsable_id: str = U2,
        motivo_diferencia: str | None = None,
        observacion: str | None = None,
        tenant_id: str = T1,
    ) -> Cierre:
        dia = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha))
        return self.cierres.cerrar(
            tenant_id=tenant_id,
            fecha=dia,
            efectivo_contado=efectivo_contado,
            responsable_id=responsable_id,
            motivo_diferencia=motivo_diferencia,
            observacion=observacion,
            ahora=self.ahora,
        )

    def cerrar_dia(
        self,
        *,
        fecha: object = "2026-11-10",
        efectivo_contado: object = 0,
        responsable_id: object = U2,
        motivo_diferencia: object = None,
        observacion: object = None,
        actor_: Actor | None = None,
    ) -> Cierre:
        """Cierre por el caso de uso real (valida responsable, motivo y fecha)."""
        return self.svc.cerrar_dia(
            actor() if actor_ is None else actor_,  # type: ignore[arg-type]
            fecha=fecha,  # type: ignore[arg-type]
            efectivo_contado=efectivo_contado,  # type: ignore[arg-type]
            responsable_id=responsable_id,  # type: ignore[arg-type]
            motivo_diferencia=motivo_diferencia,  # type: ignore[arg-type]
            observacion=observacion,  # type: ignore[arg-type]
        )

    def imputar_tramo(
        self,
        *,
        monto: int = 60000,
        medio: object = None,
        fecha: object = "2026-11-10",
        linea_id: str = LINEA1,
        presupuesto_id: str = PRESU1,
        paciente_id: str = PAC1,
        tenant_id: str = T1,
        actor_id: str = U1,
        turno_id: str | None = None,
    ) -> Movimiento | CobroPendiente | None:
        dia: date | None = None
        if fecha is not None:
            dia = fecha if isinstance(fecha, date) else date.fromisoformat(str(fecha))
        return self.svc.imputar_tramo_paciente(
            tenant_id=tenant_id,
            presupuesto_id=presupuesto_id,
            linea_id=linea_id,
            paciente_id=paciente_id,
            monto_paciente_centavos=monto,
            actor_id=actor_id,
            medio=medio,  # type: ignore[arg-type]  # los tests pasan valores inválidos a propósito
            turno_id=turno_id,
            fecha=dia,
        )

    def cobrar(
        self,
        pendiente_id: str,
        *,
        medio: object = "TRANSFERENCIA",
        actor_: Actor | None = None,
    ) -> ResultadoCobro:
        return self.svc.cobrar_pendiente(
            actor() if actor_ is None else actor_,
            pendiente_id=pendiente_id,
            medio=medio,  # type: ignore[arg-type]
        )

    # -- adaptador de C-09 (§5) -----------------------------------------

    def imputar(
        self,
        *,
        monto_paciente: int = 60000,
        monto_os: int = 0,
        medio: object = "EFECTIVO",
        linea_id: str = LINEA1,
        presupuesto_id: str = PRESU1,
        paciente_id: str = PAC1,
        prestacion_id: str = "prestacion-1",
        tenant_id: str = T1,
        actor_id: str = U1,
        turno_id: str | None = None,
    ) -> None:
        """Invoca el puerto de C-09 tal como lo hace `ServicioPresupuesto`."""
        return self.adaptador.imputar_caja(
            tenant_id=tenant_id,
            presupuesto_id=presupuesto_id,
            linea_id=linea_id,
            paciente_id=paciente_id,
            prestacion_id=prestacion_id,
            monto_paciente_centavos=monto_paciente,
            monto_os_centavos=monto_os,
            actor_id=actor_id,
            turno_id=turno_id,
            medio=medio,  # type: ignore[arg-type]  # los tests pasan valores inválidos a propósito
        )
