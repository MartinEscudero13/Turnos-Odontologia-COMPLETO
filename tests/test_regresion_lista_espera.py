"""Tasks 10.1–10.2 — regresión C-05/C-06 y validez de `origen=LISTA_ESPERA`."""
from __future__ import annotations

from pathlib import Path

import pytest
from _lista_espera_helpers import PREST30, HarnessLista
from conftest import P1, T1, dt
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.lista_espera.puertos import HuecoLiberadoMemoria
from app.routers.turnos import crear_app
from app.schemas.turno import CrearTurnoIn
from app.turnos.servicio import ServicioTurnos

BASE = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
PAYLOAD = {
    "profesional_id": P1,
    "sillon_id": "sillon-1",
    "paciente_id": "paciente-otro",
    "prestacion_id": PREST30,
    "inicio": "2026-10-14T10:00:00+00:00",
    "duracion_min": 30,
}


def test_cancelacion_c05_y_c06_siguen_en_verde_y_emiten_evento():
    # C-05: cancelación por recepción vía router sigue 200 y emite el evento.
    svc_c05 = ServicioTurnos(anticipacion_min_horas=0.0)
    hueco_c05 = HuecoLiberadoMemoria()
    client = TestClient(crear_app(svc_c05, hueco_c05))
    turno_id = client.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    assert client.post(f"/api/turnos/{turno_id}/cancelar", headers=BASE).status_code == 200
    assert hueco_c05.eventos == [(T1, turno_id)]

    # C-06: cancelación pública sigue 200 y emite el evento.
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    svc, client_publico = h.build_publico()
    vid = client_publico.post("/api/publico/t1/verificacion", json={"accion": "reservar"}).json()["verificacion_id"]
    r = client_publico.post(
        "/api/publico/t1/reservas",
        json={
            "prestacion": PREST30,
            "profesional": P1,
            "inicio": "2026-10-14T10:00:00+00:00",
            "nombre": "Paciente Demo",
            "telefono": "+5491130551234",
            "verificacion_id": vid,
        },
    )
    assert r.status_code == 201, r.text
    turno_publico_id = r.json()["turno_id"]
    token_publico = r.json()["token_publico"]
    vid_c = client_publico.post("/api/publico/t1/verificacion", json={"accion": "cancelar"}).json()["verificacion_id"]
    r2 = client_publico.post(
        f"/api/publico/t1/reservas/{token_publico}/cancelacion", json={"verificacion_id": vid_c}
    )
    assert r2.status_code == 200, r2.text
    assert (T1, turno_publico_id) in h.hueco_port.eventos


def test_origen_lista_espera_valido_en_schema_y_check():
    # El schema del borde acepta origen=LISTA_ESPERA.
    body = CrearTurnoIn(
        profesional_id=P1,
        sillon_id="sillon-1",
        paciente_id="paciente-otro",
        prestacion_id=PREST30,
        inicio=dt("2026-10-14", 10),
        duracion_min=30,
        origen="LISTA_ESPERA",
    )
    assert body.origen == "LISTA_ESPERA"
    with pytest.raises(ValidationError):
        CrearTurnoIn(
            profesional_id=P1,
            sillon_id="sillon-1",
            paciente_id="paciente-otro",
            prestacion_id=PREST30,
            inicio=dt("2026-10-14", 10),
            duracion_min=30,
            origen="INVENTADO",
        )
    # El CHECK de la 003 ya lo declara válido.
    mig = (
        Path(__file__).resolve().parent.parent
        / "backend"
        / "alembic"
        / "versions"
        / "003_turnos_anti_solape.py"
    )
    sql = mig.read_text(encoding="utf-8")
    assert "origen IN ('RECEPCION','RESERVA_ONLINE','LISTA_ESPERA')" in sql
