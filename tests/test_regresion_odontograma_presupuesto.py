"""Task 10.1 — regresión: C-04…C-08 siguen en verde con la 007 aplicada.

La migración 007 sólo crea tablas nuevas: no toca turnos, catálogos, lista de
espera ni ficha clínica, no agrega env vars/secretos y no crea tablas de C-10
(caja) ni de C-12 (coberturas).
"""
from __future__ import annotations

from pathlib import Path

from _ficha_clinica_helpers import HarnessClinica
from _ficha_clinica_helpers import actor as actor_ficha
from _odontograma_helpers import d3
from conftest import T1

RAIZ = Path(__file__).resolve().parent.parent
MIGRACION = RAIZ / "backend/alembic/versions/007_odontograma_presupuesto.py"


def test_c04_c05_c06_c07_c08_siguen_en_verde():
    # C-04: catálogos/pacientes siguen cargando.
    from app.models.catalogos import Paciente, Prestacion, Profesional, Sillon

    assert Paciente.__tablename__ == "pacientes"
    assert Profesional.__tablename__ == "profesionales"
    assert Prestacion.__tablename__ == "prestaciones"
    assert Sillon.__tablename__ == "sillones"

    # C-05: la agenda crea turnos sin gate de consentimiento (RN-AU-03).
    from app.turnos.servicio import ServicioTurnos

    turnos = ServicioTurnos(anticipacion_min_horas=0.0)
    turno = turnos.crear(
        actor_ficha("RECEPCION"),
        profesional_id="profesional-1",
        sillon_id="sillon-1",
        paciente_id="paciente-1",
        prestacion_id="prestacion-1",
        inicio=d3(),
        duracion_min=30,
    )
    assert turno.estado == "PENDIENTE"
    assert turno.tenant_id == T1

    # C-06: reserva pública sigue importando y cableable.
    from app.reservas.servicio import ServicioReservasPublicas
    from app.reservas.tokens import TokenRepositorioEnMemoria

    assert ServicioReservasPublicas is not None
    assert TokenRepositorioEnMemoria is not None

    # C-07: lista de espera sigue importando.
    from app.lista_espera.puertos import ListaEsperaMemoria, OfertaMemoria
    from app.lista_espera.servicio import ServicioListaEspera

    assert ListaEsperaMemoria is not None
    assert OfertaMemoria is not None
    assert ServicioListaEspera is not None

    # C-08: ficha clínica y su gate de consentimiento siguen intactos.
    from app.ficha_clinica.servicio import ConsentimientoRequerido, ServicioFichaClinica

    assert ServicioFichaClinica is not None
    assert ConsentimientoRequerido.codigo == 409
    clinica = HarnessClinica()
    clinica.seed_paciente("paciente-1")
    clinica.dar_consentimiento("paciente-1")
    ficha = clinica.svc.crear_ficha(
        actor_ficha("RECEPCION"), paciente_id="paciente-1"
    )
    assert ficha.paciente_id == "paciente-1"


def test_migracion_007_no_toca_otras_tablas_ni_agrega_env():
    sql = MIGRACION.read_text(encoding="utf-8")
    assert 'down_revision = "006_ficha_clinica"' in sql
    assert "CREATE TABLE odontograma_hallazgos" in sql
    assert "CREATE TABLE presupuestos" in sql
    assert "CREATE TABLE presupuesto_lineas" in sql
    assert "CREATE TABLE aceptaciones" in sql
    # Fuera de alcance C-10/C-12: ni caja ni coberturas.
    assert "CREATE TABLE movimientos_caja" not in sql
    assert "CREATE TABLE coberturas" not in sql
    assert "CREATE TABLE obras_sociales" not in sql
    # Sin env vars nuevas ni secretos.
    assert "getenv" not in sql
    assert "os.environ" not in sql
