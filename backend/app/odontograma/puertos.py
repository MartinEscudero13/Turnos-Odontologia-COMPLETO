"""Puertos y adaptadores en memoria del odontograma — C-09.

El dominio del odontograma programa contra estos protocolos para no acoplarse a
PostgreSQL ni a la identidad de C-04/C-05/C-08. Igual que C-06/C-07/C-08, el
wiring real a SQLAlchemy es un follow-up declarado.

Reglas duras:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Los adaptadores en memoria sólo devuelven lo sembrado/escrito por el test.
- Ningún puerto transporta PHI: paciente/profesional sólo se consultan por
  existencia y la auditoría nunca incluye el texto clínico (RN-CL-04).
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Literal, Protocol, cast

from app.ficha_clinica.puertos import (
    ConsentimientoMemoria,
    PacienteMemoria,
    ProfesionalMemoria,
    TurnoMemoria,
)
from app.turnos.servicio import NoEncontrado

__all__ = [
    "AccionOdontograma",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "ConsentimientoMemoria",
    "ConsentimientoPort",
    "EntradaAuditoria",
    "Hallazgo",
    "HallazgoMemoria",
    "HallazgoRepositorio",
    "PacienteMemoria",
    "PacientePort",
    "PrestacionMemoria",
    "PrestacionPort",
    "ProfesionalMemoria",
    "ProfesionalPort",
    "Reloj",
    "TurnoMemoria",
    "TurnoPort",
    "UnidadDeTrabajo",
    "UnidadDeTrabajoMemoria",
]

AccionOdontograma = Literal[
    "HALLAZGO_REGISTRADO",
    "HALLAZGO_RESUELTO",
    "LINEA_PRESUPESTADA",
]


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Hallazgo:
    """Hallazgo clínico fechado; corrección = hallazgo nuevo (D2/RN-CL-03)."""

    id: str
    tenant_id: str
    paciente_id: str
    pieza_fdi: int
    superficie: str | None
    hallazgo: str
    fecha: datetime
    profesional_id: str
    resuelto: bool
    creado_en: datetime


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: AccionOdontograma
    actor: str
    entidad: str
    entidad_id: str
    antes: dict[str, object] | None
    despues: dict[str, object] | None
    registrado_en: str


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class HallazgoRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        pieza_fdi: int,
        superficie: str | None,
        hallazgo: str,
        fecha: datetime,
        profesional_id: str,
        ahora: datetime | None = None,
    ) -> Hallazgo: ...

    def listar_por_paciente(self, *, tenant_id: str, paciente_id: str) -> list[Hallazgo]: ...

    def listar_por_pieza(
        self, *, tenant_id: str, paciente_id: str, pieza_fdi: int
    ) -> list[Hallazgo]: ...

    def obtener(self, *, tenant_id: str, hallazgo_id: str) -> Hallazgo | None: ...

    def marcar_resuelto(self, *, tenant_id: str, hallazgo_id: str) -> Hallazgo: ...


class PrestacionPort(Protocol):
    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None: ...


class PacientePort(Protocol):
    def existe(self, *, tenant_id: str, paciente_id: str) -> bool: ...


class ProfesionalPort(Protocol):
    def existe(self, *, tenant_id: str, profesional_id: str) -> bool: ...


class TurnoPort(Protocol):
    def atiende(self, *, tenant_id: str, profesional_id: str, paciente_id: str) -> bool: ...


class ConsentimientoPort(Protocol):
    def firmado(self, *, tenant_id: str, paciente_id: str) -> bool: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionOdontograma,
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


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


def _orden(hallazgo: Hallazgo) -> tuple[datetime, datetime, str]:
    return (hallazgo.fecha, hallazgo.creado_en, hallazgo.id)


class HallazgoMemoria:
    """Hallazgos en memoria scoped por tenant, con historial ordenado por fecha."""

    def __init__(self) -> None:
        self._hallazgos: dict[str, Hallazgo] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        pieza_fdi: int,
        superficie: str | None,
        hallazgo: str,
        fecha: datetime,
        profesional_id: str,
        ahora: datetime | None = None,
    ) -> Hallazgo:
        with self._lock:
            creado = Hallazgo(
                id=f"hallazgo-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                pieza_fdi=pieza_fdi,
                superficie=superficie,
                hallazgo=hallazgo,
                fecha=fecha,
                profesional_id=profesional_id,
                resuelto=False,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._hallazgos[creado.id] = creado
            return creado

    def listar_por_paciente(self, *, tenant_id: str, paciente_id: str) -> list[Hallazgo]:
        return sorted(
            (
                h
                for h in self._hallazgos.values()
                if h.tenant_id == tenant_id and h.paciente_id == paciente_id
            ),
            key=_orden,
        )

    def listar_por_pieza(
        self, *, tenant_id: str, paciente_id: str, pieza_fdi: int
    ) -> list[Hallazgo]:
        return [
            h
            for h in self.listar_por_paciente(tenant_id=tenant_id, paciente_id=paciente_id)
            if h.pieza_fdi == pieza_fdi
        ]

    def obtener(self, *, tenant_id: str, hallazgo_id: str) -> Hallazgo | None:
        hallazgo = self._hallazgos.get(hallazgo_id)
        if hallazgo is None or hallazgo.tenant_id != tenant_id:
            return None
        return hallazgo

    def marcar_resuelto(self, *, tenant_id: str, hallazgo_id: str) -> Hallazgo:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, hallazgo_id=hallazgo_id)
            if actual is None:
                raise NoEncontrado("hallazgo no encontrado")
            resuelto = replace(actual, resuelto=True)
            self._hallazgos[hallazgo_id] = resuelto
            return resuelto

    def total(self, tenant_id: str) -> int:
        return sum(1 for h in self._hallazgos.values() if h.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._hallazgos), self._siguiente)

    def restaurar(self, estado: object) -> None:
        hallazgos, siguiente = cast(tuple[dict[str, Hallazgo], int], estado)
        with self._lock:
            self._hallazgos = dict(hallazgos)
            self._siguiente = siguiente


class PrestacionMemoria:
    """Precio base en centavos por (tenant, prestación); `None` = inexistente."""

    def __init__(self, precios: Iterable[tuple[str, str, int]] = ()) -> None:
        self._precios: dict[tuple[str, str], int] = {
            (tenant_id, prestacion_id): precio
            for tenant_id, prestacion_id, precio in precios
        }

    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None:
        return self._precios.get((tenant_id, prestacion_id))

    def agregar(self, tenant_id: str, prestacion_id: str, precio_base: int) -> None:
        self._precios[(tenant_id, prestacion_id)] = precio_base


class AuditoriaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionOdontograma,
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
    """Unidad de trabajo de prueba: snapshot al entrar y restauración en error.

    Es el adaptador que usa el dominio en tests; la garantía real de producción
    es la transacción SQLAlchemy (follow-up de wiring declarado).
    """

    def __init__(self, repos: Iterable[_Instantanea]) -> None:
        self._repos: tuple[_Instantanea, ...] = tuple(repos)
        self._estados: tuple[object, ...] = ()

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


Reloj = Callable[[], datetime]
