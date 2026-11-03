# Tasks — C-06 `reserva-online-publica`

> Estado: **preparado, no implementado**. Ninguna tarea está hecha (`[ ]`).
> TDD rojo-primero: cada tarea nombra el test exacto que la verifica y el archivo
> destino. Comando de corrida: `py -m pytest tests/ -q` (launcher `py`, nunca
> `python`). Los tests nuevos se suman a los **104** de C-05 sin tocarlos.
> Datos ficticios: "Paciente Demo", teléfono ficticio formalmente válido
> (`+5491130551234`), nunca datos reales ni E.164 incompletos (R1).
> Ningún test usa el reloj real: todo test temporal pasa `ahora=` fijo como
> hacen los tests de C-05; los escenarios de anticipación están redactados de
> forma relativa al reloj congelado para que no caduquen.

## 1. Disponibilidad pública (server-side)

- [ ] 1.1 Crear `backend/app/reservas/disponibilidad.py` con
  `calcular_disponibilidad(prestacion, profesional, desde, ahora, ...)` que
  intersecta horario profesional × consultorio, resta bloqueos y turnos activos, y
  usa `calcular_fin`/`intervalos_solapan`/`PASO_MINUTOS` de
  `backend/app/turnos/`. Verifica
  `tests/test_disponibilidad_publica.py::test_disponibilidad_excluye_turnos_ocupados`
  (RED: `ModuleNotFoundError`; GREEN con el hueco de 10:00–10:30 excluido).
- [ ] 1.2 Restar bloqueos de la disponibilidad. Verifica
  `tests/test_disponibilidad_publica.py::test_disponibilidad_resta_bloqueos`
  (bloqueo 2026-10-07 09:00–12:00 `-03:00` ⇒ cero huecos ese día; RN-AG-04).
- [ ] 1.3 Aplicar la intersección de horarios profesional × consultorio. Verifica
  `tests/test_disponibilidad_publica.py::test_disponibilidad_fuera_de_interseccion_es_vacia`
  (consultorio 09–13, profesional 14–18 ⇒ `[]`; RN-AG-06).
- [ ] 1.4 Derivar la duración de la prestación. Verifica
  `tests/test_disponibilidad_publica.py::test_disponibilidad_usa_duracion_de_prestacion`
  (PREST-45 ⇒ `fin = inicio + 45 min`, literal `09:45:00-03:00`; RN-AG-01).
- [ ] 1.5 Test de paridad con el motor de C-05 (mismo predicado de solape y mismo
  `fin`). Verifica
  `tests/test_disponibilidad_publica.py::test_disponibilidad_paridad_predicado_c05`
  (mismos casos que `test_overlap.py`, sin releer la implementación).

## 2. Identificación liviana y pacientes

- [ ] 2.1 Definir `CatalogoPort`, `PacientePort`, `TenantPort` (+ adaptadores en
  memoria) en `backend/app/reservas/puertos.py`. Verifica
  `tests/test_puertos_contrato.py::test_paciente_port_buscar_por_telefono_normaliza_e164`
  (RED: módulo ausente; GREEN: `+5491130551234` ⇒ `+5491130551234`).
- [ ] 2.2 Alta de paciente mínimo cuando el teléfono no existe. Verifica
  `tests/test_reserva_identificacion.py::test_telefono_nuevo_crea_paciente_y_turno`
  (`201`, un paciente, turno `PENDIENTE`; RN-RE-05).
- [ ] 2.3 Vinculación por teléfono existente sin duplicar. Verifica
  `tests/test_reserva_identificacion.py::test_telefono_existente_vincula_sin_duplicar`
  (mismo `paciente_id`, un solo paciente con ese teléfono).
- [ ] 2.4 Rechazo de teléfono no normalizable sin efectos. Verifica
  `tests/test_reserva_identificacion.py::test_telefono_invalido_responde_422_sin_crear_paciente_ni_turno`
  (`422`, cero pacientes y cero turnos nuevos; E.164, `08:42`).

## 3. Token público

- [ ] 3.1 Implementar `TokenRepositorio` en `backend/app/reservas/tokens.py`
  (UUID v4, único, emitir/resolver/transferir/revocar). Verifica
  `tests/test_token_publico.py::test_reserva_devuelve_token_uuid_no_secuencial`
  (dos reservas ⇒ tokens distintos, no numéricos).
- [ ] 3.2 Resolución acotada al tenant. Verifica
  `tests/test_token_publico.py::test_token_solo_resuelve_en_su_tenant`
  (token de T1 en T2 ⇒ `None`/`404`).
- [ ] 3.3 Vigencia por estado y por `fin` (no por reloj). Verifica
  `tests/test_token_publico.py::test_token_de_turno_cancelado_o_vencido_no_gestiona`
  (`CANCELADO` y `fin` pasado ⇒ `404`; `PENDIENTE` con `fin` futuro ⇒ resuelve).
- [ ] 3.4 Transferir el token al turno nuevo al reprogramar. Verifica
  `tests/test_token_publico.py::test_reprogramar_transfiere_el_token_al_turno_nuevo`
  (el token original gestiona el turno nuevo y el original queda `REPROGRAMADO`).

## 4. Anti-spam (rate-limit + verificación liviana)

- [ ] 4.1 `ContadorPort` + rate-limit por IP y tenant en
  `backend/app/reservas/antispam.py`. Verifica
  `tests/test_antispam_publico.py::test_rate_limit_excedido_responde_429_sin_mutar`
  (`429` + `Retry-After`, cero turnos nuevos; `PUBLIC_RATE_LIMIT_MAX`/
  `PUBLIC_RATE_LIMIT_VENTANA_S` inyectados en el test, sin números de dominio).
- [ ] 4.2 Exigir verificación liviana por acción. Verifica
  `tests/test_antispam_publico.py::test_accion_sin_verificacion_responde_403_sin_mutar`
  (`403`, hueco sigue disponible; RN-RE-02).
- [ ] 4.3 Verificación de un solo uso con TTL `PUBLIC_VERIFICACION_TTL_MIN`.
  Verifica
  `tests/test_antispam_publico.py::test_verificacion_es_de_un_solo_uso`
  (segundo uso ⇒ `403`; vencida ⇒ `403`).
- [ ] 4.3a Endpoint emisor `POST /api/publico/{tokenTenant}/verificacion`.
  Verifica
  `tests/test_verificacion_publica.py::test_verificacion_emitida_201_con_expira_at_derivado`
  (`201`, `verificacion_id` no vacío,
  `expira_at = ahora + PUBLIC_VERIFICACION_TTL_MIN`, `canal = PUBLIC_ANTISPAM_MODO`).
- [ ] 4.3b Verificación vencida y reuso concurrente en la ruta real. Verifica
  `tests/test_verificacion_publica.py::test_verificacion_vencida_responde_403_sin_mutar`
  y
  `tests/test_verificacion_publica.py::test_verificacion_reusada_en_concurrencia_gana_una_sola`
  (dos acciones paralelas con la misma verificación ⇒ `201` y `403`).
- [ ] 4.4 Test de contrato del `VerificadorPort` (captcha u OTP indistinto).
  Verifica
  `tests/test_antispam_publico.py::test_verificador_port_acepta_captcha_u_otp`
  (el dominio no depende del proveedor; OQ-2).

## 5. Gestión pública: cancelar y reprogramar

- [ ] 5.1 Servicio público de gestión en `backend/app/reservas/servicio.py`
  reusando `ServicioTurnos.cancelar` y su anticipación. Verifica
  `tests/test_cancelar_publico.py::test_cancelacion_en_el_umbral_exacto_se_acepta`
  (`24 h` exactas entre `2026-10-09T10:00:00-03:00` y `2026-10-10T10:00:00-03:00`
  ⇒ `200` + `CANCELADO`).
- [ ] 5.2 Borde por un minuto menos. Verifica
  `tests/test_cancelar_publico.py::test_cancelacion_un_minuto_bajo_el_umbral_responde_403_sin_mutar`
  (`2026-10-09T10:01:00-03:00` ⇒ `403`, estado y horario intactos, texto de
  derivación a recepción).
- [ ] 5.3 Liberación del hueco al cancelar. Verifica
  `tests/test_cancelar_publico.py::test_cancelacion_publica_libera_el_hueco`
  (el slot vuelve a aparecer en disponibilidad; RN-RE-03).
- [ ] 5.4 Reprogramación con revalidación de solape. Verifica
  `tests/test_reprogramar_publico.py::test_reprogramacion_publica_a_hueco_ocupado_responde_409_con_tres_alternativas`
  (`409` + hasta 3 alternativas ordenadas, original intacto; RN-GL-02).
- [ ] 5.5 Reprogramación exitosa con anticipación suficiente. Verifica
  `tests/test_reprogramar_publico.py::test_reprogramacion_publica_exitosa_marca_original_y_crea_nuevo`
  (`original=REPROGRAMADO`, nuevo `PENDIENTE` en el nuevo horario).

## 6. Conflicto y concurrencia

- [ ] 6.1 Slot tomado entre pasos. Verifica
  `tests/test_reserva_conflicto.py::test_slot_tomado_entre_pasos_responde_409_con_tres_alternativas`
  (`409` + hasta 3 alternativas en orden cronológico, cero turnos del paciente).
- [ ] 6.2 Carrera de dos reservas del mismo hueco. Verifica
  `tests/test_reserva_conflicto.py::test_dos_reservas_concurrentes_del_mismo_slot_solo_una_persiste`
  (mismo patrón de `tests/test_concurrencia.py`: threads contra el mismo hueco ×5
  repeticiones ⇒ 1 sola creación y el resto `409` con 3 alternativas).
- [ ] 6.3 Prohibición de sobreturno en el borde público. Verifica
  `tests/test_reserva_conflicto.py::test_reserva_publica_con_sobreturno_responde_422_sin_turno`
  (`422`, cero turnos con `sobreturno=true`; RN-AG-03).
- [ ] 6.4 Solape por sillón no se degrada a sobreturno. Verifica
  `tests/test_reserva_conflicto.py::test_solape_por_sillon_responde_409_y_no_crea_sobreturno`
  (`409` + hasta 3 alternativas; las que existan realmente, nunca déficits inventados).

## 7. Borde API público (Pydantic + FastAPI)

- [ ] 7.1 Schemas de borde en `backend/app/schemas/reserva.py` con allow-list
  (`DisponibilidadOut`, `ReservaIn`, `ReservaOut`, `ErrorPublicoOut`), sin
  `TurnoOut`. Verifica
  `tests/test_api_reservas_publicas.py::test_payload_con_campo_extra_responde_422`
  (strict: `sobreturno`, `fin`, `tenant_id` ⇒ `422`).
- [ ] 7.2 Router `backend/app/routers/reservas_publicas.py` con
  `GET /api/publico/{tokenTenant}/disponibilidad` y
  `POST /api/publico/{tokenTenant}/reservas` inyectables
  (`crear_app_publica(...)` como `crear_app` de C-05) y placeholder/resolución
  de `TenantPort` para el `{tokenTenant}` (tenant inexistente o `activo=false`
  ⇒ `404` uniforme). Verifica
  `tests/test_api_reservas_publicas.py::test_post_reservas_publicas_201_con_token`
  (`201`, `estado=PENDIENTE`, `origen=RESERVA_ONLINE`, token no vacío).
- [ ] 7.3 Consulta del turno propio por token
  (`GET /api/publico/{tokenTenant}/reservas/{token}`). Verifica
  `tests/test_api_reservas_publicas.py::test_get_reserva_por_token_devuelve_solo_turno_propio`
  (`200` con allow-list; token inexistente ⇒ `404`).
- [ ] 7.4 Los headers de actor no elevan privilegios en rutas públicas. Verifica
  `tests/test_api_reservas_publicas.py::test_headers_de_actor_no_elevan_privilegios_en_rutas_publicas`
  (`X-Rol: ADMIN`/`X-Tenant-Id` ajeno ⇒ se ignora; origen público y tenant de la
  ruta; deuda D-A de C-03).
- [ ] 7.5 Mapear errores de dominio a HTTP con el handler existente. Verifica
  `tests/test_api_reservas_publicas.py::test_errores_publicos_mapean_403_404_409_422_429`
  (un test por código, sin exponer trazas).

## 8. Aislamiento multi-tenant y privacidad

- [ ] 8.1 Token de T1 en ruta de T2 ⇒ `404` uniforme. Verifica
  `tests/test_aislamiento_publico.py::test_token_de_tenant_a_en_ruta_de_tenant_b_responde_404`
  (mismo body que token inexistente).
- [ ] 8.2 Disponibilidad sin contaminación cruzada. Verifica
  `tests/test_aislamiento_publico.py::test_disponibilidad_de_b_no_muestra_turnos_de_a`
  (hueco ocupado en T1 se ofrece en T2).
- [ ] 8.3 Reserva en T2 sin escrituras en T1. Verifica
  `tests/test_aislamiento_publico.py::test_reserva_en_b_no_escribe_en_a`
  (conteo de turnos de T1 sin cambios).
- [ ] 8.4 Sin datos de terceros en disponibilidad. Verifica
  `tests/test_privacidad_publica.py::test_disponibilidad_no_expone_pacientes`
  (claves exactas: `inicio`, `fin`, `profesional_id`, `sillon_id`).
- [ ] 8.5 Sin datos de terceros en la reserva. Verifica
  `tests/test_privacidad_publica.py::test_reserva_no_expone_telefono_ni_nombre_de_terceros`
  (claves exactas del `201`).
- [ ] 8.6 `404` sin filtrar existencia ni PHI. Verifica
  `tests/test_privacidad_publica.py::test_404_no_filtra_existencia_ni_phi`
  (cuerpos idénticos para token inexistente y token de otro tenant).
- [ ] 8.7 Logs sin PHI ni token. Verifica
  `tests/test_privacidad_publica.py::test_logs_de_reserva_no_contienen_phi_ni_token`
  (usa `caplog`; sólo `tenant_id`, `turno_id`, estado y horarios; RN-CL-04).

## 9. Trazabilidad (auditoría append-only)

- [ ] 9.1 `AuditoriaPort` + entrada de creación pública. Verifica
  `tests/test_auditoria_publica.py::test_reserva_publica_queda_auditada_sin_phi`
  (`accion=CREADO`, actor público, `antes=None`, `despues=PENDIENTE`, sin nombre ni
  teléfono; RN-AU-02).
- [ ] 9.2 Entrada de cancelación con antes/después. Verifica
  `tests/test_auditoria_publica.py::test_cancelacion_publica_audita_antes_y_despues`
  (`PENDIENTE` → `CANCELADO`).
- [ ] 9.3 Entrada de reprogramación con antes/después. Verifica
  `tests/test_auditoria_publica.py::test_reprogramacion_publica_audita_antes_y_despues`
  (`PENDIENTE` → `REPROGRAMADO` + turno nuevo).
- [ ] 9.3a El rechazo bajo umbral deja la entrada de rechazo. Verifica
  `tests/test_auditoria_publica.py::test_rechazo_bajo_umbral_deja_entrada_sin_phi`
  (`CANCELACION_RECHAZADA` / `REPROGRAMACION_RECHAZADA`, motivo
  `BAJO_ANTICIPACION`, `antes == despues`, sin nombre ni teléfono; RN-RE-03).
- [ ] 9.4 La auditoría no admite borrado. Verifica
  `tests/test_auditoria_publica.py::test_auditoria_no_expone_metodo_de_borrado`
  (el puerto no tiene `delete`/`update`; misma aserción que `test_auditoria.py`).

## 10. Regresión y verificación del change

- [ ] 10.1 Regresión de C-05 intacta: el alta por recepción sigue funcionando y
  sin token. Verifica
  `tests/test_regresion_reserva_publica.py::test_creacion_por_recepcion_no_requiere_token_publico`
  (`ServicioTurnos.crear` con `origen=RECEPCION` ⇒ sin token, mismo contrato).
- [ ] 10.2 La anticipación y las alternativas son las de C-05 (no una copia).
  Verifica
  `tests/test_regresion_reserva_publica.py::test_reserva_publica_reusa_anticipacion_y_alternativas_de_c05`
  (mismo constructor `ServicioTurnos(anticipacion_min_horas=...)` y mismo
  `ConflictoSolape.alternativas`).
- [ ] 10.3 Suite completa en verde. Verifica la corrida
  `py -m pytest tests/ -q` (104 de C-05 + los nuevos, 0 fallos).
- [ ] 10.4 Validación OpenSpec limpia. Verifica
  `openspec validate c-06-reserva-online-publica --strict` (exit 0, sin warnings).
- [ ] 10.5 Documentación del borde: `.env.example` con los nombres de config
  nuevos (sin valores inventados) y `docs/` con el contrato público. Verifica que
  el archivo listado exista y que `RESERVA_TTL_H`/`CANCEL_ANTICIPACION_H` sigan
  sin valor fijado (OQ-1/OQ-3).

## Workflow follow-up

- Correr `revisor-escenarios-turnos` sobre `specs/reserva-publica/spec.md` antes
  de cualquier `/opsx:apply` (`AGENTS.md` §Skill propia).
- Cerrar OQ-1..OQ-9 con el dueño antes de fijar defaults en `.env.example`.
- Wiring SQLAlchemy cuando aterrice C-04 (`CatalogoPort`/`PacientePort`) y C-03
  (`AuditoriaPort` real en `backend/app/core/audit`).
- Enchufar `NotificadorPort` a C-13 (confirmación WA/email) y el hueco liberado a
  C-07 (auto-oferta).
- Landing de la UI `/r/:tokenTenant` (mobile-first) en el change de frontend
  correspondiente.
- Archivar el change recién después de implementarlo, verificarlo y con el
  `[x]` de `CHANGES.md` pedido por el dueño.
