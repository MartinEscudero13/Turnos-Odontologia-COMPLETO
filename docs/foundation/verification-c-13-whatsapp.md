# Verification — C-13 WhatsApp (Twilio y Meta Cloud API)

**Fecha**: 2026-11-16 (actualizado 2026-11-17 con Meta) · **Alcance**: recordatorios, webhook,
respuestas y recall

## Resultado

| Gate | Resultado |
|---|---|
| Tests de dominio | **15 passed** (`tests/test_whatsapp.py`) |
| Tests del adaptador Meta | **8 passed** (`tests/test_whatsapp_meta.py`) |
| Tests HTTP demo | **11 passed** (`tests/test_demo_api_whatsapp.py`) |
| Tests PostgreSQL | **2 passed** (`tests/test_whatsapp_pg.py`, con `C02_DATABASE_URL`) |
| Suite completa con DB | **890 passed, 0 skipped** |
| `ruff` | `All checks passed!` |
| `mypy` | 134 archivos, 0 errores |
| OpenSpec | `c-13-whatsapp-recordatorios` válido (`--strict`) |

## Rutas verificadas por HTTP

- `POST /api/whatsapp/recordatorios/programar` → `200` con mensaje `ENVIADO`
- `GET /api/whatsapp/mensajes` → `200` (WA y EMAIL)
- `POST /api/webhooks/whatsapp` con firma Twilio → `200`
  - `Body=SI` → turno `CONFIRMADO`
  - `Body=NO` → turno `CANCELADO` y hueco emitido a C-07
  - `MessageStatus=delivered` → `ENTREGADO`
  - firma inválida → `401`; sin `TWILIO_AUTH_TOKEN` → `503 WEBHOOK_NO_CONFIGURADO`
- `GET /api/webhooks/whatsapp/meta` con `hub.verify_token` → `200` con el challenge
- `POST /api/webhooks/whatsapp/meta` con firma `X-Hub-Signature-256` → `200`
  - respuesta sin `context.id` → se resuelve por teléfono y confirma el turno
  - `statuses: delivered` → mensaje `ENTREGADO`
  - firma inválida → `401`; sin `META_APP_SECRET` → `503 WEBHOOK_NO_CONFIGURADO`
- `POST /api/whatsapp/recall` → `200` con plantilla `RECALL`
- RBAC: `RECEPCION` programa; `ODONTOLOGO` recibe `403`; `PACIENTE` `401`

## Proveedores

### Meta WhatsApp Cloud API

- `PasarelaMeta` usa la Graph API (`/{phone_number_id}/messages`) con Bearer token y `urllib`, sin SDK.
- Envía texto libre a números de prueba del app; el `to` se normaliza a dígitos.
- `GET /api/webhooks/whatsapp/meta` valida `hub.verify_token` y devuelve el challenge.
- `POST /api/webhooks/whatsapp/meta` valida `X-Hub-Signature-256` (HMAC-SHA256 con `META_APP_SECRET`),
  aplana `statuses`/`messages` y reutiliza `ServicioWhatsApp`.
- Las respuestas `SI`/`NO` se resuelven por `context.id` o, si Meta no lo manda, por el teléfono del
  paciente contra el último recordatorio enviado.
- Variables: `META_WA_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`, `META_APP_SECRET`,
  `META_API_VERSION`.

### Twilio

- `PasarelaTwilio` usa la API REST (`Messages.json`) con Basic Auth y `urllib`, sin SDK.
- `firma_valida` implementa HMAC-SHA1 sobre URL + parámetros ordenados con `TWILIO_AUTH_TOKEN`.
- Sin `WA_PROVIDER=twilio` o sin credenciales, la demo usa `PasarelaWhatsAppFake`; los tests no tocan la red.
- Variables fuera del repo: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`, `WA_PROVIDER`.

## Reglas aplicadas

- **RN-IN-01**: API oficial (Twilio sobre WhatsApp), plantillas/recordatorios y email fallback.
- **RN-IN-03**: si Twilio falla, el turno sigue vigente, el mensaje queda `FALLIDO` y se reintenta.
- **RN-AU-01/02**: RBAC y auditoría de envíos, webhook, fallback y recall.
- **C-05**: `confirmar` PENDIENTE → CONFIRMADO con auditoría.
- **C-07**: `NO` emite el hueco al worker de auto-oferta.

## Límites que siguen

- **Sandbox**: sólo envía a números unidos; la sesión de 24 h puede requerir re-join.
- **Producción**: número propio y plantillas aprobadas por Meta; el sandbox usa texto libre.
- **Cron**: la programación se dispara por endpoint; el worker programado queda para C-15.
- **Email fallback**: adaptador de log hasta configurar SMTP.
- **SQL**: `mensajes_wa` está migrado y probado; el webhook SQL requiere `?tenant=<uuid>` para resolver RLS. La demo usa memoria.
