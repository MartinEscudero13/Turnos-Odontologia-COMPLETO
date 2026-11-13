"""Tasks 10.8–10.11 — reprogramación con seña (§10, D12 / C11-OQ-04 / F-16).

La seña **acompaña a la reserva**: con anticipación suficiente se transfiere al
turno nuevo, `expira_at = min(ahora + SENA_TTL_H, nuevo.inicio)` si estaba
`PENDIENTE`, y el token se conserva si no venció o se reemite si venció (el
anterior deja de resolver: `404`). Una seña `APLICADA` no se transfiere y el
turno nuevo no exige una segunda seña.

Datos ficticios (RN-GL-03). El calendario del harness usa horas UTC en la
grilla de 09–12 del profesional (los turnos de los tests son `Z`).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from _reserva_helpers import emitir, reservar
from _senas_helpers import T1, HarnessReservaConSena

TZ = timezone(timedelta(hours=-3))

AHORA_REPROGRAMACION = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
INICIO_ORIGINAL = "2026-11-22T11:00:00+00:00"
INICIO_DENTRO_DE_24H = "2026-11-20T11:00:00+00:00"
INICIO_LEJOS = "2026-11-25T10:00:00+00:00"


def _harness(**kwargs: object) -> HarnessReservaConSena:
    h = HarnessReservaConSena(**kwargs)  # type: ignore[arg-type]
    h.fijar_ahora("2026-11-20", 9)
    return h


def _reservar(h: HarnessReservaConSena, inicio: str = INICIO_ORIGINAL) -> dict:
    respuesta = reservar(h, inicio=inicio)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _reprogramar(h: HarnessReservaConSena, token: str, nuevo_inicio: str):
    verificacion = emitir(h, accion="reprogramar")
    return h.client.post(
        f"/api/publico/t1/reservas/{token}/reprogramacion",
        json={"nuevo_inicio": nuevo_inicio, "verificacion_id": verificacion},
    )


def _forzar(h: HarnessReservaConSena, sena_id: str, estado: str, campos: dict) -> None:
    actual = h.senas.transicionar(
        tenant_id=T1,
        sena_id=sena_id,
        desde="PENDIENTE",
        hacia=estado,  # type: ignore[arg-type]
        campos=campos,
    )
    assert actual is not None


# ---------------------------------------------------------------------------
# 10.8 — la seña pendiente acompaña al turno nuevo
# ---------------------------------------------------------------------------


def test_pendiente_acompana_al_turno_nuevo() -> None:
    h = _harness(anticipacion_min_horas=1, anticipacion_cancelacion_h=1)
    cuerpo = _reservar(h)
    sena_id = cuerpo["sena"]["sena_id"]
    token_sena = cuerpo["sena"]["token_sena"]
    expira_original = datetime.fromisoformat(
        cuerpo["sena"]["expira_at"].replace("Z", "+00:00")
    )
    assert expira_original == AHORA_REPROGRAMACION + timedelta(hours=24)

    respuesta = _reprogramar(h, cuerpo["token_publico"], INICIO_DENTRO_DE_24H)

    assert respuesta.status_code == 200, respuesta.text
    nuevo_turno = respuesta.json()["nuevo"]["turno_id"]
    sena = h.senas.obtener(tenant_id=T1, sena_id=sena_id)
    assert sena is not None
    assert sena.estado == "PENDIENTE"
    assert sena.turno_id == nuevo_turno
    # `expira_at` se acota al inicio del turno nuevo (C11-OQ-08).
    assert sena.expira_at == datetime.fromisoformat(
        INICIO_DENTRO_DE_24H.replace("+00:00", "+00:00")
    )
    # El mismo token sigue sirviendo y apunta al turno nuevo.
    vista = h.client_senas.get(f"/api/publico/t1/senas/{token_sena}")
    assert vista.status_code == 200, vista.text
    assert vista.json()["turno"]["inicio"].startswith("2026-11-20T11:00:00")
    # No se crea una segunda seña.
    assert h.senas.total(T1) == 1
    transferida = [
        entrada
        for entrada in h.auditoria_senas.de_accion("SENA_TRANSFERIDA")
    ]
    assert len(transferida) == 1
    assert transferida[0].despues["token_reemitido"] is False


# ---------------------------------------------------------------------------
# 10.9 — la seña acreditada se transfiere sin cambiar de estado
# ---------------------------------------------------------------------------


def test_acreditada_se_transfiere() -> None:
    h = _harness(anticipacion_min_horas=24, anticipacion_cancelacion_h=24)
    cuerpo = _reservar(h)
    sena_id = cuerpo["sena"]["sena_id"]
    _forzar(h, sena_id, "ACREDITADA", {"acreditada_en": h.ahora_actual})

    respuesta = _reprogramar(h, cuerpo["token_publico"], INICIO_LEJOS)

    assert respuesta.status_code == 200, respuesta.text
    nuevo_turno = respuesta.json()["nuevo"]["turno_id"]
    sena = h.senas.obtener(tenant_id=T1, sena_id=sena_id)
    assert sena is not None
    assert sena.estado == "ACREDITADA"
    assert sena.turno_id == nuevo_turno
    assert sena.acreditada_en is not None
    assert h.senas.total(T1) == 1
    transferida = h.auditoria_senas.de_accion("SENA_TRANSFERIDA")
    assert len(transferida) == 1
    assert transferida[0].despues["estado"] == "ACREDITADA"


# ---------------------------------------------------------------------------
# 10.10 — una seña aplicada no se transfiere
# ---------------------------------------------------------------------------


def test_aplicada_no_se_transfiere() -> None:
    h = _harness(anticipacion_min_horas=24, anticipacion_cancelacion_h=24)
    cuerpo = _reservar(h)
    sena_id = cuerpo["sena"]["sena_id"]
    turno_original = cuerpo["turno_id"]
    _forzar(
        h,
        sena_id,
        "APLICADA",
        {
            "acreditada_en": h.ahora_actual,
            "aplicada_en": h.ahora_actual,
            "movimiento_caja_id": "movimiento-mp-1",
            "concepto_aplicacion": "TRATAMIENTO",
        },
    )

    respuesta = _reprogramar(h, cuerpo["token_publico"], INICIO_LEJOS)

    assert respuesta.status_code == 200, respuesta.text
    sena = h.senas.obtener(tenant_id=T1, sena_id=sena_id)
    assert sena is not None
    assert sena.estado == "APLICADA"
    assert sena.turno_id == turno_original
    assert h.senas.total(T1) == 1
    no_transferida = h.auditoria_senas.de_accion("SENA_NO_TRANSFERIDA")
    assert len(no_transferida) == 1
    assert no_transferida[0].despues["motivo"] == "ESTADO_APLICADA"


# ---------------------------------------------------------------------------
# 10.11 — un token vencido se reemite al reprogramar
# ---------------------------------------------------------------------------


def test_token_vencido_se_reemite() -> None:
    h = _harness(
        anticipacion_min_horas=1,
        anticipacion_cancelacion_h=1,
        sena_ttl_h=1,
    )
    cuerpo = _reservar(h)
    token_viejo = cuerpo["sena"]["token_sena"]

    # El token venció (expira_at = 10:00Z) pero la seña sigue PENDIENTE.
    h.fijar_ahora("2026-11-20", 11)
    respuesta = _reprogramar(h, cuerpo["token_publico"], "2026-11-21T10:00:00+00:00")

    assert respuesta.status_code == 200, respuesta.text
    nuevo = respuesta.json()["sena"]
    assert nuevo is not None
    assert nuevo["token_sena"] != token_viejo
    assert nuevo["estado"] == "PENDIENTE"

    # El token anterior dejó de existir; el nuevo funciona.
    assert h.client_senas.get(f"/api/publico/t1/senas/{token_viejo}").status_code == 404
    vista = h.client_senas.get(f"/api/publico/t1/senas/{nuevo['token_sena']}")
    assert vista.status_code == 200, vista.text

    transferida = h.auditoria_senas.de_accion("SENA_TRANSFERIDA")
    assert len(transferida) == 1
    assert transferida[0].despues["token_reemitido"] is True

    sena = h.senas.obtener(tenant_id=T1, sena_id=cuerpo["sena"]["sena_id"])
    assert sena is not None
    # `expira_at` se recalculó con el TTL (el turno nuevo está más lejos que
    # `ahora + SENA_TTL_H`, así que el tope por inicio no aplica).
    assert sena.expira_at == datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
