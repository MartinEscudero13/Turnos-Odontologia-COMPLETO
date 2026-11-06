"""Task 10.1 — regresión: C-04/C-05/C-07 siguen en verde (la 006 no toca sus tablas)."""
from __future__ import annotations

from _ficha_clinica_helpers import actor, d3
from conftest import T1


def test_c04_c05_c07_siguen_en_verde():
    # C-04 catálogos/pacientes siguen cargando.
    from app.models.catalogos import Paciente, Prestacion, Profesional, Sillon

    assert Paciente.__tablename__ == "pacientes"
    assert Profesional.__tablename__ == "profesionales"
    assert Prestacion.__tablename__ == "prestaciones"
    assert Sillon.__tablename__ == "sillones"

    # C-05 turnos: crear un turno sigue funcionando (sin gate de consentimiento).
    from app.turnos.servicio import ServicioTurnos

    turnos = ServicioTurnos(anticipacion_min_horas=0.0)
    turno = turnos.crear(
        actor("RECEPCION"),
        profesional_id="profesional-1",
        sillon_id="sillon-1",
        paciente_id="paciente-1",
        prestacion_id="prestacion-1",
        inicio=d3(),
        duracion_min=30,
    )
    assert turno.id
    assert turno.estado == "PENDIENTE"
    assert turno.tenant_id == T1

    # C-07 lista de espera sigue importando y cableable.
    from app.lista_espera.puertos import ListaEsperaMemoria, OfertaMemoria
    from app.lista_espera.servicio import ServicioListaEspera

    assert ListaEsperaMemoria is not None
    assert OfertaMemoria is not None
    assert ServicioListaEspera is not None
