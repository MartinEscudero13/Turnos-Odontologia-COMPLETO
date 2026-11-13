# Tasks — C-09 `odontograma-presupuesto`

> Estado: **implementado (backend + contratos + migración 007 + tests)**; la UI queda
> diferida a `C-09-UI`. TDD rojo-primero: cada tarea nombra el test
> exacto que la verifica y el archivo destino. **C-09 v1 es backend + contratos +
> migración 007 + tests**: no hay tareas de frontend ejecutables (la UI está diferida a
> `C-09-UI`, ver §Diferido a C-09-UI).
> Corrida backend: `py -m pytest tests/ -q` (launcher `py`, nunca `python`). Los tests
> nuevos se suman a la suite existente (C-04…C-08) sin tocarla.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", P1/P2, prestación "Conducto
> Demo", obras sociales `OS-1`/`OS-2`; nunca datos reales ni aranceles reales (RN-GL-03).
> Reloj siempre inyectado y escenarios redactados en `-03:00`.

## 1. Migración 007 y modelos SQLAlchemy

- [x] 1.1 Escribir el test de migración (rojo):
  `tests/test_migracion_007.py::test_upgrade_head_crea_tablas_odontograma_y_presupuesto`
  (`alembic upgrade head` ⇒ existen `odontograma_hallazgos`, `presupuestos`,
  `presupuesto_lineas` con `origen_cobertura`/`validada_en_vivo`, `aceptaciones`,
  `down_revision="006_ficha_clinica"`).
- [x] 1.2 Implementar `backend/alembic/versions/007_odontograma_presupuesto.py` con las
  4 tablas, `tenant_id NOT NULL`, FKs, índices y RLS forzada fail-closed (D7/D8) hasta
  que 1.1 pase.
- [x] 1.3 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_downgrade_elimina_solo_007`
  (`alembic downgrade 006_ficha_clinica` ⇒ 007 fuera, 001–006 intactas; re-upgrade
  limpio).
- [x] 1.4 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_check_fdi_y_suma_de_linea_en_db`
  (`pieza_fdi=19`, `29`, `39`, `49`, `20`, `30` y `40` rechazados por el CHECK de grilla
  FDI (cuadrante 1–4 × diente 1–8); `pieza_fdi=11` y `48` aceptados; `cobertura_os +
  a_cargo_paciente <> monto` rechazado por CHECK).
- [x] 1.5 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_unique_parcial_idempotency_key`
  (dos líneas de T1 con la misma key ⇒ la segunda rechazada; la misma key en T2 se
  acepta).
- [x] 1.6 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_rls_fail_closed_y_grants` (integración; como
  `turnos_app` sin `app.tenant_id` **o con cadena vacía** ⇒ 0 filas sin error `42704`;
  `UPDATE hallazgo`/`DELETE hallazgo` rechazados; `UPDATE`/`DELETE` de
  `presupuesto_lineas` rechazados; `UPDATE aceptaciones`/`DELETE aceptaciones`
  rechazados; `UPDATE resuelto` permitido).
- [x] 1.7 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_origen_cobertura_check_y_default_validada_en_vivo`
  (`origen_cobertura='OTRA_COSA'` rechazado; `validada_en_vivo` con `DEFAULT false`).
- [x] 1.8 Escribir el test de modelos (rojo):
  `tests/test_migracion_007.py::test_modelos_sqlalchemy_cargan_sin_errores`; implementar
  `backend/app/models/odontograma.py` (`OdontogramaHallazgo`) y
  `backend/app/models/presupuesto.py` (`Presupuesto`, `PresupuestoLinea` con
  `idempotency_key`, `origen_cobertura` y `validada_en_vivo`, `Aceptacion`) con
  `Mapped[...]`, `timestamptz`, PK uuid y CHECKs espejo de la migración.

## 2. Dominio del odontograma (hallazgos e historial)

- [x] 2.1 Escribir el test de puertos en memoria (rojo):
  `tests/test_odontograma_puertos.py::test_repositorio_scoped_por_tenant`; implementar
  `backend/app/odontograma/puertos.py` con entidades `Hallazgo`, protocolos
  `HallazgoRepositorio`, `PrestacionPort`, `PacientePort`, `ProfesionalPort`,
  `TurnoPort`, `ConsentimientoPort`, `AuditoriaPort`, `UnidadDeTrabajo` y adaptadores
  en memoria.
- [x] 2.2 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_odontograma.py::test_registrar_hallazgo_valido_fdi` (`pieza_fdi=36`,
  `superficie="O"`, `profesional_id=P1`, `resuelto=false`).
- [x] 2.3 Escribir y hacer pasar
  `tests/test_odontograma.py::test_fdi_grilla_valida_32_posiciones`
  (11–18, 21–28, 31–38, 41–48 ⇒ todas aceptadas) y
  `tests/test_odontograma.py::test_fdi_diente_inexistente_x9_422`
  (`19`, `29`, `39` ⇒ `422` con mensaje de grilla) y
  `tests/test_odontograma.py::test_fdi_fuera_de_grilla_422`
  (`10`, `20`, `30`, `40`, `49`, `00`, `99` ⇒ `422` sin persistir) y
  `tests/test_odontograma.py::test_fdi_no_numerica_422`.
- [x] 2.4 Escribir y hacer pasar
  `tests/test_odontograma.py::test_payload_vacio_o_hallazgo_vacio_422`
  (`hallazgo=""` y cuerpo vacío ⇒ `422`, nunca `500`, nada persistido).
- [x] 2.5 Escribir y hacer pasar
  `tests/test_odontograma.py::test_superficie_vacia_422_y_ausente_null`.
- [x] 2.6 Escribir y hacer pasar
  `tests/test_odontograma.py::test_historial_por_pieza_ordenado`
  (dos hallazgos de la pieza 36 ordenados por `fecha`, sin mezclar la 37) y
  `tests/test_odontograma.py::test_pieza_sin_hallazgos_lista_vacia`.
- [x] 2.7 Escribir y hacer pasar
  `tests/test_odontograma.py::test_contenido_clinico_inmutable_405_y_revoke`
  (`PATCH`/`DELETE` responden `405`, `403` o `404` —nunca `200`— **y** el rol de
  aplicación no puede `UPDATE` de contenido clínico ni `DELETE` en la base; corrección =
  hallazgo nuevo). Afirma status HTTP **y** `REVOKE` en DB (M7).
- [x] 2.8 Escribir y hacer pasar
  `tests/test_odontograma.py::test_resolver_una_sola_vez`
  (`false→true` OK; segundo intento ⇒ `409`; `true→false` ⇒ `405`/`403`/`404`).
- [x] 2.9 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_sin_consentimiento_no_resuelve_hallazgo`
  (`409 CONSENTIMIENTO_REQUERIDO` y `resuelto=false` al llamar
  `POST /api/odontograma/{id}/resolver` con el paciente sin consentimiento).
- [x] 2.10 Escribir y hacer pasar
  `tests/test_odontograma.py::test_hallazgo_paciente_otro_tenant_404`.
- [x] 2.11 Escribir y hacer pasar
  `tests/test_odontograma.py::test_fecha_naive_422`
  (`fecha="2026-11-10T10:00:00"` sin offset ⇒ `422`, hallazgo no persistido).

## 3. Derivación atómica hallazgo → línea

- [x] 3.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_derivacion_presupuesto.py::test_derivar_crea_hallazgo_y_linea_en_un_paso`
  (línea con `pieza_fdi=36`, `hallazgo_id`, `monto=precio_base` de "Conducto Demo").
- [x] 3.2 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_monto_explicito_reemplaza_precio_base`.
- [x] 3.3 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_prestacion_inexistente_aborta_y_no_persiste_hallazgo`
  (`404` ⇒ 0 hallazgos y 0 líneas).
- [x] 3.4 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_monto_negativo_aborta_y_no_persiste_hallazgo`
  (`422` ⇒ 0 hallazgos y 0 líneas).
- [x] 3.5 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_fallo_de_unidad_de_trabajo_hace_rollback`
  (el adaptador en memoria revierte hallazgo y línea ante excepción).
- [x] 3.6 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_primera_derivacion_con_key_201`
  (header `Idempotency-Key` UUID válido ⇒ `201`, un hallazgo y una línea).
- [x] 3.7 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_replay_misma_key_mismo_payload_200_mismos_ids`
  (repetición exacta ⇒ `200`, mismos `hallazgo_id`/`linea_id`, 1 hallazgo y 1 línea; los
  campos que completa el servidor no rompen el replay).
- [x] 3.8 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_misma_key_payload_distinto_409`
  (cambia `pieza_fdi` o `monto` ⇒ `409`, sin mutación).
- [x] 3.9 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_idempotency_key_ausente_o_invalida_422`
  (sin header o con texto no-UUID ⇒ `422`, nada persistido).
- [x] 3.10 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_misma_key_en_otro_tenant_es_independiente`
  (T1 y T2 con la misma key conservan cada uno su derivación).
- [x] 3.11 Escribir y hacer pasar (integración con dos conexiones a PostgreSQL)
  `tests/test_derivacion_concurrente_pg.py::test_dos_derivaciones_misma_key_crean_una_sola`
  (dos derivaciones simultáneas con la misma `Idempotency-Key` ⇒ una `201`, una `200`
  replay con los mismos ids, un solo hallazgo y una sola línea; la violación del UNIQUE
  parcial nunca responde `500`).

## 4. Dominio del presupuesto (líneas, cobertura y estados)

- [x] 4.1 Escribir el test de puertos (rojo) y hacerlo pasar:
  `tests/test_presupuesto_puertos.py::test_repositorios_y_puertos_scoped_por_tenant`;
  implementar `backend/app/presupuesto/puertos.py` (`PresupuestoRepositorio`,
  `LineaRepositorio`, `AceptacionRepositorio`, `CoberturaPort`, `ImputacionPort`,
  `PrestacionPort`, `PacientePort`, adaptadores en memoria y `CoberturaSinDatos`).
- [x] 4.2 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_crear_presupuesto_borrador_sin_lineas`
  (`BORRADOR`, `vence_en=NULL`, sin líneas y 0 llamadas a los puertos de imputación).
- [x] 4.3 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_crear_presupuesto_paciente_otro_tenant_404`.
- [x] 4.4 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_crear_con_vence_en_422`
  (crear con `vence_en` en el payload ⇒ `422`, presupuesto no persistido).
- [x] 4.5 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_cobertura_50_por_ciento`
  (PACI-1 con `obra_social_id=OS-1`, `monto=100000` ⇒ `50000/50000`,
  `origen_cobertura=CONFIGURADA`, `validada_en_vivo=false`).
- [x] 4.6 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_de_otra_obra_social_no_aplica`
  (cobertura configurada para `OS-2`, paciente en `OS-1` ⇒ `0/100000`,
  `origen_cobertura=SIN_COBERTURA`).
- [x] 4.7 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_sin_obra_social_100_por_ciento_particular`
  (`0/100000`, `origen_cobertura=SIN_COBERTURA`, `validada_en_vivo=false`, y el puerto
  de cobertura no recibe consulta) y
  `tests/test_presupuesto.py::test_cobertura_inexistente_cae_a_particular`.
- [x] 4.8 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_por_monto_fijo`
  (`modo=MONTO`, `40000` sobre `100000` ⇒ `40000/60000`).
- [x] 4.9 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_tope_recorta_cobertura`
  (80 % con `tope=50000` sobre `100000` ⇒ `50000/50000`; 40 % con mismo tope ⇒
  `40000/60000`) y `tests/test_presupuesto.py::test_cobertura_mayor_al_monto_se_recorta`
  (`MONTO=200000` sobre `100000` ⇒ `100000/0`, sin saldo negativo).
- [x] 4.10 Escribir y hacer pasar `tests/test_presupuesto.py::test_monto_cero_valido`.
- [x] 4.11 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_monto_negativo_422_sin_persistir` y
  `tests/test_presupuesto.py::test_monto_no_entero_422`
  (`monto=1000.5` y `monto="100000"` ⇒ `422`, línea no persistida).
- [x] 4.12 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_prestacion_de_otro_tenant_404`
  (`prestacion_id` de T2 ⇒ `404`, línea no persistida).
- [x] 4.13 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_pieza_fdi_invalida_422`
  (`pieza_fdi=19`, `29`, `49`, `20`, `30` y `40` ⇒ `422`; línea no persistida).
- [x] 4.14 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_emitir_exige_al_menos_una_linea` (`409` sin líneas;
  con línea ⇒ `VIGENTE`).
- [x] 4.15 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_emitir_fija_el_vence_en`
  (emisión con `vence_en=2026-12-31T23:59:59-03:00` ⇒ `VIGENTE` con ese `vence_en`).
- [x] 4.16 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_emitir_con_vence_en_pasado_422`
  (`ahora=2026-11-10T10:00:00-03:00`, `vence_en=2026-11-01T00:00:00-03:00` ⇒ `422`, sigue
  `BORRADOR`).
- [x] 4.17 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_vence_en_naive_422`
  (`vence_en` sin offset al emitir ⇒ `422`, sigue `BORRADOR`).
- [x] 4.18 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_editar_lineas_solo_en_borrador`
  (`VIGENTE` ⇒ `409` al agregar línea; líneas intactas) y
  `tests/test_presupuesto.py::test_linea_sin_patch_ni_delete`
  (`PATCH`/`DELETE` de línea ⇒ `405` o `404`, nunca `200`; la línea sigue intacta).
- [x] 4.19 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_presupuesto_vencido_no_acepta`
  (`vence_en=2026-11-01T00:00:00-03:00`, `ahora=2026-11-10T10:00:00-03:00` ⇒ `409`,
  `estado=VENCIDO` **persistido**, auditoría escrita y 0 imputaciones).
- [x] 4.20 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_lectura_de_vencido_no_persiste`
  (dos `GET` reportan `VENCIDO`; la fila sigue `VIGENTE` y no hay auditoría nueva).
- [x] 4.21 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_parcial_no_vence_por_reloj`
  (`PARCIAL` con `vence_en` pasado ⇒ se reporta y permanece `PARCIAL`; aceptar una línea
  pendiente funciona).
- [x] 4.22 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_sin_vence_en_no_vence_solo`.
- [x] 4.23 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_no_se_acepta_en_borrador` (`409`).
- [x] 4.24 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_porcentaje_invalido_cae_a_particular`
  (`150 %` y `-10 %` ⇒ `0/100000`, `origen_cobertura=SIN_COBERTURA`,
  `validada_en_vivo=false`).
- [x] 4.25 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_monto_o_tope_negativo_cae_a_particular`
  (`MONTO=-50000` y `tope=-1` ⇒ `0/100000`).
- [x] 4.26 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_totales_inconsistentes_caen_a_fallback`
  (calculadora de cobertura de prueba inyectada —seam de test— que produce `60000/30000`
  sobre `100000` ⇒ se descarta el resultado, la línea persistida queda `0/100000` con
  `origen_cobertura=SIN_COBERTURA` y `validada_en_vivo=false`; nunca se guarda la
  inconsistencia).
- [x] 4.27 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_invalida_auditada_sin_phi`
  (`COBERTURA_INVALIDA_DESCARTADA` con `prestacion_id`, `obra_social_id` y `motivo`,
  sin datos personales).
- [x] 4.28 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_origen_cobertura_no_se_recalcula_al_leer`
  (línea persistida `SIN_COBERTURA`; aparece una cobertura después y el `GET` sigue
  devolviendo `SIN_COBERTURA`/`validada_en_vivo=false` sin consultar el puerto).

## 5. Aceptación parcial e imputación

- [x] 5.1 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptacion_parcial_imputa_solo_la_aceptada`
  (L1 aceptada, L2 pendiente ⇒ `PARCIAL`; agenda/caja reciben exactamente una llamada
  por L1 y ninguna por L2).
- [x] 5.2 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptacion_total_pasa_a_aceptado`
  (L1 ya aceptada + L2 aceptada ⇒ `ACEPTADO`; una imputación por línea).
- [x] 5.3 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_rechazo_no_imputa`
  (`acepta=false` registrado; estado sigue `VIGENTE`; 0 llamadas por esa línea).
- [x] 5.4 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptadas_y_rechazadas_quedan_parcial`
  (L1 aceptada + L2 rechazada ⇒ `PARCIAL`, nunca `ACEPTADO`; L2 no se imputa).
- [x] 5.5 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_todas_rechazadas_conserva_estado_anterior`
  (única línea rechazada ⇒ sigue `VIGENTE`, decisión registrada, 0 imputaciones, nunca
  `ACEPTADO`).
- [x] 5.6 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptar_linea_ya_aceptada_409_sin_duplicar`
  (una sola aceptación y una sola imputación).
- [x] 5.7 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptar_linea_ya_rechazada_409`.
- [x] 5.8 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_rechazar_linea_ya_aceptada_409`
  (la aceptación no cambia y no se revierte la imputación).
- [x] 5.9 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_imputacion_fallida_no_deja_aceptacion`
  (puerto de caja falla ⇒ `503`, sin aceptación, sin cambio de estado, sin imputación
  de agenda).
- [x] 5.10 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_imputacion_caja_recibe_tramos_actor_y_medio`
  (`monto=100000`, `cobertura_os=40000`, `a_cargo_paciente=60000`, recepción U1,
  `medio=EFECTIVO` ⇒ el puerto recibe `monto_paciente_centavos=60000`,
  `monto_os_centavos=40000`, `actor_id=U1`, `turno_id=NULL`, `medio=EFECTIVO`).
- [x] 5.11 Escribir y hacer pasar (integración)
  `tests/test_aceptacion_presupuesto.py::test_imputar_agenda_no_crea_turno`
  (la tabla `turnos` no cambia: misma cantidad de filas y mismos datos antes/después de
  aceptar una línea).
- [x] 5.12 Escribir y hacer pasar (integración con **dos conexiones a PostgreSQL reales**)
  `tests/test_aceptacion_concurrente_pg.py::test_dos_conexiones_independientes_imputan_una_vez`
  (la primera toma `SELECT ... FOR UPDATE` sobre `presupuesto_lineas`, registra e imputa;
  la segunda revalida post-lock ⇒ `409`, sin aceptación y sin llamadas a los puertos;
  resultado: una `200`, una `409`, una sola llamada por línea).
- [x] 5.13 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_lineas_no_aceptadas_consultables_para_recupero`
  (pendiente y rechazada visibles con su decisión; 0 imputaciones por ellas).
- [x] 5.14 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_fecha_aceptacion_la_fija_el_servidor`
  (`ahora` inyectado; el payload no trae fecha y la aceptación queda con el reloj del
  servidor).
- [x] 5.15 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_canal_vacio_o_body_vacio_422`
  (`canal=""` y cuerpo vacío ⇒ `422`, nunca `500`, sin aceptación ni imputación).

- [x] 5.16 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_medio_opcional_en_aceptacion_null_por_defecto`
  (aceptación sin `medio` ⇒ `medio=NULL` en la aceptación y en la llamada a caja; C-10 lo
  completa al cobrar).

## 6. RBAC, gate y aislamiento multi-tenant

- [x] 6.1 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_sin_consentimiento_hallazgo_y_derivacion_409`
  (`409 CONSENTIMIENTO_REQUERIDO`, nada persistido) y
  `tests/test_gate_odontograma.py::test_con_consentimiento_hallazgo_201`.
- [x] 6.2 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_sin_consentimiento_agenda_201`
  (usa `ServicioTurnos.crear` de C-05: la agenda no se bloquea, RN-AU-03).
- [x] 6.3 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_fila_sin_timestamp_valido_no_habilita`
  (consentimiento con `timestamp=NULL` ⇒ `409`, hallazgo no persistido).
- [x] 6.4 Escribir y hacer pasar
  `tests/test_gate_presupuesto.py::test_linea_con_pieza_sin_consentimiento_409`
  (línea con `pieza_fdi=36` ⇒ `409` y no se persiste),
  `tests/test_gate_presupuesto.py::test_linea_con_pieza_con_consentimiento_201` y
  `tests/test_gate_presupuesto.py::test_linea_sin_pieza_no_exige_consentimiento`
  (consulta administrativa ⇒ `201`).
- [x] 6.5 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_odontologo_escribe_paciente_que_atiende_y_ajeno_403`.
- [x] 6.6 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_recepcion_lee_pero_no_escribe_hallazgo`
  (lectura `200`, escritura `403`).
- [x] 6.7 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_recepcion_y_odontologo_leen_historial_de_pieza`
  (ambos `200` con el mismo historial ordenado por `fecha`).
- [x] 6.8 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_odontologo_no_firma_hallazgo_de_otro_profesional`
  (`profesional_id=P2` con actor P1 ⇒ `403`, hallazgo no persistido).
- [x] 6.9 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_recepcion_crea_y_registra_aceptacion_consultorio`
  (creación `201`; aceptación `200` con `canal=CONSULTORIO` y sin sesión de paciente).
- [x] 6.10 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_admin_registra_aceptacion_en_nombre_del_paciente`
  (`200`, `actor_id` = ADMIN, `canal=CONSULTORIO`).
- [x] 6.11 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_odontologo_crea_pero_no_acepta_403`.
- [x] 6.12 Escribir y hacer pasar
  `tests/test_acceso_paciente.py::test_paciente_sin_sesion_401_en_odontograma_y_presupuesto`
  (petición con identidad de paciente ⇒ `401`, sin exponer hallazgos ni presupuesto y sin
  registrar nada; verifican el desvío D13/C09-OQ-10).
- [x] 6.13 Escribir y hacer pasar
  `tests/test_aislamiento_odontograma.py::test_operaciones_de_t1_no_tocan_t2`
  (leer, resolver y derivar desde T2 ⇒ `404`).
- [x] 6.14 Escribir y hacer pasar
  `tests/test_aislamiento_presupuesto.py::test_leer_aceptar_e_imputar_de_otro_tenant_404`
  (sin aceptación ni imputación en T2).

## 7. Borde API (schemas y routers)

- [x] 7.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_api_odontograma.py::test_payload_con_campo_extra_422`; crear
  `backend/app/schemas/odontograma.py` con `extra="forbid"`, `AwareDatetime`,
  `hallazgo` no vacío y allow-list de salida.
- [x] 7.2 Escribir y hacer pasar
  `tests/test_api_odontograma.py::test_crud_http_201_200`
  (`POST/GET /api/odontograma`, `POST /api/odontograma` con bloque `derivar` y header
  `Idempotency-Key` —hallazgo + línea atómicos, `201` la primera vez y `200` el replay—,
  `POST /api/odontograma/{id}/resolver`) y
  `tests/test_api_odontograma.py::test_no_existe_patch_ni_delete`
  (`405`/`403`/`404` según ruta, nunca `200`), con `crear_router(svc)` y
  `actor_desde_headers`.
- [x] 7.3 Escribir y hacer pasar
  `tests/test_api_odontograma.py::test_errores_mapean_404_403_409_422`
  (incluye `409` por misma key + payload distinto, `422` por key ausente/no-UUID y `422`
  por payload vacío).
- [x] 7.4 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_payload_con_campo_extra_422`; crear
  `backend/app/schemas/presupuesto.py` (montos enteros, `canal` no vacío,
  `extra="forbid"`).
- [x] 7.5 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_crud_http_201_200`
  (`POST/GET /api/presupuestos`, `POST /api/presupuestos/{id}/lineas`,
  `POST /api/presupuestos/{id}/emitir` con `vence_en`, `POST /api/presupuestos/{id}/aceptar`)
  y `tests/test_api_presupuesto.py::test_lineas_sin_patch_ni_delete_api`
  (`PATCH`/`DELETE` de línea ⇒ `405`/`404`, nunca `200`).
- [x] 7.6 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_errores_mapean_404_403_409_422`
  (incluye `422` por emitir con `vence_en` pasado o naive, `409` por rechazar una línea
  aceptada y `422` por `canal` vacío).

## 8. Diferido a C-09-UI

> **No ejecutable en C-09.** La UI de odontograma y presupuesto fue diferida por decisión
> del dueño (2026-11-12) al change `C-09-UI`, que todavía no existe. Estas tareas quedan
> registradas como referencia y se planifican/ejecutan allí, contra los contratos de este
> change; C-09 no crea ni modifica archivos de `frontend/`.

- [ ] D.1 `frontend/src/test/odontograma.test.tsx::muestra las 32 piezas de la grilla FDI`
  (11–18, 21–28, 31–38, 41–48; sin 19/29/39/49; sin `any`). → `C-09-UI`
- [ ] D.2 `frontend/src/test/odontograma.test.tsx::registra un hallazgo y lo muestra en el historial`. → `C-09-UI`
- [ ] D.3 `frontend/src/test/odontograma.test.tsx::deriva en un clic y muestra monto, cobertura y a cargo`
  (genera un UUID como `Idempotency-Key` y lo reutiliza en el reintento). → `C-09-UI`
- [ ] D.4 `frontend/src/test/odontograma.test.tsx::FDI inválida muestra error y no crea hallazgo`. → `C-09-UI`
- [ ] D.5 `frontend/src/test/presupuesto.test.tsx::aceptación parcial muestra estado PARCIAL y sólo lo imputado`. → `C-09-UI`
- [ ] D.6 `frontend/src/test/presupuesto.test.tsx::cobertura configurada se muestra como no validada en vivo`
  (la etiqueta no aparece en líneas `SIN_COBERTURA`). → `C-09-UI`
- [ ] D.7 `frontend/src/test/presupuesto.test.tsx::el 409 de una línea ya aceptada no se muestra como éxito`. → `C-09-UI`
- [ ] D.8 `frontend/src/test/presupuesto.test.tsx::cobertura inválida se muestra como particular`
  (`origen_cobertura=SIN_COBERTURA`, `validada_en_vivo=false`, sin recalcular en cliente). → `C-09-UI`
- [ ] D.9 Design system + mockups aprobados, `npm run lint`/`typecheck`/`build` y
  screenshots 375/768/1440 con la skill `visual-turnos`, guardados en
  `openspec/changes/c-09-ui/mockups/previews/`. → `C-09-UI`

## 9. Auditoría y PHI

- [x] 9.1 Escribir y hacer pasar
  `tests/test_auditoria_odontograma.py::test_mutaciones_auditadas_sin_texto_clinico`
  (`HALLAZGO_REGISTRADO`, `HALLAZGO_RESUELTO`, `LINEA_PRESUPUESTADA`; sin texto del
  hallazgo ni nombre/teléfono).
- [x] 9.2 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_aceptacion_e_imputacion_auditadas_sin_phi`.
- [x] 9.3 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_presupuesto_creado_y_emitido_auditados`
  (`PRESUPUESTO_CREADO` y `PRESUPUESTO_EMITIDO` con `tenant_id`, actor, `presupuesto_id`
  y estado, sin PHI).
- [x] 9.4 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_vencido_persistido_auditado`
  (el `POST /aceptar` sobre un vencido deja entrada del cambio a `VENCIDO`).
- [x] 9.5 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_auditoria_sin_update_ni_delete`.
- [x] 9.6 Escribir y hacer pasar
  `tests/test_privacidad_odontograma.py::test_error_no_vuelca_texto_clinico` y
  `tests/test_privacidad_odontograma.py::test_logs_solo_llevan_ids_y_montos`.

## 10. Regresión y verificación del change

- [x] 10.1 Escribir y hacer pasar
  `tests/test_regresion_odontograma_presupuesto.py::test_c04_c05_c06_c07_c08_siguen_en_verde`
  (la 007 no toca sus tablas; gate de C-08 intacto; anti-solape de C-05 intacto).
- [x] 10.2 Correr `py -m pytest tests/ -q` (suite previa + nuevos, 0 fallos; incluye los
  tests con dos conexiones a PostgreSQL de test).
- [x] 10.3 Correr `openspec validate c-09-odontograma-presupuesto --strict` (exit 0, sin
  warnings).
- [x] 10.4 Verificar que no hay env var nueva, secretos, ni tablas de C-10/C-12 en la
  007; `.env.example` intacto.
- [x] 10.5 Verificar que C-09 **no** toca `frontend/`: el diff del change no contiene
  archivos de frontend ni tareas de UI ejecutables (UI diferida a `C-09-UI`).

## Workflow follow-up

- Correr `revisor-escenarios-turnos` sobre `specs/odontograma/spec.md` y
  `specs/presupuesto/spec.md` antes de cualquier `/opsx:apply` (`AGENTS.md` §Skill
  propia), y corregir los `BLOQUEANTE`/`MAYOR` que reporte.
- Decisiones del dueño ya aplicadas (2026-11-12): paciente sin acceso en v1 (D13,
  C09-OQ-10, **PO-06 sigue abierta**); UI diferida a `C-09-UI`; vencimiento al emitir,
  `GET` que reporta sin persistir, `POST /aceptar` que persiste `VENCIDO` con `409`,
  `PARCIAL` sin vencimiento por reloj, mixto ⇒ `PARCIAL`, rechazar una aceptada ⇒ `409`.
- Cerrar con el dueño/asesor clínico C09-OQ-1..C09-OQ-12 restantes (dentición decidua,
  superficies, canales, redondeo, estado con todas rechazadas, anulación, reverso de
  imputación y frontera comercial/clínica). La idempotencia de derivación y el
  saneamiento de cobertura ya se cerraron en D3.1/D6.1/D6.2 (2026-11-06).
- Cuando C-12 exista, implementar el adaptador real de `CoberturaPort` y un test de
  contrato; **hasta entonces no se crea la tabla de coberturas ni una equivalente** (la
  migración 010 de C-12 es la dueña) y todo es 100 % particular visible. Cuando C-10
  exista, el adaptador de `ImputacionPort` debe respetar el contrato de caja de D6
  (`monto_paciente_centavos`, `monto_os_centavos`, `actor_id`, `turno_id`, `medio`) y la
  idempotencia por `linea_id`.
- Wiring SQLAlchemy real de los repositorios de odontograma y presupuesto (follow-up
  declarado, igual que C-06/C-07/C-08).
- Crear el change `C-09-UI` con su design system, mockups aprobados y las tareas de §8.
- Reconciliar con Martin las columnas `presupuesto_lineas.hallazgo_id`,
  `idempotency_key`, `origen_cobertura` y `validada_en_vivo` (design D3/D8): no figuran
  en el ERD de `04_modelo_de_datos.md:66`.
- Archivar el change recién después de implementarlo, verificarlo y con el `[x]` de
  `CHANGES.md` pedido por el dueño.
