# Design — C-15 admin, exportación y KPIs

## Context

`tenant_parametros` (clave/valor jsonb) y `usuarios` ya existen desde 001/004. Las tablas de dominio
tienen `tenant_id` y RLS. Ver `proposal.md`.

## Decisions

**D1 — Configuración con whitelist.**
Sólo se aceptan claves conocidas: `anticipacion_cancelacion_h` (entero 0–168), `sena_modo`
(`SIN_SENA`/`PORCENTAJE`/`MONTO_FIJO`/null), `sena_valor` (entero ≥ 0/null) y
`recordatorios_habilitados` (bool). Una clave desconocida o un tipo inválido responde `422` y no
persiste. La actualización es parcial y auditada con antes/después.

**D2 — Usuarios del tenant.**
`ADMIN` crea usuarios con rol `ADMIN`/`RECEPCION`/`ODONTOLOGO`; email normalizado y único por tenant;
password mínimo 8 caracteres y hash Argon2. Nunca se devuelve `password_hash`. Un admin no puede
desactivarse a sí mismo.

**D3 — Exportación 1-clic.**
Allow-list de tablas: pacientes, profesionales, prestaciones, turnos, movimientos de caja, señas,
obras sociales, coberturas, liquidaciones y links de calendario. Se excluyen `password_hash`,
`oauth_ref`, `two_factor_secret`, `dni_cifrado` y `raw_json`. JSON devuelve secciones con conteo y
filas; CSV aplana `seccion,id,json`. Todo filtrado por tenant.

**D4 — KPIs con definiciones explícitas.**
- `turnos_por_estado`: conteo por estado en `[desde, hasta)`.
- `ausentismo_pct = AUSENTE / (PRESENTE + AUSENTE) * 100` (0 si no hay base).
- `reservas_online_pct = origen RESERVA_ONLINE / total * 100`.
- `facturacion_por_profesional`: suma de movimientos `INGRESO` no anulados con turno, agrupada por
  profesional; los movimientos sin turno no se atribuyen.
- `reasignados_2h`: turnos con `origen = LISTA_ESPERA` y `creado_en >= inicio - 2 h`.
- `ocupacion` queda fuera (requiere capacidad por horarios); se declara.

**D5 — RBAC.**
Configuración, usuarios y exportación: `ADMIN`. KPIs: `ADMIN` y `RECEPCION`. `ODONTOLOGO` y `PACIENTE`
reciben `403`/`401` sin filtrar datos.

**D6 — Sin migración.**
No hay DDL nuevo; se reutilizan las tablas existentes con RLS.

## Risks / Trade-offs

- La exportación puede ser pesada en tenants grandes: se pagina en una segunda fase; v1 exporta todo.
- Sin superadmin no hay acceso cross-tenant auditado: se declara.
- La facturación por profesional ignora movimientos sin `turno_id` (deuda de C-10).
- Sin job de respaldo: sólo se documenta el procedimiento.

## Verification

- Dominio: whitelist, aislamiento, usuarios, exportación sin secretos y matemática de KPIs.
- HTTP: config, usuarios, JSON/CSV, KPIs y RBAC.
- PostgreSQL: roundtrip de config/usuarios y exportación cross-tenant.
- Suite completa, `ruff`, `mypy`, `openspec --all --strict`.
