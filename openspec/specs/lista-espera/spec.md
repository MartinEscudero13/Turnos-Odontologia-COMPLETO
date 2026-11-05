# lista-espera Specification

## Purpose
Permitir que el consultorio mantenga una lista de espera por paciente y
prestación, y que todo hueco liberado por cancelación o reprogramación se ofrezca
automáticamente a las entradas compatibles, con expiración y rotación, antes de
volver a la disponibilidad general.

## Requirements

### Requirement: Alta en lista de espera

El sistema SHALL permitir a recepción/admin dar de alta una entrada en
`POST /api/lista-espera` con `paciente_id`, `prestacion_id`,
`profesional_pref` (opcional) y `ventana_desde`/`ventana_hasta` (opcionales),
siempre del mismo `tenant_id`; la entrada SHALL nacer en estado `PENDIENTE`.

#### Scenario: Alta válida crea entrada PENDIENTE

- **GIVEN** el tenant T1 con el paciente PACI-1 y la prestación PREST-30
- **WHEN** recepción da de alta a PACI-1 para PREST-30 sin preferencia de
  profesional
- **THEN** se persiste una entrada `PENDIENTE` de T1 con `paciente_id=PACI-1` y
  `prestacion_id=PREST-30`

#### Scenario: Paciente o prestación de otro tenant se rechaza

- **GIVEN** el tenant T1 y un paciente PACI-1 que pertenece al tenant T2
- **WHEN** recepción de T1 intenta dar de alta a PACI-1 (de T2) o a una
  prestación de T2
- **THEN** el sistema responde `404` y no crea ninguna entrada en T1

#### Scenario: Alta duplicada para la misma prestación se rechaza

- **GIVEN** T1 con PACI-1 ya `PENDIENTE` para PREST-30
- **WHEN** recepción da de alta otra vez a PACI-1 para PREST-30
- **THEN** el sistema responde `409` y no crea una segunda entrada activa para
  esa misma pareja (paciente, prestación)

### Requirement: Baja de la lista de espera

El sistema SHALL permitir dar de baja una entrada (`DELETE /api/lista-espera/{id}`)
pasándola a estado `VENCIDO`; si la entrada tenía una oferta vigente, esa oferta
SHALL anularse (`CANCELADA`) y el hueco retenido SHALL volver a ofrecerse o
público según corresponda.

#### Scenario: Baja de una entrada PENDIENTE

- **GIVEN** T1 con una entrada `PENDIENTE` de PACI-1 para PREST-30
- **WHEN** recepción da de baja esa entrada
- **THEN** la entrada pasa a `VENCIDO` y deja de aparecer en el listado activo

#### Scenario: Baja con oferta vigente anula la oferta

- **GIVEN** T1 con una entrada `OFRECIDO` que tiene una oferta `PENDIENTE` sobre
  un hueco liberado
- **WHEN** recepción da de baja esa entrada antes de que expire la oferta
- **THEN** la entrada pasa a `VENCIDO`, la oferta pasa a `CANCELADA` y el hueco
  deja de estar retenido (queda público si no hay otro compatible)

### Requirement: Listado de la lista de espera

El sistema SHALL exponer `GET /api/lista-espera` (opcionalmente filtrada por
`prestacion` y/o `profesional`) devolviendo las entradas activas del tenant en
orden de fecha de alta, sin exponer datos de otros tenants.

#### Scenario: Listado ordenado por fecha de alta

- **GIVEN** T1 con PACI-1 (alta 09:00) y PACI-2 (alta 10:00) ambos `PENDIENTE`
  para PREST-30
- **WHEN** recepción lista la lista de espera de T1 para PREST-30
- **THEN** la respuesta devuelve PACI-1 antes que PACI-2 y no incluye entradas de
  otros tenants

#### Scenario: Listado no filtra entradas ajenas

- **GIVEN** T1 y T2 con entradas de lista de espera propias
- **WHEN** recepción de T1 lista su lista de espera
- **THEN** la respuesta sólo contiene entradas de T1

### Requirement: Compatibilidad de una entrada con un hueco liberado

Una entrada SHALL ser compatible con un hueco liberado sólo si su `prestacion_id`
coincide con la del hueco, su `profesional_pref` es nulo o coincide con el
profesional del hueco, y su rango `ventana_desde`/`ventana_hasta` es nulo o
contiene el `inicio` del hueco.

#### Scenario: Entrada sin preferencias es compatible

- **GIVEN** un hueco liberado de P1 para PREST-30 y una entrada `PENDIENTE` de
  PACI-1 para PREST-30 sin `profesional_pref` ni `ventana_desde`/`ventana_hasta`
- **WHEN** el sistema evalúa la compatibilidad
- **THEN** la entrada es compatible con el hueco

#### Scenario: Preferencia de profesional acota la compatibilidad

- **GIVEN** un hueco liberado de P1 y una entrada de PACI-1 con
  `profesional_pref=P2`
- **WHEN** el sistema evalúa la compatibilidad
- **THEN** la entrada NO es compatible (prefiere a P2, no a P1)

#### Scenario: Ventana horaria acota la compatibilidad

- **GIVEN** un hueco liberado que inicia 2026-10-14T10:00:00-03:00 y una entrada
  con `ventana_hasta = 2026-10-14T09:00:00-03:00`
- **WHEN** el sistema evalúa la compatibilidad
- **THEN** la entrada NO es compatible (el hueco cae fuera de su ventana)

#### Scenario: Entradas de otra prestación no son compatibles

- **GIVEN** un hueco liberado de prestación P y entradas `PENDIENTE` cuyas
  `prestacion_id` son todas distintas de P
- **WHEN** el sistema evalúa la compatibilidad para ese hueco
- **THEN** ninguna de esas entradas se ofrece (no compatibles) y el hueco pasa a
  público

### Requirement: Auto-oferta al liberar un hueco

Cuando un turno pasa a `CANCELADO` o `REPROGRAMADO` (cualquier canal: recepción,
link público o WA), el sistema SHALL generar una oferta al primer compatible
`PENDIENTE` (por fecha de alta) con `expira_at` acotado a `slot.inicio`, marcar la
entrada `OFRECIDO` y retener el hueco; si no hay compatibles, el hueco SHALL
quedar público sin retención.

#### Scenario: Hueco liberado se ofrece al primer compatible

- **GIVEN** el reloj fijado en 2026-10-13T09:00:00-03:00, un turno de P1 en S1 de
  2026-10-14T10:00:00-03:00 a 10:30 (`-03:00`) que se cancela, y PACI-1
  `PENDIENTE` para PREST-30
- **WHEN** el worker procesa el hueco liberado
- **THEN** se crea una oferta `PENDIENTE` para PACI-1 con
  `expira_at = 2026-10-13T11:00:00-03:00` (ej. `OFERTA_TTL_MIN=120`), PACI-1 pasa
  a `OFRECIDO` y el hueco queda retenido

#### Scenario: Sin lista compatible el hueco queda público

- **GIVEN** un turno cancelado y ningún `PENDIENTE` compatible en el tenant
- **WHEN** el worker procesa el hueco liberado
- **THEN** no se crea ninguna oferta y el hueco aparece en la disponibilidad
  pública sin retención

#### Scenario: Doble evento del mismo turno genera una sola oferta

- **GIVEN** un turno cancelado que dispara dos eventos de hueco liberado (p. ej.
  retry del worker)
- **WHEN** el worker procesa ambos eventos
- **THEN** se crea exactamente una oferta para ese turno (idempotente por
  turno liberado)

#### Scenario: Turno reprogramado libera su hueco original y dispara oferta

- **GIVEN** un turno de P1 en S1 de 2026-10-14T10:00:00-03:00 a 10:30 que se
  reprograma a 2026-10-14T14:00:00-03:00, y PACI-1 `PENDIENTE` para PREST-30
- **WHEN** el worker procesa el hueco liberado por la reprogramación
- **THEN** se crea una oferta `PENDIENTE` para PACI-1 sobre el hueco original
  (10:00–10:30), PACI-1 pasa a `OFRECIDO` y el nuevo slot 14:00 queda ocupado por
  el turno reprogramado

#### Scenario: Hueco liberado demasiado cerca de su inicio acota la expiración

- **GIVEN** un hueco liberado de P1 con `slot.inicio` tal que
  `ahora + OFERTA_TTL_MIN > slot.inicio` (cancelación tardía por recepción,
  RN-RE-03), y un compatible `PENDIENTE`
- **WHEN** el worker procesa el hueco liberado
- **THEN** la oferta se crea con
  `expira_at = min(ahora + OFERTA_TTL_MIN, slot.inicio) = slot.inicio`, de modo
  que la oferta NUNCA expira después de que arranca el slot

#### Scenario: Hueco liberado con inicio ya pasado se publica directo

- **GIVEN** un hueco liberado con `slot.inicio` ya pasado (`ahora >= slot.inicio`)
- **WHEN** el worker procesa el hueco liberado
- **THEN** no se genera ronda de lista de espera: el hueco se publica directo
  como disponible sin retención

### Requirement: Rotación por expiración de la oferta

Si una oferta no es aceptada antes de `expira_at`, el sistema SHALL marcarla
`VENCIDA`, devolver la entrada a `PENDIENTE` y ofrecer el hueco al siguiente
compatible; al agotar la lista compatible el hueco SHALL quedar público.

#### Scenario: Oferta vencida rota al siguiente compatible

- **GIVEN** un hueco liberado, PACI-1 (alta 09:00) y PACI-2 (alta 10:00) ambos
  compatibles, con la oferta a PACI-1 vencida
- **WHEN** el worker procesa la expiración de la oferta a PACI-1
- **THEN** la oferta a PACI-1 queda `VENCIDA`, PACI-1 vuelve a `PENDIENTE` y se
  crea una oferta nueva para PACI-2

#### Scenario: Último compatible vencido libera el hueco al público

- **GIVEN** un hueco liberado con un único compatible cuya oferta vence
- **WHEN** el worker procesa la expiración
- **THEN** no queda ninguna oferta vigente y el hueco vuelve a la disponibilidad
  pública

### Requirement: Aceptación de la oferta con revalidación de solape

El sistema SHALL permitir aceptar una oferta vigente (no vencida) creando un
turno `origen=LISTA_ESPERA` en el hueco retenido, **revalidando el solape con
C-05**; la entrada SHALL pasar a `CONVERTIDO` y la oferta a `ACEPTADA`. Sólo el
primer aceptante SHALL ocupar el hueco.

#### Scenario: Aceptación crea el turno y convierte la entrada

- **GIVEN** una oferta `PENDIENTE` vigente a PACI-1 sobre el hueco de P1/S1
  2026-10-14T10:00:00-03:00 (PREST-30)
- **WHEN** PACI-1 acepta la oferta antes de `expira_at`
- **THEN** se crea un turno `origen=LISTA_ESPERA` de 10:00 a 10:30, la oferta
  pasa a `ACEPTADA` y la entrada a `CONVERTIDO`

#### Scenario: Aceptación tras la expiración no crea turno

- **GIVEN** una oferta a PACI-1 con `expira_at = 2026-10-13T11:00:00-03:00` y el
  reloj en 2026-10-13T11:01:00-03:00
- **WHEN** PACI-1 intenta aceptar
- **THEN** el sistema responde `409`, no crea turno y la oferta pasa a `VENCIDA`

#### Scenario: Aceptación con hueco ya tomado no crea turno

- **GIVEN** una oferta vigente a PACI-1, y el hueco ocupado por recepción antes
  de aceptar
- **WHEN** PACI-1 acepta la oferta
- **THEN** la revalidación de solape responde `409`, no se crea turno, la oferta
  pasa a `VENCIDA` y la entrada vuelve a `PENDIENTE` (sigue elegible para futuros
  huecos)

#### Scenario: Doble aceptación de la misma oferta crea un solo turno

- **GIVEN** una oferta vigente a PACI-1
- **WHEN** la oferta se acepta dos veces en paralelo
- **THEN** exactamente una aceptación crea el turno y la otra responde `409`; la
  entrada queda `CONVERTIDO` una sola vez

### Requirement: Retención del hueco durante la oferta

Mientras exista una oferta vigente (no vencida ni cancelada) sobre un hueco, el
hueco SHALL NOT ofrecerse en la disponibilidad pública del tenant; al vencer,
cancelarse o aceptarse la oferta, la retención SHALL liberarse.

#### Scenario: Hueco retenido no aparece en disponibilidad

- **GIVEN** una oferta vigente a PACI-1 sobre el hueco de P1 2026-10-14T10:00:00-03:00
- **WHEN** se consulta la disponibilidad pública de P1 para PREST-30 desde
  2026-10-14T00:00:00-03:00
- **THEN** el hueco de 10:00 no se ofrece mientras la oferta siga vigente

#### Scenario: Oferta vencida libera la retención

- **GIVEN** una oferta que vence sin aceptación
- **WHEN** el worker procesa la expiración y no hay más compatibles
- **THEN** el hueco vuelve a ofrecerse en la disponibilidad pública

### Requirement: Aislamiento multi-tenant de la lista de espera

Toda operación de lista de espera y oferta SHALL acotarse al `tenant_id`; una
entrada, oferta o token de un tenant SHALL NOT poder leerse ni mutarse desde otro
tenant.

#### Scenario: Token de oferta de un tenant no resuelve en otro

- **GIVEN** una oferta vigente de T1 con token OFR-A
- **WHEN** se intenta aceptar `OFR-A` en la ruta del tenant T2
- **THEN** el sistema responde `404` y no crea turno en T2 ni muta la oferta de T1

#### Scenario: Listado y alta nunca cruzan tenants

- **GIVEN** T1 y T2 con sus propias entradas
- **WHEN** se lista o se da de alta/baja en T1 usando identificadores de T2
- **THEN** ninguna operación lee ni escribe filas de T2

### Requirement: Audit trail inmutable (append-only)

Toda mutación de lista de espera y oferta (alta, baja, oferta, aceptación,
vencimiento) SHALL escribir un registro de auditoría inmutable (RN-AU-02) con
actor, acción, timestamp y `tenant_id`, sin PHI; los registros SHALL ser
append-only (sin UPDATE/DELETE) y siempre acotados al `tenant_id`.

#### Scenario: Mutación válida escribe registro de auditoría

- **GIVEN** el tenant T1 y una mutación válida de lista de espera (alta, baja,
  oferta, aceptación o vencimiento)
- **WHEN** la mutación se ejecuta
- **THEN** se escribe un registro de auditoría inmutable con actor, acción,
  timestamp y `tenant_id` (sin PHI)

#### Scenario: La auditoría es append-only

- **GIVEN** un registro de auditoría existente
- **WHEN** se intenta ejecutar un UPDATE o DELETE sobre ese registro
- **THEN** el sistema rechaza la operación (`403`/`405`) y el registro original
  permanece intacto

#### Scenario: La auditoría nunca cruza tenants

- **GIVEN** los tenants T1 y T2, cada uno con sus propios registros de auditoría
- **WHEN** se lista la auditoría de T1
- **THEN** el listado de T1 jamás incluye registros de T2

### Requirement: Migración 005 crea lista_espera y ofertas

El sistema SHALL aplicar la migración 005 creando `lista_espera` y `ofertas` con
`tenant_id NOT NULL`, FK a sus entidades, índices y política RLS
(`tenant_id = current_setting('app.tenant_id')`), reversible sin errores.

#### Scenario: Base vacía llega a head

- **GIVEN** una base disponible con las revisiones 001–004 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen `lista_espera` y `ofertas` con RLS y la versión vigente es 005

#### Scenario: Downgrade elimina sólo la 005

- **GIVEN** una base en la revisión 005
- **WHEN** se ejecuta `alembic downgrade 004_auth_rbac`
- **THEN** `lista_espera` y `ofertas` se eliminan sin afectar turnos ni catálogos
