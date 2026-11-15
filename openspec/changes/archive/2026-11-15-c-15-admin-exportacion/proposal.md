# Proposal — C-15 admin, exportación y KPIs (alcance parcial)

## Why

El sistema ya opera agenda, clínica, caja, OS y calendario, pero el admin del consultorio no puede
configurar parámetros, gestionar usuarios ni sacar sus datos en un clic. US-051 pide RBAC, auditoría,
exportación y reportes. C-13 sigue bloqueado por PO-03, así que este change cubre la parte que no
depende de WhatsApp y declara el resto como deuda.

## What Changes

- Endpoints de configuración del tenant (`/api/tenant/config`) sobre `tenant_parametros` con whitelist y
  validación.
- Alta, listado y activación/desactivación de usuarios del tenant (`/api/tenant/usuarios`), con hash
  Argon2 y sin exponer `password_hash`.
- Exportación 1-clic del tenant (`/api/exportacion?formato=json|csv`) con allow-list de tablas y
  exclusión de secretos.
- Reportes base (`/api/reportes/kpis`): turnos por estado, ausentismo, % reservas online, facturación
  por profesional y huecos reasignados en menos de 2 h.
- Auditoría append-only de configuración, usuarios y exportaciones.
- Sin migración: reutiliza `tenant_parametros`, `usuarios` y las tablas existentes.

## Capabilities

### New Capabilities

- `admin-tenant`: configuración, usuarios, exportación y KPIs del tenant.

### Modified Capabilities

- Ninguna.

## Impact

- `backend/app/admin/`, router y schemas.
- `backend/app/demo.py`, `backend/app/app.py`.
- Tests de dominio, HTTP demo y PostgreSQL.

## Governance

ALTO: administración de usuarios y exportación de datos del tenant. Se restringe a `ADMIN`, se audita
y no se expone PHI innecesaria ni secretos.

## Fuera de alcance (declarado)

- **WhatsApp/C-13**: recordatorios y configuración de mensajería.
- **Superadmin de plataforma**: no existe el rol; el acceso cross-tenant queda fuera.
- **Respaldo automático**: se documenta el procedimiento, no se implementa un job.
- **Ocupación**: requiere un modelo de capacidad por horarios; queda como deuda.
- **UI** de configuración y reportes (`C-15-UI` no creado).
