# Design — C-12 obras sociales y liquidación

## Context

C-09 define `CoberturaPort` pero lo implementa con una tabla en memoria vacía. `pacientes.obra_social_id`
y `prestaciones.precio_base` ya existen desde 002. `turnos.estado` incluye `PRESENTE`. Ver `proposal.md`.

## Goals / Non-Goals

**Goals:** persistir OS/coberturas/liquidaciones, calcular tramos, liquidar sólo turnos atendidos del
período, exportar CSV, aislar por tenant y dejar el presupuesto demo con cobertura real.

**Non-Goals:** validación en vivo contra la OS (SOAP/WS, fase 2), aranceles reales, cobro o conciliación
de la liquidación, UI de configuración, descarga Excel.

## Decisions

**D1 — Importes en centavos y modos compatibles con C-09.**
`modo ∈ {PORCENTAJE, MONTO}`, `valor > 0`, `tope_centavos >= 0` opcional. PORCENTAJE valida 1–100. El
monto de cobertura nunca supera el `precio_base_centavos` de la prestación (no se factura de más).

**D2 — Tramos determinísticos.**

```
base = precio_base_centavos
bruto = base * valor // 100        (PORCENTAJE)
      = valor                     (MONTO)
cobertura_os = min(bruto, tope) ; luego min(·, base)
a_cargo_paciente = base - cobertura_os
```

Sin OS del paciente o sin cobertura configurada: `cobertura_os = 0`, `a_cargo_paciente = base`,
`origen = SIN_COBERTURA`. Se expone `origen ∈ {CONFIGURADA, SIN_COBERTURA}`.

**D3 — "Atendido" es `PRESENTE`.**
La liquidación agrupa turnos con `estado = 'PRESENTE'`, `inicio ∈ [desde, hasta)` (día operativo -03:00),
paciente con la OS de la liquidación y prestación con cobertura configurada. Cancelados, ausentes,
pendientes y reprogramados quedan afuera. Turnos sin cobertura no se pueden facturar y no generan línea.

**D4 — Liquidación con snapshot inmutable.**
`BORRADOR` se puede regenerar para el mismo `(tenant, OS, período)`: se reemplazan líneas y total. Al
`CERRAR` pasa a `CERRADA` y cualquier regeneración devuelve `409 LIQUIDACION_CERRADA`. El detalle es un
snapshot: cambios posteriores en coberturas o turnos no alteran una liquidación cerrada.

**D5 — Unicidad y aislamiento.**
`UNIQUE(tenant_id, nombre)` en OS, `UNIQUE(tenant_id, obra_social_id, prestacion_id)` en coberturas y
`UNIQUE(tenant_id, obra_social_id, periodo_desde, periodo_hasta)` en liquidaciones. RLS `ENABLE + FORCE`
con `NULLIF(current_setting('app.tenant_id', true), '')::uuid` en las cuatro tablas.

**D6 — Adaptador de cobertura para C-09.**
`CoberturaPresupuesto` envuelve el servicio de C-12 y devuelve `CoberturaConfigurada` de
`app.presupuesto.puertos`; así el presupuesto demo deja de asumir 100% a cargo del paciente sin cambiar
el contrato de C-09.

**D7 — RBAC.**
Configuración (OS y coberturas) sólo `ADMIN`. Lectura y liquidaciones `ADMIN` y `RECEPCION`.
`ODONTOLOGO` y `PACIENTE` reciben `403`/`401` sin filtrar datos.

**D8 — Transparencia.**
Todas las respuestas de cobertura incluyen `validada_en_vivo: false`. La UI y la documentación dicen
"configurada, no validada en vivo" (RN-OS-01, DD-04).

## Risks / Trade-offs

- Sin validación realtime la OS puede rechazar la facturación → declarado y acotado a v1.
- El monto liquidado es el `precio_base` del catálogo, no un arancel negociado por OS → deuda de C-12
  fase 2 (tabla de aranceles por OS).
- La FK `pacientes.obra_social_id → obras_sociales` puede fallar si hubiera datos huérfanos; la migración
  valida y el seed demo usa NULL u OS sembradas.
- Regenerar un BORRADOR reemplaza líneas: no hay historial de versiones del borrador (sí de la cerrada).

## Verification

- Dominio: matemática de tramos, filtros de liquidación, idempotencia y cierre.
- HTTP: CRUD, preview de cobertura, liquidación, CSV, RBAC.
- PostgreSQL: migración 010 reversible, RLS (dos tenants) y roundtrip de repositorios.
- Suite completa, `ruff`, `mypy`, `openspec validate --all --strict`.
