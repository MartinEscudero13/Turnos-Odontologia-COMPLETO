# Verification — C-13 WhatsApp con Twilio

**Fecha**: 2026-11-16 · **Alcance**: recordatorios, webhook, respuestas y recall

## Resultado

| Gate | Resultado |
|---|---|
| Tests de dominio | **13 passed** (`tests/test_whatsapp.py`) |
| Tests HTTP demo | **5 passed** (`tests/test_demo_api_whatsapp.py`) |
| Tests PostgreSQL | **2 passed** (`tests/test_whatsapp_pg.py`, con `C02_DATABASE_URL`) |
| Suite completa con DB | **859 passed, 0 skipped** |
| `ruff` | `All checks passed!` |
| `mypy` | 131 archivos, 0 errores |
| OpenSpec | `c-13-whatsapp-recordatorios` válido (`--strict`) |

## Rutas verificadas por HTTP

- `POST /api/whatsapp/recordatorios/programar` → `200` con mensaje `ENVIADO`
- `GET /api/whatsapp/mensajes` → `200` (WA y EMAIL)
- `POST /api/webhooks/whatsapp` con firma Twilio → `200`
  - `Body=SI` → turno `CONFIRMADO`
  - `Body=NO` → turno `CANCELADO` y hueco emitido a C-07
  - `MessageStatus=delivered` → `ENTREGADO`
  - firma inválida → `401`; sin `TWILIO_AUTH_TOKEN` → `503 WEBHOOK_NO_CONFIGURADO`
- `POST /api/whatsapp/recall` → `200` con plantilla `RECALL`
- RBAC: `RECEPCION` programa; `ODONTOLOGO` recibe `403`; `PACIENTE` `401`

## Twilio

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
