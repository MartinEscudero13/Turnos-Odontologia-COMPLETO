# Spec Delta — cierre-caja

## Purpose

Cerrar la caja de cada día operativo del tenant con los totales por medio del sistema, el efectivo contado por el responsable y una diferencia explicada cuando no cuadra, dejando el cierre inmutable, el día cerrado sin altas posteriores y el devengado de obras sociales como información separada de la caja. La pantalla de cierre queda diferida a `C-10-UI` (ver `proposal.md` §Diferido a C-10-UI) y este change no declara requirements de UI.

## ADDED Requirements

### Requirement: Cierre diario con totales por medio y diferencia

El sistema SHALL registrar un cierre por día operativo con `total_efectivo`, `total_transferencia`, `total_mp` y `total_os_cobrado` netos, `total_os` como devengado informativo, `efectivo_contado`, `diferencia = efectivo_contado − total_efectivo` (C10-OQ-2), `responsable_id` y `cerrado_at`; SHALL ser único por `(tenant, fecha)` y SHALL NOT recalcularse.

#### Scenario: Cierre con diferencia cero

- **GIVEN** T1 con un ingreso en efectivo de `100000` el `2026-11-10` y `efectivo_contado=100000`
- **WHEN** recepción cierra el `2026-11-10`
- **THEN** se persiste un cierre con `total_efectivo=100000`, `total_transferencia=0`, `total_mp=0`, `total_os_cobrado=0`, `total_os=0`, `diferencia=0`, responsable y `cerrado_at`

#### Scenario: Los totales por medio son netos

- **GIVEN** T1 el `2026-11-10` con ingresos de `150000` en efectivo, `30000` por transferencia, `20000` por MP y `40000` por OS, más un egreso de efectivo de `50000`
- **WHEN** se cierra el día con `efectivo_contado=100000`
- **THEN** el cierre persiste `total_efectivo=100000`, `total_transferencia=30000`, `total_mp=20000`, `total_os_cobrado=40000` y `diferencia=0`

#### Scenario: El devengado de OS es informativo y no es caja

- **GIVEN** T1 con la línea L1 aceptada con `cobertura_os=40000` y `a_cargo_paciente=60000` en efectivo el `2026-11-10`
- **WHEN** se cierra el día con `efectivo_contado=60000`
- **THEN** el cierre persiste `total_efectivo=60000`, `total_os_cobrado=0` y `total_os=40000`, `diferencia=0` y el devengado no altera la diferencia ni los totales de caja

#### Scenario: Diferencia por faltante

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=95000` y el motivo requerido
- **THEN** el cierre persiste `diferencia=-5000` (faltante) y el motivo registrado

#### Scenario: Diferencia por sobrante

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=102000` y el motivo requerido
- **THEN** el cierre persiste `diferencia=2000` (sobrante)

#### Scenario: La diferencia se mide sólo contra el efectivo

- **GIVEN** T1 con `total_efectivo=100000`, `total_transferencia=30000` y `total_mp=20000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=100000`
- **THEN** `diferencia=0` aunque el consultorio no haya contado físicamente la transferencia ni el MP (C10-OQ-2)

#### Scenario: Un día sin movimientos se cierra en cero

- **GIVEN** T1 sin movimientos el `2026-11-08`
- **WHEN** recepción cierra el `2026-11-08` con `efectivo_contado=0`
- **THEN** se persiste el cierre con los totales en `0`, `diferencia=0` y responsable (C10-OQ-4)

#### Scenario: Un efectivo contado negativo se rechaza

- **GIVEN** T1 el `2026-11-10`
- **WHEN** se intenta cerrar con `efectivo_contado=-1`
- **THEN** el sistema responde `422`, la base rechaza el valor por el CHECK `efectivo_contado >= 0` y no se persiste el cierre

#### Scenario: Un día futuro no se cierra

- **GIVEN** T1, el reloj en `2026-11-10T10:00:00-03:00` y el día `2026-11-12` sin movimientos
- **WHEN** se intenta cerrar el `2026-11-12`
- **THEN** el sistema responde `422` y no se persiste el cierre, porque cerrar un día que todavía no ocurrió lo dejaría inmutable antes de operar

#### Scenario: Un segundo cierre del mismo día se rechaza

- **GIVEN** T1 con el `2026-11-10` cerrado
- **WHEN** recepción intenta cerrar otra vez el `2026-11-10`
- **THEN** el sistema responde `409 CIERRE_EXISTENTE`, el cierre original no cambia y no se duplica la fila

#### Scenario: Dos cierres simultáneos crean uno solo

- **GIVEN** T1 sin cierre el `2026-11-10` y dos conexiones independientes a PostgreSQL
- **WHEN** ambas intentan cerrar el mismo día a la vez
- **THEN** una responde `201` y la otra `409`, existe exactamente un cierre y ninguna responde `500`

### Requirement: Diferencia distinta de cero exige motivo

El sistema SHALL exigir `motivo_diferencia` no vacío cuando `diferencia ≠ 0`, con `observacion` opcional y auditable; sin motivo SHALL responder `422` sin persistir el cierre; el motivo SHALL quedar auditado de forma que la diferencia sea explicable.

#### Scenario: Cierre con diferencia y motivo más observación

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=95000`, `motivo="faltante de caja"` y `observacion="se revisó el cajón con el responsable"`
- **THEN** el cierre se persiste con la diferencia, ambos textos, y la auditoría registra la diferencia y que hay observación

#### Scenario: Cierre con diferencia y motivo sin observación

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=95000` y `motivo="faltante de caja"` sin `observacion`
- **THEN** el sistema responde `201`, persiste `diferencia=-5000` y la observación queda en `NULL`, porque la observación es opcional

#### Scenario: Cierre con diferencia sin motivo se rechaza

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=95000` y sin `motivo_diferencia`
- **THEN** el sistema responde `422` y no persiste el cierre

#### Scenario: Motivo vacío se rechaza

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=95000`, `motivo_diferencia=""` y una observación
- **THEN** el sistema responde `422` y no persiste el cierre

#### Scenario: Un sobrante tampoco se cierra sin motivo

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=102000` sin motivo
- **THEN** el sistema responde `422` y no persiste el cierre

#### Scenario: Con diferencia cero el motivo es opcional

- **GIVEN** T1 con `total_efectivo=100000` el `2026-11-10`
- **WHEN** se cierra con `efectivo_contado=100000` sin `motivo_diferencia`
- **THEN** el sistema responde `201` y el cierre se persiste con `diferencia=0`

#### Scenario: El motivo del cierre queda auditado

- **GIVEN** T1 con una diferencia de `-5000` explicada
- **WHEN** se consulta la auditoría del cierre
- **THEN** existe `CIERRE_DIARIO_REGISTRADO` con `cierre_id`, `fecha`, totales, `diferencia`, `responsable_id` y el motivo, sin datos personales del paciente

### Requirement: El día se cierra con un responsable del tenant

El sistema SHALL exigir un `responsable_id` de un usuario del tenant para cerrar cualquier día, con o sin movimientos; sin responsable SHALL responder `422` sin persistir el cierre y el día SHALL seguir abierto; un responsable de otro tenant SHALL responder `404`.

#### Scenario: Un día con movimientos no se cierra sin responsable

- **GIVEN** T1 con movimientos el `2026-11-10`
- **WHEN** se intenta cerrar sin `responsable_id`
- **THEN** el sistema responde `422`, no persiste el cierre y el `2026-11-10` sigue `abierto`

#### Scenario: Un día sin movimientos tampoco se cierra sin responsable

- **GIVEN** T1 sin movimientos el `2026-11-08`
- **WHEN** se intenta cerrar sin `responsable_id`
- **THEN** el sistema responde `422` y no persiste el cierre

#### Scenario: Un responsable de otro tenant no es válido

- **GIVEN** T1 y el usuario U9 del tenant T2
- **WHEN** se intenta cerrar el `2026-11-10` con `responsable_id=U9`
- **THEN** el sistema responde `404` y no persiste el cierre

#### Scenario: El responsable queda registrado en el cierre

- **GIVEN** T1 con el usuario U1 de recepción
- **WHEN** U1 cierra el `2026-11-10`
- **THEN** el cierre se persiste con `responsable_id=U1` y el actor de la auditoría es U1

### Requirement: El día cerrado es inmutable

Una vez cerrado, el día SHALL rechazar altas e imputaciones nuevas con `409 CIERRE_CERRADO`; el cierre SHALL NOT editarse ni borrarse (sin `PATCH`/`DELETE` en el borde y sin `UPDATE`/`DELETE` en la base); la única corrección SHALL ser un compensatorio fechado el día del registro, o el cobro de un pendiente, asentados en `ajustes_post_cierre`.

#### Scenario: No se cargan movimientos en un día cerrado

- **GIVEN** T1 con el `2026-11-10` cerrado
- **WHEN** recepción intenta registrar un ingreso con `fecha=2026-11-10`
- **THEN** el sistema responde `409 CIERRE_CERRADO` y el cierre no cambia

#### Scenario: El cierre no se edita por la API

- **GIVEN** T1 con el cierre del `2026-11-10`
- **WHEN** se intenta `PATCH /api/caja/cierre` o `DELETE /api/caja/cierre`
- **THEN** el sistema responde `405` (o `404` si la ruta no existe), nunca `200`, y el cierre sigue intacto

#### Scenario: El cierre no se edita en la base

- **GIVEN** la base en 008 con un cierre persistido
- **WHEN** como `turnos_app` se intenta `UPDATE` o `DELETE` sobre `cierres_diarios`
- **THEN** la base rechaza la operación y la fila permanece intacta

#### Scenario: El compensatorio no modifica el cierre

- **GIVEN** T1 con el cierre del `2026-11-10` y un movimiento de ese día
- **WHEN** ADMIN anula el movimiento al día siguiente y se crea el compensatorio
- **THEN** el cierre del `2026-11-10` conserva sus totales, su diferencia y su `cerrado_at`, y no se escribe ningún `UPDATE` sobre él

### Requirement: Obligatoriedad del cierre y cierre atrasado

El sistema SHALL NOT bloquear la operación del día por un día anterior sin cerrar; el estado de cada día SHALL ser consultable y el cierre de un día anterior SHALL estar permitido (`201`) mientras ese día no tenga cierre (interpretación de C10-OQ-3).

#### Scenario: Un día anterior sin cerrar no bloquea operar hoy

- **GIVEN** T1 con el `2026-11-09` sin cierre y el reloj en `2026-11-10T10:00:00-03:00`
- **WHEN** U1 registra un ingreso con `fecha=2026-11-10`
- **THEN** el sistema responde `201` y el `2026-11-09` sigue `abierto`

#### Scenario: El estado del día atrasado es consultable

- **GIVEN** T1 con el `2026-11-09` sin cierre
- **WHEN** se consulta el estado del `2026-11-09`
- **THEN** la respuesta devuelve `estado=abierto` con los totales vigentes del día y sin totales de cierre

#### Scenario: Un cierre atrasado se permite

- **GIVEN** T1 con el `2026-11-09` sin cierre y el reloj en `2026-11-10T10:00:00-03:00`
- **WHEN** U1 cierra el `2026-11-09` con un responsable del tenant
- **THEN** el sistema responde `201` y el `2026-11-09` queda `cerrado` con sus totales

#### Scenario: Después del cierre atrasado el día queda inmutable

- **GIVEN** T1 con el `2026-11-09` recién cerrado de forma atrasada
- **WHEN** U1 intenta registrar un movimiento con `fecha=2026-11-09`
- **THEN** el sistema responde `409 CIERRE_CERRADO`

### Requirement: La reapertura de un cierre no existe en v1

v1 SHALL NOT exponer la reapertura de un cierre; un día cerrado queda final y la reapertura queda como `C10-OQ-1` sin implementar; ninguna ruta SHALL permitir volver un cierre a abierto.

#### Scenario: No existe endpoint de reapertura

- **GIVEN** T1 con el `2026-11-10` cerrado
- **WHEN** se intenta `POST /api/caja/cierre/reabrir` o `POST /api/caja/cierre/{id}/reabrir`
- **THEN** el sistema responde `404` o `405`, nunca `200`, y el cierre sigue cerrado

#### Scenario: El día cerrado sigue rechazando altas después de un intento de reapertura

- **GIVEN** T1 con el `2026-11-10` cerrado y un intento de reapertura fallido
- **WHEN** recepción intenta cargar un movimiento con `fecha=2026-11-10`
- **THEN** el sistema sigue respondiendo `409 CIERRE_CERRADO`

### Requirement: Concurrencia entre movimientos y cierre

Toda escritura de movimiento (alta, cobro de pendiente, compensatorio) SHALL tomar `pg_advisory_xact_lock(hashtext(tenant_id || ':' || fecha))` en la misma transacción antes de validar el estado del día y de insertar; el cierre SHALL tomar el mismo lock antes de leer los totales y escribir.

#### Scenario: Un movimiento concurrente entra antes del cierre o es rechazado

- **GIVEN** T1 sin cierre el `2026-11-10` y dos conexiones independientes a PostgreSQL
- **WHEN** una registra un ingreso de `50000` en efectivo y la otra cierra el día con `efectivo_contado=50000`
- **THEN** o el ingreso entra antes del cierre y el cierre lo cuenta (`total_efectivo=50000`), o el cierre gana y el alta responde `409 CIERRE_CERRADO`; nunca queda un movimiento del `2026-11-10` fuera del cierre

#### Scenario: El cierre espera al movimiento en curso

- **GIVEN** T1 y una transacción que ya tomó el lock del `2026-11-10` para insertar un movimiento
- **WHEN** otra conexión intenta cerrar el `2026-11-10`
- **THEN** el cierre espera el lock, lee los totales después del commit y no responde `500`

#### Scenario: El cobro de un pendiente también toma el lock

- **GIVEN** T1 con un pendiente del `2026-11-10` y una conexión que está cerrando ese día
- **WHEN** otra conexión cobra el pendiente sobre esa fecha
- **THEN** el cobro espera el lock y, si el cierre ya commiteó, asienta el ajuste post-cierre en lugar de insertar en el día cerrado

### Requirement: Consulta del cierre y estado del día

El sistema SHALL exponer el cierre de una fecha y el estado `abierto`/`cerrado` del día; un día sin cierre SHALL reportarse `abierto`; un cierre de otro tenant SHALL responder `404`.

#### Scenario: Un día sin cierre se reporta abierto

- **GIVEN** T1 sin cierre el `2026-11-11`
- **WHEN** se consulta el estado del `2026-11-11`
- **THEN** la respuesta devuelve `estado=abierto`, sin totales de cierre y con el total del sistema por medio

#### Scenario: Un día cerrado devuelve su cierre

- **GIVEN** T1 con el cierre del `2026-11-10`
- **WHEN** se consulta el estado del `2026-11-10`
- **THEN** la respuesta devuelve `estado=cerrado` con totales por medio, `efectivo_contado`, `diferencia`, responsable y `cerrado_at`

#### Scenario: El cierre de otro tenant no se lee

- **GIVEN** T1 y el cierre del `2026-11-10` del tenant T2
- **WHEN** un actor de T1 consulta el cierre del `2026-11-10`
- **THEN** el sistema responde `404` y no expone datos de T2

### Requirement: RBAC del cierre

`RECEPCION` y `ADMIN` SHALL cerrar el día; `ODONTOLOGO` SHALL sólo leer el cierre y el estado del día; un rol sin permiso SHALL recibir `403`; una petición con identidad de paciente SHALL recibir `401`.

#### Scenario: Recepción cierra el día

- **GIVEN** T1 con el usuario U1 de recepción y el `2026-11-10` sin cierre
- **WHEN** U1 cierra el día
- **THEN** el sistema responde `201` con el cierre creado

#### Scenario: Admin cierra el día

- **GIVEN** T1 con el usuario U2 de ADMIN y el `2026-11-10` sin cierre
- **WHEN** U2 cierra el día
- **THEN** el sistema responde `201` con `responsable_id=U2`

#### Scenario: El odontólogo no cierra

- **GIVEN** T1 con el odontólogo U3 y el `2026-11-10` sin cierre
- **WHEN** U3 intenta cerrar el día
- **THEN** el sistema responde `403`, el día sigue abierto y no se persiste cierre

#### Scenario: El odontólogo lee el cierre

- **GIVEN** T1 con el cierre del `2026-11-10`
- **WHEN** U3 consulta el cierre y el estado del día
- **THEN** ambas consultas responden `200` con los mismos totales que ve recepción

#### Scenario: El paciente no accede al cierre

- **GIVEN** T1 con el cierre del `2026-11-10`
- **WHEN** una petición con identidad de paciente intenta consultar o crear un cierre
- **THEN** el sistema responde `401` y no expone ni registra nada

### Requirement: Auditoría del cierre

Toda creación de cierre SHALL escribir una entrada de auditoría inmutable con `tenant_id`, actor, `cierre_id`, fecha, totales, `efectivo_contado`, `diferencia`, `responsable_id`, `antes`/`después` y la presencia de motivo y observación, sin PHI.

#### Scenario: Cerrar el día deja auditoría

- **GIVEN** T1 con movimientos el `2026-11-10` y el usuario U1
- **WHEN** U1 cierra el día
- **THEN** se escribe `CIERRE_DIARIO_REGISTRADO` con `tenant_id`, `cierre_id`, `fecha`, los totales, `efectivo_contado`, `diferencia`, `responsable_id`, `antes=null` y `después` con los valores persistidos

#### Scenario: La auditoría no copia la observación

- **GIVEN** T1 con un cierre que tiene `observacion` con texto operativo
- **WHEN** se consulta la entrada de auditoría del cierre
- **THEN** la entrada indica que hay observación cargada pero no copia su contenido y no incluye nombre, DNI ni teléfono

#### Scenario: La auditoría del cierre es append-only

- **GIVEN** una entrada `CIERRE_DIARIO_REGISTRADO`
- **WHEN** se intenta `UPDATE` o `DELETE` sobre ella
- **THEN** la operación se rechaza y la entrada original permanece intacta
