"""Tasks 3.1–3.6, 4.1–4.2 — auto-oferta de huecos liberados y rotación por expiración."""
from __future__ import annotations

from _lista_espera_helpers import PREST30, HarnessLista
from conftest import T1, dt
from fastapi.testclient import TestClient

from app.lista_espera.puertos import HuecoLiberadoMemoria
from app.routers.turnos import crear_app
from app.turnos.servicio import Actor, ServicioTurnos

BASE = {"X-Tenant-Id": T1, "X-User-Id": "recep-1", "X-Rol": "RECEPCION"}
PAYLOAD = {
    "profesional_id": "profesional-1",
    "sillon_id": "sillon-1",
    "paciente_id": "paciente-otro",
    "prestacion_id": PREST30,
    "inicio": "2026-10-14T10:00:00+00:00",
    "duracion_min": 30,
}


def _recep(tenant: str = T1) -> Actor:
    return Actor(tenant_id=tenant, rol="RECEPCION", user_id="recep-1")


def _hueco_y_compatible(inicio: str = "2026-10-14", hora: int = 10):
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt(inicio, hora))
    return h, turno


def test_cancelacion_emite_evento_hueco_liberado():
    svc = ServicioTurnos(anticipacion_min_horas=0.0)
    hueco = HuecoLiberadoMemoria()  # spy sin worker
    client = TestClient(crear_app(svc, hueco))
    turno_id = client.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    r = client.post(f"/api/turnos/{turno_id}/cancelar", headers=BASE)
    assert r.status_code == 200
    assert hueco.eventos == [(T1, turno_id)]


def test_reprogramacion_emite_evento_del_hueco_original():
    svc = ServicioTurnos(anticipacion_min_horas=0.0)
    hueco = HuecoLiberadoMemoria()
    client = TestClient(crear_app(svc, hueco))
    turno_id = client.post("/api/turnos", json=PAYLOAD, headers=BASE).json()["id"]
    r = client.post(
        f"/api/turnos/{turno_id}/reprogramar",
        json={"nuevo_inicio": "2026-10-14T14:00:00+00:00"},
        headers=BASE,
    )
    assert r.status_code == 200
    assert hueco.eventos == [(T1, turno_id)]


def test_hueco_liberado_ofrece_al_primer_compatible():
    h, turno = _hueco_y_compatible()
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None
    assert oferta.estado == "PENDIENTE"
    assert oferta.expira_at == dt("2026-10-13", 11)  # ahora + 120 min
    entrada = h.lista_repo.obtener(tenant_id=T1, entrada_id=oferta.entrada_id)
    assert entrada is not None and entrada.estado == "OFRECIDO"


def test_sin_lista_compatible_hueco_queda_publico():
    h = HarnessLista()
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is None
    assert h.oferta_repo.pendientes(tenant_id=T1) == []


def test_doble_evento_del_mismo_turno_genera_una_oferta():
    h, turno = _hueco_y_compatible()
    o1 = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    o2 = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert o1 is not None
    assert o2 is None
    assert len(h.oferta_repo.pendientes(tenant_id=T1)) == 1


def test_oferta_expira_en_slot_inicio_y_hueco_pasado_se_publica_directo():
    # (a) expiración acotada al inicio del slot
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-14", 8))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10, 30))
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-14", 9))
    # ahora 09:00 + 120 min = 11:00 > 10:30 → expira_at = slot.inicio
    assert oferta is not None and oferta.expira_at == dt("2026-10-14", 10, 30)

    # (b) hueco con inicio ya pasado → público directo
    h2 = HarnessLista()
    h2.seed_catalogo()
    h2.seed_paciente("paciente-1")
    h2.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-14", 8))
    turno2 = h2.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 9))
    assert h2.svc_ofertas.procesar_hueco_liberado(T1, turno2.id, ahora=dt("2026-10-14", 10)) is None


def test_reprogramacion_libera_hueco_original_y_dispara_oferta():
    h, turno = _hueco_y_compatible()
    res = h.turnos.reprogramar(
        _recep(), turno.id, nuevo_inicio=dt("2026-10-14", 14), ahora=dt("2026-10-13", 9)
    )
    oferta = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert oferta is not None
    assert oferta.hueco_turno_id == turno.id  # slot original 10:00
    assert res.nuevo.inicio == dt("2026-10-14", 14)  # nuevo slot ocupado


def test_oferta_vencida_rota_al_siguiente_compatible():
    h = HarnessLista()
    h.seed_catalogo()
    h.seed_paciente("paciente-1")
    h.seed_paciente("paciente-2")
    e1 = h.alta_entrada(paciente_id="paciente-1", prestacion_id=PREST30, ahora=dt("2026-10-13", 9))
    e2 = h.alta_entrada(paciente_id="paciente-2", prestacion_id=PREST30, ahora=dt("2026-10-13", 10))
    turno = h.crear_turno(paciente_id="paciente-otro", inicio=dt("2026-10-14", 10))
    o1 = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert o1 is not None and o1.entrada_id == e1.id
    # vence y rota
    creadas = h.svc_ofertas.procesar_expiracion(T1, ahora=dt("2026-10-13", 11, 1))
    assert h.oferta_repo.por_token(tenant_id=T1, token=o1.token).estado == "VENCIDA"
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=e1.id).estado == "PENDIENTE"
    assert len(creadas) == 1
    assert creadas[0].entrada_id == e2.id
    assert h.lista_repo.obtener(tenant_id=T1, entrada_id=e2.id).estado == "OFRECIDO"


def test_ultimo_compatible_vencido_libera_hueco_publico():
    h, turno = _hueco_y_compatible()
    o1 = h.svc_ofertas.procesar_hueco_liberado(T1, turno.id, ahora=dt("2026-10-13", 9))
    assert o1 is not None
    creadas = h.svc_ofertas.procesar_expiracion(T1, ahora=dt("2026-10-13", 11, 1))
    assert creadas == []
    assert h.oferta_repo.pendientes(tenant_id=T1) == []
    assert h.oferta_repo.por_token(tenant_id=T1, token=o1.token).estado == "VENCIDA"
