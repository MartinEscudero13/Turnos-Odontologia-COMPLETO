# Spec Delta — turnos-anti-solape

## Purpose

Garantizar que ningún profesional ni sillón quede doble-reservado: el sistema
rechaza todo solape salvo sobreturno explícito y auditado, y libera los huecos
cancelados o reprogramados para su reutilización.

## ADDED Requirements

### Requirement: Creación de turno válido

El sistema SHALL crear un turno cuando existe hueco real (sin solape por
profesional ni por sillón en `[inicio, fin)` dentro del mismo tenant), con
`fin` calculado como `inicio + prestacion.duracion_min` y estado inicial
`PENDIENTE`.

#### Scenario: Turno válido se crea

- **DADO** un profesional y un sillón libres el 2026-10-06 de 10:00 a 10:30
  (prestación de 30 min) en el tenant T1
- **CUANDO** recepción crea el turno para ese hueco
- **ENTONCES** el turno queda persistido en estado `PENDIENTE` con `fin`
  = 10:30 calculado por el sistema, no ingresado

#### Scenario: Fin derivado de la prestación, no ingresado

- **DADO** una prestación con `duracion_min = 45`
- **CUANDO** se crea un turno con `inicio` = 09:00
- **ENTONCES** el sistema fija `fin` = 09:45 y rechaza cualquier `fin`
  provisto por el cliente que difiera del cálculo

### Requirement: Rechazo de solape por profesional o sillón

El sistema SHALL rechazar con `409 Conflict` + 3 alternativas toda creación o
reprogramación que solape `[inicio, fin)` con otro turno activo del mismo
`tenant_id` e igual `profesional_id` o igual `sillon_id`. Turnos con estado
`CANCELADO` o `REPROGRAMADO`, o con `sobreturno=true`, no bloquean.

#### Scenario: Solape por profesional → rechazo 409

- **DADO** un turno activo del profesional P1 en T1 de 10:00 a 10:30
- **CUANDO** se intenta crear otro turno con P1 (distinto sillón) de 10:15
  a 10:45
- **ENTONCES** el sistema responde `409` con 3 huecos alternativos y no
  persiste el turno

#### Scenario: Solape por sillón → rechazo 409

- **DADO** un turno activo en el sillón S1 en T1 de 11:00 a 11:30
- **CUANDO** se intenta crear otro turno en S1 (distinto profesional) de
  11:15 a 11:45
- **ENTONCES** el sistema responde `409` con 3 huecos alternativos y no
  persiste el turno

#### Scenario: Aislamiento por tenant

- **DADO** un turno activo de P1 en el tenant T1 de 10:00 a 10:30
- **CUANDO** se crea un turno con el mismo profesional y horario en el
  tenant T2
- **ENTONCES** el turno se crea sin conflicto (el anti-solape nunca mezcla
  tenants)

### Requirement: Adyacencia exacta permitida

El sistema SHALL permitir turnos adyacentes: un turno que empieza exactamente
cuando termina otro (`fin_A == inicio_B`, rango `[inicio, fin)`) no se
considera solape.

#### Scenario: Turno que empieza cuando termina otro → permitido

- **DADO** un turno activo de P1 en S1 de 10:00 a 10:30
- **CUANDO** se crea otro turno con P1 y S1 de 10:30 a 11:00
- **ENTONCES** el turno se crea correctamente en estado `PENDIENTE`

### Requirement: Cancelados y reprogramados no bloquean

El sistema SHALL excluir del anti-solape los turnos con estado `CANCELADO` o
`REPROGRAMADO`, de modo que sus huecos vuelven a estar disponibles (disparando
la auto-oferta de lista de espera en C-07).

#### Scenario: Hueco cancelado se reutiliza

- **DADO** un turno `CANCELADO` de P1 en S1 de 10:00 a 10:30
- **CUANDO** se crea un turno nuevo con P1 y S1 en ese mismo horario
- **ENTONCES** el turno se crea correctamente

#### Scenario: Reprogramar libera el hueco original

- **DADO** un turno activo de P1 de 10:00 a 10:30 que se reprograma a las
  14:00 (pasando a estado `REPROGRAMADO` + nuevo turno activo a las 14:00)
- **CUANDO** se crea otro turno con P1 de 10:00 a 10:30
- **ENTONCES** el turno se crea correctamente y el reprogramado a las 14:00
  sigue bloqueando su nuevo horario

### Requirement: Sobreturno explícito y auditado

El sistema SHALL permitir sobreturno solo como acción explícita
(`POST /api/turnos/:id/sobreturno` o flag en creación) con motivo obligatorio
no vacío, registrando actor, motivo y antes/después en la auditoría
append-only. Un sobreturno nunca se produce por accidente ni por omitir el
motivo.

#### Scenario: Sobreturno con motivo se crea y se audita

- **DADO** un turno activo de P1 de 10:00 a 10:30
- **CUANDO** recepción crea un sobreturno con P1 de 10:15 a 10:45 indicando
  motivo "urgencia con dolor"
- **ENTONCES** el sobreturno se persiste con `sobreturno=true` y la auditoría
  contiene actor, motivo y antes/después

#### Scenario: Sobreturno sin motivo se rechaza

- **DADO** un turno activo de P1 de 10:00 a 10:30
- **CUANDO** se intenta crear un sobreturno solapado sin motivo (vacío o
  ausente)
- **ENTONCES** el sistema responde `422` y no persiste el turno

### Requirement: Cancelar y reprogramar turnos

El sistema SHALL exponer cancelar (pasa a `CANCELADO`) y reprogramar (marca el
original `REPROGRAMADO` y crea el nuevo turno revalidando solape en servidor)
como operaciones auditadas que respetan la anticipación mínima configurable
del tenant (default 24 h; debajo del umbral solo recepción, quedando
auditado).

#### Scenario: Cancelación con anticipación libera el hueco

- **DADO** un turno `CONFIRMADO` para dentro de 48 h
- **CUANDO** se cancela con anticipación suficiente
- **ENTONCES** el turno pasa a `CANCELADO`, queda auditado y su hueco admite
  un turno nuevo

#### Scenario: Reprogramación revalida solape en servidor

- **DADO** un turno activo de P1 de 10:00 a 10:30 y otro turno activo de P1
  de 14:00 a 14:30
- **CUANDO** se intenta reprogramar el primero hacia las 14:15
- **ENTONCES** el sistema responde `409` con 3 alternativas y el turno
  original conserva su horario
