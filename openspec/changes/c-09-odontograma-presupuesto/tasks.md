# Tasks — C-09 `odontograma-presupuesto`

> Estado: **preparado, no implementado**. TDD rojo-primero: cada tarea nombra el test
> exacto que la verifica y el archivo destino. Corrida backend: `py -m pytest tests/ -q`
> (launcher `py`, nunca `python`); frontend: `npm test`, `npm run lint`,
> `npm run typecheck`. Los tests nuevos se suman a la suite existente (C-04…C-08) sin
> tocarla.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", P1/P2, prestación "Conducto
> Demo"; nunca datos reales ni aranceles reales (RN-GL-03). Reloj siempre inyectado y
> escenarios redactados en `-03:00`.

## 1. Migración 007 y modelos SQLAlchemy

- [ ] 1.1 Escribir el test de migración (rojo):
  `tests/test_migracion_007.py::test_upgrade_head_crea_tablas_odontograma_y_presupuesto`
  (`alembic upgrade head` ⇒ existen `odontograma_hallazgos`, `presupuestos`,
  `presupuesto_lineas`, `aceptaciones`, `down_revision="006_ficha_clinica"`).
- [ ] 1.2 Implementar `backend/alembic/versions/007_odontograma_presupuesto.py` con las
  4 tablas, `tenant_id NOT NULL`, FKs, índices y RLS forzada (D7/D8) hasta que 1.1 pase.
- [ ] 1.3 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_downgrade_elimina_solo_007`
  (`alembic downgrade 006_ficha_clinica` ⇒ 007 fuera, 001–006 intactas; re-upgrade
  limpio).
- [ ] 1.4 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_check_fdi_y_suma_de_linea_en_db`
  (`pieza_fdi=19`, `29`, `39` y `49` rechazados por el CHECK de grilla FDI (cuadrante
  1–4 × diente 1–8); `pieza_fdi=11` y `48` aceptados; `cobertura_os +
  a_cargo_paciente <> monto` rechazado por CHECK).
- [ ] 1.5 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_unique_parcial_idempotency_key`
  (dos líneas de T1 con la misma key ⇒ la segunda rechazada; la misma key en T2 se
  acepta).
- [ ] 1.6 Escribir y hacer pasar
  `tests/test_migracion_007.py::test_rls_fail_closed_y_grants` (como `turnos_app` sin
  `app.tenant_id` ⇒ 0 filas; `UPDATE hallazgo`/`DELETE hallazgo` rechazados;
  `UPDATE aceptaciones`/`DELETE aceptaciones` rechazados; `UPDATE resuelto` permitido).
- [ ] 1.7 Escribir el test de modelos (rojo):
  `tests/test_migracion_007.py::test_modelos_sqlalchemy_cargan_sin_errores`; implementar
  `backend/app/models/odontograma.py` (`OdontogramaHallazgo`) y
  `backend/app/models/presupuesto.py` (`Presupuesto`, `PresupuestoLinea` con
  `idempotency_key`, `Aceptacion`) con `Mapped[...]`, `timestamptz`, PK uuid y CHECKs
  espejo de la migración.

## 2. Dominio del odontograma (hallazgos e historial)

- [ ] 2.1 Escribir el test de puertos en memoria (rojo):
  `tests/test_odontograma_puertos.py::test_repositorio_scoped_por_tenant`; implementar
  `backend/app/odontograma/puertos.py` con entidades `Hallazgo`, protocolos
  `HallazgoRepositorio`, `PrestacionPort`, `PacientePort`, `ProfesionalPort`,
  `TurnoPort`, `ConsentimientoPort`, `AuditoriaPort`, `UnidadDeTrabajo` y adaptadores
  en memoria.
- [ ] 2.2 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_odontograma.py::test_registrar_hallazgo_valido_fdi` (`pieza_fdi=36`,
  `superficie="O"`, `profesional_id=P1`, `resuelto=false`).
- [ ] 2.3 Escribir y hacer pasar
  `tests/test_odontograma.py::test_fdi_grilla_valida_32_posiciones`
  (11–18, 21–28, 31–38, 41–48 ⇒ todas aceptadas) y
  `tests/test_odontograma.py::test_fdi_diente_inexistente_x9_422`
  (`19`, `29`, `39` ⇒ `422` con mensaje de grilla) y
  `tests/test_odontograma.py::test_fdi_fuera_de_grilla_422`
  (`10`, `49`, `00`, `99` ⇒ `422` sin persistir) y
  `tests/test_odontograma.py::test_fdi_no_numerica_422`.
- [ ] 2.4 Escribir y hacer pasar
  `tests/test_odontograma.py::test_superficie_vacia_422_y_ausente_null`.
- [ ] 2.5 Escribir y hacer pasar
  `tests/test_odontograma.py::test_historial_por_pieza_ordenado`
  (dos hallazgos de la pieza 36 ordenados por `fecha`, sin mezclar la 37) y
  `tests/test_odontograma.py::test_pieza_sin_hallazgos_lista_vacia`.
- [ ] 2.6 Escribir y hacer pasar
  `tests/test_odontograma.py::test_contenido_clinico_inmutable`
  (no hay update/delete de `hallazgo`/`pieza_fdi`; corrección = hallazgo nuevo) y
  `tests/test_odontograma.py::test_resolver_una_sola_vez`
  (`false→true` OK; segundo intento ⇒ `409`; `true→false` ⇒ rechazado).
- [ ] 2.7 Escribir y hacer pasar
  `tests/test_odontograma.py::test_hallazgo_paciente_otro_tenant_404`.
- [ ] 2.8 Escribir y hacer pasar
  `tests/test_odontograma.py::test_fecha_naive_422`
  (`fecha="2026-11-10T10:00:00"` sin offset ⇒ `422`, hallazgo no persistido).

## 3. Derivación atómica hallazgo → línea

- [ ] 3.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_derivacion_presupuesto.py::test_derivar_crea_hallazgo_y_linea_en_un_paso`
  (línea con `pieza_fdi=36`, `hallazgo_id`, `monto=precio_base` de "Conducto Demo").
- [ ] 3.2 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_monto_explicito_reemplaza_precio_base`.
- [ ] 3.3 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_prestacion_inexistente_aborta_y_no_persiste_hallazgo`
  (`404` ⇒ 0 hallazgos y 0 líneas).
- [ ] 3.4 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_monto_negativo_aborta_y_no_persiste_hallazgo`
  (`422` ⇒ 0 hallazgos y 0 líneas).
- [ ] 3.5 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_fallo_de_unidad_de_trabajo_hace_rollback`
  (el adaptador en memoria revierte hallazgo y línea ante excepción).
- [ ] 3.6 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_primera_derivacion_con_key_201`
  (header `Idempotency-Key` UUID válido ⇒ `201`, un hallazgo y una línea).
- [ ] 3.7 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_replay_misma_key_mismo_payload_200_mismos_ids`
  (repetición exacta ⇒ `200`, mismos `hallazgo_id`/`linea_id`, 1 hallazgo y 1 línea).
- [ ] 3.8 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_misma_key_payload_distinto_409`
  (cambia `pieza_fdi` o `monto` ⇒ `409`, sin mutación).
- [ ] 3.9 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_idempotency_key_ausente_o_invalida_422`
  (sin header o con texto no-UUID ⇒ `422`, nada persistido).
- [ ] 3.10 Escribir y hacer pasar
  `tests/test_derivacion_presupuesto.py::test_misma_key_en_otro_tenant_es_independiente`
  (T1 y T2 con la misma key conservan cada uno su derivación).

## 4. Dominio del presupuesto (líneas, cobertura y estados)

- [ ] 4.1 Escribir el test de puertos (rojo) y hacerlo pasar:
  `tests/test_presupuesto_puertos.py::test_repositorios_y_puertos_scoped_por_tenant`;
  implementar `backend/app/presupuesto/puertos.py` (`PresupuestoRepositorio`,
  `LineaRepositorio`, `AceptacionRepositorio`, `CoberturaPort`, `ImputacionPort`,
  `PrestacionPort`, `PacientePort`, adaptadores en memoria y `CoberturaSinDatos`).
- [ ] 4.2 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_crear_presupuesto_borrador_sin_lineas`
  (`BORRADOR`, sin líneas y 0 llamadas a los puertos de imputación).
- [ ] 4.3 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_crear_presupuesto_paciente_otro_tenant_404`.
- [ ] 4.4 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_cobertura_50_por_ciento`
  (`monto=100000` ⇒ `50000/50000`, `origen_cobertura=CONFIGURADA`,
  `validada_en_vivo=false`) y
  `tests/test_presupuesto.py::test_monto_negativo_422_sin_persistir`.
- [ ] 4.5 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_prestacion_de_otro_tenant_404`
  (`prestacion_id` de T2 ⇒ `404`, línea no persistida).
- [ ] 4.6 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_sin_obra_social_100_por_ciento_particular`
  (`0/100000`, `origen_cobertura=SIN_COBERTURA`, `validada_en_vivo=false`) y
  `tests/test_presupuesto.py::test_cobertura_inexistente_cae_a_particular`.
- [ ] 4.7 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_por_monto_fijo`
  (`modo=MONTO`, `40000` sobre `100000` ⇒ `40000/60000`).
- [ ] 4.8 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_tope_recorta_cobertura`
  (80 % con `tope=50000` sobre `100000` ⇒ `50000/50000`; 40 % con mismo tope ⇒
  `40000/60000`) y `tests/test_presupuesto.py::test_cobertura_mayor_al_monto_se_recorta`
  (`MONTO=200000` sobre `100000` ⇒ `100000/0`, sin saldo negativo).
- [ ] 4.9 Escribir y hacer pasar `tests/test_presupuesto.py::test_monto_cero_valido`.
- [ ] 4.10 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_emitir_exige_al_menos_una_linea` (`409` sin líneas;
  con línea ⇒ `VIGENTE`).
- [ ] 4.11 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_editar_lineas_solo_en_borrador` (`VIGENTE` ⇒ `409`,
  líneas intactas).
- [ ] 4.12 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_presupuesto_vencido_no_acepta`
  (`vence_en=2026-11-01T00:00:00-03:00`, `ahora=2026-11-10T10:00:00-03:00` ⇒ `VENCIDO`
  y `409`) y `tests/test_presupuesto.py::test_sin_vence_en_no_vence_solo`.
- [ ] 4.13 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_no_se_acepta_en_borrador` (`409`).
- [ ] 4.14 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_vence_en_naive_422`
  (`vence_en` sin offset ⇒ `422`, presupuesto no persistido).
- [ ] 4.15 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_linea_con_pieza_fdi_invalida_422`
  (`pieza_fdi=19`, `29` y `49` ⇒ `422`; línea no persistida).
- [ ] 4.16 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_porcentaje_invalido_cae_a_particular`
  (`150 %` y `-10 %` ⇒ `0/100000`, `origen_cobertura=SIN_COBERTURA`,
  `validada_en_vivo=false`).
- [ ] 4.17 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_monto_o_tope_negativo_cae_a_particular`
  (`MONTO=-50000` y `tope=-1` ⇒ `0/100000`).
- [ ] 4.18 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_totales_inconsistentes_caen_a_fallback`
  (calculadora de prueba que produce `60000/30000` sobre `100000` ⇒ se descarta la
  cobertura y la línea persistida queda `0/100000`; nunca se guarda la inconsistencia).
- [ ] 4.19 Escribir y hacer pasar
  `tests/test_presupuesto.py::test_cobertura_invalida_auditada_sin_phi`
  (`COBERTURA_INVALIDA_DESCARTADA` con `prestacion_id`, `obra_social_id` y `motivo`,
  sin datos personales).

## 5. Aceptación parcial e imputación

- [ ] 5.1 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptacion_parcial_imputa_solo_la_aceptada`
  (L1 aceptada, L2 pendiente ⇒ `PARCIAL`; agenda/caja reciben exactamente una llamada
  por L1 y ninguna por L2).
- [ ] 5.2 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptacion_total_pasa_a_aceptado`
  (L1 ya aceptada + L2 aceptada ⇒ `ACEPTADO`; una imputación por línea).
- [ ] 5.3 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_rechazo_no_imputa`
  (`acepta=false` registrado; 0 llamadas por esa línea).
- [ ] 5.4 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptar_linea_ya_aceptada_409_sin_duplicar`
  (una sola aceptación y una sola imputación).
- [ ] 5.5 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptar_linea_ya_rechazada_409`.
- [ ] 5.6 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_imputacion_fallida_no_deja_aceptacion`
  (puerto de caja falla ⇒ `503`, sin aceptación, sin cambio de estado, sin imputación
  de agenda).
- [ ] 5.7 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_monto_a_cargo_se_imputa_a_caja`
  (`a_cargo_paciente=60000` ⇒ `monto_centavos=60000`).
- [ ] 5.8 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_aceptaciones_concurrentes_imputan_una_vez`
  (dos aceptaciones simultáneas de L1 ⇒ una `200`, una `409`, una sola imputación).
- [ ] 5.9 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_lineas_no_aceptadas_consultables_para_recupero`
  (pendiente y rechazada visibles con su decisión; 0 imputaciones por ellas).
- [ ] 5.10 Escribir y hacer pasar
  `tests/test_aceptacion_presupuesto.py::test_fecha_aceptacion_la_fija_el_servidor`
  (`ahora` inyectado; el payload no trae fecha y la aceptación queda con el reloj del
  servidor).

## 6. RBAC, gate y aislamiento multi-tenant

- [ ] 6.1 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_sin_consentimiento_hallazgo_y_derivacion_409`
  (`409 CONSENTIMIENTO_REQUERIDO`, nada persistido) y
  `tests/test_gate_odontograma.py::test_con_consentimiento_hallazgo_201`.
- [ ] 6.2 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_sin_consentimiento_agenda_201`
  (usa `ServicioTurnos.crear` de C-05: la agenda no se bloquea, RN-AU-03).
- [ ] 6.3 Escribir y hacer pasar
  `tests/test_gate_odontograma.py::test_fila_sin_timestamp_valido_no_habilita`
  (consentimiento con `timestamp=NULL` ⇒ `409`, hallazgo no persistido).
- [ ] 6.4 Escribir y hacer pasar
  `tests/test_gate_presupuesto.py::test_linea_con_pieza_sin_consentimiento_409`
  (línea con `pieza_fdi=36` ⇒ `409` y no se persiste),
  `tests/test_gate_presupuesto.py::test_linea_con_pieza_con_consentimiento_201` y
  `tests/test_gate_presupuesto.py::test_linea_sin_pieza_no_exige_consentimiento`
  (consulta administrativa ⇒ `201`).
- [ ] 6.5 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_odontologo_escribe_paciente_que_atiende_y_ajeno_403`.
- [ ] 6.6 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_recepcion_lee_pero_no_escribe_hallazgo`
  (lectura `200`, escritura `403`).
- [ ] 6.7 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_paciente_lee_su_odontograma_no_el_ajeno` y
  `tests/test_odontograma_rbac.py::test_paciente_no_escribe_hallazgo` (`403`).
- [ ] 6.8 Escribir y hacer pasar
  `tests/test_odontograma_rbac.py::test_odontologo_no_firma_hallazgo_de_otro_profesional`
  (`profesional_id=P2` con actor P1 ⇒ `403`, hallazgo no persistido).
- [ ] 6.9 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_recepcion_crea_y_acepta`.
- [ ] 6.10 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_odontologo_crea_pero_no_acepta_403`.
- [ ] 6.11 Escribir y hacer pasar
  `tests/test_presupuesto_rbac.py::test_paciente_acepta_el_suyo_no_el_ajeno` y
  `tests/test_presupuesto_rbac.py::test_paciente_no_crea_presupuestos` (`403`).
- [ ] 6.12 Escribir y hacer pasar
  `tests/test_aislamiento_odontograma.py::test_operaciones_de_t1_no_tocan_t2`
  (leer, resolver y derivar desde T2 ⇒ `404`).
- [ ] 6.13 Escribir y hacer pasar
  `tests/test_aislamiento_presupuesto.py::test_leer_aceptar_e_imputar_de_otro_tenant_404`
  (sin aceptación ni imputación en T2).

## 7. Borde API (schemas y routers)

- [ ] 7.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_api_odontograma.py::test_payload_con_campo_extra_422`; crear
  `backend/app/schemas/odontograma.py` con `extra="forbid"`, `AwareDatetime` y
  allow-list de salida.
- [ ] 7.2 Escribir y hacer pasar
  `tests/test_api_odontograma.py::test_crud_http_201_200`
  (`POST/GET /api/odontograma`, `POST /api/odontograma` con bloque `derivar` y header
  `Idempotency-Key` —hallazgo + línea atómicos, `201` la primera vez y `200` el replay—
  y `POST /api/odontograma/{id}/resolver`) con `crear_router(svc)` y
  `actor_desde_headers`.
- [ ] 7.3 Escribir y hacer pasar
  `tests/test_api_odontograma.py::test_errores_mapean_404_403_409_422`
  (incluye `409` por misma key + payload distinto y `422` por key ausente/no-UUID).
- [ ] 7.4 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_payload_con_campo_extra_422`; crear
  `backend/app/schemas/presupuesto.py` (montos enteros, `extra="forbid"`).
- [ ] 7.5 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_crud_http_201_200`
  (`POST/GET /api/presupuestos`, `POST /api/presupuestos/{id}/lineas`,
  `POST /api/presupuestos/{id}/emitir`, `POST /api/presupuestos/{id}/aceptar`).
- [ ] 7.6 Escribir y hacer pasar
  `tests/test_api_presupuesto.py::test_errores_mapean_404_403_409_422`.

## 8. UI del odontograma y del presupuesto

- [ ] 8.1 Escribir el test (rojo) y hacerlo pasar:
  `frontend/src/test/odontograma.test.tsx::muestra las 32 piezas de la grilla FDI`
  (11–18, 21–28, 31–38, 41–48; sin 19/29/39/49; render de `/odontograma` con datos
  mockeados y sin `any`).
- [ ] 8.2 Escribir y hacer pasar
  `frontend/src/test/odontograma.test.tsx::registra un hallazgo y lo muestra en el historial`.
- [ ] 8.3 Escribir y hacer pasar
  `frontend/src/test/odontograma.test.tsx::deriva en un clic y muestra monto, cobertura y a cargo`
  (genera un UUID como `Idempotency-Key` y lo reutiliza en el reintento; el doble clic
  no crea una segunda línea).
- [ ] 8.4 Escribir y hacer pasar
  `frontend/src/test/odontograma.test.tsx::FDI inválida muestra error y no crea hallazgo`
  (probado con 19, 29 y 49).
- [ ] 8.5 Escribir y hacer pasar
  `frontend/src/test/presupuesto.test.tsx::aceptación parcial muestra estado PARCIAL y sólo lo imputado`.
- [ ] 8.6 Escribir y hacer pasar
  `frontend/src/test/presupuesto.test.tsx::cobertura configurada se muestra como no validada en vivo`.
- [ ] 8.7 Escribir y hacer pasar
  `frontend/src/test/presupuesto.test.tsx::el 409 de una línea ya aceptada no se muestra como éxito`.
- [ ] 8.8 Escribir y hacer pasar
  `frontend/src/test/presupuesto.test.tsx::cobertura inválida se muestra como particular`
  (`origen_cobertura=SIN_COBERTURA`, `validada_en_vivo=false`, sin recalcular en cliente).
- [ ] 8.9 Pasar `npm run lint`, `npm run typecheck` y `npm run build` sin `any` ni
  warnings; capturar screenshots 375/768/1440 con la skill `visual-turnos` y dejarlos
  en `openspec/changes/c-09-odontograma-presupuesto/mockups/previews/`.

## 9. Auditoría y PHI

- [ ] 9.1 Escribir y hacer pasar
  `tests/test_auditoria_odontograma.py::test_mutaciones_auditadas_sin_texto_clinico`
  (`HALLAZGO_REGISTRADO`, `HALLAZGO_RESUELTO`, `LINEA_PRESUPUESTADA`; sin texto del
  hallazgo ni nombre/teléfono).
- [ ] 9.2 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_aceptacion_e_imputacion_auditadas_sin_phi`.
- [ ] 9.3 Escribir y hacer pasar
  `tests/test_auditoria_presupuesto.py::test_auditoria_sin_update_ni_delete`.
- [ ] 9.4 Escribir y hacer pasar
  `tests/test_privacidad_odontograma.py::test_error_no_vuelca_texto_clinico` y
  `tests/test_privacidad_odontograma.py::test_logs_solo_llevan_ids_y_montos`.

## 10. Regresión y verificación del change

- [ ] 10.1 Escribir y hacer pasar
  `tests/test_regresion_odontograma_presupuesto.py::test_c04_c05_c06_c07_c08_siguen_en_verde`
  (la 007 no toca sus tablas; gate de C-08 intacto; anti-solape de C-05 intacto).
- [ ] 10.2 Correr `py -m pytest tests/ -q` (suite previa + nuevos, 0 fallos).
- [ ] 10.3 Correr `npm test`, `npm run lint`, `npm run typecheck` y `npm run build`
  (0 fallos, sin `any`).
- [ ] 10.4 Correr `openspec validate c-09-odontograma-presupuesto --strict` (exit 0, sin
  warnings).
- [ ] 10.5 Verificar que no hay env var nueva, secretos, ni tablas de C-10/C-12 en la
  007; `.env.example` intacto.

## Workflow follow-up

- Correr `revisor-escenarios-turnos` sobre `specs/odontograma/spec.md` y
  `specs/presupuesto/spec.md` antes de cualquier `/opsx:apply` (`AGENTS.md` §Skill
  propia), y corregir los `BLOQUEANTE`/`MAYOR` que reporte.
- Cerrar C09-OQ-1..C09-OQ-12 con el dueño/asesor clínico antes de fijar dentición
  decidua, superficies, canales de aceptación, redondeo, política de vencimiento y
  frontera comercial/clínica. Las OQ de idempotencia de derivación y saneamiento de
  cobertura ya se cerraron en D3.1 y D6.1/D6.2 (2026-11-06).
- Cuando C-12 exista, implementar el adaptador real de `CoberturaPort` y un test de
  contrato; **hasta entonces no se crea la tabla de coberturas ni una equivalente** (la
  migración 010 de C-12 es la dueña) y todo es 100 % particular visible. Cuando C-10
  exista, el adaptador de `ImputacionPort` (la idempotencia por `linea_id` es parte del
  contrato).
- Wiring SQLAlchemy real de los repositorios de odontograma y presupuesto (follow-up
  declarado, igual que C-06/C-07/C-08).
- Reconciliar con Martin las columnas `presupuesto_lineas.hallazgo_id` y
  `idempotency_key` (design D3): no figuran en el ERD de `04_modelo_de_datos.md:66`.
- Archivar el change recién después de implementarlo, verificarlo y con el `[x]` de
  `CHANGES.md` pedido por el dueño.
