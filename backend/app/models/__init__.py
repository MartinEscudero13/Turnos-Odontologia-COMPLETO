"""SQLAlchemy models for the project."""
from app.models.auditoria import Auditoria
from app.models.base import Base
from app.models.caja import (
    AjustePostCierre,
    CierreDiario,
    CobroPendiente,
    CuentaPorCobrarOS,
    MovimientoCaja,
)
from app.models.calendario import CalendarEnvio, CalendarEvento, CalendarLink
from app.models.catalogos import (
    Bloqueo,
    HorarioSemanal,
    Paciente,
    Prestacion,
    Profesional,
    ProfesionalPrestacion,
    Sillon,
)
from app.models.ficha_clinica import Adjunto, Consentimiento, Evolucion, Ficha
from app.models.lista_espera import ListaEspera, Oferta
from app.models.obras_sociales import Cobertura, Liquidacion, LiquidacionLinea, ObraSocial
from app.models.odontograma import OdontogramaHallazgo
from app.models.presupuesto import Aceptacion, Presupuesto, PresupuestoLinea
from app.models.refresh_token import RefreshToken
from app.models.sena import PagoMP, Sena
from app.models.tenant import ParametroTenant, Tenant
from app.models.turno import Turno
from app.models.usuario import Usuario
from app.models.whatsapp import MensajeWA

__all__ = [
    "Aceptacion",
    "Adjunto",
    "AjustePostCierre",
    "Auditoria",
    "Base",
    "Bloqueo",
    "CierreDiario",
    "CobroPendiente",
    "Cobertura",
    "Consentimiento",
    "CuentaPorCobrarOS",
    "Evolucion",
    "Ficha",
    "CalendarEnvio",
    "CalendarEvento",
    "CalendarLink",
    "HorarioSemanal",
    "ListaEspera",
    "Liquidacion",
    "LiquidacionLinea",
    "MensajeWA",
    "MovimientoCaja",
    "ObraSocial",
    "OdontogramaHallazgo",
    "Oferta",
    "Paciente",
    "PagoMP",
    "ParametroTenant",
    "Prestacion",
    "Presupuesto",
    "PresupuestoLinea",
    "Profesional",
    "ProfesionalPrestacion",
    "RefreshToken",
    "Sena",
    "Sillon",
    "Tenant",
    "Turno",
    "Usuario",
]
