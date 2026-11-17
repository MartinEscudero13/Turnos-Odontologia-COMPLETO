# Spec Delta — whatsapp

## ADDED Requirements

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
