# Spec Delta — demo-api

## ADDED Requirements

### Requirement: Demo app exposes the C-08 clinical record routes

The FastAPI app SHALL mount the C-08 router over in-memory adapters and SHALL enforce the informed
consent precondition before creating a clinical record.

#### Scenario: Missing consent blocks the clinical record
- **DADO** el paciente demo sin consentimiento firmado
- **CUANDO** se envía `POST /api/pacientes/{id}/ficha` con rol `RECEPCION`
- **ENTONCES** la respuesta es `409` y no se crea la ficha

#### Scenario: Consent unlocks the clinical record
- **DADO** un consentimiento registrado por `POST /api/consentimientos`
- **CUANDO** se repite el alta de la ficha
- **ENTONCES** la respuesta es `201` con el `paciente_id`
- **Y** `GET /api/pacientes/{id}/ficha` devuelve la ficha creada

#### Scenario: Clinical evolution is recorded
- **DADO** el paciente demo con consentimiento y un profesional del tenant
- **CUANDO** se envía `POST /api/evoluciones` con rol `ADMIN`, fecha aware y texto
- **ENTONCES** la respuesta es `201`
- **Y** `GET /api/evoluciones?paciente_id=` incluye la evolución

### Requirement: Demo app exposes the C-09 odontogram routes

The FastAPI app SHALL mount the odontogram router over in-memory adapters so a valid FDI finding can
be registered and listed.

#### Scenario: Register a finding
- **DADO** el paciente demo con consentimiento y un profesional sembrado
- **CUANDO** se envía `POST /api/odontograma` con `pieza_fdi = 36`, superficie y hallazgo
- **ENTONCES** la respuesta es `201` con el hallazgo
- **Y** `GET /api/odontograma?paciente_id=` devuelve el hallazgo

#### Scenario: Invalid FDI piece is rejected
- **DADO** una pieza FDI fuera del rango válido
- **CUANDO** se intenta registrar el hallazgo
- **ENTONCES** la respuesta es `422` y no se persiste nada

### Requirement: Demo app exposes the C-09 budget routes

The FastAPI app SHALL mount the budget router over in-memory adapters, allowing a draft to be created,
a priced line to be added and the budget to be issued.

#### Scenario: Create, add a line and issue a budget
- **DADO** el paciente demo y una prestación demo con precio base
- **CUANDO** se crea un presupuesto, se agrega una línea sin monto y se emite con vencimiento futuro
- **ENTONCES** la línea toma el precio base y el presupuesto queda `VIGENTE`
- **Y** `GET /api/presupuestos?paciente_id=` devuelve el presupuesto con su línea

#### Scenario: Issuing without lines is refused
- **DADO** un presupuesto en `BORRADOR` sin líneas
- **CUANDO** se intenta emitir
- **ENTONCES** la respuesta es `409` y el presupuesto sigue en `BORRADOR`

### Requirement: Clinical state is shared and declared

The demo SHALL share one consent adapter and one budget repository between C-08 and C-09, SHALL keep
all clinical state in memory and SHALL NOT claim SQL persistence.

#### Scenario: Restart does not claim persistence
- **DADO** una ficha y un presupuesto creados en la demo
- **CUANDO** se reinicia el proceso
- **ENTONCES** la documentación declara que el estado clínico se pierde y que la persistencia SQL de
  C-08/C-09 es un follow-up
