# Tasks — C-11 `senas-mercadopago`

> Estado: **preparado, no implementado**. Governance **CRÍTICO**: no se empieza hasta que el dueño
> apruebe `proposal.md`, `design.md`, las tres delta specs y este archivo.
> TDD rojo-primero: cada tarea nombra el test exacto que la verifica.
> **C-11 v1 es backend + contratos + migración 009 + tests**: no hay tareas de frontend
> ejecutables (la UI está diferida a `C-11-UI`, ver §12).
> Corrida backend: `py -m pytest tests/ -q` (launcher `py`, nunca `python`).
> **Gate obligatorio (§13)**: la suite debe correr con `C02_DATABASE_URL` y `skipped == 0`; sin esa
> variable el gate falla. `mypy --strict` (`py -m mypy backend/app/senas`) también es gate.
> **Ningún test llama a la red**: la pasarela se ejerce con `AdaptadorPasarelaFake` y el secreto de
> webhook de los tests es ficticio.
> Datos ficticios: "Paciente Demo"/"Otro Paciente Demo", PACI-1/PACI-9, "Conducto Demo", usuarios
> U1 (RECEPCION), U2 (ADMIN), U3 (ODONTOLOGO); `precio_base=10000`, `PORCENTAJE=30` ⇒ `3000`.
> Reloj siempre inyectado; instantes en `-03:00` (RN-GL-03).

## 0. Cobertura de reglas

| Regla | Requirement de `specs/senas` | Tareas |
|---|---|---|
| RN-SE-01 (sin seña acreditada antes de `expira_at` se libera) | Alta de la seña, Expiración y liberación, Carrera | 4.x, 7.x, 8.1–8.3 |
| RN-SE-02 (1──1 a la reserva y visible en agenda con estado) | Alta de la seña, Reprogramación, Visibilidad de la seña en agenda, RBAC, Migración | 1.6, 4.3, 4.5, 10.8–10.11, 11.1, 11.9, 11.15 |
| RN-SE-03 (webhook idempotente por `mp_payment_id`) | Webhook autenticado, Idempotencia, Acreditación | 1.6, 6.7–6.18, 8.1–8.3 |
| RN-SE-04 (aplicar al cobro o devolver según política visible) | Aplicación al cobro, Devolución, Política visible | 9.1–9.9, 10.1–10.7 |
| RN-SE-05 (monto y alcance los define el tenant) | Regla efectiva | 2.1–2.7 |
| RN-IN-03 (degradación con gracia y backoff) | Preferencia de pago | 4.6–4.10, 6.6 |
| RN-AU-02 (auditoría append-only) | Auditoría y ausencia de PHI | 11.10–11.14 |
| RN-CL-04 (sin PHI en logs ni mensajes) | Auditoría y ausencia de PHI, Privacidad | 11.10, 11.12, 5.5 |

> **RN-SE-02 "visible en agenda"** se verifica en backend con `GET /api/senas?desde=&hasta=`
> (tareas 11.9 y 11.15, filtro por `turno.inicio`, `C11-OQ-10`); **no** depende de la tarea diferida
> 12.2 de `C-11-UI`, que sólo dibuja la agenda.

## 1. Migración 009 y modelos SQLAlchemy

- [x] 1.1 Escribir el test de migración (rojo):
  `tests/test_migracion_009.py::test_upgrade_head_crea_tablas_de_senas`
  (`alembic upgrade head` ⇒ existen `senas` y `pagos_mp` con RLS forzada, `prestaciones` tiene
  `sena_modo`/`sena_valor`, `down_revision="008_caja_cierre_diario"` y la versión vigente es 009).
- [x] 1.2 Implementar `backend/alembic/versions/009_senas_mercadopago.py` con las dos tablas, FKs,
  índices, CHECKs de estado↔instante de D2, CHECKs de D3, UNIQUE de `(tenant_id, turno_id)`,
  `mp_payment_id`, `token_hash`, `(tenant_id, movimiento_caja_id)` y `(tenant_id, mp_preference_id)`,
  RLS forzada fail-closed y grants por columna (D14) hasta que 1.1 pase.
- [x] 1.3 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_downgrade_elimina_solo_009`
  (`alembic downgrade 008_caja_cierre_diario` ⇒ las dos tablas y las cuatro constraints/columnas
  nuevas de `prestaciones` desaparecen, 001–008 intactas y re-upgrade limpio).
- [x] 1.4 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_009_no_toca_caja_ni_legacy`
  (`movimientos_caja`, `cierres_diarios`, `tenant_parametros`, `turnos` y
  `prestaciones.requiere_sena`/`monto_sena` quedan exactamente como en 008).
- [x] 1.5 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_check_estado_e_instantes_en_db`
  (`estado='PAGADA'` rechazado; `monto_centavos=0` rechazado; `DEVUELTA` sin `devuelta_en` o sin
  motivo rechazada; `APLICADA` sin `movimiento_caja_id` o sin `concepto_aplicacion` rechazada;
  `LIBERADA` sin `motivo_liberacion` rechazada; `preferencia_estado='CREADA'` sin
  `mp_preference_id`/`mp_init_point` rechazada).
- [x] 1.6 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_unique_turno_pago_token_y_movimiento`
  (segunda seña del mismo turno rechazada **en el mismo tenant**; segundo `PagoMP` del mismo
  `mp_payment_id` rechazado **en cualquier tenant**; mismo `token_hash` rechazado **en cualquier
  tenant**; dos señas apuntando al mismo `movimiento_caja_id` rechazadas; una seña de un turno
  homónimo en otro tenant se acepta si el pago y el token son distintos, F-04).
- [x] 1.7 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_rls_fail_closed_y_grants_senas`
  (como `turnos_app` sin `app.tenant_id` **o con cadena vacía** ⇒ 0 filas sin error `42704` en las
  dos tablas; `DELETE` rechazado en ambas; `UPDATE` de `monto_centavos`/`regla_valor`/
  `regla_modo`/`precio_base_centavos`/`token_hash` rechazado; `UPDATE` de las columnas de
  estado/preferencia y de la transferencia de reprogramación (`turno_id`/`expira_at`, D12/F-16)
  permitido).
- [x] 1.8 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_backfill_legacy_conservador`
  (`requiere_sena=true` + `monto_sena=5000` ⇒ `MONTO_FIJO`/`5000`; `requiere_sena=true` +
  `monto_sena=NULL` ⇒ `NULL` + aviso de revisión; `requiere_sena=false` ⇒ `NULL`, sin inventar
  monto ni modo).
- [x] 1.9 Escribir el test de modelos (rojo):
  `tests/test_migracion_009.py::test_modelos_sqlalchemy_senas_cargan`; implementar
  `backend/app/models/sena.py` (`Sena`, `PagoMP`) con `Mapped[...]`, `timestamptz`, PK uuid y
  CHECKs espejo, y agregar `sena_modo`/`sena_valor` a `Prestacion` en
  `backend/app/models/catalogos.py` sin tocar las legacy.
- [x] 1.10 Escribir y hacer pasar
  `tests/test_migracion_009.py::test_check_prestacion_sena_modo_valor`
  (modo `'MITAD'` rechazado; `SIN_SENA` con `sena_valor` rechazado; `PORCENTAJE`/`MONTO_FIJO` sin
  `sena_valor` rechazados; `sena_valor` negativo rechazado).

## 2. Regla efectiva de la seña (PO-01 / RN-SE-05)

- [x] 2.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_senas_regla.py::test_override_monto_fijo_gana_al_tenant`
  (tenant `PORCENTAJE=30`, prestación `MONTO_FIJO=5000` ⇒ regla `MONTO_FIJO`, monto `5000`).
- [x] 2.2 Escribir y hacer pasar `tests/test_senas_regla.py::test_sin_sena_es_override_valido`
  (tenant `PORCENTAJE=30`, prestación `SIN_SENA` ⇒ no se cobra, aunque el tenant cobre).
- [x] 2.3 Escribir y hacer pasar `tests/test_senas_regla.py::test_herencia_del_tenant_porcentaje`
  (`sena_modo` nulo en la prestación, tenant `PORCENTAJE=30`, `precio_base=10000` ⇒ `3000`).
- [x] 2.4 Escribir y hacer pasar `tests/test_senas_regla.py::test_sin_configuracion_no_cobra`
  (sin claves en `tenant_parametros` y sin override ⇒ `SIN_SENA`, cero señas creadas).
- [x] 2.5 Escribir y hacer pasar `tests/test_senas_regla.py::test_configuracion_invalida_fail_open`
  (modo desconocido, `PORCENTAJE=0` o valor faltante ⇒ `SIN_SENA`, reserva `201` y log
  `REGLA_SENA_INVALIDA` con `tenant_id`/`prestacion_id`, sin datos del paciente).
- [x] 2.6 Escribir y hacer pasar `tests/test_senas_regla.py::test_monto_cero_no_genera_sena`
  (`precio_base=0` con `PORCENTAJE` ⇒ no se crea la seña de `0` centavos y la reserva responde
  `201` sin bloque `sena`).
- [x] 2.7 Escribir y hacer pasar `tests/test_senas_regla.py::test_truncado_al_centavo`
  (`precio_base=10000`, `PORCENTAJE=33` ⇒ `3300`; `precio_base=333`, `PORCENTAJE=50` ⇒ `166`, nunca
  `167`, C11-OQ-01).

## 3. Puertos, entidades y pasarela fake

- [x] 3.1 Escribir el test de puertos (rojo):
  `tests/test_senas_puertos.py::test_repositorios_scoped_por_tenant`; implementar
  `backend/app/senas/puertos.py` con `Sena`, `PagoMP`, `Preferencia`, `PagoExterno`, los protocolos
  de §Seams del design y adaptadores en memoria.
- [x] 3.2 Escribir y hacer pasar
  `tests/test_senas_puertos.py::test_transicionar_solo_desde_el_estado_esperado`
  (`transicionar(desde='PENDIENTE', hacia='ACREDITADA')` una sola vez; el segundo intento devuelve
  `None` y no cambia el estado).
- [x] 3.3 Escribir y hacer pasar `tests/test_senas_puertos.py::test_bloquear_y_buscar_por_hash`
  (`bloquear` devuelve la fila y `por_token` sólo resuelve el `token_hash` correcto y del tenant).
- [x] 3.4 Escribir y hacer pasar
  `tests/test_senas_puertos.py::test_pasarela_fake_sin_red`
  (`AdaptadorPasarelaFake.crear_preferencia` devuelve id e `init_point` deterministas y
  `obtener_pago` responde según lo programado con `aprobar`/`rechazar`/`demorar`/`fallar`).
- [x] 3.5 Escribir y hacer pasar
  `tests/test_senas_puertos.py::test_ningun_test_abre_sockets`
  (con `socket.socket` parcheado para fallar, corren los caminos de alta, preferencia, webhook y
  aplicación sin excepción: la frontera de red es sólo `AdaptadorPasarelaHTTP`).

## 4. Alta de la seña y preferencia (RN-SE-01, RN-IN-03)

- [x] 4.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_senas.py::test_crear_sena_porcentaje_3000`
  (reloj `2026-11-13T09:00:00-03:00`, `SENA_TTL_H=24`, turno del `2026-11-20` ⇒ seña `PENDIENTE`
  de `3000` con `regla_modo/regla_valor/precio_base_centavos` y `expira_at=2026-11-14T09:00:00-03:00`).
- [x] 4.2 Escribir y hacer pasar `tests/test_senas.py::test_expira_at_acotada_al_inicio`
  (turno del `2026-11-13T18:00:00-03:00` ⇒ `expira_at` igual al inicio, no `ahora + TTL`,
  C11-OQ-08).
- [x] 4.3 Escribir y hacer pasar `tests/test_senas.py::test_turno_sigue_pendiente`
  (tras reservar con seña el turno queda `PENDIENTE` con `origen=RESERVA_ONLINE` y la seña
  `PENDIENTE`; ningún turno `CONFIRMADO`).
- [x] 4.4 Escribir y hacer pasar `tests/test_senas.py::test_dos_reservas_dos_senas`
  (dos huecos ⇒ dos señas con `turno_id` y `token_hash` distintos).
- [x] 4.5 Escribir y hacer pasar `tests/test_senas.py::test_segunda_sena_del_mismo_turno_409`
  (segunda seña para el mismo turno ⇒ `409`, y sigue habiendo una sola).
- [x] 4.6 Escribir y hacer pasar
  `tests/test_sena_preferencia.py::test_preferencia_con_metadata_y_external_reference`
  (la preferencia se pide **después** de persistir la seña, con `external_reference=sena_id`,
  metadata de tenant/turno, vencimiento en `expira_at`; la seña queda `CREADA` con
  `mp_preference_id` e `init_point`).
- [x] 4.7 Escribir y hacer pasar
  `tests/test_sena_preferencia.py::test_mp_caido_reserva_201_y_preferencia_fallida`
  (pasarela que falla ⇒ reserva `201`, turno `PENDIENTE`, seña `PENDIENTE` con
  `preferencia_estado=FALLIDA` y ninguna fila perdida, RN-IN-03).
- [x] 4.8 Escribir y hacer pasar
  `tests/test_sena_preferencia.py::test_reintento_devuelve_la_misma_preferencia`
  (seña `CREADA` ⇒ `200` con el mismo `init_point`, sin segunda preferencia y sin sumar intentos).
- [x] 4.9 Escribir y hacer pasar `tests/test_sena_preferencia.py::test_reintento_respeta_backoff`
  (`intentos_preferencia=2` y `proximo_reintento_at` futuro ⇒ `202` con `reintentar_en`, sin llamar
  a la pasarela y sin incrementar intentos, C11-OQ-05, provisional) y
  `tests/test_sena_preferencia.py::test_backoff_tope_de_15_minutos`
  (`min(2**intentos, 15)` minutos).
- [x] 4.10 Escribir y hacer pasar `tests/test_sena_preferencia.py::test_preferencia_vencida_409`
  (seña `PENDIENTE` con `expira_at <= ahora` ⇒ `409 SENA_VENCIDA`, la pasarela **no** se invoca y no
  se crea `init_point` nuevo, F-09).
- [x] 4.11 Escribir y hacer pasar
  `tests/test_reserva_publica_sena.py::test_controles_c06_siguen_aplicando`
  (reservar con seña sin `verificacion_id`, con verificación vencida o superando el rate-limit ⇒
  `403`/`429`, sin turno y sin seña persistidos, y el espía de la pasarela registra cero llamadas,
  F-21).

## 5. Token público y superficie de pago

- [x] 5.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_sena_token_publico.py::test_lectura_allow_list`
  (`GET /api/publico/T1/senas/TOK-S` ⇒ `200` con `sena_id`, `estado`, `monto_centavos`,
  `expira_at`, `preferencia_estado`, `init_point`, `turno` y `politica`, y ninguna otra clave).
- [x] 5.2 Escribir y hacer pasar
  `tests/test_sena_token_publico.py::test_token_de_otro_tenant_404_uniforme`
  (`GET /api/publico/T2/senas/TOK-S` con TOK-S de T1 ⇒ `404` idéntico al de un token inexistente).
- [x] 5.3 Escribir y hacer pasar `tests/test_sena_token_publico.py::test_token_rotado_404`
  (tras reemitir, el token anterior responde `404` y el nuevo funciona).
- [x] 5.4 Escribir y hacer pasar
  `tests/test_sena_token_publico.py::test_sena_no_pagable_sin_init_point`
  (`LIBERADA` o `expira_at` pasado ⇒ `200` con el estado y `init_point=null`).
- [x] 5.5 Escribir y hacer pasar
  `tests/test_sena_token_publico.py::test_no_expone_datos_del_paciente`
  (sin nombre, teléfono, DNI, `paciente_id` ni `tenant_id`; el token no aparece en el log).
- [x] 5.6 Escribir y hacer pasar `tests/test_sena_token_publico.py::test_solo_se_guarda_el_hash`
  (en la base no existe el token en claro; con el hash no se puede reconstruir el link y dos señas
  nunca comparten `token_hash`).
- [x] 5.7 Escribir y hacer pasar `tests/test_api_pago_publico.py::test_contrato_de_rutas`
  (`GET`/`POST .../preferencia` responden `200/201/202/404/429` según el escenario; sin
  `verificacion_id` no hace falta; `POST` no existe en `/api/publico/.../senas/{token}/pagar`).

## 6. Webhook: autenticidad, idempotencia y acreditación (RN-SE-03)

- [x] 6.1 Escribir el test de firma (rojo):
  `tests/test_sena_webhook.py::test_firma_valida_procesa`
  (secreto ficticio por env; manifiesto `id:...;request-id:...;ts:...;` ⇒ `200`, `PagoMP`
  registrado y seña acreditada); implementar `app/senas/webhook.py` con `hmac.compare_digest`.
- [x] 6.2 Escribir y hacer pasar `tests/test_sena_webhook.py::test_firma_invalida_401`
  (`x-signature` ausente o con `v1` distinto ⇒ `401`, ningún `PagoMP`, seña `PENDIENTE` y la
  pasarela no se consulta).
- [x] 6.3 Escribir y hacer pasar `tests/test_sena_webhook.py::test_sin_secreto_503`
  (sin `MP_WEBHOOK_SECRET` ⇒ `503 WEBHOOK_NO_CONFIGURADO`, sin persistir ni acreditar).
- [x] 6.4 Escribir y hacer pasar `tests/test_sena_webhook.py::test_el_cuerpo_no_acredita`
  (cuerpo con `status=approved` y `monto=1` mientras la pasarela informa un pago rechazado ⇒ `200`,
  se registra el estado real y la seña sigue `PENDIENTE`).
- [x] 6.5 Escribir y hacer pasar
  `tests/test_sena_webhook.py::test_notificacion_no_payment_se_ignora`
  (`type=merchant_order` firmado ⇒ `200`, sin consultar la pasarela y sin tocar señas).
- [x] 6.6 Escribir y hacer pasar `tests/test_sena_webhook.py::test_pasarela_caida_503`
  (`obtener_pago` lanza `PasarelaNoDisponible` ⇒ `503`, nada acreditado, todo como estaba).
- [x] 6.7 Escribir y hacer pasar `tests/test_sena_webhook.py::test_duplicado_200_sin_efecto`
  (segunda notificación del mismo `mp_payment_id` ⇒ `200` con `resultado=DUPLICADO`, un solo
  `PagoMP` y un solo movimiento cuando se aplique).
- [x] 6.8 Escribir y hacer pasar
  `tests/test_sena_webhook.py::test_estado_no_aprobado_registra_sin_acreditar`
  (`PENDING` ⇒ `PagoMP` con `resultado=IGNORADO` y seña `PENDIENTE`).
- [x] 6.9 Escribir y hacer pasar `tests/test_sena_webhook.py::test_desorden_no_degrada`
  (`APPROVED` y luego `PENDING` del mismo pago ⇒ `estado=APPROVED` se conserva, seña `ACREDITADA` y
  cero movimientos nuevos).
- [x] 6.10 Escribir y hacer pasar `tests/test_sena_webhook.py::test_monto_distinto_no_acredita`
  (seña `3000`, pago `1000` ⇒ `200` con `resultado=MONTO_DISTINTO`, seña igual y obligación de
  devolución visible en `GET /api/senas`).
- [x] 6.11 Escribir y hacer pasar `tests/test_sena_webhook.py::test_moneda_distinta_no_acredita`
  (pago en `USD` ⇒ `resultado=MONTO_DISTINTO`, sin acreditar y con obligación de devolución,
  C11-OQ-12).
- [x] 6.12 Escribir y hacer pasar `tests/test_sena_webhook.py::test_pago_no_asociable_500`
  (`metadata` que no resuelve a una seña del tenant ⇒ `500` sin persistir, **log estructurado** con
  ids y motivo, sin fila de auditoría porque no hay entidad ni actor, y el hecho no se descarta,
  F-25).
- [x] 6.13 Escribir y hacer pasar `tests/test_sena_webhook.py::test_acredita_y_confirma_turno`
  (pago `3000` `ARS` sobre seña `PENDIENTE` con turno `PENDIENTE` ⇒ seña `ACREDITADA` con
  `acreditada_en`, turno `CONFIRMADO` y auditoría `SENA_ACREDITADA` con `mp_payment_id`).
- [x] 6.14 Escribir y hacer pasar
  `tests/test_sena_webhook.py::test_pago_sobre_turno_cancelado_devuelve`
  (turno `CANCELADO` + pago aprobado ⇒ seña `DEVUELTA` con `resultado=TURNO_NO_CONFIRMABLE`, turno
  intacto y hueco no reabierto).
- [x] 6.15 Escribir y hacer pasar
  `tests/test_sena_webhook_pg.py::test_dos_webhooks_simultaneos_acreditan_una_vez`
  (dos conexiones independientes a PostgreSQL con el mismo pago ⇒ una acredita, la otra `DUPLICADO`,
  un `PagoMP`, una seña `ACREDITADA` y una sola confirmación del turno).
- [x] 6.16 Escribir y hacer pasar
  `tests/test_sena_webhook.py::test_segundo_pago_aprobado_es_excedente`
  (seña ya `ACREDITADA` por PAG-A y un `APPROVED` de PAG-B, **pago distinto** por el mismo monto ⇒
  `resultado=PAGO_EXCEDENTE`, **no** `DUPLICADO`, la seña no cambia y la obligación de devolución de
  PAG-B aparece en `GET /api/senas`, F-11).
- [x] 6.17 Escribir y hacer pasar `tests/test_sena_webhook.py::test_refunded_de_mp`
  (PAG-C `REFUNDED` sobre seña `ACREDITADA` ⇒ `resultado=REEMBOLSADO` y seña `DEVUELTA` con
  `motivo_devolucion=REEMBOLSO_MP`; PAG-D `REFUNDED` sobre seña `APLICADA` ⇒
  `resultado=REEMBOLSO_AJUSTE_CAJA`, la seña sigue `APLICADA` y queda ajuste de caja pendiente de
  `ADMIN` visible en `GET /api/senas`, F-18).
- [x] 6.18 Escribir y hacer pasar
  `tests/test_turnos_sena.py::test_turno_presente_no_se_confirma_ni_cancela_por_sena`
  (turno en `PRESENTE` ⇒ confirmar o cancelar por la vía de la seña responde `409`, el estado no
  cambia y no se emite hueco, F-21).

## 7. Expiración y auto-oferta (RN-SE-01 + RN-RE-04)

- [x] 7.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_sena_expiracion.py::test_expira_libera_y_emite_auto_oferta`
  (reloj `2026-11-14T09:00:00-03:00`, seña con `expira_at` igual ⇒ `LIBERADA` con
  `motivo_liberacion=EXPIRACION`, turno `CANCELADO` con motivo `SENA_NO_ACREDITADA` y
  `HuecoLiberadoPort.emitir` llamado con ese `turno_id`).
- [x] 7.2 Escribir y hacer pasar `tests/test_sena_expiracion.py::test_no_expira_antes`
  (seña vigente ⇒ sigue `PENDIENTE` y el turno sigue `PENDIENTE`).
- [x] 7.3 Escribir y hacer pasar `tests/test_sena_expiracion.py::test_segunda_corrida_no_duplica`
  (segunda corrida con el mismo reloj ⇒ sin transición, sin segundo evento y sin error).
- [x] 7.4 Escribir y hacer pasar
  `tests/test_sena_expiracion.py::test_turno_ya_cancelado_libera_igual`
  (turno `CANCELADO` por otro canal ⇒ la seña se libera, el turno no cambia y no hay segundo
  evento).
- [x] 7.5 Escribir y hacer pasar `tests/test_sena_expiracion.py::test_pago_tardio_no_reabre`
  (pago aprobado después de liberar ⇒ `DEVUELTA` con `resultado=FUERA_DE_TIEMPO`, turno
  `CANCELADO`, hueco todavía retenido por la oferta, C11-OQ-07).
- [x] 7.6 Escribir y hacer pasar `tests/test_sena_expiracion.py::test_reloj_inyectado`
  (dos relojes distintos producen dos resultados distintos sin `sleep`; el worker no lee el reloj
  del sistema).
- [x] 7.7 Escribir y hacer pasar
  `tests/test_sena_expiracion.py::test_emite_el_mismo_puerto_que_c06`
  (un espía de `HuecoLiberadoPort` recibe exactamente `(tenant_id, turno_id)`; la oferta la crea
  `ServicioAutoOferta`, C-11 no la reimplementa).
- [x] 7.8 Escribir y hacer pasar
  `tests/test_sena_expiracion.py::test_fallo_al_emitir_hace_rollback`
  (el puerto de hueco liberado falla ⇒ no queda escritura parcial: la seña sigue `PENDIENTE`, el
  turno sigue `PENDIENTE`, no hay auditoría de `SENA_LIBERADA` y el siguiente barrido la procesa,
  F-14).
- [x] 7.9 Registrar el barrido en el runner de workers (cron/Redis, DD-08):
  `backend/app/senas/runner.py` invoca `procesar_expiraciones(tenant_id, ahora)` por tenant con el
  intervalo configurado en el runner; test `tests/test_sena_expiracion.py::test_runner_registrado`
  (el job queda registrado y una seña vencida se libera al ejecutarlo). Sin este wiring la seña
  vencida no libera el turno: es **dependencia operativa** declarada en `proposal.md` (F-15).
- [x] 7.10 Escribir y hacer pasar
  `tests/test_sena_expiracion.py::test_barrido_de_t1_no_toca_t2`
  (T1 y T2 con señas `PENDIENTE` vencidas ⇒ procesar T1 libera sólo la de T1; la de T2 sigue
  `PENDIENTE` y su turno no se cancela, F-20).

## 8. Carreras con PostgreSQL real

- [x] 8.1 Escribir y hacer pasar
  `tests/test_sena_carreras_pg.py::test_acreditacion_gana_la_carrera`
  (dos conexiones, acreditación commiteada primero ⇒ seña `ACREDITADA`, turno `CONFIRMADO`, sin
  auto-oferta).
- [x] 8.2 Escribir y hacer pasar `tests/test_sena_carreras_pg.py::test_expiracion_gana_la_carrera`
  (expiración primero ⇒ la seña queda `LIBERADA`, el turno `CANCELADO` y el webhook responde `200`
  con `resultado=FUERA_DE_TIEMPO`, nunca `DUPLICADO` y nunca `500`, sin segundo evento de hueco.
  Cuando llega ese pago tardío la seña pasa de `LIBERADA` a `DEVUELTA` —la plata no puede quedar
  retenida— y el estado final observado es `DEVUELTA` con `liberada_en` del barrido: son **dos
  momentos**, no una contradicción con 7.5 ni con D4/D8).
- [x] 8.3 Escribir y hacer pasar `tests/test_sena_carreras_pg.py::test_el_perdedor_no_pisa`
  (una sola transición registrada, un solo instante del estado ganador y ninguna escritura posterior
  que lo cambie).
- [x] 8.4 Escribir y hacer pasar
  `tests/test_sena_carreras_pg.py::test_dos_reservas_del_mismo_hueco_una_sena`
  (una `201` y una `409` con alternativas; un turno y una seña, sin seña huérfana. Es el único
  caso con SQL crudo: la garantía es el `EXCLUDE` de C-05 y el alta pública de C-06 no tiene
  wiring a PostgreSQL).
- [x] 8.5 Escribir y hacer pasar `tests/test_sena_carreras_pg.py::test_dos_aplicar_un_movimiento`
  (dos conexiones aplicando la misma seña ⇒ un `INGRESO MP`, la otra `409 SENA_YA_APLICADA`;
  corre el **caso de uso real** `ServicioSenasAplicacion.aplicar` de §9, no un contrato SQL).
- [x] 8.6 Escribir y hacer pasar `tests/test_sena_carreras_pg.py::test_aplicar_vs_cierre`
  (o el movimiento entra antes y el cierre lo cuenta, o el cierre gana y `aplicar` da
  `409 CIERRE_CERRADO`; nunca un movimiento del día fuera del cierre, D9. También usa el caso de
  uso real de §9 sobre la misma transacción que C-10).
- [x] 8.7 Escribir y hacer pasar
  `tests/test_sena_carreras_pg.py::test_reprogramacion_vs_webhook`
  (la seña queda atada al turno nuevo y el turno confirmado es ese, nunca el original).

## 9. Aplicación al cobro a través de C-10 (C10-OQ-6)

- [x] 9.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_sena_aplicacion.py::test_aplicar_crea_movimiento_mp`
  (seña `ACREDITADA` de `3000` del turno TUR-1 y U1 ⇒ `INGRESO` de `3000` `medio=MP`
  `turno_id=TUR-1`, seña `APLICADA` con `movimiento_caja_id` y
  `concepto_aplicacion=TRATAMIENTO`).
- [x] 9.2 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_segundo_aplicar_409_sin_movimiento`
  (⇒ `409 SENA_YA_APLICADA` y un solo movimiento para la seña).
- [x] 9.3 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_dia_cerrado_409_y_sigue_acreditada`
  (día cerrado ⇒ `409 CIERRE_CERRADO`, sin movimiento y la seña sigue `ACREDITADA`).
- [x] 9.4 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_aplicar_desde_pendiente_409`
  (seña `PENDIENTE` ⇒ `409 ESTADO_INVALIDO`, sin movimiento).
- [x] 9.5 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_movimiento_suma_en_totales_del_dia`
  (el `INGRESO MP` aparece en `GET /api/caja/movimientos?fecha=` y suma en
  `totales_vigentes.mp` según el contrato de C-10).
- [x] 9.6 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_no_escribe_caja_directo`
  (con el puerto espía, `app/senas` no instancia repositorios de `app/caja` ni escribe
  `movimientos_caja`: el único camino es `AplicacionCajaPort`).
- [x] 9.7 Escribir y hacer pasar
  `tests/test_sena_caja_contrato.py::test_contrato_con_el_alta_de_c10`
  (el adaptador llama a `ServicioCaja.registrar_movimiento` con la firma real —incluida `fecha` del
  día de la aplicación en `-03:00`—, propaga `404` de turno ajeno y `409 CIERRE_CERRADO`, y comparte
  la transacción `TransaccionSQL(session)`; F-13).
- [x] 9.8 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_cancelacion_tardia_solo_admin`
  (turno cancelado bajo el umbral: U1 con `concepto=CANCELACION_TARDIA` ⇒ `403` sin movimiento;
  U2 ⇒ `APLICADA` con `concepto_aplicacion=CANCELACION_TARDIA` y movimiento `MP`, C11-OQ-03).
- [x] 9.9 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_presupuesto_aceptado_vigente_409`
  (paciente con presupuesto `ACEPTADO` vigente en C-09 ⇒ `409 PRESUPUESTO_CON_SENA`, sin
  movimiento, la seña sigue `ACREDITADA` y la pasarela de caja no se invoca, C11-OQ-13).
- [x] 9.10 Escribir y hacer pasar
  `tests/test_sena_aplicacion.py::test_ingreso_usa_el_dia_de_la_aplicacion`
  (seña acreditada el `2026-11-10` y aplicada el `2026-11-13` ⇒ el `INGRESO` queda con
  `fecha=2026-11-13`, no con la de acreditación ni la del turno; ese día cerrado ⇒
  `409 CIERRE_CERRADO` sin movimiento y la seña sigue `ACREDITADA`, F-13).

## 10. Devolución, política y reprogramación (RN-SE-04)

- [x] 10.1 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_sena_devolucion.py::test_cancelar_con_anticipacion_deja_devuelta`
  (reloj `2026-11-20T09:00:00-03:00`, turno del `2026-11-22`, `anticipacion_cancelacion_h=24` ⇒
  turno `CANCELADO`, seña `DEVUELTA` con `motivo_devolucion=POLITICA_CANCELACION` y
  `devuelta_por=null`).
- [x] 10.2 Escribir y hacer pasar
  `tests/test_sena_devolucion.py::test_cancelar_bajo_umbral_no_devuelve_sola`
  (`403` público como hoy, turno intacto y seña `ACREDITADA` hasta la decisión de `ADMIN`,
  C11-OQ-03).
- [x] 10.3 Escribir y hacer pasar `tests/test_sena_devolucion.py::test_admin_devuelve_con_motivo`
  (U2 ADMIN ⇒ `DEVUELTA` con `devuelta_por=U2`, `devuelta_en`, motivo y auditoría
  `SENA_DEVUELTA`).
- [x] 10.4 Escribir y hacer pasar `tests/test_sena_devolucion.py::test_recepcion_no_devuelve`
  (U1 ⇒ `403` y la seña sigue `ACREDITADA`).
- [x] 10.5 Escribir y hacer pasar `tests/test_sena_devolucion.py::test_sin_motivo_422`
  (`motivo` ausente o `""` ⇒ `422`, sin cambio de estado).
- [x] 10.6 Escribir y hacer pasar `tests/test_sena_devolucion.py::test_aplicada_no_se_devuelve`
  (seña `APLICADA` ⇒ `409`, sigue `APLICADA`).
- [x] 10.7 Escribir y hacer pasar
  `tests/test_sena_devolucion.py::test_politica_visible_en_reserva_y_token`
  (`politica={anticipacion_cancelacion_h:24, reembolsable:true, hay_pago_acreditado:false}` al
  reservar, `reembolsable:true` también con la seña `PENDIENTE` o `LIBERADA`, y
  `hay_pago_acreditado:true` sólo con la seña `ACREDITADA`; sin PHI, F-01).
- [x] 10.8 Escribir el test (rojo) y hacerlo pasar:
  `tests/test_sena_reprogramacion.py::test_pendiente_acompana_al_turno_nuevo`
  (seña `PENDIENTE` ⇒ apunta al turno nuevo, `expira_at` recalculado con el tope del inicio, mismo
  token y sin segunda seña).
- [x] 10.9 Escribir y hacer pasar
  `tests/test_sena_reprogramacion.py::test_acreditada_se_transfiere`
  (seña `ACREDITADA` ⇒ sigue `ACREDITADA` en el turno nuevo, sin segunda seña y con auditoría
  `SENA_TRANSFERIDA`).
- [x] 10.10 Escribir y hacer pasar
  `tests/test_sena_reprogramacion.py::test_aplicada_no_se_transfiere`
  (seña `APLICADA` ⇒ no cambia de turno, el turno nuevo no crea seña y se audita
  `SENA_NO_TRANSFERIDA`).
- [x] 10.11 Escribir y hacer pasar
  `tests/test_sena_reprogramacion.py::test_token_vencido_se_reemite`
  (seña `PENDIENTE` con token vencido + reprogramación válida ⇒ `expira_at` recalculado, el token
  anterior responde `404`, se entrega uno nuevo y se audita `SENA_TRANSFERIDA` con
  `token_reemitido=true`; si el token no venció, el mismo token sigue sirviendo, F-16).

## 11. RBAC, aislamiento, auditoría y PHI

- [ ] 11.1 Escribir y hacer pasar `tests/test_api_senas.py::test_odontologo_lee_no_aplica`
  (U3 ⇒ `200` al leer y `403` al aplicar, sin movimientos).
- [ ] 11.2 Escribir y hacer pasar `tests/test_api_senas.py::test_recepcion_aplica_no_devuelve`
  (U1 ⇒ `200` al aplicar y `403` al devolver).
- [ ] 11.3 Escribir y hacer pasar `tests/test_api_senas.py::test_admin_aplica_y_devuelve`
  (U2 ⇒ `APLICADA` y `DEVUELTA`, ambas auditadas con U2).
- [ ] 11.4 Escribir y hacer pasar `tests/test_api_senas.py::test_paciente_401`
  (identidad de paciente en listar/aplicar/devolver ⇒ `401`, sin exponer ni modificar nada).
- [ ] 11.5 Escribir y hacer pasar `tests/test_api_senas.py::test_schema_rechaza_campos_extra`
  (`tenant_id`, `paciente_nombre`, `monto_centavos` donde no corresponde ⇒ `422`).
- [ ] 11.6 Escribir y hacer pasar
  `tests/test_aislamiento_senas.py::test_sena_de_t1_no_se_lee_desde_t2`
  (lectura por id desde T2 ⇒ `404` y ningún dato de T1).
- [ ] 11.7 Escribir y hacer pasar
  `tests/test_aislamiento_senas.py::test_aplicar_desde_otro_tenant_404`
  (⇒ `404` y ningún movimiento en T2).
- [ ] 11.8 Escribir y hacer pasar
  `tests/test_aislamiento_senas.py::test_webhook_no_cruza_tenants`
  (metadata de T2 con `sena_id` de T1 ⇒ no acredita, `500`, log con ids).
- [ ] 11.9 Escribir y hacer pasar `tests/test_aislamiento_senas.py::test_listado_no_mezcla`
  (`GET /api/senas` de T1 devuelve sólo las de T1).
- [ ] 11.10 Escribir el test de auditoría (rojo) y hacerlo pasar:
  `tests/test_auditoria_senas.py::test_cada_transicion_audita`
  (`SENA_CREADA`, `SENA_PREFERENCIA_CREADA`, `SENA_ACREDITADA`, `SENA_APLICADA`,
  `SENA_DEVUELTA`, `SENA_LIBERADA`, `SENA_TRANSFERIDA`, `SENA_REEMBOLSO_MP` con `sena_id`, monto,
  actor y `antes`/`después`).
- [ ] 11.11 Escribir y hacer pasar
  `tests/test_auditoria_senas.py::test_webhook_rechazado_no_copia_cuerpo`
  (firma inválida ⇒ `SENA_WEBHOOK_RECHAZADO` con ids y motivo de dominio, sin cuerpo ni datos del
  pagador).
- [ ] 11.12 Escribir y hacer pasar `tests/test_auditoria_senas.py::test_raw_json_minimizado`
  (`raw_json` sólo con id, estado, detalle, monto, moneda, `date_approved`, referencia y metadata;
  sin email, nombre, tarjeta ni cuotas, C11-OQ-11).
- [ ] 11.13 Escribir y hacer pasar `tests/test_errors_phi.py::test_error_de_sena_sin_phi`
  (el error de dominio y el log llevan sólo código, `sena_id`, `tenant_id` y monto).
- [ ] 11.14 Escribir y hacer pasar `tests/test_auditoria_senas.py::test_auditoria_append_only`
  (`UPDATE`/`DELETE` sobre una entrada de señas rechazados; la entrada original permanece).
- [ ] 11.15 Escribir y hacer pasar
  `tests/test_api_senas.py::test_listado_por_inicio_del_turno`
  (`GET /api/senas?desde=2026-11-15&hasta=2026-11-30` devuelve sólo la seña cuyo `turno.inicio`
  cae en el rango, aunque la seña se haya creado antes; el filtro es sobre `turno.inicio` y no
  sobre `creado_en` ni `expira_at`, C11-OQ-10).
- [ ] 11.16 Escribir y hacer pasar
  `tests/test_aislamiento_senas.py::test_devolver_desde_otro_tenant_404`
  (U2 `ADMIN` de T2 llama a `POST /api/senas/{id}/devolver` con una seña de T1 ⇒ `404`, la seña de
  T1 sigue `ACREDITADA` y no queda obligación en T2, F-20).

## 12. Diferido a `C-11-UI` (no ejecutable en C-11)

> **No se implementa acá.** Sin `design-system/README.md` aprobado no hay UI (política
> `design-mockups`, modo `deferred`). Estas tareas describen qué deberá cubrir el change visual.

- [ ] 12.1 (C-11-UI) Página `/pagar/:tokenSena`: estado, monto, expiración, política visible y
      botón de pago con `init_point`; estados PENDIENTE/ACREDITADA/LIBERADA/DEVUELTA/APLICADA y
      reintento cuando `preferencia_estado=FALLIDA`.
- [ ] 12.2 (C-11-UI) Agenda con el estado de la seña por turno, consumiendo `GET /api/senas`.
- [ ] 12.3 (C-11-UI) Acción de recepción "aplicar seña" y de `ADMIN` "devolver seña con motivo",
      con los `409`/`403` visibles.
- [ ] 12.4 (C-11-UI) `/config` de la regla del tenant y override por prestación, si C-15 no lo
      tomó antes.
- [ ] 12.5 (C-11-UI) Mockups aprobados y capturas 390×844 / 1440×900 antes de aplicar.

## 13. Gate de verificación y governance

- [ ] 13.1 Suite completa con PostgreSQL real y sin tests salteados:
  `$env:C02_DATABASE_URL=...; py -m pytest tests/ -q` ⇒ `skipped == 0`. Sin la variable el gate
  **falla** (mismo criterio que C-10).
- [ ] 13.2 `py -m mypy backend/app/senas` con config `strict` en verde.
- [ ] 13.3 `py -m ruff check .` en verde.
- [ ] 13.4 `openspec validate c-11-senas-mercadopago --strict` en verde.
- [ ] 13.5 Correr `revisor-escenarios-turnos` sobre `specs/senas`, `specs/reserva-publica` y
  `specs/turnos-anti-solape`, y corregir todo `BLOQUEANTE`/`MAYOR` antes de aplicar.
- [ ] 13.6 Estado de las OQ: **fijadas 2026-11-13** `C11-OQ-01` (truncar al centavo), `C11-OQ-03`
  (decide `ADMIN`), `C11-OQ-04` (transferir), `C11-OQ-09` (reembolso manual) y `C11-OQ-10`
  (endpoint propio); **provisional** `C11-OQ-02` (24 h) y el backoff de `C11-OQ-05`; **abiertas no
  bloqueantes** `C11-OQ-05`, `06`, `07`, `08`, `11`, `12` y `13`. `design.md` §Open Questions y
  `docs/decisiones-po.md` §C-11 quedan sincronizados con ese estado.
- [ ] 13.7 Verificación de cierre de esta auditoría: no queda `devuelve:false` al reservar, ni
  `DUPLICADO` para pagos distintos, ni `por_mp_payment` sin `tenant_id`, ni referencias a
  `C11-OQ-12` para el descuento contra presupuesto.
- [ ] 13.8 Aprobación explícita del dueño sobre proposal + design + specs + tasks. **Sin este
  paso no se escribe una línea de `backend/`, `tests/`, `frontend/` ni de migración.**
