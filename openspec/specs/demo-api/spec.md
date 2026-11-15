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
