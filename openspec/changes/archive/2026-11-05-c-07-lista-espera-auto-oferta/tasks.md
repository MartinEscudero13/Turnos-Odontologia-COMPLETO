# Tasks — C-07 `lista-espera-auto-oferta`

> Estado: **preparado, no implementado**. TDD rojo-primero: cada tarea nombra el
> test exacto que la verifica y el archivo destino. Corrida: `py -m pytest tests/ -q`
> (launcher `py`, nunca `python`). Los tests nuevos se suman a la suite de C-05
> (104) + C-06 (48) sin tocarla.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", prestaciones PREST-30
> (Consulta, 30 min) y PREST-45 (Limpieza, 45 min); nunca datos reales (R1).
> Ningún test usa el reloj real: todo test temporal inyecta `ahora=` fijo y los
> escenarios están redactados en `-03:00`.

## 1. Migración 005 (`lista_espera` + `ofertas` + RLS)

- [x] 1.1 Crear `backend/alembic/versions/005_lista_espera.py` con `lista_espera`
  (`tenant_id NOT NULL` FK, `paciente_id`, `prestacion_id`, `profesional_pref?`,
  `ventana_desde?`, `ventana_hasta?`, `estado` CHECK, `creado_en`) y `ofertas`
  (`lista_espera_id`, `hueco_turno_id?`, `expira_at`, `estado` CHECK, `token`
  uuid, `creado_en`), índices `(tenant_id, estado)`, `(tenant_id, expira_at)` y
  `UNIQUE(tenant_id, lista_espera_id)` parcial para oferta vigente, y RLS
  `tenant_id = current_setting('app.tenant_id')` en ambas. Verifica
  `tests/test_migracion_005.py::test_upgrade_head_crea_lista_espera_y_ofertas_con_rls`
  (`alembic upgrade head` ⇒ tablas existen, `down_revision="004_auth_rbac"`).
- [x] 1.2 Downgrade reversible. Verifica
  `tests/test_migracion_005.py::test_downgrade_elimina_solo_005`
  (`alembic downgrade 004_auth_rbac` ⇒ 005 fuera, turnos/catálogos intactos).
- [x] 1.3 Modelos SQLAlchemy `ListaEspera` y `Oferta` en
  `backend/app/models/lista_espera.py` con type hints y FKs. Verifica
  `tests/test_migracion_005.py::test_modelos_sqlalchemy_cargan_sin_errores`.

## 2. Dominio lista de espera (alta/baja/listar/compatibles)

- [x] 2.1 Puertos `ListaEsperaRepositorio`, `OfertaRepositorio`, `OfertaPort`,
  `HuecoLiberadoPort`, `NotificadorPort` (+ adaptadores en memoria) en
  `backend/app/lista_espera/puertos.py`. Verifica
  `tests/test_lista_espera_puertos.py::test_repositorio_memoria_scoped_por_tenant`
  (alta en T1 no visible en T2; RLS lógico).
- [x] 2.2 Alta en `ServicioListaEspera.alta` con validación de tenant. Verifica
  `tests/test_lista_espera.py::test_alta_crea_entrada_pendiente`
  (`PENDIENTE`, `paciente_id`, `prestacion_id` correctos).
- [x] 2.3 Alta con paciente/prestación de otro tenant o inexistente → `404`.
  Verifica `tests/test_lista_espera.py::test_alta_paciente_o_prestacion_otro_tenant_responde_404`
  (cero entradas nuevas; multi-tenant).
- [x] 2.4 Alta duplicada para la misma (paciente, prestación) activa → `409`.
  Verifica `tests/test_lista_espera.py::test_alta_duplicada_responde_409_sin_duplicar`.
- [x] 2.5 Baja (`PENDIENTE → VENCIDO`) y baja con oferta vigente anula la oferta.
  Verifica `tests/test_lista_espera.py::test_baja_entrada_pendiente_y_baja_con_oferta_anula_oferta`
  (`VENCIDO`; oferta `CANCELADA`; hueco liberado).
- [x] 2.6 Listar ordenado por fecha de alta con filtros. Verifica
  `tests/test_lista_espera.py::test_listar_ordenado_por_fecha_de_alta_sin_mezclar_tenants`
  (PACI-1 antes que PACI-2; sin entradas de T2).
- [x] 2.7 Compatibilidad: prestación exacta, `profesional_pref` y
  `ventana_desde`/`ventana_hasta` acotan. Verifica
  `tests/test_lista_espera.py::test_compatibilidad_prestacion_pref_y_ventana`
  (coincide / pref distinto no / fuera de ventana no).

## 3. Auto-oferta al liberar un hueco

- [x] 3.1 `HuecoLiberadoPort.emitir` en el borde de `cancelar`/`reprogramar`
  (router de turnos y servicio público C-06) y adaptador Redis con idempotencia
  `auto_oferta:{turno_id}`. Verifica
  `tests/test_auto_oferta.py::test_cancelacion_emite_evento_hueco_liberado`
  (una emisión por turno liberado).
- [x] 3.2 Worker `backend/app/lista_espera/worker.py` ofrece al primer compatible.
  Verifica `tests/test_auto_oferta.py::test_hueco_liberado_ofrece_al_primer_compatible`
  (oferta `PENDIENTE`, `expira_at = ahora + OFERTA_TTL_MIN`, entrada `OFRECIDO`).
- [x] 3.3 Sin lista compatible → slot público (sin oferta, sin retención). Verifica
  `tests/test_auto_oferta.py::test_sin_lista_compatible_hueco_queda_publico`.
- [x] 3.4 Idempotencia: doble evento del mismo turno ⇒ una sola oferta. Verifica
  `tests/test_auto_oferta.py::test_doble_evento_del_mismo_turno_genera_una_oferta`.
- [x] 3.5 Borde: expiración acotada al slot y hueco con inicio ya pasado. Verifica
  `tests/test_auto_oferta.py::test_oferta_expira_en_slot_inicio_y_hueco_pasado_se_publica_directo`
  (`expira_at = min(ahora + OFERTA_TTL_MIN, slot.inicio)`; si `ahora >= slot.inicio`
  ⇒ público directo sin ronda de lista de espera).
- [x] 3.6 Turno reprogramado libera su hueco original y dispara oferta. Verifica
  `tests/test_auto_oferta.py::test_reprogramacion_libera_hueco_original_y_dispara_oferta`
  (oferta sobre el slot original; el nuevo slot queda ocupado).

## 4. Expiración y rotación

- [x] 4.1 Oferta vencida rota al siguiente compatible. Verifica
  `tests/test_auto_oferta.py::test_oferta_vencida_rota_al_siguiente_compatible`
  (oferta a PACI-1 `VENCIDA`, PACI-1 vuelve `PENDIENTE`, oferta nueva a PACI-2).
- [x] 4.2 Último compatible vencido libera el hueco al público. Verifica
  `tests/test_auto_oferta.py::test_ultimo_compatible_vencido_libera_hueco_publico`
  (sin ofertas vigentes; hueco vuelve a disponibilidad).

## 5. Aceptación de la oferta (primer aceptante + revalidación)

- [x] 5.1 Aceptación crea turno `origen=LISTA_ESPERA` revalidando solape. Verifica
  `tests/test_aceptacion_oferta.py::test_aceptacion_crea_turno_y_convierte_entrada`
  (`ServicioTurnos.crear` con `origen="LISTA_ESPERA"`; oferta `ACEPTADA`, entrada
  `CONVERTIDO`).
- [x] 5.2 Aceptación tras expiración → `409` sin turno. Verifica
  `tests/test_aceptacion_oferta.py::test_aceptacion_tras_expira_responde_409_sin_turno`.
- [x] 5.3 Aceptación con hueco ya tomado → revalidación `409`, oferta `VENCIDA`,
  entrada vuelve `PENDIENTE` (no rota: el hueco ya lo ocupó recepción). Verifica
  `tests/test_aceptacion_oferta.py::test_aceptacion_con_hueco_tomado_no_crea_turno`.
- [x] 5.4 Doble aceptación concurrente ⇒ una sola crea turno. Verifica
  `tests/test_aceptacion_oferta.py::test_doble_aceptacion_crea_un_solo_turno`
  (threads contra el mismo token ⇒ una `201`, otra `409`).

## 6. Hold del hueco en la disponibilidad pública (C-06)

- [x] 6.1 `OfertaPort.huecos_retenidos` y resta en `ServicioReservasPublicas.disponibilidad`.
  Verifica `tests/test_hold_hueco.py::test_hueco_retenido_no_aparece_en_disponibilidad`
  (oferta vigente ⇒ hueco excluido).
- [x] 6.2 Liberación de la retención al vencer/aceptar/cancelar. Verifica
  `tests/test_hold_hueco.py::test_oferta_vencida_libera_retencion`
  (tras vencer/aceptar ⇒ hueco vuelve a ofrecerse).
- [x] 6.3 Regresión C-06: disponibilidad sin ofertas idéntica a la actual. Verifica
  `tests/test_hold_hueco.py::test_disponibilidad_sin_ofertas_no_cambia_respecto_c06`.

## 7. Borde API (`/api/lista-espera` + aceptación pública)

- [x] 7.1 Schemas en `backend/app/schemas/lista_espera.py` (allow-list, sin PHI).
  Verifica `tests/test_api_lista_espera.py::test_payload_con_campo_extra_responde_422`
  (strict: `tenant_id`/`fin` ⇒ `422`).
- [x] 7.2 Router `backend/app/routers/lista_espera.py` con `POST /api/lista-espera`,
  `DELETE /api/lista-espera/{id}`, `GET /api/lista-espera` inyectables
  (`crear_router(...)`) y actor por headers (RBAC recepción/admin). Verifica
  `tests/test_api_lista_espera.py::test_alta_baja_listar_por_http_201_200_204`.
- [x] 7.3 Endpoint público `POST /api/publico/{tokenTenant}/ofertas/{token}/aceptar`.
  Verifica `tests/test_api_lista_espera.py::test_aceptar_oferta_publica_201_con_turno`
  (turno `origen=LISTA_ESPERA`; token ajeno/inexistente ⇒ `404`).
- [x] 7.4 Mapeo de errores de dominio a HTTP. Verifica
  `tests/test_api_lista_espera.py::test_errores_lista_espera_mapean_404_409_422`
  (un test por código, sin exponer trazas).

## 8. Aislamiento multi-tenant

- [x] 8.1 Token de oferta de T1 no resuelve en T2. Verifica
  `tests/test_aislamiento_lista_espera.py::test_token_oferta_de_a_en_b_responde_404`.
- [x] 8.2 Listado/alta/baja nunca cruzan tenants. Verifica
  `tests/test_aislamiento_lista_espera.py::test_operaciones_de_a_no_tocan_b`.
- [x] 8.3 La retención de un hueco en T1 no afecta la disponibilidad de T2. Verifica
  `tests/test_aislamiento_lista_espera.py::test_retencion_de_a_no_afecta_disponibilidad_de_b`.

## 9. Trazabilidad (auditoría append-only, sin PHI)

- [x] 9.1 `AuditoriaPort` registra alta/baja/oferta/aceptación/vencimiento/
  cancelación sin PHI, con actor, acción, timestamp y `tenant_id`. Verifica
  `tests/test_auditoria_lista_espera.py::test_oferta_y_aceptacion_auditadas_sin_phi`
  (sólo `tenant_id`, `entrada_id`, `oferta_id`, `turno_id`, estados; RN-AU-02).
- [x] 9.2 La auditoría es append-only: UPDATE/DELETE sobre un registro se rechazan
  (`403`/`405`). Verifica
  `tests/test_auditoria_lista_espera.py::test_auditoria_sin_delete_ni_update`.
- [x] 9.3 La auditoría nunca cruza tenants. Verifica
  `tests/test_auditoria_lista_espera.py::test_auditoria_de_a_no_incluye_registros_de_b`.

## 10. Regresión y verificación del change

- [x] 10.1 Regresión C-05/C-06 intacta: cancelación por recepción y pública siguen
  funcionando y ahora emiten el evento. Verifica
  `tests/test_regresion_lista_espera.py::test_cancelacion_c05_y_c06_siguen_en_verde_y_emiten_evento`.
- [x] 10.2 `origen=LISTA_ESPERA` es un valor válido del schema y del CHECK de la 003.
  Verifica `tests/test_regresion_lista_espera.py::test_origen_lista_espera_valido_en_schema_y_check`.
- [x] 10.3 Suite completa en verde. Verifica `py -m pytest tests/ -q`
  (104 de C-05 + 48 de C-06 + nuevos, 0 fallos).
- [x] 10.4 Validación OpenSpec limpia. Verifica
  `openspec validate c-07-lista-espera-auto-oferta --strict` (exit 0, sin warnings).
- [x] 10.5 Documentación del borde: `.env.example` con `OFERTA_TTL_MIN` (sin valor
  fijado, C07-OQ-1) y `docs/` con el contrato. Verifica que el archivo exista y que
  `OFERTA_TTL_MIN` siga sin valor.

## Workflow follow-up

- Correr `revisor-escenarios-turnos` sobre `specs/lista-espera/spec.md` y
  `specs/reserva-publica/spec.md` antes de cualquier `/opsx:apply` (`AGENTS.md`
  §Skill propia).
- Cerrar C07-OQ-1..C07-OQ-4 con el dueño antes de fijar defaults en `.env.example`.
- Wiring SQLAlchemy real de `ListaEsperaRepositorio`/`OfertaRepositorio` y Redis
  de `HuecoLiberadoPort` (ya desbloqueado con C-04/C-03 archivados).
- Enchufar `NotificadorPort` a C-13 (WA "SI"/"NO" y link de aceptación).
- Archivar el change recién después de implementarlo, verificarlo y con el `[x]`
  de `CHANGES.md` pedido por el dueño.
