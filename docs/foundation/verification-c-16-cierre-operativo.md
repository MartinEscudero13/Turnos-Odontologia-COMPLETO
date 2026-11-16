# Verification — C-16 Cierre operativo

**Fecha**: 2026-11-16 · **Alcance**: UI operativa, imputación presupuesto→caja, ocupación, superadmin y respaldo

## Resultado

| Gate | Resultado |
|---|---|
| Backend local | **821 passed, 53 skipped** |
| Backend con PostgreSQL | **874 passed, 0 skipped** |
| Frontend | **37 passed** (5 archivos) |
| `ruff check .` | OK |
| `mypy` | 132 archivos, 0 errores |
| `npm run typecheck` / `lint` / `build` | OK |
| `openspec validate --all --strict` | **22/22** |
| Migraciones | 001 → 012 sin cambios |

## Rutas verificadas

| Acción | Endpoint | Cobertura |
|---|---|---|
| Confirmar turno | `POST /api/turnos/{id}/confirmar` | `test_turnos_estado.py`, `test_demo_api_acciones.py` |
| Marcar presente | `POST /api/turnos/{id}/presente` | idem |
| Marcar ausente | `POST /api/turnos/{id}/ausente` | idem |
| Anular movimiento | `POST /api/caja/movimientos/{id}/anular` | HTTP (motivo obligatorio) |
| Cobrar pendiente | `POST /api/caja/pendientes/{id}/cobrar` | HTTP |
| Cierres y reportes | `GET /api/caja/cierres`, `GET /api/caja/reportes` | HTTP |
| Aceptar/rechazar línea | `POST /api/presupuestos/{id}/aceptar` | HTTP + dominio |
| Resolver hallazgo | `POST /api/odontograma/{id}/resolver` | dominio |
| Activar/desactivar OS | `PATCH /api/obras-sociales/{id}` | HTTP |
| Desconectar calendario | `DELETE /api/calendar/links/{id}` | HTTP |
| Activar/desactivar usuario | `PATCH /api/tenant/usuarios/{id}` | HTTP |
| KPIs con ocupación | `GET /api/reportes/kpis` | dominio + HTTP |

## UI

- **Agenda**: botones Confirmar/Presente/Ausente/Cancelar según estado; estados finales sin acciones.
- **Caja**: anulación con motivo, cobros pendientes con medio, cierres y reportes por rango.
- **Clínica**: aceptar/rechazar líneas y resolver hallazgos.
- **Obras sociales**: alta, activación, coberturas, simulación, liquidación, detalle y CSV.
- **Calendario**: conectar, push, webhook y desconectar.
- **Configuración**: parámetros, usuarios con toggle, exportación y KPIs con ocupación.

Los tests de componentes viven en `frontend/src/pages/app/accionesInternas.test.tsx` y verifican que
cada acción dispare el método y la ruta correctos con `fetch` stubbeado.

## Integración presupuesto → caja

`ImputacionCaja` (`backend/app/caja/adaptadores.py`) implementa `ImputacionPort` y delega en
`ServicioCaja.imputar_tramo_paciente`:

- con `medio=None` deja un `CobroPendiente` visible en Caja;
- con medio crea el ingreso idempotente por `(línea, tramo PACIENTE)`;
- un replay es no-op o `409 IMPUTACION_DUPLICADA`, igual que C-10.

## Ocupación

`DatosReporte` suma `minutos_ocupados` y `minutos_disponibles`; `ServicioAdmin.kpis` calcula
`ocupacion_pct` con la misma protección contra denominador cero. En SQL, los minutos disponibles salen
de `horarios_semanales` por profesional y día de la semana; sin horarios el KPI devuelve `0.0`.

## Operación

- `tools/superadmin.py`: `list`, `create`, `activate`, `deactivate` con `DATABASE_URL`.
- `tools/backup.py`: `pg_dump --format=custom` y `pg_restore --clean --if-exists`; falla con instrucciones
  si falta la herramienta.
- `docker-compose.yml`: servicio `backup` bajo el perfil `backup`; `backups/` ignorado por Git.

## Límites que siguen

- Superadmin sin rol HTTP ni auditoría de tenant: es una operación de plataforma por CLI.
- Respaldo no agendado por el stack (cron del host/orquestador).
- Twilio de producción pendiente de número y plantillas; la demo usa el adaptador fake.
- Persistencia SQL del camino de la API: deuda declarada desde C-02.
