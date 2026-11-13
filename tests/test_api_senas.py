"""Tasks 11.1–11.5 y 11.15 — superficie interna de señas: RBAC y contrato.

Criterios (spec `senas` §RBAC y §Visibilidad de la seña en agenda, design D13):

- `ODONTOLOGO` lee (listado y detalle) pero **no** aplica ⇒ `403` sin movimientos;
- `RECEPCION` aplica (`200`) pero **no** devuelve (`403`);
- `ADMIN` aplica y devuelve, y la auditoría registra a U2 como actor;
- una identidad de paciente en una ruta interna ⇒ `401` (nunca `403`), sin
  exponer ni modificar nada;
- los payloads son estrictos (`extra="forbid"`): `tenant_id`,
  `paciente_nombre` o `monto_centavos` donde no corresponde ⇒ `422`;
- `GET /api/senas?desde=&hasta=` filtra por **`turno.inicio`** en
  `[desde, hasta)`, no por `creado_en` ni por `expira_at` (C11-OQ-10); sin
  parámetros usa el día operativo vigente;
- la **exportación de señas no existe** en C-11: nada de `/api/senas/export`.

Datos ficticios (RN-GL-03): T1, TUR-1/TUR-2, PACI-1, U1 (RECEPCION),
U2 (ADMIN), U3 (ODONTOLOGO), `monto=3000`, reloj `2026-11-13T09:00:00-03:00`.
"""
from __future__ import annotations

from _senas_helpers import (
    AHORA,
    PACI1,
    T1,
    TUR1,
    TUR2,
    U1,
    U2,
    U3,
    HarnessSenaAplicacion,
    d3,
)
from fastapi.testclient import TestClient

from app.caja.servicio import dia_operativo


def _headers(rol: str, user_id: str) -> dict[str, str]:
    return {"X-Tenant-Id": T1, "X-User-Id": user_id, "X-Rol": rol}


RECEP = _headers("RECEPCION", U1)
ADMIN = _headers("ADMIN", U2)
ODONTO = _headers("ODONTOLOGO", U3)
PACIENTE = _headers("PACIENTE", PACI1)

RANGO = {"desde": "2026-11-10", "hasta": "2026-11-30"}


def _client(h: HarnessSenaAplicacion) -> TestClient:
    return h.client_interno


# ---------------------------------------------------------------------------
# 11.1 — el odontólogo lee pero no aplica
# ---------------------------------------------------------------------------


def test_odontologo_lee_no_aplica() -> None:
    # GIVEN T1 con una seña ACREDITADA y el odontólogo U3.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN U3 lista, lee el detalle e intenta aplicarla.
    listado = client.get("/api/senas", params=RANGO, headers=ODONTO)
    detalle = client.get(f"/api/senas/{sena.id}", headers=ODONTO)
    aplicacion = client.post(
        f"/api/senas/{sena.id}/aplicar", json={}, headers=ODONTO
    )

    # THEN lee 200 y escribir es 403, sin movimiento ni cambio de estado.
    assert listado.status_code == 200, listado.text
    assert [s["sena_id"] for s in listado.json()] == [sena.id]
    assert detalle.status_code == 200, detalle.text
    assert detalle.json()["estado"] == "ACREDITADA"
    assert aplicacion.status_code == 403, aplicacion.text
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.movimientos.total(T1) == 0


# ---------------------------------------------------------------------------
# 11.2 — recepción aplica pero no devuelve
# ---------------------------------------------------------------------------


def test_recepcion_aplica_no_devuelve() -> None:
    # GIVEN T1 con dos señas ACREDITADAS y U1 de recepción.
    h = HarnessSenaAplicacion()
    a_aplicar = h.sembrar_sena(turno_id=TUR1, estado="ACREDITADA")
    a_devolver = h.sembrar_sena(turno_id=TUR2, estado="ACREDITADA")
    client = _client(h)

    # WHEN U1 aplica la primera e intenta devolver la segunda.
    aplicacion = client.post(
        f"/api/senas/{a_aplicar.id}/aplicar",
        json={"concepto": "TRATAMIENTO"},
        headers=RECEP,
    )
    devolucion = client.post(
        f"/api/senas/{a_devolver.id}/devolver",
        json={"motivo": "cancelación con aviso"},
        headers=RECEP,
    )

    # THEN aplica con 200 y devuelve 403: la seña sigue ACREDITADA.
    assert aplicacion.status_code == 200, aplicacion.text
    assert aplicacion.json()["estado"] == "APLICADA"
    assert devolucion.status_code == 403, devolucion.text
    assert h.sena(a_devolver).estado == "ACREDITADA"
    assert h.sena(a_devolver).devuelta_por is None


# ---------------------------------------------------------------------------
# 11.3 — ADMIN aplica y devuelve (ambas auditadas con U2)
# ---------------------------------------------------------------------------


def test_admin_aplica_y_devuelve() -> None:
    # GIVEN T1 con dos señas ACREDITADAS y U2 de ADMIN.
    h = HarnessSenaAplicacion()
    a_aplicar = h.sembrar_sena(turno_id=TUR1, estado="ACREDITADA")
    a_devolver = h.sembrar_sena(turno_id=TUR2, estado="ACREDITADA")
    client = _client(h)

    # WHEN U2 aplica una y devuelve la otra con motivo.
    aplicacion = client.post(
        f"/api/senas/{a_aplicar.id}/aplicar",
        json={"concepto": "TRATAMIENTO"},
        headers=ADMIN,
    )
    devolucion = client.post(
        f"/api/senas/{a_devolver.id}/devolver",
        json={"motivo": "cancelación con aviso"},
        headers=ADMIN,
    )

    # THEN la primera queda APLICADA y la segunda DEVUELTA con su obligación.
    assert aplicacion.status_code == 200, aplicacion.text
    assert aplicacion.json()["estado"] == "APLICADA"
    assert devolucion.status_code == 200, devolucion.text
    assert devolucion.json()["estado"] == "DEVUELTA"
    assert devolucion.json()["motivo_devolucion"] == "cancelación con aviso"
    assert devolucion.json()["devuelta_por"] == U2
    obligaciones = devolucion.json()["obligaciones"]
    assert [o["tipo"] for o in obligaciones] == ["REINTEGRO"]
    assert obligaciones[0]["monto_centavos"] == 3000

    # AND ambas transiciones llevan a U2 como actor en la auditoría.
    actores = {(entrada.accion, entrada.actor) for entrada in h.auditoria.entradas}
    assert ("SENA_APLICADA", U2) in actores
    assert ("SENA_DEVUELTA", U2) in actores


# ---------------------------------------------------------------------------
# 11.4 — identidad de paciente ⇒ 401 en todas las rutas internas
# ---------------------------------------------------------------------------


def test_paciente_401() -> None:
    # GIVEN T1 con una seña ACREDITADA y una petición con identidad de paciente.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN la identidad de paciente lista, lee, aplica y devuelve.
    respuestas = [
        client.get("/api/senas", params=RANGO, headers=PACIENTE),
        client.get(f"/api/senas/{sena.id}", headers=PACIENTE),
        client.post(f"/api/senas/{sena.id}/aplicar", json={}, headers=PACIENTE),
        client.post(
            f"/api/senas/{sena.id}/devolver",
            json={"motivo": "cancelación con aviso"},
            headers=PACIENTE,
        ),
    ]

    # THEN 401 (nunca 403) en las cuatro, sin exponer ni modificar nada.
    for respuesta in respuestas:
        assert respuesta.status_code == 401, respuesta.text
        assert sena.id not in respuesta.text
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.movimientos.total(T1) == 0
    assert h.auditoria.entradas == []


# ---------------------------------------------------------------------------
# 11.5 — el schema rechaza campos extra
# ---------------------------------------------------------------------------


def test_schema_rechaza_campos_extra() -> None:
    # GIVEN T1 con una seña ACREDITADA.
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN el payload intenta colar un campo que no corresponde.
    intentos = [
        (f"/api/senas/{sena.id}/aplicar", {"concepto": "TRATAMIENTO", "tenant_id": T1}),
        (
            f"/api/senas/{sena.id}/aplicar",
            {"concepto": "TRATAMIENTO", "paciente_nombre": "Paciente Demo"},
        ),
        (
            f"/api/senas/{sena.id}/aplicar",
            {"concepto": "TRATAMIENTO", "monto_centavos": 1},
        ),
        (f"/api/senas/{sena.id}/devolver", {"motivo": "con aviso", "tenant_id": T1}),
        (
            f"/api/senas/{sena.id}/devolver",
            {"motivo": "con aviso", "monto_centavos": 1},
        ),
        (f"/api/senas/{sena.id}/devolver", {"motivo": ""}),
    ]
    respuestas = [
        client.post(ruta, json=cuerpo, headers=RECEP) for ruta, cuerpo in intentos
    ]

    # THEN 422 y la seña no cambia: ningún campo ajeno se procesa.
    for respuesta in respuestas:
        assert respuesta.status_code == 422, respuesta.text
    assert h.sena(sena).estado == "ACREDITADA"
    assert h.movimientos.total(T1) == 0
    assert h.auditoria.entradas == []


# ---------------------------------------------------------------------------
# 11.15 — el filtro es por inicio del turno
# ---------------------------------------------------------------------------


def test_listado_por_inicio_del_turno() -> None:
    # GIVEN T1 con una seña para un turno del 2026-11-20, otra del 2026-12-01 y
    # una tercera para el día operativo vigente (2026-11-13). Las tres se
    # crearon antes del rango y vencen fuera de él.
    h = HarnessSenaAplicacion()
    noviembre = h.sembrar_sena(
        turno_id=TUR1, estado="ACREDITADA", turno_inicio=d3("2026-11-20")
    )
    diciembre = h.sembrar_sena(
        turno_id=TUR2, estado="PENDIENTE", turno_inicio=d3("2026-12-01")
    )
    assert diciembre.creado_en.date().isoformat() == "2026-11-10"
    assert noviembre.expira_at.date().isoformat() == "2026-11-14"
    hoy = h.sembrar_sena(
        turno_id="turno-hoy", estado="PENDIENTE", turno_inicio=AHORA
    )
    client = _client(h)

    # WHEN se pide el rango 2026-11-15 → 2026-11-30 (exclusivo).
    rango = client.get(
        "/api/senas",
        params={"desde": "2026-11-15", "hasta": "2026-11-30"},
        headers=RECEP,
    )

    # THEN devuelve sólo la seña cuyo `turno.inicio` cae en el rango.
    assert rango.status_code == 200, rango.text
    assert [s["sena_id"] for s in rango.json()] == [noviembre.id]
    assert rango.json()[0]["turno"]["inicio"].startswith("2026-11-20T10:00:00")

    # AND sin parámetros el rango por defecto es el día operativo vigente.
    assert dia_operativo(AHORA).isoformat() == "2026-11-13"
    por_defecto = client.get("/api/senas", headers=RECEP)
    assert por_defecto.status_code == 200, por_defecto.text
    assert [s["sena_id"] for s in por_defecto.json()] == [hoy.id]


def test_rango_invalido_422() -> None:
    # GIVEN T1 con una seña y U1 de recepción.
    h = HarnessSenaAplicacion()
    h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN el rango viene invertido o vacío.
    for params in (
        {"desde": "2026-11-30", "hasta": "2026-11-15"},
        {"desde": "2026-11-15", "hasta": "2026-11-15"},
    ):
        respuesta = client.get("/api/senas", params=params, headers=RECEP)
        # THEN 422: no se inventa una ventana.
        assert respuesta.status_code == 422, respuesta.text


# ---------------------------------------------------------------------------
# Extra (regla dura del change): la exportación de señas no existe
# ---------------------------------------------------------------------------

def test_exportacion_de_senas_no_existe() -> None:
    # GIVEN T1 con una seña y usuarios internos.
    h = HarnessSenaAplicacion()
    h.sembrar_sena(estado="ACREDITADA")
    client = _client(h)

    # WHEN cualquiera pide la exportación de señas (no existe en C-11).
    for headers in (RECEP, ADMIN, ODONTO):
        respuesta = client.get("/api/senas/export", headers=headers)
        # THEN 404/405, nunca 200.
        assert respuesta.status_code in (404, 405), respuesta.text
        assert respuesta.status_code != 200


# ---------------------------------------------------------------------------
# Contrato de la vista interna: sin PHI ni campos internos
# ---------------------------------------------------------------------------


def test_vista_interna_sin_phi() -> None:
    # GIVEN T1 con una seña de "Paciente Demo".
    h = HarnessSenaAplicacion()
    sena = h.sembrar_sena(estado="ACREDITADA", paciente_id="Paciente Demo")
    client = _client(h)

    # WHEN se lee el detalle y el listado.
    detalle = client.get(f"/api/senas/{sena.id}", headers=RECEP)
    listado = client.get("/api/senas", params=RANGO, headers=RECEP)

    # THEN la allow-list no trae nombre, paciente, tenant ni el token.
    assert detalle.status_code == 200, detalle.text
    for payload in (detalle.json(), listado.json()[0]):
        assert set(payload) == {
            "sena_id",
            "turno_id",
            "turno",
            "estado",
            "monto_centavos",
            "expira_at",
            "preferencia_estado",
            "politica",
            "obligaciones",
            "acreditada_en",
            "aplicada_en",
            "liberada_en",
            "devuelta_en",
            "motivo_liberacion",
            "motivo_devolucion",
            "concepto_aplicacion",
            "devuelta_por",
            "movimiento_caja_id",
            "creado_en",
        }
        assert "Paciente Demo" not in repr(payload)
        assert "paciente_id" not in payload
        assert "token" not in repr(payload).lower()
    assert "Paciente Demo" not in listado.text
