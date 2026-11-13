"""Servicio de odontograma — C-09 (hallazgos, historial, resolución y derivación).

Dominio puro: programa contra los puertos de `puertos.py` y los puertos mínimos
de `app.presupuesto.puertos`; no toca DB ni red. Reproduce el contrato de la
migración 007 y de la KB:

- RN-CL-01/D1: grilla FDI permanente (32 posiciones) con `422` explícito.
- RN-CL-03/D2: el contenido clínico es inmutable; corregir es otro hallazgo y
  `resuelto` sólo pasa de `false` a `true` una vez (`409` al repetir).
- RN-AU-03/D11: consentimiento con timestamp válido para toda operación
  clínica (`409 CONSENTIMIENTO_REQUERIDO`); la agenda no se bloquea.
- D3: derivación hallazgo → línea atómica e idempotente por
  `Idempotency-Key` (UUID), con replay `200` y `409` si el payload difiere.
- D10: ADMIN y ODONTOLOGO escriben; ODONTOLOGO sólo sobre sus pacientes y su
  propia firma; RECEPCION sólo lee.
- RN-CL-04/D12: auditoría append-only sin texto clínico ni datos personales.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from app.ficha_clinica.servicio import Conflicto, ConsentimientoRequerido
from app.odontograma.fdi import validar_monto, validar_pieza_fdi
from app.odontograma.puertos import (
    AccionOdontograma,
    AuditoriaPort,
    ConsentimientoPort,
    Hallazgo,
    HallazgoRepositorio,
    PacientePort,
    PrestacionPort,
    ProfesionalPort,
    Reloj,
    TurnoPort,
    UnidadDeTrabajo,
)
from app.presupuesto.puertos import (
    IdempotencyKeyDuplicada,
    Linea,
    LineaRepositorio,
    Presupuesto,
    PresupuestoRepositorio,
)
from app.turnos.servicio import Actor, Invalido, NoAutenticado, NoEncontrado, Prohibido

__all__ = ["Derivacion", "ServicioOdontograma"]

_ESCRIBE_CLINICA = frozenset({"ADMIN", "ODONTOLOGO"})
_LEE_CLINICA = frozenset({"ADMIN", "RECEPCION", "ODONTOLOGO"})


@dataclass(frozen=True)
class Derivacion:
    """Resultado de derivar: `creada=True` ⇒ 201; `False` ⇒ replay 200."""

    hallazgo: Hallazgo
    linea: Linea
    creada: bool


class _CarreraIdempotencia(Exception):
    """Señal interna: el INSERT perdió contra el UNIQUE parcial (D3.2)."""


class ServicioOdontograma:
    """Casos de uso del odontograma (registro, historial, resolución y derivación)."""

    def __init__(
        self,
        hallazgos: HallazgoRepositorio,
        presupuestos: PresupuestoRepositorio,
        lineas: LineaRepositorio,
        prestaciones: PrestacionPort,
        pacientes: PacientePort,
        profesionales: ProfesionalPort,
        turnos: TurnoPort,
        consentimientos: ConsentimientoPort,
        auditoria: AuditoriaPort,
        uow_factory: Callable[[], UnidadDeTrabajo],
        reloj: Reloj | None = None,
    ) -> None:
        self._hallazgos = hallazgos
        self._presupuestos = presupuestos
        self._lineas = lineas
        self._prestaciones = prestaciones
        self._pacientes = pacientes
        self._profesionales = profesionales
        self._turnos = turnos
        self._consentimientos = consentimientos
        self._auditoria = auditoria
        self._uow_factory = uow_factory
        self._reloj: Reloj = reloj or (lambda: datetime.now(UTC))

    # ------------------------------------------------------------------
    # Registro e historial
    # ------------------------------------------------------------------

    def registrar_hallazgo(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        pieza_fdi: object,
        hallazgo: str,
        fecha: datetime,
        superficie: object | None = None,
        profesional_id: str | None = None,
        ahora: datetime | None = None,
    ) -> Hallazgo:
        """Registra un hallazgo clínico FDI válido (RN-CL-01/RN-AU-03)."""
        tenant_id, pieza, profesional, superficie_limpia = self._validar_clinico(
            actor,
            paciente_id=paciente_id,
            pieza_fdi=pieza_fdi,
            hallazgo=hallazgo,
            fecha=fecha,
            superficie=superficie,
            profesional_id=profesional_id,
        )
        return self._crear_hallazgo(
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            pieza_fdi=pieza,
            superficie=superficie_limpia,
            hallazgo=hallazgo,
            fecha=fecha,
            profesional_id=profesional,
            actor=actor,
            ahora=ahora,
        )

    def listar_historial(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        pieza_fdi: object | None = None,
    ) -> list[Hallazgo]:
        """Historial del paciente (o de una pieza) ordenado por `fecha`."""
        # RBAC/401 antes de cualquier lookup: la identidad de paciente no tiene
        # sesión en v1 y no debe filtrar si el paciente existe.
        self._exigir_lectura(actor, paciente_id)
        tenant_id = actor.tenant_id
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        if pieza_fdi is None:
            return self._hallazgos.listar_por_paciente(
                tenant_id=tenant_id, paciente_id=paciente_id
            )
        pieza = validar_pieza_fdi(pieza_fdi)
        return self._hallazgos.listar_por_pieza(
            tenant_id=tenant_id, paciente_id=paciente_id, pieza_fdi=pieza
        )

    def resolver(self, actor: Actor, *, hallazgo_id: str) -> Hallazgo:
        """Marca `resuelto=false → true` una única vez (409 al repetir)."""
        self._exigir_rol(actor, _ESCRIBE_CLINICA)
        tenant_id = actor.tenant_id
        hallazgo = self._hallazgos.obtener(tenant_id=tenant_id, hallazgo_id=hallazgo_id)
        if hallazgo is None:
            raise NoEncontrado("hallazgo no encontrado")
        self._exigir_firma_y_paciente(actor, hallazgo)
        self._exigir_consentimiento(tenant_id, hallazgo.paciente_id)
        if hallazgo.resuelto:
            raise Conflicto("hallazgo ya resuelto")
        resuelto = self._hallazgos.marcar_resuelto(
            tenant_id=tenant_id, hallazgo_id=hallazgo_id
        )
        self._auditar(
            tenant_id,
            "HALLAZGO_RESUELTO",
            actor.user_id,
            "hallazgo",
            hallazgo.id,
            antes={"resuelto": False},
            despues={"resuelto": True},
        )
        return resuelto

    # ------------------------------------------------------------------
    # Derivación atómica hallazgo → línea (D3)
    # ------------------------------------------------------------------

    def derivar(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        pieza_fdi: object,
        hallazgo: str,
        fecha: datetime,
        prestacion_id: str,
        idempotency_key: str | None,
        superficie: object | None = None,
        profesional_id: str | None = None,
        monto: int | None = None,
        ahora: datetime | None = None,
    ) -> Derivacion:
        """Registra el hallazgo y su línea en una sola unidad de trabajo."""
        clave = self._normalizar_key(idempotency_key)
        tenant_id, pieza, profesional, superficie_limpia = self._validar_clinico(
            actor,
            paciente_id=paciente_id,
            pieza_fdi=pieza_fdi,
            hallazgo=hallazgo,
            fecha=fecha,
            superficie=superficie,
            profesional_id=profesional_id,
        )
        precio_base = self._prestaciones.precio_base(
            tenant_id=tenant_id, prestacion_id=prestacion_id
        )
        if precio_base is None:
            raise NoEncontrado("prestación no encontrada")
        monto_efectivo = validar_monto(precio_base if monto is None else monto)

        # Replay fuera de la unidad de trabajo: no se escribe nada.
        existente = self._lineas.por_idempotency_key(
            tenant_id=tenant_id, idempotency_key=clave
        )
        if existente is not None:
            return self._replay(
                tenant_id=tenant_id,
                existente=existente,
                pieza_fdi=pieza,
                superficie=superficie_limpia,
                hallazgo=hallazgo,
                profesional_id=profesional,
                prestacion_id=prestacion_id,
                monto=monto_efectivo,
            )

        try:
            with self._uow_factory():
                # Recheck dentro de la unidad de trabajo: cierra la ventana
                # entre el SELECT de arriba y el INSERT de la línea.
                existente = self._lineas.por_idempotency_key(
                    tenant_id=tenant_id, idempotency_key=clave
                )
                if existente is not None:
                    return self._replay(
                        tenant_id=tenant_id,
                        existente=existente,
                        pieza_fdi=pieza,
                        superficie=superficie_limpia,
                        hallazgo=hallazgo,
                        profesional_id=profesional,
                        prestacion_id=prestacion_id,
                        monto=monto_efectivo,
                    )
                creado = self._crear_hallazgo(
                    tenant_id=tenant_id,
                    paciente_id=paciente_id,
                    pieza_fdi=pieza,
                    superficie=superficie_limpia,
                    hallazgo=hallazgo,
                    fecha=fecha,
                    profesional_id=profesional,
                    actor=actor,
                    ahora=ahora,
                )
                presupuesto = self._presupuesto_borrador(tenant_id, paciente_id, ahora)
                self._auditar(
                    tenant_id,
                    "LINEA_PRESUPESTADA",
                    actor.user_id,
                    "presupuesto",
                    presupuesto.id,
                    despues={
                        "paciente_id": paciente_id,
                        "pieza_fdi": pieza,
                        "prestacion_id": prestacion_id,
                        "monto_centavos": monto_efectivo,
                        "hallazgo_id": creado.id,
                    },
                )
                try:
                    linea = self._lineas.agregar(
                        tenant_id=tenant_id,
                        presupuesto_id=presupuesto.id,
                        prestacion_id=prestacion_id,
                        monto=monto_efectivo,
                        cobertura_os=0,
                        a_cargo_paciente=monto_efectivo,
                        origen_cobertura="SIN_COBERTURA",
                        validada_en_vivo=False,
                        pieza_fdi=pieza,
                        hallazgo_id=creado.id,
                        idempotency_key=clave,
                        ahora=ahora,
                    )
                except IdempotencyKeyDuplicada as exc:
                    raise _CarreraIdempotencia from exc
        except _CarreraIdempotencia:
            # El INSERT perdió la carrera: se relee la fila ganadora y se
            # responde replay o 409, nunca 500 (D3.2). La unidad de trabajo ya
            # revirtió el hallazgo que había creado esta transacción.
            ganadora = self._lineas.por_idempotency_key(
                tenant_id=tenant_id, idempotency_key=clave
            )
            if ganadora is None:
                raise Conflicto("conflicto de idempotencia en la derivación") from None
            return self._replay(
                tenant_id=tenant_id,
                existente=ganadora,
                pieza_fdi=pieza,
                superficie=superficie_limpia,
                hallazgo=hallazgo,
                profesional_id=profesional,
                prestacion_id=prestacion_id,
                monto=monto_efectivo,
            )
        return Derivacion(hallazgo=creado, linea=linea, creada=True)

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _presupuesto_borrador(
        self, tenant_id: str, paciente_id: str, ahora: datetime | None
    ) -> Presupuesto:
        existente = self._presupuestos.borrador_de_paciente(
            tenant_id=tenant_id, paciente_id=paciente_id
        )
        if existente is not None:
            return existente
        return self._presupuestos.crear(
            tenant_id=tenant_id, paciente_id=paciente_id, ahora=ahora
        )

    def _crear_hallazgo(
        self,
        *,
        tenant_id: str,
        paciente_id: str,
        pieza_fdi: int,
        superficie: str | None,
        hallazgo: str,
        fecha: datetime,
        profesional_id: str,
        actor: Actor,
        ahora: datetime | None,
    ) -> Hallazgo:
        creado = self._hallazgos.registrar(
            tenant_id=tenant_id,
            paciente_id=paciente_id,
            pieza_fdi=pieza_fdi,
            superficie=superficie,
            hallazgo=hallazgo,
            fecha=fecha,
            profesional_id=profesional_id,
            ahora=self._momento(ahora),
        )
        self._auditar(
            tenant_id,
            "HALLAZGO_REGISTRADO",
            actor.user_id,
            "hallazgo",
            creado.id,
            # Sin el texto clínico: sólo ids, pieza y fecha (RN-CL-04).
            despues={
                "paciente_id": paciente_id,
                "pieza_fdi": pieza_fdi,
                "profesional_id": profesional_id,
                "fecha": fecha.isoformat(),
            },
        )
        return creado

    def _validar_clinico(
        self,
        actor: Actor,
        *,
        paciente_id: str,
        pieza_fdi: object,
        hallazgo: object,
        fecha: datetime,
        superficie: object | None,
        profesional_id: str | None,
    ) -> tuple[str, int, str, str | None]:
        self._exigir_rol(actor, _ESCRIBE_CLINICA)
        self._exigir_aware(fecha)
        if not isinstance(hallazgo, str) or not hallazgo.strip():
            raise Invalido("hallazgo requerido")
        superficie_limpia = self._validar_superficie(superficie)
        pieza = validar_pieza_fdi(pieza_fdi)
        tenant_id = actor.tenant_id
        if not self._pacientes.existe(tenant_id=tenant_id, paciente_id=paciente_id):
            raise NoEncontrado("paciente no encontrado")
        profesional = self._profesional_efectivo(actor, profesional_id)
        if not self._profesionales.existe(
            tenant_id=tenant_id, profesional_id=profesional
        ):
            raise NoEncontrado("profesional no encontrado")
        self._exigir_firma_y_paciente(actor, _SoloPaciente(paciente_id, profesional))
        self._exigir_consentimiento(tenant_id, paciente_id)
        return tenant_id, pieza, profesional, superficie_limpia

    def _profesional_efectivo(self, actor: Actor, profesional_id: str | None) -> str:
        if actor.rol == "ODONTOLOGO":
            if profesional_id is not None and profesional_id != actor.profesional_id:
                raise Prohibido("odontólogo sólo firma sus propios hallazgos")
            if actor.profesional_id is None:
                raise Prohibido("odontólogo sin profesional asociado")
            return actor.profesional_id
        if profesional_id is None:
            raise Invalido("profesional requerido")
        return profesional_id

    def _exigir_firma_y_paciente(
        self, actor: Actor, hallazgo: Hallazgo | _SoloPaciente
    ) -> None:
        if actor.rol != "ODONTOLOGO":
            return
        if actor.profesional_id is None or actor.profesional_id != hallazgo.profesional_id:
            raise Prohibido("odontólogo sólo opera sobre sus propios hallazgos")
        if not self._turnos.atiende(
            tenant_id=actor.tenant_id,
            profesional_id=actor.profesional_id,
            paciente_id=hallazgo.paciente_id,
        ):
            raise Prohibido("odontólogo no atiende a este paciente")

    def _exigir_lectura(self, actor: Actor, paciente_id: str) -> None:
        self._exigir_rol(actor, _LEE_CLINICA)
        if actor.rol == "ODONTOLOGO" and (
            actor.profesional_id is None
            or not self._turnos.atiende(
                tenant_id=actor.tenant_id,
                profesional_id=actor.profesional_id,
                paciente_id=paciente_id,
            )
        ):
            raise Prohibido("odontólogo no atiende a este paciente")

    def _exigir_consentimiento(self, tenant_id: str, paciente_id: str) -> None:
        if not self._consentimientos.firmado(
            tenant_id=tenant_id, paciente_id=paciente_id
        ):
            raise ConsentimientoRequerido("CONSENTIMIENTO_REQUERIDO")

    def _replay(
        self,
        *,
        tenant_id: str,
        existente: Linea,
        pieza_fdi: int,
        superficie: str | None,
        hallazgo: str,
        profesional_id: str,
        prestacion_id: str,
        monto: int,
    ) -> Derivacion:
        previo = (
            self._hallazgos.obtener(
                tenant_id=tenant_id, hallazgo_id=existente.hallazgo_id
            )
            if existente.hallazgo_id is not None
            else None
        )
        if previo is None:
            raise Conflicto("derivación previa inconsistente")
        coincide = (
            previo.pieza_fdi == pieza_fdi
            and previo.superficie == superficie
            and previo.hallazgo == hallazgo
            and previo.profesional_id == profesional_id
            and existente.prestacion_id == prestacion_id
            and existente.monto == monto
        )
        if not coincide:
            raise Conflicto("Idempotency-Key reutilizada con otro payload")
        return Derivacion(hallazgo=previo, linea=existente, creada=False)

    @staticmethod
    def _normalizar_key(idempotency_key: str | None) -> str:
        if not isinstance(idempotency_key, str) or not idempotency_key.strip():
            raise Invalido("Idempotency-Key requerido (UUID)")
        try:
            clave = uuid.UUID(idempotency_key)
        except (ValueError, AttributeError, TypeError) as exc:
            raise Invalido("Idempotency-Key inválido: se espera un UUID") from exc
        return str(clave)

    @staticmethod
    def _validar_superficie(superficie: object | None) -> str | None:
        if superficie is None:
            return None
        if not isinstance(superficie, str) or not superficie.strip():
            raise Invalido("superficie no puede estar vacía")
        return superficie

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    @staticmethod
    def _exigir_rol(actor: Actor, roles: frozenset[str]) -> None:
        if actor.rol == "PACIENTE":
            # v1 no tiene sesión de paciente (D13): 401, no 403.
            raise NoAutenticado("sesión interna requerida")
        if actor.rol not in roles:
            raise Prohibido("rol sin permiso")

    @staticmethod
    def _exigir_aware(valor: datetime) -> None:
        if valor.tzinfo is None or valor.tzinfo.utcoffset(valor) is None:
            raise Invalido("fecha debe ser timezone-aware")

    def _auditar(
        self,
        tenant_id: str,
        accion: AccionOdontograma,
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


@dataclass(frozen=True)
class _SoloPaciente:
    """Vista mínima para reutilizar el chequeo de firma/paciente al registrar."""

    paciente_id: str
    profesional_id: str
