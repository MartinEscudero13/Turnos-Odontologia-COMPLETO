"""Tasks 11.10–11.12 y 11.14 — auditoría y PHI de señas (RN-AU-02, RN-CL-04).

Criterios (design D15, spec §Auditoría y ausencia de PHI en señas):

- cada transición deja una entrada append-only con `tenant_id`, actor,
  `entidad`/`entidad_id` (`sena_id`), monto y `antes`/`después`;
- un webhook rechazado **no copia el cuerpo** recibido ni datos del pagador:
  queda el log estructurado con ids y motivo de dominio;
- `raw_json` del pago es una allow-list exacta (`id`, `status`,
  `status_detail`, `transaction_amount`, `currency_id`, `date_approved`,
  `external_reference`, `metadata`) sin pagador, tarjeta ni cuotas
  (C11-OQ-11);
- la auditoría no expone `update`/`delete`: la entrada original permanece.

Datos ficticios: T1, TUR-1/TUR-2, U1 (RECEPCION), U2 (ADMIN), `3000`.
"""
from __future__ import annotations

import logging

import pytest
from _senas_helpers import (
    AHORA,
    REQUEST_ID,
    T1,
    TS_FIRMA,
    TUR1,
    TUR2,
    U1,
    U2,
    HarnessSenaAplicacion,
    HarnessSenaCiclo,
    HarnessSenas,
    d3,
)

from app.turnos.servicio import Actor

TRANSICIONES = {
    "SENA_ACREDITADA",
    "SENA_APLICADA",
    "SENA_DEVUELTA",
    "SENA_LIBERADA",
    "SENA_REEMBOLSO_MP",
    "SENA_TRANSFERIDA",
}

# Acciones que el §11 exige verificar; `SENA_NO_TRANSFERIDA` y
# `SENA_PREFERENCIA_FALLIDA` viajan por el mismo puerto y se auditan igual.
ACCIONES_EXIGIDAS = TRANSICIONES | {
    "SENA_CREADA",
    "SENA_PREFERENCIA_CREADA",
}


# ---------------------------------------------------------------------------
# 11.10 — cada transición audita
# ---------------------------------------------------------------------------


def test_cada_transicion_audita() -> None:
    # GIVEN las señas de todos los caminos: alta, preferencia, transferencia,
    # webhook (acreditación y reembolso), expiración, aplicación y devolución.
    publico = HarnessSenas()
    publico.configurar()
    publico.crear()  # SENA_CREADA + SENA_PREFERENCIA_CREADA
    transferida = publico.svc.transferir_a_turno(
        tenant_id=T1,
        turno_anterior=TUR1,
        turno_nuevo=TUR2,
        turno_inicio=d3("2026-11-25"),
        ahora=AHORA,
    )
    assert transferida is not None

    caida = HarnessSenas()
    caida.configurar()
    caida.pasarela.fallar()
    caida.crear()  # SENA_PREFERENCIA_FALLIDA

    ciclo = HarnessSenaCiclo()
    acreditada = ciclo.sembrar_sena()
    ciclo.notificar(sena=acreditada, mp_payment_id="PAG-1")  # SENA_ACREDITADA
    ciclo.notificar(
        sena=acreditada, mp_payment_id="PAG-1", estado="REFUNDED"
    )  # SENA_DEVUELTA + SENA_REEMBOLSO_MP

    vencida = HarnessSenaCiclo()
    por_vencer = vencida.sembrar_sena(expira_at=AHORA)
    vencida.worker.procesar_expiraciones(tenant_id=T1, ahora=AHORA)

    aplicacion = HarnessSenaAplicacion()
    a_aplicar = aplicacion.sembrar_sena(turno_id=TUR1, estado="ACREDITADA")
    aplicacion.svc.aplicar(
        tenant_id=T1,
        sena_id=a_aplicar.id,
        actor=Actor(tenant_id=T1, rol="RECEPCION", user_id=U1),
        ahora=AHORA,
    )  # SENA_APLICADA
    a_devolver = aplicacion.sembrar_sena(turno_id=TUR2, estado="ACREDITADA")
    aplicacion.svc.devolver(
        tenant_id=T1,
        sena_id=a_devolver.id,
        actor=Actor(tenant_id=T1, rol="ADMIN", user_id=U2),
        motivo="cancelación con aviso",
        ahora=AHORA,
    )  # SENA_DEVUELTA

    # WHEN se consultan todas las entradas de auditoría del tenant.
    entradas = [
        *publico.auditoria.de_tenant(T1),
        *caida.auditoria.de_tenant(T1),
        *ciclo.auditoria.de_tenant(T1),
        *vencida.auditoria.de_tenant(T1),
        *aplicacion.auditoria.de_tenant(T1),
    ]

    # THEN están todas las acciones exigidas, con su entidad y su actor.
    assert {entrada.accion for entrada in entradas} >= ACCIONES_EXIGIDAS
    assert any(entrada.accion == "SENA_PREFERENCIA_FALLIDA" for entrada in entradas)

    for entrada in entradas:
        assert entrada.tenant_id == T1
        assert entrada.entidad == "sena"
        assert entrada.entidad_id, entrada.accion  # el sena_id
        assert entrada.actor, entrada.accion
        assert entrada.registrado_en, entrada.accion
        # El monto acompañado del hecho: sin él no se puede reconstruir la plata.
        assert entrada.despues is not None, entrada.accion
        assert entrada.despues["monto_centavos"] == 3000, entrada.accion
        if entrada.accion in TRANSICIONES:
            assert entrada.antes, entrada.accion
            assert entrada.despues["estado"], entrada.accion
        if entrada.accion == "SENA_CREADA":
            assert entrada.antes is None
        # Sin PHI: ni nombre, ni teléfono, ni DNI en ninguna entrada.
        texto = repr(entrada.antes) + repr(entrada.despues)
        assert "Paciente Demo" not in texto
        assert "+5491100000000" not in texto

    # AND la seña que expiró quedó LIBERADA y su entrada nombra el turno.
    liberada = next(
        entrada for entrada in entradas if entrada.accion == "SENA_LIBERADA"
    )
    assert liberada.despues is not None
    assert liberada.despues["turno_id"] == por_vencer.turno_id

    # AND la transición del turno viaja en la misma entrada append-only
    # (`turnos-anti-solape`): PENDIENTE → CONFIRMADO al acreditar y
    # PENDIENTE → CANCELADO al liberar, con antes/después observable.
    acreditada = next(
        entrada for entrada in entradas if entrada.accion == "SENA_ACREDITADA"
    )
    assert acreditada.despues is not None
    assert acreditada.despues["turno_antes"] == "PENDIENTE"
    assert acreditada.despues["turno_despues"] == "CONFIRMADO"
    assert liberada.despues["turno_antes"] == "PENDIENTE"
    assert liberada.despues["turno_despues"] == "CANCELADO"


# ---------------------------------------------------------------------------
# 11.11 — un webhook rechazado no copia el cuerpo
# ---------------------------------------------------------------------------


def test_webhook_rechazado_no_copia_cuerpo(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """La firma se verifica **antes** de resolver el tenant (D7).

    Consecuencia declarada: el rechazo no puede auditarse contra un tenant que
    todavía no se conoce (`auditoria.tenant_id` es `NOT NULL` y no se inventa) y
    tampoco se persiste el pago. El hecho queda en el log estructurado con ids y
    motivo de dominio, y **nunca** con el cuerpo ni datos del pagador (F-25).
    """
    # GIVEN una notificación con firma inválida y un cuerpo con datos del pagador.
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    cuerpo = {
        "type": "payment",
        "data": {"id": "PAG-9"},
        "payer": {"email": "pagador@demo.test", "first_name": "Paciente Demo"},
    }
    logger = logging.getLogger("app.senas.webhook")

    # WHEN se procesa el webhook con una firma que no corresponde.
    with caplog.at_level(logging.WARNING, logger="app.senas.webhook"):
        respuesta = h.client.post(
            "/api/webhooks/mercadopago?data.id=PAG-9&type=payment",
            json=cuerpo,
            headers={
                "x-request-id": REQUEST_ID,
                "x-signature": f"ts={TS_FIRMA},v1={'0' * 64}",
            },
        )

    # THEN 401 sin persistir nada: ni pago, ni seña acreditada, ni auditoría.
    assert respuesta.status_code == 401, respuesta.text
    assert respuesta.json() == {
        "detalle": "la firma no coincide",
        "codigo": "FIRMA_INVALIDA",
    }
    assert h.pago("PAG-9") is None
    assert h.pagos.total(T1) == 0
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.auditoria.entradas == []

    # AND el rechazo deja id y motivo de dominio, sin copiar el cuerpo.
    registros = [r for r in caplog.records if r.name == logger.name]
    assert registros, "falta el log estructurado del rechazo"
    registro = registros[-1]
    assert registro.codigo == "FIRMA_INVALIDA"
    assert registro.mp_payment_id == "PAG-9"
    assert registro.motivo == "firma_invalida"
    assert "pagador@demo.test" not in caplog.text
    assert "Paciente Demo" not in caplog.text
    assert "payer" not in caplog.text


# ---------------------------------------------------------------------------
# 11.12 — raw_json minimizado
# ---------------------------------------------------------------------------


def test_raw_json_minimizado() -> None:
    # GIVEN un pago aprobado con metadata de seña/turno/tenant.
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    # WHEN llega la notificación firmada.
    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1")
    assert respuesta.status_code == 200, respuesta.text

    # THEN raw_json es exactamente la allow-list del design (C11-OQ-11).
    pago = h.pago("PAG-1")
    assert pago is not None
    assert set(pago.raw_json) == {
        "id",
        "status",
        "status_detail",
        "transaction_amount",
        "currency_id",
        "date_approved",
        "external_reference",
        "metadata",
    }
    assert pago.raw_json["id"] == "PAG-1"
    assert pago.raw_json["status"] == "APPROVED"
    assert pago.raw_json["status_detail"] == "accredited"
    assert pago.raw_json["transaction_amount"] == 3000
    assert pago.raw_json["currency_id"] == "ARS"
    assert pago.raw_json["external_reference"] == sena.id
    assert set(pago.raw_json["metadata"]) == {"sena_id", "turno_id", "tenant_id"}

    # AND no viaja ningún dato del pagador ni de la tarjeta.
    serializado = repr(pago.raw_json)
    for prohibido in (
        "payer",
        "email",
        "first_name",
        "card",
        "installments",
        "phone",
        "document",
    ):
        assert prohibido not in serializado
    assert "pagador@demo.test" not in serializado


# ---------------------------------------------------------------------------
# 11.14 — la auditoría es append-only
# ---------------------------------------------------------------------------


def test_auditoria_append_only() -> None:
    # GIVEN una seña creada y su entrada de auditoría.
    h = HarnessSenas()
    h.configurar()
    h.crear()
    entradas = h.auditoria.de_tenant(T1)
    assert entradas, "la seña no dejó auditoría"
    original = entradas[0]

    # WHEN se intenta mutar la auditoría desde el puerto.
    # THEN el puerto no expone update/delete y la entrada original permanece.
    for metodo in ("actualizar", "borrar", "eliminar", "update", "delete"):
        assert not hasattr(h.auditoria, metodo)
    copia = h.auditoria.de_tenant(T1)
    copia.clear()
    assert h.auditoria.de_tenant(T1) == entradas
    assert h.auditoria.entradas[0] == original
    assert original.accion == "SENA_CREADA"
    assert original.entidad_id


# ---------------------------------------------------------------------------
# La vista interna expone la obligación de devolución (RN-SE-04)
# ---------------------------------------------------------------------------


def test_obligacion_de_reintegro_visible_en_el_listado() -> None:
    # GIVEN T1 con una seña y un pago de monto distinto registrado por el webhook.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="PENDIENTE")
    h.pagos.registrar_o_actualizar(
        tenant_id=T1,
        sena_id=sena.id,
        mp_payment_id="PAG-4",
        monto_centavos=1000,
        moneda="ARS",
        estado="APPROVED",
        resultado="MONTO_DISTINTO",
        raw_json={"id": "PAG-4"},
        ahora=AHORA,
    )

    # WHEN la consulta interna lista las señas del rango.
    listado = h.client_interno.get(
        "/api/senas",
        params={"desde": "2026-11-10", "hasta": "2026-11-30"},
        headers={"X-Tenant-Id": T1, "X-User-Id": U1, "X-Rol": "RECEPCION"},
    )

    # THEN la obligación de PAG-4 aparece con su monto y su origen.
    assert listado.status_code == 200, listado.text
    [vista] = listado.json()
    assert vista["sena_id"] == sena.id
    assert vista["obligaciones"] == [
        {
            "origen": "PAGO",
            "tipo": "REINTEGRO",
            "monto_centavos": 1000,
            "motivo": "MONTO_DISTINTO",
            "mp_payment_id": "PAG-4",
        }
    ]
