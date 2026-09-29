# Turnos-Odontologia — Base de Conocimiento

SaaS multi-tenant argentino que une clínica odontológica profunda + obras sociales + WhatsApp/Mercado Pago. Generada en Mode B (Q&A resuelta) desde `docs/discovery/informe-discovery.md` (18 sistemas + 3 turneros, 2026-09-29) y `docs/discovery/checklist-discovery.md`.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance v1.0, fuera de alcance, métricas |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack (Next.js TS + PostgreSQL multi-tenant), arquitectura, integraciones, API |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Paciente/Odontólogo/Recepción/Admin + RBAC por (tenant, rol) + rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | Dominios, ERD, entidades (`tenant_id` raíz + EXCLUDE anti-solape), seed |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-AG/RE/SE/CL/OS/CJ/AU/IN/GL (agenda, seña, OS, caja, auditoría) |
| [06_funcionalidades.md](06_funcionalidades.md) | 6 épicas, US-001…US-052 con criterios y traza a RN |
| [07_flujos_principales.md](07_flujos_principales.md) | Reserva+seña, WA, odontograma→presupuesto→caja, lista de espera, cierre, GCal |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones (RLS, monorepo modular, idempotencia), directorios, seguridad, env |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | DD-01…DD-06 (stack, descartes, OS, WA, login) + SU-01…SU-04 |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | IN-01/IN-02 + PO-01…PO-11 (incluye todo "No evidenciado") |
| [11_integraciones.md](11_integraciones.md) | Extra: WA/MP/GCal/OS/ARCA v1 vs roadmap + guion de demo |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md)

## Resumen Ejecutivo

Agenda multi-profesional/sillón con anti-solapamiento real en DB, reserva 24/7 con seña Mercado Pago y liberación automática, odontograma FDI que deriva en presupuesto con aceptación parcial, caja multi-medio y OS configurable — todo aislado por tenant desde el día 1. Compite cerrando el hueco argentino: clínica profunda + OS/ARCA + WA/MP en un solo producto con precio ARS transparente.
