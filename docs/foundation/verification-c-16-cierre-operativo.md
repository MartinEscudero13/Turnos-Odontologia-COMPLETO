# Verification — C-16 Cierre operativo

**Fecha**: 2026-11-16 · **Alcance**: UI operativa, imputación presupuesto→caja, ocupación, superadmin y respaldo

## Resultado

| Gate | Resultado |
|---|---|
| Backend local | **837 passed, 53 skipped** |
| Backend con PostgreSQL | **890 passed, 0 skipped** |
| Frontend | **41 passed** (6 archivos) |
| `ruff check .` | OK |
| `mypy` | 134 archivos, 0 errores |
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

## Correcciones de bugs (2026-11-17)

- **Líneas de presupuesto**: el backend devuelve `{ linea, aceptacion }`; el front ahora tipa y
  renderiza esa estructura (antes mostraba la tabla vacía/mal).
- **Primer request autenticada**: `AuthProvider` fija el actor/token en `useLayoutEffect`, antes de los
  `useEffect` de las páginas (evita 401 al entrar al panel).
- **Fechas date-only**: `YYYY-MM-DD` se interpreta como día local; se corrigió el corrimiento de huso en
  Caja y liquidaciones. `SenasPage` calcula el rango con la fecha local.
- **Configuración compartida**: el toggle de recordatorios de `/app/config` ahora gobierna el servicio de
  WhatsApp (`ConfigWhatsAppAdmin`) y se agregó la anticipación del recordatorio.
- **Alta de paciente con consentimiento**: el checkbox crea también el consentimiento clínico versionado.
- **Clínica**: el profesional se preselecciona al cargar, evitando el 422 en el primer registro.
- **Login**: el mensaje de error lee `detalle` (el contrato del backend) y no `detail`.
- **Sesión de 15 min**: `api()` renueva el access token con el refresh token y reintenta una vez; si
  falla, cierra la sesión y redirige al login (antes quedaba “Error 401” en la página).
- **Caja**: los cobros resueltos ya no se listan como pendientes y el reporte se recarga al cobrar.
- **Paciente nuevo → Clínica**: los dominios clínicos leen la tabla SQL de pacientes mediante
  `PacienteSQL`; antes un paciente creado en Pacientes no existía para ficha/odontograma/presupuesto.
- **Tipografía de KPIs**: los valores técnicos largos (por ejemplo `movimientos_vigentes`) usan la
  variante `Stat variant="text"` y no desbordan la tarjeta.
- **Facturación por profesional**: Dashboard y Configuración muestran el nombre del profesional y no
  el UUID.
- **Datos de demo**: la agenda arranca con 4 turnos sembrados (2 `PRESENTE`, 1 `AUSENTE`, 1
  `PENDIENTE`) y un movimiento de caja de $120; los tests siguen arrancando sin seed (`APP_ENV=test`).

## Límites que siguen

- Superadmin sin rol HTTP ni auditoría de tenant: es una operación de plataforma por CLI.
- Respaldo no agendado por el stack (cron del host/orquestador).
- Twilio de producción pendiente de número y plantillas; la demo usa el adaptador fake.
- Persistencia SQL del camino de la API: deuda declarada desde C-02.
