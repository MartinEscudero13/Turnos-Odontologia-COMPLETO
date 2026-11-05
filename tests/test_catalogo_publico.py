"""Tasks 0.1–0.4 — catálogo público (enabler backend de F-02). RED primero.

Todo dato es ficticio (regla dura: NUNCA datos reales de pacientes). El catálogo
es de solo lectura, scoped por `{tokenTenant}` y con allow-list estricta: no
expone `tenant_id`, precios, pacientes ni horarios.
"""
from __future__ import annotations

from _reserva_helpers import T3, Harness
from conftest import T1, T2

from app.reservas.puertos import Prestacion, Profesional, TenantMemoria

T4 = "a0000000-0000-4000-8000-000000000004"  # activo, sin catálogo sembrado

PREST30 = "PREST-30"
PREST45 = "PREST-45"
PREST_AJENA = "PREST-60"

P1 = "P1"
P2 = "P2"
P_INACTIVO = "P-INACTIVO"
P_AJENO = "P-AJENO"


def _harness() -> Harness:
    """Harness con t1/t2 activos con datos, t3 inactivo y t4 activo vacío."""
    return Harness(
        tenants=TenantMemoria(
            {
                "t1": (T1, True),
                "t2": (T2, True),
                "t3": (T3, False),
                "t4": (T4, True),
            }
        )
    )


def _sembrar(h: Harness) -> None:
    c = h.catalogo
    # T1: dos prestaciones y dos profesionales activos + uno inactivo.
    c.agregar_prestacion(Prestacion(id=PREST45, tenant_id=T1, duracion_min=45, nombre="Limpieza"))
    c.agregar_prestacion(Prestacion(id=PREST30, tenant_id=T1, duracion_min=30, nombre="Consulta"))
    c.agregar_profesional(Profesional(id=P2, tenant_id=T1, nombre="Dr. Ejemplo"))
    c.agregar_profesional(Profesional(id=P1, tenant_id=T1, nombre="Dra. Demo"))
    c.agregar_profesional(
        Profesional(id=P_INACTIVO, tenant_id=T1, activo=False, nombre="Dr. Inactivo")
    )
    # T2: datos distintos que nunca deben filtrarse en el catálogo de T1.
    c.agregar_prestacion(Prestacion(id=PREST_AJENA, tenant_id=T2, duracion_min=60, nombre="Blanqueamiento"))
    c.agregar_profesional(Profesional(id=P_AJENO, tenant_id=T2, nombre="Dr. Ajeno"))


def _get(h: Harness, token_tenant: str = "t1"):
    return h.client.get(f"/api/publico/{token_tenant}/catalogo")


def test_catalogo_tenant_devuelve_solo_sus_prestaciones_y_profesionales():
    h = _harness()
    _sembrar(h)

    r = _get(h)

    assert r.status_code == 200, r.text
    body = r.json()
    assert [p["id"] for p in body["prestaciones"]] == [PREST30, PREST45]
    assert [(p["nombre"], p["duracion_min"]) for p in body["prestaciones"]] == [
        ("Consulta", 30),
        ("Limpieza", 45),
    ]
    ids_prof = {p["id"] for p in body["profesionales"]}
    assert ids_prof == {P1, P2}
    nombres_prof = {p["nombre"] for p in body["profesionales"]}
    assert nombres_prof == {"Dra. Demo", "Dr. Ejemplo"}
    # Aislamiento multi-tenant: nada de T2.
    assert PREST_AJENA not in {p["id"] for p in body["prestaciones"]}
    assert P_AJENO not in ids_prof


def test_catalogo_no_expone_phi_ni_claves_internas():
    h = _harness()
    _sembrar(h)

    r = _get(h)

    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"prestaciones", "profesionales"}
    for prestacion in body["prestaciones"]:
        assert set(prestacion) == {"id", "nombre", "duracion_min"}
    for profesional in body["profesionales"]:
        assert set(profesional) == {"id", "nombre"}
    serializado = r.text
    for clave_prohibida in (
        "tenant_id",
        "precio_base",
        "paciente_id",
        "telefono",
        "horario",
        "sillon",
    ):
        assert clave_prohibida not in serializado


def test_catalogo_token_tenant_inexistente_404():
    h = _harness()
    _sembrar(h)

    r = h.client.get("/api/publico/NO-EXISTE/catalogo")

    assert r.status_code == 404, r.text
    assert r.json() == {"detalle": "recurso no encontrado", "alternativas": []}
    # Tenant inactivo se comporta igual que inexistente (404 uniforme).
    r_inactivo = _get(h, "t3")
    assert r_inactivo.status_code == 404, r_inactivo.text
    assert r_inactivo.json() == r.json()


def test_catalogo_tenant_sin_datos_devuelve_listas_vacias():
    h = _harness()
    _sembrar(h)

    r = _get(h, "t4")

    assert r.status_code == 200, r.text
    assert r.json() == {"prestaciones": [], "profesionales": []}


def test_catalogo_excluye_profesional_inactivo_y_no_inventa_profesionales():
    h = _harness()
    _sembrar(h)

    body = _get(h).json()

    assert P_INACTIVO not in {p["id"] for p in body["profesionales"]}
    r_vacio = _get(h, "t4")
    assert r_vacio.json()["profesionales"] == []
