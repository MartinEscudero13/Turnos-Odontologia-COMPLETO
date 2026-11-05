# Spec Delta — reserva-publica

## MODIFIED Requirements

### Requirement: Disponibilidad pública calculada en el servidor

El sistema SHALL exponer en
`GET /api/publico/{tokenTenant}/disponibilidad?prestacion=&profesional=&desde=`
sólo huecos reales del tenant resuelto, calculados servidor-side como
intersección de horario del profesional y del consultorio, menos bloqueos
vigentes y menos turnos activos, menos los huecos retenidos por una oferta de
lista de espera vigente (C-07), con la `duracion_min` de la prestación. `desde`
abre una ventana de `PUBLIC_DISPONIBILIDAD_HORIZONTE_D` días (valor en `OQ-5`) y
la respuesta es una lista cronológica. Ningún `inicio` fuera de ese cálculo
SHALL aceptarse al reservar.

#### Scenario: Huecos reales con turnos ya reservados

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant
  T1 con la prestación PREST-30 (30 min), el profesional P1 habilitado y horario
  semanal 09:00 a 12:00 del 2026-10-06, y un turno activo de P1 en el sillón S1
  de 2026-10-06T10:00:00-03:00 a 2026-10-06T10:30:00-03:00
- **WHEN** el paciente pide
  `GET /api/publico/T1/disponibilidad?prestacion=PREST-30&profesional=P1&desde=2026-10-06T00:00:00-03:00`
- **THEN** la respuesta `200` no incluye ningún hueco que solape
  `[2026-10-06T10:00:00-03:00, 2026-10-06T10:30:00-03:00)` y cada hueco ofrecido
  dura 30 min

#### Scenario: Un bloqueo resta disponibilidad

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y el
  profesional P1 con horario 09:00 a 12:00 y un bloqueo del
  2026-10-07T09:00:00-03:00 al 2026-10-07T12:00:00-03:00
- **WHEN** el paciente pide `GET /api/publico/T1/disponibilidad` con
  `desde=2026-10-07T00:00:00-03:00`
- **THEN** la respuesta `200` no ofrece ningún hueco del 2026-10-07

#### Scenario: Sin intersección entre profesional y consultorio

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el
  consultorio con horario 09:00 a 13:00 y el profesional P1 con horario 14:00 a
  18:00 del 2026-10-08
- **WHEN** el paciente pide `GET /api/publico/T1/disponibilidad` con
  `desde=2026-10-08T00:00:00-03:00`
- **THEN** la respuesta `200` devuelve la lista de huecos vacía

#### Scenario: Fin derivado de la prestación

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y la
  prestación PREST-45 con `duracion_min = 45`
- **WHEN** la respuesta `200` de `GET /api/publico/T1/disponibilidad` ofrece un
  hueco que empieza en 2026-10-06T09:00:00-03:00
- **THEN** ese hueco termina en 2026-10-06T09:45:00-03:00

#### Scenario: Un inicio fuera de la grilla o bloqueado se rechaza

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el
  profesional P1 con horario 09:00 a 12:00 del 2026-10-06 y un bloqueo de
  10:00 a 11:00 de ese día, y una verificación válida para reservar en T1
- **WHEN** se envía `POST /api/publico/T1/reservas` con
  `inicio=2026-10-06T10:15:00-03:00` (dentro del bloqueo) y, en otra solicitud,
  con `inicio=2026-10-06T13:00:00-03:00` (fuera de horario)
- **THEN** ambas respuestas son `409` con alternativas reales, ningún turno
  queda persistido y el `200` de disponibilidad nunca había ofrecido esos inicios

#### Scenario: Un hueco retenido por una oferta vigente no se ofrece

- **GIVEN** el reloj del servidor fijado en `2026-10-13T09:00:00-03:00`, el
  profesional P1 libre de 2026-10-14T10:00:00-03:00 a 10:30 y una oferta de
  lista de espera vigente (C-07) reteniendo ese hueco
- **WHEN** el paciente pide `GET /api/publico/T1/disponibilidad` con
  `desde=2026-10-14T00:00:00-03:00`
- **THEN** la respuesta `200` no ofrece el hueco de 2026-10-14T10:00:00-03:00
  mientras la oferta siga vigente, y vuelve a ofrecerlo cuando la oferta vence,
  se cancela o se acepta
