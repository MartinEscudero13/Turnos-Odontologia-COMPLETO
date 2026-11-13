"""Tasks 10.1–10.7 — devolución, política visible y su elegibilidad (§10, D12).

Reglas fijadas:

- La cancelación con anticipación **>= snapshot** de la seña la deja `DEVUELTA`
  (si estaba `ACREDITADA`) con `motivo_devolucion='POLITICA_CANCELACION'` y sin
  actor, o `LIBERADA` si nunca se cobró. Bajo el umbral el paciente recibe `403`
  y decide un humano `ADMIN` (`C11-OQ-03`).
- La elegibilidad se decide con el **snapshot** guardado en la seña, no con la
  configuración viva (`F-19`).
- `DEVUELTA` es una obligación **manual**: no se llama a la API de reembolsos de
  Mercado Pago (`C11-OQ-09`); sólo `ADMIN` devuelve y con motivo no vacío.

Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

import pytest
from _reserva_helpers import emitir, reservar
from _senas_helpers import (
    AHORA,
    T1,
    U1,
    U2,
    HarnessReservaConSena,
    HarnessSenaAplicacion,
    HarnessSenas,
)

from app.senas.aplicacion import CODIGO_SENA_NO_DEVOLUBLE
from app.senas.servicio import ConflictoSena
from app.turnos.servicio import Actor, Invalido, Prohibido

RECEPCION = Actor(tenant_id=T1, rol="RECEPCION", user_id=U1)
ADMIN = Actor(tenant_id=T1, rol="ADMIN", user_id=U2)


def _acreditar(h: HarnessReservaConSena, sena_id: str) -> None:
    actual = h.senas.transicionar(
        tenant_id=T1,
        sena_id=sena_id,
        desde="PENDIENTE",
        hacia="ACREDITADA",
        campos={"acreditada_en": h.ahora_actual},
    )
    assert actual is not None


def _reservar_para(h: HarnessReservaConSena, inicio: str):
    respuesta = reservar(h, inicio=inicio)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()


def _cancelar(h: HarnessReservaConSena, token: str):
    verificacion = emitir(h, accion="cancelar")
    return h.client.post(
        f"/api/publico/t1/reservas/{token}/cancelacion",
        json={"verificacion_id": verificacion},
    )


# ---------------------------------------------------------------------------
# 10.1 — cancelar con anticipación deja la seña a devolver
# ---------------------------------------------------------------------------


def test_cancelar_con_anticipacion_deja_devuelta() -> None:
    h = HarnessReservaConSena(
        anticipacion_min_horas=24, anticipacion_cancelacion_h=24
    )
    h.fijar_ahora("2026-11-20", 9)
    cuerpo = _reservar_para(h, "2026-11-22T11:00:00+00:00")
    sena_id = cuerpo["sena"]["sena_id"]
    _acreditar(h, sena_id)

    respuesta = _cancelar(h, cuerpo["token_publico"])

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["estado"] == "CANCELADO"
    sena = h.senas.obtener(tenant_id=T1, sena_id=sena_id)
    assert sena is not None
    assert sena.estado == "DEVUELTA"
    assert sena.motivo_devolucion == "POLITICA_CANCELACION"
    assert sena.devuelta_por is None
    assert sena.devuelta_en is not None
    accion = [
        entrada
        for entrada in h.auditoria_senas.entradas
        if entrada.accion == "SENA_DEVUELTA"
    ]
    assert len(accion) == 1


# ---------------------------------------------------------------------------
# 10.2 — cancelar bajo el umbral no devuelve sola
# ---------------------------------------------------------------------------


def test_cancelar_bajo_umbral_no_devuelve_sola() -> None:
    h = HarnessReservaConSena(
        anticipacion_min_horas=24, anticipacion_cancelacion_h=24
    )
    h.fijar_ahora("2026-11-20", 9)
    cuerpo = _reservar_para(h, "2026-11-22T11:00:00+00:00")
    sena_id = cuerpo["sena"]["sena_id"]
    _acreditar(h, sena_id)

    h.fijar_ahora("2026-11-21", 20)
    respuesta = _cancelar(h, cuerpo["token_publico"])

    assert respuesta.status_code == 403, respuesta.text
    sena = h.senas.obtener(tenant_id=T1, sena_id=sena_id)
    assert sena is not None
    assert sena.estado == "ACREDITADA"
    assert sena.devuelta_en is None
    turno = h.turnos.obtener(
        Actor(tenant_id=T1, rol="RECEPCION", user_id="publico"),
        cuerpo["turno_id"],
    )
    assert turno.estado in ("PENDIENTE", "CONFIRMADO")


# ---------------------------------------------------------------------------
# La elegibilidad usa el snapshot y no la configuración viva (F-19)
# ---------------------------------------------------------------------------


def test_elegibilidad_usa_el_snapshot_de_la_sena() -> None:
    # Configuración viva 48 h, snapshot 12 h: el snapshot autoriza con 24 h.
    permiso = HarnessReservaConSena(
        anticipacion_min_horas=48, anticipacion_cancelacion_h=12
    )
    permiso.fijar_ahora("2026-11-20", 9)
    cuerpo = _reservar_para(permiso, "2026-11-22T11:00:00+00:00")
    _acreditar(permiso, cuerpo["sena"]["sena_id"])
    permiso.fijar_ahora("2026-11-21", 9)  # 24 h antes del turno
    assert _cancelar(permiso, cuerpo["token_publico"]).status_code == 200

    # Configuración viva 12 h, snapshot 48 h: el snapshot rechaza con 24 h.
    rechazo = HarnessReservaConSena(
        anticipacion_min_horas=12, anticipacion_cancelacion_h=48
    )
    rechazo.fijar_ahora("2026-11-20", 9)
    cuerpo = _reservar_para(rechazo, "2026-11-22T11:00:00+00:00")
    _acreditar(rechazo, cuerpo["sena"]["sena_id"])
    rechazo.fijar_ahora("2026-11-21", 9)
    assert _cancelar(rechazo, cuerpo["token_publico"]).status_code == 403


# ---------------------------------------------------------------------------
# 10.3 — ADMIN devuelve con motivo
# ---------------------------------------------------------------------------


def test_admin_devuelve_con_motivo() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")

    devuelta = h.svc.devolver(
        tenant_id=T1,
        sena_id=sena.id,
        actor=ADMIN,
        motivo="cancelación con aviso",
        ahora=AHORA,
    )

    assert devuelta.estado == "DEVUELTA"
    assert devuelta.devuelta_por == U2
    assert devuelta.devuelta_en == AHORA
    assert devuelta.motivo_devolucion == "cancelación con aviso"
    auditoria = h.auditoria.de_accion("SENA_DEVUELTA")
    assert len(auditoria) == 1
    assert auditoria[0].actor == U2
    assert auditoria[0].entidad_id == sena.id


# ---------------------------------------------------------------------------
# 10.4 — recepción no puede devolver
# ---------------------------------------------------------------------------


def test_recepcion_no_devuelve() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")

    with pytest.raises(Prohibido) as excinfo:
        h.svc.devolver(
            tenant_id=T1,
            sena_id=sena.id,
            actor=RECEPCION,
            motivo="lo intento igual",
            ahora=AHORA,
        )

    assert excinfo.value.codigo == 403
    assert h.sena(sena).estado == "ACREDITADA"


# ---------------------------------------------------------------------------
# 10.5 — devolver sin motivo se rechaza
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("motivo", ["", "   "])
def test_sin_motivo_422(motivo: str) -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")

    with pytest.raises(Invalido) as excinfo:
        h.svc.devolver(
            tenant_id=T1,
            sena_id=sena.id,
            actor=ADMIN,
            motivo=motivo,
            ahora=AHORA,
        )

    assert excinfo.value.codigo == 422
    assert h.sena(sena).estado == "ACREDITADA"


# ---------------------------------------------------------------------------
# 10.6 — una seña aplicada no se devuelve
# ---------------------------------------------------------------------------


def test_aplicada_no_se_devuelve() -> None:
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="APLICADA")

    with pytest.raises(ConflictoSena) as excinfo:
        h.svc.devolver(
            tenant_id=T1,
            sena_id=sena.id,
            actor=ADMIN,
            motivo="después del cobro",
            ahora=AHORA,
        )

    assert excinfo.value.codigo == 409
    assert excinfo.value.codigo_dominio == CODIGO_SENA_NO_DEVOLUBLE
    assert h.sena(sena).estado == "APLICADA"
    # Corregir después del cobro es una anulación de C-10, no otra devolución.
    assert h.movimientos_del_dia(AHORA.date()) == []


# ---------------------------------------------------------------------------
# 10.7 — la política es visible al reservar y en el token, sin PHI
# ---------------------------------------------------------------------------


def test_politica_visible_en_reserva_y_token() -> None:
    reserva = HarnessReservaConSena(
        anticipacion_min_horas=24, anticipacion_cancelacion_h=24
    )
    reserva.fijar_ahora("2026-11-20", 9)
    cuerpo = _reservar_para(reserva, "2026-11-22T11:00:00+00:00")

    politica = cuerpo["sena"]["politica"]
    assert politica == {
        "anticipacion_cancelacion_h": 24,
        "reembolsable": True,
        "hay_pago_acreditado": False,
    }

    h = HarnessSenas()
    h.configurar()
    creada = h.crear()
    token = creada.token_sena

    # PENDIENTE: la promesa ya está visible, la plata todavía no.
    vista = h.client.get(f"/api/publico/t1/senas/{token}").json()
    assert vista["politica"]["reembolsable"] is True
    assert vista["politica"]["hay_pago_acreditado"] is False

    # ACREDITADA: hay plata retenida.
    h.senas.transicionar(
        tenant_id=T1,
        sena_id=creada.sena.id,
        desde="PENDIENTE",
        hacia="ACREDITADA",
        campos={"acreditada_en": AHORA},
    )
    vista = h.client.get(f"/api/publico/t1/senas/{token}").json()
    assert vista["politica"]["hay_pago_acreditado"] is True
    assert vista["politica"]["reembolsable"] is True

    for estado, campos in (
        ("LIBERADA", {"liberada_en": AHORA, "motivo_liberacion": "EXPIRACION"}),
        (
            "DEVUELTA",
            {
                "devuelta_en": AHORA,
                "motivo_devolucion": "POLITICA_CANCELACION",
                "devuelta_por": None,
            },
        ),
        (
            "APLICADA",
            {
                "acreditada_en": AHORA,
                "aplicada_en": AHORA,
                "movimiento_caja_id": "movimiento-mp-9",
                "concepto_aplicacion": "TRATAMIENTO",
            },
        ),
    ):
        otro = HarnessSenas()
        otro.configurar()
        senal = otro.crear(turno_id=f"turno-{estado.lower()}")
        actual = otro.senas.transicionar(
            tenant_id=T1,
            sena_id=senal.sena.id,
            desde="PENDIENTE",
            hacia=estado,  # type: ignore[arg-type]
            campos=campos,
        )
        assert actual is not None
        vista = otro.client.get(
            f"/api/publico/t1/senas/{senal.token_sena}"
        ).json()
        assert vista["politica"]["reembolsable"] is True
        assert vista["politica"]["hay_pago_acreditado"] is False
        # Sin PHI ni ids internos.
        for clave in ("paciente_id", "tenant_id", "nombre", "telefono"):
            assert clave not in vista
