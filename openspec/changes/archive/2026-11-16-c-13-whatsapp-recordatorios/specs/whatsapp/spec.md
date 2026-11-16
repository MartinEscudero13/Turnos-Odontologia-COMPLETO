# Spec Delta — whatsapp

## ADDED Requirements

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
