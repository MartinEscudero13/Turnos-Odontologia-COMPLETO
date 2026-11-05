# reserva-publica Specification

## Purpose
Permitir que un paciente reserve, cancele o reprograme un turno por un link
público sin login, viendo sólo huecos reales calculados en el servidor y con la
misma garantía de anti-solapamiento, aislamiento por tenant y privacidad que la
agenda interna.

## Requirements

### Requirement: Disponibilidad pública calculada en el servidor

El sistema SHALL exponer en
`GET /api/publico/{tokenTenant}/disponibilidad?prestacion=&profesional=&desde=`
sólo huecos reales del tenant resuelto, calculados como la intersección del
horario del profesional y del consultorio, menos bloqueos, turnos activos y
huecos retenidos por una oferta de lista de espera vigente (C-07), con la
`duracion_min` de la prestación. `desde` abre una ventana de
`PUBLIC_DISPONIBILIDAD_HORIZONTE_D` días y la respuesta es una lista cronológica.

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

### Requirement: Identificación liviana con vinculación por teléfono

El sistema SHALL crear la reserva pública con nombre y teléfono normalizado E.164,
sin login; si el teléfono ya existe en el tenant, SHALL vincular la reserva al
paciente existente y SHALL NOT crear un paciente duplicado, tampoco ante dos
reservas concurrentes con el mismo teléfono nuevo. La comparación de nombre al
vincular queda en `OQ-8`: este change no la exige ni la prohíbe.

#### Scenario: Teléfono nuevo crea paciente y turno

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant
  T1 sin ningún paciente con el teléfono `+5491100000000` y una verificación
  válida para reservar
- **WHEN** el paciente "Paciente Demo" reserva con nombre "Paciente Demo" y
  teléfono `+54 9 11 0000 0000` para un hueco libre
- **THEN** se crea un paciente nuevo en T1 con teléfono normalizado
  `+5491100000000` y el turno queda asociado a ese paciente con estado `PENDIENTE`

#### Scenario: Teléfono existente vincula sin duplicar

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el
  paciente PACI-1 de T1 con teléfono normalizado `+5491100000000` y un turno suyo,
  y una verificación válida para reservar
- **WHEN** otra reserva pública de T1 usa el mismo teléfono `+5491100000000`
- **THEN** el turno nuevo referencia `PACI-1` y no existe un segundo paciente
  con ese teléfono en T1

#### Scenario: Dos reservas concurrentes con el mismo teléfono nuevo crean un paciente

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant
  T1 sin pacientes con `+5491100000000`, dos huecos libres distintos y una
  verificación válida para cada reserva
- **WHEN** las dos reservas con ese mismo teléfono se procesan en paralelo
- **THEN** ambas responden `201`, existe exactamente un paciente con
  `+5491100000000` en T1 y los dos turnos referencian su mismo `paciente_id`

#### Scenario: Teléfono inválido no crea nada

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant
  T1 sin pacientes y una verificación válida para reservar
- **WHEN** se envía una reserva con teléfono `no-es-un-telefono`
- **THEN** el sistema responde `422` sin crear paciente ni turno

### Requirement: Reserva pública con token y confirmación inmediata

El sistema SHALL crear en `POST /api/publico/{tokenTenant}/reservas` un turno
`PENDIENTE` con `origen=RESERVA_ONLINE` y un `token_publico` UUID v4 único, y
SHALL responder `201` con el turno propio. El payload acepta sólo `prestacion`,
`profesional`, `inicio`, `nombre`, `telefono` y `verificacion_id`; el servidor
deriva `fin` de `duracion_min` y elige un sillón activo libre.
`GET /api/publico/{tokenTenant}/reservas/{token}` SHALL devolver ese mismo turno.

#### Scenario: Reserva creada con token público

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el tenant
  T1 con PREST-30, el profesional P1, los sillones activos S1 y S2, S1 ocupado de
  11:00 a 11:30 del 2026-10-06 y S2 libre, y una verificación válida para reservar
- **WHEN** "Paciente Demo" envía `POST /api/publico/T1/reservas` con
  `prestacion=PREST-30`, `profesional=P1`, `inicio=2026-10-06T11:00:00-03:00`,
  `nombre=Paciente Demo`, `telefono=+5491100000000`, `verificacion_id=VER-1`
- **THEN** la respuesta `201` trae `estado=PENDIENTE`,
  `origen=RESERVA_ONLINE`, `inicio=2026-10-06T11:00:00-03:00`,
  `fin=2026-10-06T11:30:00-03:00` calculado por el servidor, `sillon_id=S2`
  elegido por el servidor y un `token_publico` UUID v4 no vacío

#### Scenario: Cada reserva obtiene un token distinto

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y dos
  reservas consecutivas creadas en el mismo tenant T1
- **WHEN** se comparan sus `token_publico`
- **THEN** los dos tokens son distintos, cada uno es un UUID v4 parseable y
  ninguno coincide con el `turno_id` ni con el `tokenTenant`

#### Scenario: El fin nunca lo fija el cliente

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y el
  payload mínimo válido de reserva (`prestacion`, `profesional`, `inicio`,
  `nombre`, `telefono`, `verificacion_id`) al que se agrega el campo `fin` con
  `2026-10-06T11:15:00-03:00`
- **WHEN** el paciente envía la reserva a `POST /api/publico/T1/reservas`
- **THEN** el sistema responde `422` porque `fin` está fuera del payload
  declarado, y no crea el turno

#### Scenario: Sin sillón libre responde 409 sin turno

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, el
  profesional P1 libre y los únicos sillones activos S1 y S2 ocupados de 11:00 a
  11:30 del 2026-10-06
- **WHEN** el paciente reserva con `inicio=2026-10-06T11:00:00-03:00`
- **THEN** el sistema responde `409` con alternativas reales, ningún turno
  queda persistido y `GET /api/publico/T1/disponibilidad` tampoco ofrecía ese
  inicio

#### Scenario: Un hueco del mismo día es reservable sin lead time adicional

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un hueco
  libre el mismo día de 11:00 a 11:30
- **WHEN** el paciente consulta disponibilidad con `desde=2026-10-05T00:00:00-03:00`
  y reserva ese hueco
- **THEN** el hueco se ofrece y la reserva responde `201`: mientras `OQ-6`
  siga abierta, `C-06` no impone un lead time mínimo adicional al reloj del
  servidor

#### Scenario: Consulta del turno propio por token

- **GIVEN** una reserva `PENDIENTE` de T1 con `token_publico` TOK-B
- **WHEN** se pide `GET /api/publico/T1/reservas/TOK-B`
- **THEN** la respuesta `200` trae sólo `turno_id`, `estado`, `inicio`, `fin`,
  `prestacion` y `token_publico`, sin `tenant_id` ni `paciente_id`

### Requirement: Verificación liviana de un solo uso

El sistema SHALL emitir en `POST /api/publico/{tokenTenant}/verificacion`, con
body `accion` (`reservar`, `cancelar` o `reprogramar`), una verificación de un
solo uso y responder `201` con `verificacion_id`, `expira_at` (`ahora` +
`PUBLIC_VERIFICACION_TTL_MIN`) y `canal` (valor de `PUBLIC_ANTISPAM_MODO`; captcha
u OTP queda en `OQ-2`). Las tres acciones SHALL exigir un `verificacion_id`
válido, no vencido y no consumido, y SHALL responder `403` sin mutar estado si no
lo hay.

#### Scenario: Emisión de una verificación válida

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y el tenant
  T1 con `PUBLIC_VERIFICACION_TTL_MIN = 10` y `PUBLIC_ANTISPAM_MODO` configurado
- **WHEN** se envía `POST /api/publico/T1/verificacion` con
  `accion=reservar`
- **THEN** la respuesta `201` trae un `verificacion_id` no vacío,
  `expira_at=2026-10-05T09:10:00-03:00` y `canal` igual al valor configurado de
  `PUBLIC_ANTISPAM_MODO`, sin fijar aquí si es captcha u OTP (`OQ-2`)

#### Scenario: Verificación vencida responde 403 sin mutar

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:11:00-03:00`, una
  verificación emitida a las 09:00 con `PUBLIC_VERIFICACION_TTL_MIN = 10` y un
  hueco libre en T1
- **WHEN** se intenta reservar ese hueco con ese `verificacion_id`
- **THEN** el sistema responde `403`, no crea el turno y el hueco sigue
  ofreciéndose en `GET /api/publico/T1/disponibilidad`

#### Scenario: La verificación es de un solo uso

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y una
  verificación ya consumida por una reserva exitosa en T1
- **WHEN** se reutiliza la misma verificación para una segunda reserva
- **THEN** el sistema responde `403` y no crea el segundo turno

#### Scenario: Reuso concurrente de la misma verificación

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, una sola
  verificación válida y dos solicitudes simultáneas de T1 para el mismo hueco
- **WHEN** ambas se procesan en paralelo con ese `verificacion_id`
- **THEN** exactamente una responde `201`, la otra responde `403` y queda un
  solo turno persistido en ese horario

#### Scenario: Acción sin verificación válida se rechaza

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y el tenant
  T1 con el hueco de 2026-10-06T11:00:00-03:00 libre
- **WHEN** se envía `POST /api/publico/T1/reservas` sin la verificación liviana
- **THEN** el sistema responde `403` y el hueco sigue ofreciéndose en
  `GET /api/publico/T1/disponibilidad`

#### Scenario: Verificación válida permite reservar

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y una
  verificación liviana válida, no consumida y no vencida para T1
- **WHEN** se envía la reserva de un hueco libre
- **THEN** el sistema responde `201` con el turno en estado `PENDIENTE`

### Requirement: Rate-limit por IP y por tenant

El sistema SHALL limitar las acciones públicas por `(tenant, IP)` y por
`(tenant, acción)` a `PUBLIC_RATE_LIMIT_MAX` solicitudes por
`PUBLIC_RATE_LIMIT_VENTANA_S` segundos (valores en `OQ-3`); al excederlo SHALL
responder `429` con `Retry-After` sin mutar estado, sin revelar si el hueco o el
turno existen.

#### Scenario: Rate-limit por IP excedido no muta estado

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un mismo
  origen que supera `PUBLIC_RATE_LIMIT_MAX` solicitudes en
  `PUBLIC_RATE_LIMIT_VENTANA_S` segundos sobre T1
- **WHEN** envía una reserva más
- **THEN** el sistema responde `429` con `Retry-After` y no crea el turno

#### Scenario: Rate-limit por tenant frena una IP nueva

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y
  `PUBLIC_RATE_LIMIT_MAX` solicitudes de reserva en T1 hechas desde IP distintas
  dentro de `PUBLIC_RATE_LIMIT_VENTANA_S`
- **WHEN** una IP que no había participado envía otra reserva a T1
- **THEN** el sistema responde `429` con `Retry-After` y no crea el turno

### Requirement: Cancelar y reprogramar con anticipación mínima

Con `token_publico` válido y la verificación de la acción, el paciente SHALL poder
cancelar o reprogramar su turno sólo si falta al menos `CANCEL_ANTICIPACION_H`
antes del inicio (default 24 h); por debajo del umbral la acción pública SHALL
responder `403` sin mutar el turno, derivar a recepción y dejar una entrada de
auditoría del rechazo.

#### Scenario: Exactamente en el umbral se acepta

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00`, un turno
  de T1 que inicia exactamente 24 h después (`2026-10-21T09:00:00-03:00`), estado
  `PENDIENTE`, `CANCEL_ANTICIPACION_H = 24` y una verificación válida para cancelar
- **WHEN** con su `token_publico` se envía
  `POST /api/publico/T1/reservas/TOK-C/cancelacion` con `verificacion_id=VER-2`
- **THEN** el sistema responde `200` y el turno queda en estado `CANCELADO`

#### Scenario: Un minuto por debajo del umbral se rechaza sin mutar

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:01:00-03:00`, un turno
  de T1 que inicia en `2026-10-21T09:00:00-03:00` (23 h 59 min),
  `CANCEL_ANTICIPACION_H = 24` y una verificación válida para cancelar
- **WHEN** con su `token_publico` se envía
  `POST /api/publico/T1/reservas/TOK-C/cancelacion`
- **THEN** el sistema responde `403`, indica que debe gestionarse en
  recepción y el turno conserva estado `PENDIENTE` y horario

#### Scenario: El rechazo bajo el umbral queda auditado

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:01:00-03:00` y un turno
  de T1 que inicia en `2026-10-21T09:00:00-03:00` con `CANCEL_ANTICIPACION_H = 24`
- **WHEN** la cancelación pública responde `403` por estar bajo el umbral
- **THEN** existe una entrada append-only `CANCELACION_RECHAZADA` del turno,
  con motivo `BAJO_ANTICIPACION`, `antes=PENDIENTE`, `despues=PENDIENTE` y sin
  nombre ni teléfono

#### Scenario: La cancelación pública libera el hueco

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un turno
  de T1 del 2026-10-06 de 10:00 a 10:30 (`-03:00`) cancelado con anticipación
  suficiente por su paciente
- **WHEN** se pide disponibilidad para ese profesional y sillón desde
  `2026-10-06T00:00:00-03:00`
- **THEN** el hueco de 2026-10-06T10:00:00-03:00 vuelve a ofrecerse

#### Scenario: Reprogramación pública exitosa

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00`, un turno
  `PENDIENTE` de T1 el 2026-10-21 de 10:00 a 10:30 (`-03:00`) y el hueco de 14:00
  a 14:30 libre, con verificación válida para reprogramar
- **WHEN** el paciente reprograma a `2026-10-21T14:00:00-03:00` con su
  `token_publico` y `verificacion_id=VER-3`
- **THEN** el sistema responde `200`, el turno original queda `REPROGRAMADO`,
  se crea un turno `PENDIENTE` de 14:00 a 14:30 y el `token_publico` sigue
  gestionando el turno nuevo

#### Scenario: Reprogramar bajo el umbral se rechaza sin mutar

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:01:00-03:00`, un turno
  `PENDIENTE` de T1 que inicia en `2026-10-21T09:00:00-03:00`, el hueco de 14:00
  a 14:30 libre y una verificación válida para reprogramar
- **WHEN** el paciente intenta reprogramar a `2026-10-21T14:00:00-03:00`
- **THEN** el sistema responde `403`, el turno original conserva
  `inicio=2026-10-21T09:00:00-03:00` y estado `PENDIENTE`, no se crea turno nuevo
  y queda la entrada `REPROGRAMACION_RECHAZADA` con motivo `BAJO_ANTICIPACION`

#### Scenario: Reprogramar a un hueco ocupado no toca el original

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, un turno
  PENDIENTE de T1 el 2026-10-12 de 10:00 a 10:30 (`-03:00`) y otro turno activo
  de 14:00 a 14:30 del mismo profesional y sillón
- **WHEN** el paciente reprograma su turno a 2026-10-12T14:15:00-03:00 con su
  `token_publico` y una verificación válida
- **THEN** el sistema responde `409` con hasta 3 alternativas y el turno
  original conserva `inicio=2026-10-12T10:00:00-03:00` y estado `PENDIENTE`

#### Scenario: Cancelar sin verificación válida no muta

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00` y un turno
  `PENDIENTE` de T1 que inicia el `2026-10-21T09:00:00-03:00` con
  `CANCEL_ANTICIPACION_H = 24`
- **WHEN** se envía `POST /api/publico/T1/reservas/TOK-C/cancelacion` sin
  `verificacion_id`
- **THEN** el sistema responde `403`, el turno conserva `PENDIENTE` y no
  aparece la entrada `CANCELADO` en la auditoría

#### Scenario: Reprogramar sin verificación válida no muta

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00` y un turno
  `PENDIENTE` de T1 el 2026-10-21 de 10:00 a 10:30 (`-03:00`) con un hueco libre
  a las 14:00
- **WHEN** se envía la reprogramación con su `token_publico` sin
  `verificacion_id`
- **THEN** el sistema responde `403`, el original conserva `PENDIENTE` en
  10:00 y no se crea turno nuevo

### Requirement: Hueco tomado, concurrencia y prohibición de sobreturno

Si el hueco elegido deja de estar libre al confirmar, el sistema SHALL responder
`409` con hasta 3 alternativas reales (las que existan) y SHALL NOT crear el
turno; ante reservas concurrentes del mismo hueco, exactamente una SHALL
persistir. Las rutas públicas SHALL NOT crear sobreturnos: el solape se rechaza,
nunca se convierte en sobreturno.

#### Scenario: Slot tomado entre pasos responde 409 con alternativas

- **GIVEN** el reloj del servidor fijado en `2026-10-12T09:00:00-03:00`, un
  paciente que vio libre el hueco de 2026-10-13T10:00:00-03:00 y, antes de
  confirmar, recepción ocupa ese hueco de 10:00 a 10:30
- **WHEN** el paciente confirma el hueco que había visto con una verificación
  válida
- **THEN** el sistema responde `409` con hasta 3 alternativas en orden
  cronológico y no crea ningún turno para el paciente

#### Scenario: Dos reservas concurrentes del mismo hueco

- **GIVEN** el reloj del servidor fijado en `2026-10-12T09:00:00-03:00` y dos
  solicitudes públicas simultáneas de T1 para el mismo hueco de
  2026-10-13T11:00:00-03:00, con una verificación válida cada una
- **WHEN** ambas se procesan en paralelo
- **THEN** exactamente una responde `201`, la otra responde `409` con hasta 3
  alternativas y queda un solo turno persistido en ese horario

#### Scenario: El público no puede crear sobreturno

- **GIVEN** el reloj del servidor fijado en `2026-10-12T09:00:00-03:00` y un
  payload de reserva pública que incluye `sobreturno: true`
- **WHEN** se envía a `POST /api/publico/T1/reservas`
- **THEN** el sistema responde `422` y no persiste ningún turno con
  `sobreturno=true`

#### Scenario: El solape por sillón no se degrada a sobreturno

- **GIVEN** el reloj del servidor fijado en `2026-10-13T09:00:00-03:00` y el sillón
  S1 de T1 ocupado de 2026-10-14T11:00:00-03:00 a 2026-10-14T11:30:00-03:00 por
  otro profesional
- **WHEN** el paciente reserva con el profesional P2 en S1 desde
  2026-10-14T11:15:00-03:00
- **THEN** el sistema responde `409` con hasta 3 alternativas y no crea el
  turno

### Requirement: Aislamiento multi-tenant en las rutas públicas

Toda ruta pública SHALL resolver el tenant desde el segmento `{tokenTenant}` de
`/api/publico/{tokenTenant}/...` y acotar lecturas y escrituras a ese `tenant_id`;
un `tokenTenant` inexistente o de un tenant con `activo=false` SHALL responder
`404`, y un `token_publico` de otro tenant SHALL responder `404` idéntico al de un
token inexistente, sin revelar su existencia.

#### Scenario: Token de un tenant en la ruta de otro

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un turno
  activo del tenant T1 con `token_publico` TOK-A
- **WHEN** se usa `GET /api/publico/T2/reservas/TOK-A`
- **THEN** el sistema responde `404` sin devolver datos del turno de T1

#### Scenario: La disponibilidad no se contamina entre tenants

- **GIVEN** el reloj del servidor fijado en `2026-10-14T09:00:00-03:00`, el
  profesional P1 y el sillón S1 ocupados en T1 el 2026-10-15 de 10:00 a 10:30
  (`-03:00`) y libres en T2 a la misma hora
- **WHEN** se pide disponibilidad pública de T2 desde
  2026-10-15T00:00:00-03:00
- **THEN** el hueco de 2026-10-15T10:00:00-03:00 se ofrece en T2 y no en T1

#### Scenario: Una reserva en un tenant no escribe en otro

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y los
  tenants T1 y T2 con el mismo hueco libre
- **WHEN** se crea una reserva pública en T2
- **THEN** T1 sigue sin turnos en ese horario

#### Scenario: Los headers de actor no cambian el tenant público

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y un
  request a `POST /api/publico/T2/reservas` con `X-Tenant-Id: T1` y `X-Rol: ADMIN`
- **WHEN** el sistema procesa la reserva
- **THEN** la reserva queda en T2 con `origen=RESERVA_ONLINE` y no se aplica
  ningún permiso de `ADMIN`

#### Scenario: tokenTenant inexistente o tenant inactivo responde 404

- **GIVEN** un `tokenTenant=NO-EXISTE` sin tenant y un tenant T3 con
  `activo=false` y `tokenTenant=T3`
- **WHEN** se piden `GET /api/publico/NO-EXISTE/disponibilidad` y
  `GET /api/publico/T3/disponibilidad`
- **THEN** ambas respuestas son `404` con el mismo cuerpo, sin `tenant_id` ni
  datos de agenda

### Requirement: Privacidad de respuestas y logs

Las respuestas públicas SHALL contener sólo datos del hueco y del turno propio;
SHALL NOT exponer nombre, teléfono ni dato clínico de otros pacientes, y los logs
SHALL NOT registrar PHI.

#### Scenario: La disponibilidad no expone pacientes

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y la
  disponibilidad de T1 con turnos activos de dos pacientes distintos
- **WHEN** el paciente consulta `GET /api/publico/T1/disponibilidad`
- **THEN** ninguna entrada incluye `paciente_id`, nombre, teléfono ni dato
  clínico

#### Scenario: La reserva sólo devuelve el turno propio

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00`, T1 con la
  reserva de "Paciente Demo" y otro turno activo de "Otro Paciente Demo" con
  teléfono `+5491100000001`
- **WHEN** se lee la respuesta `201` de la reserva de "Paciente Demo"
- **THEN** sus únicas claves son `turno_id`, `estado`, `inicio`, `fin`,
  `origen`, `prestacion`, `sillon_id` y `token_publico`, y no aparece el nombre ni
  el teléfono de "Otro Paciente Demo"

#### Scenario: El 404 no filtra si el turno existe en otro tenant

- **GIVEN** un token inexistente y un token real de T1 usados en la ruta pública
  de T2
- **WHEN** se comparan ambas respuestas de `GET /api/publico/T2/reservas/{token}`
- **THEN** ambas son `404` con el mismo cuerpo, sin `tenant_id`, nombre ni
  teléfono

#### Scenario: Los logs no contienen PHI

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y una
  reserva pública exitosa en T1
- **WHEN** se inspecciona el registro estructurado de la operación
- **THEN** sólo aparecen identificadores (`tenant_id`, `turno_id`), estado y
  horarios; no aparecen nombre, teléfono ni token

### Requirement: Trazabilidad de las acciones públicas

Toda reserva, cancelación y reprogramación pública SHALL dejar una entrada
append-only en la auditoría del tenant con actor público, antes/después y sin PHI;
todo rechazo por anticipación insuficiente SHALL dejar además su entrada de
rechazo con motivo.

#### Scenario: La reserva pública queda auditada

- **GIVEN** el reloj del servidor fijado en `2026-10-05T09:00:00-03:00` y una
  reserva pública exitosa en T1
- **WHEN** se consulta la auditoría del turno
- **THEN** existe una entrada `CREADO` con actor público, `antes` vacío,
  `despues=PENDIENTE` y sin nombre ni teléfono

#### Scenario: Cancelación pública audita el antes y el después

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00` y un turno
  `PENDIENTE` de T1 cancelado por el paciente con anticipación suficiente
- **WHEN** se consulta la auditoría del turno
- **THEN** existe una entrada `CANCELADO` con `antes=PENDIENTE` y
  `despues=CANCELADO`

#### Scenario: La reprogramación pública audita el antes y el después

- **GIVEN** el reloj del servidor fijado en `2026-10-20T09:00:00-03:00` y un turno
  `PENDIENTE` de T1 el 2026-10-21 de 10:00 a 10:30 (`-03:00`) reprogramado con
  anticipación suficiente
- **WHEN** se consulta la auditoría del turno original
- **THEN** existe una entrada `REPROGRAMADO` con `antes=PENDIENTE` y
  `despues=REPROGRAMADO`, y el turno nuevo tiene su entrada `CREADO`

### Requirement: Catálogo público de prestaciones y profesionales

El sistema SHALL exponer `GET /api/publico/{tokenTenant}/catalogo`, resolviendo
el tenant desde `{tokenTenant}`, con las prestaciones activas (`id`, `nombre`,
`duracion_min`) y los profesionales activos (`id`, `nombre`). La respuesta SHALL
NOT incluir `tenant_id`, precios, datos de pacientes ni horarios, y SHALL ser de
solo lectura: permite elegir `prestacion`/`profesional` antes de pedir huecos,
sin reemplazar el cálculo de disponibilidad.

#### Scenario: Catálogo del tenant con datos sembrados

- **GIVEN** el tenant T1 con las prestaciones `PREST-30` (`Consulta`, 30 min) y
  `PREST-45` (`Limpieza`, 45 min), y los profesionales activos `P1` (`Dra. Demo`)
  y `P2` (`Dr. Ejemplo`), y el tenant T2 con datos distintos
- **WHEN** el paciente pide `GET /api/publico/T1/catalogo`
- **THEN** la respuesta `200` incluye exactamente las dos prestaciones de T1 con
  `id`, `nombre` y `duracion_min`, y los dos profesionales de T1 con `id` y
  `nombre`, sin datos de T2

#### Scenario: Allow-list sin PHI ni claves internas

- **GIVEN** un catálogo sembrado con prestaciones y profesionales
- **WHEN** se inspeccionan las claves de la respuesta `200`
- **THEN** cada prestación expone solo `id`, `nombre` y `duracion_min`, cada
  profesional solo `id` y `nombre`, y no aparecen `tenant_id`, `precio_base`,
  `paciente_id`, nombre/teléfono de pacientes ni horarios

#### Scenario: tokenTenant inexistente responde 404 uniforme

- **GIVEN** un `tokenTenant` que no resuelve a ningún tenant activo
- **WHEN** se pide `GET /api/publico/NO-EXISTE/catalogo`
- **THEN** la respuesta es `404` con `detalle` uniforme y lista de alternativas
  vacía, sin listas de prestaciones ni profesionales

#### Scenario: Tenant sin catálogo devuelve listas vacías

- **GIVEN** el tenant T3 activo pero sin prestaciones ni profesionales sembrados
- **WHEN** el paciente pide `GET /api/publico/T3/catalogo`
- **THEN** la respuesta `200` es `{"prestaciones": [], "profesionales": []}` sin
  inventar datos
