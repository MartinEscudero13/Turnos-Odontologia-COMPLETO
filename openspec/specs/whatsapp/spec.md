# whatsapp Specification

## Purpose

Enviar recordatorios de turno y recibir respuestas por WhatsApp usando Twilio, confirmar o cancelar
turnos desde el mensaje, reintentar con fallback email y ofrecer recall clínico separado del marketing.
El sandbox de Twilio es el proveedor de la demo; producción requiere número propio y plantillas
aprobadas. Los mensajes se persisten por tenant con RLS.

## Requirements

### Requirement: Scheduled appointment reminders

The system SHALL create one reminder per appointment and template, send it through the configured
provider and keep the message state. A repeated request SHALL not duplicate the reminder.

#### Scenario: Reminder for an upcoming appointment
- **DADO** un turno PENDIENTE dentro de la ventana de anticipación y un paciente con teléfono
- **CUANDO** se programan los recordatorios
- **ENTONCES** se crea un mensaje `RECORDATORIO` en estado `ENVIADO` con `provider_message_id`
- **Y** una segunda programación no crea otro mensaje para el mismo turno

#### Scenario: Patient without phone is skipped
- **DADO** un turno cuyo paciente no tiene teléfono
- **CUANDO** se programan los recordatorios
- **ENTONCES** no se crea mensaje y no se llama a la pasarela

#### Scenario: Provider failure falls back to email
- **DADO** una pasarela que falla
- **CUANDO** se envía el recordatorio
- **ENTONCES** el mensaje WA queda `FALLIDO` y se registra un mensaje `EMAIL`
- **Y** el turno sigue vigente

### Requirement: Twilio webhook and replies

The system SHALL validate the Twilio signature and process delivery states and replies. `SI` SHALL
confirm the appointment; `NO` SHALL cancel it and release the slot to C-07.

#### Scenario: Delivery status
- **DADO** un mensaje con `provider_message_id`
- **CUANDO** llega `MessageStatus=delivered`
- **ENTONCES** el mensaje pasa a `ENTREGADO`

#### Scenario: Confirm reply
- **DADO** un mensaje de recordatorio de un turno PENDIENTE
- **CUANDO** el paciente responde `SI`
- **ENTONCES** el turno pasa a `CONFIRMADO` y se registra la respuesta

#### Scenario: Cancel reply
- **DADO** un turno cancelable
- **CUANDO** el paciente responde `NO`
- **ENTONCES** el turno pasa a `CANCELADO` y se emite el hueco para la lista de espera

#### Scenario: Ambiguous reply
- **DADO** una respuesta que no es SI/NO
- **CUANDO** llega el webhook
- **ENTONCES** el mensaje queda `AMBIGUA` y la respuesta incluye `link_confirmacion`

#### Scenario: Invalid signature
- **DADO** un webhook sin firma válida
- **CUANDO** se procesa
- **ENTONCES** la respuesta es `401` y no se modifica ningún mensaje

### Requirement: Retry queue

Failed messages SHALL be retried with backoff up to three attempts. Exhausted messages SHALL remain
visible and SHALL not block the agenda.

#### Scenario: Retry succeeds
- **DADO** un mensaje fallido y la pasarela recuperada
- **CUANDO** se procesa la cola
- **ENTONCES** el mensaje pasa a `ENVIADO`

#### Scenario: Retries exhausted
- **DADO** un mensaje con tres intentos fallidos
- **CUANDO** se procesa la cola
- **ENTONCES** queda `FALLIDO` sin nuevos reintentos

### Requirement: Sanitary recall

The system SHALL create a `RECALL` message with clinical reason and target date, separate from
marketing.

#### Scenario: Recall created
- **DADO** un paciente con teléfono y un profesional habilitado
- **CUANDO** se solicita un recall con motivo y fecha
- **ENTONCES** se crea un mensaje `RECALL` y se envía por WhatsApp

### Requirement: Tenant isolation and RBAC

Every message SHALL be filtered by tenant and protected by RLS. Only `ADMIN`/`RECEPCION` SHALL operate
reminders; `ODONTOLOGO`/`ADMIN` SHALL create recalls.

#### Scenario: Reception schedules reminders
- **DADO** un actor RECEPCION
- **CUANDO** programa recordatorios
- **ENTONCES** la respuesta es `200`

#### Scenario: Patient has no access
- **DADO** un actor PACIENTE
- **CUANDO** consulta mensajes
- **ENTONCES** la respuesta es `401`

### Requirement: Meta WhatsApp Cloud API provider

The system SHALL allow `WA_PROVIDER=meta` to send WhatsApp text messages through the Meta Graph API
using a Bearer token and the configured phone number ID. The provider SHALL be selected behind the
existing gateway port without changing the reminder, retry or recall logic.

#### Scenario: Send a reminder through Meta
- **DADO** `WA_PROVIDER=meta` con token y phone number ID válidos
- **CUANDO** se programan recordatorios
- **ENTONCES** el mensaje se envía a `/{phone_number_id}/messages` y guarda el `wamid` devuelto

#### Scenario: Missing Meta credentials
- **DADO** `WA_PROVIDER=meta` sin token o sin phone number ID
- **CUANDO** arranca la demo
- **ENTONCES** se usa la pasarela fake y no se toca la red

### Requirement: Meta webhook verification and signature

The system SHALL expose `GET /api/webhooks/whatsapp/meta` for `hub.challenge` verification and
`POST /api/webhooks/whatsapp/meta` for events. The POST SHALL validate `X-Hub-Signature-256` with
`META_APP_SECRET` and SHALL fail closed when the secret is missing.

#### Scenario: Verification challenge
- **DADO** `META_VERIFY_TOKEN` configurado
- **CUANDO** Meta llama con `hub.mode=subscribe` y el token correcto
- **ENTONCES** la respuesta es `200` con el challenge

#### Scenario: Invalid signature
- **DADO** un cuerpo y una firma que no coinciden
- **CUANDO** llega el POST
- **ENTONCES** la respuesta es `401` y no se modifica ningún mensaje

#### Scenario: Missing app secret
- **DADO** el webhook sin `META_APP_SECRET`
- **CUANDO** llega el POST
- **ENTONCES** la respuesta es `503 WEBHOOK_NO_CONFIGURADO`

### Requirement: Meta delivery states and replies

The system SHALL process `statuses` (`sent`, `delivered`, `read`, `failed`) and inbound `messages`.
A `SI` or `NO` reply SHALL confirm or cancel the appointment, resolving it by `context.id` when present
or by the sender phone against the last message otherwise.

#### Scenario: Delivered status
- **DADO** un mensaje con `wamid`
- **CUANDO** llega `statuses[].status=delivered`
- **ENTONCES** el mensaje pasa a `ENTREGADO`

#### Scenario: Reply without context
- **DADO** un recordatorio enviado al teléfono del paciente
- **CUANDO** el paciente responde `SI` sin citar el mensaje
- **ENTONCES** el turno pasa a `CONFIRMADO` y se registra la respuesta

#### Scenario: Reply with context
- **DADO** una respuesta con `context.id` igual al `wamid` del recordatorio
- **CUANDO** el paciente responde `NO`
- **ENTONCES** el turno pasa a `CANCELADO` y se emite el hueco a C-07
