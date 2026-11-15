"""Composition root for the C-05/C-06 demo.

This is intentionally in-memory: it makes the already-tested domain reachable
through HTTP without pretending that the remaining domains have production
persistence. Restarting the process resets this state.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from app.reservas.antispam import ContadorMemoria, VerificadorMemoria
from app.reservas.puertos import (
    AuditoriaMemoria,
    CatalogoMemoria,
    HorarioSemanal,
    NotificadorNulo,
    PacienteMemoria,
    Prestacion,
    Profesional,
    Sillon,
    TenantMemoria,
)
from app.reservas.servicio import ServicioReservasPublicas
from app.reservas.tokens import TokenRepositorioEnMemoria
from app.seed import DEMO_TENANT_ID, DEMO_TENANT_SLUG
from app.turnos.servicio import ServicioTurnos

PRESTACION_CONSULTA = "prestacion-consulta-demo"
PRESTACION_LIMPIEZA = "prestacion-limpieza-demo"
PROFESIONAL_DEMO_1 = "profesional-demo-1"
PROFESIONAL_DEMO_2 = "profesional-demo-2"
SILLON_DEMO_1 = "sillon-demo-1"
SILLON_DEMO_2 = "sillon-demo-2"


@dataclass(frozen=True)
class DemoServices:
    turnos: ServicioTurnos
    reservas: ServicioReservasPublicas
    catalogo: CatalogoMemoria
    pacientes: PacienteMemoria
    auditoria: AuditoriaMemoria


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


def build_demo_services() -> DemoServices:
    turnos = ServicioTurnos()
    catalogo = _seed_catalogo()
    pacientes = PacienteMemoria()
    tenants = TenantMemoria({DEMO_TENANT_SLUG: (DEMO_TENANT_ID, True)})
    tokens = TokenRepositorioEnMemoria()
    contador = ContadorMemoria()
    verificador = VerificadorMemoria(ttl_min=10, canal="captcha")
    auditoria = AuditoriaMemoria()
    reservas = ServicioReservasPublicas(
        turnos,
        catalogo,
        pacientes,
        tenants,
        tokens,
        contador,
        verificador,
        auditoria,
        NotificadorNulo(),
        rate_limit_max=1000,
        rate_limit_ventana_s=60,
        horizonte_dias=7,
    )
    return DemoServices(
        turnos=turnos,
        reservas=reservas,
        catalogo=catalogo,
        pacientes=pacientes,
        auditoria=auditoria,
    )
