# Design — C-16 Cierre operativo

## Context

Ver `proposal.md`. El dominio ya tenía las transiciones y los endpoints de caja, presupuesto, obras
sociales, calendario y usuarios; faltaba exponerlos en el SPA y cerrar los huecos de C-15. La demo corre
sobre adaptadores en memoria y algunas integraciones se prueban contra PostgreSQL.

## Decisions

**D1 — Transiciones de agenda auditadas.**
`ServicioTurnos.confirmar` y `_marcar_asistencia` validan la máquina de estados y escriben
`AuditoriaEntrada`. La UI sólo ofrece las acciones legales para el estado actual.

**D2 — Aceptación de presupuesto conectada a caja.**
`ImputacionCaja` implementa `ImputacionPort` delegando en
`ServicioCaja.imputar_tramo_paciente`. Con `medio=None` deja un cobro pendiente; con medio crea el
ingreso idempotente. Así el flujo presupuesto → caja es demostrable de punta a punta.

**D3 — Cobro de pendientes con medio explícito.**
La UI ofrece efectivo y transferencia; el servidor valida el medio y mantiene la idempotencia de C-10.

**D4 — Ocupación medible sin inventar capacidad.**
`DatosReporte` suma `minutos_ocupados` (turnos en estados que bloquean agenda) y `minutos_disponibles`
(capacidad semanal de los profesionales en el período). `ocupacion_pct` se calcula con la misma
protección contra división por cero que los demás porcentajes. Es un KPI de reporte; los tests de caja
siguen exigiendo que `/api/caja/reportes/ocupacion` no exista.

**D5 — Superadmin fuera de la API.**
La API resuelve un tenant por request y RLS impide el cruce. `tools/superadmin.py` usa la credencial de
dueño para listar/crear/activar/desactivar tenants. No se agrega un rol HTTP nuevo ni se toca el RBAC.

**D6 — Respaldo con herramientas estándar.**
`tools/backup.py` envuelve `pg_dump`/`pg_restore` en formato custom y `docker-compose.yml` agrega el
servicio `backup` bajo el perfil `backup`. `backups/` queda ignorado por Git.

**D7 — Tests de componentes sin red.**
Las páginas internas se prueban con `fetch` stubbeado, verificando que la acción dispare el método y la
ruta correctos.

## Risks / Trade-offs

- La aceptación sin medio crea un pendiente; el operador debe cobrarlo en Caja (flujo esperado).
- La ocupación en SQL usa la capacidad semanal declarada por profesional; si no hay horarios cargados
  el denominador es cero y el KPI queda en `0.0`.
- El superadmin por CLI requiere acceso a la base y no queda auditado en la tabla de auditoría del
  tenant; se documenta como operación de plataforma.

## Verification

- `pytest tests/test_turnos_estado.py tests/test_demo_api_acciones.py`.
- Suite completa local y con `C02_DATABASE_URL`.
- `ruff`, `mypy`, `npm run typecheck/lint/test/build`.
- `openspec validate --all --strict`.
