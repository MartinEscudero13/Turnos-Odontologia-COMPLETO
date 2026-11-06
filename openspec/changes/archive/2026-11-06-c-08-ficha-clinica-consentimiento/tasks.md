# Tasks — C-08 `ficha-clinica-consentimiento`

> Estado: **preparado, no implementado**. TDD rojo-primero: cada tarea nombra el
> test exacto que la verifica y el archivo destino. Corrida: `py -m pytest tests/ -q`
> (launcher `py`, nunca `python`). Los tests nuevos se suman a la suite existente
> (C-05 + C-06 + C-07) sin tocarla.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", profesional P1/P2; nunca
> datos reales (RN-GL-03). Ningún test usa el reloj real: todo test temporal inyecta
> `ahora=` fijo y los escenarios están redactados en `-03:00`.

## 1. Migración 006 (`fichas` + `evoluciones` + `adjuntos` + `consentimientos` + RLS)

- [x] 1.1 Crear `backend/alembic/versions/006_ficha_clinica.py` con `fichas`
  (`tenant_id NOT NULL` FK, `paciente_id`, `UNIQUE(tenant_id, paciente_id)`,
  `creado_en`), `evoluciones` (`paciente_id`, `profesional_id`, `fecha`, `texto`,
  `firma_hash?`, `creado_en`), `adjuntos` (`ficha_id`, `tipo` CHECK `('RX','FOTO')`,
  `storage_ref`, `creado_en`) y `consentimientos` (`paciente_id`, `timestamp NOT NULL`,
  `canal`, `creado_en`), índices `(tenant_id, paciente_id)` y `(tenant_id, ficha_id)`,
  RLS forzada en las 4 tablas y `GRANT SELECT, INSERT` + `REVOKE UPDATE, DELETE`
  sobre `evoluciones` y `consentimientos`. Verifica
  `tests/test_migracion_006.py::test_upgrade_head_crea_tablas_clinicas_con_rls`
  (`alembic upgrade head` ⇒ tablas existen, `down_revision="005_lista_espera"`).
- [x] 1.2 Downgrade reversible. Verifica
  `tests/test_migracion_006.py::test_downgrade_elimina_solo_006`
  (`alembic downgrade 005_lista_espera` ⇒ 006 fuera, turnos/catálogos/lista_espera intactos).
- [x] 1.3 Modelos SQLAlchemy `Ficha`, `Evolucion`, `Adjunto`, `Consentimiento` en
  `backend/app/models/ficha_clinica.py` con type hints y FKs. Verifica
  `tests/test_migracion_006.py::test_modelos_sqlalchemy_cargan_sin_errores`.
- [x] 1.4 Inmutabilidad a nivel DB: UPDATE/DELETE sobre `evoluciones` y `consentimientos`
  fallan por revoke. Verifica
  `tests/test_migracion_006.py::test_update_delete_evolucion_rechazados_por_db` y
  `tests/test_migracion_006.py::test_update_delete_consentimiento_rechazados_por_db`
  (como `turnos_app`: UPDATE y DELETE ⇒ error de permisos).

## 2. Dominio ficha clínica (ficha 1—1 + consentimiento)

- [x] 2.1 Puertos `FichaRepositorio`, `EvolucionRepositorio`, `AdjuntoRepositorio`,
  `ConsentimientoRepositorio`, `AuditoriaPort` (+ adaptadores en memoria) en
  `backend/app/ficha_clinica/puertos.py`. Verifica
  `tests/test_ficha_clinica_puertos.py::test_repositorio_memoria_scoped_por_tenant`
  (ficha/consentimiento de T1 no visible en T2).
- [x] 2.2 `ServicioFichaClinica.crear_ficha` crea la ficha 1—1. Verifica
  `tests/test_ficha_clinica.py::test_crear_ficha_ligada_1_a_1`.
- [x] 2.3 Segunda ficha para el mismo paciente → `409` (sin duplicar). Verifica
  `tests/test_ficha_clinica.py::test_segunda_ficha_responde_409`.
- [x] 2.4 Paciente de otro tenant → `404`. Verifica
  `tests/test_ficha_clinica.py::test_ficha_paciente_otro_tenant_responde_404`.
- [x] 2.5 `registrar_consentimiento` persiste timestamp + canal. Verifica
  `tests/test_consentimiento.py::test_registrar_consentimiento_timestamp_canal`.
- [x] 2.6 Re-firma crea nuevo registro sin editar el anterior. Verifica
  `tests/test_consentimiento.py::test_refirma_crea_nuevo_registro`.
- [x] 2.7 Consentimientos append-only: el servicio no expone update/delete; UPDATE/DELETE
  ⇒ `403`/`405` y el consentimiento no cambia. Verifica
  `tests/test_consentimiento.py::test_consentimiento_append_only`.

## 3. Evoluciones append-only

- [x] 3.1 `registrar_evolucion` con consentimiento previo. Verifica
  `tests/test_evoluciones.py::test_evolucion_valida_con_consentimiento`
  (`profesional_id`, `fecha`, `texto`, `firma_hash?` correctos).
- [x] 3.2 Corrección = nueva evolución; la original permanece intacta. Verifica
  `tests/test_evoluciones.py::test_corregir_agrega_nueva_evolucion_no_edita_original`.
- [x] 3.3 No hay endpoints de update/delete (el servicio no expone mutación). Verifica
  `tests/test_evoluciones.py::test_servicio_sin_update_delete` (intento de UPDATE/DELETE
  ⇒ `Prohibido`/`405` y la lista de evoluciones no cambia).
- [x] 3.4 Paciente o profesional de otro tenant → `404`. Verifica
  `tests/test_evoluciones.py::test_evolucion_paciente_o_profesional_otro_tenant_404`.

## 4. Adjuntos scoped por tenant

- [x] 4.1 `registrar_adjunto` tipo `RX`/`FOTO` con referencia opaca. Verifica
  `tests/test_adjuntos.py::test_adjunto_valido_tipo_rx`.
- [x] 4.2 Tipo inválido → `422`. Verifica
  `tests/test_adjuntos.py::test_adjunto_tipo_invalido_422`.
- [x] 4.3 Ficha de otro tenant → `404`. Verifica
  `tests/test_adjuntos.py::test_adjunto_ficha_otro_tenant_404`.
- [x] 4.4 `storage_ref` no porta PHI (sólo referencia opaca). Verifica
  `tests/test_adjuntos.py::test_storage_ref_sin_phi`.

## 5. Gate de consentimiento (bloquea clínica, no agenda)

- [x] 5.1 `_exigir_consentimiento` usa `consentimientos`, no `consentimiento_ok`, y exige
  `timestamp` válido (NOT NULL). Verifica
  `tests/test_gate_consentimiento.py::test_gate_consulta_consentimientos`
  (boolean `true` sin fila ⇒ clínica bloqueada; fila con `timestamp` válido ⇒ habilitada)
  y `tests/test_gate_consentimiento.py::test_fila_sin_timestamp_valido_no_desbloquea`
  (fila sin `timestamp` válido ⇒ clínica bloqueada).
- [x] 5.2 Sin consentimiento → `409 CONSENTIMIENTO_REQUERIDO` en ficha/evolución/adjunto.
  Verifica `tests/test_gate_consentimiento.py::test_sin_consentimiento_clinica_bloqueada_409`.
- [x] 5.3 La agenda no se bloquea: turno para el mismo paciente sin consentimiento → `201`.
  Verifica `tests/test_gate_consentimiento.py::test_sin_consentimiento_turno_agenda_201`
  (usa `ServicioTurnos.crear` de C-05).

## 6. RBAC clínico

- [x] 6.1 Odontólogo escribe evolución de un paciente que atiende (turno con su
  `profesional_id`) → `201`. Verifica
  `tests/test_ficha_clinica.py::test_odontologo_escribe_paciente_que_atiende`.
- [x] 6.2 Odontólogo no escribe sobre paciente ajeno → `403`. Verifica
  `tests/test_ficha_clinica.py::test_odontologo_paciente_ajeno_403`.
- [x] 6.3 Recepción no registra evoluciones (sólo ficha base + consentimiento) → `403`.
  Verifica `tests/test_ficha_clinica.py::test_recepcion_no_registra_evolucion`.
- [x] 6.4 Paciente lee su propia ficha/evolución/adjunto (`200`) y no los ajenos
  (`403`/`404`). Verifica `tests/test_ficha_clinica.py::test_paciente_lee_su_ficha_no_la_ajena`
  y `tests/test_ficha_clinica.py::test_paciente_lee_su_evolucion_adjunto_no_los_ajenos`.
- [x] 6.5 Recepción crea la ficha base y registra el consentimiento → `201`. Verifica
  `tests/test_ficha_clinica.py::test_recepcion_crea_ficha_y_consentimiento`.

## 7. Borde API (`/api/pacientes/{id}/ficha` + `/api/evoluciones` + `/api/adjuntos` + `/api/consentimientos`)

- [x] 7.1 Schemas allow-list en `backend/app/schemas/ficha_clinica.py` (sin PHI, sin
  `tenant_id` en payload). Verifica
  `tests/test_api_ficha_clinica.py::test_payload_con_campo_extra_responde_422`.
- [x] 7.2 Router `backend/app/routers/ficha_clinica.py` con `POST/GET
  /api/pacientes/{id}/ficha`, `POST/GET /api/evoluciones`, `POST/GET /api/adjuntos`,
  `POST/GET /api/consentimientos` inyectables (`crear_router(svc)`) y actor por headers.
  Verifica `tests/test_api_ficha_clinica.py::test_crud_por_http_201_200`.
- [x] 7.3 Mapeo de errores de dominio a HTTP (404/403/409/422). Verifica
  `tests/test_api_ficha_clinica.py::test_errores_mapean_404_403_409_422`
  (un test por código, sin exponer trazas).

## 8. Aislamiento multi-tenant

- [x] 8.1 Ficha/evoluciones de T1 no visibles ni mutables desde T2. Verifica
  `tests/test_aislamiento_ficha_clinica.py::test_operaciones_de_a_no_tocan_b`.
- [x] 8.2 El consentimiento de T1 no aplica en T2. Verifica
  `tests/test_aislamiento_ficha_clinica.py::test_consentimiento_de_a_no_aplica_en_b`.
- [x] 8.3 Adjunto de T1 no listable desde T2. Verifica
  `tests/test_aislamiento_ficha_clinica.py::test_adjunto_de_a_no_listable_en_b`.

## 9. Auditoría clínica append-only sin PHI

- [x] 9.1 `AuditoriaPort` registra ficha/evolución/adjunto/consentimiento sin PHI
  (actor, acción, `antes`/`después`, ids y estados; nunca el `texto` ni nombre/teléfono).
  Verifica `tests/test_auditoria_ficha_clinica.py::test_mutaciones_auditadas_sin_phi`
  (RN-AU-02: quién/qué/cuándo/antes/después).
- [x] 9.2 Auditoría append-only (sin UPDATE/DELETE). Verifica
  `tests/test_auditoria_ficha_clinica.py::test_auditoria_sin_delete_ni_update`.
- [x] 9.3 Sin PHI en logs: un error de evolución no incluye el `texto`. Verifica
  `tests/test_auditoria_ficha_clinica.py::test_error_no_vuelca_texto_evolucion`.

## 10. Regresión y verificación del change

- [x] 10.1 Regresión C-04/C-05/C-07 intacta: catálogos, turnos y lista de espera
  siguen en verde (la 006 no toca sus tablas). Verifica
  `tests/test_regresion_ficha_clinica.py::test_c04_c05_c07_siguen_en_verde`.
- [x] 10.2 Suite completa en verde. Verifica `py -m pytest tests/ -q`
  (suite previa + nuevos, 0 fallos).
- [x] 10.3 Validación OpenSpec limpia. Verifica
  `openspec validate c-08-ficha-clinica-consentimiento --strict` (exit 0, sin warnings).
- [x] 10.4 Sin env var nueva ni secretos; `.env.example` intacto. Verifica que el
  archivo no cambió y no se agregó ningún secreto.

## Workflow follow-up

- Correr `revisor-escenarios-turnos` sobre `specs/ficha-clinica/spec.md` antes de
  cualquier `/opsx:apply` (`AGENTS.md` §Skill propia).
- Cerrar C08-OQ-1..C08-OQ-8 con el dueño/asesor legal antes de fijar `firma_hash`,
  storage de adjuntos y el enum de `canal`.
- Wiring SQLAlchemy real de `FichaRepositorio`/`EvolucionRepositorio`/`AdjuntoRepositorio`/
  `ConsentimientoRepositorio` (ya desbloqueado con C-03/C-04 archivados).
- Revisar PO-06 y PO-10 (firma móvil self-service y cumplimiento Ley 27.706/25.326)
  antes del apply del flujo de firma.
- Reconciliar `adjuntos` con Martin: la tabla no figura en el ERD de la KB
  (`04_modelo_de_datos.md:21`); C-08 la introduce como tabla nueva en la 006 (design D11).
- Archivar el change recién después de implementarlo, verificarlo y con el `[x]` de
  `CHANGES.md` pedido por el dueño.
