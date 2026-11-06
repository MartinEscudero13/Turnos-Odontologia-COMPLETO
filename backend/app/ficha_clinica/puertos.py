"""Puertos (protocolos) y adaptadores en memoria del dominio de ficha clínica.

C-08 programa contra estos puertos para no acoplarse a PostgreSQL ni a la
identidad de C-04/C-05. Igual que C-06/C-07, el dominio queda testeable sin DB;
el wiring real a SQLAlchemy es un follow-up explícito.

Reglas duras cumplidas acá:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Los adaptadores en memoria sólo devuelven lo sembrado/escrito por el test.
- Ningún puerto transporta PHI: `PacientePort`/`ProfesionalPort` sólo exponen
  existencia por id (sin nombre/teléfono) y `storage_ref` es una referencia opaca.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Protocol

TipoAdjunto = Literal["RX", "FOTO"]

AccionClinica = Literal[
    "FICHA_CREADA",
    "EVOLUCION_REGISTRADA",
    "ADJUNTO_REGISTRADO",
    "CONSENTIMIENTO_REGISTRADO",
]


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Ficha:
    id: str
    tenant_id: str
    paciente_id: str
    creado_en: datetime


@dataclass(frozen=True)
class Evolucion:
    id: str
    tenant_id: str
    paciente_id: str
    profesional_id: str
    fecha: datetime
    texto: str
    firma_hash: str | None
    creado_en: datetime


@dataclass(frozen=True)
class Adjunto:
    id: str
    tenant_id: str
    ficha_id: str
    tipo: str
    storage_ref: str
    creado_en: datetime


@dataclass(frozen=True)
class Consentimiento:
    id: str
    tenant_id: str
    paciente_id: str
    timestamp: datetime | None  # nullable sólo para modelar el gate defensivo (fila inválida)
    canal: str
    creado_en: datetime


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: AccionClinica
    actor: str
    entidad: str
    entidad_id: str
    antes: dict[str, object] | None
    despues: dict[str, object] | None
    registrado_en: str


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class FichaRepositorio(Protocol):
    def crear(self, *, tenant_id: str, paciente_id: str, ahora: datetime | None = None) -> Ficha: ...

    def por_paciente(self, *, tenant_id: str, paciente_id: str) -> Ficha | None: ...

    def obtener(self, *, tenant_id: str, ficha_id: str) -> Ficha | None: ...


class EvolucionRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        profesional_id: str,
        fecha: datetime,
        texto: str,
        firma_hash: str | None = None,
        ahora: datetime | None = None,
    ) -> Evolucion: ...

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Evolucion]: ...


class AdjuntoRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        ficha_id: str,
        tipo: str,
        storage_ref: str,
        ahora: datetime | None = None,
    ) -> Adjunto: ...

    def listar(self, *, tenant_id: str, ficha_id: str) -> list[Adjunto]: ...


class ConsentimientoRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        timestamp: datetime | None,
        canal: str,
        ahora: datetime | None = None,
    ) -> Consentimiento: ...

    def firmado(self, *, tenant_id: str, paciente_id: str) -> bool: ...

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Consentimiento]: ...


class PacientePort(Protocol):
    def existe(self, *, tenant_id: str, paciente_id: str) -> bool: ...


class ProfesionalPort(Protocol):
    def existe(self, *, tenant_id: str, profesional_id: str) -> bool: ...


class TurnoPort(Protocol):
    def atiende(self, *, tenant_id: str, profesional_id: str, paciente_id: str) -> bool: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionClinica,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


class FichaMemoria:
    """Fichas en memoria scoped por (tenant, paciente) con ancla 1—1."""

    def __init__(self) -> None:
        self._fichas: dict[str, Ficha] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def crear(self, *, tenant_id: str, paciente_id: str, ahora: datetime | None = None) -> Ficha:
        with self._lock:
            ficha = Ficha(
                id=f"ficha-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._fichas[ficha.id] = ficha
            return ficha

    def por_paciente(self, *, tenant_id: str, paciente_id: str) -> Ficha | None:
        for f in self._fichas.values():
            if f.tenant_id == tenant_id and f.paciente_id == paciente_id:
                return f
        return None

    def obtener(self, *, tenant_id: str, ficha_id: str) -> Ficha | None:
        f = self._fichas.get(ficha_id)
        if f is None or f.tenant_id != tenant_id:
            return None
        return f

    def total(self, tenant_id: str) -> int:
        return sum(1 for f in self._fichas.values() if f.tenant_id == tenant_id)


class EvolucionMemoria:
    """Evoluciones append-only en memoria: sólo `registrar` y `listar`."""

    def __init__(self) -> None:
        self._evoluciones: list[Evolucion] = []
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        profesional_id: str,
        fecha: datetime,
        texto: str,
        firma_hash: str | None = None,
        ahora: datetime | None = None,
    ) -> Evolucion:
        with self._lock:
            evolucion = Evolucion(
                id=f"evolucion-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                profesional_id=profesional_id,
                fecha=fecha,
                texto=texto,
                firma_hash=firma_hash,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._evoluciones.append(evolucion)
            return evolucion

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Evolucion]:
        return [
            e
            for e in self._evoluciones
            if e.tenant_id == tenant_id and e.paciente_id == paciente_id
        ]


class AdjuntoMemoria:
    """Adjuntos en memoria scoped por (tenant, ficha)."""

    def __init__(self) -> None:
        self._adjuntos: list[Adjunto] = []
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        ficha_id: str,
        tipo: str,
        storage_ref: str,
        ahora: datetime | None = None,
    ) -> Adjunto:
        with self._lock:
            adjunto = Adjunto(
                id=f"adjunto-{self._siguiente}",
                tenant_id=tenant_id,
                ficha_id=ficha_id,
                tipo=tipo,
                storage_ref=storage_ref,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._adjuntos.append(adjunto)
            return adjunto

    def listar(self, *, tenant_id: str, ficha_id: str) -> list[Adjunto]:
        return [
            a for a in self._adjuntos if a.tenant_id == tenant_id and a.ficha_id == ficha_id
        ]


class ConsentimientoMemoria:
    """Consentimientos append-only; `firmado` exige timestamp válido (no mera fila)."""

    def __init__(self) -> None:
        self._consentimientos: list[Consentimiento] = []
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        timestamp: datetime | None,
        canal: str,
        ahora: datetime | None = None,
    ) -> Consentimiento:
        with self._lock:
            consentimiento = Consentimiento(
                id=f"consentimiento-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                timestamp=timestamp,
                canal=canal,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._consentimientos.append(consentimiento)
            return consentimiento

    def firmado(self, *, tenant_id: str, paciente_id: str) -> bool:
        for c in self._consentimientos:
            if (
                c.tenant_id == tenant_id
                and c.paciente_id == paciente_id
                and c.timestamp is not None
                and c.timestamp.tzinfo is not None
            ):
                return True
        return False

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Consentimiento]:
        return [
            c
            for c in self._consentimientos
            if c.tenant_id == tenant_id and c.paciente_id == paciente_id
        ]

    def total(self, tenant_id: str) -> int:
        return sum(1 for c in self._consentimientos if c.tenant_id == tenant_id)


class PacienteMemoria:
    """Existencia de pacientes por (tenant, id), sin PHI."""

    def __init__(self, pacientes: Iterable[tuple[str, str]] = ()) -> None:
        self._pacientes = set(pacientes)

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        return (tenant_id, paciente_id) in self._pacientes

    def agregar(self, tenant_id: str, paciente_id: str) -> None:
        self._pacientes.add((tenant_id, paciente_id))


class ProfesionalMemoria:
    """Existencia de profesionales por (tenant, id), sin PHI."""

    def __init__(self, profesionales: Iterable[tuple[str, str]] = ()) -> None:
        self._profesionales = set(profesionales)

    def existe(self, *, tenant_id: str, profesional_id: str) -> bool:
        return (tenant_id, profesional_id) in self._profesionales

    def agregar(self, tenant_id: str, profesional_id: str) -> None:
        self._profesionales.add((tenant_id, profesional_id))


class TurnoMemoria:
    """Conjunto de (tenant, profesional, paciente) con turno: "pacientes que atiende"."""

    def __init__(self, atendidos: Iterable[tuple[str, str, str]] = ()) -> None:
        self._atendidos = set(atendidos)

    def atiende(self, *, tenant_id: str, profesional_id: str, paciente_id: str) -> bool:
        return (tenant_id, profesional_id, paciente_id) in self._atendidos

    def agregar(self, tenant_id: str, profesional_id: str, paciente_id: str) -> None:
        self._atendidos.add((tenant_id, profesional_id, paciente_id))


class AuditoriaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionClinica,
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


Reloj = Callable[[], datetime]
