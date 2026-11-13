"""Puertos y adaptadores en memoria de caja — C-10 (§2).

El dominio de caja programa contra estos protocolos para no acoplarse a
PostgreSQL ni a la identidad de C-03/C-04/C-05. Igual que C-06/C-07/C-08/C-09,
el wiring real a SQLAlchemy es un follow-up declarado; los tests de migración
cubren CHECKs, UNIQUE, RLS, grants y el lock real.

Reglas duras:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Montos enteros en centavos; la fecha operativa es `date` (D1).
- El UNIQUE parcial de imputación por `(tenant_id, linea_id, tramo)` **no**
  incluye el medio (H1) y el de pendientes no depende de la resolución.
- `MedioPago` se importa de `app.presupuesto.puertos` (M11): no se redeclara.
- El lock de día es una simulación declarada (`bloqueos_dia`): la garantía real
  `pg_advisory_xact_lock(hashtext(tenant||':'||fecha))` vive en el adaptador
  SQLAlchemy y se prueba con dos conexiones a PostgreSQL (D14).

Sin PHI: las entidades sólo llevan ids, fechas, medios y montos.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from types import TracebackType
from typing import Literal, Protocol, cast

from app.presupuesto.puertos import MedioPago
from app.turnos.servicio import NoEncontrado

TipoMovimiento = Literal["INGRESO", "EGRESO"]
OrigenMovimiento = Literal["MANUAL", "IMPUTACION", "COMPENSACION"]
TramoCaja = Literal["PACIENTE", "OS"]
TipoAjuste = Literal["AJUSTE_ANULACION", "COBRO_PENDIENTE"]

MEDIOS: tuple[MedioPago, ...] = ("EFECTIVO", "TRANSFERENCIA", "MP", "OS")

AccionCaja = Literal[
    "MOVIMIENTO_CAJA_REGISTRADO",
    "MOVIMIENTO_CAJA_ANULADO",
    "MOVIMIENTO_COMPENSATORIO_REGISTRADO",
    "AJUSTE_POST_CIERRE_REGISTRADO",
    "COBRO_PENDIENTE_REGISTRADO",
    "COBRO_PENDIENTE_RESUELTO",
    "CIERRE_DIARIO_REGISTRADO",
]

Reloj = Callable[[], datetime]

__all__ = [
    "AccionCaja",
    "Ajuste",
    "AjusteDuplicado",
    "AjustePostCierreMemoria",
    "AjustePostCierreRepositorio",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "Cierre",
    "CierreDiarioMemoria",
    "CierreDuplicado",
    "CierreMemoria",
    "CierreRepositorio",
    "CobroPendiente",
    "CobroPendienteMemoria",
    "CobroPendienteRepositorio",
    "CobroYaResuelto",
    "CuentaPorCobrarOS",
    "CuentaPorCobrarOSMemoria",
    "CuentaPorCobrarOSRepositorio",
    "CuentaPorCobrarDuplicada",
    "EntradaAuditoria",
    "ImputacionDuplicada",
    "LineaPresupuestoMemoria",
    "LineaPresupuestoPort",
    "MEDIOS",
    "MedioPago",
    "Movimiento",
    "MovimientoMemoria",
    "MovimientoRepositorio",
    "OrigenMovimiento",
    "Reloj",
    "TipoAjuste",
    "TipoMovimiento",
    "TotalesCajaPort",
    "TramoCaja",
    "TurnoMemoria",
    "TurnoPort",
    "UnidadDeTrabajo",
    "UnidadDeTrabajoMemoria",
    "UsuarioMemoria",
    "UsuarioPort",
    "YaAnulado",
]


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Movimiento:
    id: str
    tenant_id: str
    fecha: date
    medio: MedioPago
    monto: int
    tipo: TipoMovimiento
    usuario_id: str
    tramo: TramoCaja | None
    turno_id: str | None
    presupuesto_id: str | None
    linea_id: str | None
    paciente_id: str | None
    origen: OrigenMovimiento
    compensa_a_id: str | None
    anulado: bool
    motivo_anulacion: str | None
    anulado_por: str | None
    anulado_en: datetime | None
    creado_en: datetime


@dataclass(frozen=True)
class Cierre:
    id: str
    tenant_id: str
    fecha: date
    total_efectivo: int
    total_transferencia: int
    total_mp: int
    total_os_cobrado: int
    total_os: int
    efectivo_contado: int
    diferencia: int
    responsable_id: str
    motivo_diferencia: str | None
    observacion: str | None
    cerrado_at: datetime
    creado_en: datetime


@dataclass(frozen=True)
class CobroPendiente:
    id: str
    tenant_id: str
    fecha: date
    presupuesto_id: str
    linea_id: str
    paciente_id: str
    monto_centavos: int
    actor_id: str
    turno_id: str | None
    creado_en: datetime
    resuelto_en: datetime | None
    movimiento_id: str | None


@dataclass(frozen=True)
class Ajuste:
    id: str
    tenant_id: str
    cierre_id: str
    tipo: TipoAjuste
    movimiento_original_id: str | None
    cobro_pendiente_id: str | None
    monto: int
    medio: MedioPago
    motivo: str | None
    actor_id: str
    compensatorio_id: str
    creado_en: datetime


@dataclass(frozen=True)
class CuentaPorCobrarOS:
    id: str
    tenant_id: str
    fecha: date
    presupuesto_id: str
    linea_id: str
    paciente_id: str
    monto_centavos: int
    creado_en: datetime


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: AccionCaja
    actor: str
    entidad: str
    entidad_id: str
    antes: dict[str, object] | None
    despues: dict[str, object] | None
    registrado_en: str


# ---------------------------------------------------------------------------
# Errores de repositorio (el servicio los traduce a 409 y anota el dominio)
# ---------------------------------------------------------------------------


class ImputacionDuplicada(Exception):
    """Ya existe una imputación para `(tenant, línea, tramo)` (H1)."""


class YaAnulado(Exception):
    """El movimiento ya fue anulado (una sola transición, D2)."""


class CierreDuplicado(Exception):
    """El día ya tiene cierre (`UNIQUE (tenant_id, fecha)`)."""


class CobroYaResuelto(Exception):
    """El pendiente ya fue cobrado (409 COBRO_YA_RESUELTO)."""


class AjusteDuplicado(Exception):
    """Ya existe un ajuste para el mismo hecho corregido (D1)."""


class CuentaPorCobrarDuplicada(Exception):
    """Ya existe el devengado OS de la línea (`UNIQUE (tenant_id, linea_id)`)."""


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class MovimientoRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        medio: MedioPago,
        monto: int,
        tipo: TipoMovimiento,
        usuario_id: str,
        tramo: TramoCaja | None = None,
        turno_id: str | None = None,
        presupuesto_id: str | None = None,
        linea_id: str | None = None,
        paciente_id: str | None = None,
        origen: OrigenMovimiento = "MANUAL",
        compensa_a_id: str | None = None,
        motivo_anulacion: str | None = None,
        ahora: datetime | None = None,
    ) -> Movimiento: ...

    def obtener(self, *, tenant_id: str, movimiento_id: str) -> Movimiento | None: ...

    def listar_por_fecha(self, *, tenant_id: str, fecha: date) -> list[Movimiento]: ...

    def listar_por_rango(
        self, *, tenant_id: str, desde: date, hasta: date
    ) -> list[Movimiento]: ...

    def buscar_imputacion(
        self, *, tenant_id: str, linea_id: str, tramo: TramoCaja
    ) -> Movimiento | None: ...

    def anular(
        self,
        *,
        tenant_id: str,
        movimiento_id: str,
        motivo: str,
        actor_id: str,
        ahora: datetime | None = None,
    ) -> Movimiento: ...


class CierreRepositorio(Protocol):
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
    ) -> Cierre: ...

    def obtener(self, *, tenant_id: str, fecha: date) -> Cierre | None: ...

    def listar(self, *, tenant_id: str, desde: date, hasta: date) -> list[Cierre]: ...


class CobroPendienteRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        actor_id: str,
        turno_id: str | None = None,
        ahora: datetime | None = None,
    ) -> CobroPendiente: ...

    def obtener(self, *, tenant_id: str, pendiente_id: str) -> CobroPendiente | None: ...

    def buscar_por_linea(self, *, tenant_id: str, linea_id: str) -> CobroPendiente | None: ...

    def listar(self, *, tenant_id: str, fecha: date | None = None) -> list[CobroPendiente]: ...

    def resolver(
        self,
        *,
        tenant_id: str,
        pendiente_id: str,
        movimiento_id: str,
        ahora: datetime | None = None,
    ) -> CobroPendiente: ...


class AjustePostCierreRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        cierre_id: str,
        tipo: TipoAjuste,
        monto: int,
        medio: MedioPago,
        actor_id: str,
        compensatorio_id: str,
        movimiento_original_id: str | None = None,
        cobro_pendiente_id: str | None = None,
        motivo: str | None = None,
        ahora: datetime | None = None,
    ) -> Ajuste: ...

    def listar_por_cierre(self, *, tenant_id: str, cierre_id: str) -> list[Ajuste]: ...


class CuentaPorCobrarOSRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        ahora: datetime | None = None,
    ) -> CuentaPorCobrarOS: ...

    def buscar_por_linea(
        self, *, tenant_id: str, linea_id: str
    ) -> CuentaPorCobrarOS | None: ...

    def total_devengado(self, *, tenant_id: str, fecha: date) -> int: ...


class TotalesCajaPort(Protocol):
    def totales_por_medio(self, *, tenant_id: str, fecha: date) -> dict[MedioPago, int]: ...


class LineaPresupuestoPort(Protocol):
    """Existencia de la línea dentro del tenant y del presupuesto (D6.8).

    El adaptador de C-09 valida contra esta pieza que `linea_id` pertenece a
    `presupuesto_id` y al tenant: un id de T2 nunca resuelve en T1 (`404`).
    """

    def pertenece(self, *, tenant_id: str, presupuesto_id: str, linea_id: str) -> bool: ...


class TurnoPort(Protocol):
    def existe(self, *, tenant_id: str, turno_id: str) -> bool: ...


class UsuarioPort(Protocol):
    """Pertenencia de un usuario al tenant (D4: responsable del cierre).

    El cierre exige un `responsable_id` de un usuario del tenant: un id de T2
    nunca resuelve en T1 (`404`), igual que el resto de las referencias.
    """

    def existe(self, *, tenant_id: str, usuario_id: str) -> bool: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionCaja,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None: ...


class UnidadDeTrabajo(Protocol):
    """Commit en éxito y rollback en excepción sobre los repositorios cubiertos."""

    def __enter__(self) -> UnidadDeTrabajo: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def bloquear_dia(self, *, tenant_id: str, fecha: date) -> None: ...

    def bloquear_movimiento(self, *, tenant_id: str, movimiento_id: str) -> Movimiento: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


class MovimientoMemoria:
    """Movimientos en memoria scoped por tenant; espeja el UNIQUE por tramo."""

    def __init__(self) -> None:
        self._movimientos: dict[str, Movimiento] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        medio: MedioPago,
        monto: int,
        tipo: TipoMovimiento,
        usuario_id: str,
        tramo: TramoCaja | None = None,
        turno_id: str | None = None,
        presupuesto_id: str | None = None,
        linea_id: str | None = None,
        paciente_id: str | None = None,
        origen: OrigenMovimiento = "MANUAL",
        compensa_a_id: str | None = None,
        motivo_anulacion: str | None = None,
        ahora: datetime | None = None,
    ) -> Movimiento:
        with self._lock:
            if origen == "IMPUTACION" and linea_id is not None:
                for existente in self._movimientos.values():
                    if (
                        existente.tenant_id == tenant_id
                        and existente.linea_id == linea_id
                        and existente.tramo == tramo
                        and existente.origen == "IMPUTACION"
                    ):
                        raise ImputacionDuplicada(
                            f"línea {linea_id} ya imputada en el tramo {tramo}"
                        )
            momento = _ahora(ahora)
            movimiento = Movimiento(
                id=f"movimiento-{self._siguiente}",
                tenant_id=tenant_id,
                fecha=fecha,
                medio=medio,
                monto=monto,
                tipo=tipo,
                usuario_id=usuario_id,
                tramo=tramo,
                turno_id=turno_id,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                origen=origen,
                compensa_a_id=compensa_a_id,
                anulado=False,
                motivo_anulacion=motivo_anulacion,
                anulado_por=None,
                anulado_en=None,
                creado_en=momento,
            )
            self._siguiente += 1
            self._movimientos[movimiento.id] = movimiento
            return movimiento

    def obtener(self, *, tenant_id: str, movimiento_id: str) -> Movimiento | None:
        movimiento = self._movimientos.get(movimiento_id)
        if movimiento is None or movimiento.tenant_id != tenant_id:
            return None
        return movimiento

    def listar_por_fecha(self, *, tenant_id: str, fecha: date) -> list[Movimiento]:
        return sorted(
            (
                m
                for m in self._movimientos.values()
                if m.tenant_id == tenant_id and m.fecha == fecha
            ),
            key=lambda m: (m.creado_en, m.id),
        )

    def listar_por_rango(
        self, *, tenant_id: str, desde: date, hasta: date
    ) -> list[Movimiento]:
        return sorted(
            (
                m
                for m in self._movimientos.values()
                if m.tenant_id == tenant_id and desde <= m.fecha <= hasta
            ),
            key=lambda m: (m.fecha, m.creado_en, m.id),
        )

    def buscar_imputacion(
        self, *, tenant_id: str, linea_id: str, tramo: TramoCaja
    ) -> Movimiento | None:
        for movimiento in self._movimientos.values():
            if (
                movimiento.tenant_id == tenant_id
                and movimiento.linea_id == linea_id
                and movimiento.tramo == tramo
                and movimiento.origen == "IMPUTACION"
            ):
                return movimiento
        return None

    def anular(
        self,
        *,
        tenant_id: str,
        movimiento_id: str,
        motivo: str,
        actor_id: str,
        ahora: datetime | None = None,
    ) -> Movimiento:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, movimiento_id=movimiento_id)
            if actual is None:
                raise NoEncontrado("movimiento de caja no encontrado")
            if actual.anulado:
                raise YaAnulado("el movimiento ya está anulado")
            anulado = replace(
                actual,
                anulado=True,
                motivo_anulacion=motivo,
                anulado_por=actor_id,
                anulado_en=_ahora(ahora),
            )
            self._movimientos[movimiento_id] = anulado
            return anulado

    def totales_por_medio(self, *, tenant_id: str, fecha: date) -> dict[MedioPago, int]:
        totales: dict[MedioPago, int] = {medio: 0 for medio in MEDIOS}
        for movimiento in self._movimientos.values():
            if (
                movimiento.tenant_id != tenant_id
                or movimiento.fecha != fecha
                or movimiento.anulado
            ):
                continue
            signo = 1 if movimiento.tipo == "INGRESO" else -1
            totales[movimiento.medio] += signo * movimiento.monto
        return totales

    def total(self, tenant_id: str) -> int:
        return sum(1 for m in self._movimientos.values() if m.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._movimientos), self._siguiente)

    def restaurar(self, estado: object) -> None:
        movimientos, siguiente = cast(tuple[dict[str, Movimiento], int], estado)
        with self._lock:
            self._movimientos = dict(movimientos)
            self._siguiente = siguiente


class CierreMemoria:
    """Cierres en memoria; calcula los totales desde movimientos y devengado OS."""

    def __init__(
        self,
        movimientos: TotalesCajaPort,
        cuentas: CuentaPorCobrarOSRepositorio,
    ) -> None:
        self._movimientos = movimientos
        self._cuentas = cuentas
        self._cierres: dict[tuple[str, date], Cierre] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

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
        with self._lock:
            if (tenant_id, fecha) in self._cierres:
                raise CierreDuplicado(f"el día {fecha} ya tiene cierre")
            totales = self._movimientos.totales_por_medio(tenant_id=tenant_id, fecha=fecha)
            momento = _ahora(ahora)
            cierre = Cierre(
                id=f"cierre-{self._siguiente}",
                tenant_id=tenant_id,
                fecha=fecha,
                total_efectivo=totales["EFECTIVO"],
                total_transferencia=totales["TRANSFERENCIA"],
                total_mp=totales["MP"],
                total_os_cobrado=totales["OS"],
                total_os=self._cuentas.total_devengado(tenant_id=tenant_id, fecha=fecha),
                efectivo_contado=efectivo_contado,
                diferencia=efectivo_contado - totales["EFECTIVO"],
                responsable_id=responsable_id,
                motivo_diferencia=motivo_diferencia,
                observacion=observacion,
                cerrado_at=momento,
                creado_en=momento,
            )
            self._siguiente += 1
            self._cierres[(tenant_id, fecha)] = cierre
            return cierre

    def obtener(self, *, tenant_id: str, fecha: date) -> Cierre | None:
        cierre = self._cierres.get((tenant_id, fecha))
        if cierre is None or cierre.tenant_id != tenant_id:
            return None
        return cierre

    def listar(self, *, tenant_id: str, desde: date, hasta: date) -> list[Cierre]:
        return sorted(
            (
                c
                for c in self._cierres.values()
                if c.tenant_id == tenant_id and desde <= c.fecha <= hasta
            ),
            key=lambda c: (c.fecha, c.id),
        )

    def total(self, tenant_id: str) -> int:
        return sum(1 for c in self._cierres.values() if c.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._cierres), self._siguiente)

    def restaurar(self, estado: object) -> None:
        cierres, siguiente = cast(tuple[dict[tuple[str, date], Cierre], int], estado)
        with self._lock:
            self._cierres = dict(cierres)
            self._siguiente = siguiente


class CobroPendienteMemoria:
    """Pendientes uno por línea (sin condición de resolución, H1)."""

    def __init__(self) -> None:
        self._pendientes: dict[str, CobroPendiente] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        actor_id: str,
        turno_id: str | None = None,
        ahora: datetime | None = None,
    ) -> CobroPendiente:
        with self._lock:
            if self.buscar_por_linea(tenant_id=tenant_id, linea_id=linea_id) is not None:
                raise ImputacionDuplicada(
                    f"la línea {linea_id} ya tiene un cobro pendiente"
                )
            pendiente = CobroPendiente(
                id=f"pendiente-{self._siguiente}",
                tenant_id=tenant_id,
                fecha=fecha,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                monto_centavos=monto_centavos,
                actor_id=actor_id,
                turno_id=turno_id,
                creado_en=_ahora(ahora),
                resuelto_en=None,
                movimiento_id=None,
            )
            self._siguiente += 1
            self._pendientes[pendiente.id] = pendiente
            return pendiente

    def obtener(self, *, tenant_id: str, pendiente_id: str) -> CobroPendiente | None:
        pendiente = self._pendientes.get(pendiente_id)
        if pendiente is None or pendiente.tenant_id != tenant_id:
            return None
        return pendiente

    def buscar_por_linea(self, *, tenant_id: str, linea_id: str) -> CobroPendiente | None:
        for pendiente in self._pendientes.values():
            if pendiente.tenant_id == tenant_id and pendiente.linea_id == linea_id:
                return pendiente
        return None

    def listar(self, *, tenant_id: str, fecha: date | None = None) -> list[CobroPendiente]:
        return sorted(
            (
                p
                for p in self._pendientes.values()
                if p.tenant_id == tenant_id and (fecha is None or p.fecha == fecha)
            ),
            key=lambda p: (p.creado_en, p.id),
        )

    def resolver(
        self,
        *,
        tenant_id: str,
        pendiente_id: str,
        movimiento_id: str,
        ahora: datetime | None = None,
    ) -> CobroPendiente:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, pendiente_id=pendiente_id)
            if actual is None:
                raise NoEncontrado("cobro pendiente no encontrado")
            if actual.resuelto_en is not None:
                raise CobroYaResuelto("el cobro pendiente ya fue resuelto")
            resuelto = replace(
                actual, resuelto_en=_ahora(ahora), movimiento_id=movimiento_id
            )
            self._pendientes[pendiente_id] = resuelto
            return resuelto

    def total(self, tenant_id: str) -> int:
        return sum(1 for p in self._pendientes.values() if p.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._pendientes), self._siguiente)

    def restaurar(self, estado: object) -> None:
        pendientes, siguiente = cast(tuple[dict[str, CobroPendiente], int], estado)
        with self._lock:
            self._pendientes = dict(pendientes)
            self._siguiente = siguiente


class AjustePostCierreMemoria:
    """Ledger append-only de ajustes post-cierre, único por hecho corregido."""

    def __init__(self) -> None:
        self._ajustes: dict[str, Ajuste] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        cierre_id: str,
        tipo: TipoAjuste,
        monto: int,
        medio: MedioPago,
        actor_id: str,
        compensatorio_id: str,
        movimiento_original_id: str | None = None,
        cobro_pendiente_id: str | None = None,
        motivo: str | None = None,
        ahora: datetime | None = None,
    ) -> Ajuste:
        with self._lock:
            for existente in self._ajustes.values():
                if existente.tenant_id != tenant_id:
                    continue
                if (
                    movimiento_original_id is not None
                    and existente.movimiento_original_id == movimiento_original_id
                ):
                    raise AjusteDuplicado("ya existe un ajuste para ese movimiento")
                if (
                    cobro_pendiente_id is not None
                    and existente.cobro_pendiente_id == cobro_pendiente_id
                ):
                    raise AjusteDuplicado("ya existe un ajuste para ese cobro pendiente")
            ajuste = Ajuste(
                id=f"ajuste-{self._siguiente}",
                tenant_id=tenant_id,
                cierre_id=cierre_id,
                tipo=tipo,
                movimiento_original_id=movimiento_original_id,
                cobro_pendiente_id=cobro_pendiente_id,
                monto=monto,
                medio=medio,
                motivo=motivo,
                actor_id=actor_id,
                compensatorio_id=compensatorio_id,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._ajustes[ajuste.id] = ajuste
            return ajuste

    def listar_por_cierre(self, *, tenant_id: str, cierre_id: str) -> list[Ajuste]:
        return sorted(
            (
                a
                for a in self._ajustes.values()
                if a.tenant_id == tenant_id and a.cierre_id == cierre_id
            ),
            key=lambda a: (a.creado_en, a.id),
        )

    def total(self, tenant_id: str) -> int:
        return sum(1 for a in self._ajustes.values() if a.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._ajustes), self._siguiente)

    def restaurar(self, estado: object) -> None:
        ajustes, siguiente = cast(tuple[dict[str, Ajuste], int], estado)
        with self._lock:
            self._ajustes = dict(ajustes)
            self._siguiente = siguiente


class CuentaPorCobrarOSMemoria:
    """Devengado informativo OS: uno por línea, nunca suma en la caja."""

    def __init__(self) -> None:
        self._cuentas: dict[str, CuentaPorCobrarOS] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        fecha: date,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        monto_centavos: int,
        ahora: datetime | None = None,
    ) -> CuentaPorCobrarOS:
        with self._lock:
            if self.buscar_por_linea(tenant_id=tenant_id, linea_id=linea_id) is not None:
                raise CuentaPorCobrarDuplicada(
                    f"la línea {linea_id} ya tiene devengado OS"
                )
            cuenta = CuentaPorCobrarOS(
                id=f"cuenta-os-{self._siguiente}",
                tenant_id=tenant_id,
                fecha=fecha,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                monto_centavos=monto_centavos,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._cuentas[cuenta.id] = cuenta
            return cuenta

    def buscar_por_linea(
        self, *, tenant_id: str, linea_id: str
    ) -> CuentaPorCobrarOS | None:
        for cuenta in self._cuentas.values():
            if cuenta.tenant_id == tenant_id and cuenta.linea_id == linea_id:
                return cuenta
        return None

    def total_devengado(self, *, tenant_id: str, fecha: date) -> int:
        return sum(
            c.monto_centavos
            for c in self._cuentas.values()
            if c.tenant_id == tenant_id and c.fecha == fecha
        )

    def total(self, tenant_id: str) -> int:
        return sum(1 for c in self._cuentas.values() if c.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._cuentas), self._siguiente)

    def restaurar(self, estado: object) -> None:
        cuentas, siguiente = cast(tuple[dict[str, CuentaPorCobrarOS], int], estado)
        with self._lock:
            self._cuentas = dict(cuentas)
            self._siguiente = siguiente


class TurnoMemoria:
    """Existencia de turnos por `(tenant, turno)`; `404` si no pertenece."""

    def __init__(self, turnos: Iterable[tuple[str, str]] = ()) -> None:
        self._turnos: set[tuple[str, str]] = set(turnos)

    def agregar(self, tenant_id: str, turno_id: str) -> None:
        self._turnos.add((tenant_id, turno_id))

    def existe(self, *, tenant_id: str, turno_id: str) -> bool:
        return (tenant_id, turno_id) in self._turnos

    def total(self, tenant_id: str) -> int:
        return sum(1 for dueño, _ in self._turnos if dueño == tenant_id)


class UsuarioMemoria:
    """Pertenencia de usuarios por `(tenant, usuario)`: `404` si no es del tenant."""

    def __init__(self, usuarios: Iterable[tuple[str, str]] = ()) -> None:
        self._usuarios: set[tuple[str, str]] = set(usuarios)

    def agregar(self, tenant_id: str, usuario_id: str) -> None:
        self._usuarios.add((tenant_id, usuario_id))

    def existe(self, *, tenant_id: str, usuario_id: str) -> bool:
        return (tenant_id, usuario_id) in self._usuarios

    def total(self, tenant_id: str) -> int:
        return sum(1 for dueño, _ in self._usuarios if dueño == tenant_id)


class LineaPresupuestoMemoria:
    """Pertenencia de líneas por `(tenant, presupuesto, línea)` en memoria."""

    def __init__(self, lineas: Iterable[tuple[str, str, str]] = ()) -> None:
        self._lineas: set[tuple[str, str, str]] = set(lineas)

    def agregar(self, tenant_id: str, presupuesto_id: str, linea_id: str) -> None:
        self._lineas.add((tenant_id, presupuesto_id, linea_id))

    def pertenece(self, *, tenant_id: str, presupuesto_id: str, linea_id: str) -> bool:
        return (tenant_id, presupuesto_id, linea_id) in self._lineas


class AuditoriaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionCaja,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        with self._lock:
            self.entradas.append(
                EntradaAuditoria(
                    tenant_id=tenant_id,
                    accion=accion,
                    actor=actor,
                    entidad=entidad,
                    entidad_id=entidad_id,
                    antes=antes,
                    despues=despues,
                    registrado_en=datetime.now(UTC).isoformat(),
                )
            )

    def de_tenant(self, tenant_id: str) -> list[EntradaAuditoria]:
        return [e for e in self.entradas if e.tenant_id == tenant_id]

    def de_accion(self, accion: AccionCaja) -> list[EntradaAuditoria]:
        return [e for e in self.entradas if e.accion == accion]

    def instantanea(self) -> object:
        with self._lock:
            return list(self.entradas)

    def restaurar(self, estado: object) -> None:
        entradas = cast(list[EntradaAuditoria], estado)
        with self._lock:
            self.entradas = list(entradas)


class _Instantanea(Protocol):
    def instantanea(self) -> object: ...

    def restaurar(self, estado: object) -> None: ...


class UnidadDeTrabajoMemoria:
    """Unidad de trabajo de prueba: snapshot al entrar y rollback en error.

    `bloquear_dia` **simula** el advisory lock por `(tenant, fecha)` y deja
    rastro en `bloqueos_dia`; sin locks reales no hay garantía de exclusión en
    memoria (la prueba vive en PostgreSQL con dos conexiones, D14).
    """

    def __init__(
        self,
        repos: Iterable[_Instantanea],
        movimientos: MovimientoRepositorio,
    ) -> None:
        self._repos: tuple[_Instantanea, ...] = tuple(repos)
        self._estados: tuple[object, ...] = ()
        self._movimientos = movimientos
        self.bloqueos_dia: list[tuple[str, date]] = []
        self.bloqueos_movimiento: list[tuple[str, str]] = []

    def __enter__(self) -> UnidadDeTrabajoMemoria:
        self._estados = tuple(repo.instantanea() for repo in self._repos)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            for repo, estado in zip(self._repos, self._estados, strict=True):
                repo.restaurar(estado)

    def bloquear_dia(self, *, tenant_id: str, fecha: date) -> None:
        self.bloqueos_dia.append((tenant_id, fecha))

    def bloquear_movimiento(self, *, tenant_id: str, movimiento_id: str) -> Movimiento:
        self.bloqueos_movimiento.append((tenant_id, movimiento_id))
        movimiento = self._movimientos.obtener(
            tenant_id=tenant_id, movimiento_id=movimiento_id
        )
        if movimiento is None:
            raise NoEncontrado("movimiento de caja no encontrado")
        return movimiento


# Alias histórico de la entidad (mantiene el nombre del design §Seams).
CierreDiarioMemoria = CierreMemoria
