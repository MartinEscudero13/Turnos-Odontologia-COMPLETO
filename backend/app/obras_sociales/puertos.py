"""Puertos, entidades y adaptadores en memoria de C-12.

El dominio no conoce SQLAlchemy: recibe repositorios y lecturas inyectadas. Los
adaptadores en memoria permiten probar la matemática de cobertura, los filtros
de la liquidación y el cierre inmutable sin base de datos.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime
from typing import Literal, Protocol

from app.turnos.servicio import TurnoError

ModoCobertura = Literal["PORCENTAJE", "MONTO"]
OrigenCobertura = Literal["CONFIGURADA", "SIN_COBERTURA"]
EstadoLiquidacion = Literal["BORRADOR", "CERRADA"]

Reloj = Callable[[], datetime]

CODIGO_OBRA_SOCIAL_DUPLICADA = "OBRA_SOCIAL_DUPLICADA"
CODIGO_LIQUIDACION_CERRADA = "LIQUIDACION_CERRADA"
CODIGO_SIN_TURNOS = "SIN_TURNOS_ELEGIBLES"

__all__ = [
    "CODIGO_LIQUIDACION_CERRADA",
    "CODIGO_OBRA_SOCIAL_DUPLICADA",
    "CODIGO_SIN_TURNOS",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "Cobertura",
    "CoberturaMemoria",
    "CoberturaRepositorio",
    "Conflicto",
    "EstadoLiquidacion",
    "Liquidacion",
    "LiquidacionDuplicada",
    "LiquidacionMemoria",
    "LiquidacionRepositorio",
    "LineaLiquidacion",
    "ModoCobertura",
    "ObraSocial",
    "ObraSocialDuplicada",
    "ObraSocialMemoria",
    "ObraSocialRepositorio",
    "OrigenCobertura",
    "PacienteObraSocialMemoria",
    "PacienteObraSocialPort",
    "PrestacionPrecioMemoria",
    "PrestacionPrecioPort",
    "TramoCobertura",
    "TurnoAtendido",
    "TurnosAtendidosMemoria",
    "TurnosAtendidosPort",
]


class Conflicto(TurnoError):
    """`409` de obras sociales con código de dominio observable."""

    codigo = 409

    def __init__(self, codigo_dominio: str, mensaje: str) -> None:
        super().__init__(mensaje)
        self.codigo_dominio: str = codigo_dominio


class ObraSocialDuplicada(Exception):
    """Señal de repositorio: el UNIQUE de nombre por tenant se violó."""


class LiquidacionDuplicada(Exception):
    """Señal de repositorio: ya existe una liquidación del mismo período."""


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ObraSocial:
    id: str
    tenant_id: str
    nombre: str
    activa: bool
    creado_en: datetime


@dataclass(frozen=True)
class Cobertura:
    id: str
    tenant_id: str
    obra_social_id: str
    prestacion_id: str
    modo: ModoCobertura
    valor: int
    tope_centavos: int | None
    creado_en: datetime

    @property
    def validada_en_vivo(self) -> bool:
        """v1 declara la cobertura configurada, nunca validada (RN-OS-01)."""
        return False


@dataclass(frozen=True)
class TramoCobertura:
    precio_base_centavos: int
    cobertura_os: int
    a_cargo_paciente: int
    origen: OrigenCobertura
    validada_en_vivo: bool = False


@dataclass(frozen=True)
class TurnoAtendido:
    turno_id: str
    paciente_id: str
    prestacion_id: str
    inicio: datetime
    precio_base_centavos: int


@dataclass(frozen=True)
class LineaLiquidacion:
    id: str
    turno_id: str
    paciente_id: str
    prestacion_id: str
    fecha: datetime
    monto_centavos: int


@dataclass(frozen=True)
class Liquidacion:
    id: str
    tenant_id: str
    obra_social_id: str
    periodo_desde: date
    periodo_hasta: date
    estado: EstadoLiquidacion
    total_centavos: int
    creado_en: datetime
    cerrada_en: datetime | None = None
    lineas: tuple[LineaLiquidacion, ...] = ()


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: str
    actor: str
    entidad: str
    entidad_id: str
    antes: dict[str, object] | None = None
    despues: dict[str, object] | None = None
    at: datetime = field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Puertos
# ---------------------------------------------------------------------------


class ObraSocialRepositorio(Protocol):
    def crear(self, *, tenant_id: str, nombre: str, ahora: datetime) -> ObraSocial: ...

    def obtener(self, *, tenant_id: str, obra_social_id: str) -> ObraSocial | None: ...

    def por_nombre(self, *, tenant_id: str, nombre: str) -> ObraSocial | None: ...

    def listar(self, *, tenant_id: str, solo_activas: bool = False) -> list[ObraSocial]: ...

    def cambiar_estado(
        self, *, tenant_id: str, obra_social_id: str, activa: bool, ahora: datetime
    ) -> ObraSocial: ...


class CoberturaRepositorio(Protocol):
    def upsert(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        prestacion_id: str,
        modo: ModoCobertura,
        valor: int,
        tope_centavos: int | None,
        ahora: datetime,
    ) -> Cobertura: ...

    def obtener(
        self, *, tenant_id: str, obra_social_id: str, prestacion_id: str
    ) -> Cobertura | None: ...

    def listar(self, *, tenant_id: str, obra_social_id: str | None = None) -> list[Cobertura]: ...


class LiquidacionRepositorio(Protocol):
    def obtener(self, *, tenant_id: str, liquidacion_id: str) -> Liquidacion | None: ...

    def buscar(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> Liquidacion | None: ...

    def listar(
        self,
        *,
        tenant_id: str,
        obra_social_id: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Liquidacion]: ...

    def crear(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        desde: date,
        hasta: date,
        ahora: datetime,
    ) -> Liquidacion: ...

    def reemplazar_lineas(
        self,
        *,
        tenant_id: str,
        liquidacion_id: str,
        lineas: list[tuple[TurnoAtendido, int]],
    ) -> Liquidacion: ...

    def cerrar(
        self, *, tenant_id: str, liquidacion_id: str, ahora: datetime
    ) -> Liquidacion: ...


class TurnosAtendidosPort(Protocol):
    def atendidos(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> list[TurnoAtendido]: ...


class PacienteObraSocialPort(Protocol):
    def existe(self, *, tenant_id: str, paciente_id: str) -> bool: ...

    def obra_social(self, *, tenant_id: str, paciente_id: str) -> str | None: ...


class PrestacionPrecioPort(Protocol):
    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: str,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


class ObraSocialMemoria:
    def __init__(self, reloj: Reloj | None = None) -> None:
        self._reloj = reloj or (lambda: datetime.now(UTC))
        self._items: dict[str, ObraSocial] = {}
        self._secuencia = 0

    def crear(self, *, tenant_id: str, nombre: str, ahora: datetime) -> ObraSocial:
        if self.por_nombre(tenant_id=tenant_id, nombre=nombre) is not None:
            raise ObraSocialDuplicada(nombre)
        self._secuencia += 1
        creada = ObraSocial(
            id=f"os-{self._secuencia}",
            tenant_id=tenant_id,
            nombre=nombre,
            activa=True,
            creado_en=ahora,
        )
        self._items[creada.id] = creada
        return creada

    def obtener(self, *, tenant_id: str, obra_social_id: str) -> ObraSocial | None:
        item = self._items.get(obra_social_id)
        return item if item is not None and item.tenant_id == tenant_id else None

    def por_nombre(self, *, tenant_id: str, nombre: str) -> ObraSocial | None:
        for item in self._items.values():
            if item.tenant_id == tenant_id and item.nombre == nombre:
                return item
        return None

    def listar(self, *, tenant_id: str, solo_activas: bool = False) -> list[ObraSocial]:
        return sorted(
            (
                item
                for item in self._items.values()
                if item.tenant_id == tenant_id and (item.activa or not solo_activas)
            ),
            key=lambda item: item.nombre,
        )

    def cambiar_estado(
        self, *, tenant_id: str, obra_social_id: str, activa: bool, ahora: datetime
    ) -> ObraSocial:
        del ahora
        item = self.obtener(tenant_id=tenant_id, obra_social_id=obra_social_id)
        if item is None:
            raise KeyError(obra_social_id)
        actualizada = replace(item, activa=activa)
        self._items[obra_social_id] = actualizada
        return actualizada


class CoberturaMemoria:
    def __init__(self, reloj: Reloj | None = None) -> None:
        self._reloj = reloj or (lambda: datetime.now(UTC))
        self._items: dict[tuple[str, str, str], Cobertura] = {}
        self._secuencia = 0

    def upsert(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        prestacion_id: str,
        modo: ModoCobertura,
        valor: int,
        tope_centavos: int | None,
        ahora: datetime,
    ) -> Cobertura:
        clave = (tenant_id, obra_social_id, prestacion_id)
        existente = self._items.get(clave)
        if existente is not None:
            actualizada = replace(
                existente, modo=modo, valor=valor, tope_centavos=tope_centavos
            )
            self._items[clave] = actualizada
            return actualizada
        self._secuencia += 1
        creada = Cobertura(
            id=f"cobertura-{self._secuencia}",
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            prestacion_id=prestacion_id,
            modo=modo,
            valor=valor,
            tope_centavos=tope_centavos,
            creado_en=ahora,
        )
        self._items[clave] = creada
        return creada

    def obtener(
        self, *, tenant_id: str, obra_social_id: str, prestacion_id: str
    ) -> Cobertura | None:
        return self._items.get((tenant_id, obra_social_id, prestacion_id))

    def listar(self, *, tenant_id: str, obra_social_id: str | None = None) -> list[Cobertura]:
        return sorted(
            (
                item
                for (dueno, os_id, _), item in self._items.items()
                if dueno == tenant_id and (obra_social_id is None or os_id == obra_social_id)
            ),
            key=lambda item: (item.obra_social_id, item.prestacion_id),
        )


class LiquidacionMemoria:
    def __init__(self, reloj: Reloj | None = None) -> None:
        self._reloj = reloj or (lambda: datetime.now(UTC))
        self._items: dict[str, Liquidacion] = {}
        self._secuencia = 0

    def obtener(self, *, tenant_id: str, liquidacion_id: str) -> Liquidacion | None:
        item = self._items.get(liquidacion_id)
        return item if item is not None and item.tenant_id == tenant_id else None

    def buscar(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> Liquidacion | None:
        for item in self._items.values():
            if (
                item.tenant_id == tenant_id
                and item.obra_social_id == obra_social_id
                and item.periodo_desde == desde
                and item.periodo_hasta == hasta
            ):
                return item
        return None

    def listar(
        self,
        *,
        tenant_id: str,
        obra_social_id: str | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Liquidacion]:
        return sorted(
            (
                item
                for item in self._items.values()
                if item.tenant_id == tenant_id
                and (obra_social_id is None or item.obra_social_id == obra_social_id)
                and (desde is None or item.periodo_hasta >= desde)
                and (hasta is None or item.periodo_desde <= hasta)
            ),
            key=lambda item: (item.periodo_desde, item.id),
        )

    def crear(
        self,
        *,
        tenant_id: str,
        obra_social_id: str,
        desde: date,
        hasta: date,
        ahora: datetime,
    ) -> Liquidacion:
        if self.buscar(tenant_id=tenant_id, obra_social_id=obra_social_id, desde=desde, hasta=hasta):
            raise LiquidacionDuplicada(f"{obra_social_id}:{desde}:{hasta}")
        self._secuencia += 1
        creada = Liquidacion(
            id=f"liquidacion-{self._secuencia}",
            tenant_id=tenant_id,
            obra_social_id=obra_social_id,
            periodo_desde=desde,
            periodo_hasta=hasta,
            estado="BORRADOR",
            total_centavos=0,
            creado_en=ahora,
        )
        self._items[creada.id] = creada
        return creada

    def reemplazar_lineas(
        self,
        *,
        tenant_id: str,
        liquidacion_id: str,
        lineas: list[tuple[TurnoAtendido, int]],
    ) -> Liquidacion:
        item = self.obtener(tenant_id=tenant_id, liquidacion_id=liquidacion_id)
        if item is None:
            raise KeyError(liquidacion_id)
        detalle = tuple(
            LineaLiquidacion(
                id=f"{item.id}-linea-{indice}",
                turno_id=turno.turno_id,
                paciente_id=turno.paciente_id,
                prestacion_id=turno.prestacion_id,
                fecha=turno.inicio,
                monto_centavos=monto,
            )
            for indice, (turno, monto) in enumerate(lineas, start=1)
        )
        actualizada = replace(
            item, lineas=detalle, total_centavos=sum(linea.monto_centavos for linea in detalle)
        )
        self._items[liquidacion_id] = actualizada
        return actualizada

    def cerrar(
        self, *, tenant_id: str, liquidacion_id: str, ahora: datetime
    ) -> Liquidacion:
        item = self.obtener(tenant_id=tenant_id, liquidacion_id=liquidacion_id)
        if item is None:
            raise KeyError(liquidacion_id)
        cerrada = replace(item, estado="CERRADA", cerrada_en=ahora)
        self._items[liquidacion_id] = cerrada
        return cerrada


class TurnosAtendidosMemoria:
    def __init__(self) -> None:
        self._turnos: list[tuple[str, TurnoAtendido, str]] = []

    def agregar(self, turno: TurnoAtendido, *, tenant_id: str, obra_social_id: str) -> None:
        self._turnos.append((tenant_id, turno, obra_social_id))

    def atendidos(
        self, *, tenant_id: str, obra_social_id: str, desde: date, hasta: date
    ) -> list[TurnoAtendido]:
        inicio = datetime.combine(desde, datetime.min.time(), tzinfo=UTC)
        fin = datetime.combine(hasta, datetime.min.time(), tzinfo=UTC)
        return sorted(
            (
                turno
                for dueno, turno, obra in self._turnos
                if dueno == tenant_id
                and obra == obra_social_id
                and inicio <= turno.inicio < fin
            ),
            key=lambda turno: turno.inicio,
        )


class PacienteObraSocialMemoria:
    def __init__(self) -> None:
        self._obras: dict[tuple[str, str], str] = {}
        self._pacientes: set[tuple[str, str]] = set()

    def agregar(self, tenant_id: str, paciente_id: str, obra_social_id: str | None) -> None:
        self._pacientes.add((tenant_id, paciente_id))
        if obra_social_id is None:
            self._obras.pop((tenant_id, paciente_id), None)
        else:
            self._obras[(tenant_id, paciente_id)] = obra_social_id

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        return (tenant_id, paciente_id) in self._pacientes

    def obra_social(self, *, tenant_id: str, paciente_id: str) -> str | None:
        return self._obras.get((tenant_id, paciente_id))


class PrestacionPrecioMemoria:
    def __init__(self) -> None:
        self._precios: dict[tuple[str, str], int] = {}

    def agregar(self, tenant_id: str, prestacion_id: str, precio_base: int) -> None:
        self._precios[(tenant_id, prestacion_id)] = precio_base

    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None:
        return self._precios.get((tenant_id, prestacion_id))


class AuditoriaMemoria:
    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: str,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self.entradas.append(
            EntradaAuditoria(
                tenant_id=tenant_id,
                accion=accion,
                actor=actor,
                entidad=entidad,
                entidad_id=entidad_id,
                antes=antes,
                despues=despues,
            )
        )
