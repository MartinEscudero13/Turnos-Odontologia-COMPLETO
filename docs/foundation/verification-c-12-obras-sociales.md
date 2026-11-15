# Verification — C-12 obras sociales y liquidación

**Fecha**: 2026-11-15 · **Alcance**: catálogo de OS, coberturas, tramos y liquidación

## Resultado

| Gate | Resultado |
|---|---|
| Tests de dominio | **25 passed** (`tests/test_obras_sociales.py`) |
| Tests HTTP demo | **10 passed** (`tests/test_demo_api_obras_sociales.py`) |
| Tests PostgreSQL | **3 passed** (`tests/test_obras_sociales_pg.py`, con `C02_DATABASE_URL`) |
| Suite completa con DB | **775 passed, 0 skipped** |

La migración se validó en un PostgreSQL 16 efímero: `upgrade head` → suite completa → `downgrade base`,
incluyendo el ciclo downgrade/re-upgrade de `test_migracion_009.py`.
| Suite completa local | exit 0 |
| `ruff` | `All checks passed!` |
| `mypy` | 110 archivos, 0 errores |
| OpenSpec | `c-12-obras-sociales-liquidacion` válido (`--strict`) |

## Rutas verificadas por HTTP

- `POST /api/obras-sociales` → `201` · duplicado → `409 OBRA_SOCIAL_DUPLICADA`
- `GET /api/obras-sociales` → `200` con las 3 OS demo
- `PATCH /api/obras-sociales/{id}` → `200` con el estado nuevo
- `PUT /api/coberturas` → `200` con `validada_en_vivo = false`
- `GET /api/coberturas?obra_social_id=` → `200`
- `GET /api/coberturas/preview?paciente_id=&prestacion_id=` → `200` con los dos tramos
- `POST /api/liquidaciones` → `201` con detalle y total
- `GET /api/liquidaciones/{id}/export.csv` → `200 text/csv` con encabezado y líneas
- `POST /api/liquidaciones/{id}/cerrar` → `200 CERRADA`; regenerar → `409 LIQUIDACION_CERRADA`
- Sin turnos elegibles → `409 SIN_TURNOS_ELEGIBLES`
- Cross-tenant → `404`; `RECEPCION` configurando → `403`; `PACIENTE` → `401`

## Modelo y persistencia

Migración **010**:

- `obras_sociales`, `coberturas`, `liquidaciones`, `liquidacion_lineas` con RLS `ENABLE + FORCE`.
- `UNIQUE(tenant_id, nombre)`, `UNIQUE(tenant_id, obra_social_id, prestacion_id)`,
  `UNIQUE(tenant_id, obra_social_id, periodo_desde, periodo_hasta)`.
- `CHECK` de modo, porcentaje 1–100, montos y período.
- FK `pacientes.obra_social_id → obras_sociales` con `ON DELETE SET NULL`.
- Grants por columna y `REVOKE DELETE` en catálogo, coberturas y cabeceras.

Los repositorios SQL (`ObraSocialSQL`, `CoberturaSQL`, `LiquidacionSQL`, `TurnosAtendidosSQL`,
`PacienteObraSocialSQL`, `PrestacionPrecioSQL`) fijan `app.tenant_id` y filtran por tenant. Los
`UNIQUE` se convierten en señales de dominio con savepoint para no abortar la transacción.

## Reglas aplicadas

- **RN-OS-01**: cobertura configurable por OS × prestación; `validada_en_vivo = false` siempre.
- **RN-OS-02**: liquidación por período con detalle por turno y export CSV.
- **RN-OS-03**: seed demo de 3 obras sociales ficticias.
- **RN-AU-01/02**: RBAC por rol y auditoría append-only de las operaciones exitosas.
- **RN-GL-03**: todos los datos de tests y demo son ficticios.

## Integración con C-09

`CoberturaPresupuesto` implementa el `CoberturaPort` de C-09 sobre el catálogo de C-12. En la demo,
`Consulta` de `OS Demo Norte` cubre 50% con tope 4000: la línea del presupuesto queda en
`cobertura_os = 4000` y `a_cargo_paciente = 6000`.

## Límites que siguen

- **Sin validación realtime** con la OS (PO-04): la cobertura es declarativa.
- **Sin aranceles por OS** (PO-08): el monto base es `prestaciones.precio_base`.
- **Sin UI** de configuración ni de liquidación (`C-12-UI` no creado).
- La demo sigue en memoria; la persistencia SQL real de OS está probada en PostgreSQL pero no cableada
  al arranque de la app.
- La liquidación no registra cobro ni conciliación bancaria: es un presentable, no un pago.
