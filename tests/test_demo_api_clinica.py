"""HTTP tests for the C-08/C-09 demo wiring.

Cada test construye su propia app: el composition root es en memoria y el estado
no se comparte entre tests. Todos los datos son ficticios (RN-GL-03).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_PACIENTE_1,
    DEMO_PACIENTE_2,
    DEMO_TENANT_ID,
    DEMO_USER_ID,
    PRECIO_CONSULTA_CENTAVOS,
    PRESTACION_CONSULTA,
    PROFESIONAL_DEMO_1,
)

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(rol: str = "RECEPCION", user_id: str = DEMO_USER_ID) -> dict[str, str]:
    return {"X-Tenant-Id": DEMO_TENANT_ID, "X-User-Id": user_id, "X-Rol": rol}


def ahora() -> str:
    return datetime.now(UTC).isoformat()


def registrar_consentimiento(c: TestClient, paciente_id: str = DEMO_PACIENTE_1) -> None:
    response = c.post(
        "/api/consentimientos",
        headers=actor(),
        json={"paciente_id": paciente_id, "timestamp": ahora(), "canal": "mostrador"},
    )
    assert response.status_code == 201, response.text


# ---------------------------------------------------------------------------
# C-08 — ficha clínica
# ---------------------------------------------------------------------------


def test_ficha_sin_consentimiento_da_409_y_con_consentimiento_se_crea() -> None:
    c = client()

    sin_consentimiento = c.post(f"/api/pacientes/{DEMO_PACIENTE_1}/ficha", headers=actor())
    assert sin_consentimiento.status_code == 409, sin_consentimiento.text

    registrar_consentimiento(c, DEMO_PACIENTE_1)

    creada = c.post(f"/api/pacientes/{DEMO_PACIENTE_1}/ficha", headers=actor())
    assert creada.status_code == 201, creada.text
    assert creada.json()["paciente_id"] == DEMO_PACIENTE_1

    obtenida = c.get(f"/api/pacientes/{DEMO_PACIENTE_1}/ficha", headers=actor())
    assert obtenida.status_code == 200, obtenida.text
    assert obtenida.json()["id"] == creada.json()["id"]


def test_evolucion_clinica_se_registra_y_se_lista() -> None:
    c = client()
    registrar_consentimiento(c, DEMO_PACIENTE_1)

    alta = c.post(
        "/api/evoluciones",
        headers=actor(rol="ADMIN"),
        json={
            "paciente_id": DEMO_PACIENTE_1,
            "profesional_id": PROFESIONAL_DEMO_1,
            "fecha": ahora(),
            "texto": "Control de rutina sin hallazgos.",
        },
    )
    assert alta.status_code == 201, alta.text

    listado = c.get(
        "/api/evoluciones",
        headers=actor(rol="ADMIN"),
        params={"paciente_id": DEMO_PACIENTE_1},
    )
    assert listado.status_code == 200, listado.text
    assert [e["texto"] for e in listado.json()] == ["Control de rutina sin hallazgos."]


# ---------------------------------------------------------------------------
# C-09 — odontograma
# ---------------------------------------------------------------------------


def test_odontograma_registra_hallazgo_y_lo_lista() -> None:
    c = client()
    registrar_consentimiento(c, DEMO_PACIENTE_1)

    alta = c.post(
        "/api/odontograma",
        headers=actor(rol="ADMIN"),
        json={
            "paciente_id": DEMO_PACIENTE_1,
            "pieza_fdi": 36,
            "superficie": "OCLUSAL",
            "hallazgo": "CARIES",
            "fecha": ahora(),
            "profesional_id": PROFESIONAL_DEMO_1,
        },
    )
    assert alta.status_code == 201, alta.text
    assert alta.json()["pieza_fdi"] == 36

    listado = c.get(
        "/api/odontograma",
        headers=actor(rol="ADMIN"),
        params={"paciente_id": DEMO_PACIENTE_1},
    )
    assert listado.status_code == 200, listado.text
    assert [h["hallazgo"] for h in listado.json()] == ["CARIES"]


def test_odontograma_rechaza_pieza_fdi_invalida() -> None:
    c = client()
    registrar_consentimiento(c, DEMO_PACIENTE_1)

    response = c.post(
        "/api/odontograma",
        headers=actor(rol="ADMIN"),
        json={
            "paciente_id": DEMO_PACIENTE_1,
            "pieza_fdi": 99,
            "hallazgo": "CARIES",
            "fecha": ahora(),
            "profesional_id": PROFESIONAL_DEMO_1,
        },
    )
    assert response.status_code == 422, response.text
    assert (
        c.get(
            "/api/odontograma",
            headers=actor(rol="ADMIN"),
            params={"paciente_id": DEMO_PACIENTE_1},
        ).json()
        == []
    )


# ---------------------------------------------------------------------------
# C-09 — presupuesto
# ---------------------------------------------------------------------------


def test_presupuesto_crea_linea_al_precio_base_y_emite() -> None:
    c = client()

    creado = c.post("/api/presupuestos", headers=actor(), json={"paciente_id": DEMO_PACIENTE_1})
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]
    assert creado.json()["estado"] == "BORRADOR"

    linea = c.post(
        f"/api/presupuestos/{presupuesto_id}/lineas",
        headers=actor(),
        json={"prestacion_id": PRESTACION_CONSULTA},
    )
    assert linea.status_code == 201, linea.text
    assert linea.json()["monto"] == PRECIO_CONSULTA_CENTAVOS
    assert linea.json()["a_cargo_paciente"] == PRECIO_CONSULTA_CENTAVOS

    emitido = c.post(
        f"/api/presupuestos/{presupuesto_id}/emitir",
        headers=actor(),
        json={"vence_en": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    )
    assert emitido.status_code == 200, emitido.text
    assert emitido.json()["estado"] == "VIGENTE"

    listado = c.get(
        "/api/presupuestos", headers=actor(), params={"paciente_id": DEMO_PACIENTE_1}
    )
    assert listado.status_code == 200, listado.text
    assert len(listado.json()) == 1
    assert len(listado.json()[0]["lineas"]) == 1


def test_presupuesto_sin_lineas_no_se_emite() -> None:
    c = client()
    creado = c.post("/api/presupuestos", headers=actor(), json={"paciente_id": DEMO_PACIENTE_2})
    assert creado.status_code == 201, creado.text

    emitido = c.post(
        f"/api/presupuestos/{creado.json()['id']}/emitir",
        headers=actor(),
        json={"vence_en": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    )
    assert emitido.status_code == 409, emitido.text
    assert (
        c.get(f"/api/presupuestos/{creado.json()['id']}", headers=actor()).json()["estado"]
        == "BORRADOR"
    )


def test_los_dominios_previos_siguen_montados() -> None:
    c = client()

    assert c.get("/api/health").status_code == 200
    assert c.get("/api/publico/demo/catalogo").status_code == 200
    assert c.get("/api/turnos", headers=actor()).status_code == 200
