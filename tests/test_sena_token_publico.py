"""Tasks 5.1–5.6 — token público y superficie de pago (D6, F-16, F-30).

El token es opaco (32 bytes urlsafe), se persiste sólo su SHA-256 y hay uno solo
vigente por seña: el anterior responde `404` después de reemitir. Un token de
otro tenant produce el **mismo** `404` que uno inexistente, y la respuesta no
lleva PHI ni el token en los logs. Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import re
from datetime import timedelta

from _reserva_helpers import reservar
from _senas_helpers import (
    AHORA,
    HarnessReservaConSena,
    HarnessSenas,
    d3,
)
from conftest import T1

from app.senas.token import hash_token

CLAVES_SENA_PUBLICA = {
    "sena_id",
    "estado",
    "monto_centavos",
    "expira_at",
    "preferencia_estado",
    "init_point",
    "turno",
    "politica",
}


def test_lectura_allow_list() -> None:
    h = HarnessSenas()
    h.configurar()
    creada = h.crear()

    respuesta = h.client.get(f"/api/publico/t1/senas/{creada.token_sena}")

    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert set(body.keys()) == CLAVES_SENA_PUBLICA
    assert body["sena_id"] == creada.sena.id
    assert body["estado"] == "PENDIENTE"
    assert body["monto_centavos"] == 3000
    assert body["preferencia_estado"] == "CREADA"
    assert body["init_point"] == creada.sena.mp_init_point
    assert set(body["turno"].keys()) == {"inicio", "fin", "prestacion"}
    assert body["turno"]["prestacion"] == "PREST-1"
    assert set(body["politica"].keys()) == {
        "anticipacion_cancelacion_h",
        "reembolsable",
        "hay_pago_acreditado",
    }
    assert body["politica"] == {
        "anticipacion_cancelacion_h": 24,
        "reembolsable": True,
        "hay_pago_acreditado": False,
    }


def test_token_de_otro_tenant_404_uniforme() -> None:
    h = HarnessSenas()
    h.configurar()
    creada = h.crear()

    ajeno = h.client.get(f"/api/publico/t2/senas/{creada.token_sena}")
    inexistente = h.client.get("/api/publico/t2/senas/NO-EXISTE")

    assert ajeno.status_code == 404
    assert inexistente.status_code == 404
    assert ajeno.json() == inexistente.json()
    texto = json.dumps(ajeno.json())
    assert creada.sena.id not in texto
    assert "tenant_id" not in texto


def test_token_rotado_404() -> None:
    h = HarnessSenas()
    h.configurar()
    creada = h.crear()
    nuevo_token = "tok-nuevo-de-prueba-0123456789abcdefghij"
    rotada = h.senas.reemitir_token(
        tenant_id=T1,
        sena_id=creada.sena.id,
        token_hash=hash_token(nuevo_token),
        ahora=AHORA + timedelta(hours=1),
    )
    assert rotada.token_rotado_en is not None

    anterior = h.client.get(f"/api/publico/t1/senas/{creada.token_sena}")
    vigente = h.client.get(f"/api/publico/t1/senas/{nuevo_token}")

    assert anterior.status_code == 404
    assert vigente.status_code == 200
    assert vigente.json()["sena_id"] == creada.sena.id


def test_sena_no_pagable_sin_init_point() -> None:
    # (a) Seña LIBERADA: se muestra el resultado, sin link de pago.
    h = HarnessSenas()
    h.configurar()
    liberada = h.crear()
    h.senas.transicionar(
        tenant_id=T1,
        sena_id=liberada.sena.id,
        desde="PENDIENTE",
        hacia="LIBERADA",
        campos={"liberada_en": AHORA + timedelta(hours=1), "motivo_liberacion": "EXPIRACION"},
    )
    r_liberada = h.client.get(f"/api/publico/t1/senas/{liberada.token_sena}")
    assert r_liberada.status_code == 200
    assert r_liberada.json()["estado"] == "LIBERADA"
    assert r_liberada.json()["init_point"] is None

    # (b) Seña PENDIENTE con `expira_at` en el pasado: tampoco hay link.
    vencida = h.crear(turno_id="turno-2", inicio=d3("2026-11-25", 10))
    h.senas.actualizar(
        tenant_id=T1,
        sena_id=vencida.sena.id,
        campos={"expira_at": AHORA - timedelta(hours=1)},
    )
    r_vencida = h.client.get(f"/api/publico/t1/senas/{vencida.token_sena}")
    assert r_vencida.status_code == 200
    assert r_vencida.json()["estado"] == "PENDIENTE"
    assert r_vencida.json()["init_point"] is None


def test_no_expone_datos_del_paciente(caplog) -> None:
    caplog.set_level(logging.INFO)
    h = HarnessReservaConSena()

    reserva = reservar(h.base, nombre="Paciente Demo", telefono="+5491100000000")
    assert reserva.status_code == 201, reserva.text
    token = reserva.json()["sena"]["token_sena"]

    respuesta = h.client_senas.get(f"/api/publico/t1/senas/{token}")

    assert respuesta.status_code == 200, respuesta.text
    body = respuesta.json()
    assert set(body.keys()) == CLAVES_SENA_PUBLICA
    texto = json.dumps(body)
    assert "Paciente Demo" not in texto
    assert "+5491100000000" not in texto
    for prohibida in ("nombre", "telefono", "dni", "paciente_id", "tenant_id"):
        assert prohibida not in body
        assert prohibida not in texto
    # El token tampoco se escribe en el log estructurado de la aplicación
    # (el access-log del transporte HTTP repite la URL; el log de `app.*` no).
    logs_app = "\n".join(
        registro.getMessage()
        for registro in caplog.records
        if registro.name.startswith("app.")
    )
    assert body["sena_id"] in logs_app
    assert token not in logs_app
    assert "Paciente Demo" not in logs_app
    assert "+5491100000000" not in logs_app


def test_solo_se_guarda_el_hash() -> None:
    h = HarnessSenas()
    h.configurar()
    primera = h.crear()
    segunda = h.crear(turno_id="turno-2", inicio=d3("2026-11-21", 10))

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", primera.token_sena)
    assert primera.sena.token_hash == hash_token(primera.token_sena)
    assert len(primera.sena.token_hash) == 64
    assert primera.sena.token_hash != primera.token_sena
    # Ninguna columna de la fila guarda el token en claro.
    para_el_token = {
        str(getattr(primera.sena, campo.name)) for campo in dataclasses.fields(primera.sena)
    }
    assert primera.token_sena not in para_el_token
    # El hash no permite reconstruir el link y nunca se repite entre señas.
    assert hash_token("otro-token") != primera.sena.token_hash
    assert primera.sena.token_hash != segunda.sena.token_hash
    assert primera.token_sena != segunda.token_sena
    assert h.senas.por_token(tenant_id=T1, token_hash=hash_token(primera.token_sena)) is not None
    assert h.senas.por_token(tenant_id=T1, token_hash=primera.token_sena) is None
