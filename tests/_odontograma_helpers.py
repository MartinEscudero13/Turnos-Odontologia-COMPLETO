"""Helpers compartidos por los tests de C-09 (no recolectados por pytest).

Cablea `ServicioOdontograma` con adaptadores en memoria, datos ficticios
("Paciente Demo"/"Otro Paciente Demo", P1/P2, prestación "Conducto Demo" con
`precio_base=150000` centavos) y reloj inyectado (`d3`, `-03:00`). La unidad de
trabajo cubre hallazgos, presupuestos, líneas y auditoría: si el caso de uso
falla, no queda ni hallazgo, ni línea, ni rastro de auditoría.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from conftest import P1, T1

from app.odontograma.puertos import (
    AuditoriaMemoria,
    ConsentimientoMemoria,
    HallazgoMemoria,
    PacienteMemoria,
    PrestacionMemoria,
    ProfesionalMemoria,
    TurnoMemoria,
    UnidadDeTrabajoMemoria,
)
from app.odontograma.servicio import ServicioOdontograma
from app.presupuesto.puertos import LineaMemoria, PresupuestoMemoria
from app.turnos.servicio import Actor

TZ = timezone(timedelta(hours=-3))

PAC1 = "paciente-1"
PAC9 = "paciente-9"
PREST1 = "prestacion-1"
PREST9 = "prestacion-9"
KEY = "550e8400-e29b-41d4-a716-446655440000"
PRECIO_CONDUCTO = 150000


def d3(dia: str = "2026-11-10", hora: int = 10, minuto: int = 0) -> datetime:
    y, m, d = (int(x) for x in dia.split("-"))
    return datetime(y, m, d, hora, minuto, tzinfo=TZ)


def actor(
    rol: str,
    tenant: str = T1,
    user_id: str = "usuario-1",
    profesional_id: str | None = None,
) -> Actor:
    return Actor(tenant_id=tenant, rol=rol, user_id=user_id, profesional_id=profesional_id)


class HarnessOdontograma:
    """Dominio C-09 cableado en memoria, con semillas ficticias de T1."""

    def __init__(self) -> None:
        self.hallazgos = HallazgoMemoria()
        self.presupuestos = PresupuestoMemoria()
        self.lineas = LineaMemoria()
        self.prestaciones = PrestacionMemoria()
        self.pacientes = PacienteMemoria()
        self.profesionales = ProfesionalMemoria()
        self.turnos = TurnoMemoria()
        self.consentimientos = ConsentimientoMemoria()
        self.auditoria = AuditoriaMemoria()
        self.uow = UnidadDeTrabajoMemoria(
            [self.hallazgos, self.presupuestos, self.lineas, self.auditoria]
        )
        self.svc = ServicioOdontograma(
            self.hallazgos,
            self.presupuestos,
            self.lineas,
            self.prestaciones,
            self.pacientes,
            self.profesionales,
            self.turnos,
            self.consentimientos,
            self.auditoria,
            uow_factory=lambda: UnidadDeTrabajoMemoria(
                [self.hallazgos, self.presupuestos, self.lineas, self.auditoria]
            ),
        )
        self.seed_paciente(PAC1)
        self.seed_profesional(P1)
        self.seed_atiende(P1, PAC1)
        self.seed_prestacion(PREST1, PRECIO_CONDUCTO)

    # -- semillas -------------------------------------------------------

    def seed_paciente(self, paciente_id: str, tenant: str = T1) -> None:
        self.pacientes.agregar(tenant, paciente_id)

    def seed_profesional(self, profesional_id: str, tenant: str = T1) -> None:
        self.profesionales.agregar(tenant, profesional_id)

    def seed_atiende(
        self, profesional_id: str, paciente_id: str, tenant: str = T1
    ) -> None:
        self.turnos.agregar(tenant, profesional_id, paciente_id)

    def seed_prestacion(
        self, prestacion_id: str, precio_base: int, tenant: str = T1
    ) -> None:
        self.prestaciones.agregar(tenant, prestacion_id, precio_base)

    def dar_consentimiento(self, paciente_id: str, tenant: str = T1) -> None:
        self.consentimientos.registrar(
            tenant_id=tenant,
            paciente_id=paciente_id,
            timestamp=d3("2026-11-09", hora=9),
            canal="móvil",
            ahora=d3("2026-11-09", hora=9),
        )
