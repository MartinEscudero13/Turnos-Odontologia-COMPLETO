"""Composition root for the demo API (C-05, C-06, C-07, C-10 and C-11).

This is intentionally in-memory: it makes the already-tested domain reachable
through HTTP without pretending that the remaining domains have production
persistence. Restarting the process resets this state, and no real patient data
or credentials are used anywhere (RN-GL-03).
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone

from app.caja.puertos import (
    AjustePostCierreMemoria,
    CierreMemoria,
    CobroPendienteMemoria,
    CuentaPorCobrarOSMemoria,
    MovimientoMemoria,
    TurnoMemoria,
    UnidadDeTrabajoMemoria,
    UsuarioMemoria,
)
from app.caja.puertos import (
    AuditoriaMemoria as AuditoriaCajaMemoria,
)
from app.caja.servicio import ServicioCaja
from app.calendario.puertos import (
    AuditoriaMemoria as AuditoriaCalendarioMemoria,
)
from app.calendario.puertos import (
    ColaCalendarioMemoria,
    EventoMemoria,
    LinkMemoria,
    PasarelaGoogleFake,
    TurnoCalendario,
    TurnosCalendarioMemoria,
)
from app.calendario.servicio import ServicioCalendario
from app.ficha_clinica.puertos import (
    AdjuntoMemoria,
    ConsentimientoMemoria,
    EvolucionMemoria,
    FichaMemoria,
    ProfesionalMemoria,
)
from app.ficha_clinica.puertos import (
    AuditoriaMemoria as AuditoriaFichaMemoria,
)
from app.ficha_clinica.puertos import (
    PacienteMemoria as PacienteFichaMemoria,
)
from app.ficha_clinica.puertos import (
    TurnoMemoria as TurnoFichaMemoria,
)
from app.ficha_clinica.servicio import ServicioFichaClinica
from app.lista_espera.puertos import (
    AuditoriaMemoria as AuditoriaListaMemoria,
)
from app.lista_espera.puertos import (
    HuecoLiberadoMemoria,
    HuecoRetenido,
    ListaEsperaMemoria,
    OfertaMemoria,
    OfertaPortMemoria,
)
from app.lista_espera.puertos import (
    NotificadorNulo as NotificadorListaNulo,
)
from app.lista_espera.servicio import ServicioListaEspera
from app.lista_espera.worker import ServicioAutoOferta
from app.obras_sociales.adaptadores import CoberturaPresupuesto
from app.obras_sociales.puertos import (
    AuditoriaMemoria as AuditoriaObrasSocialesMemoria,
)
from app.obras_sociales.puertos import (
    CoberturaMemoria as CoberturaObrasSocialesMemoria,
)
from app.obras_sociales.puertos import (
    LiquidacionMemoria,
    ObraSocialMemoria,
    PacienteObraSocialMemoria,
    PrestacionPrecioMemoria,
    TurnoAtendido,
    TurnosAtendidosMemoria,
)
from app.obras_sociales.servicio import ServicioObrasSociales
from app.odontograma.puertos import (
    AuditoriaMemoria as AuditoriaOdontogramaMemoria,
)
from app.odontograma.puertos import (
    HallazgoMemoria,
)
from app.odontograma.puertos import (
    PrestacionMemoria as PrestacionOdontogramaMemoria,
)
from app.odontograma.puertos import (
    UnidadDeTrabajoMemoria as UowOdontogramaMemoria,
)
from app.odontograma.servicio import ServicioOdontograma
from app.presupuesto.puertos import (
    AceptacionMemoria,
    ImputacionMemoria,
    LineaMemoria,
    PresupuestoMemoria,
)
from app.presupuesto.puertos import (
    AuditoriaMemoria as AuditoriaPresupuestoMemoria,
)
from app.presupuesto.puertos import (
    PacienteMemoria as PacientePresupuestoMemoria,
)
from app.presupuesto.puertos import (
    PrestacionMemoria as PrestacionPresupuestoMemoria,
)
from app.presupuesto.puertos import (
    UnidadDeTrabajoMemoria as UowPresupuestoMemoria,
)
from app.presupuesto.servicio import ServicioPresupuesto
from app.reservas.antispam import ContadorMemoria, VerificadorMemoria
from app.reservas.puertos import (
    AuditoriaMemoria,
    CatalogoMemoria,
    HorarioSemanal,
    NotificadorNulo,
    Paciente,
    PacienteMemoria,
    Prestacion,
    Profesional,
    Sillon,
    TenantMemoria,
)
from app.reservas.servicio import ServicioReservasPublicas
from app.reservas.tokens import TokenRepositorioEnMemoria
from app.seed import DEMO_TENANT_ID, DEMO_TENANT_SLUG
from app.senas.adaptadores import AplicacionCajaServicio
from app.senas.aplicacion import ServicioSenasAplicacion
from app.senas.consulta import ServicioSenasConsulta
from app.senas.puertos import (
    AdaptadorPasarelaFake,
    AuditoriaSenaMemoria,
    ConfiguracionSenaMemoria,
    PagoMPMemoria,
    PresupuestosMemoria,
    SenaMemoria,
    TurnoMemoriaSena,
)
from app.senas.servicio import ServicioSenas
from app.senas.webhook import ServicioSenasWebhook
from app.turnos.servicio import Actor, NoEncontrado, ServicioTurnos, Turno

PRESTACION_CONSULTA = "prestacion-consulta-demo"
PRESTACION_LIMPIEZA = "prestacion-limpieza-demo"
PROFESIONAL_DEMO_1 = "profesional-demo-1"
PROFESIONAL_DEMO_2 = "profesional-demo-2"
SILLON_DEMO_1 = "sillon-demo-1"
SILLON_DEMO_2 = "sillon-demo-2"

DEMO_USER_ID = "usuario-demo-recepcion"
DEMO_ADMIN_ID = "usuario-demo-admin"
DEMO_PACIENTE_1 = "paciente-demo-1"
DEMO_PACIENTE_2 = "paciente-demo-2"

PRECIO_CONSULTA_CENTAVOS = 10000
PRECIO_LIMPIEZA_CENTAVOS = 15000

OFERTA_TTL_MIN = 120
SENA_TTL_H = 24
ANTICIPACION_CANCELACION_H = 24
TZ_DEMO = timezone(timedelta(hours=-3))


def demo_periodo_actual(ahora: datetime | None = None) -> tuple[date, date]:
    """Período mensual de la demo: `[primer día, primer día del mes siguiente)`."""
    momento = ahora or datetime.now(TZ_DEMO)
    dia = momento.astimezone(TZ_DEMO).date()
    desde = dia.replace(day=1)
    hasta = (desde.replace(day=28) + timedelta(days=4)).replace(day=1)
    return desde, hasta


@dataclass(frozen=True)
class DemoServices:
    """Services and shared adapters wired once per app instance."""

    turnos: ServicioTurnos
    reservas: ServicioReservasPublicas
    catalogo: CatalogoMemoria
    pacientes: PacienteMemoria
    tenants: TenantMemoria
    auditoria: AuditoriaMemoria
    lista_espera: ServicioListaEspera
    ofertas: ServicioAutoOferta
    hueco_port: HuecoLiberadoMemoria
    oferta_port: OfertaPortMemoria
    caja: ServicioCaja
    senas: ServicioSenas
    senas_consulta: ServicioSenasConsulta
    senas_aplicacion: ServicioSenasAplicacion
    senas_webhook: ServicioSenasWebhook
    ficha_clinica: ServicioFichaClinica
    odontograma: ServicioOdontograma
    presupuesto: ServicioPresupuesto
    obras_sociales: ServicioObrasSociales
    calendario: ServicioCalendario


def _seed_catalogo() -> CatalogoMemoria:
    catalogo = CatalogoMemoria()
    catalogo.agregar_prestacion(
        Prestacion(id=PRESTACION_CONSULTA, tenant_id=DEMO_TENANT_ID, duracion_min=30, nombre="Consulta")
    )
    catalogo.agregar_prestacion(
        Prestacion(id=PRESTACION_LIMPIEZA, tenant_id=DEMO_TENANT_ID, duracion_min=45, nombre="Limpieza")
    )
    catalogo.agregar_profesional(
        Profesional(id=PROFESIONAL_DEMO_1, tenant_id=DEMO_TENANT_ID, nombre="Dra. Demo Uno")
    )
    catalogo.agregar_profesional(
        Profesional(id=PROFESIONAL_DEMO_2, tenant_id=DEMO_TENANT_ID, nombre="Dr. Demo Dos")
    )
    catalogo.agregar_sillon(Sillon(id=SILLON_DEMO_1, tenant_id=DEMO_TENANT_ID))
    catalogo.agregar_sillon(Sillon(id=SILLON_DEMO_2, tenant_id=DEMO_TENANT_ID))
    for dia in range(1, 8):
        for profesional_id in (PROFESIONAL_DEMO_1, PROFESIONAL_DEMO_2):
            catalogo.agregar_horario(
                HorarioSemanal(
                    tenant_id=DEMO_TENANT_ID,
                    dia=dia,
                    desde=time(9, 0),
                    hasta=time(12, 0),
                    profesional_id=profesional_id,
                )
            )
        catalogo.agregar_horario(
            HorarioSemanal(
                tenant_id=DEMO_TENANT_ID,
                dia=dia,
                desde=time(8, 0),
                hasta=time(18, 0),
                profesional_id=None,
            )
        )
    for profesional_id in (PROFESIONAL_DEMO_1, PROFESIONAL_DEMO_2):
        for prestacion_id in (PRESTACION_CONSULTA, PRESTACION_LIMPIEZA):
            catalogo.agregar_habilitado(DEMO_TENANT_ID, profesional_id, prestacion_id)
    return catalogo


def _seed_pacientes() -> PacienteMemoria:
    return PacienteMemoria(
        [
            Paciente(
                id=DEMO_PACIENTE_1,
                tenant_id=DEMO_TENANT_ID,
                nombre="Paciente Demo Uno",
                telefono="+5491130551001",
            ),
            Paciente(
                id=DEMO_PACIENTE_2,
                tenant_id=DEMO_TENANT_ID,
                nombre="Paciente Demo Dos",
                telefono="+5491130551002",
            ),
        ]
    )


def _seed_configuracion_senas() -> ConfiguracionSenaMemoria:
    configuracion = ConfiguracionSenaMemoria()
    configuracion.configurar(tenant_id=DEMO_TENANT_ID, modo="PORCENTAJE", valor=30)
    configuracion.agregar_prestacion(
        tenant_id=DEMO_TENANT_ID,
        prestacion_id=PRESTACION_CONSULTA,
        precio_base_centavos=PRECIO_CONSULTA_CENTAVOS,
    )
    configuracion.agregar_prestacion(
        tenant_id=DEMO_TENANT_ID,
        prestacion_id=PRESTACION_LIMPIEZA,
        precio_base_centavos=PRECIO_LIMPIEZA_CENTAVOS,
        sena_modo="SIN_SENA",
    )
    return configuracion


def build_demo_services(
    reloj: Callable[[], datetime] | None = None,
) -> DemoServices:
    """Build the in-memory demo graph shared by every mounted router."""
    clock: Callable[[], datetime] = reloj or (lambda: datetime.now(UTC))
    turnos = ServicioTurnos()
    catalogo = _seed_catalogo()
    pacientes = _seed_pacientes()
    tenants = TenantMemoria({DEMO_TENANT_SLUG: (DEMO_TENANT_ID, True)})

    # -- C-07 lista de espera + auto-oferta ----------------------------
    lista_repo = ListaEsperaMemoria()
    oferta_repo = OfertaMemoria()
    auditoria_lista = AuditoriaListaMemoria()
    lista_espera = ServicioListaEspera(
        lista_repo,
        oferta_repo,
        catalogo,
        pacientes,
        auditoria_lista,
        reloj=clock,
    )
    ofertas = ServicioAutoOferta(
        turnos,
        lista_repo,
        oferta_repo,
        auditoria_lista,
        NotificadorListaNulo(),
        oferta_ttl_min=OFERTA_TTL_MIN,
        reloj=clock,
    )
    hueco_port = HuecoLiberadoMemoria(handler=_handler_hueco(ofertas))
    oferta_port = OfertaPortMemoria(oferta_repo, _resolver_slot(turnos))

    # -- C-10 caja -----------------------------------------------------
    movimientos = MovimientoMemoria()
    cuentas = CuentaPorCobrarOSMemoria()
    cierres = CierreMemoria(movimientos, cuentas)
    pendientes = CobroPendienteMemoria()
    ajustes = AjustePostCierreMemoria()
    turnos_caja = TurnoMemoria()
    usuarios = UsuarioMemoria()
    auditoria_caja = AuditoriaCajaMemoria()
    usuarios.agregar(DEMO_TENANT_ID, DEMO_USER_ID)
    usuarios.agregar(DEMO_TENANT_ID, DEMO_ADMIN_ID)

    def uow_factory() -> UnidadDeTrabajoMemoria:
        return UnidadDeTrabajoMemoria(
            [movimientos, cierres, pendientes, ajustes, cuentas, auditoria_caja],
            movimientos,
        )

    caja = ServicioCaja(
        movimientos,
        cierres,
        pendientes,
        ajustes,
        cuentas,
        turnos_caja,
        auditoria_caja,
        usuarios=usuarios,
        uow_factory=uow_factory,
        reloj=clock,
    )

    # -- C-11 señas ----------------------------------------------------
    senas_repo = SenaMemoria(reloj=clock)
    pagos = PagoMPMemoria(reloj=clock)
    configuracion = _seed_configuracion_senas()
    pasarela = AdaptadorPasarelaFake()
    auditoria_senas = AuditoriaSenaMemoria()
    turnos_senas = TurnoMemoriaSena()
    senas = ServicioSenas(
        senas_repo,
        configuracion,
        pasarela,
        auditoria_senas,
        tenants=tenants,
        contador=ContadorMemoria(),
        sena_ttl_h=SENA_TTL_H,
        anticipacion_cancelacion_h=ANTICIPACION_CANCELACION_H,
        rate_limit_max=1000,
        rate_limit_ventana_s=60,
        url_pago_base="https://demo.local/pagar",
        url_webhook="https://demo.local/api/webhooks/mercadopago",
        reloj=clock,
    )
    senas_consulta = ServicioSenasConsulta(senas_repo, pagos, reloj=clock)
    senas_aplicacion = ServicioSenasAplicacion(
        senas_repo,
        turnos_senas,
        AplicacionCajaServicio(caja),
        PresupuestosMemoria(),
        auditoria_senas,
        reloj=clock,
    )
    # Sin `MP_WEBHOOK_SECRET` real no se inventan credenciales: el borde queda
    # fail-closed (503 WEBHOOK_NO_CONFIGURADO) hasta configurar el proveedor.
    senas_webhook = ServicioSenasWebhook(
        senas_repo,
        pagos,
        turnos_senas,
        pasarela,
        auditoria_senas,
        secreto=None,
        reloj=clock,
    )

    # -- C-12 obras sociales y liquidación -----------------------------
    atendidos_os = TurnosAtendidosMemoria()
    pacientes_os = PacienteObraSocialMemoria()
    prestaciones_os = PrestacionPrecioMemoria()
    prestaciones_os.agregar(DEMO_TENANT_ID, PRESTACION_CONSULTA, PRECIO_CONSULTA_CENTAVOS)
    prestaciones_os.agregar(DEMO_TENANT_ID, PRESTACION_LIMPIEZA, PRECIO_LIMPIEZA_CENTAVOS)
    obras_sociales = ServicioObrasSociales(
        ObraSocialMemoria(),
        CoberturaObrasSocialesMemoria(),
        LiquidacionMemoria(),
        atendidos_os,
        pacientes_os,
        prestaciones_os,
        AuditoriaObrasSocialesMemoria(),
        reloj=clock,
    )
    admin = Actor(tenant_id=DEMO_TENANT_ID, rol="ADMIN", user_id=DEMO_ADMIN_ID)
    os_norte = obras_sociales.crear_obra_social(admin, nombre="OS Demo Norte")
    os_sur = obras_sociales.crear_obra_social(admin, nombre="OS Demo Sur")
    obras_sociales.crear_obra_social(admin, nombre="OS Demo Centro")
    obras_sociales.configurar_cobertura(
        admin,
        obra_social_id=os_norte.id,
        prestacion_id=PRESTACION_CONSULTA,
        modo="PORCENTAJE",
        valor=50,
        tope_centavos=4000,
    )
    obras_sociales.configurar_cobertura(
        admin,
        obra_social_id=os_norte.id,
        prestacion_id=PRESTACION_LIMPIEZA,
        modo="MONTO",
        valor=8000,
    )
    obras_sociales.configurar_cobertura(
        admin,
        obra_social_id=os_sur.id,
        prestacion_id=PRESTACION_CONSULTA,
        modo="PORCENTAJE",
        valor=30,
    )
    pacientes_os.agregar(DEMO_TENANT_ID, DEMO_PACIENTE_1, os_norte.id)
    pacientes_os.agregar(DEMO_TENANT_ID, DEMO_PACIENTE_2, os_sur.id)
    desde_demo, _ = demo_periodo_actual(clock())
    inicio_demo = datetime.combine(desde_demo, time(10, 0), tzinfo=TZ_DEMO)
    for indice, (paciente_id, prestacion_id, precio) in enumerate(
        (
            (DEMO_PACIENTE_1, PRESTACION_CONSULTA, PRECIO_CONSULTA_CENTAVOS),
            (DEMO_PACIENTE_1, PRESTACION_LIMPIEZA, PRECIO_LIMPIEZA_CENTAVOS),
            (DEMO_PACIENTE_2, PRESTACION_CONSULTA, PRECIO_CONSULTA_CENTAVOS),
        ),
        start=1,
    ):
        atendidos_os.agregar(
            TurnoAtendido(
                turno_id=f"turno-atendido-{indice}",
                paciente_id=paciente_id,
                prestacion_id=prestacion_id,
                inicio=inicio_demo + timedelta(hours=indice),
                precio_base_centavos=precio,
            ),
            tenant_id=DEMO_TENANT_ID,
            obra_social_id=os_norte.id if paciente_id == DEMO_PACIENTE_1 else os_sur.id,
        )

    # -- C-14 Google Calendar -----------------------------------------
    turnos_calendario = TurnosCalendarioMemoria()
    dia_calendario, _ = demo_periodo_actual(clock())
    turnos_calendario.agregar(
        DEMO_TENANT_ID,
        TurnoCalendario(
            turno_id="turno-demo-calendario",
            profesional_id=PROFESIONAL_DEMO_1,
            inicio=datetime.combine(dia_calendario.replace(day=10), time(10, 0), tzinfo=TZ_DEMO),
            fin=datetime.combine(dia_calendario.replace(day=10), time(10, 30), tzinfo=TZ_DEMO),
            estado="PENDIENTE",
            resumen="Turno demo",
        ),
    )
    calendario = ServicioCalendario(
        LinkMemoria(),
        EventoMemoria(),
        ColaCalendarioMemoria(),
        PasarelaGoogleFake(),
        turnos_calendario,
        AuditoriaCalendarioMemoria(),
        reloj=clock,
    )
    calendario.conectar(
        admin,
        profesional_id=PROFESIONAL_DEMO_1,
        gcal_calendar_id="demo-calendar@example.test",
        oauth_ref="demo-oauth-ref",
    )

    # -- C-08 ficha clínica + C-09 odontograma/presupuesto -------------
    consentimientos = ConsentimientoMemoria()
    pacientes_clinicos = PacienteFichaMemoria()
    profesionales_clinicos = ProfesionalMemoria()
    turnos_clinicos = TurnoFichaMemoria()
    for paciente_id in (DEMO_PACIENTE_1, DEMO_PACIENTE_2):
        pacientes_clinicos.agregar(DEMO_TENANT_ID, paciente_id)
        turnos_clinicos.agregar(DEMO_TENANT_ID, PROFESIONAL_DEMO_1, paciente_id)
    for profesional_id in (PROFESIONAL_DEMO_1, PROFESIONAL_DEMO_2):
        profesionales_clinicos.agregar(DEMO_TENANT_ID, profesional_id)

    ficha_clinica = ServicioFichaClinica(
        FichaMemoria(),
        EvolucionMemoria(),
        AdjuntoMemoria(),
        consentimientos,
        pacientes_clinicos,
        profesionales_clinicos,
        turnos_clinicos,
        AuditoriaFichaMemoria(),
        reloj=clock,
    )

    presupuestos_repo = PresupuestoMemoria()
    lineas_repo = LineaMemoria()
    prestaciones_odonto = PrestacionOdontogramaMemoria()
    prestaciones_odonto.agregar(DEMO_TENANT_ID, PRESTACION_CONSULTA, PRECIO_CONSULTA_CENTAVOS)
    prestaciones_odonto.agregar(DEMO_TENANT_ID, PRESTACION_LIMPIEZA, PRECIO_LIMPIEZA_CENTAVOS)
    hallazgos_repo = HallazgoMemoria()
    auditoria_odonto = AuditoriaOdontogramaMemoria()
    odontograma = ServicioOdontograma(
        hallazgos_repo,
        presupuestos_repo,
        lineas_repo,
        prestaciones_odonto,
        pacientes_clinicos,
        profesionales_clinicos,
        turnos_clinicos,
        consentimientos,
        auditoria_odonto,
        uow_factory=lambda: UowOdontogramaMemoria(
            [hallazgos_repo, presupuestos_repo, lineas_repo, auditoria_odonto]
        ),
        reloj=clock,
    )

    pacientes_presupuesto = PacientePresupuestoMemoria()
    pacientes_presupuesto.agregar(DEMO_TENANT_ID, DEMO_PACIENTE_1, os_norte.id)
    pacientes_presupuesto.agregar(DEMO_TENANT_ID, DEMO_PACIENTE_2, os_sur.id)
    prestaciones_presupuesto = PrestacionPresupuestoMemoria()
    prestaciones_presupuesto.agregar(DEMO_TENANT_ID, PRESTACION_CONSULTA, PRECIO_CONSULTA_CENTAVOS)
    prestaciones_presupuesto.agregar(DEMO_TENANT_ID, PRESTACION_LIMPIEZA, PRECIO_LIMPIEZA_CENTAVOS)
    aceptaciones_repo = AceptacionMemoria()
    auditoria_presupuesto = AuditoriaPresupuestoMemoria()
    presupuesto = ServicioPresupuesto(
        presupuestos_repo,
        lineas_repo,
        aceptaciones_repo,
        prestaciones_presupuesto,
        pacientes_presupuesto,
        CoberturaPresupuesto(obras_sociales),
        ImputacionMemoria(),
        auditoria_presupuesto,
        consentimientos=consentimientos,
        uow_factory=lambda: UowPresupuestoMemoria(
            [presupuestos_repo, lineas_repo, aceptaciones_repo, auditoria_presupuesto],
            lineas_repo,
        ),
        reloj=clock,
    )

    # -- C-06 reserva pública (con el enganche de C-11) ----------------
    auditoria_publica = AuditoriaMemoria()
    reservas = ServicioReservasPublicas(
        turnos,
        catalogo,
        pacientes,
        tenants,
        TokenRepositorioEnMemoria(),
        ContadorMemoria(),
        VerificadorMemoria(ttl_min=10, canal="captcha"),
        auditoria_publica,
        NotificadorNulo(),
        hueco_port=hueco_port,
        oferta_port=oferta_port,
        rate_limit_max=1000,
        rate_limit_ventana_s=60,
        horizonte_dias=7,
        reloj=clock,
        sena_port=senas,
    )

    return DemoServices(
        turnos=turnos,
        reservas=reservas,
        catalogo=catalogo,
        pacientes=pacientes,
        tenants=tenants,
        auditoria=auditoria_publica,
        lista_espera=lista_espera,
        ofertas=ofertas,
        hueco_port=hueco_port,
        oferta_port=oferta_port,
        caja=caja,
        senas=senas,
        senas_consulta=senas_consulta,
        senas_aplicacion=senas_aplicacion,
        senas_webhook=senas_webhook,
        ficha_clinica=ficha_clinica,
        odontograma=odontograma,
        presupuesto=presupuesto,
        obras_sociales=obras_sociales,
        calendario=calendario,
    )


def _handler_hueco(ofertas: ServicioAutoOferta) -> Callable[[str, str], None]:
    """Adapt the auto-offer worker to the port signature (drops the offer result)."""

    def handler(tenant_id: str, turno_id: str) -> None:
        ofertas.procesar_hueco_liberado(tenant_id, turno_id)

    return handler


def _resolver_slot(turnos: ServicioTurnos) -> Callable[[str, str], HuecoRetenido | None]:
    """Resolve a held slot from C-05 without leaking cross-tenant turns."""

    def resolver(tenant_id: str, turno_id: str) -> HuecoRetenido | None:
        try:
            turno: Turno = turnos.obtener(
                Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="demo-slot"),
                turno_id,
            )
        except NoEncontrado:
            return None
        return HuecoRetenido(
            tenant_id=tenant_id,
            hueco_turno_id=turno.id,
            profesional_id=turno.profesional_id,
            sillon_id=turno.sillon_id,
            inicio=turno.inicio,
            fin=turno.fin,
        )

    return resolver
