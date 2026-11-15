# Verification — C-15 admin, exportación y KPIs (parcial)

**Fecha**: 2026-11-15 · **Alcance**: configuración, usuarios, exportación y reportes base

## Resultado

| Gate | Resultado |
|---|---|
| Tests de dominio | **26 passed** (`tests/test_admin.py`) |
| Tests HTTP demo | **8 passed** (`tests/test_demo_api_admin.py`) |
| Tests PostgreSQL | **4 passed** (`tests/test_admin_pg.py`, con `C02_DATABASE_URL`) |
| Suite completa con DB | **838 passed, 0 skipped** |
| `ruff` | `All checks passed!` |
| `mypy` | 123 archivos, 0 errores |
| OpenSpec | `c-15-admin-exportacion` válido (`--strict`) |

Sin migración nueva: se reutilizan `tenant_parametros`, `usuarios` y las tablas de dominio con RLS.
El ciclo `upgrade head → suite completa → downgrade base` se validó en PostgreSQL 16 real.

## Rutas verificadas por HTTP

- `GET /api/tenant/config` → `200`
- `PUT /api/tenant/config` → `200` (update parcial); clave desconocida → `422`
- `GET /api/tenant/usuarios` → `200` sin `password_hash`
- `POST /api/tenant/usuarios` → `201`; email duplicado → `409 USUARIO_DUPLICADO`
- `PATCH /api/tenant/usuarios/{id}` → `200`; auto-desactivación → `409 AUTO_DESACTIVACION`
- `GET /api/exportacion?formato=json` → `200 application/json`
- `GET /api/exportacion?formato=csv` → `200 text/csv` con `seccion,id,json`
- `GET /api/reportes/kpis?desde=&hasta=` → `200`; período invertido → `422`
- RBAC: `RECEPCION` no exporta (`403`), sí ve KPIs; `ODONTOLOGO` `403`; `PACIENTE` `401`

## Reglas y definiciones

- **Configuración**: whitelist `anticipacion_cancelacion_h` (0–168), `sena_modo`, `sena_valor`,
  `recordatorios_habilitados`; actualización parcial y auditada con antes/después.
- **Usuarios**: roles `ADMIN`/`RECEPCION`/`ODONTOLOGO`, email único por tenant, password mínimo 8 y hash
  Argon2; nunca se devuelve el hash.
- **Exportación**: allow-list de 10 secciones; se excluyen `password_hash`, `oauth_ref`,
  `two_factor_secret`, `dni_cifrado`, `raw_json` y `token_hash`; todo filtrado por tenant.
- **KPIs**:
  - `ausentismo_pct = AUSENTE / (PRESENTE + AUSENTE)`.
  - `reservas_online_pct = RESERVA_ONLINE / total`.
  - `facturacion_por_profesional` con movimientos `INGRESO` no anulados que tengan turno.
  - `reasignados_2h`: turnos `LISTA_ESPERA` creados hasta 2 h antes del inicio.

## Límites que siguen

- **WhatsApp/C-13**: bloqueado por PO-03; C-15 no configura recordatorios ni mensajería.
- **Sin superadmin cross-tenant** ni acceso auditado a PHI de otro tenant.
- **Sin job de respaldo**: sólo se declara el procedimiento de exportación.
- **Sin KPI de ocupación**: requiere un modelo de capacidad por horarios.
- **Sin UI** de configuración/reportes (`C-15-UI` no creado).
- La demo usa adaptadores en memoria; los repositorios SQL están probados contra PostgreSQL pero no
  cableados al arranque.
