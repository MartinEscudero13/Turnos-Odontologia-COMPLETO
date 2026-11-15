# Tasks — `c-15-admin-exportacion`

## 1. RED

- [x] 1.1 `tests/test_admin.py`: config (lectura, update parcial, clave inválida, auditoría), usuarios (alta, duplicado, rol inválido, no auto-desactivarse) y RBAC.
- [x] 1.2 `tests/test_admin.py`: exportación JSON/CSV sin secretos y aislada por tenant; KPIs (ausentismo, online, reasignados <2 h, período inválido).
- [x] 1.3 `tests/test_demo_api_admin.py`: config, usuarios, exportación, KPIs y RBAC por HTTP.
- [x] 1.4 `tests/test_admin_pg.py` + helper: roundtrip de config/usuarios y exportación cross-tenant.

## 2. Dominio

- [x] 2.1 `app/admin/puertos.py` con entidades, protocolos y adaptadores en memoria.
- [x] 2.2 `app/admin/servicio.py`: whitelist, validaciones, usuarios con Argon2, exportación y KPIs con definiciones explícitas.
- [x] 2.3 `app/admin/repositorios.py`: config sobre `tenant_parametros`, usuarios, exportación por allow-list y reportes SQL.

## 3. Borde y demo

- [x] 3.1 Schemas y router (`/api/tenant/config`, `/api/tenant/usuarios`, `/api/exportacion`, `/api/reportes/kpis`) con RBAC.
- [x] 3.2 Cablear en `demo.py` con config/usuarios/exportación/KPIs ficticios y montar el router.

## 4. Cierre

- [x] 4.1 Documentar que WhatsApp, superadmin, respaldo automático, ocupación y UI quedan fuera.
- [x] 4.2 `docs/foundation/verification-c-15-admin.md` y gates completos.
- [x] 4.3 Archivar, commitear y verificar CI.
