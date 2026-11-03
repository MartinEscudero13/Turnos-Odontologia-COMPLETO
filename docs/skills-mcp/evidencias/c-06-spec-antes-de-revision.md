# Spec Delta — reserva-publica

## Purpose

Permitir que un paciente reserve, cancele o reprograme un turno por un link
público sin login, viendo sólo huecos reales calculados en el servidor y con la
misma garantía de anti-solapamiento, aislamiento por tenant y privacidad que la
agenda interna.

## ADDED Requirements

### Requirement: Disponibilidad pública calculada en el servidor

El sistema SHALL exponer en `GET /api/disponibilidad?prestacion=&profesional=&desde=`
sólo huecos reales del tenant resuelto, calculados servidor-side como
intersección de horario del profesional y del consultorio, menos bloqueos
vigentes, con la `duracion_min` de la prestación. Ningún horario propuesto por el
cliente SHALL aceptarse fuera de ese cálculo.

#### Scenario: Huecos reales con turnos ya reservados

- **DADO** el tenant T1 con la prestación PREST-30 (30 min), el profesional P1
  habilitado y horario semanal 09:00 a 12:00 del 2026-10-06, y un turno activo
  de P1 en el sillón S1 de 2026-10-06T10:00:00-03:00 a 2026-10-06T10:30:00-03:00
- **CUANDO** el paciente pide
  `GET /api/disponibilidad?prestacion=PREST-30&profesional=P1&desde=2026-10-06T00:00:00-03:00`
- **ENTONCES** la respuesta `200` no incluye ningún hueco que solape
  `[2026-10-06T10:00:00-03:00, 2026-10-06T10:30:00-03:00)` y cada hueco ofrecido
  dura 30 min

#### Scenario: Un bloqueo resta disponibilidad

- **DADO** el profesional P1 con horario 09:00 a 12:00 y un bloqueo del
  2026-10-07T09:00:00-03:00 al 2026-10-07T12:00:00-03:00
- **CUANDO** el paciente pide disponibilidad desde 2026-10-07T00:00:00-03:00
- **ENTONCES** la respuesta `200` no ofrece ningún hueco del 2026-10-07

#### Scenario: Sin intersección entre profesional y consultorio

- **DADO** el consultorio con horario 09:00 a 13:00 y el profesional P1 con
  horario 14:00 a 18:00 del 2026-10-08
- **CUANDO** el paciente pide disponibilidad desde 2026-10-08T00:00:00-03:00
- **ENTONCES** la respuesta `200` devuelve la lista de huecos vacía

#### Scenario: Fin derivado de la prestación

- **DADO** la prestación PREST-45 con `duracion_min = 45`
- **CUANDO** la respuesta ofrece un hueco que empieza en 2026-10-06T09:00:00-03:00
- **ENTONCES** ese hueco termina en 2026-10-06T09:45:00-03:00

### Requirement: Identificación liviana con vinculación por teléfono

El sistema SHALL crear la reserva pública con nombre y teléfono normalizado, sin
login; si el teléfono ya existe en el tenant, SHALL vincular la reserva al
paciente existente y SHALL NOT crear un paciente duplicado.

#### Scenario: Teléfono nuevo crea paciente y turno

- **DADO** el tenant T1 sin ningún paciente con el teléfono `0000-0000`
- **CUANDO** el paciente "Paciente Demo" reserva con nombre "Paciente Demo" y
  teléfono `0000-0000` para un hueco libre
- **ENTONCES** se crea un paciente nuevo en T1 y el turno queda asociado a ese
  paciente con estado `PENDIENTE`

#### Scenario: Teléfono existente vincula sin duplicar

- **DADO** el paciente PACI-1 de T1 con teléfono normalizado `+540000000000` y un
  turno suyo
- **CUANDO** otra reserva pública de T1 usa el mismo teléfono `+540000000000`
- **ENTONCES** el turno nuevo referencia `PACI-1` y no existe un segundo paciente
  con ese teléfono en T1

#### Scenario: Teléfono inválido no crea nada

- **DADO** el tenant T1 sin pacientes
- **CUANDO** se envía una reserva con teléfono `no-es-un-telefono`
- **ENTONCES** el sistema responde `422` sin crear paciente ni turno

### Requirement: Reserva pública con token y confirmación inmediata

El sistema SHALL crear en `POST /api/reservas/publicas` un turno `PENDIENTE` con
`origen=RESERVA_ONLINE` y un `token_publico` único e impredecible, y SHALL
responder `201` con la confirmación y el token con el que el paciente gestiona su
turno.

#### Scenario: Reserva creada con token público

- **DADO** el tenant T1 con un hueco libre el 2026-10-06 de 11:00 a 11:30
  (`-03:00`) y el teléfono `0000-0000` sin paciente previo
- **CUANDO** "Paciente Demo" confirma la reserva de ese hueco
- **ENTONCES** la respuesta `201` trae el turno en estado `PENDIENTE`,
  `origen=RESERVA_ONLINE`, `fin=2026-10-06T11:30:00-03:00` calculado por el
  servidor y un `token_publico` no vacío

#### Scenario: Cada reserva obtiene un token distinto

- **DADO** dos reservas consecutivas creadas en el mismo tenant T1
- **CUANDO** se comparan sus `token_publico`
- **ENTONCES** los dos tokens son distintos y ninguno es un número secuencial

#### Scenario: El fin nunca lo fija el cliente

- **DADO** un payload de reserva que incluye un campo `fin` con
  `2026-10-06T11:15:00-03:00`
- **CUANDO** el paciente envía la reserva
- **ENTONCES** el sistema responde `422` y no crea el turno

### Requirement: Verificación liviana y rate-limit anti-spam

El sistema SHALL exigir en cada acción pública una verificación liviana de un solo
uso y SHALL aplicar rate-limit por IP y por tenant; una acción sin verificación
válida SHALL responder `403` y una acción por encima del límite SHALL responder
`429`, sin mutar estado en ningún caso.

#### Scenario: Acción sin verificación válida se rechaza

- **DADO** el tenant T1 con el hueco de 2026-10-06T11:00:00-03:00 libre
- **CUANDO** se envía `POST /api/reservas/publicas` sin la verificación liviana
- **ENTONCES** el sistema responde `403` y el hueco sigue ofreciéndose en
  `GET /api/disponibilidad`

#### Scenario: La verificación es de un solo uso

- **DADO** una verificación ya consumida por una reserva exitosa en T1
- **CUANDO** se reutiliza la misma verificación para una segunda reserva
- **ENTONCES** el sistema responde `403` y no crea el segundo turno

#### Scenario: Rate-limit excedido no muta estado

- **DADO** un mismo origen que supera `PUBLIC_RATE_LIMIT_MAX` solicitudes en
  `PUBLIC_RATE_LIMIT_VENTANA_S` segundos sobre T1
- **CUANDO** envía una reserva más
- **ENTONCES** el sistema responde `429` con `Retry-After` y no crea el turno

#### Scenario: Verificación válida permite reservar

- **DADO** una verificación liviana válida, no consumida y no vencida para T1
- **CUANDO** se envía la reserva de un hueco libre
- **ENTONCES** el sistema responde `201` con el turno en estado `PENDIENTE`

### Requirement: Cancelar y reprogramar con anticipación mínima

Con `token_publico` válido, el paciente SHALL poder cancelar o reprogramar su
turno sólo si falta al menos `CANCEL_ANTICIPACION_H` antes del inicio (default
24 h); por debajo del umbral la acción pública SHALL rechazarse sin mutar el turno
y derivar a recepción.

#### Scenario: Exactamente en el umbral se acepta

- **DADO** un turno de T1 con `inicio = 2026-10-10T10:00:00-03:00`, estado
  `PENDIENTE` y `CANCEL_ANTICIPACION_H = 24`
- **CUANDO** con su `token_publico` se cancela el 2026-10-09T10:00:00-03:00
- **ENTONCES** el sistema responde `200` y el turno queda en estado `CANCELADO`

#### Scenario: Un minuto por debajo del umbral se rechaza sin mutar

- **DADO** el mismo turno de T1 con `inicio = 2026-10-10T10:00:00-03:00` y
  `CANCEL_ANTICIPACION_H = 24`
- **CUANDO** con su `token_publico` se cancela el 2026-10-09T10:01:00-03:00
- **ENTONCES** el sistema responde `403`, indica que debe gestionarse en
  recepción y el turno conserva estado `PENDIENTE` y horario

#### Scenario: La cancelación pública libera el hueco

- **DADO** un turno de T1 del 2026-10-06 de 10:00 a 10:30 (`-03:00`) cancelado
  con anticipación suficiente por su paciente
- **CUANDO** se pide disponibilidad para ese profesional y sillón desde
  2026-10-06T00:00:00-03:00
- **ENTONCES** el hueco de 2026-10-06T10:00:00-03:00 vuelve a ofrecerse

#### Scenario: Reprogramar a un hueco ocupado no toca el original

- **DADO** un turno PENDIENTE de T1 el 2026-10-12 de 10:00 a 10:30 (`-03:00`) y
  otro turno activo de 14:00 a 14:30 del mismo profesional y sillón
- **CUANDO** el paciente reprograma su turno a 2026-10-12T14:15:00-03:00 con su
  `token_publico`
- **ENTONCES** el sistema responde `409` con 3 alternativas y el turno original
  conserva `inicio=2026-10-12T10:00:00-03:00` y estado `PENDIENTE`

### Requirement: Hueco tomado, concurrencia y prohibición de sobreturno

Si el hueco elegido deja de estar libre al confirmar, el sistema SHALL responder
`409` con 3 alternativas reales y SHALL NOT crear el turno; ante reservas
concurrentes del mismo hueco, exactamente una SHALL persistir. Las rutas públicas
SHALL NOT crear sobreturnos: el solape se rechaza, nunca se convierte en
sobreturno.

#### Scenario: Slot tomado entre pasos responde 409 con alternativas

- **DADO** un paciente que vio libre el hueco de 2026-10-13T10:00:00-03:00 y,
  antes de confirmar, recepción ocupa ese hueco de 10:00 a 10:30
- **CUANDO** el paciente confirma el hueco que había visto
- **ENTONCES** el sistema responde `409` con exactamente 3 alternativas en orden
  cronológico y no crea ningún turno para el paciente

#### Scenario: Dos reservas concurrentes del mismo hueco

- **DADO** dos solicitudes públicas simultáneas de T1 para el mismo hueco de
  2026-10-13T11:00:00-03:00 y con verificación válida cada una
- **CUANDO** ambas se procesan en paralelo
- **ENTONCES** exactamente una responde `201`, la otra responde `409` con 3
  alternativas y queda un solo turno persistido en ese horario

#### Scenario: El público no puede crear sobreturno

- **DADO** un payload de reserva pública que incluye `sobreturno: true`
- **CUANDO** se envía a `POST /api/reservas/publicas`
- **ENTONCES** el sistema responde `422` y no persiste ningún turno con
  `sobreturno=true`

#### Scenario: El solape por sillón no se degrada a sobreturno

- **DADO** el sillón S1 de T1 ocupado de 2026-10-14T11:00:00-03:00 a
  2026-10-14T11:30:00-03:00 por otro profesional
- **CUANDO** el paciente reserva con el profesional P2 en S1 desde
  2026-10-14T11:15:00-03:00
- **ENTONCES** el sistema responde `409` con 3 alternativas y no crea el turno

### Requirement: Aislamiento multi-tenant en las rutas públicas

Toda ruta pública SHALL resolver el tenant desde `/r/:tokenTenant` y acotar
lecturas y escrituras a ese `tenant_id`; un `token_publico` de otro tenant SHALL
responder `404`, idéntico al de un token inexistente, sin revelar su existencia.

#### Scenario: Token de un tenant en la ruta de otro

- **DADO** un turno activo del tenant T1 con `token_publico` TOK-A
- **CUANDO** se usa TOK-A en una ruta pública del tenant T2
- **ENTONCES** el sistema responde `404` sin devolver datos del turno de T1

#### Scenario: La disponibilidad no se contamina entre tenants

- **DADO** el profesional P1 y el sillón S1 ocupados en T1 el 2026-10-15 de 10:00
  a 10:30 (`-03:00`) y libres en T2 a la misma hora
- **CUANDO** se pide disponibilidad pública de T2 desde
  2026-10-15T00:00:00-03:00
- **ENTONCES** el hueco de 2026-10-15T10:00:00-03:00 se ofrece en T2

#### Scenario: Una reserva en un tenant no escribe en otro

- **DADO** los tenants T1 y T2 con el mismo hueco libre
- **CUANDO** se crea una reserva pública en T2
- **ENTONCES** T1 sigue sin turnos en ese horario

#### Scenario: Los headers de actor no cambian el tenant público

- **DADO** un request a la ruta pública de T2 con `X-Tenant-Id: T1` y
  `X-Rol: ADMIN`
- **CUANDO** el sistema procesa la reserva
- **ENTONCES** la reserva queda en T2 con `origen=RESERVA_ONLINE` y no se aplica
  ningún permiso de `ADMIN`

### Requirement: Privacidad de respuestas y logs

Las respuestas públicas SHALL contener sólo datos del hueco y del turno propio;
SHALL NOT exponer nombre, teléfono ni dato clínico de otros pacientes, y los logs
SHALL NOT registrar PHI.

#### Scenario: La disponibilidad no expone pacientes

- **DADO** la disponibilidad de T1 con turnos activos de otros pacientes
- **CUANDO** el paciente consulta `GET /api/disponibilidad`
- **ENTONCES** ninguna entrada incluye `paciente_id`, nombre, teléfono ni dato
  clínico

#### Scenario: La reserva sólo devuelve el turno propio

- **DADO** una reserva exitosa de "Paciente Demo" en T1
- **CUANDO** se lee la respuesta `201`
- **ENTONCES** contiene el turno propio y su token, y no contiene el teléfono ni
  el nombre de ningún otro paciente

#### Scenario: El 404 no filtra si el turno existe en otro tenant

- **DADO** un token inexistente y un token real de T1 usados en la ruta pública
  de T2
- **CUANDO** se comparan ambas respuestas
- **ENTONCES** ambas son `404` con el mismo cuerpo, sin `tenant_id`, nombre ni
  teléfono

#### Scenario: Los logs no contienen PHI

- **DADO** una reserva pública exitosa en T1
- **CUANDO** se inspecciona el registro estructurado de la operación
- **ENTONCES** sólo aparecen identificadores (`tenant_id`, `turno_id`), estado y
  horarios; no aparecen nombre, teléfono ni token

### Requirement: Trazabilidad de las acciones públicas

Toda reserva, cancelación y reprogramación pública SHALL dejar una entrada
append-only en la auditoría del tenant con actor público, antes/después y sin PHI.

#### Scenario: La reserva pública queda auditada

- **DADO** una reserva pública exitosa en T1
- **CUANDO** se consulta la auditoría del turno
- **ENTONCES** existe una entrada `CREADO` con actor público, `antes` vacío,
  `despues=PENDIENTE` y sin nombre ni teléfono

#### Scenario: Cancelación pública audita el antes y el después

- **DADO** un turno `PENDIENTE` de T1 cancelado por el paciente con anticipación
  suficiente
- **CUANDO** se consulta la auditoría del turno
- **ENTONCES** existe una entrada `CANCELADO` con `antes=PENDIENTE` y
  `despues=CANCELADO`
