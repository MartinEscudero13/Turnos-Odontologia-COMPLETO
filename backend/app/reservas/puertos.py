"""Puertos (protocolos) y adaptadores en memoria del dominio de reserva pública.

C-06 programa contra estos puertos para no acoplarse a C-04 (catálogos/pacientes),
C-03 (auditoría), Redis (contadores/verificación) ni C-13 (notificación). Con C-03 y
C-04 ya archivados el wiring real es un follow-up explícito; acá el dominio queda
completamente testeable sin DB ni red.

Reglas duras cumplidas acá:
- Toda operación recibe `tenant_id` explícito (nunca una query sin tenant).
- Los adaptadores en memoria solo devuelven lo sembrado por el test (nunca inventan datos).
- Ningún puerto transporta nombre/teléfono de terceros salvo `PacientePort` (que es
  exactamente el puerto de identificación, RN-RE-05).
"""
from __future__ import annotations

import re
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, time
from typing import Literal, Protocol

E164_RE = re.compile(r"^\+[1-9][0-9]{7,14}$")

AccionPublica = Literal["reservar", "cancelar", "reprogramar"]

AccionAuditada = Literal[
    "CREADO",
    "CANCELADO",
    "REPROGRAMADO",
    "CANCELACION_RECHAZADA",
    "REPROGRAMACION_RECHAZADA",
]


def normalizar_telefono_e164(telefono: str) -> str | None:
    """Normaliza a E.164 compacto (sin espacios/guiones/paréntesis) o devuelve None."""
    compact = re.sub(r"[\s().\-]", "", telefono)
    if not E164_RE.fullmatch(compact):
        return None
    return compact


# ---------------------------------------------------------------------------
# Entidades mínimas (proyecciones de catálogo, sin PHI)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Prestacion:
    id: str
    tenant_id: str
    duracion_min: int


@dataclass(frozen=True)
class Profesional:
    id: str
    tenant_id: str
    activo: bool = True


@dataclass(frozen=True)
class Sillon:
    id: str
    tenant_id: str
    activo: bool = True


@dataclass(frozen=True)
class HorarioSemanal:
    tenant_id: str
    dia: int  # 1=Lunes .. 7=Domingo
    desde: time
    hasta: time
    profesional_id: str | None = None  # None => horario del consultorio


@dataclass(frozen=True)
class Bloqueo:
    tenant_id: str
    desde: datetime
    hasta: datetime
    profesional_id: str | None = None
    sillon_id: str | None = None


@dataclass(frozen=True)
class Paciente:
    id: str
    tenant_id: str
    nombre: str
    telefono: str


@dataclass(frozen=True)
class TokenResuelto:
    tenant_id: str
    turno_id: str


@dataclass(frozen=True)
class DesafioPublico:
    verificacion_id: str
    expira_at: datetime
    canal: str


@dataclass(frozen=True)
class EntradaAuditoria:
    tenant_id: str
    turno_id: str
    accion: AccionAuditada
    actor: str
    antes: str | None
    despues: str
    motivo: str | None
    registrado_en: str


# ---------------------------------------------------------------------------
# Puertos (protocolos)
# ---------------------------------------------------------------------------


class CatalogoPort(Protocol):
    def prestacion(self, tenant_id: str, prestacion_id: str) -> Prestacion | None: ...
    def profesional(self, tenant_id: str, profesional_id: str) -> Profesional | None: ...
    def profesionales_habilitados(
        self, tenant_id: str, prestacion_id: str
    ) -> Sequence[Profesional]: ...
    def sillones_activos(self, tenant_id: str) -> Sequence[Sillon]: ...
    def horario_profesional(
        self, tenant_id: str, profesional_id: str
    ) -> Sequence[HorarioSemanal]: ...
    def horario_consultorio(self, tenant_id: str) -> Sequence[HorarioSemanal]: ...
    def bloqueos(self, tenant_id: str, desde: datetime, hasta: datetime) -> Sequence[Bloqueo]: ...


class PacientePort(Protocol):
    def buscar_por_telefono(self, tenant_id: str, telefono_e164: str) -> Paciente | None: ...
    def crear_minimo(self, tenant_id: str, nombre: str, telefono_e164: str) -> Paciente: ...


class TenantPort(Protocol):
    def resolver(self, token_tenant: str) -> str | None: ...


class TokenRepositorio(Protocol):
    def emitir(self, tenant_id: str, turno_id: str) -> str: ...
    def resolver(self, tenant_id: str, token: str) -> TokenResuelto | None: ...
    def transferir(self, token: str, turno_nuevo_id: str) -> None: ...
    def revocar(self, token: str) -> None: ...


class ContadorPort(Protocol):
    def incrementar(self, clave: str, ventana_s: int) -> int: ...
    def ttl_s(self, clave: str) -> int: ...


class VerificadorPort(Protocol):
    def desafio(
        self, *, tenant_id: str, accion: AccionPublica, ip: str, ahora: datetime
    ) -> DesafioPublico: ...
    def verificar(
        self, *, tenant_id: str, accion: AccionPublica, prueba: str, ip: str, ahora: datetime
    ) -> bool: ...


class NotificadorPort(Protocol):
    def reserva_creada(self, *, tenant_id: str, turno_id: str) -> None: ...


class AuditoriaPort(Protocol):
    def registrar(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        accion: AccionAuditada,
        actor: str,
        antes: str | None,
        despues: str,
        motivo: str | None = None,
    ) -> None: ...


# ---------------------------------------------------------------------------
# Adaptadores en memoria
# ---------------------------------------------------------------------------


class CatalogoMemoria:
    """Catálogo en memoria: solo devuelve lo sembrado, scoped por (tenant, id)."""

    def __init__(
        self,
        prestaciones: Sequence[Prestacion] = (),
        profesionales: Sequence[Profesional] = (),
        sillones: Sequence[Sillon] = (),
        horarios: Sequence[HorarioSemanal] = (),
        bloqueos: Sequence[Bloqueo] = (),
        habilitados: Sequence[tuple[str, str, str]] = (),  # (tenant_id, profesional_id, prestacion_id)
    ) -> None:
        self._prestaciones = {(p.tenant_id, p.id): p for p in prestaciones}
        self._profesionales = {(p.tenant_id, p.id): p for p in profesionales}
        self._sillones = {(s.tenant_id, s.id): s for s in sillones}
        self._horarios = list(horarios)
        self._bloqueos = list(bloqueos)
        self._habilitados = set(habilitados)

    def prestacion(self, tenant_id: str, prestacion_id: str) -> Prestacion | None:
        return self._prestaciones.get((tenant_id, prestacion_id))

    def profesional(self, tenant_id: str, profesional_id: str) -> Profesional | None:
        return self._profesionales.get((tenant_id, profesional_id))

    def profesionales_habilitados(
        self, tenant_id: str, prestacion_id: str
    ) -> Sequence[Profesional]:
        return [
            p
            for (tid, _), p in self._profesionales.items()
            if tid == tenant_id and p.activo and (tenant_id, p.id, prestacion_id) in self._habilitados
        ]

    def sillones_activos(self, tenant_id: str) -> Sequence[Sillon]:
        return [s for (tid, _), s in self._sillones.items() if tid == tenant_id and s.activo]

    def horario_profesional(
        self, tenant_id: str, profesional_id: str
    ) -> Sequence[HorarioSemanal]:
        return [
            h
            for h in self._horarios
            if h.tenant_id == tenant_id and h.profesional_id == profesional_id
        ]

    def horario_consultorio(self, tenant_id: str) -> Sequence[HorarioSemanal]:
        return [
            h for h in self._horarios if h.tenant_id == tenant_id and h.profesional_id is None
        ]

    def bloqueos(self, tenant_id: str, desde: datetime, hasta: datetime) -> Sequence[Bloqueo]:
        return [
            b
            for b in self._bloqueos
            if b.tenant_id == tenant_id and b.hasta > desde and b.desde < hasta
        ]

    # ---- helpers de siembra (tests) ----

    def agregar_prestacion(self, p: Prestacion) -> None:
        self._prestaciones[(p.tenant_id, p.id)] = p

    def agregar_profesional(self, p: Profesional) -> None:
        self._profesionales[(p.tenant_id, p.id)] = p

    def agregar_sillon(self, s: Sillon) -> None:
        self._sillones[(s.tenant_id, s.id)] = s

    def agregar_horario(self, h: HorarioSemanal) -> None:
        self._horarios.append(h)

    def agregar_bloqueo(self, b: Bloqueo) -> None:
        self._bloqueos.append(b)

    def agregar_habilitado(self, tenant_id: str, profesional_id: str, prestacion_id: str) -> None:
        self._habilitados.add((tenant_id, profesional_id, prestacion_id))


class PacienteMemoria:
    """Pacientes en memoria con deduplicación atómica por (tenant, teléfono E.164)."""

    def __init__(self, pacientes: Sequence[Paciente] = ()) -> None:
        self._pacientes = list(pacientes)
        self._lock = threading.Lock()

    def buscar_por_telefono(self, tenant_id: str, telefono_e164: str) -> Paciente | None:
        e164 = normalizar_telefono_e164(telefono_e164)
        objetivo = e164 if e164 is not None else telefono_e164
        for p in self._pacientes:
            if p.tenant_id == tenant_id and p.telefono == objetivo:
                return p
        return None

    def crear_minimo(self, tenant_id: str, nombre: str, telefono_e164: str) -> Paciente:
        e164 = normalizar_telefono_e164(telefono_e164) or telefono_e164
        with self._lock:
            for p in self._pacientes:
                if p.tenant_id == tenant_id and p.telefono == e164:
                    return p  # la carrera de alta ya se cerró en otra transacción
            nuevo = Paciente(
                id=f"paciente-{len(self._pacientes) + 1}",
                tenant_id=tenant_id,
                nombre=nombre,
                telefono=e164,
            )
            self._pacientes.append(nuevo)
            return nuevo

    def agregar(self, p: Paciente) -> None:
        self._pacientes.append(p)

    def total(self, tenant_id: str) -> int:
        return sum(1 for p in self._pacientes if p.tenant_id == tenant_id)


class TenantMemoria:
    """Resuelve el `{tokenTenant}` (slug público) a un `tenant_id` activo."""

    def __init__(self, tenants: dict[str, tuple[str, bool]]) -> None:
        # slug -> (tenant_id, activo)
        self._tenants = dict(tenants)

    def resolver(self, token_tenant: str) -> str | None:
        entry = self._tenants.get(token_tenant)
        if entry is None:
            return None
        tenant_id, activo = entry
        return tenant_id if activo else None


class NotificadorNulo:
    """Notificador no-op hasta C-13 (confirmación WA/email)."""

    def reserva_creada(self, *, tenant_id: str, turno_id: str) -> None:
        del tenant_id, turno_id
        return None


class AuditoriaMemoria:
    """Auditoría append-only en memoria: solo `registrar`, sin update/delete."""

    def __init__(self) -> None:
        self.entradas: list[EntradaAuditoria] = []
        self._lock = threading.Lock()

    def registrar(
        self,
        *,
        tenant_id: str,
        turno_id: str,
        accion: AccionAuditada,
        actor: str,
        antes: str | None,
        despues: str,
        motivo: str | None = None,
    ) -> None:
        with self._lock:
            self.entradas.append(
                EntradaAuditoria(
                    tenant_id=tenant_id,
                    turno_id=turno_id,
                    accion=accion,
                    actor=actor,
                    antes=antes,
                    despues=despues,
                    motivo=motivo,
                    registrado_en=datetime.now(UTC).isoformat(),
                )
            )
