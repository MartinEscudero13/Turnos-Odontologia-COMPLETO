"""Servicio de reserva pública — reusa `ServicioTurnos` de C-05 y lo abre sin login.

Flujo de reserva: resuelve el tenant por el path público, aplica rate-limit y
verificación single-use, identifica al paciente por teléfono E.164 (sin duplicar),
elige un sillón activo libre reusando la disponibilidad server-side, crea el turno
`PENDIENTE` con `origen=RESERVA_ONLINE` vía `ServicioTurnos.crear` y emite un
`token_publico` UUID v4. Cancelar/reprogramar reusan `ServicioTurnos.cancelar`/
`reprogramar` con su comparación de anticipación (borde exacto acepta, D6).

Todo error de dominio sale por `TurnoError` (código HTTP) para que el router lo mapee.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.logging import get_logger
from app.reservas.disponibilidad import DisponibilidadSlot, calcular_disponibilidad
from app.reservas.puertos import (
    AccionAuditada,
    AccionPublica,
    AuditoriaPort,
    CatalogoPort,
    ContadorPort,
    DesafioPublico,
    NotificadorPort,
    Paciente,
    PacientePort,
    Prestacion,
    Profesional,
    Sillon,
    TenantPort,
    TokenRepositorio,
    VerificadorPort,
    normalizar_telefono_e164,
)
from app.turnos.alternativas import Alternativa, HuecoOcupado, buscar_alternativas
from app.turnos.servicio import (
    Actor,
    ConflictoSolape,
    Invalido,
    NoEncontrado,
    Prohibido,
    ServicioTurnos,
    Turno,
    TurnoError,
)

logger = get_logger("app.reservas")

ESTADOS_GESTIONABLES = frozenset({"PENDIENTE", "CONFIRMADO"})

_ACCION_CANCELAR: AccionPublica = "cancelar"
_ACCION_REPROGRAMAR: AccionPublica = "reprogramar"
_ACCION_RESERVAR: AccionPublica = "reservar"


class DemasiadasSolicitudes(TurnoError):
    """429 — rate-limit excedido, con `Retry-After`."""

    codigo = 429

    def __init__(self, mensaje: str, retry_after_s: int) -> None:
        super().__init__(mensaje)
        self.retry_after_s = retry_after_s


@dataclass(frozen=True)
class ReservaCreada:
    turno: Turno
    token_publico: str
    paciente_id: str


class ServicioReservasPublicas:
    """Casos de uso públicos. Dependencias inyectables (D9), sin reloj real (tests)."""

    def __init__(
        self,
        servicio_turnos: ServicioTurnos,
        catalogo: CatalogoPort,
        pacientes: PacientePort,
        tenants: TenantPort,
        tokens: TokenRepositorio,
        contador: ContadorPort,
        verificador: VerificadorPort,
        auditoria: AuditoriaPort,
        notificador: NotificadorPort | None = None,
        *,
        rate_limit_max: int,
        rate_limit_ventana_s: int,
        horizonte_dias: int,
        reloj: Callable[[], datetime] | None = None,
    ) -> None:
        self._servicio_turnos = servicio_turnos
        self._catalogo = catalogo
        self._pacientes = pacientes
        self._tenants = tenants
        self._tokens = tokens
        self._contador = contador
        self._verificador = verificador
        self._auditoria = auditoria
        self._notificador = notificador
        self._rate_limit_max = rate_limit_max
        self._rate_limit_ventana_s = rate_limit_ventana_s
        self._horizonte_dias = horizonte_dias
        self._reloj = reloj or (lambda: datetime.now(UTC))

    @property
    def servicio_turnos(self) -> ServicioTurnos:
        return self._servicio_turnos

    @classmethod
    def _app_default(cls) -> ServicioReservasPublicas:
        """Servicio vacío de respaldo (solo para `crear_app_publica()` sin argumentos)."""
        from app.reservas.antispam import ContadorMemoria, VerificadorMemoria
        from app.reservas.puertos import (
            AuditoriaMemoria,
            CatalogoMemoria,
            PacienteMemoria,
            TenantMemoria,
        )
        from app.reservas.tokens import TokenRepositorioEnMemoria

        return cls(
            ServicioTurnos(),
            CatalogoMemoria(),
            PacienteMemoria(),
            TenantMemoria({}),
            TokenRepositorioEnMemoria(),
            ContadorMemoria(),
            VerificadorMemoria(ttl_min=10, canal="captcha"),
            AuditoriaMemoria(),
            rate_limit_max=10,
            rate_limit_ventana_s=60,
            horizonte_dias=30,
        )

    # ---- helpers ----

    def _momento(self, ahora: datetime | None) -> datetime:
        return ahora if ahora is not None else self._reloj()

    def _resolver_tenant(self, token_tenant: str) -> str:
        tenant_id = self._tenants.resolver(token_tenant)
        if tenant_id is None:
            raise NoEncontrado("recurso no encontrado")
        return tenant_id

    def _chequear_rate_limit(self, tenant_id: str, accion: AccionPublica, ip: str) -> None:
        clave_ip = f"ip:{tenant_id}:{ip}"
        clave_accion = f"accion:{tenant_id}:{accion}"
        n_ip = self._contador.incrementar(clave_ip, self._rate_limit_ventana_s)
        n_accion = self._contador.incrementar(clave_accion, self._rate_limit_ventana_s)
        if n_ip > self._rate_limit_max or n_accion > self._rate_limit_max:
            retry = max(self._contador.ttl_s(clave_ip), self._contador.ttl_s(clave_accion))
            raise DemasiadasSolicitudes("demasiadas solicitudes", retry)

    def _verificar(
        self, tenant_id: str, accion: AccionPublica, verificacion_id: str, ip: str, momento: datetime
    ) -> None:
        if not self._verificador.verificar(
            tenant_id=tenant_id, accion=accion, prueba=verificacion_id, ip=ip, ahora=momento
        ):
            raise Prohibido("verificación inválida")

    def _ocupados(self, tenant_id: str) -> list[HuecoOcupado]:
        actor = Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="publico")
        return [
            HuecoOcupado(
                tenant_id=t.tenant_id,
                profesional_id=t.profesional_id,
                sillon_id=t.sillon_id,
                inicio=t.inicio,
                fin=t.fin,
                estado=t.estado,
                sobreturno=t.sobreturno,
            )
            for t in self._servicio_turnos.listar(actor)
        ]

    def _paciente_o_crear(self, tenant_id: str, nombre: str, telefono_e164: str) -> Paciente:
        existente = self._pacientes.buscar_por_telefono(tenant_id, telefono_e164)
        if existente is not None:
            return existente
        return self._pacientes.crear_minimo(tenant_id, nombre, telefono_e164)

    def _turno_por_token(self, tenant_id: str, token: str, momento: datetime) -> Turno:
        resuelto = self._tokens.resolver(tenant_id, token)
        if resuelto is None:
            raise NoEncontrado("recurso no encontrado")
        actor = Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="publico")
        turno = self._servicio_turnos.obtener(actor, resuelto.turno_id)
        if turno.estado not in ESTADOS_GESTIONABLES or turno.fin <= momento:
            raise NoEncontrado("recurso no encontrado")
        return turno

    def _alternativas(
        self,
        tenant_id: str,
        prestacion: Prestacion,
        profesional: Profesional,
        sillon_id: str,
        desde: datetime,
    ) -> list[Alternativa]:
        ocupados = self._ocupados(tenant_id)
        bloqueos = [
            (b.desde, b.hasta)
            for b in self._catalogo.bloqueos(tenant_id, desde, desde + timedelta(days=30))
        ]
        return buscar_alternativas(
            desde,
            prestacion.duracion_min,
            tenant_id,
            profesional.id,
            sillon_id,
            ocupados,
            bloqueos=bloqueos,
            cantidad=3,
        )

    # ---- disponibilidad ----

    def disponibilidad(
        self,
        token_tenant: str,
        prestacion_id: str,
        profesional_id: str | None,
        desde: datetime,
        ahora: datetime | None = None,
    ) -> list[DisponibilidadSlot]:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        prestacion = self._catalogo.prestacion(tenant_id, prestacion_id)
        if prestacion is None:
            raise NoEncontrado("prestación no encontrada")
        if profesional_id is not None:
            prof = self._catalogo.profesional(tenant_id, profesional_id)
            if prof is None:
                raise NoEncontrado("profesional no encontrado")
            profesionales: Sequence[Profesional] = [prof]
        else:
            profesionales = self._catalogo.profesionales_habilitados(tenant_id, prestacion_id)
        sillones = [s for s in self._catalogo.sillones_activos(tenant_id) if s.activo]
        horario_consultorio = self._catalogo.horario_consultorio(tenant_id)
        bloqueos = self._catalogo.bloqueos(
            tenant_id, desde, desde + timedelta(days=self._horizonte_dias)
        )
        ocupados = self._ocupados(tenant_id)
        resultado: list[DisponibilidadSlot] = []
        for prof in profesionales:
            hp = self._catalogo.horario_profesional(tenant_id, prof.id)
            resultado.extend(
                calcular_disponibilidad(
                    prestacion=prestacion,
                    profesional=prof,
                    sillones=sillones,
                    desde=desde,
                    ahora=momento,
                    horario_profesional=hp,
                    horario_consultorio=horario_consultorio,
                    bloqueos=bloqueos,
                    ocupados=ocupados,
                    horizonte_dias=self._horizonte_dias,
                )
            )
        resultado.sort(key=lambda s: (s.inicio, s.profesional_id, s.sillon_id))
        return resultado

    # ---- verificación ----

    def emitir_verificacion(
        self, token_tenant: str, accion: AccionPublica, ip: str, ahora: datetime | None = None
    ) -> DesafioPublico:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        return self._verificador.desafio(tenant_id=tenant_id, accion=accion, ip=ip, ahora=momento)

    # ---- reserva ----

    def reservar(
        self,
        token_tenant: str,
        *,
        prestacion_id: str,
        profesional_id: str,
        inicio: datetime,
        nombre: str,
        telefono: str,
        verificacion_id: str,
        ip: str,
        ahora: datetime | None = None,
    ) -> ReservaCreada:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        self._chequear_rate_limit(tenant_id, _ACCION_RESERVAR, ip)
        self._verificar(tenant_id, _ACCION_RESERVAR, verificacion_id, ip, momento)

        telefono_e164 = normalizar_telefono_e164(telefono)
        if telefono_e164 is None:
            raise Invalido("teléfono inválido")

        prestacion = self._catalogo.prestacion(tenant_id, prestacion_id)
        if prestacion is None:
            raise NoEncontrado("prestación no encontrada")
        prof = self._catalogo.profesional(tenant_id, profesional_id)
        if prof is None:
            raise NoEncontrado("profesional no encontrado")

        paciente = self._paciente_o_crear(tenant_id, nombre, telefono_e164)
        sillones = [s for s in self._catalogo.sillones_activos(tenant_id) if s.activo]
        sillon_id = self._sillon_libre(tenant_id, prestacion, prof, sillones, inicio, momento)
        sillon_representativo = sillones[0].id if sillones else ""
        if sillon_id is None:
            alts = self._alternativas(
                tenant_id, prestacion, prof, sillon_representativo, inicio
            )
            raise ConflictoSolape("sin hueco disponible", alts)

        actor = Actor(tenant_id=tenant_id, rol="PACIENTE", user_id=paciente.id)
        try:
            turno = self._servicio_turnos.crear(
                actor,
                profesional_id=prof.id,
                sillon_id=sillon_id,
                paciente_id=paciente.id,
                prestacion_id=prestacion.id,
                inicio=inicio,
                duracion_min=prestacion.duracion_min,
                origen="RESERVA_ONLINE",
            )
        except ConflictoSolape:
            alts = self._alternativas(
                tenant_id, prestacion, prof, sillon_representativo, inicio
            )
            raise ConflictoSolape("hueco tomado", alts) from None

        token = self._tokens.emitir(tenant_id, turno.id)
        logger.info(
            "reserva_publica tenant_id=%s turno_id=%s estado=%s inicio=%s fin=%s",
            tenant_id,
            turno.id,
            turno.estado,
            turno.inicio.isoformat(),
            turno.fin.isoformat(),
        )
        self._auditar(tenant_id, turno.id, "CREADO", None, turno.estado)
        if self._notificador is not None:
            self._notificador.reserva_creada(tenant_id=tenant_id, turno_id=turno.id)
        return ReservaCreada(turno=turno, token_publico=token, paciente_id=paciente.id)

    def _sillon_libre(
        self,
        tenant_id: str,
        prestacion: Prestacion,
        prof: Profesional,
        sillones: Sequence[Sillon],
        inicio: datetime,
        momento: datetime,
    ) -> str | None:
        horario_profesional = self._catalogo.horario_profesional(tenant_id, prof.id)
        horario_consultorio = self._catalogo.horario_consultorio(tenant_id)
        bloqueos = self._catalogo.bloqueos(tenant_id, inicio, inicio + timedelta(days=1))
        ocupados = self._ocupados(tenant_id)
        slots = calcular_disponibilidad(
            prestacion=prestacion,
            profesional=prof,
            sillones=sillones,
            desde=inicio,
            ahora=momento,
            horario_profesional=horario_profesional,
            horario_consultorio=horario_consultorio,
            bloqueos=bloqueos,
            ocupados=ocupados,
            horizonte_dias=1,
        )
        for slot in slots:
            if slot.inicio == inicio:
                return slot.sillon_id
        return None

    # ---- consulta ----

    def obtener(self, token_tenant: str, token: str, ahora: datetime | None = None) -> Turno:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        return self._turno_por_token(tenant_id, token, momento)

    # ---- gestión ----

    def cancelar(
        self,
        token_tenant: str,
        token: str,
        verificacion_id: str,
        ip: str,
        ahora: datetime | None = None,
    ) -> Turno:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        turno = self._turno_por_token(tenant_id, token, momento)
        self._chequear_rate_limit(tenant_id, _ACCION_CANCELAR, ip)
        self._verificar(tenant_id, _ACCION_CANCELAR, verificacion_id, ip, momento)

        actor = Actor(tenant_id=tenant_id, rol="PACIENTE", user_id=turno.paciente_id)
        try:
            cancelado = self._servicio_turnos.cancelar(actor, turno.id, ahora=momento)
        except Prohibido:
            self._auditar(
                tenant_id,
                turno.id,
                "CANCELACION_RECHAZADA",
                turno.estado,
                turno.estado,
                motivo="BAJO_ANTICIPACION",
            )
            raise
        self._auditar(tenant_id, turno.id, "CANCELADO", turno.estado, "CANCELADO")
        return cancelado

    def reprogramar(
        self,
        token_tenant: str,
        token: str,
        *,
        nuevo_inicio: datetime,
        verificacion_id: str,
        ip: str,
        ahora: datetime | None = None,
    ) -> ServicioTurnos.Reprogramacion:
        momento = self._momento(ahora)
        tenant_id = self._resolver_tenant(token_tenant)
        turno = self._turno_por_token(tenant_id, token, momento)
        self._chequear_rate_limit(tenant_id, _ACCION_REPROGRAMAR, ip)
        self._verificar(tenant_id, _ACCION_REPROGRAMAR, verificacion_id, ip, momento)

        actor = Actor(tenant_id=tenant_id, rol="PACIENTE", user_id=turno.paciente_id)
        try:
            res = self._servicio_turnos.reprogramar(
                actor, turno.id, nuevo_inicio=nuevo_inicio, ahora=momento
            )
        except Prohibido:
            self._auditar(
                tenant_id,
                turno.id,
                "REPROGRAMACION_RECHAZADA",
                turno.estado,
                turno.estado,
                motivo="BAJO_ANTICIPACION",
            )
            raise
        self._tokens.transferir(token, res.nuevo.id)
        self._auditar(tenant_id, turno.id, "REPROGRAMADO", turno.estado, "REPROGRAMADO")
        self._auditar(tenant_id, res.nuevo.id, "CREADO", None, "PENDIENTE")
        return res

    # ---- auditoría ----

    def _auditar(
        self,
        tenant_id: str,
        turno_id: str,
        accion: AccionAuditada,
        antes: str | None,
        despues: str,
        motivo: str | None = None,
    ) -> None:
        self._auditoria.registrar(
            tenant_id=tenant_id,
            turno_id=turno_id,
            accion=accion,
            actor="publico",
            antes=antes,
            despues=despues,
            motivo=motivo,
        )
