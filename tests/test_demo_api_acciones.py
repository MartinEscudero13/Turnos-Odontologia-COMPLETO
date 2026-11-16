"""HTTP tests de las acciones internas que consume el SPA (C-05/C-09/C-10/C-12/C-14/C-15).

Cada test crea su propia app: el composition root es en memoria y el estado no se
comparte. Datos ficticios (RN-GL-03).
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.app import create_app
from app.core.settings import Settings
from app.demo import (
    DEMO_PACIENTE_1,
    DEMO_TENANT_ID,
    DEMO_USER_ID,
    PRESTACION_CONSULTA,
    PROFESIONAL_DEMO_1,
    PROFESIONAL_DEMO_2,
    SILLON_DEMO_1,
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


def crear_turno(c: TestClient, *, dias: int = 3) -> str:
    inicio = (datetime.now(UTC) + timedelta(days=dias)).isoformat()
    response = c.post(
        "/api/turnos",
        headers=actor(),
        json={
            "profesional_id": PROFESIONAL_DEMO_1,
            "sillon_id": SILLON_DEMO_1,
            "paciente_id": DEMO_PACIENTE_1,
            "prestacion_id": PRESTACION_CONSULTA,
            "duracion_min": 30,
            "inicio": inicio,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def presupuesto_emitido(c: TestClient) -> tuple[str, str]:
    """Devuelve (presupuesto_id, linea_id) de un presupuesto vigente."""
    consentimiento = c.post(
        "/api/consentimientos",
        headers=actor(),
        json={
            "paciente_id": DEMO_PACIENTE_1,
            "timestamp": datetime.now(UTC).isoformat(),
            "canal": "mostrador",
        },
    )
    assert consentimiento.status_code == 201, consentimiento.text
    creado = c.post("/api/presupuestos", headers=actor(), json={"paciente_id": DEMO_PACIENTE_1})
    assert creado.status_code == 201, creado.text
    presupuesto_id = creado.json()["id"]
    linea = c.post(
        f"/api/presupuestos/{presupuesto_id}/lineas",
        headers=actor(),
        json={"prestacion_id": PRESTACION_CONSULTA},
    )
    assert linea.status_code == 201, linea.text
    emitido = c.post(
        f"/api/presupuestos/{presupuesto_id}/emitir",
        headers=actor(),
        json={"vence_en": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    )
    assert emitido.status_code == 200, emitido.text
    return presupuesto_id, linea.json()["id"]


# ---------------------------------------------------------------------------
# C-05 — agenda
# ---------------------------------------------------------------------------


def test_confirmar_y_marcar_presente() -> None:
    c = client()
    turno_id = crear_turno(c)

    confirmado = c.post(f"/api/turnos/{turno_id}/confirmar", headers=actor())
    assert confirmado.status_code == 200, confirmado.text
    assert confirmado.json()["estado"] == "CONFIRMADO"

    presente = c.post(f"/api/turnos/{turno_id}/presente", headers=actor())
    assert presente.status_code == 200, presente.text
    assert presente.json()["estado"] == "PRESENTE"


def test_marcar_ausente_desde_confirmado() -> None:
    c = client()
    turno_id = crear_turno(c)
    c.post(f"/api/turnos/{turno_id}/confirmar", headers=actor())

    ausente = c.post(f"/api/turnos/{turno_id}/ausente", headers=actor())

    assert ausente.status_code == 200, ausente.text
    assert ausente.json()["estado"] == "AUSENTE"


def test_no_se_marca_presente_sin_confirmar() -> None:
    c = client()
    turno_id = crear_turno(c)

    response = c.post(f"/api/turnos/{turno_id}/presente", headers=actor())

    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# C-09 → C-10 — aceptación, pendiente y cobro
# ---------------------------------------------------------------------------


def test_aceptar_presupuesto_deja_pendiente_y_cobrarlo_lo_resuelve() -> None:
    c = client()
    presupuesto_id, linea_id = presupuesto_emitido(c)

    decision = c.post(
        f"/api/presupuestos/{presupuesto_id}/aceptar",
        headers=actor(),
        json={"linea_id": linea_id, "acepta": True, "canal": "mostrador", "medio": None},
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["acepta"] is True

    pendientes = c.get("/api/caja/pendientes", headers=actor())
    assert pendientes.status_code == 200, pendientes.text
    assert len(pendientes.json()) == 1
    pendiente_id = pendientes.json()[0]["id"]

    cobro = c.post(
        f"/api/caja/pendientes/{pendiente_id}/cobrar",
        headers=actor(),
        json={"medio": "EFECTIVO"},
    )
    assert cobro.status_code == 201, cobro.text
    assert cobro.json()["movimiento"]["monto"] > 0

    resueltos = c.get("/api/caja/pendientes", headers=actor()).json()
    assert resueltos[0]["id"] == pendiente_id
    assert resueltos[0]["movimiento_id"] is not None
    assert resueltos[0]["resuelto_en"] is not None


def test_anular_movimiento_exige_motivo_y_lo_marca() -> None:
    c = client()
    hoy = datetime.now(UTC).date().isoformat()
    registrado = c.post(
        "/api/caja/movimientos",
        headers=actor(),
        json={"monto": 5000, "medio": "EFECTIVO", "tipo": "INGRESO", "fecha": hoy},
    )
    assert registrado.status_code == 201, registrado.text
    movimiento_id = registrado.json()["id"]

    sin_motivo = c.post(
        f"/api/caja/movimientos/{movimiento_id}/anular",
        headers=actor("ADMIN"),
        json={"motivo": ""},
    )
    assert sin_motivo.status_code == 422, sin_motivo.text

    anulado = c.post(
        f"/api/caja/movimientos/{movimiento_id}/anular",
        headers=actor("ADMIN"),
        json={"motivo": "Error de carga"},
    )
    assert anulado.status_code == 200, anulado.text
    assert anulado.json()["anulado"] is True


def test_reporte_y_cierres_listan_por_rango() -> None:
    c = client()
    hoy = datetime.now(UTC).date()
    desde = (hoy - timedelta(days=7)).isoformat()
    hasta = hoy.isoformat()
    c.post(
        "/api/caja/movimientos",
        headers=actor(),
        json={"monto": 7000, "medio": "TRANSFERENCIA", "tipo": "INGRESO", "fecha": hasta},
    )

    reporte = c.get(
        "/api/caja/reportes", headers=actor(), params={"desde": desde, "hasta": hasta}
    )
    assert reporte.status_code == 200, reporte.text
    assert reporte.json()["totales"]["transferencia"] == 7000
    assert c.get(
        "/api/caja/cierres", headers=actor(), params={"desde": desde, "hasta": hasta}
    ).status_code == 200


# ---------------------------------------------------------------------------
# C-12 / C-14 / C-15 — toggles y desconexión
# ---------------------------------------------------------------------------


def test_obra_social_se_activa_y_desactiva() -> None:
    c = client()
    creada = c.post(
        "/api/obras-sociales", headers=actor("ADMIN"), json={"nombre": "OS Demo Toggle"}
    )
    assert creada.status_code == 201, creada.text
    obra_id = creada.json()["id"]

    baja = c.patch(
        f"/api/obras-sociales/{obra_id}", headers=actor("ADMIN"), json={"activa": False}
    )
    assert baja.status_code == 200, baja.text
    assert baja.json()["activa"] is False

    alta = c.patch(
        f"/api/obras-sociales/{obra_id}", headers=actor("ADMIN"), json={"activa": True}
    )
    assert alta.status_code == 200, alta.text
    assert alta.json()["activa"] is True


def test_calendario_conecta_y_desconecta() -> None:
    c = client()
    conectado = c.post(
        "/api/calendar/oauth",
        headers=actor("ADMIN"),
        json={
            "profesional_id": PROFESIONAL_DEMO_2,
            "gcal_calendar_id": "demo-toggle@example.test",
            "oauth_ref": "demo-ref",
        },
    )
    assert conectado.status_code == 201, conectado.text
    link_id = conectado.json()["id"]

    desconectado = c.delete(f"/api/calendar/links/{link_id}", headers=actor("ADMIN"))

    assert desconectado.status_code == 200, desconectado.text
    assert desconectado.json()["estado"] == "DESCONECTADO"


def test_usuario_se_activa_y_desactiva() -> None:
    c = client()
    creado = c.post(
        "/api/tenant/usuarios",
        headers=actor("ADMIN"),
        json={
            "nombre": "Demo Toggle",
            "email": "toggle@demo.test",
            "password": "password-segura",
            "rol": "RECEPCION",
        },
    )
    assert creado.status_code == 201, creado.text
    usuario_id = creado.json()["id"]

    baja = c.patch(
        f"/api/tenant/usuarios/{usuario_id}", headers=actor("ADMIN"), json={"activo": False}
    )
    assert baja.status_code == 200, baja.text
    assert baja.json()["activo"] is False

    alta = c.patch(
        f"/api/tenant/usuarios/{usuario_id}", headers=actor("ADMIN"), json={"activo": True}
    )
    assert alta.status_code == 200, alta.text
    assert alta.json()["activo"] is True
