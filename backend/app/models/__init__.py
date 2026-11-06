"""SQLAlchemy models for the project."""
from app.models.auditoria import Auditoria
from app.models.base import Base
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
from app.models.refresh_token import RefreshToken
from app.models.tenant import ParametroTenant, Tenant
from app.models.turno import Turno
from app.models.usuario import Usuario

__all__ = [
    "Adjunto",
    "Auditoria",
    "Base",
    "Bloqueo",
    "Consentimiento",
    "Evolucion",
    "Ficha",
    "HorarioSemanal",
    "ListaEspera",
    "Oferta",
    "Paciente",
    "ParametroTenant",
    "Prestacion",
    "Profesional",
    "ProfesionalPrestacion",
    "RefreshToken",
    "Sillon",
    "Tenant",
    "Turno",
    "Usuario",
]
