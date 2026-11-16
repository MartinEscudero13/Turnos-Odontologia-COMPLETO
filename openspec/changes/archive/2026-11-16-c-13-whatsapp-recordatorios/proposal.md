# Proposal — C-13 WhatsApp con Twilio

## Why

El roadmap deja C-13 bloqueado por PO-03. El equipo eligió **Twilio WhatsApp Sandbox** para el TPI:
permite enviar y recibir mensajes reales sin crear una app de Meta ni esperar verificación de negocio.
Con eso se cierra el recordatorio de turnos, la confirmación/cancelación por WhatsApp y el recall
sanitario, con email como fallback.

## What Changes

- Modelo `mensajes_wa` (migración **012**) con estados, canal, intentos, respuesta y RLS.
- Dominio `app/whatsapp/` con puertos, servicio, adaptador Twilio y adaptadores en memoria/fake.
- Programación de recordatorios por anticipación configurable; envío idempotente por turno+plantilla.
- Webhook `POST /api/webhooks/whatsapp` con validación de firma Twilio, estados de entrega y respuestas
  `SI`/`NO`: confirma o cancela el turno; `NO` dispara la auto-oferta de C-07.
- Fallback por email cuando Twilio falla; cola con reintentos y backoff (RN-IN-03).
- Recall sanitario separado del marketing (`POST /api/whatsapp/recall`).
- Endpoints de operación y una pantalla mínima en el SPA (`/app/whatsapp`).
- Variables `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` y `WA_PROVIDER` fuera del repo.

## Capabilities

### New Capabilities

- `whatsapp`: recordatorios, confirmación/cancelación por Twilio, fallback y recall.

### Modified Capabilities

- C-05 gana `confirmar` (transición PENDIENTE → CONFIRMADO) para la respuesta `SI`.
- C-07 recibe el hueco liberado cuando la respuesta es `NO`.

## Impact

- `backend/app/models/whatsapp.py`, migración `012_whatsapp_recordatorios.py`.
- `backend/app/whatsapp/`, router y schemas.
- `backend/app/turnos/servicio.py` (`confirmar`), `backend/app/demo.py`, `backend/app/app.py`.
- `frontend/src/pages/app/WhatsAppPage.tsx` y navegación.
- Tests de dominio, HTTP demo, PostgreSQL y regresión de turnos.

## Fuera de alcance

- Aprobación de plantillas de producción y número propio; el sandbox usa texto libre dentro de la
  ventana de 24 h.
- Campañas de marketing.
- SMTP real: el fallback usa un adaptador de log hasta que se configure un proveedor.
