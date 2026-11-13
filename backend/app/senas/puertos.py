"""Puertos, entidades y adaptadores en memoria de señas — C-11 §3.

El dominio de señas programa contra estos protocolos para no acoplarse a
PostgreSQL ni a la identidad de C-03/C-04/C-05. Igual que C-06…C-10, el wiring
real a SQLAlchemy es un follow-up declarado; los tests de migración cubren
CHECKs, UNIQUE, RLS, grants y los locks reales.

Reglas duras:

- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Montos enteros en centavos; instantes *aware* (RN-GL-03, offset `-03:00`).
- Unicidad global de `mp_payment_id` y `token_hash` (RN-SE-03): no se acotan al
  tenant y ninguna lectura cross-tenant se usa para decidir; la colisión se
  resuelve en el `INSERT` (F-04/F-05).
- `transicionar` es **condicional** (`desde` → `hacia`): si el estado esperado
  no coincide devuelve `None` y no escribe. Los locks reales (`SELECT … FOR
  UPDATE`) viven en el adaptador SQL y se prueban con dos conexiones a
  PostgreSQL (D11): en memoria no hay garantía de concurrencia.
- La frontera de red es **sólo** `PasarelaPagosPort`. `AdaptadorPasarelaFake`
  es determinista y no abre sockets; ningún test usa el adaptador HTTP.
- Sin PHI: las entidades sólo llevan ids, estados, montos e instantes.

`Sena.turno_inicio` es un metadato de proyección (join con `turnos`) para poder
filtrar el listado por `turno.inicio` (C11-OQ-10) sin depender de la fecha de
creación ni de `expira_at`; no es una columna de `senas`.
"""
from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from types import TracebackType
from typing import Any, Literal, Protocol, cast, runtime_checkable

from app.senas.regla import ModoSena, PrestacionSena
from app.turnos.servicio import NoEncontrado, TurnoError

__all__ = [
    "AccionSena",
    "AdaptadorPasarelaFake",
    "AplicacionCajaMemoria",
    "AplicacionCajaPort",
    "AuditoriaPort",
    "AuditoriaSenaMemoria",
    "ConceptoAplicacion",
    "ConfiguracionSenaMemoria",
    "ConfiguracionSenaPort",
    "ContadorSenaPort",
    "EntradaAuditoriaSena",
    "EstadoPagoMP",
    "EstadoPreferencia",
    "EstadoSena",
    "MedioPagoMP",
    "MedioPagoMP",
    "MovimientoRef",
    "PagoExterno",
    "PagoMP",
    "PagoMPMemoria",
    "PagoMPRepositorio",
    "PagoNoEncontrado",
    "PasarelaNoDisponible",
    "PasarelaPagosPort",
    "PoliticaSena",
    "Preferencia",
    "PresupuestosMemoria",
    "PresupuestosPort",
    "MOTIVO_CANCELACION",
    "MOTIVO_POLITICA_CANCELACION",
    "Reloj",
    "ResolutorTenantPort",
    "ResultadoPagoMP",
    "Sena",
    "SenaCreada",
    "SenaDuplicada",
    "SenaInvalida",
    "SenaMemoria",
    "SenaPort",
    "SenaRepositorio",
    "SenaCancelacionPort",
    "SenaReprogramacionPort",
    "SenaTransferida",
    "TokenDuplicado",
    "TransaccionNula",
    "TransicionTurnoInvalida",
    "TurnoMemoriaSena",
    "TurnoPort",
    "TurnoRef",
    "UnidadDeTrabajoMemoria",
    "UnidadDeTrabajoPort",
    "rango_estado",
]

EstadoSena = Literal["PENDIENTE", "ACREDITADA", "LIBERADA", "APLICADA", "DEVUELTA"]
EstadoPreferencia = Literal["POR_CREAR", "CREADA", "FALLIDA"]
EstadoPagoMP = Literal[
    "APPROVED", "PENDING", "IN_PROCESS", "REJECTED", "CANCELLED", "REFUNDED", "OTHER"
]
ResultadoPagoMP = Literal[
    "ACREDITADA",
    "DEVUELTA",
    "IGNORADO",
    "MONTO_DISTINTO",
    "PAGO_EXCEDENTE",
    "TURNO_NO_CONFIRMABLE",
    "FUERA_DE_TIEMPO",
    "DUPLICADO",
    "REEMBOLSADO",
    "REEMBOLSO_AJUSTE_CAJA",
]
ConceptoAplicacion = Literal["TRATAMIENTO", "CANCELACION_TARDIA"]
MedioPagoMP = Literal["MP"]

# D12: motivos fijos de la devolución/liberación ordenada por la política.
MOTIVO_POLITICA_CANCELACION = "POLITICA_CANCELACION"
MOTIVO_CANCELACION = "CANCELACION"

AccionSena = Literal[
    "SENA_CREADA",
    "SENA_PREFERENCIA_CREADA",
    "SENA_PREFERENCIA_FALLIDA",
    "SENA_ACREDITADA",
    "SENA_LIBERADA",
    "SENA_APLICADA",
    "SENA_DEVUELTA",
    "SENA_REEMBOLSO_MP",
    "SENA_TRANSFERIDA",
    "SENA_NO_TRANSFERIDA",
    "SENA_WEBHOOK_RECHAZADO",
]

Reloj = Callable[[], datetime]

# D3: el estado informado por MP no retrocede. El ranking sólo decide si se
# actualiza la columna `estado`; nunca revierte un efecto ya aplicado.
_RANKING_ESTADO: dict[EstadoPagoMP, int] = {
    "APPROVED": 6,
    "REFUNDED": 5,
    "IN_PROCESS": 4,
    "PENDING": 3,
    "REJECTED": 2,
    "CANCELLED": 1,
    "OTHER": 0,
}


def rango_estado(estado: EstadoPagoMP) -> int:
    """Peso del estado de MP: un `PENDING` posterior no degrada un `APPROVED`."""
    return _RANKING_ESTADO[estado]


# ---------------------------------------------------------------------------
# Entidades
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sena:
    """Obligación de pago de una reserva (espeja `senas`, D2)."""

    id: str
    tenant_id: str
    turno_id: str
    monto_centavos: int
    estado: EstadoSena
    regla_modo: ModoSena
    regla_valor: int
    precio_base_centavos: int
    anticipacion_cancelacion_h: int
    expira_at: datetime
    token_hash: str
    creado_en: datetime
    mp_preference_id: str | None = None
    mp_init_point: str | None = None
    preferencia_estado: EstadoPreferencia = "POR_CREAR"
    intentos_preferencia: int = 0
    proximo_reintento_at: datetime | None = None
    token_rotado_en: datetime | None = None
    acreditada_en: datetime | None = None
    aplicada_en: datetime | None = None
    liberada_en: datetime | None = None
    devuelta_en: datetime | None = None
    motivo_liberacion: str | None = None
    concepto_aplicacion: ConceptoAplicacion | None = None
    devuelta_por: str | None = None
    motivo_devolucion: str | None = None
    movimiento_caja_id: str | None = None
    # Metadatos de proyección (join con `turnos`), no columnas de `senas`:
    # permiten el listado por `turno.inicio` (C11-OQ-10) y la vista pública.
    turno_inicio: datetime | None = None
    turno_fin: datetime | None = None
    turno_prestacion: str | None = None


@dataclass(frozen=True)
class PagoMP:
    """Un pago notificado por MP (espeja `pagos_mp`, D3)."""

    id: str
    tenant_id: str
    mp_payment_id: str
    sena_id: str
    monto_centavos: int
    moneda: str
    estado: EstadoPagoMP
    resultado: ResultadoPagoMP
    raw_json: Mapping[str, Any]
    recibido_en: datetime
    actualizado_en: datetime
    aprobado_en: datetime | None = None


@dataclass(frozen=True)
class Preferencia:
    """Preferencia de checkout creada en Mercado Pago."""

    mp_preference_id: str
    init_point: str


@dataclass(frozen=True)
class PagoExterno:
    """Pago tal como lo devuelve la re-consulta a Mercado Pago (D7)."""

    mp_payment_id: str
    estado: EstadoPagoMP
    monto_centavos: int
    moneda: str
    external_reference: str | None
    metadata: Mapping[str, str]
    aprobado_en: datetime | None = None


@dataclass(frozen=True)
class TurnoRef:
    """Vista mínima del turno que C-11 necesita (C-05 es el dueño).

    `paciente_id` sólo se usa para el guard de presupuesto aceptado vigente de
    C-09 (C11-OQ-13): no se expone en ninguna vista pública ni se loguea.
    """

    id: str
    tenant_id: str
    estado: str
    inicio: datetime
    fin: datetime
    paciente_id: str | None = None


@dataclass(frozen=True)
class MovimientoRef:
    """Movimiento de caja creado por el alta de C-10 (`INGRESO`/`MP`)."""

    id: str
    tenant_id: str
    turno_id: str
    monto_centavos: int
    medio: MedioPagoMP
    tipo: Literal["INGRESO"]
    fecha: date
    actor_id: str
    concepto: ConceptoAplicacion


@dataclass(frozen=True)
class EntradaAuditoriaSena:
    tenant_id: str
    accion: AccionSena
    actor: str
    entidad: str
    entidad_id: str
    antes: Mapping[str, Any] | None
    despues: Mapping[str, Any] | None
    registrado_en: str


@dataclass(frozen=True)
class PoliticaSena:
    """Política visible al reservar y al pagar (D12, F-01).

    `reembolsable` es **la promesa** y vale `True` desde la creación; no depende
    del estado de la seña. `hay_pago_acreditado` es el hecho actual: sólo
    `True` con la seña `ACREDITADA`.
    """

    anticipacion_cancelacion_h: int
    reembolsable: bool = True
    hay_pago_acreditado: bool = False


@dataclass(frozen=True)
class SenaCreada:
    """Resultado del alta: la seña, el token en claro (una sola vez) y la política."""

    sena: Sena
    token_sena: str
    politica: PoliticaSena


@dataclass(frozen=True)
class SenaTransferida:
    """Resultado de una reprogramación sobre la seña (C11-OQ-04, F-16).

    `token_sena` sólo trae valor cuando el token anterior había vencido y se
    reemitió uno nuevo; el token anterior deja de resolver (`404`).
    """

    sena: Sena
    token_sena: str | None = None
    token_reemitido: bool = False


# ---------------------------------------------------------------------------
# Errores de dominio y de infraestructura
# ---------------------------------------------------------------------------


class SenaInvalida(Exception):
    """Datos inválidos para crear o aplicar una seña (no persiste nada)."""


class SenaDuplicada(Exception):
    """El turno ya tiene seña (`UNIQUE (tenant_id, turno_id)`)."""


class TokenDuplicado(Exception):
    """El `token_hash` ya existe (`UNIQUE (token_hash)`, global)."""


class PasarelaNoDisponible(Exception):
    """La pasarela no responde o está caída (RN-IN-03: no se pierde nada)."""


class PagoNoEncontrado(Exception):
    """Mercado Pago no conoce el id de pago consultado."""


class TransicionTurnoInvalida(TurnoError):
    """`409` — el turno no está en el estado que habilita la transición.

    `confirmar_por_sena` sólo actúa desde `PENDIENTE` y `cancelar_por_sena`
    también: un turno en un estado final (`PRESENTE`, `AUSENTE`, `CANCELADO`, …)
    no se confirma ni se cancela por la vía de la seña (F-21).
    """

    codigo = 409
    codigo_dominio = "TRANSICION_TURNO_INVALIDA"


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class ResolutorTenantPort(Protocol):
    """Resuelve el `{tokenTenant}` (slug público) a `tenant_id` (mismo C-06)."""

    def resolver(self, token_tenant: str) -> str | None: ...


class ContadorSenaPort(Protocol):
    """Rate-limit público de C-06 (`ContadorPort`), reusado sin cambios."""

    def incrementar(self, clave: str, ventana_s: int) -> int: ...

    def ttl_s(self, clave: str) -> int: ...


class ConfiguracionSenaPort(Protocol):
    """Lectura de los dos niveles de la regla (D1): prestación y tenant."""

    def parametros(self, *, tenant_id: str) -> Mapping[str, Any]: ...

    def prestacion(
        self, *, tenant_id: str, prestacion_id: str
    ) -> PrestacionSena | None: ...


class SenaPort(Protocol):
    """Enganche desde C-06: crea la seña si la regla efectiva la exige."""

    def crear_si_corresponde(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        prestacion_id: str,
        turno_inicio: datetime,
        turno_fin: datetime | None = None,
        ahora: datetime | None = None,
    ) -> SenaCreada | None: ...


@runtime_checkable
class SenaCancelacionPort(Protocol):
    """Efecto de C-11 en la cancelación de C-06 (RN-SE-04, D12).

    C-06 decide si la cancelación procede; C-11 sólo aplica el efecto sobre la
    seña con el **snapshot** de la política. `anticipacion_de_sena` devuelve el
    snapshot guardado (`None` si el turno no tiene seña) para que C-06 autorice
    con la misma regla que después ejecuta la devolución (`F-19`).
    """

    def anticipacion_de_sena(self, *, tenant_id: str, turno_id: str) -> int | None: ...

    def cancelar_con_sena(
        self, *, tenant_id: str, turno_id: str, ahora: datetime | None = None
    ) -> Sena | None: ...


@runtime_checkable
class SenaReprogramacionPort(Protocol):
    """Transferencia de la seña al turno nuevo (C11-OQ-04, F-16)."""

    def transferir_a_turno(
        self,
        *,
        tenant_id: str,
        turno_anterior: str,
        turno_nuevo: str,
        turno_inicio: datetime,
        turno_fin: datetime | None = None,
        ahora: datetime | None = None,
    ) -> SenaTransferida | None: ...


class SenaRepositorio(Protocol):
    def crear(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        monto_centavos: int,
        regla_modo: ModoSena,
        regla_valor: int,
        precio_base_centavos: int,
        anticipacion_cancelacion_h: int,
        expira_at: datetime,
        token_hash: str,
        ahora: datetime | None = None,
        turno_inicio: datetime | None = None,
        turno_fin: datetime | None = None,
        turno_prestacion: str | None = None,
    ) -> Sena: ...

    def obtener(self, *, tenant_id: str, sena_id: str) -> Sena | None: ...

    def por_turno(self, *, tenant_id: str, turno_id: str) -> Sena | None: ...

    def por_token(self, *, tenant_id: str, token_hash: str) -> Sena | None: ...

    def listar(
        self,
        *,
        tenant_id: str,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[Sena]: ...

    def vencidas(self, *, tenant_id: str, ahora: datetime) -> list[Sena]: ...

    def bloquear(self, *, tenant_id: str, sena_id: str) -> Sena: ...

    def transicionar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        desde: EstadoSena,
        hacia: EstadoSena,
        campos: Mapping[str, Any] | None = None,
    ) -> Sena | None: ...

    def actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        campos: Mapping[str, Any],
        desde: EstadoSena | None = None,
    ) -> Sena | None: ...

    def reemitir_token(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        token_hash: str,
        ahora: datetime | None = None,
    ) -> Sena: ...


class UnidadDeTrabajoPort(Protocol):
    """Unidad de trabajo que la expiración y el webhook abren por operación.

    En PostgreSQL es `TransaccionSQL(session)` (commit si es la más externa); en
    memoria, `UnidadDeTrabajoMemoria` restaura la instantánea si algo falla. La
    atomicidad del release (seña + turno + evento de hueco) depende de esto
    (D10/F-14).
    """

    def __enter__(self) -> object: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...


class PagoMPRepositorio(Protocol):
    def registrar_o_actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        mp_payment_id: str,
        monto_centavos: int,
        moneda: str,
        estado: EstadoPagoMP,
        resultado: ResultadoPagoMP | None = None,
        raw_json: Mapping[str, Any],
        aprobado_en: datetime | None = None,
        ahora: datetime | None = None,
    ) -> PagoMP: ...

    def obtener(self, *, tenant_id: str, mp_payment_id: str) -> PagoMP | None: ...

    def listar(self, *, tenant_id: str, sena_id: str | None = None) -> list[PagoMP]: ...


class PasarelaPagosPort(Protocol):
    """Única frontera con la red (D5). Los tests usan el adaptador fake."""

    def crear_preferencia(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        turno_id: str,
        monto_centavos: int,
        descripcion: str,
        expira_at: datetime,
        url_pago: str,
        url_webhook: str,
    ) -> Preferencia: ...

    def obtener_pago(self, *, mp_payment_id: str) -> PagoExterno: ...


class AplicacionCajaPort(Protocol):
    """Aplicación al cobro vía el alta de C-10 (D9); C-11 no escribe caja."""

    def registrar_ingreso_mp(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        monto_centavos: int,
        fecha: date,
        actor_id: str,
        concepto: str,
    ) -> MovimientoRef: ...


class PresupuestosPort(Protocol):
    """Sólo lectura sobre C-09 para el guard de presupuesto aceptado."""

    def aceptado_vigente(
        self, *, tenant_id: str, paciente_id: str, ahora: datetime
    ) -> bool: ...


class TurnoPort(Protocol):
    """Extensión mínima de C-05: confirmar/cancelar por seña."""

    def confirmar_por_sena(
        self, *, tenant_id: str, turno_id: str, ahora: datetime
    ) -> None: ...

    def cancelar_por_sena(
        self, *, tenant_id: str, turno_id: str, motivo: str, ahora: datetime
    ) -> None: ...

    def turno_de(self, *, tenant_id: str, turno_id: str) -> TurnoRef | None: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionSena,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: Mapping[str, Any] | None = None,
        despues: Mapping[str, Any] | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


def _ahora(ahora: datetime | None, reloj: Reloj | None = None) -> datetime:
    if ahora is not None:
        return ahora
    if reloj is not None:
        return reloj()
    return datetime.now(UTC)


class SenaMemoria:
    """Señas en memoria scoped por tenant; espeja los UNIQUE de la migración 009."""

    def __init__(self, *, reloj: Reloj | None = None) -> None:
        self._senas: dict[str, Sena] = {}
        self._siguiente = 1
        self._lock = threading.Lock()
        self._reloj = reloj
        self.bloqueos: list[tuple[str, str]] = []

    # -- lectura --------------------------------------------------------

    def obtener(self, *, tenant_id: str, sena_id: str) -> Sena | None:
        sena = self._senas.get(sena_id)
        if sena is None or sena.tenant_id != tenant_id:
            return None
        return sena

    def por_turno(self, *, tenant_id: str, turno_id: str) -> Sena | None:
        for sena in self._senas.values():
            if sena.tenant_id == tenant_id and sena.turno_id == turno_id:
                return sena
        return None

    def por_token(self, *, tenant_id: str, token_hash: str) -> Sena | None:
        for sena in self._senas.values():
            if sena.tenant_id == tenant_id and sena.token_hash == token_hash:
                return sena
        return None

    def listar(
        self,
        *,
        tenant_id: str,
        desde: datetime | None = None,
        hasta: datetime | None = None,
    ) -> list[Sena]:
        def en_rango(sena: Sena) -> bool:
            # C11-OQ-10: el rango es sobre `turno.inicio`, no sobre `creado_en`.
            referencia = sena.turno_inicio if sena.turno_inicio is not None else sena.creado_en
            if desde is not None and referencia < desde:
                return False
            return not (hasta is not None and referencia >= hasta)

        return sorted(
            (s for s in self._senas.values() if s.tenant_id == tenant_id and en_rango(s)),
            key=lambda s: (s.turno_inicio or s.creado_en, s.id),
        )

    def vencidas(self, *, tenant_id: str, ahora: datetime) -> list[Sena]:
        return sorted(
            (
                s
                for s in self._senas.values()
                if s.tenant_id == tenant_id
                and s.estado == "PENDIENTE"
                and s.expira_at <= ahora
            ),
            key=lambda s: (s.expira_at, s.id),
        )

    # -- escritura ------------------------------------------------------

    def crear(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        monto_centavos: int,
        regla_modo: ModoSena,
        regla_valor: int,
        precio_base_centavos: int,
        anticipacion_cancelacion_h: int,
        expira_at: datetime,
        token_hash: str,
        ahora: datetime | None = None,
        turno_inicio: datetime | None = None,
        turno_fin: datetime | None = None,
        turno_prestacion: str | None = None,
    ) -> Sena:
        if monto_centavos <= 0:
            raise SenaInvalida("el monto de la seña debe ser positivo")
        if regla_modo == "SIN_SENA":
            raise SenaInvalida("SIN_SENA no genera fila de seña")
        if not token_hash:
            raise SenaInvalida("la seña exige token")
        with self._lock:
            for existente in self._senas.values():
                if existente.token_hash == token_hash:
                    raise TokenDuplicado("el token_hash ya existe")
                if existente.tenant_id == tenant_id and existente.turno_id == turno_id:
                    raise SenaDuplicada("el turno ya tiene seña")
            momento = _ahora(ahora, self._reloj)
            sena = Sena(
                id=f"sena-{self._siguiente}",
                tenant_id=tenant_id,
                turno_id=turno_id,
                monto_centavos=monto_centavos,
                estado="PENDIENTE",
                regla_modo=regla_modo,
                regla_valor=regla_valor,
                precio_base_centavos=precio_base_centavos,
                anticipacion_cancelacion_h=anticipacion_cancelacion_h,
                expira_at=expira_at,
                token_hash=token_hash,
                creado_en=momento,
                turno_inicio=turno_inicio,
                turno_fin=turno_fin,
                turno_prestacion=turno_prestacion,
            )
            self._siguiente += 1
            self._senas[sena.id] = sena
            return sena

    def bloquear(self, *, tenant_id: str, sena_id: str) -> Sena:
        """Simula `SELECT … FOR UPDATE`; la garantía real es de PostgreSQL."""
        sena = self.obtener(tenant_id=tenant_id, sena_id=sena_id)
        if sena is None:
            raise NoEncontrado("seña no encontrada")
        self.bloqueos.append((tenant_id, sena_id))
        return sena

    def transicionar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        desde: EstadoSena,
        hacia: EstadoSena,
        campos: Mapping[str, Any] | None = None,
    ) -> Sena | None:
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, sena_id=sena_id)
            if actual is None or actual.estado != desde:
                return None
            datos: dict[str, Any] = dict(campos or {})
            datos["estado"] = hacia
            nueva = replace(actual, **datos)
            self._senas[sena_id] = nueva
            return nueva

    def actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        campos: Mapping[str, Any],
        desde: EstadoSena | None = None,
    ) -> Sena | None:
        """Update condicional de columnas mutables (preferencia/token).

        No cambia `estado` (eso es `transicionar`) y devuelve `None` si el guard
        `desde` no coincide, igual que la transición condicional de D11.
        """
        datos: dict[str, Any] = dict(campos)
        if "estado" in datos:
            raise SenaInvalida("usá transicionar para cambiar el estado")
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, sena_id=sena_id)
            if actual is None:
                raise NoEncontrado("seña no encontrada")
            if desde is not None and actual.estado != desde:
                return None
            nueva = replace(actual, **datos)
            self._senas[sena_id] = nueva
            return nueva

    def reemitir_token(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        token_hash: str,
        ahora: datetime | None = None,
    ) -> Sena:
        if not token_hash:
            raise SenaInvalida("la seña exige token")
        with self._lock:
            actual = self.obtener(tenant_id=tenant_id, sena_id=sena_id)
            if actual is None:
                raise NoEncontrado("seña no encontrada")
            for existente in self._senas.values():
                if existente.id != sena_id and existente.token_hash == token_hash:
                    raise TokenDuplicado("el token_hash ya existe")
            nueva = replace(
                actual,
                token_hash=token_hash,
                token_rotado_en=_ahora(ahora, self._reloj),
            )
            self._senas[sena_id] = nueva
            return nueva

    def total(self, tenant_id: str) -> int:
        return sum(1 for s in self._senas.values() if s.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._senas), self._siguiente)

    def restaurar(self, estado: object) -> None:
        senas, siguiente = cast(tuple[dict[str, Sena], int], estado)
        with self._lock:
            self._senas = dict(senas)
            self._siguiente = siguiente


class PagoMPMemoria:
    """Libro de idempotencia en memoria: `mp_payment_id` único **global**."""

    def __init__(self, *, reloj: Reloj | None = None) -> None:
        self._pagos: dict[str, PagoMP] = {}
        self._siguiente = 1
        self._lock = threading.Lock()
        self._reloj = reloj

    def obtener(self, *, tenant_id: str, mp_payment_id: str) -> PagoMP | None:
        for pago in self._pagos.values():
            if pago.tenant_id == tenant_id and pago.mp_payment_id == mp_payment_id:
                return pago
        return None

    def listar(self, *, tenant_id: str, sena_id: str | None = None) -> list[PagoMP]:
        return sorted(
            (
                p
                for p in self._pagos.values()
                if p.tenant_id == tenant_id and (sena_id is None or p.sena_id == sena_id)
            ),
            key=lambda p: (p.recibido_en, p.id),
        )

    def registrar_o_actualizar(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        mp_payment_id: str,
        monto_centavos: int,
        moneda: str,
        estado: EstadoPagoMP,
        resultado: ResultadoPagoMP | None = None,
        raw_json: Mapping[str, Any],
        aprobado_en: datetime | None = None,
        ahora: datetime | None = None,
    ) -> PagoMP:
        """Registra el pago o refresca el existente (mismo `mp_payment_id`).

        `resultado=None` significa "conservar el efecto ya aplicado": una
        renotificación no borra el `ACREDITADA` que explica la plata retenida
        (el `DUPLICADO` es el resultado de **esa** notificación, no del pago).
        La `moneda` es la real que informó la pasarela: un pago en `USD` se
        registra igual con su resultado (`MONTO_DISTINTO`), porque la plata que
        entró mal tiene que quedar visible para devolverla (corrección 009).
        """
        if monto_centavos <= 0:
            raise SenaInvalida("el monto del pago debe ser positivo")
        if not moneda or moneda != moneda.upper():
            raise SenaInvalida("la moneda del pago debe venir normalizada")
        momento = _ahora(ahora, self._reloj)
        with self._lock:
            for existente in self._pagos.values():
                if existente.mp_payment_id != mp_payment_id:
                    continue
                if existente.tenant_id != tenant_id:
                    # La fila ganadora del UNIQUE global no se reescribe desde
                    # otro tenant (F-04/F-05).
                    return existente
                if rango_estado(estado) > rango_estado(existente.estado):
                    actualizado_estado = estado
                else:
                    actualizado_estado = existente.estado
                actualizado = replace(
                    existente,
                    estado=actualizado_estado,
                    resultado=resultado if resultado is not None else existente.resultado,
                    raw_json=dict(raw_json),
                    actualizado_en=momento,
                    aprobado_en=aprobado_en if aprobado_en is not None else existente.aprobado_en,
                )
                self._pagos[existente.id] = actualizado
                return actualizado
            pago = PagoMP(
                id=f"pago-{self._siguiente}",
                tenant_id=tenant_id,
                mp_payment_id=mp_payment_id,
                sena_id=sena_id,
                monto_centavos=monto_centavos,
                moneda=moneda,
                estado=estado,
                resultado=resultado or "IGNORADO",
                raw_json=dict(raw_json),
                recibido_en=momento,
                actualizado_en=momento,
                aprobado_en=aprobado_en,
            )
            self._siguiente += 1
            self._pagos[pago.id] = pago
            return pago

    def total(self, tenant_id: str) -> int:
        return sum(1 for p in self._pagos.values() if p.tenant_id == tenant_id)

    def instantanea(self) -> object:
        with self._lock:
            return (dict(self._pagos), self._siguiente)

    def restaurar(self, estado: object) -> None:
        pagos, siguiente = cast(tuple[dict[str, PagoMP], int], estado)
        with self._lock:
            self._pagos = dict(pagos)
            self._siguiente = siguiente


class AdaptadorPasarelaFake:
    """Pasarela determinista y sin red (D5).

    `crear_preferencia` devuelve ids derivados del `sena_id` y `obtener_pago`
    responde lo programado con `aprobar`/`rechazar`/`demorar`/`fallar`.
    """

    def __init__(self, *, base_url: str = "https://mp.test") -> None:
        self._base_url = base_url
        self._pagos: dict[str, PagoExterno] = {}
        self._fallas: set[str] = set()
        self._caida = False
        self.preferencias: list[dict[str, Any]] = []
        self.consultas: list[str] = []

    def crear_preferencia(
        self,
        *,
        tenant_id: str,
        sena_id: str,
        turno_id: str,
        monto_centavos: int,
        descripcion: str,
        expira_at: datetime,
        url_pago: str,
        url_webhook: str,
    ) -> Preferencia:
        if self._caida:
            raise PasarelaNoDisponible("la pasarela está caída")
        self.preferencias.append(
            {
                "tenant_id": tenant_id,
                "sena_id": sena_id,
                "external_reference": sena_id,
                "metadata": {
                    "sena_id": sena_id,
                    "turno_id": turno_id,
                    "tenant_id": tenant_id,
                },
                "turno_id": turno_id,
                "monto_centavos": monto_centavos,
                "descripcion": descripcion,
                "expira_at": expira_at,
                "url_pago": url_pago,
                "url_webhook": url_webhook,
            }
        )
        return Preferencia(
            mp_preference_id=f"pref-{sena_id}",
            init_point=f"{self._base_url}/checkout/{sena_id}",
        )

    def obtener_pago(self, *, mp_payment_id: str) -> PagoExterno:
        self.consultas.append(mp_payment_id)
        if self._caida or mp_payment_id in self._fallas:
            raise PasarelaNoDisponible("la pasarela no responde")
        pago = self._pagos.get(mp_payment_id)
        if pago is None:
            raise PagoNoEncontrado("Mercado Pago no conoce el pago")
        return pago

    # -- programación de los pagos --------------------------------------

    def programar(
        self,
        *,
        mp_payment_id: str,
        estado: EstadoPagoMP,
        sena_id: str,
        monto_centavos: int,
        moneda: str = "ARS",
        tenant_id: str | None = None,
        turno_id: str | None = None,
        aprobado_en: datetime | None = None,
    ) -> PagoExterno:
        metadata: dict[str, str] = {"sena_id": sena_id}
        if tenant_id is not None:
            metadata["tenant_id"] = tenant_id
        if turno_id is not None:
            metadata["turno_id"] = turno_id
        pago = PagoExterno(
            mp_payment_id=mp_payment_id,
            estado=estado,
            monto_centavos=monto_centavos,
            moneda=moneda,
            external_reference=sena_id,
            metadata=metadata,
            aprobado_en=aprobado_en if estado == "APPROVED" else None,
        )
        self._pagos[mp_payment_id] = pago
        return pago

    def aprobar(
        self,
        mp_payment_id: str,
        *,
        sena_id: str,
        monto_centavos: int,
        moneda: str = "ARS",
        tenant_id: str | None = None,
        turno_id: str | None = None,
        aprobado_en: datetime | None = None,
    ) -> PagoExterno:
        return self.programar(
            mp_payment_id=mp_payment_id,
            estado="APPROVED",
            sena_id=sena_id,
            monto_centavos=monto_centavos,
            moneda=moneda,
            tenant_id=tenant_id,
            turno_id=turno_id,
            aprobado_en=aprobado_en,
        )

    def rechazar(
        self,
        mp_payment_id: str,
        *,
        sena_id: str,
        monto_centavos: int,
        moneda: str = "ARS",
        tenant_id: str | None = None,
        turno_id: str | None = None,
    ) -> PagoExterno:
        return self.programar(
            mp_payment_id=mp_payment_id,
            estado="REJECTED",
            sena_id=sena_id,
            monto_centavos=monto_centavos,
            moneda=moneda,
            tenant_id=tenant_id,
            turno_id=turno_id,
        )

    def demorar(
        self,
        mp_payment_id: str,
        *,
        sena_id: str,
        monto_centavos: int,
        moneda: str = "ARS",
        tenant_id: str | None = None,
        turno_id: str | None = None,
    ) -> PagoExterno:
        return self.programar(
            mp_payment_id=mp_payment_id,
            estado="PENDING",
            sena_id=sena_id,
            monto_centavos=monto_centavos,
            moneda=moneda,
            tenant_id=tenant_id,
            turno_id=turno_id,
        )

    def fallar(self, mp_payment_id: str | None = None) -> None:
        """Programa una falla: de un pago puntual o de toda la pasarela."""
        if mp_payment_id is None:
            self._caida = True
        else:
            self._fallas.add(mp_payment_id)

    def recuperar(self, mp_payment_id: str | None = None) -> None:
        if mp_payment_id is None:
            self._caida = False
        else:
            self._fallas.discard(mp_payment_id)


class ConfiguracionSenaMemoria:
    """Dos niveles de D1 en memoria: parámetros del tenant y override por prestación.

    `parametros` devuelve sólo lo configurado (claves `sena_modo`/`sena_valor`);
    la ausencia de ambas es "sin configuración" y la resuelve `resolver_regla`.
    """

    def __init__(self) -> None:
        self._parametros: dict[str, dict[str, Any]] = {}
        self._prestaciones: dict[tuple[str, str], PrestacionSena] = {}

    def configurar(self, *, tenant_id: str, modo: str | None, valor: int | None) -> None:
        claves: dict[str, Any] = {}
        if modo is not None:
            claves["sena_modo"] = modo
        if valor is not None:
            claves["sena_valor"] = valor
        self._parametros[tenant_id] = claves

    def agregar_prestacion(
        self,
        *,
        tenant_id: str,
        prestacion_id: str,
        precio_base_centavos: int,
        sena_modo: str | None = None,
        sena_valor: int | None = None,
    ) -> PrestacionSena:
        prestacion = PrestacionSena(
            id=prestacion_id,
            precio_base_centavos=precio_base_centavos,
            sena_modo=sena_modo,
            sena_valor=sena_valor,
        )
        self._prestaciones[(tenant_id, prestacion_id)] = prestacion
        return prestacion

    def parametros(self, *, tenant_id: str) -> Mapping[str, Any]:
        return dict(self._parametros.get(tenant_id, {}))

    def prestacion(self, *, tenant_id: str, prestacion_id: str) -> PrestacionSena | None:
        return self._prestaciones.get((tenant_id, prestacion_id))


class TurnoMemoriaSena:
    """Estados de turno en memoria para los puertos de C-05 (D4)."""

    def __init__(self, turnos: Mapping[tuple[str, str], datetime] | None = None) -> None:
        self._turnos: dict[tuple[str, str], TurnoRef] = {}
        self._lock = threading.Lock()
        for (tenant_id, turno_id), inicio in (turnos or {}).items():
            self.agregar(tenant_id=tenant_id, turno_id=turno_id, inicio=inicio)

    def agregar(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        inicio: datetime,
        estado: str = "PENDIENTE",
        paciente_id: str | None = None,
    ) -> TurnoRef:
        turno = TurnoRef(
            id=turno_id,
            tenant_id=tenant_id,
            estado=estado,
            inicio=inicio,
            fin=inicio + timedelta(minutes=30),
            paciente_id=paciente_id,
        )
        self._turnos[(tenant_id, turno_id)] = turno
        return turno

    def turno_de(self, *, tenant_id: str, turno_id: str) -> TurnoRef | None:
        return self._turnos.get((tenant_id, turno_id))

    def confirmar_por_sena(
        self, *, tenant_id: str, turno_id: str, ahora: datetime  # noqa: ARG002 — contrato de C-05
    ) -> None:
        self._transicionar(tenant_id=tenant_id, turno_id=turno_id, hacia="CONFIRMADO")

    def cancelar_por_sena(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        motivo: str,  # noqa: ARG002 — el motivo de C-05 no se usa en memoria
        ahora: datetime,  # noqa: ARG002 — contrato de C-05
    ) -> None:
        self._transicionar(tenant_id=tenant_id, turno_id=turno_id, hacia="CANCELADO")

    def _transicionar(self, *, tenant_id: str, turno_id: str, hacia: str) -> None:
        actual = self.turno_de(tenant_id=tenant_id, turno_id=turno_id)
        if actual is None:
            raise NoEncontrado("turno no encontrado")
        if actual.estado != "PENDIENTE":
            raise TransicionTurnoInvalida(
                f"el turno {turno_id} no está PENDIENTE (está {actual.estado})"
            )
        self._turnos[(tenant_id, turno_id)] = replace(actual, estado=hacia)

    # -- instantánea (rollback de la unidad de trabajo en memoria) ------

    def instantanea(self) -> object:
        with self._lock:
            return dict(self._turnos)

    def restaurar(self, estado: object) -> None:
        with self._lock:
            self._turnos = dict(cast(dict[tuple[str, str], TurnoRef], estado))


class AplicacionCajaMemoria:
    """Espía del alta de C-10: registra la llamada y devuelve el movimiento."""

    def __init__(self) -> None:
        self.llamadas: list[dict[str, Any]] = []
        self.registros: list[MovimientoRef] = []
        self._siguiente = 1
        self._lock = threading.Lock()

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
        if monto_centavos <= 0:
            raise SenaInvalida("el ingreso MP debe ser positivo")
        if concepto not in ("TRATAMIENTO", "CANCELACION_TARDIA"):
            raise SenaInvalida("concepto de aplicación inválido")
        with self._lock:
            self.llamadas.append(
                {
                    "tenant_id": tenant_id,
                    "turno_id": turno_id,
                    "monto_centavos": monto_centavos,
                }
            )
            movimiento = MovimientoRef(
                id=f"movimiento-mp-{self._siguiente}",
                tenant_id=tenant_id,
                turno_id=turno_id,
                monto_centavos=monto_centavos,
                medio="MP",
                tipo="INGRESO",
                fecha=fecha,
                actor_id=actor_id,
                concepto=cast(ConceptoAplicacion, concepto),
            )
            self._siguiente += 1
            self.registros.append(movimiento)
            return movimiento


class PresupuestosMemoria:
    """Sólo lectura de C-09: pacientes con presupuesto ACEPTADO vigente."""

    def __init__(self, vigentes: set[tuple[str, str]] | None = None) -> None:
        self._vigentes: set[tuple[str, str]] = set(vigentes or set())

    def marcar(self, *, tenant_id: str, paciente_id: str) -> None:
        self._vigentes.add((tenant_id, paciente_id))

    def aceptado_vigente(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        ahora: datetime,  # noqa: ARG002 — la vigencia la resuelve C-09
    ) -> bool:
        return (tenant_id, paciente_id) in self._vigentes


class AuditoriaSenaMemoria:
    """Auditoría append-only en memoria: sólo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoriaSena] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        accion: AccionSena,
        actor: str,
        entidad: str,
        entidad_id: str,
        antes: Mapping[str, Any] | None = None,
        despues: Mapping[str, Any] | None = None,
    ) -> None:
        with self._lock:
            self.entradas.append(
                EntradaAuditoriaSena(
                    tenant_id=tenant_id,
                    accion=accion,
                    actor=actor,
                    entidad=entidad,
                    entidad_id=entidad_id,
                    antes=dict(antes) if antes is not None else None,
                    despues=dict(despues) if despues is not None else None,
                    registrado_en=datetime.now(UTC).isoformat(),
                )
            )

    def de_tenant(self, tenant_id: str) -> list[EntradaAuditoriaSena]:
        return [entrada for entrada in self.entradas if entrada.tenant_id == tenant_id]

    def de_accion(self, accion: AccionSena) -> list[EntradaAuditoriaSena]:
        return [entrada for entrada in self.entradas if entrada.accion == accion]

    def instantanea(self) -> object:
        with self._lock:
            return list(self.entradas)

    def restaurar(self, estado: object) -> None:
        entradas = cast(list[EntradaAuditoriaSena], estado)
        with self._lock:
            self.entradas = list(entradas)


# ---------------------------------------------------------------------------
# Unidades de trabajo
# ---------------------------------------------------------------------------


class _Instantaneable(Protocol):
    def instantanea(self) -> object: ...

    def restaurar(self, estado: object) -> None: ...


class TransaccionNula:
    """Unidad de trabajo sin transacción (adaptadores que ya son atómicos).

    Se usa cuando el dominio corre contra adaptadores en memoria que no
    necesitan rollback. El adaptador SQL inyecta `TransaccionSQL(session)`, que
    es el que da la garantía real (D10/D11).
    """

    def __enter__(self) -> TransaccionNula:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        del exc_type, exc, tb
        return None


class UnidadDeTrabajoMemoria:
    """UoW de los tests en memoria: instantánea y rollback si algo falla.

    No pretende reemplazar a PostgreSQL: reproduce el contrato "todo o nada" de
    la transacción por seña (seña + turno + evento de hueco) para poder probar
    el rollback de §7 sin base real (F-14).
    """

    def __init__(self, *adaptadores: _Instantaneable) -> None:
        self._adaptadores = adaptadores
        self._instantanea: list[tuple[_Instantaneable, object]] = []

    def __enter__(self) -> UnidadDeTrabajoMemoria:
        self._instantanea = [(a, a.instantanea()) for a in self._adaptadores]
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        del exc, tb
        if exc_type is not None:
            for adaptador, estado in reversed(self._instantanea):
                adaptador.restaurar(estado)
        self._instantanea = []
        return None
