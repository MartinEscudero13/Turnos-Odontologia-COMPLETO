"""HTTP tests de C-15 en la demo (admin, exportación y KPIs)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import DEMO_ADMIN_ID, DEMO_TENANT_ID, DEMO_USER_ID

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(
    rol: str = "ADMIN",
    user_id: str = DEMO_ADMIN_ID,
) -> dict[str, str]:
    return {"X-Tenant-Id": DEMO_TENANT_ID, "X-User-Id": user_id, "X-Rol": rol}


def test_config_get_y_update_parcial() -> None:
    c = client()

    inicial = c.get("/api/tenant/config", headers=actor())
    assert inicial.status_code == 200, inicial.text
    assert inicial.json()["anticipacion_cancelacion_h"] == 24

    actualizada = c.put(
        "/api/tenant/config",
        headers=actor(),
        json={"anticipacion_cancelacion_h": 48, "recordatorios_habilitados": True},
    )
    assert actualizada.status_code == 200, actualizada.text
    assert actualizada.json()["anticipacion_cancelacion_h"] == 48
    assert actualizada.json()["recordatorios_habilitados"] is True
    assert actualizada.json()["sena_modo"] == "PORCENTAJE"


def test_config_clave_desconocida_es_422() -> None:
    c = client()

    response = c.put(
        "/api/tenant/config",
        headers=actor(),
        json={"descuento_secreto": 10},
    )
    assert response.status_code == 422, response.text
    assert (
        c.get("/api/tenant/config", headers=actor()).json()["anticipacion_cancelacion_h"] == 24
    )


def test_usuarios_listar_crear_y_duplicado() -> None:
    c = client()

    listado = c.get("/api/tenant/usuarios", headers=actor())
    assert listado.status_code == 200, listado.text
    assert [u["email"] for u in listado.json()] == [
        "admin@demo.test",
        "recepcion@demo.test",
    ]
    assert all("password_hash" not in u for u in listado.json())

    creado = c.post(
        "/api/tenant/usuarios",
        headers=actor(),
        json={
            "nombre": "Odontólogo Nuevo",
            "email": "Odonto@Demo.Test",
            "password": "secreto-123",
            "rol": "ODONTOLOGO",
        },
    )
    assert creado.status_code == 201, creado.text
    assert creado.json()["email"] == "odonto@demo.test"

    duplicado = c.post(
        "/api/tenant/usuarios",
        headers=actor(),
        json={
            "nombre": "Otro",
            "email": "odonto@demo.test",
            "password": "secreto-123",
            "rol": "ADMIN",
        },
    )
    assert duplicado.status_code == 409, duplicado.text
    assert duplicado.json()["codigo"] == "USUARIO_DUPLICADO"


def test_admin_no_se_desactiva_a_si_mismo() -> None:
    c = client()

    response = c.patch(
        f"/api/tenant/usuarios/{DEMO_ADMIN_ID}",
        headers=actor(),
        json={"activo": False},
    )
    assert response.status_code == 409, response.text
    assert response.json()["codigo"] == "AUTO_DESACTIVACION"


def test_exportacion_json_y_csv_sin_secretos() -> None:
    c = client()

    json_out = c.get("/api/exportacion", headers=actor(), params={"formato": "json"})
    assert json_out.status_code == 200, json_out.text
    assert json_out.headers["content-type"].startswith("application/json")
    assert json_out.json()["secciones"]["pacientes"] == 2
    assert "oauth_ref" not in json_out.text
    assert "password_hash" not in json_out.text

    csv_out = c.get("/api/exportacion", headers=actor(), params={"formato": "csv"})
    assert csv_out.status_code == 200, csv_out.text
    assert csv_out.headers["content-type"].startswith("text/csv")
    assert csv_out.text.splitlines()[0] == "seccion,id,json"
    assert "pacientes," in csv_out.text


def test_kpis_base() -> None:
    c = client()

    response = c.get(
        "/api/reportes/kpis",
        headers=actor(),
        params={"desde": "2026-11-01", "hasta": "2026-12-01"},
    )
    assert response.status_code == 200, response.text
    cuerpo = response.json()
    assert cuerpo["total_turnos"] == 4
    assert cuerpo["ausentismo_pct"] == 33.33
    assert cuerpo["reservas_online_pct"] == 25.0
    assert cuerpo["reasignados_2h"] == 1
    assert cuerpo["ocupacion_pct"] == 37.5


def test_kpis_periodo_invalido_es_422() -> None:
    c = client()

    response = c.get(
        "/api/reportes/kpis",
        headers=actor(),
        params={"desde": "2026-12-01", "hasta": "2026-11-01"},
    )
    assert response.status_code == 422, response.text


def test_rbac_admin() -> None:
    c = client()

    assert c.get("/api/tenant/config", headers=actor("PACIENTE")).status_code == 401
    assert c.get("/api/tenant/config", headers=actor("ODONTOLOGO")).status_code == 403
    assert c.get("/api/exportacion", headers=actor("RECEPCION")).status_code == 403
    assert (
        c.get(
            "/api/reportes/kpis",
            headers=actor("RECEPCION", DEMO_USER_ID),
            params={"desde": "2026-11-01", "hasta": "2026-12-01"},
        ).status_code
        == 200
    )
