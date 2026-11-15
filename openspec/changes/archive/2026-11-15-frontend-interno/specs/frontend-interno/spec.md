# Spec Delta — frontend-interno

## ADDED Requirements

### Requirement: Demo session and internal routes

The SPA SHALL provide a login with a real session and a demo session, and SHALL expose the internal
modules under `/app`.

#### Scenario: Demo login
- **DADO** el seed demo aplicado
- **CUANDO** el usuario elige "Entrar en modo demo"
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

The SPA SHALL list and create patients and turns, and SHALL cancel a turn.

#### Scenario: Create a patient
- **DADO** el formulario de pacientes
- **CUANDO** se envía nombre y teléfono E.164
- **ENTONCES** el paciente aparece en la tabla

#### Scenario: Create and cancel a turn
- **DADO** paciente, prestación, profesional, sillón y fecha
- **CUANDO** se crea el turno
- **ENTONCES** aparece en la agenda
- **Y** al cancelarlo cambia a `CANCELADO`

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
and settlements, and calendar links and blocks.

#### Scenario: Cash day
- **DADO** una fecha
- **CUANDO** se abre Caja
- **ENTONCES** se ven los totales por medio y los movimientos
- **Y** se puede registrar un movimiento o cerrar el día

#### Scenario: Settlement CSV
- **DADO** una liquidación
- **CUANDO** se elige "CSV"
- **ENTONCES** se descarga el archivo con el actor autenticado

#### Scenario: Calendar push
- **DADO** un turno y un link conectado
- **CUANDO** se pushea el turno
- **ENTONCES** el evento queda sincronizado y los bloqueos se refrescan

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
