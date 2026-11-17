# Tasks — `c-17-proveedor-meta`

## 1. Adaptador

- [x] 1.1 `PasarelaMeta` con Graph API, Bearer token y normalización del `to`.
- [x] 1.2 `meta_desde_env()` y selección `meta → twilio → fake` en `demo.py`.

## 2. Webhook

- [x] 2.1 `GET /api/webhooks/whatsapp/meta` con `hub.verify_token`.
- [x] 2.2 `POST` con firma `X-Hub-Signature-256` y aplanado `eventos_meta`.
- [x] 2.3 Resolución de respuestas por `context.id` o por teléfono (`paciente_por_telefono` y
  `ultimo_por_paciente`); también aplica a Twilio.

## 3. Configuración y docs

- [x] 3.1 `META_*` en Compose y `.env.example`.
- [x] 3.2 README, verificación C-13 y CHANGES.

## 4. Cierre

- [x] 4.1 Tests del adaptador, webhook, estados y respuestas.
- [x] 4.2 Gates: ruff, mypy, pytest local/PostgreSQL, frontend y OpenSpec.
- [x] 4.3 Smoke HTTP contra la app real con el proveedor fake y webhook Meta firmado.
