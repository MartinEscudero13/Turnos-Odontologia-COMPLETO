"""Puertos (protocolos) y adaptadores en memoria del dominio de lista de espera.

C-07 programa contra estos puertos para no acoplarse a PostgreSQL/Redis ni a la
notificación de C-13. Igual que C-06, el dominio queda testeable sin DB ni red;
el wiring real a SQLAlchemy/Redis es un follow-up explícito.

Reglas duras cumplidas acá:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Los adaptadores en memoria sólo devuelven lo sembrado/escrito por el test.
- Ningún puerto transporta PHI (nombres/teléfonos de pacientes quedan en C-04/C-06).
"""
from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal, Protocol

EstadoEntrada = Literal["PENDIENTE", "OFRECIDO", "CONVERTIDO", "VENCIDO"]
EstadoOferta = Literal["PENDIENTE", "ACEPTADA", "VENCIDA", "CANCELADA"]

AccionListaEspera = Literal[
    "ALTA", "BAJA", "OFRECIDO", "OFERTA_VENCIDA", "OFERTA_ACEPTADA", "OFERTA_CANCELADA",
]


class EntradaDuplicada(Exception):
    """Ya existe una entrada activa para (paciente, prestación) en el tenant."""


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entrada:
    id: str
    tenant_id: str
    paciente_id: str
    prestacion_id: str
    estado: EstadoEntrada
    creado_en: datetime
    profesional_pref: str | None = None
    ventana_desde: datetime | None = None
    ventana_hasta: datetime | None = None


@dataclass(frozen=True)
class Oferta:
    id: str
    tenant_id: str
    entrada_id: str
    hueco_turno_id: str | None
    expira_at: datetime
    estado: EstadoOferta
    token: str
    creado_en: datetime


@dataclass(frozen=True)
class HuecoRetenido:
    """Hueco retenido por una oferta vigente (slot del turno liberado)."""

    tenant_id: str
    hueco_turno_id: str
    profesional_id: str
    sillon_id: str
    inicio: datetime
    fin: datetime


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    accion: AccionListaEspera
    actor: str
    entrada_id: str | None
    oferta_id: str | None
    turno_id: str | None
    estado_antes: str | None
    estado_despues: str | None
    registrado_en: str


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class ListaEsperaRepositorio(Protocol):
    def alta(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        prestacion_id: str,
        profesional_pref: str | None = None,
        ventana_desde: datetime | None = None,
        ventana_hasta: datetime | None = None,
        ahora: datetime | None = None,
    ) -> Entrada: ...

    def baja(self, *, tenant_id: str, entrada_id: str, ahora: datetime | None = None) -> Entrada: ...

    def listar(
        self,
        *,
        tenant_id: str,
        prestacion_id: str | None = None,
        profesional_id: str | None = None,
    ) -> list[Entrada]: ...

    def compatibles(
        self,
        *,
        tenant_id: str,
        prestacion_id: str,
        profesional_id: str,
        inicio: datetime,
        ahora: datetime | None = None,
    ) -> list[Entrada]: ...

    def obtener(self, *, tenant_id: str, entrada_id: str) -> Entrada | None: ...

    def buscar_activa(
        self, *, tenant_id: str, paciente_id: str, prestacion_id: str
    ) -> Entrada | None: ...

    def cambiar_estado(
        self, *, tenant_id: str, entrada_id: str, estado: EstadoEntrada
    ) -> Entrada: ...


class OfertaRepositorio(Protocol):
    def crear(
        self,
        *,
        tenant_id: str,
        entrada_id: str,
        hueco_turno_id: str | None,
        expira_at: datetime,
        token: str,
        ahora: datetime | None = None,
    ) -> Oferta: ...

    def por_token(self, *, tenant_id: str, token: str) -> Oferta | None: ...

    def vigente_para(self, *, tenant_id: str, hueco_turno_id: str) -> Oferta | None: ...

    def vigente_para_entrada(self, *, tenant_id: str, entrada_id: str) -> Oferta | None: ...

    def pendientes(self, *, tenant_id: str) -> list[Oferta]: ...

    def vencidas(self, *, tenant_id: str, ahora: datetime) -> list[Oferta]: ...

    def entradas_ofertadas(self, *, tenant_id: str, hueco_turno_id: str) -> set[str]: ...

    def aceptar(self, *, tenant_id: str, token: str, ahora: datetime) -> Oferta | None: ...

    def marcar(self, *, tenant_id: str, oferta_id: str, estado: EstadoOferta) -> Oferta: ...

    def cancelar(self, *, tenant_id: str, oferta_id: str) -> Oferta: ...


class OfertaPort(Protocol):
    def huecos_retenidos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[HuecoRetenido]: ...


class HuecoLiberadoPort(Protocol):
    def emitir(self, *, tenant_id: str, turno_id: str) -> None: ...


class NotificadorPort(Protocol):
    def oferta_emitida(self, *, tenant_id: str, oferta_id: str) -> None: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionListaEspera,
        actor: str,
        entrada_id: str | None = None,
        oferta_id: str | None = None,
        turno_id: str | None = None,
        estado_antes: str | None = None,
        estado_despues: str | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------

_ESTADOS_ACTIVOS: frozenset[str] = frozenset({"PENDIENTE", "OFRECIDO"})


def _ahora(ahora: datetime | None) -> datetime:
    return ahora if ahora is not None else datetime.now(UTC)


class ListaEsperaMemoria:
    """Entradas de lista de espera en memoria, scoped por (tenant, id)."""

    def __init__(self) -> None:
        self._entradas: dict[str, Entrada] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def alta(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        prestacion_id: str,
        profesional_pref: str | None = None,
        ventana_desde: datetime | None = None,
        ventana_hasta: datetime | None = None,
        ahora: datetime | None = None,
    ) -> Entrada:
        with self._lock:
            if self.buscar_activa(
                tenant_id=tenant_id, paciente_id=paciente_id, prestacion_id=prestacion_id
            ) is not None:
                raise EntradaDuplicada("entrada activa ya existe")
            entrada = Entrada(
                id=f"entrada-{self._siguiente}",
                tenant_id=tenant_id,
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                estado="PENDIENTE",
                creado_en=_ahora(ahora),
                profesional_pref=profesional_pref,
                ventana_desde=ventana_desde,
                ventana_hasta=ventana_hasta,
            )
            self._siguiente += 1
            self._entradas[entrada.id] = entrada
            return entrada

    def baja(self, *, tenant_id: str, entrada_id: str, ahora: datetime | None = None) -> Entrada:
        del ahora
        with self._lock:
            actual = self._entradas[entrada_id]
            if actual.tenant_id != tenant_id:
                raise KeyError(entrada_id)
            retirada = replace(actual, estado="VENCIDO")
            self._entradas[entrada_id] = retirada
            return retirada

    def listar(
        self,
        *,
        tenant_id: str,
        prestacion_id: str | None = None,
        profesional_id: str | None = None,
    ) -> list[Entrada]:
        resultado = [
            e
            for e in self._entradas.values()
            if e.tenant_id == tenant_id
            and e.estado in _ESTADOS_ACTIVOS
            and (prestacion_id is None or e.prestacion_id == prestacion_id)
            and (
                profesional_id is None
                or e.profesional_pref is None
                or e.profesional_pref == profesional_id
            )
        ]
        resultado.sort(key=lambda e: (e.creado_en, e.id))
        return resultado

    def compatibles(
        self,
        *,
        tenant_id: str,
        prestacion_id: str,
        profesional_id: str,
        inicio: datetime,
        ahora: datetime | None = None,
    ) -> list[Entrada]:
        del ahora
        resultado = [
            e
            for e in self._entradas.values()
            if e.tenant_id == tenant_id
            and e.estado == "PENDIENTE"
            and e.prestacion_id == prestacion_id
            and (e.profesional_pref is None or e.profesional_pref == profesional_id)
            and (e.ventana_desde is None or e.ventana_desde <= inicio)
            and (e.ventana_hasta is None or e.ventana_hasta > inicio)
        ]
        resultado.sort(key=lambda e: (e.creado_en, e.id))
        return resultado

    def obtener(self, *, tenant_id: str, entrada_id: str) -> Entrada | None:
        e = self._entradas.get(entrada_id)
        if e is None or e.tenant_id != tenant_id:
            return None
        return e

    def buscar_activa(
        self, *, tenant_id: str, paciente_id: str, prestacion_id: str
    ) -> Entrada | None:
        for e in self._entradas.values():
            if (
                e.tenant_id == tenant_id
                and e.paciente_id == paciente_id
                and e.prestacion_id == prestacion_id
                and e.estado in _ESTADOS_ACTIVOS
            ):
                return e
        return None

    def cambiar_estado(
        self, *, tenant_id: str, entrada_id: str, estado: EstadoEntrada
    ) -> Entrada:
        with self._lock:
            actual = self._entradas[entrada_id]
            if actual.tenant_id != tenant_id:
                raise KeyError(entrada_id)
            cambiada = replace(actual, estado=estado)
            self._entradas[entrada_id] = cambiada
            return cambiada

    def total(self, tenant_id: str) -> int:
        return sum(1 for e in self._entradas.values() if e.tenant_id == tenant_id)


class OfertaMemoria:
    """Ofertas en memoria con reclamo atómico (`aceptar`) para la doble aceptación."""

    def __init__(self) -> None:
        self._ofertas: dict[str, Oferta] = {}
        self._siguiente = 1
        self._lock = threading.Lock()

    def crear(
        self,
        *,
        tenant_id: str,
        entrada_id: str,
        hueco_turno_id: str | None,
        expira_at: datetime,
        token: str,
        ahora: datetime | None = None,
    ) -> Oferta:
        with self._lock:
            oferta = Oferta(
                id=f"oferta-{self._siguiente}",
                tenant_id=tenant_id,
                entrada_id=entrada_id,
                hueco_turno_id=hueco_turno_id,
                expira_at=expira_at,
                estado="PENDIENTE",
                token=token,
                creado_en=_ahora(ahora),
            )
            self._siguiente += 1
            self._ofertas[oferta.id] = oferta
            return oferta

    def por_token(self, *, tenant_id: str, token: str) -> Oferta | None:
        for o in self._ofertas.values():
            if o.tenant_id == tenant_id and o.token == token:
                return o
        return None

    def vigente_para(self, *, tenant_id: str, hueco_turno_id: str) -> Oferta | None:
        for o in self._ofertas.values():
            if (
                o.tenant_id == tenant_id
                and o.hueco_turno_id == hueco_turno_id
                and o.estado == "PENDIENTE"
            ):
                return o
        return None

    def vigente_para_entrada(self, *, tenant_id: str, entrada_id: str) -> Oferta | None:
        for o in self._ofertas.values():
            if o.tenant_id == tenant_id and o.entrada_id == entrada_id and o.estado == "PENDIENTE":
                return o
        return None

    def pendientes(self, *, tenant_id: str) -> list[Oferta]:
        return [o for o in self._ofertas.values() if o.tenant_id == tenant_id and o.estado == "PENDIENTE"]

    def vencidas(self, *, tenant_id: str, ahora: datetime) -> list[Oferta]:
        return [
            o
            for o in self._ofertas.values()
            if o.tenant_id == tenant_id and o.estado == "PENDIENTE" and o.expira_at <= ahora
        ]

    def entradas_ofertadas(self, *, tenant_id: str, hueco_turno_id: str) -> set[str]:
        return {
            o.entrada_id
            for o in self._ofertas.values()
            if o.tenant_id == tenant_id and o.hueco_turno_id == hueco_turno_id
        }

    def aceptar(self, *, tenant_id: str, token: str, ahora: datetime) -> Oferta | None:
        with self._lock:
            o = self.por_token(tenant_id=tenant_id, token=token)
            if o is None or o.estado != "PENDIENTE" or o.expira_at <= ahora:
                return None
            aceptada = replace(o, estado="ACEPTADA")
            self._ofertas[o.id] = aceptada
            return aceptada

    def marcar(self, *, tenant_id: str, oferta_id: str, estado: EstadoOferta) -> Oferta:
        with self._lock:
            o = self._ofertas[oferta_id]
            if o.tenant_id != tenant_id:
                raise KeyError(oferta_id)
            marcada = replace(o, estado=estado)
            self._ofertas[oferta_id] = marcada
            return marcada

    def cancelar(self, *, tenant_id: str, oferta_id: str) -> Oferta:
        return self.marcar(tenant_id=tenant_id, oferta_id=oferta_id, estado="CANCELADA")

    def total(self, tenant_id: str) -> int:
        return sum(1 for o in self._ofertas.values() if o.tenant_id == tenant_id)


class OfertaPortMemoria:
    """Consulta de huecos retenidos resolviendo el slot desde un `slot_resolver`."""

    def __init__(
        self,
        ofertas: OfertaRepositorio,
        slot_resolver: Callable[[str, str], HuecoRetenido | None],
    ) -> None:
        self._ofertas = ofertas
        self._slot_resolver = slot_resolver

    def huecos_retenidos(
        self, *, tenant_id: str, desde: datetime, hasta: datetime
    ) -> list[HuecoRetenido]:
        resultado: list[HuecoRetenido] = []
        for o in self._ofertas.pendientes(tenant_id=tenant_id):
            if o.hueco_turno_id is None:
                continue
            slot = self._slot_resolver(tenant_id, o.hueco_turno_id)
            if slot is not None and slot.inicio < hasta and slot.fin > desde:
                resultado.append(slot)
        return resultado


class HuecoLiberadoMemoria:
    """`HuecoLiberadoPort` síncrono e idempotente (clave `auto_oferta:{turno_id}`).

    Modela el SETNX de Redis en memoria: una sola emisión por turno liberado y
    despacho directo al handler (el worker) cuando se inyecta.
    """

    def __init__(self, handler: Callable[[str, str], None] | None = None) -> None:
        self._handler = handler
        self._vistos: set[str] = set()
        self.eventos: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def emitir(self, *, tenant_id: str, turno_id: str) -> None:
        clave = f"auto_oferta:{turno_id}"
        with self._lock:
            if clave in self._vistos:
                return
            self._vistos.add(clave)
            self.eventos.append((tenant_id, turno_id))
        if self._handler is not None:
            self._handler(tenant_id, turno_id)


class NotificadorNulo:
    """Notificador no-op hasta C-13 (WA/email)."""

    def oferta_emitida(self, *, tenant_id: str, oferta_id: str) -> None:
        del tenant_id, oferta_id
        return None


class AuditoriaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionListaEspera,
        actor: str,
        entrada_id: str | None = None,
        oferta_id: str | None = None,
        turno_id: str | None = None,
        estado_antes: str | None = None,
        estado_despues: str | None = None,
    ) -> None:
        with self._lock:
            self.entradas.append(
                EntradaAuditoria(
                    tenant_id=tenant_id,
                    accion=accion,
                    actor=actor,
                    entrada_id=entrada_id,
                    oferta_id=oferta_id,
                    turno_id=turno_id,
                    estado_antes=estado_antes,
                    estado_despues=estado_despues,
                    registrado_en=datetime.now(UTC).isoformat(),
                )
            )

    def de_tenant(self, tenant_id: str) -> list[EntradaAuditoria]:
        return [e for e in self.entradas if e.tenant_id == tenant_id]
