"""Task 5.7 — contrato de rutas públicas de pago (D13, F-30).

`GET .../senas/{token}` y `POST .../senas/{token}/preferencia` no exigen sesión
ni `verificacion_id`; la preferencia responde `200` (ya existe), `201` (creada) o
`202` (backoff) y ambas comparten el rate-limit de C-06 (`429`). No existe un
endpoint de pago directo del lado del servidor: el paciente paga con el link de
Mercado Pago.
"""
from __future__ import annotations

from datetime import timedelta

from _senas_helpers import AHORA, HarnessSenas


def _url(token: str, tenant: str = "t1") -> str:
    return f"/api/publico/{tenant}/senas/{token}"


def test_contrato_de_rutas() -> None:
    h = HarnessSenas(rate_limit_max=1000)
    h.configurar()
    creada = h.crear()
    token = creada.token_sena

    consulta = h.client.get(_url(token))
    assert consulta.status_code == 200
    assert consulta.json()["sena_id"] == creada.sena.id

    # La preferencia ya existe ⇒ misma preferencia, 200 (no crea otra).
    existente = h.client.post(f"{_url(token)}/preferencia")
    assert existente.status_code == 200
    assert existente.json()["init_point"] == creada.sena.mp_init_point
    assert len(h.pasarela.preferencias) == 1

    # Seña con preferencia FALLIDA y backoff cumplido ⇒ 201 con link nuevo.
    caida = HarnessSenas(rate_limit_max=1000)
    caida.configurar()
    caida.pasarela.fallar()
    creada_caida = caida.crear()
    caida.pasarela.recuperar()
    assert creada_caida.sena.preferencia_estado == "FALLIDA"
    caida.fijar_ahora(AHORA + timedelta(minutes=3))
    creada_nueva = caida.client.post(f"{_url(creada_caida.token_sena)}/preferencia")
    assert creada_nueva.status_code == 201
    assert creada_nueva.json()["init_point"]
    assert creada_nueva.json()["preferencia_estado"] == "CREADA"

    # Backoff vigente ⇒ 202 con `reintentar_en` y sin llamar a la pasarela.
    caida.senas.actualizar(
        tenant_id=creada_caida.sena.tenant_id,
        sena_id=creada_caida.sena.id,
        campos={
            "preferencia_estado": "FALLIDA",
            "intentos_preferencia": 3,
            "proximo_reintento_at": AHORA + timedelta(minutes=8),
            "mp_preference_id": None,
            "mp_init_point": None,
        },
    )
    llamadas = len(caida.pasarela.preferencias)
    backoff = caida.client.post(f"{_url(creada_caida.token_sena)}/preferencia")
    assert backoff.status_code == 202
    assert backoff.json()["reintentar_en"]
    assert len(caida.pasarela.preferencias) == llamadas

    # Token inexistente y token de otro tenant ⇒ 404 uniforme, en GET y POST.
    assert h.client.get(_url("NO-EXISTE")).status_code == 404
    assert h.client.post(f"{_url('NO-EXISTE')}/preferencia").status_code == 404
    ajeno = h.client.get(_url(token, tenant="t2"))
    assert ajeno.status_code == 404
    assert h.client.post(f"{_url(token, tenant='t2')}/preferencia").status_code == 404

    # Sin verificación previa: la superficie pública no la exige en ningún paso.
    assert "verificacion_id" not in consulta.request.url.query.decode()

    # Rate-limit de C-06: agotado ⇒ 429, sin datos ni llamada a la pasarela.
    limitado = HarnessSenas(rate_limit_max=1)
    limitado.configurar()
    limitada = limitado.crear()
    assert limitado.client.get(_url(limitada.token_sena)).status_code == 200
    bloqueada = limitado.client.get(_url(limitada.token_sena))
    assert bloqueada.status_code == 429
    assert bloqueada.json()["detalle"]
    preferencias_antes = len(limitado.pasarela.preferencias)
    assert limitado.client.post(f"{_url(limitada.token_sena)}/preferencia").status_code == 429
    assert len(limitado.pasarela.preferencias) == preferencias_antes

    # No hay pago server-side: el link es de Mercado Pago.
    assert h.client.post(f"{_url(token)}/pagar").status_code in (404, 405)
    assert h.client.get(f"{_url(token)}/pagar").status_code in (404, 405)
