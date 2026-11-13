"""Tasks 6.1–6.14, 6.16 y 6.17 — webhook de Mercado Pago (RN-SE-03, D7/D8).

La pasarela es `AdaptadorPasarelaFake` y el secreto de firma es **ficticio**:
ningún test abre sockets ni usa credenciales reales. Reloj inyectado en
`-03:00`; datos ficticios (`Paciente Demo`, `PREST-1`, `3000`).

Contrato que se verifica acá:

- la firma HMAC manda: sin firma válida no hay `401` ni persistencia;
- sin secreto, `503` fail-closed;
- el cuerpo **no** acredita: la verdad es la re-consulta a la pasarela;
- `DUPLICADO` es sólo el mismo `mp_payment_id`; un pago distinto sobre una seña
  ya resuelta es `PAGO_EXCEDENTE` y un monto/moneda distintos son
  `MONTO_DISTINTO`; ambos dejan la obligación de devolución registrada y
  consultable (`pagos.listar`), que es lo que `GET /api/senas` expondrá en §11;
- el pago no asociable es `500` con log estructurado, nunca descartado.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from _senas_helpers import (
    AHORA,
    TUR1,
    HarnessSenaCiclo,
    firmar,
)
from conftest import T1, T2


def test_firma_valida_procesa() -> None:
    """6.1 — con la firma correcta se registra el pago y se acredita la seña."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1", monto_centavos=3000)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "ACREDITADA"
    assert respuesta.json()["mp_payment_id"] == "PAG-1"
    assert respuesta.json()["sena_id"] == sena.id
    pago = h.pago("PAG-1")
    assert pago is not None
    assert (pago.estado, pago.resultado, pago.moneda) == ("APPROVED", "ACREDITADA", "ARS")
    assert pago.monto_centavos == 3000
    assert pago.sena_id == sena.id
    actual = h.sena(sena)
    assert actual.estado == "ACREDITADA"
    assert actual.acreditada_en == AHORA
    # El raw_json es la allow-list: ids, estado, monto y metadata; sin pagador.
    assert pago.raw_json["id"] == "PAG-1"
    assert pago.raw_json["status"] == "APPROVED"
    assert pago.raw_json["metadata"]["sena_id"] == sena.id
    assert "payer" not in pago.raw_json
    assert "card" not in pago.raw_json


def test_firma_invalida_401() -> None:
    """6.2 — sin `x-signature` o con otro `v1`: 401, nada persistido, cero consultas."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    for variante in ("ausente", "invalida", "otro_secreto"):
        respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1", firma=variante)
        assert respuesta.status_code == 401, (variante, respuesta.text)
        assert respuesta.json()["codigo"] == "FIRMA_INVALIDA"
        assert h.pago("PAG-1") is None
        assert h.sena(sena).estado == "PENDIENTE"
        assert h.pasarela.consultas == []
    assert h.auditoria.de_accion("SENA_ACREDITADA") == []


def test_sin_secreto_503() -> None:
    """6.3 — sin `MP_WEBHOOK_SECRET` el webhook falla cerrado."""
    h = HarnessSenaCiclo(secreto=None)
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1", firma="ausente")

    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "WEBHOOK_NO_CONFIGURADO"
    assert h.pago("PAG-1") is None
    assert h.sena(sena).estado == "PENDIENTE"
    # Ni siquiera se consulta la pasarela: fail-closed de verdad.
    assert h.pasarela.consultas == []


def test_el_cuerpo_no_acredita() -> None:
    """6.4 — el cuerpo declara `approved` y `monto=1`, la pasarela dice `REJECTED`."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    h.pasarela.rechazar("PAG-1", sena_id=sena.id, monto_centavos=3000, tenant_id=T1)

    respuesta = h.client.post(
        "/api/webhooks/mercadopago?data.id=PAG-1&type=payment",
        json={
            "type": "payment",
            "data": {"id": "PAG-1", "status": "approved", "transaction_amount": 1},
        },
        headers={"x-request-id": "req-ficticio-1", "x-signature": firmar("PAG-1")},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "IGNORADO"
    pago = h.pago("PAG-1")
    assert pago is not None
    # Se registra el estado REAL de la pasarela, no el del cuerpo.
    assert (pago.estado, pago.resultado) == ("REJECTED", "IGNORADO")
    assert pago.monto_centavos == 3000
    assert h.sena(sena).estado == "PENDIENTE"


def test_notificacion_no_payment_se_ignora() -> None:
    """6.5 — `type=merchant_order` firmado: 200 sin consultar la pasarela."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="ORDER-1", tipo="merchant_order")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "IGNORADO"
    assert h.pasarela.consultas == []
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.pagos.total(T1) == 0


def test_pasarela_caida_503() -> None:
    """6.6 — MP no responde al re-consultar: 503, nada cambia, MP reintenta."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    h.pasarela.fallar("PAG-1")

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1")

    assert respuesta.status_code == 503, respuesta.text
    assert respuesta.json()["codigo"] == "MP_NO_DISPONIBLE"
    assert h.pago("PAG-1") is None
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.auditoria.de_accion("SENA_ACREDITADA") == []


def test_duplicado_200_sin_efecto() -> None:
    """6.7 — la segunda notificación del mismo pago: DUPLICADO y ningún efecto."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    primera = h.notificar(sena=sena, mp_payment_id="PAG-1")
    segunda = h.notificar(sena=sena, mp_payment_id="PAG-1")

    assert primera.status_code == 200, primera.text
    assert primera.json()["resultado"] == "ACREDITADA"
    assert segunda.status_code == 200, segunda.text
    assert segunda.json()["resultado"] == "DUPLICADO"
    assert h.pagos.total(T1) == 1
    # Un solo hecho auditado y una sola acreditación.
    assert len(h.auditoria.de_accion("SENA_ACREDITADA")) == 1
    assert h.sena(sena).estado == "ACREDITADA"
    # La obligación se conserva: el `DUPLICADO` no borra el efecto aplicado.
    assert h.pago("PAG-1") is not None
    assert h.pago("PAG-1").resultado == "ACREDITADA"


def test_estado_no_aprobado_registra_sin_acreditar() -> None:
    """6.8 — `PENDING` deja fila `IGNORADO` y la seña sigue `PENDIENTE`."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-2", estado="PENDING")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "IGNORADO"
    pago = h.pago("PAG-2")
    assert pago is not None
    assert (pago.estado, pago.resultado) == ("PENDING", "IGNORADO")
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.turnos.turno_de(tenant_id=T1, turno_id=TUR1).estado == "PENDIENTE"  # type: ignore[union-attr]


def test_desorden_no_degrada() -> None:
    """6.9 — un `PENDING` posterior a `APPROVED` no des-acredita ni degrada."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    h.notificar(sena=sena, mp_payment_id="PAG-3", estado="APPROVED")
    tarde = h.notificar(sena=sena, mp_payment_id="PAG-3", estado="PENDING")

    assert tarde.status_code == 200, tarde.text
    assert tarde.json()["resultado"] == "DUPLICADO"
    pago = h.pago("PAG-3")
    assert pago is not None
    assert pago.estado == "APPROVED"  # el ranking no retrocede (D3)
    assert pago.resultado == "ACREDITADA"
    assert h.sena(sena).estado == "ACREDITADA"
    assert len(h.auditoria.de_accion("SENA_ACREDITADA")) == 1
    assert h.auditoria.de_accion("SENA_DEVUELTA") == []


def test_monto_distinto_no_acredita() -> None:
    """6.10 — seña de `3000`, pago de `1000`: MONTO_DISTINTO y devolución visible."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-4", monto_centavos=1000)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "MONTO_DISTINTO"
    assert h.sena(sena).estado == "PENDIENTE"
    pago = h.pago("PAG-4")
    assert pago is not None
    assert (pago.monto_centavos, pago.resultado) == (1000, "MONTO_DISTINTO")
    obligaciones = h.obligaciones()
    assert [p.mp_payment_id for p in obligaciones] == ["PAG-4"]


def test_moneda_distinta_no_acredita() -> None:
    """6.11 — pago en `USD`: MONTO_DISTINTO, se registra y queda la devolución."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(
        sena=sena, mp_payment_id="PAG-USD", monto_centavos=3000, moneda="USD"
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "MONTO_DISTINTO"
    pago = h.pago("PAG-USD")
    assert pago is not None
    # La moneda real se persiste: con `CHECK moneda='ARS'` esta fila no existiría.
    assert (pago.moneda, pago.resultado) == ("USD", "MONTO_DISTINTO")
    assert h.sena(sena).estado == "PENDIENTE"
    assert [p.mp_payment_id for p in h.obligaciones()] == ["PAG-USD"]


def test_pago_no_asociable_500(caplog: pytest.LogCaptureFixture) -> None:
    """6.12 — no resuelve a una seña del tenant: 500, sin persistir y con log."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    logger = logging.getLogger("app.senas.webhook")

    with caplog.at_level(logging.ERROR, logger="app.senas.webhook"):
        respuesta = h.notificar(
            sena=sena, mp_payment_id="PAG-5", sena_id="sena-inexistente"
        )

    assert respuesta.status_code == 500, respuesta.text
    assert respuesta.json()["codigo"] == "PAGO_NO_ASOCIABLE"
    assert h.pagos.total(T1) == 0
    assert h.sena(sena).estado == "PENDIENTE"
    assert h.auditoria.de_tenant(T1) == []
    # Log estructurado: ids y motivo, sin cuerpo ni datos del pagador.
    registros = [r for r in caplog.records if r.name == logger.name]
    assert registros, "falta el log estructurado del pago no asociable"
    registro = registros[-1]
    assert registro.codigo == "PAGO_NO_ASOCIABLE"
    assert registro.mp_payment_id == "PAG-5"
    assert registro.tenant_id == T1
    assert registro.sena_id == "sena-inexistente"
    assert registro.motivo == "sena_no_encontrada_en_el_tenant"
    assert "Paciente Demo" not in registro.getMessage()


def test_acredita_y_confirma_turno() -> None:
    """6.13 — seña ACREDITADA + turno CONFIRMADO + auditoría con el pago."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-1")

    assert respuesta.status_code == 200, respuesta.text
    actual = h.sena(sena)
    assert actual.estado == "ACREDITADA"
    assert actual.acreditada_en is not None
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "CONFIRMADO"
    entradas = h.auditoria.de_accion("SENA_ACREDITADA")
    assert len(entradas) == 1
    assert entradas[0].actor == "webhook-mp"
    assert entradas[0].antes == {"estado": "PENDIENTE"}
    assert entradas[0].despues is not None
    assert entradas[0].despues["mp_payment_id"] == "PAG-1"
    assert entradas[0].despues["estado"] == "ACREDITADA"


def test_pago_sobre_turno_cancelado_devuelve() -> None:
    """6.14 — turno CANCELADO: DEVUELTA/TURNO_NO_CONFIRMABLE, sin reabrir hueco."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena(turno_estado="CANCELADO")

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-6")

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "TURNO_NO_CONFIRMABLE"
    actual = h.sena(sena)
    assert actual.estado == "DEVUELTA"
    assert actual.motivo_devolucion == "TURNO_NO_CONFIRMABLE"
    assert actual.devuelta_por is None
    turno = h.turnos.turno_de(tenant_id=T1, turno_id=TUR1)
    assert turno is not None and turno.estado == "CANCELADO"
    # El hueco no se reabre: no se emite ningún evento de hueco liberado.
    assert h.eventos_hueco() == []


def test_segundo_pago_aprobado_es_excedente() -> None:
    """6.16 — otro `APPROVED` por el mismo monto es PAGO_EXCEDENTE, no DUPLICADO."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    assert h.notificar(sena=sena, mp_payment_id="PAG-A").json()["resultado"] == "ACREDITADA"

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-B", monto_centavos=3000)

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "PAGO_EXCEDENTE"
    assert h.sena(sena).estado == "ACREDITADA"
    pago_b = h.pago("PAG-B")
    assert pago_b is not None
    assert pago_b.resultado == "PAGO_EXCEDENTE"
    assert [p.mp_payment_id for p in h.obligaciones()] == ["PAG-B"]
    # Sólo una acreditación: la segunda plata no se aplica.
    assert len(h.auditoria.de_accion("SENA_ACREDITADA")) == 1


def test_refunded_de_mp() -> None:
    """6.17 — `REFUNDED` cierra la obligación o pide ajuste de caja (F-18)."""
    # (a) Seña ACREDITADA: el reembolso la deja DEVUELTA con su motivo.
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    h.notificar(sena=sena, mp_payment_id="PAG-C")

    reembolso = h.notificar(
        sena=sena, mp_payment_id="PAG-C", estado="REFUNDED"
    )

    assert reembolso.status_code == 200, reembolso.text
    assert reembolso.json()["resultado"] == "REEMBOLSADO"
    actual = h.sena(sena)
    assert actual.estado == "DEVUELTA"
    assert actual.motivo_devolucion == "REEMBOLSO_MP"
    assert actual.devuelta_por is None
    pago = h.pago("PAG-C")
    assert pago is not None and pago.resultado == "REEMBOLSADO"
    assert h.auditoria.de_accion("SENA_REEMBOLSO_MP")

    # (b) Seña APLICADA: la plata ya está en caja, sólo queda el ajuste.
    h2 = HarnessSenaCiclo()
    aplicada = h2.sembrar_sena(estado="APLICADA")
    h2.notificar(sena=aplicada, mp_payment_id="PAG-D")

    ajuste = h2.notificar(sena=aplicada, mp_payment_id="PAG-D", estado="REFUNDED")

    assert ajuste.status_code == 200, ajuste.text
    assert ajuste.json()["resultado"] == "REEMBOLSO_AJUSTE_CAJA"
    assert h2.sena(aplicada).estado == "APLICADA"
    assert [p.mp_payment_id for p in h2.obligaciones()] == ["PAG-D"]


def test_metadata_del_cuerpo_no_manda() -> None:
    """F-26 — la metadata confiable es la de la re-consulta, no la del cuerpo."""
    h = HarnessSenaCiclo()
    sena = h.sembrar_sena()
    # El pago re-consultado pertenece a T1; el cuerpo intenta declarar T2.
    h.pasarela.aprobar(
        "PAG-7",
        sena_id=sena.id,
        monto_centavos=3000,
        tenant_id=T1,
        turno_id=sena.turno_id,
    )

    respuesta = h.client.post(
        "/api/webhooks/mercadopago?data.id=PAG-7&type=payment",
        json={
            "type": "payment",
            "data": {"id": "PAG-7"},
            "metadata": {"tenant_id": T2, "sena_id": "otra-sena"},
        },
        headers={"x-request-id": "req-ficticio-1", "x-signature": firmar("PAG-7")},
    )

    assert respuesta.status_code == 200, respuesta.text
    assert respuesta.json()["resultado"] == "ACREDITADA"
    assert h.pago("PAG-7", tenant_id=T2) is None
    assert h.sena(sena).estado == "ACREDITADA"


def test_reloj_inyectado_no_usa_el_del_sistema() -> None:
    """D10 — el webhook sella los instantes con el reloj inyectado."""
    h = HarnessSenaCiclo(ahora=AHORA + timedelta(days=2))
    sena = h.sembrar_sena(expira_at=AHORA + timedelta(days=3))

    respuesta = h.notificar(sena=sena, mp_payment_id="PAG-9")

    assert respuesta.status_code == 200, respuesta.text
    assert h.sena(sena).acreditada_en == AHORA + timedelta(days=2)
