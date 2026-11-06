"""Servicio de ficha clínica — C-08 (ficha 1—1, evoluciones, adjuntos, consentimiento).

Dominio puro: programa contra los puertos en memoria de `puertos.py`; no toca DB
ni red. Valida que paciente, profesional y ficha pertenezcan al mismo tenant
(404), exige consentimiento previo con `timestamp` válido para toda operación
clínica (409 CONSENTIMIENTO_REQUERIDO), respeta el RBAC clínico de la matriz
(403) y escribe auditoría append-only sin PHI.
"""
from __future__ import annotations

from datetime import UTC, datetime

from app.ficha_clinica.puertos import (
    AccionClinica,
    Adjunto,
    AdjuntoRepositorio,
    AuditoriaPort,
    Consentimiento,
    ConsentimientoRepositorio,
    Evolucion,
    EvolucionRepositorio,
    Ficha,
    FichaRepositorio,
    PacientePort,
    ProfesionalPort,
    Reloj,
    TurnoPort,
)
from app.turnos.servicio import Actor, Invalido, NoEncontrado, Prohibido, TurnoError


class ConsentimientoRequerido(TurnoError):
    """409 — falta consentimiento informado firmado (precondición de estado, D9)."""

    codigo = 409


class Conflicto(TurnoError):
    """409 — conflicto de dominio (ficha duplicada)."""

    codigo = 409


_ESCRIBE_EVOLUCION = frozenset({"ADMIN", "ODONTOLOGO"})
_CREA_FICHA = frozenset({"ADMIN", "RECEPCION"})
_TIPOS_ADJUNTO = frozenset({"RX", "FOTO"})


class ServicioFichaClinica:
    """Casos de uso de la ficha clínica (ficha, evoluciones, adjuntos, consentimiento)."""

    def __init__(
        self,
        fichas: FichaRepositorio,
        evoluciones: EvolucionRepositorio,
        adjuntos: AdjuntoRepositorio,
        consentimientos: ConsentimientoRepositorio,
        pacientes: PacientePort,
        profesionales: ProfesionalPort,
        turnos: TurnoPort,
        auditoria: AuditoriaPort,
        reloj: Reloj | None = None,
    ) -> None:
        self._fichas = fichas
        self._evoluciones = evoluciones
        self._adjuntos = adjuntos
        self._consentimientos = consentimientos
        self._pacientes = pacientes
        self._profesionales = profesionales
        self._turnos = turnos
        self._auditoria = auditoria
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Ficha 1—1
    # ------------------------------------------------------------------

    def crear_ficha(self, actor: Actor, *, paciente_id: str, ahora: datetime | None = None) -> Ficha:
        self._exigir_rol(actor, _CREA_FICHA)
        tenant_id = actor.tenant_id
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        self._exigir_consentimiento(tenant_id, paciente_id)
        if self._fichas.por_paciente(tenant_id=tenant_id, paciente_id=paciente_id) is not None:
            raise Conflicto("ficha clínica ya existe")
        ficha = self._fichas.crear(
            tenant_id=tenant_id, paciente_id=paciente_id, ahora=self._momento(ahora)
        )
        self._auditar(
            tenant_id, "FICHA_CREADA", actor.user_id, "ficha", ficha.id,
            despues={"paciente_id": paciente_id},
        )
        return ficha

    def obtener_ficha(self, actor: Actor, *, paciente_id: str) -> Ficha:
        tenant_id = actor.tenant_id
        ficha = self._fichas.por_paciente(tenant_id=tenant_id, paciente_id=paciente_id)
        if ficha is None:
            raise NoEncontrado("ficha no encontrada")
        self._exigir_lectura(actor, paciente_id)
        return ficha

    # ------------------------------------------------------------------
    # Consentimiento (append-only)
    # ------------------------------------------------------------------

    def registrar_consentimiento(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        timestamp: datetime,
        canal: str,
        ahora: datetime | None = None,
    ) -> Consentimiento:
        self._exigir_rol(actor, _CREA_FICHA)
        tenant_id = actor.tenant_id
        self._exigir_aware(timestamp)
        if not canal or not canal.strip():
            raise Invalido("canal requerido")
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        consentimiento = self._consentimientos.registrar(
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            timestamp=timestamp,
            canal=canal,
            ahora=self._momento(ahora),
        )
        self._auditar(
            tenant_id, "CONSENTIMIENTO_REGISTRADO", actor.user_id, "consentimiento",
            consentimiento.id,
            despues={"paciente_id": paciente_id, "canal": canal, "timestamp": timestamp.isoformat()},
        )
        return consentimiento

    def listar_consentimientos(self, actor: Actor, *, paciente_id: str) -> list[Consentimiento]:
        self._exigir_lectura(actor, paciente_id)
        return self._consentimientos.listar(tenant_id=actor.tenant_id, paciente_id=paciente_id)

    # ------------------------------------------------------------------
    # Evoluciones (append-only)
    # ------------------------------------------------------------------

    def registrar_evolucion(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        profesional_id: str,
        fecha: datetime,
        texto: str,
        firma_hash: str | None = None,
        ahora: datetime | None = None,
    ) -> Evolucion:
        self._exigir_rol(actor, _ESCRIBE_EVOLUCION)
        self._exigir_aware(fecha)
        if not texto or not texto.strip():
            raise Invalido("texto de evolución requerido")
        tenant_id = actor.tenant_id
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        if not self._profesionales.existe(tenant_id=tenant_id, profesional_id=profesional_id):
            raise NoEncontrado("profesional no encontrado")
        if actor.rol == "ODONTOLOGO":
            if actor.profesional_id is None or profesional_id != actor.profesional_id:
                raise Prohibido("odontólogo sólo registra sus propias evoluciones")
            if not self._turnos.atiende(
                tenant_id=tenant_id, profesional_id=actor.profesional_id, paciente_id=paciente_id
            ):
                raise Prohibido("odontólogo no atiende a este paciente")
        self._exigir_consentimiento(tenant_id, paciente_id)
        evolucion = self._evoluciones.registrar(
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            profesional_id=profesional_id,
            fecha=fecha,
            texto=texto,
            firma_hash=firma_hash,
            ahora=self._momento(ahora),
        )
        self._auditar(
            tenant_id, "EVOLUCION_REGISTRADA", actor.user_id, "evolucion", evolucion.id,
            despues={
                "paciente_id": paciente_id,
                "profesional_id": profesional_id,
                "fecha": fecha.isoformat(),
            },
        )
        return evolucion

    def listar_evoluciones(self, actor: Actor, *, paciente_id: str) -> list[Evolucion]:
        self._exigir_lectura(actor, paciente_id)
        return self._evoluciones.listar(tenant_id=actor.tenant_id, paciente_id=paciente_id)

    # ------------------------------------------------------------------
    # Adjuntos (referencia opaca)
    # ------------------------------------------------------------------

    def registrar_adjunto(
        self,
        actor: Actor,
        *,
        ficha_id: str,
        tipo: str,
        storage_ref: str,
        ahora: datetime | None = None,
    ) -> Adjunto:
        self._exigir_rol(actor, _ESCRIBE_EVOLUCION)
        tenant_id = actor.tenant_id
        if tipo not in _TIPOS_ADJUNTO:
            raise Invalido("tipo de adjunto inválido")
        if not storage_ref or not storage_ref.strip():
            raise Invalido("referencia de almacenamiento requerida")
        ficha = self._fichas.obtener(tenant_id=tenant_id, ficha_id=ficha_id)
        if ficha is None:
            raise NoEncontrado("ficha no encontrada")
        if actor.rol == "ODONTOLOGO" and (
            actor.profesional_id is None
            or not self._turnos.atiende(
                tenant_id=tenant_id, profesional_id=actor.profesional_id, paciente_id=ficha.paciente_id
            )
        ):
            raise Prohibido("odontólogo no atiende a este paciente")
        self._exigir_consentimiento(tenant_id, ficha.paciente_id)
        adjunto = self._adjuntos.registrar(
            tenant_id=tenant_id, ficha_id=ficha_id, tipo=tipo, storage_ref=storage_ref,
            ahora=self._momento(ahora),
        )
        self._auditar(
            tenant_id, "ADJUNTO_REGISTRADO", actor.user_id, "adjunto", adjunto.id,
            despues={"ficha_id": ficha_id, "tipo": tipo},
        )
        return adjunto

    def listar_adjuntos(self, actor: Actor, *, ficha_id: str) -> list[Adjunto]:
        tenant_id = actor.tenant_id
        ficha = self._fichas.obtener(tenant_id=tenant_id, ficha_id=ficha_id)
        if ficha is None:
            raise NoEncontrado("ficha no encontrada")
        self._exigir_lectura(actor, ficha.paciente_id)
        return self._adjuntos.listar(tenant_id=tenant_id, ficha_id=ficha_id)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    def _exigir_consentimiento(self, tenant_id: str, paciente_id: str) -> None:
        if not self._consentimientos.firmado(tenant_id=tenant_id, paciente_id=paciente_id):
            raise ConsentimientoRequerido("CONSENTIMIENTO_REQUERIDO")

    @staticmethod
    def _exigir_rol(actor: Actor, roles: frozenset[str]) -> None:
        if actor.rol not in roles:
            raise Prohibido("rol sin permiso")

    @staticmethod
    def _exigir_aware(valor: datetime) -> None:
        if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
            raise Invalido("fecha debe ser timezone-aware")

    def _exigir_lectura(self, actor: Actor, paciente_id: str) -> None:
        if actor.rol in ("ADMIN", "RECEPCION"):
            return
        if actor.rol == "ODONTOLOGO":
            if actor.profesional_id is None or not self._turnos.atiende(
                tenant_id=actor.tenant_id, profesional_id=actor.profesional_id, paciente_id=paciente_id
            ):
                raise Prohibido("odontólogo no atiende a este paciente")
            return
        if actor.rol == "PACIENTE":
            if actor.user_id != paciente_id:
                raise NoEncontrado("ficha no encontrada")
            return
        raise Prohibido("rol sin permiso")

    def _auditar(
        self,
        tenant_id: str,
        accion: AccionClinica,
        actor_id: str,
        entidad: str,
        entidad_id: str,
        *,
        antes: dict[str, object] | None = None,
        despues: dict[str, object] | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            accion=accion,
            actor=actor_id,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
        )
