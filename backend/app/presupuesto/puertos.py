"""Puertos y adaptadores en memoria del presupuesto — C-09 (secciones 3–5).

El dominio del presupuesto programa contra estos protocolos para no acoplarse a
PostgreSQL ni a la identidad de C-04/C-05/C-08/C-10/C-12. Igual que C-06/C-07/
C-08, el wiring real a SQLAlchemy es un follow-up declarado.

Reglas duras:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Los montos son enteros en centavos y una línea cumple
  `cobertura_os + a_cargo_paciente = monto` (D6/D8).
- La key de idempotencia es tenant-scoped (D3.1) y el adaptador en memoria la
  hace cumplir con la misma semántica que el UNIQUE parcial de la migración 007.
- Ningún puerto transporta PHI: paciente/profesional sólo se consultan por
  existencia y la auditoría nunca incluye el texto clínico (RN-CL-04).

Sobre el lock de aceptación (D4/B1): `bloquear` del repositorio y
`bloquear_linea` de la unidad de trabajo **simulan** con un método explícito el
`SELECT ... FOR UPDATE` de producción. Un adaptador en memoria no tiene locks
reales y **no prueba** la garantía de exclusión: esa prueba vive en
`tests/test_aceptacion_concurrente_pg.py` con dos conexiones a PostgreSQL.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from types import TracebackType
from typing import Literal, Protocol, cast

from app.turnos.servicio import NoEncontrado

EstadoPresupuesto = Literal["BORRADOR", "VIGENTE", "PARCIAL", "ACEPTADO", "VENCIDO"]
OrigenCobertura = Literal["CONFIGURADA", "SIN_COBERTURA"]
MedioPago = Literal["EFECTIVO", "TRANSFERENCIA", "MP", "OS"]
ModoCobertura = Literal["PORCENTAJE", "MONTO"]

AccionPresupuesto = Literal[
    "PRESUPUESTO_CREADO",
    "PRESUPUESTO_EMITIDO",
    "PRESUPUESTO_VENCIDO",
    "LINEA_PRESUPESTADA",
    "ACEPTACION_REGISTRADA",
    "IMPUTACION_REGISTRADA",
    "COBERTURA_INVALIDA_DESCARTADA",
]

Reloj = Callable[[], datetime]

__all__ = [
    "AccionPresupuesto",
    "Aceptacion",
    "AceptacionMemoria",
    "AceptacionRepositorio",
    "AuditoriaMemoria",
    "AuditoriaPort",
    "CoberturaConfigurada",
    "CoberturaMemoria",
    "CoberturaPort",
    "CoberturaSinDatos",
    "ConsentimientoPort",
    "EntradaAuditoria",
    "EstadoPresupuesto",
    "IdempotencyKeyDuplicada",
    "ImputacionMemoria",
    "ImputacionPort",
    "LlamadaAgenda",
    "LlamadaCaja",
    "Linea",
    "LineaMemoria",
    "LineaRepositorio",
    "MedioPago",
    "ModoCobertura",
    "OrigenCobertura",
    "PacienteMemoria",
    "PacientePort",
    "PrestacionMemoria",
    "PrestacionPort",
    "Presupuesto",
    "PresupuestoMemoria",
    "PresupuestoRepositorio",
    "Reloj",
    "UnidadDeTrabajo",
    "UnidadDeTrabajoMemoria",
]


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Presupuesto:
    id: str
    tenant_id: str
    paciente_id: str
    estado: EstadoPresupuesto
    vence_en: datetime | None
    creado_en: datetime
    actualizado_en: datetime


@dataclass(frozen=True)
class Linea:
    """Línea de presupuesto con montos enteros en centavos (D6/D8)."""

    id: str
    tenant_id: str
    presupuesto_id: str
    hallazgo_id: str | None
    pieza_fdi: int | None
    prestacion_id: str
    monto: int
    cobertura_os: int
    a_cargo_paciente: int
    origen_cobertura: OrigenCobertura
    validada_en_vivo: bool
    idempotency_key: str | None
    creado_en: datetime


@dataclass(frozen=True)
class Aceptacion:
    """Decisión de una línea: ledger append-only (D4/RN-CL-02).

    `medio` es opcional y **no** es `canal` (B3): dice cómo se cobra y C-10 lo
    completa al registrar el movimiento. La columna física de `medio` en el
    ledger llega con C-10; el dominio ya lo registra para no cambiar el contrato
    de aceptación cuando exista la caja.
    """

    id: str
    tenant_id: str
    linea_id: str
    acepta: bool
    fecha: datetime
    canal: str
    medio: MedioPago | None
    creado_en: datetime


@dataclass(frozen=True)
class CoberturaConfigurada:
    """Cobertura declarada por C-12; v1 no la valida en vivo (RN-OS-01/DD-04)."""

    modo: ModoCobertura
    valor: int
    tope: int | None = None


@dataclass(frozen=True)
class LlamadaAgenda:
    """Intención de imputación a agenda: no hay datos de turno (M10)."""

    tenant_id: str
    presupuesto_id: str
    linea_id: str
    paciente_id: str
    prestacion_id: str
    monto_centavos: int


@dataclass(frozen=True)
class LlamadaCaja:
    """Contrato de caja de D6/B3: dos tramos, actor, turno y medio."""

    tenant_id: str
    presupuesto_id: str
    linea_id: str
    paciente_id: str
    prestacion_id: str
    monto_paciente_centavos: int
    monto_os_centavos: int
    actor_id: str
    turno_id: str | None
    medio: MedioPago | None


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: AccionPresupuesto
    actor: str
    entidad: str
    entidad_id: str
    antes: dict[str, object] | None
    despues: dict[str, object] | None
    registrado_en: str


class IdempotencyKeyDuplicada(Exception):
    """La key ya existe en el tenant (equivale a la violación del UNIQUE parcial)."""


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class PresupuestoRepositorio(Protocol):
    def crear(
        self, *, tenant_id: str, paciente_id: str, ahora: datetime | None = None
    ) -> Presupuesto: ...

    def obtener(self, *, tenant_id: str, presupuesto_id: str) -> Presupuesto | None: ...

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Presupuesto]: ...

    def borrador_de_paciente(
        self, *, tenant_id: str, paciente_id: str
    ) -> Presupuesto | None: ...

    def actualizar_estado(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        estado: EstadoPresupuesto,
        ahora: datetime | None = None,
    ) -> Presupuesto: ...

    def emitir(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        vence_en: datetime | None,
        ahora: datetime | None = None,
    ) -> Presupuesto: ...


class LineaRepositorio(Protocol):
    def agregar(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        prestacion_id: str,
        monto: int,
        cobertura_os: int,
        a_cargo_paciente: int,
        origen_cobertura: OrigenCobertura,
        validada_en_vivo: bool,
        pieza_fdi: int | None = None,
        hallazgo_id: str | None = None,
        idempotency_key: str | None = None,
        ahora: datetime | None = None,
    ) -> Linea: ...

    def listar(self, *, tenant_id: str, presupuesto_id: str) -> list[Linea]: ...

    def por_idempotency_key(
        self, *, tenant_id: str, idempotency_key: str
    ) -> Linea | None: ...

    def bloquear(self, *, tenant_id: str, linea_id: str) -> Linea: ...


class AceptacionRepositorio(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        linea_id: str,
        acepta: bool,
        fecha: datetime,
        canal: str,
        medio: MedioPago | None = None,
        ahora: datetime | None = None,
    ) -> Aceptacion: ...

    def ultima_por_linea(self, *, tenant_id: str, linea_id: str) -> Aceptacion | None: ...

    def listar_por_linea(self, *, tenant_id: str, linea_id: str) -> list[Aceptacion]: ...


class CoberturaPort(Protocol):
    """C-09 define; C-12 implementará contra `obras_sociales`/`coberturas`."""

    def cobertura(
        self, *, tenant_id: str, obra_social_id: str | None, prestacion_id: str
    ) -> CoberturaConfigurada | None: ...


class ImputacionPort(Protocol):
    """C-09 define; C-05/C-10 implementarán.

    `imputar_agenda` **sólo registra la intención**: no crea un turno (M10).
    """

    def imputar_agenda(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        linea_id: str,
        paciente_id: str,
        prestacion_id: str,
        monto_centavos: int,
    ) -> None: ...

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
    ) -> None: ...


class PrestacionPort(Protocol):
    def precio_base(self, *, tenant_id: str, prestacion_id: str) -> int | None: ...


class PacientePort(Protocol):
    def existe(self, *, tenant_id: str, paciente_id: str) -> bool: ...

    def obra_social_id(self, *, tenant_id: str, paciente_id: str) -> str | None: ...


class ConsentimientoPort(Protocol):
    """Gate clínico de C-08 reutilizado para líneas con pieza/hallazgo (D11)."""

    def firmado(self, *, tenant_id: str, paciente_id: str) -> bool: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionPresupuesto,
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

    def bloquear_linea(self, *, tenant_id: str, linea_id: str) -> Linea: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


class PresupuestoMemoria:
    """Presupuestos en memoria scoped por (tenant, paciente)."""

    def __init__(self) -> None:
        self._presupuestos: dict[str, Presupuesto] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def crear(
        self, *, tenant_id: str, paciente_id: str, ahora: datetime | None = None
    ) -> Presupuesto:
        with self._lock:
            momento = _ahora(ahora)
            creado = Presupuesto(
                id=f"presupuesto-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                estado="BORRADOR",
                vence_en=None,
                creado_en=momento,
                actualizado_en=momento,
            )
            self._siguiente += 1
            self._presupuestos[creado.id] = creado
            return creado

    def obtener(self, *, tenant_id: str, presupuesto_id: str) -> Presupuesto | None:
        presupuesto = self._presupuestos.get(presupuesto_id)
        if presupuesto is None or presupuesto.tenant_id != tenant_id:
            return None
        return presupuesto

    def listar(self, *, tenant_id: str, paciente_id: str) -> list[Presupuesto]:
        return sorted(
            (
                p
                for p in self._presupuestos.values()
                if p.tenant_id == tenant_id and p.paciente_id == paciente_id
            ),
            key=lambda p: (p.creado_en, p.id),
        )

    def borrador_de_paciente(
        self, *, tenant_id: str, paciente_id: str
    ) -> Presupuesto | None:
        borradores = [
            p
            for p in self._presupuestos.values()
            if p.tenant_id == tenant_id
            and p.paciente_id == paciente_id
            and p.estado == "BORRADOR"
        ]
        if not borradores:
            return None
        return max(borradores, key=lambda p: (p.creado_en, p.id))

    def actualizar_estado(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        estado: EstadoPresupuesto,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, presupuesto_id=presupuesto_id)
            if actual is None:
                raise NoEncontrado("presupuesto no encontrado")
            actualizado = replace(
                actual, estado=estado, actualizado_en=_ahora(ahora)
            )
            self._presupuestos[presupuesto_id] = actualizado
            return actualizado

    def emitir(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        vence_en: datetime | None,
        ahora: datetime | None = None,
    ) -> Presupuesto:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, presupuesto_id=presupuesto_id)
            if actual is None:
                raise NoEncontrado("presupuesto no encontrado")
            emitido = replace(
                actual,
                estado="VIGENTE",
                vence_en=vence_en,
                actualizado_en=_ahora(ahora),
            )
            self._presupuestos[presupuesto_id] = emitido
            return emitido

    def total(self, tenant_id: str) -> int:
        return sum(1 for p in self._presupuestos.values() if p.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._presupuestos), self._siguiente)

    def restaurar(self, estado: object) -> None:
        presupuestos, siguiente = cast(tuple[dict[str, Presupuesto], int], estado)
        with self._lock:
            self._presupuestos = dict(presupuestos)
            self._siguiente = siguiente


class LineaMemoria:
    """Líneas en memoria; el UNIQUE parcial por tenant se verifica al agregar."""

    def __init__(self) -> None:
        self._lineas: list[Linea] = []
        self._siguiente = 1
        self._lock = threading.Lock()

    def agregar(
        self,
        *,
        tenant_id: str,
        presupuesto_id: str,
        prestacion_id: str,
        monto: int,
        cobertura_os: int,
        a_cargo_paciente: int,
        origen_cobertura: OrigenCobertura,
        validada_en_vivo: bool,
        pieza_fdi: int | None = None,
        hallazgo_id: str | None = None,
        idempotency_key: str | None = None,
        ahora: datetime | None = None,
    ) -> Linea:
        with self._lock:
            if idempotency_key is not None and any(
                linea.tenant_id == tenant_id
                and linea.idempotency_key == idempotency_key
                for linea in self._lineas
            ):
                raise IdempotencyKeyDuplicada(idempotency_key)
            linea = Linea(
                id=f"linea-{self._siguiente}",
                tenant_id=tenant_id,
                presupuesto_id=presupuesto_id,
                hallazgo_id=hallazgo_id,
                pieza_fdi=pieza_fdi,
                prestacion_id=prestacion_id,
                monto=monto,
                cobertura_os=cobertura_os,
                a_cargo_paciente=a_cargo_paciente,
                origen_cobertura=origen_cobertura,
                validada_en_vivo=validada_en_vivo,
                idempotency_key=idempotency_key,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._lineas.append(linea)
            return linea

    def listar(self, *, tenant_id: str, presupuesto_id: str) -> list[Linea]:
        return [
            linea
            for linea in self._lineas
            if linea.tenant_id == tenant_id and linea.presupuesto_id == presupuesto_id
        ]

    def por_idempotency_key(
        self, *, tenant_id: str, idempotency_key: str
    ) -> Linea | None:
        for linea in self._lineas:
            if linea.tenant_id == tenant_id and linea.idempotency_key == idempotency_key:
                return linea
        return None

    def bloquear(self, *, tenant_id: str, linea_id: str) -> Linea:
        """Simulación explícita del `SELECT ... FOR UPDATE` (D4/B1).

        En memoria no hay locks: este método sólo devuelve la fila vigente del
        tenant y falla con `404` si no existe. La garantía real de exclusión se
        prueba contra PostgreSQL con dos conexiones independientes.
        """
        for linea in self._lineas:
            if linea.tenant_id == tenant_id and linea.id == linea_id:
                return linea
        raise NoEncontrado("línea de presupuesto no encontrada")

    def total(self, tenant_id: str) -> int:
        return sum(1 for linea in self._lineas if linea.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (list(self._lineas), self._siguiente)

    def restaurar(self, estado: object) -> None:
        lineas, siguiente = cast(tuple[list[Linea], int], estado)
        with self._lock:
            self._lineas = list(lineas)
            self._siguiente = siguiente


class AceptacionMemoria:
    """Ledger append-only en memoria: sólo `registrar` y lecturas."""

    def __init__(self) -> None:
        self._aceptaciones: list[Aceptacion] = []
        self._siguiente = 1
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        linea_id: str,
        acepta: bool,
        fecha: datetime,
        canal: str,
        medio: MedioPago | None = None,
        ahora: datetime | None = None,
    ) -> Aceptacion:
        with self._lock:
            aceptacion = Aceptacion(
                id=f"aceptacion-{self._siguiente}",
                tenant_id=tenant_id,
                linea_id=linea_id,
                acepta=acepta,
                fecha=fecha,
                canal=canal,
                medio=medio,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._aceptaciones.append(aceptacion)
            return aceptacion

    def ultima_por_linea(self, *, tenant_id: str, linea_id: str) -> Aceptacion | None:
        for aceptacion in reversed(self._aceptaciones):
            if aceptacion.tenant_id == tenant_id and aceptacion.linea_id == linea_id:
                return aceptacion
        return None

    def listar_por_linea(self, *, tenant_id: str, linea_id: str) -> list[Aceptacion]:
        return [
            a
            for a in self._aceptaciones
            if a.tenant_id == tenant_id and a.linea_id == linea_id
        ]

    def total(self, tenant_id: str) -> int:
        return sum(1 for a in self._aceptaciones if a.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (list(self._aceptaciones), self._siguiente)

    def restaurar(self, estado: object) -> None:
        aceptaciones, siguiente = cast(tuple[list[Aceptacion], int], estado)
        with self._lock:
            self._aceptaciones = list(aceptaciones)
            self._siguiente = siguiente


class CoberturaMemoria:
    """Coberturas declaradas por (tenant, obra social, prestación).

    Registra cada consulta: permite probar que el servicio no consulta una
    cobertura que no corresponde al paciente (M1).
    """

    def __init__(self) -> None:
        self._coberturas: dict[tuple[str, str, str], CoberturaConfigurada] = {}
        self.consultas: list[tuple[str, str | None, str]] = []

    def agregar(
        self,
        tenant_id: str,
        obra_social_id: str,
        prestacion_id: str,
        config: CoberturaConfigurada,
    ) -> None:
        self._coberturas[(tenant_id, obra_social_id, prestacion_id)] = config

    def cobertura(
        self, *, tenant_id: str, obra_social_id: str | None, prestacion_id: str
    ) -> CoberturaConfigurada | None:
        self.consultas.append((tenant_id, obra_social_id, prestacion_id))
        if obra_social_id is None:
            return None
        return self._coberturas.get((tenant_id, obra_social_id, prestacion_id))


class CoberturaSinDatos:
    """Adaptador por defecto de v1: no existe tabla de coberturas (D6).

    Hasta que C-12 cree la tabla, toda línea es 100 % particular visible
    (`origen_cobertura=SIN_COBERTURA`, `validada_en_vivo=false`).
    """

    def __init__(self) -> None:
        self.consultas: list[tuple[str, str | None, str]] = []

    def cobertura(
        self, *, tenant_id: str, obra_social_id: str | None, prestacion_id: str
    ) -> CoberturaConfigurada | None:
        self.consultas.append((tenant_id, obra_social_id, prestacion_id))
        return None


class ImputacionMemoria:
    """Adaptador de caja/agenda que registra las llamadas para los tests.

    `imputar_agenda` no crea turnos: sólo se guarda la intención (M10).
    """

    def __init__(self, *, fallar_caja: bool = False, fallar_agenda: bool = False) -> None:
        self.llamadas_agenda: list[LlamadaAgenda] = []
        self.llamadas_caja: list[LlamadaCaja] = []
        self._fallar_caja = fallar_caja
        self._fallar_agenda = fallar_agenda

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
        if self._fallar_agenda:
            raise RuntimeError("agenda no disponible")
        self.llamadas_agenda.append(
            LlamadaAgenda(
                tenant_id=tenant_id,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                monto_centavos=monto_centavos,
            )
        )

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
        if self._fallar_caja:
            raise RuntimeError("caja no disponible")
        self.llamadas_caja.append(
            LlamadaCaja(
                tenant_id=tenant_id,
                presupuesto_id=presupuesto_id,
                linea_id=linea_id,
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                monto_paciente_centavos=monto_paciente_centavos,
                monto_os_centavos=monto_os_centavos,
                actor_id=actor_id,
                turno_id=turno_id,
                medio=medio,
            )
        )


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


class PacienteMemoria:
    """Existencia de pacientes y su obra social, sin PHI."""

    def __init__(self) -> None:
        self._pacientes: dict[tuple[str, str], str | None] = {}

    def agregar(
        self, tenant_id: str, paciente_id: str, obra_social_id: str | None = None
    ) -> None:
        self._pacientes[(tenant_id, paciente_id)] = obra_social_id

    def existe(self, *, tenant_id: str, paciente_id: str) -> bool:
        return (tenant_id, paciente_id) in self._pacientes

    def obra_social_id(self, *, tenant_id: str, paciente_id: str) -> str | None:
        return self._pacientes.get((tenant_id, paciente_id))


class AuditoriaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionPresupuesto,
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

    def de_accion(self, accion: str) -> list[EntradaAuditoria]:
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

    `bloquear_linea` **simula** el `SELECT ... FOR UPDATE` con un método
    explícito y deja rastro en `bloqueos` para que el test pueda verificar que
    la aceptación lo toma antes de revalidar (D4/B1). Es una simulación
    declarada: sin locks reales no hay garantía de exclusión en memoria.
    """

    def __init__(self, repos: Iterable[_Instantanea], lineas: LineaMemoria) -> None:
        self._repos: tuple[_Instantanea, ...] = tuple(repos)
        self._estados: tuple[object, ...] = ()
        self._lineas = lineas
        self.bloqueos: list[tuple[str, str]] = []

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

    def bloquear_linea(self, *, tenant_id: str, linea_id: str) -> Linea:
        self.bloqueos.append((tenant_id, linea_id))
        return self._lineas.bloquear(tenant_id=tenant_id, linea_id=linea_id)
