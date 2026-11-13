# Spec Delta — caja

## Purpose

Registrar todo movimiento de dinero del consultorio con medio, tipo, monto, usuario y día operativo, permitir anularlo sólo con motivo y sin borrarlo nunca, asentar los ajustes posteriores al cierre sin editar el cierre, cobrar las imputaciones del presupuesto aceptado y consultar el día y sus totales, dentro del tenant y sin PHI. La UI de caja queda diferida a `C-10-UI` (ver `proposal.md` §Diferido a C-10-UI) y este change no declara requirements de UI.

## ADDED Requirements

### Requirement: Registro de movimientos multi-medio

El sistema SHALL registrar movimientos con `medio` ∈ {EFECTIVO, TRANSFERENCIA, MP, OS}, `tipo` ∈ {INGRESO, EGRESO}, `monto` entero positivo en centavos, `fecha` operativa y `usuario_id`; SHALL rechazar con `422` monto no entero, cero o negativo, medio o tipo inválido y fecha no ISO; sin `fecha` SHALL usarse el día del reloj en el offset fijo `-03:00` (C10-OQ-8); un `turno_id` ajeno SHALL responder `404`.

#### Scenario: Registro de un ingreso en efectivo

- **GIVEN** el tenant T1 y el usuario U1 de recepción
- **WHEN** U1 registra un `INGRESO` de `monto=150000` con `medio=EFECTIVO`, `fecha=2026-11-10` y `turno_id=TUR-1`
- **THEN** se persiste un movimiento de T1 con esos valores, `anulado=false`, `origen=MANUAL`, `tramo=NULL` y `usuario_id=U1`

#### Scenario: Registro de un egreso

- **GIVEN** T1 y el usuario U1 de recepción
- **WHEN** U1 registra un `EGRESO` de `monto=20000` con `medio=TRANSFERENCIA` y `fecha=2026-11-10`
- **THEN** el movimiento se persiste con `tipo=EGRESO` y cuenta en los totales del día con signo negativo

#### Scenario: Los cuatro medios son válidos

- **GIVEN** T1 y el usuario U1
- **WHEN** U1 registra cuatro ingresos del mismo día, uno por cada medio `EFECTIVO`, `TRANSFERENCIA`, `MP` y `OS`
- **THEN** los cuatro se persisten y el día muestra un total por cada medio

#### Scenario: Monto inválido se rechaza

- **GIVEN** T1 y el usuario U1
- **WHEN** U1 registra un movimiento con `monto=0`, `monto=-100`, `monto=1000.5` o `monto="1000"`
- **THEN** el sistema responde `422` y no persiste ningún movimiento

#### Scenario: Medio o tipo inválido se rechaza

- **GIVEN** T1 y el usuario U1
- **WHEN** U1 registra un movimiento con `medio="CHEQUE"` o con `tipo="AJUSTE"`
- **THEN** el sistema responde `422` y no persiste el movimiento

#### Scenario: Fecha sin zona o mal formada se rechaza

- **GIVEN** T1 y el usuario U1
- **WHEN** U1 registra un movimiento con `fecha="10/11/2026"` o `fecha="2026-11-10T10:00:00-03:00"`
- **THEN** el sistema responde `422` y no persiste el movimiento, porque `fecha` es un día operativo (`YYYY-MM-DD`)

#### Scenario: Sin fecha se usa el reloj del servidor en el offset del consultorio

- **GIVEN** T1, el usuario U1 y `ahora=2026-11-10T22:00:00-03:00` inyectado
- **WHEN** U1 registra un movimiento sin `fecha`
- **THEN** el movimiento se persiste con `fecha=2026-11-10`

#### Scenario: El día operativo respeta el offset -03:00

- **GIVEN** T1, el usuario U1 y `ahora=2026-11-11T01:30:00Z` inyectado, que en `-03:00` es el `2026-11-10T22:30`
- **WHEN** U1 registra un movimiento sin `fecha`
- **THEN** el movimiento se persiste con `fecha=2026-11-10` y no con `2026-11-11` (C10-OQ-8)

#### Scenario: Turno de otro tenant no se puede asociar

- **GIVEN** T1 con el usuario U1 y el turno TUR-9 del tenant T2
- **WHEN** U1 registra un movimiento con `turno_id=TUR-9`
- **THEN** el sistema responde `404` y no persiste el movimiento

### Requirement: Anulación con motivo, nunca borrado

El sistema SHALL anular un movimiento sólo con `motivo` no vacío y SHALL persistir `anulado=true`, `motivo_anulacion`, `anulado_por` y `anulado_en` en la misma operación; SHALL NOT editar `monto`, `medio`, `tipo`, `fecha`, `turno_id` ni `usuario_id`; el anulado SHALL excluirse de los totales; una segunda anulación SHALL responder `409`; SHALL NOT existir `DELETE` de movimientos.

#### Scenario: Anular en un día abierto excluye el movimiento de los totales

- **GIVEN** T1 con un ingreso vigente de `monto=150000` con `medio=EFECTIVO` en `2026-11-10` y sin cierre
- **WHEN** ADMIN anula el movimiento con `motivo="cobro duplicado"`
- **THEN** el movimiento queda `anulado=true` con `motivo_anulacion`, `anulado_por` y `anulado_en`, no se crea compensatorio ni ajuste, y el total de efectivo del día baja a 0

#### Scenario: Anular sin motivo se rechaza

- **GIVEN** T1 con un movimiento vigente
- **WHEN** ADMIN intenta anularlo sin `motivo` o con `motivo=""`
- **THEN** el sistema responde `422` y el movimiento sigue vigente

#### Scenario: Una segunda anulación se rechaza

- **GIVEN** T1 con el movimiento M1 ya anulado
- **WHEN** ADMIN intenta anular M1 de nuevo
- **THEN** el sistema responde `409 ANULADO`, no cambia la anulación original y no crea un segundo compensatorio ni un segundo ajuste

#### Scenario: El movimiento no se borra ni se edita

- **GIVEN** T1 con un movimiento vigente de `monto=150000`
- **WHEN** se intenta `DELETE /api/caja/movimientos/{id}` o `PATCH /api/caja/movimientos/{id}`
- **THEN** el sistema responde `405` (o `404` si la ruta no existe), nunca `200`, y el movimiento sigue intacto

#### Scenario: El motivo conserva el monto original

- **GIVEN** T1 con un ingreso anulado de `monto=150000`
- **WHEN** se consulta el movimiento anulado
- **THEN** devuelve `monto=150000`, `medio` y `tipo` originales, `anulado=true` y el `motivo_anulacion`, sin ningún valor reescrito

### Requirement: Día cerrado: altas rechazadas y corrección por compensación

En un día con cierre el sistema SHALL NOT aceptar altas ni imputaciones sobre esa fecha (`409 CIERRE_CERRADO`), salvo la anulación y el cobro de un pendiente, que se asientan en `ajustes_post_cierre`; la anulación SHALL crear un compensatorio de tipo inverso, mismo medio y monto, fechado el día del registro, y el cierre SHALL conservar sus totales.

#### Scenario: Un movimiento nuevo en un día cerrado se rechaza

- **GIVEN** T1 con `2026-11-10` cerrado
- **WHEN** U1 registra un ingreso con `fecha=2026-11-10`
- **THEN** el sistema responde `409 CIERRE_CERRADO`, no persiste el movimiento y el cierre no cambia

#### Scenario: Anular después del cierre crea un compensatorio

- **GIVEN** T1 con el ingreso M1 de `monto=150000` con `medio=EFECTIVO` en `2026-11-10`, el día cerrado y `ahora=2026-11-11T09:00:00-03:00`
- **WHEN** ADMIN anula M1 con `motivo="error de carga"`
- **THEN** M1 queda `anulado=true` y se crea un `EGRESO` de `monto=150000` con `medio=EFECTIVO`, `origen=COMPENSACION`, `compensa_a_id=M1`, `motivo_anulacion="error de carga"` y `fecha=2026-11-11`

#### Scenario: El compensatorio de un egreso es un ingreso

- **GIVEN** T1 con un `EGRESO` de `20000` con `medio=TRANSFERENCIA` en `2026-11-10` y ese día cerrado
- **WHEN** ADMIN anula el egreso al día siguiente
- **THEN** el compensatorio es un `INGRESO` de `20000` con `medio=TRANSFERENCIA` y `fecha=2026-11-11`, que suma al total de transferencia de ese día

#### Scenario: El compensatorio cuenta en el día del registro

- **GIVEN** T1 con el `EGRESO` compensatorio de `150000` en efectivo fechado `2026-11-11` y ese día sin cierre
- **WHEN** se consultan los movimientos del `2026-11-11`
- **THEN** el `EGRESO` compensatorio aparece en ese día y descuenta del total de efectivo del `2026-11-11`, mientras el `2026-11-10` conserva su total

#### Scenario: Un compensatorio también se puede anular

- **GIVEN** T1 con un movimiento compensatorio vigente fechado `2026-11-11` y ese día sin cierre
- **WHEN** ADMIN anula el compensatorio con un motivo
- **THEN** el sistema responde `200`, el compensatorio queda anulado y no se crea otro compensatorio porque el día está abierto

#### Scenario: Si el día del registro también está cerrado no se asienta la corrección

- **GIVEN** T1 con `2026-11-10` y `2026-11-11` cerrados y un movimiento de `2026-11-10`
- **WHEN** ADMIN anula el movimiento el `2026-11-11`
- **THEN** el sistema responde `409 CIERRE_CERRADO`, no anula el movimiento y no crea compensatorio ni ajuste, porque no hay día abierto donde asentarlo

#### Scenario: Dos anulaciones simultáneas dejan un solo compensatorio

- **GIVEN** T1 con un movimiento de un día cerrado y dos conexiones independientes a PostgreSQL
- **WHEN** ambas intentan anular el mismo movimiento a la vez
- **THEN** una responde `200` y la otra `409`, y existe exactamente un compensatorio y un ajuste

### Requirement: Ajustes post-cierre referenciados al cierre

El sistema SHALL asentar en `ajustes_post_cierre` —`tipo` AJUSTE_ANULACION o COBRO_PENDIENTE, `cierre_id`, `monto`, `medio`, actor y el movimiento que lo materializa— todo ajuste cuya fecha operativa ya tenga cierre; SHALL NOT insertar movimientos en esa fecha y SHALL NOT recalcular el cierre.

#### Scenario: Anular un movimiento de un día cerrado asienta el ajuste

- **GIVEN** T1 con el ingreso M1 de `150000` en `2026-11-10` cerrado y `ahora=2026-11-11T09:00:00-03:00`
- **WHEN** ADMIN anula M1 con `motivo="error de carga"`
- **THEN** se crea un ajuste `AJUSTE_ANULACION` con `cierre_id` del `2026-11-10`, `movimiento_original_id=M1`, `monto=150000`, `medio=EFECTIVO`, el motivo, el actor y `compensatorio_id` del `EGRESO` creado el `2026-11-11`

#### Scenario: La anulación post-cierre no inserta nada en la fecha cerrada

- **GIVEN** T1 con el cierre del `2026-11-10` y M1 de ese día
- **WHEN** ADMIN anula M1 el `2026-11-11`
- **THEN** la cantidad de movimientos con `fecha=2026-11-10` no cambia, ningún movimiento existente de ese día cambia su `monto` ni su `medio`, y el compensatorio solo existe en `2026-11-11`

#### Scenario: El cierre conserva sus totales exactos

- **GIVEN** T1 con el cierre del `2026-11-10`, sus totales persistidos, un movimiento de ese día y un cobro pendiente de ese día
- **WHEN** ADMIN anula un movimiento de ese día cerrado y cobra un pendiente de ese día
- **THEN** la fila del cierre conserva `total_efectivo`, `total_transferencia`, `total_mp`, `total_os_cobrado`, `total_os`, `efectivo_contado`, `diferencia` y `cerrado_at` sin cambios, y no se escribe ningún `UPDATE` sobre `cierres_diarios`

#### Scenario: Cobrar un pendiente con fecha operativa cerrada asienta el ajuste y responde 201

- **GIVEN** T1 con un cobro pendiente de `60000` para L1 con `fecha=2026-11-10` cerrado y `ahora=2026-11-11T09:00:00-03:00`
- **WHEN** U1 cobra el pendiente con `medio=TRANSFERENCIA`
- **THEN** el sistema responde `201`, crea un `INGRESO` de `60000` con `fecha=2026-11-11`, resuelve el pendiente con `resuelto_en` y `movimiento_id`, y asienta un ajuste `COBRO_PENDIENTE` con `cierre_id` del `2026-11-10` y ese movimiento

#### Scenario: El ajuste no suma en los totales de caja

- **GIVEN** T1 con un ajuste `AJUSTE_ANULACION` de `150000` referido al cierre del `2026-11-10`
- **WHEN** se consultan los totales del `2026-11-10` y del `2026-11-11`
- **THEN** el ajuste no aparece como movimiento ni suma en ninguno de los dos días, porque solo explica la diferencia contra el cierre

### Requirement: Idempotencia de imputación por tramo

`movimientos_caja` SHALL llevar `tramo` ∈ {PACIENTE, OS}, obligatorio si `origen=IMPUTACION`, con UNIQUE parcial `(tenant_id, linea_id, tramo)` que no incluye `medio`; `cobros_pendientes` SHALL tener UNIQUE `(tenant_id, linea_id)` sin condición de resolución; un replay idéntico SHALL ser no-op y un replay con monto o medio distinto SHALL responder `409 IMPUTACION_DUPLICADA`.

#### Scenario: El replay idéntico no duplica

- **GIVEN** T1 con L1 ya imputada en el tramo `PACIENTE` con `medio=EFECTIVO` y `monto=60000`
- **WHEN** el puerto recibe otra vez la misma línea, tramo, medio y monto
- **THEN** no se crea un segundo movimiento, la operación no falla y existe un solo movimiento para `(L1, PACIENTE)`

#### Scenario: Un replay con otro medio se rechaza y no duplica el ingreso

- **GIVEN** T1 con L1 ya imputada en el tramo `PACIENTE` con `medio=EFECTIVO` y `monto=60000`
- **WHEN** el puerto recibe L1 con `medio=TRANSFERENCIA` y el mismo monto
- **THEN** el sistema responde `409 IMPUTACION_DUPLICADA` y sigue existiendo un solo movimiento de `60000` para L1, porque el `medio` no forma parte de la clave de idempotencia

#### Scenario: Un replay con monto distinto se rechaza

- **GIVEN** T1 con L1 ya imputada con `medio=EFECTIVO` y `monto=60000`
- **WHEN** el puerto recibe otra vez L1 con `medio=EFECTIVO` y `monto=70000`
- **THEN** el sistema responde `409 IMPUTACION_DUPLICADA` y no modifica el movimiento existente

#### Scenario: Un replay posterior al cobro no crea un segundo pendiente

- **GIVEN** T1 con un pendiente de L1 ya cobrado y su movimiento de `60000`
- **WHEN** el puerto recibe otra vez L1 con `medio=NULL`
- **THEN** no se crea un segundo pendiente ni un segundo movimiento, la operación no falla y la línea sigue con un único registro de cobro

#### Scenario: Dos imputaciones simultáneas crean un solo movimiento

- **GIVEN** T1 con L1 sin imputar y dos conexiones independientes a PostgreSQL
- **WHEN** ambas imputan la misma línea, tramo y medio a la vez
- **THEN** existe un solo movimiento, ninguna conexión responde `500` y la que pierde la carrera no duplica

### Requirement: Cobros pendientes cuando falta el medio

Con `medio=NULL` el sistema SHALL registrar un cobro pendiente con `fecha` operativa, sin movimiento y uno por línea; al cobrarlo con un medio válido SHALL crear el movimiento y resolver el pendiente, auditando ambos hechos; un pendiente resuelto SHALL NOT cobrarse otra vez (`409`) y mientras esté pendiente SHALL NOT sumar a los totales.

#### Scenario: Imputación sin medio crea un pendiente y ningún movimiento

- **GIVEN** T1 con la línea L1 de `a_cargo_paciente=60000` y `cobertura_os=0`
- **WHEN** el puerto imputa L1 con `medio=NULL` y fecha operativa `2026-11-10`
- **THEN** se crea un cobro pendiente de `monto_centavos=60000` para L1 con `fecha=2026-11-10`, no se crea ningún movimiento y el total del día no cambia

#### Scenario: Cobrar el pendiente crea el movimiento

- **GIVEN** T1 con un cobro pendiente de `60000` para L1 con fecha abierta
- **WHEN** U1 cobra el pendiente con `medio=TRANSFERENCIA`
- **THEN** se crea un `INGRESO` de `monto=60000` con `medio=TRANSFERENCIA` y la trazabilidad de L1, el pendiente queda resuelto con `movimiento_id` y `resuelto_en`, y ambas acciones quedan auditadas

#### Scenario: Un pendiente resuelto no se cobra dos veces

- **GIVEN** T1 con un cobro pendiente ya resuelto
- **WHEN** U1 intenta cobrarlo otra vez con cualquier medio
- **THEN** el sistema responde `409 COBRO_YA_RESUELTO` y no se crea un segundo movimiento

#### Scenario: Un pendiente de otro tenant no se cobra

- **GIVEN** T1 y el cobro pendiente PEND-9 del tenant T2
- **WHEN** un usuario de T1 intenta cobrar PEND-9
- **THEN** el sistema responde `404` y no crea movimientos en T1

#### Scenario: Un tramo en cero no crea pendiente

- **GIVEN** T1 con la línea L2 de `a_cargo_paciente=0` sin cobertura
- **WHEN** el puerto imputa L2 con `medio=NULL`
- **THEN** no se crea cobro pendiente ni movimiento y no hay error

#### Scenario: Una imputación sin medio en un día cerrado se rechaza

- **GIVEN** T1 con `2026-11-10` cerrado y la línea L1 sin imputar
- **WHEN** el puerto imputa L1 con `medio=NULL` y fecha operativa `2026-11-10`
- **THEN** el sistema responde `409 CIERRE_CERRADO` y no crea pendiente ni movimiento

### Requirement: Imputación desde presupuesto con dos tramos

El adaptador SHALL implementar el puerto de C-09 sin cambiar su firma: el tramo `monto_paciente_centavos` SHALL generar un `INGRESO` con el `medio` recibido —o un cobro pendiente si es `NULL`— y el tramo `monto_os_centavos` SHALL registrar un devengado en `cuentas_por_cobrar_os`, nunca un `INGRESO`; un tramo en 0 SHALL NOT generar nada.

#### Scenario: Sólo el tramo del paciente genera un movimiento

- **GIVEN** T1 con la línea L1 de `monto=100000`, `cobertura_os=0` y `a_cargo_paciente=100000`
- **WHEN** el puerto imputa L1 con `medio=EFECTIVO`
- **THEN** se crea un único `INGRESO` de `monto=100000` con `medio=EFECTIVO`, `tramo=PACIENTE`, `usuario_id=U1`, `presupuesto_id=PRES-1` y `linea_id=L1`

#### Scenario: El tramo de obra social se registra como cuenta por cobrar informativa

- **GIVEN** T1 con la línea L1 de `monto=100000`, `cobertura_os=40000` y `a_cargo_paciente=60000`
- **WHEN** el puerto imputa L1 con `medio=EFECTIVO`
- **THEN** se crea un `INGRESO` de `60000` con `medio=EFECTIVO` y una cuenta por cobrar OS de `40000` para L1, con cero movimientos de `medio=OS` y sin sumar `40000` a los totales de caja

#### Scenario: El tramo OS nunca genera dos ingresos por el mismo monto

- **GIVEN** T1 con L1 ya imputada con `cobertura_os=40000`
- **WHEN** se repite exactamente la misma imputación de L1 (mismo tramo paciente y misma cobertura OS)
- **THEN** el replay es no-op, existe una sola cuenta por cobrar OS de `40000` para L1 y ningún `INGRESO` de `medio=OS` creado por la imputación

#### Scenario: Sólo la cobertura genera cuenta por cobrar y ningún movimiento

- **GIVEN** T1 con la línea L3 de `monto=40000`, `cobertura_os=40000` y `a_cargo_paciente=0`
- **WHEN** el puerto imputa L3 con `medio=EFECTIVO`
- **THEN** no se crea ningún movimiento, se crea una cuenta por cobrar OS de `40000` para L3 y no hay error

#### Scenario: El medio OS no se acepta en el tramo del paciente

- **GIVEN** T1 con la línea L1 de `a_cargo_paciente=60000` y `cobertura_os=40000`
- **WHEN** se invoca directamente el adaptador con `medio=OS`
- **THEN** el adaptador responde `422 MEDIO_OS_RESERVADO` y no crea movimientos ni cuentas por cobrar (C10-OQ-5)

#### Scenario: El turno asociado se persiste

- **GIVEN** T1 con la línea L1 y el turno TUR-1 del mismo tenant
- **WHEN** la imputación llega con `turno_id=TUR-1` y `medio=MP`
- **THEN** el movimiento se persiste con `turno_id=TUR-1` y `medio=MP`

#### Scenario: Una línea de otro tenant no se imputa

- **GIVEN** T1 y la línea L9 del presupuesto de T2
- **WHEN** llega una imputación con `tenant_id=T1` y `linea_id=L9`
- **THEN** el sistema responde `404` y no crea movimientos, pendientes ni cuentas por cobrar en T1

### Requirement: Punto de observación de los errores del adaptador

El adaptador SHALL exponer sus errores como excepciones de dominio con `codigo` HTTP (422, 409, 404) al invocarse directamente. A través de `POST /api/presupuestos/{id}/aceptar`, C-09 SHALL traducir cualquier excepción del puerto a `503` y SHALL NOT persistir la aceptación (`servicio.py:516-519`); C-10 SHALL NOT modificar C-09.

#### Scenario: El error del adaptador se observa directo

- **GIVEN** T1 con la línea L1 y el día `2026-11-10` cerrado
- **WHEN** se invoca `AdaptadorCaja.imputar_caja` directamente para L1 con fecha `2026-11-10`
- **THEN** la excepción de dominio tiene `codigo=409` y `CIERRE_CERRADO`, y no se escribe nada

#### Scenario: A través de C-09 el mismo error es 503 y no persiste la aceptación

- **GIVEN** T1 con la línea L1 de un presupuesto vigente y el día operativo cerrado
- **WHEN** recepción acepta L1 por `POST /api/presupuestos/{id}/aceptar`
- **THEN** C-09 responde `503`, no se persiste la aceptación, el presupuesto sigue vigente y no se crea ningún movimiento

#### Scenario: Un replay con otro medio no es alcanzable desde C-09

- **GIVEN** T1 con L1 ya aceptada y su movimiento de imputación
- **WHEN** recepción intenta aceptar L1 otra vez por `POST /api/presupuestos/{id}/aceptar`
- **THEN** C-09 responde `409` antes de invocar el puerto (`servicio.py:448-454`) y el `409 IMPUTACION_DUPLICADA` solo es observable invocando el adaptador directamente

### Requirement: Consulta diaria con totales vigentes y del cierre

`GET /api/caja/movimientos?fecha=` SHALL devolver movimientos, cobros pendientes, `totales_vigentes`, `totales_cierre` (`null` si el día está abierto) y `difieren_del_cierre: bool`; `fecha` ausente SHALL responder `422`; SHALL NOT exponer una sección de señas aplicadas (C10-OQ-6).

#### Scenario: Totales por medio del día

- **GIVEN** T1 con dos ingresos en efectivo de `100000` y `50000`, un egreso de efectivo de `20000`, un ingreso `MP` de `30000` y un ingreso `OS` de `40000` el `2026-11-10`
- **WHEN** se consultan los movimientos del `2026-11-10`
- **THEN** la respuesta devuelve `totales_vigentes` con `efectivo=130000`, `transferencia=0`, `mp=30000` y `os=40000`

#### Scenario: Los anulados no suman

- **GIVEN** T1 con un ingreso vigente de `100000` y otro anulado de `50000` el mismo día
- **WHEN** se consultan los totales del día
- **THEN** el total del medio correspondiente es `100000` y el movimiento anulado aparece listado como anulado

#### Scenario: Un día sin movimientos devuelve totales en cero

- **GIVEN** T1 sin movimientos el `2026-11-08`
- **WHEN** se consultan los movimientos del `2026-11-08`
- **THEN** los cuatro totales son `0`, la lista de movimientos está vacía, `totales_cierre` es `null`, `difieren_del_cierre=false` y el estado del cierre es `abierto`

#### Scenario: La consulta informa el estado del cierre

- **GIVEN** T1 con el `2026-11-10` cerrado y el `2026-11-11` sin cierre
- **WHEN** se consultan ambos días
- **THEN** el `2026-11-10` devuelve `cerrado` con `totales_cierre` y el `2026-11-11` devuelve `abierto` con `totales_cierre=null`

#### Scenario: Un día cerrado con anulación posterior informa las dos cifras

- **GIVEN** T1 con el `2026-11-10` cerrado con `total_efectivo=150000` y un ingreso de `150000` anulado el `2026-11-11`
- **WHEN** se consultan los movimientos del `2026-11-10`
- **THEN** la respuesta devuelve `totales_vigentes.efectivo=0`, `totales_cierre.total_efectivo=150000` y `difieren_del_cierre=true`, sin recalcular el cierre

#### Scenario: La fecha es obligatoria

- **GIVEN** T1 con movimientos
- **WHEN** se llama `GET /api/caja/movimientos` sin `fecha`
- **THEN** el sistema responde `422` y no devuelve movimientos de ningún día

### Requirement: Reportes base de caja

El sistema SHALL exponer la facturación neta por medio y por día sobre movimientos vigentes, declarando `fuente: "movimientos_vigentes"`, y el listado de cierres del período; SHALL NOT exponer ocupación, ausentismo ni facturación por profesional (C-15).

#### Scenario: Facturación por medio en un rango

- **GIVEN** T1 con movimientos vigentes en `2026-11-09` y `2026-11-10`
- **WHEN** se pide `GET /api/caja/reportes?desde=2026-11-09&hasta=2026-11-10`
- **THEN** la respuesta devuelve totales netos por día y por medio, `fuente="movimientos_vigentes"` y ningún dato personal

#### Scenario: El reporte excluye movimientos anulados

- **GIVEN** T1 con un ingreso vigente de `100000` y otro anulado de `50000` el `2026-11-09`
- **WHEN** se pide el reporte del `2026-11-09`
- **THEN** el total del medio es `100000` y el monto anulado no aparece sumado

#### Scenario: Los datos de T2 no entran en el reporte de T1

- **GIVEN** T1 con un ingreso de `100000` y T2 con un ingreso de `900000` el mismo día
- **WHEN** un actor de T1 pide el reporte del día
- **THEN** el total es `100000` y no aparece ningún movimiento de T2

#### Scenario: Listado de cierres del período

- **GIVEN** T1 con los cierres de `2026-11-09` y `2026-11-10`
- **WHEN** se pide `GET /api/caja/cierres?desde=2026-11-09&hasta=2026-11-10`
- **THEN** devuelve ambos con fecha, totales, `efectivo_contado`, `diferencia` y `responsable_id`

#### Scenario: Los cierres de T2 no se listan en T1

- **GIVEN** T1 con un cierre y T2 con dos cierres del mismo período
- **WHEN** un actor de T1 pide los cierres del período
- **THEN** devuelve solo el cierre de T1 y ninguna fila de T2

#### Scenario: Un rango inválido se rechaza

- **GIVEN** T1 con movimientos
- **WHEN** se pide `GET /api/caja/reportes?desde=2026-11-10&hasta=2026-11-09`
- **THEN** el sistema responde `422` y no calcula el reporte

#### Scenario: Los KPIs de agenda no están en caja

- **GIVEN** T1 con movimientos y turnos
- **WHEN** se intenta `GET /api/caja/reportes/ocupacion` o `GET /api/caja/reportes/facturacion-profesional`
- **THEN** el sistema responde `404` o `405`, nunca `200`, porque esos KPIs son de C-15

### Requirement: RBAC de caja

`ODONTOLOGO` SHALL tener sólo lectura; `RECEPCION` y `ADMIN` SHALL registrar movimientos, cobrar pendientes, cerrar el día y leer reportes; sólo `ADMIN` SHALL anular con motivo y exportar; un rol sin permiso SHALL recibir `403`; una identidad de paciente SHALL recibir `401`.

#### Scenario: Recepción registra un movimiento y cobra un pendiente

- **GIVEN** T1 con el usuario U1 de recepción y un cobro pendiente
- **WHEN** U1 registra un ingreso y cobra el pendiente
- **THEN** ambas operaciones responden `201`/`200` y quedan con `usuario_id=U1`

#### Scenario: El odontólogo lee pero no escribe

- **GIVEN** T1 con el odontólogo U3
- **WHEN** U3 consulta los movimientos del día y luego intenta registrar uno
- **THEN** la consulta responde `200` y el alta responde `403` sin persistir nada

#### Scenario: Recepción no puede anular

- **GIVEN** T1 con un movimiento vigente y el usuario U1 de recepción
- **WHEN** U1 intenta anular el movimiento con un motivo válido
- **THEN** el sistema responde `403`, el movimiento sigue vigente y no se crea compensatorio ni ajuste (C10-OQ-9)

#### Scenario: Admin anula con motivo

- **GIVEN** T1 con un movimiento vigente y el usuario U2 de ADMIN
- **WHEN** U2 anula el movimiento con un motivo válido
- **THEN** el sistema responde `200` y la anulación queda registrada con `anulado_por=U2`

#### Scenario: Recepción lee los reportes de caja

- **GIVEN** T1 con movimientos y el usuario U1 de recepción
- **WHEN** U1 pide `GET /api/caja/reportes` y `GET /api/caja/cierres`
- **THEN** ambas consultas responden `200` con los datos de T1

#### Scenario: La exportación de caja no existe en C-10 y es de ADMIN

- **GIVEN** T1 con el usuario U1 de recepción y el usuario U2 de ADMIN
- **WHEN** cualquiera de los dos pide `GET /api/caja/reportes/export`
- **THEN** el sistema responde `404` o `405`, nunca `200`, porque la exportación 1-clic es de ADMIN y vive en C-15 (`03_actores_y_roles.md:28`, `CHANGES.md:406`)

#### Scenario: El paciente no tiene sesión ni acceso a la caja

- **GIVEN** T1 con movimientos del día
- **WHEN** una petición se presenta con identidad de paciente para leer o registrar movimientos
- **THEN** el sistema responde `401` y no expone ni registra nada

### Requirement: Aislamiento multi-tenant de caja

Toda operación sobre movimientos, cobros pendientes, ajustes, cuentas por cobrar OS, reportes y cierres SHALL acotarse al `tenant_id`; un recurso de otro tenant SHALL NOT poder leerse, anularse, cobrarse ni imputarse desde el tenant actual.

#### Scenario: Un movimiento de T1 no se ve desde T2

- **GIVEN** T1 con el movimiento M1 del `2026-11-10` y el tenant T2
- **WHEN** un actor de T2 consulta los movimientos del `2026-11-10`
- **THEN** M1 no aparece y la consulta de M1 por id responde `404`

#### Scenario: Anular desde otro tenant falla

- **GIVEN** T2 y el movimiento M1 de T1
- **WHEN** un ADMIN de T2 intenta anular M1
- **THEN** el sistema responde `404`, M1 sigue vigente y no se crea compensatorio ni ajuste

#### Scenario: Cobrar un pendiente desde otro tenant falla

- **GIVEN** T2 y el cobro pendiente PEND-1 de T1
- **WHEN** un usuario de T2 intenta cobrarlo
- **THEN** el sistema responde `404` y no se crea ningún movimiento en T2

#### Scenario: Un ajuste de T1 no se lee desde T2

- **GIVEN** T1 con un ajuste post-cierre y el tenant T2
- **WHEN** un actor de T2 consulta el cierre y los movimientos del día ajustado
- **THEN** el ajuste no aparece y el cierre de T1 responde `404`

### Requirement: Migración 008 con RLS y trazabilidad

La migración 008 SHALL crear `movimientos_caja`, `cierres_diarios`, `cobros_pendientes`, `ajustes_post_cierre` y `cuentas_por_cobrar_os` con `tenant_id NOT NULL`, RLS forzada fail-closed, CHECKs de dominio y los UNIQUE de cierre e idempotencia, y SHALL ser reversible sin tocar 001–007 ni `aceptaciones`.

#### Scenario: La base llega a head con las tablas de caja

- **GIVEN** una base con las revisiones 001–007 aplicadas
- **WHEN** se ejecuta `alembic upgrade head`
- **THEN** existen las cinco tablas nuevas con RLS forzada, y la versión vigente es 008

#### Scenario: El downgrade elimina sólo la 008

- **GIVEN** una base en la revisión 008
- **WHEN** se ejecuta `alembic downgrade 007_odontograma_presupuesto`
- **THEN** las cinco tablas se eliminan, las tablas de 001–007 quedan intactas y re-upgradeables

#### Scenario: La 008 no toca aceptaciones

- **GIVEN** una base en la revisión 008
- **WHEN** se inspeccionan las columnas de `aceptaciones`
- **THEN** son las mismas de la 007 y no existe una columna `medio`, porque el medio de pago vive solo en `movimientos_caja`

#### Scenario: Sin tenant la RLS devuelve cero filas

- **GIVEN** la base en 008 con movimientos de T1 y el rol de aplicación sin `app.tenant_id` o con cadena vacía
- **WHEN** se consulta cualquiera de las cinco tablas
- **THEN** la consulta devuelve 0 filas sin lanzar el error `42704`

#### Scenario: La base rechaza montos y anulaciones inválidas

- **GIVEN** la base en 008
- **WHEN** se intenta insertar un movimiento con `monto=0` o marcar `anulado=true` sin motivo ni actor
- **THEN** la base rechaza la fila por el CHECK correspondiente

#### Scenario: La base exige tramo en la imputación

- **GIVEN** la base en 008
- **WHEN** se intenta insertar un movimiento con `origen='IMPUTACION'` y `tramo=NULL`, o con `tramo='OTRO'`
- **THEN** la base rechaza la fila por el CHECK de `tramo`

#### Scenario: La idempotencia de imputación es por tramo y tenant-scoped

- **GIVEN** una imputación de T1 para la línea L1 con `tramo='PACIENTE'`
- **WHEN** se intenta insertar otra fila de T1 con la misma `linea_id` y `tramo` pero otro `medio`, y la misma combinación en T2
- **THEN** la base rechaza la segunda fila de T1 y acepta la de T2

#### Scenario: El pendiente es único por línea aunque esté resuelto

- **GIVEN** la base en 008 con un pendiente resuelto de L1 en T1
- **WHEN** se intenta insertar otro pendiente de L1 en T1
- **THEN** el UNIQUE de `(tenant_id, linea_id)` rechaza la fila, aunque el primero esté resuelto

#### Scenario: Los movimientos no se editan ni se borran

- **GIVEN** la base en 008 con el movimiento M1 de `monto=150000`
- **WHEN** como `turnos_app` se intenta `UPDATE` de `monto` o `medio`, o `DELETE` de M1
- **THEN** la base rechaza la operación y M1 permanece intacto; `UPDATE` de las columnas de anulación sí está permitido

#### Scenario: El ajuste post-cierre es inmutable

- **GIVEN** la base en 008 con un ajuste persistido
- **WHEN** como `turnos_app` se intenta `UPDATE` o `DELETE` sobre `ajustes_post_cierre`
- **THEN** la base rechaza la operación y el ajuste permanece intacto

### Requirement: Sin PHI en caja

El sistema SHALL NOT incluir nombre, DNI, teléfono ni texto clínico en logs, errores ni respuestas de caja; los schemas SHALL usar allow-list estricta y SHALL rechazar campos extra.

#### Scenario: Un error de caja no vuelca PHI

- **GIVEN** un movimiento de un paciente con datos personales
- **WHEN** se produce un error de dominio al anularlo
- **THEN** la respuesta incluye sólo el código y el mensaje de dominio, sin nombre, DNI ni teléfono

#### Scenario: El schema rechaza campos extra

- **GIVEN** un payload de movimiento con `tenant_id` o `paciente_nombre` inyectados
- **WHEN** se envía a la API
- **THEN** el sistema responde `422` y no procesa el movimiento

#### Scenario: Los logs sólo llevan identificadores y montos

- **GIVEN** un movimiento registrado correctamente
- **WHEN** se escribe el log estructurado
- **THEN** contiene `tenant_id`, `movimiento_id`, `fecha`, `medio` y `monto`, y no datos personales ni texto clínico

### Requirement: Auditoría append-only de caja

Toda mutación de caja SHALL escribir un registro de auditoría inmutable con `tenant_id`, actor, acción, `antes`/`después`, timestamp y sin PHI.

#### Scenario: Registrar un movimiento deja auditoría

- **GIVEN** T1 con el usuario U1
- **WHEN** U1 registra un movimiento
- **THEN** se escribe `MOVIMIENTO_CAJA_REGISTRADO` con `tenant_id`, actor, `movimiento_id`, `fecha`, `medio`, `tipo` y `monto`

#### Scenario: Anular deja auditoría con el antes y el después

- **GIVEN** T1 con un movimiento vigente
- **WHEN** ADMIN lo anula con `motivo="cobro duplicado"`
- **THEN** se escribe `MOVIMIENTO_CAJA_ANULADO` con `movimiento_id`, el motivo, el actor, `antes={"anulado": false}` y `después={"anulado": true, "motivo_anulacion": "cobro duplicado"}`, sin PHI

#### Scenario: El compensatorio deja auditoría y referencia al original

- **GIVEN** T1 con un movimiento de un día cerrado
- **WHEN** ADMIN lo anula y se crea el compensatorio
- **THEN** se escribe `MOVIMIENTO_COMPENSATORIO_REGISTRADO` con `movimiento_id`, `compensa_a_id`, `medio`, `tipo`, `monto` y `fecha`

#### Scenario: El ajuste post-cierre deja auditoría

- **GIVEN** T1 con un movimiento de un día cerrado y un pendiente de ese día
- **WHEN** ADMIN anula el movimiento y U1 cobra el pendiente
- **THEN** se escriben `AJUSTE_POST_CIERRE_REGISTRADO` con `ajuste_id`, `cierre_id`, `tipo`, `monto`, `medio` y `compensatorio_id`, sin PHI

#### Scenario: Los pendientes dejan auditoría

- **GIVEN** T1 con una imputación sin medio y luego el cobro del pendiente
- **WHEN** se registran ambas operaciones
- **THEN** se escriben `COBRO_PENDIENTE_REGISTRADO` y `COBRO_PENDIENTE_RESUELTO` con ids y montos, sin PHI

#### Scenario: La auditoría de caja es append-only

- **GIVEN** una entrada de auditoría de caja
- **WHEN** se intenta `UPDATE` o `DELETE` sobre ella
- **THEN** la operación se rechaza y la entrada original permanece intacta
