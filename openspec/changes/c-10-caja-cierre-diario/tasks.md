# Tasks — C-10 `caja-cierre-diario`

> Estado: **preparado, no implementado**. Governance **ALTO**: no se empieza hasta que el
> dueño apruebe el proposal/design/specs. Decisiones del dueño del 2026-11-12 ya incorporadas:
> **D1** `ajustes_post_cierre`, **D2** C-09 intacto (`503` vía aceptación), **D3** motivo
> obligatorio/observación opcional, **D4** tramo OS como cuenta por cobrar informativa.
> TDD rojo-primero: cada tarea nombra el test exacto que la verifica y el archivo destino.
> **C-10 v1 es backend + contratos + migración 008 + tests**: no hay tareas de frontend
> ejecutables (la UI está diferida a `C-10-UI`, ver §12).
> Corrida backend: `py -m pytest tests/ -q` (launcher `py`, nunca `python`).
> **Gate obligatorio (§11)**: la suite debe correr con `C02_DATABASE_URL` y `skipped == 0`; sin
> esa variable el gate falla. `mypy --strict` (`py -m mypy backend/app/caja`) también es gate.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", PACI-1/PACI-9, "Conducto Demo",
> usuarios U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO); nunca datos reales ni montos reales
> (RN-GL-03). Reloj siempre inyectado; fechas operativas `YYYY-MM-DD` e instantes en `-03:00`.

## 1. Migración 008 y modelos SQLAlchemy

- [x] 1.1 Escribir el test de migración (rojo):
  `tests/test_migracion_008.py::test_upgrade_head_crea_tablas_de_caja`
  (`alembic upgrade head` ⇒ existen `movimientos_caja`, `cierres_diarios`,
  `cobros_pendientes`, `ajustes_post_cierre` y `cuentas_por_cobrar_os`;
  `down_revision="007_odontograma_presupuesto"`).
- [x] 1.2 Implementar `backend/alembic/versions/008_caja_cierre_diario.py` con las 5 tablas,
  FKs, índices, CHECKs, UNIQUE del cierre, UNIQUE por `(tenant_id, linea_id, tramo)`, UNIQUE de
  pendientes por `(tenant_id, linea_id)` sin condición de resolución y RLS forzada fail-closed
  (D7/D8) hasta que 1.1 pase.
- [x] 1.3 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_downgrade_elimina_solo_008`
  (`alembic downgrade 007_odontograma_presupuesto` ⇒ las 5 tablas fuera, 001–007 intactas y
  re-upgrade limpio).
- [x] 1.4 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_008_no_toca_aceptaciones`
  (las columnas de `aceptaciones` son las de la 007 y no se le agrega ninguna columna nueva, M7).
- [x] 1.5 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_check_monto_anulacion_y_diferencia_en_db`
  (`monto=0` y negativo rechazados; `anulado=true` sin motivo/actor/instante rechazado;
  `diferencia <> efectivo_contado - total_efectivo` rechazada; `efectivo_contado=-1` rechazado;
  `medio='CHEQUE'` y `tipo='AJUSTE'` rechazados; `origen='COMPENSACION'` sin `compensa_a_id`
  rechazado; `origen='IMPUTACION'` con `tramo=NULL` o `tramo='OTRO'` rechazado).
- [x] 1.6 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_check_diferencia_solo_exige_motivo`
  (`diferencia≠0` con `motivo_diferencia` y sin `observacion` aceptado; `diferencia≠0` sin motivo
  rechazado por el CHECK; `motivo_diferencia=""` rechazado; `observacion=""` rechazada, M2).
- [x] 1.7 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_unique_cierre_e_idempotencia_por_tramo`
  (`UNIQUE (tenant_id, fecha)` rechaza el segundo cierre de T1 y acepta el mismo día en T2; el
  UNIQUE parcial `(tenant_id, linea_id, tramo)` rechaza el segundo movimiento de imputación de T1
  aunque cambie el `medio`, acepta `tramo='OS'` junto a `tramo='PACIENTE'` de la misma línea y
  acepta el de T2; una fila `MANUAL` con la misma línea no colisiona).
- [x] 1.8 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_unique_pendiente_y_cuenta_por_cobrar_os`
  (`cobros_pendientes` rechaza un segundo pendiente de la misma línea **aunque el primero esté
  resuelto**; `cuentas_por_cobrar_os` rechaza el segundo devengado de la misma línea; ambos
  aceptan la misma línea en T2).
- [x] 1.9 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_check_ajuste_post_cierre`
  (`AJUSTE_ANULACION` sin `movimiento_original_id` rechazado; `COBRO_PENDIENTE` sin
  `cobro_pendiente_id` rechazado; `monto=0` rechazado; `motivo` vacío en `AJUSTE_ANULACION`
  rechazado; segundo ajuste para el mismo original rechazado por el UNIQUE parcial).
- [x] 1.10 Escribir y hacer pasar
  `tests/test_migracion_008.py::test_rls_fail_closed_y_grants_caja` (integración; como
  `turnos_app` sin `app.tenant_id` **o con cadena vacía** ⇒ 0 filas sin error `42704` en las 5
  tablas; `DELETE` de movimientos rechazado; `UPDATE` de `monto`/`medio`/`tramo`/`fecha`
  rechazado; `UPDATE` de las 4 columnas de anulación permitido; `UPDATE`/`DELETE` de
  `cierres_diarios`, `ajustes_post_cierre` y `cuentas_por_cobrar_os` rechazados;
  `UPDATE (resuelto_en, movimiento_id)` de pendientes permitido y `DELETE` rechazado, N1).
- [x] 1.11 Escribir el test de modelos (rojo):
  `tests/test_migracion_008.py::test_modelos_sqlalchemy_caja_cargan_sin_errores`; implementar
  `backend/app/models/caja.py` (`MovimientoCaja`, `CierreDiario`, `CobroPendiente`,
  `AjustePostCierre`, `CuentaPorCobrarOS`) con `Mapped[...]`, `Date` para la fecha operativa,
  `timestamptz` para los instantes, PK uuid y CHECKs espejo de la migración.

## 2. Dominio de caja (movimientos)

- [x] 2.1 Escribir el test de puertos en memoria (rojo):
  `tests/test_caja_puertos.py::test_repositorios_scoped_por_tenant`; implementar
  `backend/app/caja/puertos.py` con entidades (`Movimiento`, `Cierre`, `CobroPendiente`,
  `Ajuste`, `CuentaPorCobrarOS`), los protocolos de §Seams, `TotalesCajaPort`, `AuditoriaPort`,
  `UnidadDeTrabajo` y adaptadores en memoria. `MedioPago` se **importa** de
  `app.presupuesto.puertos` (M11).
- [x] 2.2 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_caja.py::test_registrar_ingreso_efectivo`
  (`INGRESO` de `150000` con `medio=EFECTIVO`, `fecha=2026-11-10`, `turno_id=TUR-1`,
  `usuario_id=U1`, `anulado=false`, `origen=MANUAL`, `tramo=NULL`).
- [x] 2.3 Escribir y hacer pasar `tests/test_caja.py::test_registrar_egreso`
  (`EGRESO` de `20000` con `medio=TRANSFERENCIA` y total del medio con signo negativo).
- [x] 2.4 Escribir y hacer pasar `tests/test_caja.py::test_cuatro_medios_validos`
  (un ingreso por cada medio ⇒ 4 movimientos y 4 totales por medio).
- [x] 2.5 Escribir y hacer pasar `tests/test_caja.py::test_monto_invalido_422`
  (`monto=0`, `-100`, `1000.5`, `"1000"` ⇒ `422` y 0 movimientos).
- [x] 2.6 Escribir y hacer pasar `tests/test_caja.py::test_medio_o_tipo_invalido_422`
  (`medio="CHEQUE"`, `tipo="AJUSTE"` ⇒ `422` y 0 movimientos).
- [x] 2.7 Escribir y hacer pasar `tests/test_caja.py::test_fecha_mal_formada_422`
  (`fecha="10/11/2026"` y `fecha="2026-11-10T10:00:00-03:00"` ⇒ `422`).
- [x] 2.8 Escribir y hacer pasar `tests/test_caja.py::test_sin_fecha_usa_reloj_servidor`
  (`ahora=2026-11-10T22:00:00-03:00` ⇒ `fecha=2026-11-10`).
- [x] 2.9 Escribir y hacer pasar `tests/test_caja.py::test_dia_operativo_offset_menos_03`
  (`ahora=2026-11-11T01:30:00Z` ⇒ `fecha=2026-11-10`; documenta C10-OQ-8).
- [x] 2.10 Escribir y hacer pasar `tests/test_caja.py::test_turno_otro_tenant_404`
  (`turno_id` de T2 ⇒ `404`, movimiento no persistido).
- [x] 2.11 Escribir y hacer pasar `tests/test_caja.py::test_movimiento_sin_patch_ni_delete`
  (`PATCH`/`DELETE` de movimiento ⇒ `405`/`403`/`404`, nunca `200`; el movimiento sigue intacto).

## 3. Anulación, compensación y ajustes post-cierre

- [x] 3.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_anulacion_caja.py::test_anular_dia_abierto_excluye_de_totales`
  (ingreso de `150000` anulado con motivo ⇒ `anulado=true` con actor e instante, sin
  compensatorio ni ajuste, total de efectivo en `0`).
- [x] 3.2 Escribir y hacer pasar `tests/test_anulacion_caja.py::test_anular_sin_motivo_422`
  (sin `motivo` y con `motivo=""` ⇒ `422`, el movimiento sigue vigente).
- [x] 3.3 Escribir y hacer pasar `tests/test_anulacion_caja.py::test_segunda_anulacion_409`
  (`409 ANULADO`, la anulación original no cambia, sin segundo compensatorio ni segundo ajuste).
- [x] 3.4 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_anulacion_conserva_monto_y_medio`
  (el movimiento anulado devuelve `monto`, `medio` y `tipo` originales).
- [x] 3.5 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_post_movimiento_en_dia_cerrado_409`
  (`409 CIERRE_CERRADO`, nada persistido, cierre sin cambios).
- [x] 3.6 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_anular_post_cierre_crea_compensatorio`
  (`ahora=2026-11-11T09:00:00-03:00` ⇒ `EGRESO` de `150000` `EFECTIVO`,
  `origen=COMPENSACION`, `compensa_a_id=M1`, mismo motivo y `fecha=2026-11-11`).
- [x] 3.7 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_anular_post_cierre_asienta_ajuste`
  (`ajustes_post_cierre` con `tipo=AJUSTE_ANULACION`, `cierre_id` del día cerrado,
  `movimiento_original_id=M1`, `monto=150000`, `medio=EFECTIVO`, el motivo, el actor y
  `compensatorio_id` del compensatorio; D1).
- [x] 3.8 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_anulacion_post_cierre_no_inserta_en_la_fecha_cerrada`
  (la cantidad de movimientos con `fecha=2026-11-10` no cambia; ningún movimiento de ese día
  cambia `monto`/`medio`; el compensatorio sólo existe en `2026-11-11`).
- [x] 3.9 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_compensatorio_no_edita_el_cierre`
  (totales, `efectivo_contado`, `diferencia` y `cerrado_at` del cierre sin cambios y 0
  `UPDATE` sobre `cierres_diarios`).
- [x] 3.10 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_compensatorio_de_egreso_es_ingreso`
  (`EGRESO` de `20000` `TRANSFERENCIA` anulado post-cierre ⇒ `INGRESO` compensatorio del mismo
  monto y medio, y suma al total de transferencia del día del registro, N3).
- [x] 3.11 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_compensatorio_cuenta_en_dia_del_registro`
  (el compensatorio descuenta del total del `2026-11-11`, no del `2026-11-10`).
- [x] 3.12 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_anular_un_compensatorio`
  (un compensatorio de un día abierto se anula con motivo ⇒ `200`, sin segundo compensatorio, N7).
- [x] 3.13 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_dia_del_registro_cerrado_409`
  (`2026-11-10` y `2026-11-11` cerrados ⇒ anular el movimiento de `2026-11-10` responde
  `409 CIERRE_CERRADO`, no anula y no crea compensatorio ni ajuste).
- [x] 3.14 Escribir y hacer pasar
  `tests/test_anulacion_caja.py::test_ajuste_no_suma_en_totales`
  (el ajuste no aparece como movimiento ni suma en los totales del día cerrado ni del día del
  registro).
- [x] 3.15 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**)
  `tests/test_anulacion_concurrente_pg.py::test_dos_anulaciones_dejan_un_compensatorio`
  (una `200`, una `409`, exactamente un compensatorio y un ajuste, sin `500`).

## 4. Cobros pendientes (`medio=NULL` de C-09)

- [x] 4.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_cobros_pendientes.py::test_imputacion_sin_medio_crea_pendiente_sin_movimiento`
  (L1 de `a_cargo_paciente=60000` y `cobertura_os=0` ⇒ 1 pendiente de `60000` con
  `fecha=2026-11-10`, 0 movimientos y total del día sin cambios).
- [x] 4.2 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_cobrar_pendiente_crea_movimiento_y_audita`
  (`medio=TRANSFERENCIA` y día abierto ⇒ `INGRESO` de `60000` con trazabilidad de L1,
  `tramo=PACIENTE`, `resuelto_en` y `movimiento_id`, más `COBRO_PENDIENTE_RESUELTO`).
- [x] 4.3 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_pendiente_resuelto_no_se_cobra_dos_veces`
  (`409 COBRO_YA_RESUELTO`, un solo movimiento).
- [x] 4.4 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_replay_sin_medio_no_crea_segundo_pendiente`
  (el replay de la imputación sin medio con el pendiente **abierto** y **resuelto** no crea un
  segundo pendiente; la misma línea en T2 sí puede tener el suyo; H1).
- [x] 4.5 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_replay_con_otro_medio_409`
  (`409 IMPUTACION_DUPLICADA` y un solo movimiento en el día, aunque el `medio` cambie; H1).
- [x] 4.6 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_cobro_con_fecha_cerrada_asienta_ajuste_201`
  (`fecha` del pendiente cerrada y `ahora=2026-11-11T09:00:00-03:00` ⇒ `201`, `INGRESO` con
  `fecha=2026-11-11`, pendiente resuelto, ajuste `COBRO_PENDIENTE` con el `cierre_id` del día
  cerrado y el cierre con sus totales intactos; H4).
- [x] 4.7 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_imputacion_sin_medio_en_dia_cerrado_409`
  (`409 CIERRE_CERRADO`, 0 pendientes y 0 movimientos).
- [x] 4.8 Escribir y hacer pasar
  `tests/test_cobros_pendientes.py::test_tramo_cero_no_crea_pendiente`
  (`a_cargo_paciente=0` y `medio=NULL` ⇒ 0 pendientes, 0 movimientos, sin error).

## 5. Adaptador real del puerto de C-09 (contrato intacto)

- [ ] 5.1 Escribir el test de contrato (rojo) y hacerlo pasar:
  `tests/test_contrato_imputacion_caja.py::test_firma_del_puerto_es_la_de_c09`
  (inspección de `ImputacionPort.imputar_caja`: mismos nombres y orden de parámetros, todos
  keyword-only; el adaptador de C-10 satisface el protocolo; `imputar_agenda` sigue siendo no-op
  y no crea turnos).
- [ ] 5.2 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_contrato_imputacion_caja.py::test_medio_pago_se_importa_no_se_redeclara`
  (`app.caja` y `app.caja.adaptador_imputacion` usan exactamente
  `app.presupuesto.puertos.MedioPago` (`__module__`/identidad), no un `Literal` propio, y la
  anotación del parámetro `medio` del adaptador coincide con la del protocolo; M11).
- [ ] 5.3 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_imputacion_caja.py::test_solo_tramo_paciente_crea_un_movimiento`
  (`monto=100000`, `cobertura_os=0`, `a_cargo_paciente=100000`, `medio=EFECTIVO` ⇒ 1 `INGRESO`
  con `tramo=PACIENTE`, `usuario_id=U1`, `presupuesto_id` y `linea_id`).
- [ ] 5.4 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_tramo_os_crea_cuenta_por_cobrar`
  (`cobertura_os=40000`, `a_cargo_paciente=0` ⇒ 1 cuenta por cobrar OS de `40000`, 0 movimientos
  y total del día sin cambios; D4).
- [ ] 5.5 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_dos_tramos_crean_movimiento_y_cuenta_por_cobrar`
  (`60000` `EFECTIVO` + `40000` OS ⇒ 1 `INGRESO` de `60000` `tramo=PACIENTE`, 1 cuenta por cobrar
  OS de `40000`, 0 `INGRESO` con `medio=OS`, y la suma de movimientos del día es `60000`).
- [ ] 5.6 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_os_no_genera_dos_ingresos_por_la_misma_linea`
  (repetir la imputación de L1 no crea otro devengado ni un `INGRESO` de OS; después de la
  acreditación de C-12 el UNIQUE por `(linea, tramo='OS')` sigue impidiendo un segundo ingreso;
  D4).
- [ ] 5.7 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_medio_os_en_tramo_paciente_422`
  (adaptador invocado directamente ⇒ `422 MEDIO_OS_RESERVADO`, 0 movimientos y 0 cuentas por
  cobrar; documenta C10-OQ-5 y el punto de observación).
- [ ] 5.8 Escribir y hacer pasar `tests/test_imputacion_caja.py::test_turno_se_persiste`
  (`turno_id=TUR-1`, `medio=MP` ⇒ el movimiento guarda `turno_id` y `medio`).
- [ ] 5.9 Escribir y hacer pasar `tests/test_imputacion_caja.py::test_replay_identico_no_duplica`
  (misma línea/tramo/medio/monto ⇒ un solo movimiento, sin excepción).
- [ ] 5.10 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_replay_con_otro_medio_409`
  (`409 IMPUTACION_DUPLICADA`, un solo `INGRESO` y el existente no se modifica; H1).
- [ ] 5.11 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_replay_con_monto_distinto_409`
  (`409 IMPUTACION_DUPLICADA`, el movimiento existente no se modifica).
- [ ] 5.12 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_imputacion_no_crea_turno`
  (integración: la tabla `turnos` no cambia al imputar; `imputar_agenda` sigue sin efectos).
- [ ] 5.13 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_imputacion_en_dia_cerrado_409`
  (el adaptador invocado directamente con una fecha cerrada ⇒ `409 CIERRE_CERRADO` y 0 escrituras).
- [ ] 5.14 Escribir y hacer pasar
  `tests/test_imputacion_caja.py::test_imputacion_de_otra_linea_tenant_404`
  (`linea_id` de T2 con `tenant_id=T1` ⇒ `404`, 0 movimientos, 0 pendientes y 0 cuentas por
  cobrar en T1).
- [ ] 5.15 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**)
  `tests/test_imputacion_concurrente_pg.py::test_dos_imputaciones_crean_un_solo_movimiento`
  (una inspección real del UNIQUE por `(linea, tramo)`; ninguna conexión responde `500`).
- [ ] 5.16 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**, M4)
  `tests/test_imputacion_atomica_pg.py::test_fallo_de_caja_revierte_la_aceptacion_de_c09`
  (aceptación real de C-09 con la 007 y la 008 aplicadas: cuando la escritura de caja falla, la
  transacción revierte `aceptaciones`, `presupuesto_lineas`/estado y no deja movimientos; se
  verifica en la misma unidad de trabajo, **no** con adaptadores en memoria).
- [ ] 5.17 Escribir y hacer pasar (integración)
  `tests/test_imputacion_caja.py::test_aceptacion_con_dia_cerrado_responde_503`
  (`POST /api/presupuestos/{id}/aceptar` con el día cerrado ⇒ `503`, 0 aceptaciones, presupuesto
  `VIGENTE` y 0 movimientos; H5/D2).

## 6. Cierre diario

- [ ] 6.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_cierre_caja.py::test_cierre_diferencia_cero`
  (ingreso de `100000` en efectivo y `efectivo_contado=100000` ⇒ `diferencia=0` y `cerrado_at`).
- [ ] 6.2 Escribir y hacer pasar `tests/test_cierre_caja.py::test_totales_por_medio_netos`
  (ingresos `150000` efectivo, `30000` transferencia, `20000` MP, `40000` OS y egreso `50000`
  efectivo ⇒ cuatro totales de caja correctos y `diferencia=0`).
- [ ] 6.3 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_total_os_es_devengado_informativo`
  (L1 con `cobertura_os=40000` y `a_cargo_paciente=60000` en efectivo ⇒ `total_os=40000`,
  `total_os_cobrado=0`, `diferencia=0` y el devengado no cambia ningún total de caja; D4/M12).
- [ ] 6.4 Escribir y hacer pasar `tests/test_cierre_caja.py::test_total_os_cobrado_es_caja`
  (un `INGRESO` manual de `40000` con `medio=OS` ⇒ `total_os_cobrado=40000` y `total_os` sin
  cambios).
- [ ] 6.5 Escribir y hacer pasar `tests/test_cierre_caja.py::test_diferencia_faltante`
  (`efectivo_contado=95000` con motivo ⇒ `diferencia=-5000`).
- [ ] 6.6 Escribir y hacer pasar `tests/test_cierre_caja.py::test_diferencia_sobrante`
  (`efectivo_contado=102000` con motivo ⇒ `diferencia=2000`).
- [ ] 6.7 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_diferencia_solo_contra_efectivo`
  (`total_efectivo=100000`, `total_transferencia=30000`, `total_mp=20000` y
  `efectivo_contado=100000` ⇒ `diferencia=0`; C10-OQ-2).
- [ ] 6.8 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_sin_movimientos_cierra_en_cero`
  (totales en `0`, `diferencia=0`, con responsable; documenta C10-OQ-4).
- [ ] 6.9 Escribir y hacer pasar `tests/test_cierre_caja.py::test_segundo_cierre_409`
  (`409 CIERRE_EXISTENTE`, el cierre original intacto, una sola fila).
- [ ] 6.10 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_cierre_con_diferencia_y_motivo`
  (motivo persistido y auditado; `observacion` opcional).
- [ ] 6.11 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_cierre_con_diferencia_y_motivo_sin_observacion_201`
  (`201`, `diferencia=-5000`, `observacion` nula; D3/M2).
- [ ] 6.12 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_cierre_con_diferencia_sin_motivo_422`
  (`422`, sin cierre persistido).
- [ ] 6.13 Escribir y hacer pasar `tests/test_cierre_caja.py::test_motivo_vacio_422`
  (`motivo_diferencia=""` con observación ⇒ `422`).
- [ ] 6.14 Escribir y hacer pasar `tests/test_cierre_caja.py::test_sobrante_sin_motivo_422`
  (`efectivo_contado=102000` sin motivo ⇒ `422`).
- [ ] 6.15 Escribir y hacer pasar `tests/test_cierre_caja.py::test_diferencia_cero_sin_motivo_201`
  (`efectivo_contado=100000` y `total_efectivo=100000` sin motivo ⇒ `201`).
- [ ] 6.16 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_con_movimientos_sin_responsable_422`
  (sin `responsable_id` ⇒ `422`, sin cierre y el día sigue `abierto`; reemplaza el escenario
  inverificable de "movimiento sin responsable", M1).
- [ ] 6.17 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_sin_movimientos_sin_responsable_422`
  (sin `responsable_id` ⇒ `422`, sin cierre).
- [ ] 6.18 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_responsable_otro_tenant_404`
  (`responsable_id` de T2 ⇒ `404`, sin cierre).
- [ ] 6.19 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_responsable_queda_en_el_cierre`
  (`responsable_id=U1` y actor de auditoría U1).
- [ ] 6.20 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_efectivo_contado_negativo_422`
  (`efectivo_contado=-1` ⇒ `422`, sin cierre; N9).
- [ ] 6.21 Escribir y hacer pasar `tests/test_cierre_caja.py::test_dia_futuro_no_se_cierra`
  (reloj en `2026-11-10`, cierre del `2026-11-12` ⇒ `422`, sin cierre; interpretación N9).
- [ ] 6.22 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_anterior_sin_cerrar_no_bloquea`
  (`2026-11-09` sin cierre y alta del `2026-11-10` ⇒ `201`, el `2026-11-09` sigue abierto;
  interpretación de C10-OQ-3, M3).
- [ ] 6.23 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_cierre_atrasado_se_permite`
  (el `2026-11-09` se cierra el `2026-11-10` ⇒ `201`, estado `cerrado`; M3).
- [ ] 6.24 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_atrasado_cerrado_queda_inmutable`
  (después del cierre atrasado, un alta con `fecha=2026-11-09` ⇒ `409 CIERRE_CERRADO`).
- [ ] 6.25 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_cierre_no_se_edita_por_api`
  (`PATCH`/`DELETE` del cierre ⇒ `405`/`404`, nunca `200`; el cierre intacto).
- [ ] 6.26 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_reapertura_no_existe`
  (`POST /api/caja/cierre/reabrir` y `/api/caja/cierre/{id}/reabrir` ⇒ `404`/`405`, nunca
  `200`; documenta C10-OQ-1).
- [ ] 6.27 Escribir y hacer pasar
  `tests/test_cierre_caja.py::test_dia_cerrado_sigue_bloqueado_tras_intento_de_reapertura`
  (tras la reapertura fallida, cargar un movimiento del día cerrado sigue dando `409`).
- [ ] 6.28 Escribir y hacer pasar `tests/test_cierre_caja.py::test_estado_dia_abierto`
  (`estado=abierto`, sin totales de cierre y con total del sistema por medio).
- [ ] 6.29 Escribir y hacer pasar `tests/test_cierre_caja.py::test_estado_dia_cerrado`
  (`estado=cerrado` con totales, `efectivo_contado`, `diferencia`, responsable y `cerrado_at`).
- [ ] 6.30 Escribir y hacer pasar `tests/test_cierre_caja.py::test_cierre_otro_tenant_404`
  (cierre de T2 consultado desde T1 ⇒ `404`).
- [ ] 6.31 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**)
  `tests/test_cierre_concurrente_pg.py::test_dos_cierres_simultaneos_crean_uno_solo`
  (una `201`, una `409`, un solo cierre, sin `500`; lock por `(tenant, fecha)` antes de leer
  totales y escribir).
- [ ] 6.32 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**, H2)
  `tests/test_carrera_movimiento_cierre_pg.py::test_movimiento_y_cierre_no_se_cruzan`
  (una conexión registra un ingreso de `50000` y la otra cierra con `efectivo_contado=50000`: o el
  movimiento entra antes y el cierre lo cuenta (`total_efectivo=50000`), o el cierre gana y el
  alta responde `409 CIERRE_CERRADO`; en ningún caso queda un movimiento del día fuera del cierre
  ni un `500`).
- [ ] 6.33 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**, H2)
  `tests/test_carrera_movimiento_cierre_pg.py::test_cobro_de_pendiente_respeta_el_lock`
  (el cobro espera el lock y, si el cierre commiteó, asienta el ajuste post-cierre en lugar de
  insertar en el día cerrado).

## 7. Consulta diaria y reportes base

- [ ] 7.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_consulta_caja.py::test_totales_por_medio_del_dia`
  (`efectivo=130000`, `transferencia=0`, `mp=30000`, `os=40000` en `totales_vigentes`).
- [ ] 7.2 Escribir y hacer pasar `tests/test_consulta_caja.py::test_anulados_no_suman`
  (total `100000`; el anulado aparece listado como anulado).
- [ ] 7.3 Escribir y hacer pasar
  `tests/test_consulta_caja.py::test_dia_sin_movimientos_totales_cero`
  (cuatro totales en `0`, lista vacía, `estado=abierto`, `totales_cierre=null`,
  `difieren_del_cierre=false`).
- [ ] 7.4 Escribir y hacer pasar
  `tests/test_consulta_caja.py::test_consulta_informa_estado_cierre`
  (`2026-11-10` cerrado con `totales_cierre` y `2026-11-11` abierto con `null`).
- [ ] 7.5 Escribir y hacer pasar
  `tests/test_consulta_caja.py::test_dia_cerrado_con_anulacion_posterior_difiere`
  (`total_efectivo` del cierre `150000`, `totales_vigentes.efectivo=0` y
  `difieren_del_cierre=true` con las dos cifras; H6).
- [ ] 7.6 Escribir y hacer pasar `tests/test_consulta_caja.py::test_fecha_obligatoria_422`
  (`GET /api/caja/movimientos` sin `fecha` ⇒ `422`).
- [ ] 7.7 Escribir y hacer pasar
  `tests/test_reportes_caja.py::test_facturacion_por_medio_en_rango`
  (rango `2026-11-09..2026-11-10` ⇒ netos por día y medio, `fuente="movimientos_vigentes"`, sin
  datos personales).
- [ ] 7.8 Escribir y hacer pasar
  `tests/test_reportes_caja.py::test_reporte_excluye_anulados`
  (ingreso vigente `100000` y anulado `50000` ⇒ total `100000`).
- [ ] 7.9 Escribir y hacer pasar
  `tests/test_reportes_caja.py::test_reporte_no_incluye_t2`
  (T1 `100000` y T2 `900000` el mismo día ⇒ total de T1 `100000`, sin filas de T2; M6).
- [ ] 7.10 Escribir y hacer pasar `tests/test_reportes_caja.py::test_listado_de_cierres`
  (dos cierres con fecha, totales, `efectivo_contado`, `diferencia` y `responsable_id`).
- [ ] 7.11 Escribir y hacer pasar
  `tests/test_reportes_caja.py::test_listado_de_cierres_no_incluye_t2`
  (un cierre en T1 y dos en T2 ⇒ devuelve sólo el de T1; M6).
- [ ] 7.12 Escribir y hacer pasar `tests/test_reportes_caja.py::test_rango_invalido_422`
  (`desde > hasta` ⇒ `422` en reportes y en cierres).
- [ ] 7.13 Escribir y hacer pasar
  `tests/test_reportes_caja.py::test_kpis_de_agenda_no_expuestos`
  (`/api/caja/reportes/ocupacion` y `/api/caja/reportes/facturacion-profesional` ⇒ `404` o
  `405`, nunca `200`; documenta D12/C-15).

## 8. RBAC y aislamiento multi-tenant

- [ ] 8.1 Escribir y hacer pasar `tests/test_caja_rbac.py::test_recepcion_registra_y_cobra`
  (`201`/`200`, `usuario_id=U1`).
- [ ] 8.2 Escribir y hacer pasar `tests/test_caja_rbac.py::test_odontologo_lee_pero_no_escribe`
  (lectura `200`, alta `403`, nada persistido).
- [ ] 8.3 Escribir y hacer pasar `tests/test_caja_rbac.py::test_recepcion_no_anula_403`
  (`403`, el movimiento sigue vigente y no hay compensatorio ni ajuste; documenta C10-OQ-9).
- [ ] 8.4 Escribir y hacer pasar `tests/test_caja_rbac.py::test_admin_anula_con_motivo`
  (`200`, `anulado_por=U2`).
- [ ] 8.5 Escribir y hacer pasar `tests/test_caja_rbac.py::test_recepcion_lee_reportes`
  (`GET /api/caja/reportes` y `GET /api/caja/cierres` ⇒ `200` para U1; M5).
- [ ] 8.6 Escribir y hacer pasar `tests/test_caja_rbac.py::test_exportacion_de_caja_no_existe`
  (`GET /api/caja/reportes/export` con U1 y U2 ⇒ `404`/`405`, nunca `200`; la exportación es de
  ADMIN y vive en C-15; M5).
- [ ] 8.7 Escribir y hacer pasar `tests/test_caja_rbac.py::test_paciente_sin_sesion_401`
  (lectura y alta con identidad de paciente ⇒ `401`, nada expuesto ni persistido).
- [ ] 8.8 Escribir y hacer pasar `tests/test_caja_rbac.py::test_recepcion_cierra` (`201`).
- [ ] 8.9 Escribir y hacer pasar `tests/test_caja_rbac.py::test_admin_cierra`
  (`201`, `responsable_id=U2`).
- [ ] 8.10 Escribir y hacer pasar `tests/test_caja_rbac.py::test_odontologo_no_cierra_403`
  (`403`, día abierto, sin cierre).
- [ ] 8.11 Escribir y hacer pasar `tests/test_caja_rbac.py::test_odontologo_lee_cierre`
  (cierre y estado del día `200` con los mismos totales que recepción).
- [ ] 8.12 Escribir y hacer pasar
  `tests/test_caja_rbac.py::test_paciente_no_accede_al_cierre_401`
  (`401`, nada expuesto ni registrado).
- [ ] 8.13 Escribir y hacer pasar
  `tests/test_aislamiento_caja.py::test_movimiento_t1_no_visible_en_t2`
  (no aparece en la lista de T2 y el `GET` por id responde `404`).
- [ ] 8.14 Escribir y hacer pasar
  `tests/test_aislamiento_caja.py::test_anular_desde_otro_tenant_404`
  (M1 sigue vigente y no hay compensatorio ni ajuste).
- [ ] 8.15 Escribir y hacer pasar
  `tests/test_aislamiento_caja.py::test_cobrar_pendiente_otro_tenant_404`
  (sin movimientos en T2).
- [ ] 8.16 Escribir y hacer pasar
  `tests/test_aislamiento_caja.py::test_ajuste_no_visible_desde_otro_tenant`
  (el cierre y los ajustes de T1 no se leen desde T2).
- [ ] 8.17 Escribir y hacer pasar
  `tests/test_aislamiento_caja.py::test_imputacion_de_otro_tenant_no_escribe_en_t1`
  (`404`, 0 movimientos, 0 pendientes y 0 cuentas por cobrar en T1).

## 9. Borde API (schemas y routers)

- [ ] 9.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_api_caja.py::test_payload_con_campo_extra_422`; crear
  `backend/app/schemas/caja.py` con `extra="forbid"`, `monto` entero estricto, `date` para la
  fecha operativa, `AwareDatetime` para instantes y allow-list de salida.
- [ ] 9.2 Escribir y hacer pasar `tests/test_api_caja.py::test_crud_http_movimientos_201_200`
  (`POST/GET /api/caja/movimientos`, `POST /api/caja/movimientos/{id}/anular`,
  `GET/POST /api/caja/cierre`, `GET /api/caja/cierres`, `GET /api/caja/pendientes`,
  `POST /api/caja/pendientes/{id}/cobrar`, `GET /api/caja/reportes`) con `crear_router(svc)` y
  `actor_desde_headers`.
- [ ] 9.3 Escribir y hacer pasar `tests/test_api_caja.py::test_errores_mapean_404_403_409_422`
  (`404` cross-tenant, `403` RBAC, `409 CIERRE_CERRADO`/`ANULADO`/`IMPUTACION_DUPLICADA`/
  `COBRO_YA_RESUELTO`/`CIERRE_EXISTENTE`, `422` montos/medio/fecha/responsable/motivo,
  `401` identidad de paciente). No debe existir `MOVIMIENTOS_SIN_RESPONSABLE`.
- [ ] 9.4 Escribir y hacer pasar `tests/test_api_caja.py::test_cierre_http_201_200_409_422`
  (cierre `201`, consulta `200`, segundo cierre `409`, diferencia sin motivo `422`, diferencia
  con motivo sin observación `201`).
- [ ] 9.5 Escribir y hacer pasar `tests/test_api_caja.py::test_rutas_inexistentes_404_405`
  (reapertura, KPIs de agenda y exportación de caja ⇒ `404`/`405`, nunca `200`).
- [ ] 9.6 Escribir y hacer pasar `tests/test_api_caja.py::test_ajuste_expuesto_en_la_consulta`
  (el día cerrado con anulación posterior devuelve `totales_vigentes`, `totales_cierre` y
  `difieren_del_cierre=true`, y los ajustes asociados al cierre son consultables sin PHI).

## 10. Auditoría y PHI

- [ ] 10.1 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_movimiento_registrado_auditado`
  (`MOVIMIENTO_CAJA_REGISTRADO` con `tenant_id`, actor, `movimiento_id`, `fecha`, `medio`,
  `tipo` y `monto`).
- [ ] 10.2 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_anulacion_auditada_con_antes_y_despues`
  (`MOVIMIENTO_CAJA_ANULADO` con `movimiento_id`, motivo, actor, `antes={"anulado": false}` y
  `después={"anulado": true, ...}`; N8).
- [ ] 10.3 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_compensatorio_auditado_con_referencia`
  (`MOVIMIENTO_COMPENSATORIO_REGISTRADO` con `compensa_a_id`, `medio`, `tipo`, `monto` y
  `fecha`).
- [ ] 10.4 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_ajuste_post_cierre_auditado`
  (`AJUSTE_POST_CIERRE_REGISTRADO` con `ajuste_id`, `cierre_id`, `tipo`, `monto`, `medio` y
  `compensatorio_id`).
- [ ] 10.5 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_pendientes_auditados`
  (`COBRO_PENDIENTE_REGISTRADO` y `COBRO_PENDIENTE_RESUELTO` con ids y montos, sin PHI).
- [ ] 10.6 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_cierre_auditado_y_motivo`
  (`CIERRE_DIARIO_REGISTRADO` con `cierre_id`, `fecha`, totales, `efectivo_contado`,
  `diferencia`, `responsable_id`, `antes=null` y `después`; motivo cuando aplica).
- [ ] 10.7 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_auditoria_no_copia_observacion`
  (la entrada indica `observacion_cargada` sin copiar su contenido ni datos personales).
- [ ] 10.8 Escribir y hacer pasar
  `tests/test_auditoria_caja.py::test_auditoria_append_only`
  (`UPDATE`/`DELETE` de la entrada rechazados, original intacto).
- [ ] 10.9 Escribir y hacer pasar `tests/test_privacidad_caja.py::test_error_no_vuelca_phi`
  (error de dominio sin nombre, DNI ni teléfono).
- [ ] 10.10 Escribir y hacer pasar
  `tests/test_privacidad_caja.py::test_logs_solo_llevan_ids_y_montos`
  (`tenant_id`, `movimiento_id`, `fecha`, `medio`, `monto`; sin PHI ni texto clínico).

## 11. Regresión y gate final del change

- [ ] 11.1 Escribir y hacer pasar
  `tests/test_regresion_caja.py::test_c03_c05_c09_siguen_en_verde`
  (la 008 no toca tablas de C-03/C-05/C-09 ni `aceptaciones`; el gate de consentimiento y el
  anti-solape intactos; la aceptación de C-09 sigue respondiendo `200` con `medio=NULL` porque
  ahora existe el cobro pendiente).
- [ ] 11.2 **Gate de suite (M8)**: correr `py -m pytest tests/ -q` con `C02_DATABASE_URL`
  apuntando a PostgreSQL migrado y verificar que el resumen tenga **`skipped == 0`**. Si la
  variable no está configurada, el gate **falla explícitamente** con el mensaje
  "C02_DATABASE_URL no configurada: el gate no se acepta con skips"; no se acepta verde con tests
  de integración salteados.
- [ ] 11.3 **Gate de tipos (M11)**: correr `py -m mypy backend/app/caja` con la configuración
  `strict` de `pyproject.toml` y 0 errores.
- [ ] 11.4 Correr `openspec validate c-10-caja-cierre-diario --strict` (exit 0, sin warnings).
- [ ] 11.5 Verificar que no hay env var nueva, secretos ni tablas de C-11/C-12 en la 008;
  `.env.example` intacto.
- [ ] 11.6 Verificar que C-10 **no** toca `frontend/` ni C-09: el diff no contiene archivos de
  `frontend/`, `app.presupuesto` ni columnas nuevas en `aceptaciones`, y no hay requirements de UI en
  `## ADDED Requirements`.

## 12. Diferido a C-10-UI

> **No ejecutable en C-10.** La SPA `/caja` fue diferida por decisión del dueño (2026-11-12) al
> change `C-10-UI`, que todavía no existe. Estas tareas se planifican y ejecutan allí, contra los
> contratos de este change; C-10 no crea ni modifica archivos de `frontend/` y no crea mockups ni
> design system. Los criterios completos están en `proposal.md` §Diferido a C-10-UI.

- [ ] D.1 `frontend/src/test/caja.test.tsx::lista los movimientos del día con su medio y su total`
  (los cuatro medios, anulados marcados; sin `any`). → `C-10-UI`
- [ ] D.2 `frontend/src/test/caja.test.tsx::registra un ingreso y un egreso y refresca los totales`
  (totales calculados por el servidor, nunca en el cliente). → `C-10-UI`
- [ ] D.3 `frontend/src/test/caja.test.tsx::el día cerrado no permite cargar movimientos y ofrece compensar`
  (`409 CIERRE_CERRADO` se muestra como error, no como éxito). → `C-10-UI`
- [ ] D.4 `frontend/src/test/caja.test.tsx::muestra los cobros pendientes y permite cobrarlos con un medio`. → `C-10-UI`
- [ ] D.5 `frontend/src/test/caja.test.tsx::muestra totales vigentes y del cierre cuando difieren`
  (`difieren_del_cierre=true` rotulado como "anulación posterior al cierre"). → `C-10-UI`
- [ ] D.6 `frontend/src/test/cierre-caja.test.tsx::exige motivo cuando la diferencia no es cero y acepta observación vacía`
  (`422` visible, el día sigue abierto). → `C-10-UI`
- [ ] D.7 `frontend/src/test/cierre-caja.test.tsx::el cierre cerrado se muestra inmutable con totales persistidos`. → `C-10-UI`
- [ ] D.8 Design system + mockups aprobados, `npm run lint`/`typecheck`/`build` y screenshots
  375/768/1440 con la skill `visual-turnos`, guardados en
  `openspec/changes/c-10-ui/mockups/previews/`. → `C-10-UI`

## Workflow follow-up

- **Governance ALTO**: no correr `/opsx:apply` hasta la aprobación explícita del dueño sobre
  `proposal.md`, `design.md` y las dos delta specs.
- Correr `revisor-escenarios-turnos` sobre `specs/caja/spec.md` y `specs/cierre-caja/spec.md`
  antes de implementar y corregir los `BLOQUEANTE`/`MAYOR`.
- Cerrar con el dueño las `C10-OQ` abiertas (`design.md` §Open Questions): reapertura
  (C10-OQ-1), retro-fecha y bloqueo (C10-OQ-3), día vacío (C10-OQ-4), `OS` en el tramo del
  paciente (C10-OQ-5), señas de C-11 (C10-OQ-6), pendiente impago (C10-OQ-7) y anulación por
  recepción (C10-OQ-9). **Fijadas**: C10-OQ-2 (diferencia sólo contra efectivo), C10-OQ-8
  (offset `-03:00`) y C10-OQ-10 (OS como devengado informativo, cobro en C-12).
- Reconciliar con Martin las desviaciones del ERD: columnas nuevas de `movimientos_caja` y
  `cierres_diarios`, las tablas `cobros_pendientes`, `ajustes_post_cierre` y
  `cuentas_por_cobrar_os`, y los endpoints nuevos (`/api/caja/cierres`, `/api/caja/pendientes*`,
  `/api/caja/reportes`). **No** hay addendum a `aceptaciones` (M7).
- Coordinar con C-09 (ya archivado) que su adaptador real use `AdaptadorCaja` de C-10 y mantenga
  la firma; **C-10 no modifica** el protocolo, el servicio ni las tablas de C-09.
- Crear el change `C-10-UI` con su design system, mockups aprobados y las tareas de §12.
- Wiring SQLAlchemy real de los repositorios de caja (follow-up declarado, igual que
  C-06/C-07/C-08/C-09).
- Archivar el change recién después de implementarlo, verificarlo y con el `[x]` de `CHANGES.md`
  pedido por el dueño.
