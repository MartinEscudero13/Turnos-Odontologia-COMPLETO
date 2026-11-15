"""HTTP tests for the C-07/C-10/C-11 demo wiring.

Cada test construye su propia app: el composition root es en memoria y el estado
no se comparte entre tests. Todos los datos son ficticios (RN-GL-03).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_PACIENTE_1,
    DEMO_TENANT_ID,
    DEMO_USER_ID,
    PRESTACION_CONSULTA,
    PRESTACION_LIMPIEZA,
    PROFESIONAL_DEMO_1,
)

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)

TZ_OPERATIVA = timezone(timedelta(hours=-3))


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(rol: str = "RECEPCION", user_id: str = DEMO_USER_ID) -> dict[str, str]:
    return {"X-Tenant-Id": DEMO_TENANT_ID, "X-User-Id": user_id, "X-Rol": rol}


def dia_operativo() -> str:
    return datetime.now(TZ_OPERATIVA).date().isoformat()


def desde_disponibilidad(dias: int = 2) -> str:
    dia = (datetime.now(TZ_OPERATIVA) + timedelta(days=dias)).date().isoformat()
    return f"{dia}T00:00:00-03:00"


def primer_slot(c: TestClient, prestacion: str) -> dict[str, str]:
    response = c.get(
        "/api/publico/demo/disponibilidad",
        params={
            "prestacion": prestacion,
            "profesional": PROFESIONAL_DEMO_1,
            "desde": desde_disponibilidad(),
        },
    )
    assert response.status_code == 200, response.text
    slots = response.json()
    assert slots, "el catálogo demo debería ofrecer al menos un hueco"
    return slots[0]


def reservar(c: TestClient, prestacion: str, inicio: str) -> dict[str, object]:
    verificacion = c.post("/api/publico/demo/verificacion", json={"accion": "reservar"})
    assert verificacion.status_code == 201, verificacion.text
    response = c.post(
        "/api/publico/demo/reservas",
        json={
            "prestacion": prestacion,
            "profesional": PROFESIONAL_DEMO_1,
            "inicio": inicio,
            "nombre": "Paciente Demo",
            "telefono": "+5491130551234",
            "verificacion_id": verificacion.json()["verificacion_id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------------------------------------------------------------------------
# C-07 — lista de espera
# ---------------------------------------------------------------------------


def test_lista_espera_alta_y_listado() -> None:
    c = client()

    alta = c.post(
        "/api/lista-espera",
        headers=actor(),
        json={"paciente_id": DEMO_PACIENTE_1, "prestacion_id": PRESTACION_CONSULTA},
    )
    assert alta.status_code == 201, alta.text
    entrada = alta.json()
    assert entrada["estado"] == "PENDIENTE"
    assert entrada["paciente_id"] == DEMO_PACIENTE_1

    listado = c.get("/api/lista-espera", headers=actor())
    assert listado.status_code == 200, listado.text
    assert [e["id"] for e in listado.json()] == [entrada["id"]]


def test_lista_espera_rechaza_rol_paciente() -> None:
    c = client()

    response = c.post(
        "/api/lista-espera",
        headers=actor(rol="PACIENTE"),
        json={"paciente_id": DEMO_PACIENTE_1, "prestacion_id": PRESTACION_CONSULTA},
    )
    assert response.status_code == 403, response.text
    assert c.get("/api/lista-espera", headers=actor()).json() == []


def test_lista_espera_filtra_por_prestacion() -> None:
    c = client()
    for paciente_id, prestacion in (
        (DEMO_PACIENTE_1, PRESTACION_CONSULTA),
        (DEMO_PACIENTE_1, PRESTACION_LIMPIEZA),
    ):
        assert (
            c.post(
                "/api/lista-espera",
                headers=actor(),
                json={"paciente_id": paciente_id, "prestacion_id": prestacion},
            ).status_code
            == 201
        )

    consulta = c.get(
        "/api/lista-espera", headers=actor(), params={"prestacion_id": PRESTACION_CONSULTA}
    )
    assert consulta.status_code == 200, consulta.text
    assert [e["prestacion_id"] for e in consulta.json()] == [PRESTACION_CONSULTA]


# ---------------------------------------------------------------------------
# C-10 — caja
# ---------------------------------------------------------------------------


def test_caja_registra_movimiento_y_consulta_el_dia() -> None:
    c = client()
    fecha = dia_operativo()

    alta = c.post(
        "/api/caja/movimientos",
        headers=actor(),
        json={"monto": 150000, "medio": "EFECTIVO", "tipo": "INGRESO", "fecha": fecha},
    )
    assert alta.status_code == 201, alta.text
    assert alta.json()["monto"] == 150000

    consulta = c.get("/api/caja/movimientos", headers=actor(), params={"fecha": fecha})
    assert consulta.status_code == 200, consulta.text
    cuerpo = consulta.json()
    assert cuerpo["estado"] == "abierto"
    assert cuerpo["totales_vigentes"]["efectivo"] == 150000
    assert len(cuerpo["movimientos"]) == 1


def test_caja_acumula_movimientos_del_mismo_medio() -> None:
    c = client()
    fecha = dia_operativo()

    for monto in (100000, 75000):
        assert (
            c.post(
                "/api/caja/movimientos",
                headers=actor(),
                json={"monto": monto, "medio": "TRANSFERENCIA", "fecha": fecha},
            ).status_code
            == 201
        )

    consulta = c.get("/api/caja/movimientos", headers=actor(), params={"fecha": fecha})
    assert consulta.status_code == 200, consulta.text
    assert consulta.json()["totales_vigentes"]["transferencia"] == 175000
    assert consulta.json()["totales_vigentes"]["efectivo"] == 0


def test_caja_dia_cerrado_rechaza_movimientos_nuevos() -> None:
    c = client()
    fecha = dia_operativo()

    assert (
        c.post(
            "/api/caja/movimientos",
            headers=actor(),
            json={"monto": 150000, "medio": "EFECTIVO", "fecha": fecha},
        ).status_code
        == 201
    )
    cierre = c.post(
        "/api/caja/cierre",
        headers=actor(),
        json={"efectivo_contado": 150000, "responsable_id": DEMO_USER_ID, "fecha": fecha},
    )
    assert cierre.status_code == 201, cierre.text

    rechazo = c.post(
        "/api/caja/movimientos",
        headers=actor(),
        json={"monto": 1000, "medio": "EFECTIVO", "fecha": fecha},
    )
    assert rechazo.status_code == 409, rechazo.text


# ---------------------------------------------------------------------------
# C-11 — señas
# ---------------------------------------------------------------------------


def test_reserva_publica_crea_sena_y_se_lee_por_token() -> None:
    c = client()
    slot = primer_slot(c, PRESTACION_CONSULTA)
    reserva = reservar(c, PRESTACION_CONSULTA, slot["inicio"])

    sena = reserva["sena"]
    assert isinstance(sena, dict), reserva
    assert sena["estado"] == "PENDIENTE"
    assert sena["monto_centavos"] == 3000
    assert sena["token_sena"]

    publica = c.get(f"/api/publico/demo/senas/{sena['token_sena']}")
    assert publica.status_code == 200, publica.text
    assert publica.json()["sena_id"] == sena["sena_id"]
    assert publica.json()["turno"]["prestacion"] == PRESTACION_CONSULTA

    dia = (datetime.strptime(slot["inicio"][:10], "%Y-%m-%d")).date()
    internas = c.get(
        "/api/senas",
        headers=actor(),
        params={"desde": dia.isoformat(), "hasta": (dia + timedelta(days=1)).isoformat()},
    )
    assert internas.status_code == 200, internas.text
    assert [s["sena_id"] for s in internas.json()] == [sena["sena_id"]]


def test_reserva_de_limpieza_no_exige_sena() -> None:
    c = client()
    slot = primer_slot(c, PRESTACION_LIMPIEZA)
    reserva = reservar(c, PRESTACION_LIMPIEZA, slot["inicio"])

    assert reserva.get("sena") is None
    assert reserva["estado"] == "PENDIENTE"


def test_webhook_sin_secreto_es_fail_closed() -> None:
    c = client()

    response = c.post("/api/webhooks/mercadopago", json={})
    assert response.status_code == 503, response.text
    assert response.json()["codigo"] == "WEBHOOK_NO_CONFIGURADO"


def test_health_y_turnos_siguen_montados() -> None:
    c = client()

    assert c.get("/api/health").status_code == 200
    assert c.get("/api/turnos", headers=actor()).status_code == 200
    assert c.get("/api/publico/demo/catalogo").status_code == 200
