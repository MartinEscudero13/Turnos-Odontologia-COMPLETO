"""Helpers compartidos por los tests de C-07 (no recolectados por pytest).

Cablea `ServicioTurnos`, `ServicioListaEspera`, `ServicioAutoOferta`, los puertos
en memoria y (opcionalmente) `ServicioReservasPublicas` con reloj congelado
mutable. Todo dato es ficticio (R1).
"""
from __future__ import annotations

from datetime import datetime, time

from conftest import P1, P2, S1, S2, T1, T2, dt
from fastapi.testclient import TestClient

from app.lista_espera.puertos import (
    AuditoriaMemoria,
    HuecoLiberadoMemoria,
    HuecoRetenido,
    ListaEsperaMemoria,
    NotificadorNulo,
    OfertaMemoria,
    OfertaPortMemoria,
)
from app.lista_espera.servicio import ServicioListaEspera
from app.lista_espera.worker import ServicioAutoOferta
from app.reservas.antispam import ContadorMemoria, VerificadorMemoria
from app.reservas.puertos import (
    AuditoriaMemoria as AuditoriaMemoriaPublica,
)
from app.reservas.puertos import (
    CatalogoMemoria,
    HorarioSemanal,
    Paciente,
    PacienteMemoria,
    Prestacion,
    Profesional,
    Sillon,
    TenantMemoria,
)
from app.reservas.puertos import (
    NotificadorNulo as NotificadorNuloPublico,
)
from app.reservas.servicio import ServicioReservasPublicas
from app.reservas.tokens import TokenRepositorioEnMemoria
from app.routers.lista_espera import crear_app as crear_app_lista
from app.routers.reservas_publicas import crear_app_publica
from app.turnos.servicio import Actor, NoEncontrado, ServicioTurnos, Turno

PREST30 = "PREST-30"
PREST45 = "PREST-45"

OFERTA_TTL_MIN = 120


class HarnessLista:
    """Dominio C-07 + reserva pública cableados en memoria, con reloj congelado."""

    def __init__(
        self,
        *,
        oferta_ttl_min: int = OFERTA_TTL_MIN,
        horizonte_dias: int = 7,
        reloj_inicial: datetime | None = None,
    ) -> None:
        self.turnos = ServicioTurnos(anticipacion_min_horas=0.0)
        self.catalogo = CatalogoMemoria()
        self.pacientes = PacienteMemoria()
        self.tenants = TenantMemoria({"t1": (T1, True), "t2": (T2, True)})
        self.lista_repo = ListaEsperaMemoria()
        self.oferta_repo = OfertaMemoria()
        self.auditoria = AuditoriaMemoria()
        self.auditoria_publica = AuditoriaMemoriaPublica()
        self._reloj = {"ahora": reloj_inicial or dt("2026-10-05", 9)}

        self.svc_lista = ServicioListaEspera(
            self.lista_repo,
            self.oferta_repo,
            self.catalogo,
            self.pacientes,
            self.auditoria,
            reloj=lambda: self._reloj["ahora"],
        )
        self.svc_ofertas = ServicioAutoOferta(
            self.turnos,
            self.lista_repo,
            self.oferta_repo,
            self.auditoria,
            NotificadorNulo(),
            oferta_ttl_min=oferta_ttl_min,
            reloj=lambda: self._reloj["ahora"],
        )
        self.hueco_port = HuecoLiberadoMemoria(handler=self.svc_ofertas.procesar_hueco_liberado)
        self.oferta_port = OfertaPortMemoria(self.oferta_repo, self._resolver_slot)
        self._horizonte_dias = horizonte_dias

    # ---- reloj ----

    def fijar_ahora(self, dia: str, hora: int = 9, minuto: int = 0) -> datetime:
        self._reloj["ahora"] = dt(dia, hora, minuto)
        return self._reloj["ahora"]

    @property
    def ahora(self) -> datetime:
        return self._reloj["ahora"]

    # ---- siembra ----

    def seed_catalogo(self, tenant: str = T1) -> None:
        c = self.catalogo
        c.agregar_prestacion(Prestacion(id=PREST30, tenant_id=tenant, duracion_min=30))
        c.agregar_prestacion(Prestacion(id=PREST45, tenant_id=tenant, duracion_min=45))
        for p in (P1, P2):
            c.agregar_profesional(Profesional(id=p, tenant_id=tenant))
        for s in (S1, S2):
            c.agregar_sillon(Sillon(id=s, tenant_id=tenant))
        for dia in range(1, 8):
            for p in (P1, P2):
                c.agregar_horario(
                    HorarioSemanal(
                        tenant_id=tenant, dia=dia, desde=time(9, 0), hasta=time(12, 0), profesional_id=p
                    )
                )
            c.agregar_horario(
                HorarioSemanal(tenant_id=tenant, dia=dia, desde=time(8, 0), hasta=time(18, 0), profesional_id=None)
            )
        for p in (P1, P2):
            c.agregar_habilitado(tenant, p, PREST30)
            c.agregar_habilitado(tenant, p, PREST45)

    def seed_paciente(self, paciente_id: str, tenant: str = T1) -> None:
        self.pacientes.agregar(
            Paciente(id=paciente_id, tenant_id=tenant, nombre="Paciente Demo", telefono="+5491100000001")
        )

    # ---- acciones de dominio ----

    def alta_entrada(self, *, paciente_id: str, prestacion_id: str = PREST30, tenant: str = T1, **kwargs):
        return self.svc_lista.alta(
            Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1"),
            paciente_id=paciente_id,
            prestacion_id=prestacion_id,
            **kwargs,
        )

    def crear_turno(
        self,
        *,
        paciente_id: str,
        inicio: datetime,
        prestacion_id: str = PREST30,
        duracion_min: int = 30,
        tenant: str = T1,
        profesional_id: str = P1,
        sillon_id: str = S1,
    ) -> Turno:
        return self.turnos.crear(
            Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1"),
            profesional_id=profesional_id,
            sillon_id=sillon_id,
            paciente_id=paciente_id,
            prestacion_id=prestacion_id,
            inicio=inicio,
            duracion_min=duracion_min,
        )

    def cancelar_turno(self, turno_id: str, tenant: str = T1, *, ahora: datetime | None = None) -> Turno:
        return self.turnos.cancelar(
            Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1"), turno_id, ahora=ahora
        )

    def _resolver_slot(self, tenant_id: str, turno_id: str) -> HuecoRetenido | None:
        try:
            t = self.turnos.obtener(
                Actor(tenant_id=tenant_id, rol="RECEPCION", user_id="slot"), turno_id
            )
        except NoEncontrado:
            return None
        return HuecoRetenido(
            tenant_id=tenant_id,
            hueco_turno_id=turno_id,
            profesional_id=t.profesional_id,
            sillon_id=t.sillon_id,
            inicio=t.inicio,
            fin=t.fin,
        )

    # ---- reserva pública (hold) ----

    def build_publico(self) -> tuple[ServicioReservasPublicas, TestClient]:
        svc = ServicioReservasPublicas(
            self.turnos,
            self.catalogo,
            self.pacientes,
            self.tenants,
            TokenRepositorioEnMemoria(),
            ContadorMemoria(),
            VerificadorMemoria(ttl_min=10, canal="captcha"),
            self.auditoria_publica,
            NotificadorNuloPublico(),
            hueco_port=self.hueco_port,
            oferta_port=self.oferta_port,
            rate_limit_max=1000,
            rate_limit_ventana_s=60,
            horizonte_dias=self._horizonte_dias,
            reloj=lambda: self._reloj["ahora"],
        )
        return svc, TestClient(crear_app_publica(svc))

    # ---- borde lista de espera (API) ----

    def build_lista(self) -> TestClient:
        return TestClient(crear_app_lista(self.svc_lista, self.svc_ofertas, self.tenants))
