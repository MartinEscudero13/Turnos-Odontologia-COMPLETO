# Spec Delta — turnos-anti-solape

## Purpose

Explicitar las dos transiciones que C-11 dispara sobre el turno —`PENDIENTE → CONFIRMADO` al
acreditarse la seña y `PENDIENTE → CANCELADO` al vencer la seña— sin agregar estados, sin relajar
el anti-solape y sin cambiar el contrato existente de creación, cancelación y reprogramación.

## ADDED Requirements

### Requirement: Confirmación y liberación del turno por seña

El sistema SHALL confirmar un turno sólo desde `PENDIENTE` cuando su seña se acredita, y SHALL
cancelarlo desde `PENDIENTE` cuando la seña expira sin pago, con motivo `SENA_NO_ACREDITADA`;
ambas transiciones SHALL ser auditadas con `antes`/`después` y SHALL rechazar con `409` cualquier
repetición o cualquier origen distinto de `PENDIENTE`.

#### Scenario: La seña acreditada confirma el turno

- **GIVEN** T1 con el turno TUR-1 en estado `PENDIENTE` y su seña `PENDIENTE`
- **WHEN** la seña se acredita
- **THEN** TUR-1 queda `CONFIRMADO` y la auditoría del turno registra la transición con `antes=PENDIENTE` y `despues=CONFIRMADO`, sin nombre ni teléfono

#### Scenario: La seña vencida cancela el turno y libera el hueco

- **GIVEN** T1 con el turno TUR-2 en `PENDIENTE` y su seña vencida sin acreditar
- **WHEN** el worker de expiración libera la seña
- **THEN** TUR-2 queda `CANCELADO` con motivo `SENA_NO_ACREDITADA`, el hueco deja de bloquear la agenda y se emite el evento de hueco liberado a C-07

#### Scenario: No se confirma dos veces

- **GIVEN** T1 con el turno TUR-3 ya `CONFIRMADO` por su seña
- **WHEN** llega una segunda acreditación de la misma seña
- **THEN** el turno sigue `CONFIRMADO`, no se registra una segunda transición y el webhook responde `200` sin efecto

#### Scenario: Un turno cancelado no se confirma

- **GIVEN** T1 con el turno TUR-4 `CANCELADO` por el paciente y su seña aún `PENDIENTE`
- **WHEN** llega el pago aprobado de esa seña
- **THEN** el turno sigue `CANCELADO`, no se reabre el hueco y la seña queda `DEVUELTA` en lugar de acreditarse

#### Scenario: Las transiciones siguen siendo las de la máquina de estados

- **GIVEN** T1 con el turno TUR-5 en estado `PRESENTE`
- **WHEN** se intenta confirmarlo o cancelarlo por la vía de la seña
- **THEN** el sistema responde `409` y no cambia el estado, porque sólo se permite desde `PENDIENTE`
