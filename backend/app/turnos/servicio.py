"""Servicio de turnos — tasks 3.1→3.4 sobre el dominio standalone.

Espeja en memoria el contrato de la migración 003: fin calculado
servidor-side, anti-solape por (tenant, profesional) y (tenant, sillón)
con half-open [inicio, fin), finales y sobreturnos que no bloquean,
tenant-scoped en toda query y auditoría append-only.
La garantía real ante concurrencia vive en el EXCLUDE de la DB (D1);
acá se replica el predicado para paridad de comportamiento.

Errores: excepciones con `codigo` HTTP (el router FastAPI los mapea).
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from app.turnos.alternativas import Alternativa, HuecoOcupado, buscar_alternativas
from app.turnos.estados import EstadoTurno, libera_hueco, transicion_valida
from app.turnos.fin import calcular_fin, fin_cliente_valido
from app.turnos.overlap import intervalos_solapan

Rol = Literal["PACIENTE", "ODONTOLOGO", "RECEPCION", "ADMIN"]

OrigenTurno = Literal["RECEPCION", "RESERVA_ONLINE", "LISTA_ESPERA"]


@dataclass(frozen=True)
class Actor:
    """Quién opera: tenant + rol + usuario (RBAC mínimo; JWT real en C-03)."""

    tenant_id: str
    rol: Rol
    user_id: str
    profesional_id: str | None = None


@dataclass(frozen=True)
class Turno:
    """Turno de agenda (datos ficticios en tests/demos)."""

    id: str
    tenant_id: str
    profesional_id: str
    sillon_id: str
    paciente_id: str
    prestacion_id: str
    inicio: datetime
    fin: datetime
    estado: EstadoTurno = "PENDIENTE"
    sobreturno: bool = False
    motivo_sobreturno: str | None = None
    origen: OrigenTurno = "RECEPCION"


@dataclass(frozen=True)
class AuditoriaEntrada:
    """Rastro append-only: quién/qué/cuándo/antes/después (sin PHI en logs)."""

    turno_id: str
    tenant_id: str
    accion: Literal["CREADO", "SOBRETURNO", "CANCELADO", "REPROGRAMADO"]
    actor: str
    antes: EstadoTurno | None
    despues: EstadoTurno
    registrado_en: str
    motivo: str | None = None


class TurnoError(Exception):
    """Error de dominio con código HTTP para el borde API."""

    codigo: int = 422

    def __init__(self, mensaje: str) -> None:
        super().__init__(mensaje)
        self.mensaje: str = mensaje


class Invalido(TurnoError):
    """422 — payload o transición inválida."""

    codigo = 422


class Prohibido(TurnoError):
    """403 — RBAC o anticipación mínima."""

    codigo = 403


class NoEncontrado(TurnoError):
    """404 — turno inexistente o de otro tenant."""

    codigo = 404


class ConflictoSolape(TurnoError):
    """409 — hueco ocupado + alternativas (RN-GL-02)."""

    codigo = 409

    def __init__(self, mensaje: str, alternativas: list[Alternativa] | None = None) -> None:
        super().__init__(mensaje)
        self.alternativas: list[Alternativa] = list(alternativas or [])


class ServicioTurnos:
    """Dominio + casos de uso de turnos (in-memory; DB real en migración 003)."""

    ANTICIPACION_DEFAULT_HORAS = 24.0

    def __init__(self, anticipacion_min_horas: float = ANTICIPACION_DEFAULT_HORAS) -> None:
        self._turnos: dict[str, Turno] = {}
        self._auditoria: list[AuditoriaEntrada] = []
        self._siguiente = 1
        self._lock = threading.Lock()
        self._anticipacion_min_horas = anticipacion_min_horas

    # ---- 3.1 CRUD ----

    def crear(
        self,
        actor: Actor,
        *,
        profesional_id: str,
        sillon_id: str,
        paciente_id: str,
        prestacion_id: str,
        inicio: datetime,
        duracion_min: int,
        fin_cliente: datetime | None = None,
        sobreturno: bool = False,
        motivo_sobreturno: str | None = None,
        origen: OrigenTurno = "RECEPCION",
    ) -> Turno:
        """Crea un turno si hay hueco real; calcula fin servidor-side."""
        self._exigir_aware(inicio)
        permiso = self._puede_crear(actor, paciente_id, profesional_id, sobreturno)
        if permiso is not None:
            raise permiso
        if sobreturno and (motivo_sobreturno is None or not motivo_sobreturno.strip()):
            raise Invalido("sobreturno exige motivo no vacío")
        try:
            fin = calcular_fin(inicio, duracion_min)
        except ValueError as exc:
            raise Invalido(str(exc)) from exc
        if fin_cliente is not None:
            self._exigir_aware(fin_cliente)
            if not fin_cliente_valido(inicio, duracion_min, fin_cliente):
                raise Invalido("fin provisto difiere del cálculo servidor-side")
        with self._lock:
            if not sobreturno and self._hay_solape(
                actor.tenant_id, profesional_id, sillon_id, inicio, fin, excluir_id=None
            ):
                alts = self._alternativas(
                    actor.tenant_id, profesional_id, sillon_id, duracion_min, inicio, None
                )
                raise ConflictoSolape("hueco ocupado", alts)
            turno = Turno(
                id=f"turno-{self._siguiente}",
                tenant_id=actor.tenant_id,
                profesional_id=profesional_id,
                sillon_id=sillon_id,
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                inicio=inicio,
                fin=fin,
                sobreturno=sobreturno,
                motivo_sobreturno=motivo_sobreturno,
                origen=origen,
            )
            self._siguiente += 1
            self._turnos[turno.id] = turno
            if sobreturno:
                self._auditar(
                    turno, "SOBRETURNO", actor.user_id, motivo_sobreturno, None, "PENDIENTE"
                )
            return turno

    def listar(self, actor: Actor) -> list[Turno]:
        """Turnos del tenant del actor (paciente: solo los propios)."""
        propios = [t for t in self._turnos.values() if t.tenant_id == actor.tenant_id]
        if actor.rol == "PACIENTE":
            propios = [t for t in propios if t.paciente_id == actor.user_id]
        return propios

    def obtener(self, actor: Actor, turno_id: str) -> Turno:
        """Un turno por id; 404 si no existe, es de otro tenant o paciente ajeno."""
        t = self._turnos.get(turno_id)
        if t is None or t.tenant_id != actor.tenant_id:
            raise NoEncontrado("turno no encontrado")
        if actor.rol == "PACIENTE" and t.paciente_id != actor.user_id:
            raise NoEncontrado("turno no encontrado")
        return t

    def actualizar(self, actor: Actor, turno_id: str, *, paciente_id: str) -> Turno:
        """Solo pacienteId es actualizable; estados finales no editables."""
        actual = self.obtener(actor, turno_id)
        if actor.rol == "PACIENTE":
            raise Prohibido("paciente no actualiza turnos")
        if not self._puede_escribir(actor, actual):
            raise Prohibido("fuera de tu agenda")
        if libera_hueco(actual.estado):
            raise Invalido("turno en estado final no editable")
        actualizado = replace(actual, paciente_id=paciente_id)
        self._turnos[turno_id] = actualizado
        return actualizado

    # ---- 3.2 sobreturno sobre turno existente ----

    def sobreturno(self, actor: Actor, turno_id: str, *, motivo: str) -> Turno:
        """Marca sobreturno explícito: motivo no vacío obligatorio + audita."""
        if motivo is None or not motivo.strip():
            raise Invalido("sobreturno exige motivo no vacío")
        actual = self.obtener(actor, turno_id)
        if actor.rol == "PACIENTE":
            raise Prohibido("paciente no crea sobreturnos")
        if not self._puede_escribir(actor, actual):
            raise Prohibido("fuera de tu agenda")
        if libera_hueco(actual.estado):
            raise Invalido("turno en estado final")
        marcado = replace(actual, sobreturno=True, motivo_sobreturno=motivo)
        self._turnos[turno_id] = marcado
        self._auditar(marcado, "SOBRETURNO", actor.user_id, motivo, actual.estado, actual.estado)
        return marcado

    # ---- 3.3 cancelar / reprogramar ----

    def cancelar(self, actor: Actor, turno_id: str, *, ahora: datetime | None = None) -> Turno:
        """Pasa a CANCELADO (audita). Bajo anticipación mínima: solo recepción."""
        actual = self.obtener(actor, turno_id)
        if not self._puede_escribir(actor, actual):
            raise Prohibido("sin permiso sobre este turno")
        if not transicion_valida(actual.estado, "CANCELADO"):
            raise Invalido(f"transición {actual.estado} → CANCELADO ilegal")
        if self._bajo_anticipacion(actual, ahora) and not self._es_recepcion(actor):
            raise Prohibido("bajo anticipación mínima: solo recepción")
        cancelado = replace(actual, estado="CANCELADO")
        self._turnos[turno_id] = cancelado
        self._auditar(cancelado, "CANCELADO", actor.user_id, None, actual.estado, "CANCELADO")
        return cancelado

    @dataclass(frozen=True)
    class Reprogramacion:
        """Par atómico: original marcado + nuevo turno."""

        original: Turno
        nuevo: Turno

    def reprogramar(
        self,
        actor: Actor,
        turno_id: str,
        *,
        nuevo_inicio: datetime,
        duracion_min: int | None = None,
        ahora: datetime | None = None,
    ) -> Reprogramacion:
        """Marca el original REPROGRAMADO y crea el nuevo revalidando solape.

        La revalidación ocurre ANTES de mutar: si el destino está ocupado
        (409) el original conserva horario y estado (atomicidad).
        """
        self._exigir_aware(nuevo_inicio)
        actual = self.obtener(actor, turno_id)
        if not self._puede_escribir(actor, actual):
            raise Prohibido("sin permiso sobre este turno")
        if not transicion_valida(actual.estado, "REPROGRAMADO"):
            raise Invalido(f"transición {actual.estado} → REPROGRAMADO ilegal")
        if self._bajo_anticipacion(actual, ahora) and not self._es_recepcion(actor):
            raise Prohibido("bajo anticipación mínima: solo recepción")
        duracion = duracion_min if duracion_min is not None else self._duracion_de(actual)
        try:
            nuevo_fin = calcular_fin(nuevo_inicio, duracion)
        except ValueError as exc:
            raise Invalido(str(exc)) from exc
        with self._lock:
            if self._hay_solape(
                actual.tenant_id,
                actual.profesional_id,
                actual.sillon_id,
                nuevo_inicio,
                nuevo_fin,
                excluir_id=actual.id,
            ):
                alts = self._alternativas(
                    actual.tenant_id,
                    actual.profesional_id,
                    actual.sillon_id,
                    duracion,
                    nuevo_inicio,
                    actual.id,
                )
                raise ConflictoSolape("destino ocupado", alts)
            original = replace(actual, estado="REPROGRAMADO")
            nuevo = Turno(
                id=f"turno-{self._siguiente}",
                tenant_id=actual.tenant_id,
                profesional_id=actual.profesional_id,
                sillon_id=actual.sillon_id,
                paciente_id=actual.paciente_id,
                prestacion_id=actual.prestacion_id,
                inicio=nuevo_inicio,
                fin=nuevo_fin,
            )
            self._siguiente += 1
            self._turnos[turno_id] = original
            self._turnos[nuevo.id] = nuevo
            self._auditar(original, "REPROGRAMADO", actor.user_id, None, actual.estado, "REPROGRAMADO")
            return ServicioTurnos.Reprogramacion(original=original, nuevo=nuevo)

    # ---- 4.3 auditoría append-only ----

    def auditoria(self, actor: Actor, turno_id: str | None = None) -> list[AuditoriaEntrada]:
        """Rastro consultable (paciente sin acceso; odontólogo ve su agenda)."""
        if actor.rol == "PACIENTE":
            raise Prohibido("paciente sin acceso a auditoría")
        if actor.rol == "ODONTOLOGO":
            entradas = [
                e
                for e in self._auditoria
                if (t := self._turnos.get(e.turno_id)) is not None
                and t.profesional_id == actor.profesional_id
            ]
        else:
            entradas = [e for e in self._auditoria if e.tenant_id == actor.tenant_id]
        if turno_id is not None:
            entradas = [e for e in entradas if e.turno_id == turno_id]
        return list(entradas)

    # ---- helpers ----

    @staticmethod
    def _exigir_aware(valor: datetime) -> None:
        if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
            raise Invalido("inicio/fin deben ser timezone-aware (timestamptz)")

    def _puede_crear(
        self, actor: Actor, paciente_id: str, profesional_id: str, sobreturno: bool
    ) -> TurnoError | None:
        if actor.rol == "PACIENTE":
            if paciente_id != actor.user_id:
                return Prohibido("paciente solo crea sus turnos")
            if sobreturno:
                return Prohibido("paciente no crea sobreturnos")
            return None
        if actor.rol == "ODONTOLOGO" and profesional_id != actor.profesional_id:
            return Prohibido("odontólogo solo agenda propia")
        return None

    def _puede_escribir(self, actor: Actor, turno: Turno) -> bool:
        if actor.rol in ("ADMIN", "RECEPCION"):
            return True
        if actor.rol == "ODONTOLOGO":
            return turno.profesional_id == actor.profesional_id
        return turno.paciente_id == actor.user_id

    @staticmethod
    def _es_recepcion(actor: Actor) -> bool:
        return actor.rol in ("RECEPCION", "ADMIN")

    def _bajo_anticipacion(self, turno: Turno, ahora: datetime | None) -> bool:
        if ahora is None:
            from datetime import timezone as _tz

            ahora = datetime.now(_tz.utc)
            if turno.inicio.tzinfo is None:
                return False
        delta_horas = (turno.inicio - ahora).total_seconds() / 3600
        return delta_horas < self._anticipacion_min_horas

    @staticmethod
    def _duracion_de(turno: Turno) -> int:
        return round((turno.fin - turno.inicio).total_seconds() / 60)

    def _hay_solape(
        self,
        tenant_id: str,
        profesional_id: str,
        sillon_id: str,
        inicio: datetime,
        fin: datetime,
        excluir_id: str | None,
    ) -> bool:
        """Replica el predicado parcial del EXCLUDE 003 (D1/D2)."""
        if inicio >= fin:
            return True
        for t in self._turnos.values():
            if t.id == excluir_id:
                continue
            if t.tenant_id != tenant_id:
                continue
            if t.profesional_id != profesional_id and t.sillon_id != sillon_id:
                continue
            if libera_hueco(t.estado):
                continue
            if t.sobreturno:
                continue
            if intervalos_solapan(inicio, fin, t.inicio, t.fin):
                return True
        return False

    def _alternativas(
        self,
        tenant_id: str,
        profesional_id: str,
        sillon_id: str,
        duracion_min: int,
        desde: datetime,
        excluir_id: str | None,
    ) -> list[Alternativa]:
        """3 huecos reales servidor-side (RN-GL-02) para el body del 409."""
        ocupados = [
            HuecoOcupado(
                tenant_id=t.tenant_id,
                profesional_id=t.profesional_id,
                sillon_id=t.sillon_id,
                inicio=t.inicio,
                fin=t.fin,
                estado=t.estado,
                sobreturno=t.sobreturno,
            )
            for t in self._turnos.values()
            if t.id != excluir_id
        ]
        return buscar_alternativas(
            desde, duracion_min, tenant_id, profesional_id, sillon_id, ocupados
        )

    def _auditar(
        self,
        turno: Turno,
        accion: Literal["CREADO", "SOBRETURNO", "CANCELADO", "REPROGRAMADO"],
        actor_id: str,
        motivo: str | None,
        antes: EstadoTurno | None,
        despues: EstadoTurno,
    ) -> None:
        from datetime import timezone as _tz

        entrada = AuditoriaEntrada(
            turno_id=turno.id,
            tenant_id=turno.tenant_id,
            accion=accion,
            actor=actor_id,
            antes=antes,
            despues=despues,
            registrado_en=datetime.now(_tz.utc).isoformat(),
            motivo=motivo,
        )
        self._auditoria.append(entrada)
