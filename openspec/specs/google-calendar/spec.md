# google-calendar Specification

## Purpose

Sincronizar la agenda de cada profesional con Google Calendar manteniendo al sistema como fuente de
verdad (RN-IN-02): push idempotente de turnos, eventos externos como bloqueo informativo, cola de
reintentos con backoff y degradación sin romper la agenda cuando GCal o el token fallan (RN-IN-03).
El OAuth real y la lectura de bloqueos por C-06 quedan fuera de v1.

## Requirements

### Requirement: Per-professional calendar link

The system SHALL link one Google Calendar per professional and tenant. The link SHALL store a
reference to the OAuth credential (never the raw token) and SHALL be unique per professional.

#### Scenario: Connect a calendar
- **DADO** un profesional del tenant sin link
- **CUANDO** un `ADMIN` envía `POST /api/calendar/oauth` con `gcal_calendar_id` y `oauth_ref`
- **ENTONCES** la respuesta es `201` con estado `CONECTADO`
- **Y** `GET /api/calendar/links` devuelve el link del profesional

#### Scenario: Duplicate link is a conflict
- **DADO** un profesional con link `CONECTADO`
- **CUANDO** se intenta conectar otro calendario para el mismo profesional
- **ENTONCES** la respuesta es `409` y el link original no cambia

#### Scenario: Odontologist only manages own link
- **DADO** un actor `ODONTOLOGO` con `X-Profesional-Id` distinto al del body
- **CUANDO** intenta conectar el calendario de otro profesional
- **ENTONCES** la respuesta es `403`

### Requirement: Push of internal turns

The system SHALL push created or modified turns to the linked calendar and SHALL remove the external
event when the turn is cancelled. Push SHALL be idempotent per turn.

#### Scenario: Push creates one event
- **DADO** un link `CONECTADO`
- **CUANDO** se pushea un turno vigente
- **ENTONCES** la pasarela registra un evento y la respuesta es `201`
- **Y** una segunda pusheada del mismo turno actualiza el mismo `gcal_event_id` sin duplicar

#### Scenario: Cancel removes the event
- **DADO** un turno ya pusheado
- **CUANDO** se cancela y se pushea la cancelación
- **ENTONCES** la pasarela elimina el evento y el mapeo queda `CANCELADO`

#### Scenario: Professional without link is a no-op
- **DADO** un profesional sin link
- **CUANDO** se pushea un turno
- **ENTONCES** no se llama a la pasarela y la respuesta indica que no hay link

### Requirement: External events become informative blocks

The system SHALL store external calendar events as informative blocks. If an external event overlaps a
vigente internal turn, the internal turn SHALL remain unchanged and the block SHALL be marked as a
system conflict (RN-IN-02).

#### Scenario: External event without overlap
- **DADO** un link `CONECTADO` y ningún turno en el rango
- **CUANDO** llega un evento externo por webhook con token válido
- **ENTONCES** se guarda como `BLOQUEADO` y aparece en `/api/calendar/bloqueos`

#### Scenario: External event overlapping an internal turn
- **DADO** un turno interno vigente en el rango del evento externo
- **CUANDO** llega el evento externo
- **ENTONCES** el turno interno no cambia y el evento queda `CONFLICTO_SISTEMA`

#### Scenario: Invalid webhook token
- **DADO** un link con `oauth_ref` conocido
- **CUANDO** el webhook llega con un token distinto
- **ENTONCES** la respuesta es `401` y no se persiste ningún evento

### Requirement: Graceful degradation with retry queue

When the calendar provider fails, the system SHALL keep the internal agenda working, SHALL queue the
push with backoff and SHALL mark the link as revoked when the token is rejected (RN-IN-03).

#### Scenario: Provider down queues the event
- **DADO** una pasarela que falla
- **CUANDO** se pushea un turno
- **ENTONCES** el turno sigue vigente, el evento queda `PENDIENTE` y se encola un envío

#### Scenario: Retry succeeds later
- **DADO** un envío pendiente y la pasarela recuperada
- **CUANDO** se procesa la cola
- **ENTONCES** el evento pasa a `SINCRONIZADO` y el envío a `PROCESADO`

#### Scenario: Retries are exhausted
- **DADO** una pasarela que sigue fallando y un envío con 3 intentos
- **CUANDO** se procesa la cola
- **ENTONCES** el envío queda `AGOTADO` y la agenda interna sigue operativa

#### Scenario: Revoked token
- **DADO** una pasarela que responde token revocado
- **CUANDO** se procesa la cola
- **ENTONCES** el link queda `TOKEN_REVOCADO`, el envío no se pierde y la agenda no se modifica

### Requirement: Tenant isolation for calendar data

Every calendar table SHALL be protected by row-level security and every query SHALL filter by
`tenant_id`.

#### Scenario: No tenant context returns no rows
- **DADO** una sesión PostgreSQL sin `app.tenant_id`
- **CUANDO** se consultan links, eventos o envíos
- **ENTONCES** la consulta devuelve cero filas
