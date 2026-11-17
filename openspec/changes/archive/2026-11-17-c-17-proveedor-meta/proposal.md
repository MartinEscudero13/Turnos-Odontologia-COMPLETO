# Proposal — C-17 Proveedor Meta WhatsApp Cloud API

## Why

La cuenta trial de Twilio quedó bloqueada por un incidente de Twilio con perfiles nuevos: el sandbox
confirma el join, pero la API rechaza el envío con `572002`. Para no depender de ese incidente se agrega
el proveedor oficial de Meta detrás del mismo puerto, de modo que la demo pueda enviar WhatsApp real con
un número de prueba.

## What Changes

- Adaptador `PasarelaMeta` (Graph API, Bearer token, sin SDK) para enviar texto.
- `WA_PROVIDER=meta` con `META_WA_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`,
  `META_APP_SECRET` y `META_API_VERSION`.
- Verificación `GET /api/webhooks/whatsapp/meta` con `hub.verify_token`.
- Webhook `POST /api/webhooks/whatsapp/meta` con firma `X-Hub-Signature-256`, estados y respuestas.
- Resolución de respuestas por `context.id` o por teléfono del paciente contra el último mensaje.
- El webhook de Twilio también gana la resolución por teléfono para respuestas sin `OriginalRepliedMessageSid`.
- Variables de Compose y `.env.example`.

## Capabilities

### Modified Capabilities

- `whatsapp`: suma el proveedor Meta Cloud API y el webhook firmado.

## Impact

- `backend/app/whatsapp/meta.py`, `servicio.py`, `routers/whatsapp.py`, `demo.py`.
- `tests/test_whatsapp_meta.py`, `tests/test_demo_api_whatsapp.py`, `tests/test_whatsapp.py`.
- `docker-compose.yml`, `.env.example`, `README.md`, `docs/foundation/verification-c-13-whatsapp.md`.

## Fuera de alcance

- Token permanente de system user: la demo usa el token temporal de 24 h.
- Plantillas aprobadas de producción; el número de prueba usa texto libre.
