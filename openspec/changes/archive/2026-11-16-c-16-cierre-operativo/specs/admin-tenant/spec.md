# Spec Delta — admin-tenant

## MODIFIED Requirements

### Requirement: Base KPIs

The system SHALL expose base KPIs for a period with explicit definitions: turns by state, absenteeism,
online reservation share, billing by professional, slots reassigned in under two hours and occupancy.
Occupancy SHALL be the share of booked minutes over the capacity offered by professionals in the
period, with a `0.0` result when the denominator is zero.

#### Scenario: Absenteeism
- **DADO** 2 turnos `PRESENTE` y 2 `AUSENTE` en el período
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ausentismo_pct = 50.0`

#### Scenario: Online reservation share
- **DADO** 1 turno `RESERVA_ONLINE` y 3 de otros orígenes
- **CUANDO** se consultan los KPIs
- **ENTONCES** `reservas_online_pct = 25.0`

#### Scenario: Reassigned under two hours
- **DADO** un turno `LISTA_ESPERA` creado 30 minutos antes de su inicio y otro 3 horas antes
- **CUANDO** se consultan los KPIs
- **ENTONCES** `reasignados_2h = 1`

#### Scenario: Occupancy
- **DADO** 540 minutos ocupados y 1440 minutos de capacidad en el período
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ocupacion_pct = 37.5`

#### Scenario: Occupancy without capacity
- **DADO** un período sin horarios cargados y sin turnos
- **CUANDO** se consultan los KPIs
- **ENTONCES** `ocupacion_pct = 0.0`

#### Scenario: Invalid period
- **DADO** `desde` posterior a `hasta`
- **CUANDO** se consultan los KPIs
- **ENTONCES** la respuesta es `422`
