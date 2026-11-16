# frontend-interno Specification

## Purpose

Operar el consultorio desde el SPA: sesión con login real o demo, agenda con transiciones de estado,
pacientes, clínica con decisiones de presupuesto, caja con anulación y cobros pendientes, señas,
WhatsApp, obras sociales, calendario y administración. Consume la API de C-05…C-15 con actor por
headers y JWT para catálogos. La edición avanzada de entidades queda fuera.

## Requirements

### Requirement: Demo session and internal routes

The SPA SHALL provide a login with a real session and a demo session, and SHALL expose the internal
modules under `/app`.

#### Scenario: Demo login
- **DADO** el seed demo aplicado
- **CUANDO** el usuario inicia sesión con las credenciales demo
- **ENTONCES** se abre `/app` con la sesión de `admin@demo.test`

#### Scenario: Protected route without session
- **DADO** un usuario sin sesión
- **CUANDO** visita `/app/agenda`
- **ENTONCES** es redirigido a `/login`

#### Scenario: Navigation
- **DADO** una sesión activa
- **CUANDO** se abre el panel
- **ENTONCES** el rail muestra Agenda, Pacientes, Clínica, Caja, Señas, Obras sociales, Calendario y Configuración

### Requirement: Agenda and patients from the SPA

The SPA SHALL list and create patients and turns, and SHALL expose the legal agenda transitions:
confirm a pending turn, mark a confirmed turn as present or absent, and cancel a non-final turn.

#### Scenario: Create a patient
- **DADO** el formulario de pacientes
- **CUANDO** se envía nombre y teléfono E.164
- **ENTONCES** el paciente aparece en la tabla

#### Scenario: Create and cancel a turn
- **DADO** paciente, prestación, profesional, sillón y fecha
- **CUANDO** se crea el turno
- **ENTONCES** aparece en la agenda
- **Y** al cancelarlo cambia a `CANCELADO`

#### Scenario: Confirm and register attendance
- **DADO** un turno `PENDIENTE`
- **CUANDO** se toca "Confirmar" y luego "Presente"
- **ENTONCES** el turno pasa a `CONFIRMADO` y después a `PRESENTE`
- **Y** la grilla ya no ofrece acciones para un turno final

### Requirement: Clinical workflow from the SPA

The SPA SHALL support consent, ficha, evolutions, odontogram findings and budgets for a selected
patient.

#### Scenario: Consent unlocks the ficha
- **DADO** un paciente sin consentimiento
- **CUANDO** se registra el consentimiento y se crea la ficha
- **ENTONCES** la ficha queda disponible

#### Scenario: Budget with coverage
- **DADO** un paciente con obra social
- **CUANDO** se agrega una línea y se emite el presupuesto
- **ENTONCES** la tabla muestra cobertura OS y a cargo del paciente

### Requirement: Cash, deposits, insurance and calendar screens

The SPA SHALL show the daily cash totals and movements, the deposits of a period, insurance coverage
and settlements, and calendar links and blocks. The cash screen SHALL also allow voiding a movement
with a reason, collecting a pending charge, and consulting closures and range reports.

#### Scenario: Cash day
- **DADO** una fecha
- **CUANDO** se abre Caja
- **ENTONCES** se ven los totales por medio y los movimientos
- **Y** se puede registrar un movimiento o cerrar el día

#### Scenario: Void and pending charge
- **DADO** un movimiento vigente y un cobro pendiente
- **CUANDO** se anula con motivo y se cobra el pendiente
- **ENTONCES** el movimiento queda anulado y el pendiente resuelto con su ingreso

#### Scenario: Settlement CSV
- **DADO** una liquidación
- **CUANDO** se elige "CSV"
- **ENTONCES** se descarga el archivo con el actor autenticado

#### Scenario: Settlement detail
- **DADO** una liquidación listada
- **CUANDO** se elige "Detalle"
- **ENTONCES** se muestran sus líneas y el total

#### Scenario: Calendar push
- **DADO** un turno y un link conectado
- **CUANDO** se pushea el turno
- **ENTONCES** el evento queda sincronizado y los bloqueos se refrescan

#### Scenario: Disconnect calendar
- **DADO** un link `CONECTADO`
- **CUANDO** se toca "Desconectar"
- **ENTONCES** el link pasa a `DESCONECTADO`

### Requirement: Admin screen

The SPA SHALL edit tenant configuration, create users, download the tenant export and compute KPIs.

#### Scenario: Update configuration
- **DADO** la pantalla Configuración
- **CUANDO** se cambia la anticipación y se guarda
- **ENTONCES** el valor queda actualizado

#### Scenario: Export
- **DADO** la pantalla Configuración
- **CUANDO** se elige JSON o CSV
- **ENTONCES** se descarga el archivo sin secretos

#### Scenario: KPIs
- **DADO** un período
- **CUANDO** se calculan los KPIs
- **ENTONCES** se muestran turnos, ausentismo, online y reasignados

### Requirement: Budget decisions and finding resolution

The SPA SHALL let reception accept or reject each budget line and resolve an open odontogram finding.
An accepted line without a payment method SHALL leave a pending charge visible in cash.

#### Scenario: Accept a budget line
- **DADO** un presupuesto vigente con una línea
- **CUANDO** se toca "Aceptar"
- **ENTONCES** la línea queda aceptada y aparece un cobro pendiente en Caja

#### Scenario: Reject a budget line
- **DADO** un presupuesto vigente con una línea
- **CUANDO** se toca "Rechazar"
- **ENTONCES** la línea queda rechazada y no se imputa a caja

#### Scenario: Resolve finding
- **DADO** un hallazgo abierto
- **CUANDO** se toca "Resolver"
- **ENTONCES** el hallazgo queda resuelto

### Requirement: Insurance and user state toggles

The SPA SHALL activate or deactivate insurance providers and tenant users from their tables, and SHALL
show the WhatsApp screen.

#### Scenario: Deactivate insurance
- **DADO** una obra social activa
- **CUANDO** se toca "Desactivar"
- **ENTONCES** la obra social queda inactiva sin borrar historial

#### Scenario: Deactivate user
- **DADO** un usuario activo
- **CUANDO** se toca "Desactivar"
- **ENTONCES** el usuario queda inactivo

#### Scenario: WhatsApp screen
- **DADO** una sesión interna
- **CUANDO** se abre `/app/whatsapp`
- **ENTONCES** se pueden programar recordatorios, procesar reintentos y enviar un recall
