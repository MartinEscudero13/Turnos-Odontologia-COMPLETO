"""Helpers compartidos por los tests de C-08 (no recolectados por pytest).

Cablea `ServicioFichaClinica` con puertos en memoria y datos ficticios
("Paciente Demo", profesional P1/P2). Ningún test usa el reloj real: los
escenarios inyectan `ahora=` fijo en `-03:00`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import T1

from app.ficha_clinica.puertos import (
    AdjuntoMemoria,
    AuditoriaMemoria,
    ConsentimientoMemoria,
    EvolucionMemoria,
    FichaMemoria,
    PacienteMemoria,
    ProfesionalMemoria,
    TurnoMemoria,
)
from app.ficha_clinica.servicio import ServicioFichaClinica
from app.turnos.servicio import Actor

TZ = timezone(timedelta(hours=-3))


def d3(dia: str = "2026-11-10", hora: int = 10, minuto: int = 0) -> datetime:
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, minuto, tzinfo=TZ)


def actor(rol: str, tenant: str = T1, user_id: str = "usuario-1", profesional_id: str | None = None) -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id, profesional_id=profesional_id)


class HarnessClinica:
    """Dominio C-08 cableado en memoria, sin reloj real."""

    def __init__(self) -> None:
        self.fichas = FichaMemoria()
        self.evoluciones = EvolucionMemoria()
        self.adjuntos = AdjuntoMemoria()
        self.consentimientos = ConsentimientoMemoria()
        self.pacientes = PacienteMemoria()
        self.profesionales = ProfesionalMemoria()
        self.turnos = TurnoMemoria()
        self.auditoria = AuditoriaMemoria()
        self.svc = ServicioFichaClinica(
            self.fichas,
            self.evoluciones,
            self.adjuntos,
            self.consentimientos,
            self.pacientes,
            self.profesionales,
            self.turnos,
            self.auditoria,
        )

    def seed_paciente(self, paciente_id: str, tenant: str = T1) -> None:
        self.pacientes.agregar(tenant, paciente_id)

    def seed_profesional(self, profesional_id: str, tenant: str = T1) -> None:
        self.profesionales.agregar(tenant, profesional_id)

    def seed_atiende(self, profesional_id: str, paciente_id: str, tenant: str = T1) -> None:
        self.turnos.agregar(tenant, profesional_id, paciente_id)

    def dar_consentimiento(self, paciente_id: str, tenant: str = T1) -> None:
        self.svc.registrar_consentimiento(
            actor("RECEPCION", tenant=tenant, user_id="recep-1"),
            paciente_id=paciente_id,
            timestamp=d3(),
            canal="móvil",
        )
