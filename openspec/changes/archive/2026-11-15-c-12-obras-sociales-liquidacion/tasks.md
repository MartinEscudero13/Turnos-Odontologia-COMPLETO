# Tasks — `c-12-obras-sociales-liquidacion`

## 1. RED — tests primero

- [x] 1.1 `tests/test_obras_sociales.py` (en memoria): catálogo (alta, duplicado, RBAC, auditoría), validaciones de cobertura (`PORCENTAJE` 1–100, `MONTO > 0`, tope) y matemática de tramos (porcentaje con tope, monto capeado, sin OS, sin cobertura).
- [x] 1.2 `tests/test_obras_sociales.py` (en memoria): liquidación (sólo `PRESENTE`, período `[desde, hasta)` en `-03:00`, otra OS/tenant, sin elegibles, regeneración de `BORRADOR`, cierre inmutable, concurrencia por UNIQUE) y CSV (columnas y centavos enteros).
- [x] 1.3 `tests/test_demo_api_obras_sociales.py`: CRUD, preview de cobertura, liquidación, CSV, `403`/`404` cross-tenant; verificar 404 antes de montar.
- [x] 1.4 `tests/test_obras_sociales_pg.py` + helper: RLS sin `app.tenant_id`, aislamiento de dos tenants y roundtrip de repositorios; verificar que se saltea sin `C02_DATABASE_URL`.

## 2. Persistencia

- [x] 2.1 Crear `models/obras_sociales.py` (obras_sociales, coberturas, liquidaciones, liquidacion_lineas) con CHECKs y UNIQUEs; verificar que importa y que `Base.metadata` las registra.
- [x] 2.2 Escribir la migración 010 con RLS `ENABLE + FORCE`, grants por columna, FK opcional de `pacientes.obra_social_id` y downgrade reversible; verificar `upgrade`/`downgrade` contra PostgreSQL.
- [x] 2.3 Implementar repositorios SQL (`ObraSocialSQL`, `CoberturaSQL`, `LiquidacionSQL`, `TurnosAtendidosSQL`) y verificar con el test PG.

## 3. Dominio y borde

- [x] 3.1 Implementar `app/obras_sociales/puertos.py` y `servicio.py` (catálogo, coberturas con validaciones, cálculo de tramos, liquidación, cierre, CSV) con RBAC y auditoría.
- [x] 3.2 Implementar `app/schemas/obras_sociales.py` y `app/routers/obras_sociales.py`; verificar `validada_en_vivo = false` y errores 403/404/409/422.
- [x] 3.3 Implementar el adaptador `CoberturaPresupuesto` para C-09 y verificar que `a_cargo_paciente` usa la cobertura configurada.

## 4. Demo y documentos

- [x] 4.1 Cablear el servicio en `backend/app/demo.py` con 3 OS ficticias, coberturas demo y turnos atendidos sembrados; montar el router en `create_app`.
- [x] 4.2 Actualizar `README.md`, `CONTINUAR.md` y `CHANGES.md` (C-12 completado, deudas de UI y aranceles por OS).
- [x] 4.3 Escribir `docs/foundation/verification-c-12-obras-sociales.md` y correr `pytest`, `ruff`, `mypy`, `openspec validate --all --strict`; archivar y commitear.
