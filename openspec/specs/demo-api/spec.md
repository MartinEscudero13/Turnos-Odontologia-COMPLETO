# demo-api Specification

## Purpose
Make the already-tested C-05/C-06 core reachable through the real API so a demo can authenticate, see the demo catalog, choose availability and create a reservation without mocks at the HTTP boundary.

## Requirements

### Requirement: Demo app exposes C-05 and C-06 routers

The FastAPI app SHALL mount the C-05 turnos router and the C-06 public reservation router alongside health, auth and catálogos.

#### Scenario: Health and domain routes coexist
- **DADO** la app creada por `create_app`
- **CUANDO** se consulta `/api/health` y `/api/turnos`
- **ENTONCES** health responde `200` y turnos responde `200` o `422` de contrato, nunca `404`

#### Scenario: Public catalog is reachable
- **DADO** el tenant demo `demo`
- **CUANDO** se consulta `GET /api/publico/demo/catalogo`
- **ENTONCES** la respuesta `200` trae prestaciones y profesionales del catálogo demo

### Requirement: Demo catalog is tenant-scoped and fictitious

The system SHALL seed a reproducible demo tenant with fictitious professionals, chairs, services and weekly availability. No real patient data SHALL be present.

#### Scenario: Seeded availability exists
- **DADO** el catálogo demo sembrado
- **CUANDO** se consulta disponibilidad para una prestación en una fecha hábil
- **ENTONCES** hay al menos un hueco con `inicio`, `fin`, profesional y sillón

#### Scenario: Another tenant has no catalog
- **DADO** un token de tenant inexistente
- **CUANDO** se consulta el catálogo público
- **ENTONCES** la respuesta es `404` y no expone el catálogo de `demo`

### Requirement: Public reservation creates a turn through the real API

The system SHALL allow the C-06 flow to emit a verification and create a reservation through HTTP, returning the turn and public token.

#### Scenario: Reserve a real slot
- **DADO** un hueco de disponibilidad del tenant demo
- **CUANDO** se emite una verificación para `reservar` y se envía la reserva con nombre y teléfono ficticios
- **ENTONCES** la respuesta `201` incluye turno, estado `PENDIENTE` y `token_publico`

#### Scenario: Missing verification is rejected
- **DADO** una reserva pública sin `verificacion_id`
- **CUANDO** se envía al endpoint de reservas
- **ENTONCES** la respuesta es `403` y no crea turno

### Requirement: Demo wiring is isolated and declared

The system SHALL keep C-05/C-06 demo state in memory, SHALL NOT use real patient data or external credentials, and SHALL document the reset-on-restart boundary.

#### Scenario: Restart does not claim persistence
- **DADO** una reserva creada en la demo
- **CUANDO** se reinicia el proceso
- **ENTONCES** la documentación declara que el estado puede perderse y que la persistencia SQL de esos dominios es un follow-up

### Requirement: Demo app exposes the C-07 waiting-list routes

The FastAPI app SHALL mount the C-07 waiting-list router with in-memory adapters so reception can
create and list waiting-list entries against the demo tenant.

#### Scenario: Create and list a waiting-list entry
- **DADO** el tenant demo con un paciente ficticio sembrado
- **CUANDO** se envía `POST /api/lista-espera` con `paciente_id`, `prestacion_id` y un actor `RECEPCION`
- **ENTONCES** la respuesta es `201` con estado `PENDIENTE`
- **Y** `GET /api/lista-espera` devuelve la entrada creada

#### Scenario: Waiting list requires an internal role
- **DADO** un actor con rol `PACIENTE`
- **CUANDO** se intenta dar de alta una entrada
- **ENTONCES** la respuesta es `403` y no se crea la entrada

### Requirement: Demo app exposes the C-10 cash routes

The FastAPI app SHALL mount the C-10 cash router over in-memory repositories with a shared clock, so a
movement can be registered and the operational day queried by HTTP.

#### Scenario: Register a movement and query the day
- **DADO** el tenant demo y una fecha operativa sin cierre
- **CUANDO** se registra un ingreso por `150000` en `EFECTIVO`
- **ENTONCES** la respuesta es `201`
- **Y** la consulta del día devuelve el total de `EFECTIVO` igual a `150000`

#### Scenario: Closed day rejects new movements
- **DADO** un día cerrado con responsable del tenant demo
- **CUANDO** se intenta registrar otro movimiento en esa fecha
- **ENTONCES** la respuesta es `409`

### Requirement: Demo reservation creates a C-11 deposit when configured

The public reservation flow SHALL include the C-11 deposit port. When the demo rule requires a deposit,
the reservation response SHALL include the deposit block with its one-time public token.

#### Scenario: Deposit required for Consulta
- **DADO** la regla demo `PORCENTAJE 30` sobre `Consulta` con precio base `10000`
- **CUANDO** se completa una reserva pública
- **ENTONCES** la respuesta `201` incluye `sena.estado = PENDIENTE` y `sena.monto_centavos = 3000`
- **Y** `GET /api/publico/demo/senas/{token_sena}` devuelve la misma seña

#### Scenario: Deposit not required for Limpieza
- **DADO** la prestación demo `Limpieza` configurada como `SIN_SENA`
- **CUANDO** se completa una reserva pública de `Limpieza`
- **ENTONCES** la respuesta `201` devuelve `sena = null`

### Requirement: Demo app exposes internal deposit routes

The FastAPI app SHALL mount the C-11 internal reading routes so operators can list deposits of their
tenant without PHI.

#### Scenario: List deposits of the demo tenant
- **DADO** una seña creada desde una reserva pública
- **CUANDO** `GET /api/senas` se consulta con un actor interno del tenant demo
- **ENTONCES** la respuesta es `200` e incluye la seña creada

### Requirement: Webhook stays fail-closed without credentials

Without a configured Mercado Pago secret, the webhook route SHALL reject every payload and SHALL NOT
create or mutate deposits.

#### Scenario: Webhook without secret
- **DADO** la demo sin `MP_WEBHOOK_SECRET`
- **CUANDO** llega `POST /api/webhooks/mercadopago`
- **ENTONCES** la respuesta es `503` con código `WEBHOOK_NO_CONFIGURADO`
