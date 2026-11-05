"""Tasks 4.3a–4.3b — emisor de verificación y single-use en la ruta real: RED primero."""
from __future__ import annotations

import threading

from _reserva_helpers import Harness, catalogo_estandar, emitir, reserva_payload
from conftest import P1, T1, dt

from app.turnos.servicio import Actor, TurnoError


def _harness(**kw) -> Harness:
    h = Harness(ttl_min=10, canal="captcha", reloj_inicial=dt("2026-10-05", 9), **kw)
    catalogo_estandar(h)
    return h


def test_verificacion_emitida_201_con_expira_at_derivado():
    h = _harness()
    r = h.client.post("/api/publico/t1/verificacion", json={"accion": "reservar"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["verificacion_id"]
    assert body["expira_at"] == "2026-10-05T09:10:00Z"
    assert body["canal"] == "captcha"


def test_verificacion_vencida_responde_403_sin_mutar():
    h = _harness()
    vid = emitir(h)  # expira_at = 09:10
    h.fijar_ahora("2026-10-05", 9, 11)
    r = h.client.post(
        "/api/publico/t1/reservas", json=reserva_payload(verificacion_id=vid)
    )
    assert r.status_code == 403, r.text
    assert h.turnos.listar(Actor(tenant_id=T1, rol="RECEPCION", user_id="x")) == []  # no muta


def test_verificacion_reusada_en_concurrencia_gana_una_sola():
    h = _harness()
    d = h.svc.emitir_verificacion("t1", "reservar", "1.2.3.4")
    vid = d.verificacion_id
    resultados: list[int] = []

    def intentar() -> None:
        try:
            h.svc.reservar(
                "t1",
                prestacion_id="PREST-30",
                profesional_id=P1,
                inicio=dt("2026-10-06", 10),
                nombre="Paciente Demo",
                telefono="+5491130551234",
                verificacion_id=vid,
                ip="1.2.3.4",
            )
            resultados.append(201)
        except TurnoError as exc:
            resultados.append(exc.codigo)

    hilos = [threading.Thread(target=intentar) for _ in range(2)]
    for t in hilos:
        t.start()
    for t in hilos:
        t.join()
    assert sorted(resultados) == [201, 403]
