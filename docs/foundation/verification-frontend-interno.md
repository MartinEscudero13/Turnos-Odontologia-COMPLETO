# Verification — Frontend interno (F-06)

**Fecha**: 2026-11-15 · **Alcance**: SPA operativo para C-05…C-15

## Resultado

| Gate | Resultado |
|---|---|
| Tests frontend | **32 passed** (4 files) |
| `npm run typecheck` | OK |
| `npm run lint` | OK (0 warnings) |
| `npm run build` | OK (`dist` generado) |
| Seed demo | Idempotente (2 corridas) |
| Login + endpoints internos | `200` contra PostgreSQL real |
| OpenSpec | `frontend-interno` válido (`--strict`) |

## Rutas del SPA

- `/login` — login real + “Entrar en modo demo”
- `/app` — resumen con KPIs, accesos y facturación
- `/app/agenda` — crear turno, listar, cancelar
- `/app/pacientes` — alta y listado con consentimiento
- `/app/clinica?paciente=<id>` — consentimiento, ficha, evoluciones, odontograma y presupuesto
- `/app/caja` — totales por medio, movimientos y cierre
- `/app/senas` — señas por período
- `/app/obras-sociales` — OS, coberturas, preview, liquidaciones y CSV
- `/app/calendario` — links, push, webhook simulado y bloqueos
- `/app/config` — parámetros, usuarios, exportación y KPIs

## Seed y Compose

`backend/seed_demo.py` crea (idempotente):

- Tenant `demo`
- Usuarios `admin@demo.test`, `recepcion@demo.test`, `odontologo@demo.test` (password `demo1234`)
- 2 profesionales, 2 sillones, 2 prestaciones y 2 pacientes ficticios

Compose agrega el servicio `migrate` con `alembic upgrade head && python seed_demo.py`; la API espera
`service_completed_successfully`.

## Decisiones

- **Actor + JWT**: el cliente envía `X-Tenant-Id`, `X-User-Id`, `X-Rol` para C-05…C-15 y
  `Authorization` para catálogos/auth.
- **Sesión persistente** en `localStorage`; logout limpia storage y contexto.
- **Descargas autenticadas** de CSV/JSON por blob, no por `<a href>`.
- **Modo demo** usa credenciales sembradas; si falta el seed, muestra error accionable.

## Límites que siguen

- WhatsApp/C-13 no tiene UI (bloqueado por PO-03).
- Sin superadmin cross-tenant ni edición avanzada.
- Sin paginación: pensado para 1–3 sillones.
- Sin refresh automático de JWT: una sesión muy larga puede requerir re-login.
- La demo sigue en memoria; el seed sólo cubre auth/catálogos.
