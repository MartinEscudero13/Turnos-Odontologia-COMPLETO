"""HTTP tests de C-12 en la demo (obras sociales, cobertura y liquidación)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_PACIENTE_1,
    DEMO_PACIENTE_2,
    DEMO_TENANT_ID,
    DEMO_USER_ID,
    PRESTACION_CONSULTA,
    demo_periodo_actual,
)

SETTINGS = Settings(
    APP_ENV="test",
    DATABASE_URL="postgresql+psycopg://turnos:pwd@db:5432/turnos",
    REDIS_URL="redis://localhost:6379/0",
    JWT_SECRET="test-secret-that-is-long-enough-for-local-dev-1234567890",
    APP_URL="http://localhost:5173",
)

OTRO_TENANT = "b0000000-0000-4000-8000-000000000099"


def client() -> TestClient:
    return TestClient(create_app(SETTINGS))


def actor(
    rol: str = "ADMIN", tenant: str = DEMO_TENANT_ID, user_id: str = DEMO_USER_ID
) -> dict[str, str]:
    return {"X-Tenant-Id": tenant, "X-User-Id": user_id, "X-Rol": rol}


def obra_social_id(c: TestClient, nombre: str = "OS Demo Norte") -> str:
    obras = c.get("/api/obras-sociales", headers=actor()).json()
    return next(obra["id"] for obra in obras if obra["nombre"] == nombre)


# ---------------------------------------------------------------------------
# Catálogo y coberturas
# ---------------------------------------------------------------------------


def test_catalogo_inicial_y_creacion() -> None:
    c = client()

    listado = c.get("/api/obras-sociales", headers=actor())
    assert listado.status_code == 200, listado.text
    assert [obra["nombre"] for obra in listado.json()] == [
        "OS Demo Centro",
        "OS Demo Norte",
        "OS Demo Sur",
    ]

    creada = c.post(
        "/api/obras-sociales", headers=actor(), json={"nombre": "OS Demo Nuevo"}
    )
    assert creada.status_code == 201, creada.text
    assert creada.json()["activa"] is True

    duplicada = c.post(
        "/api/obras-sociales", headers=actor(), json={"nombre": "OS Demo Nuevo"}
    )
    assert duplicada.status_code == 409, duplicada.text
    assert duplicada.json()["codigo"] == "OBRA_SOCIAL_DUPLICADA"


def test_configurar_cobertura_y_preview() -> None:
    c = client()
    os_norte = obra_social_id(c)

    cobertura = c.put(
        "/api/coberturas",
        headers=actor(),
        json={
            "obra_social_id": os_norte,
            "prestacion_id": PRESTACION_CONSULTA,
            "modo": "PORCENTAJE",
            "valor": 60,
            "tope_centavos": 4500,
        },
    )
    assert cobertura.status_code == 200, cobertura.text
    assert cobertura.json()["validada_en_vivo"] is False

    preview = c.get(
        "/api/coberturas/preview",
        headers=actor(),
        params={"paciente_id": DEMO_PACIENTE_1, "prestacion_id": PRESTACION_CONSULTA},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json() == {
        "precio_base_centavos": 10000,
        "cobertura_os": 4500,
        "a_cargo_paciente": 5500,
        "origen": "CONFIGURADA",
        "validada_en_vivo": False,
    }


def test_preview_usa_la_os_del_paciente() -> None:
    c = client()

    preview = c.get(
        "/api/coberturas/preview",
        headers=actor(),
        params={"paciente_id": DEMO_PACIENTE_2, "prestacion_id": PRESTACION_CONSULTA},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cobertura_os"] == 3000
    assert preview.json()["a_cargo_paciente"] == 7000


def test_cobertura_invalida_es_422() -> None:
    c = client()
    os_norte = obra_social_id(c)

    response = c.put(
        "/api/coberturas",
        headers=actor(),
        json={
            "obra_social_id": os_norte,
            "prestacion_id": PRESTACION_CONSULTA,
            "modo": "PORCENTAJE",
            "valor": 150,
        },
    )
    assert response.status_code == 422, response.text
    assert c.get("/api/coberturas", headers=actor()).json()[0]["valor"] == 50


# ---------------------------------------------------------------------------
# Liquidación
# ---------------------------------------------------------------------------


def test_liquidacion_y_export_csv() -> None:
    c = client()
    os_norte = obra_social_id(c)
    desde, hasta = demo_periodo_actual()

    generada = c.post(
        "/api/liquidaciones",
        headers=actor(),
        json={
            "obra_social_id": os_norte,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
    assert generada.status_code == 201, generada.text
    cuerpo = generada.json()
    assert cuerpo["estado"] == "BORRADOR"
    assert cuerpo["total_centavos"] == 12000
    assert [linea["monto_centavos"] for linea in cuerpo["lineas"]] == [4000, 8000]

    exportado = c.get(
        f"/api/liquidaciones/{cuerpo['id']}/export.csv", headers=actor()
    )
    assert exportado.status_code == 200, exportado.text
    assert exportado.headers["content-type"].startswith("text/csv")
    lineas = exportado.text.strip().splitlines()
    assert lineas[0] == "turno_id,fecha,paciente_id,prestacion_id,monto_centavos"
    assert len(lineas) == 3

    cerrada = c.post(
        f"/api/liquidaciones/{cuerpo['id']}/cerrar", headers=actor()
    )
    assert cerrada.status_code == 200, cerrada.text
    assert cerrada.json()["estado"] == "CERRADA"

    reintento = c.post(
        "/api/liquidaciones",
        headers=actor(),
        json={
            "obra_social_id": os_norte,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
    assert reintento.status_code == 409, reintento.text
    assert reintento.json()["codigo"] == "LIQUIDACION_CERRADA"


def test_liquidacion_sin_turnos_es_409() -> None:
    c = client()
    nueva = c.post(
        "/api/obras-sociales", headers=actor(), json={"nombre": "OS Demo Vacía"}
    ).json()
    desde, hasta = demo_periodo_actual()

    response = c.post(
        "/api/liquidaciones",
        headers=actor(),
        json={
            "obra_social_id": nueva["id"],
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
    assert response.status_code == 409, response.text
    assert response.json()["codigo"] == "SIN_TURNOS_ELEGIBLES"


def test_liquidacion_de_otra_os_no_mezcla() -> None:
    c = client()
    os_sur = obra_social_id(c, "OS Demo Sur")
    desde, hasta = demo_periodo_actual()

    generada = c.post(
        "/api/liquidaciones",
        headers=actor(),
        json={
            "obra_social_id": os_sur,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    )
    assert generada.status_code == 201, generada.text
    assert generada.json()["total_centavos"] == 3000
    assert len(generada.json()["lineas"]) == 1


# ---------------------------------------------------------------------------
# RBAC y aislamiento
# ---------------------------------------------------------------------------


def test_rbac_de_obras_sociales() -> None:
    c = client()

    assert (
        c.post(
            "/api/obras-sociales", headers=actor("RECEPCION"), json={"nombre": "OS X"}
        ).status_code
        == 403
    )
    assert c.get("/api/obras-sociales", headers=actor("ODONTOLOGO")).status_code == 403
    assert c.get("/api/obras-sociales", headers=actor("PACIENTE")).status_code == 401


def test_liquidacion_cross_tenant_es_404() -> None:
    c = client()
    os_norte = obra_social_id(c)
    desde, hasta = demo_periodo_actual()
    liquidacion = c.post(
        "/api/liquidaciones",
        headers=actor(),
        json={
            "obra_social_id": os_norte,
            "desde": desde.isoformat(),
            "hasta": hasta.isoformat(),
        },
    ).json()

    assert c.get("/api/obras-sociales", headers=actor(tenant=OTRO_TENANT)).json() == []
    ajeno = c.get(
        f"/api/liquidaciones/{liquidacion['id']}", headers=actor(tenant=OTRO_TENANT)
    )
    assert ajeno.status_code == 404, ajeno.text


def test_presupuesto_usa_la_cobertura_configurada() -> None:
    c = client()
    creado = c.post(
        "/api/presupuestos", headers=actor("RECEPCION"), json={"paciente_id": DEMO_PACIENTE_1}
    )
    assert creado.status_code == 201, creado.text

    linea = c.post(
        f"/api/presupuestos/{creado.json()['id']}/lineas",
        headers=actor("RECEPCION"),
        json={"prestacion_id": PRESTACION_CONSULTA},
    )
    assert linea.status_code == 201, linea.text
    assert linea.json()["monto"] == 10000
    assert linea.json()["cobertura_os"] == 4000
    assert linea.json()["a_cargo_paciente"] == 6000
