# Explore — C-05 `turnos-anti-solape`

> Nota de método: las skills `openspec-explore` / `openspec-propose` no están
> instaladas en este entorno (el Skill tool devuelve "not found"; skills
> disponibles verificadas por listado). Se ejecutó su equivalente vía CLI
> `openspec` (única fuente de verdad del estado) + lectura directa de la
> base de conocimiento. Este archivo guarda el resultado del Explore.

## Problema (Discovery)

Los consultorios coordinan turnos por WhatsApp/teléfono → **dobles reservas
(problema #1 del Discovery)**, confirmaciones manuales y huecos improductivos
(`docs/discovery/checklist-discovery.md` §1, §3.2, §5.1, §7.2).

## Estado del código

- `src/` **no existe**: repo sin código previo (verificado con glob `src/**/*` → 0 archivos).
- `openspec list --json` → `changes: []`; `openspec list --specs` → `specs: []`.
  No hay specs previas ni changes en curso: C-05 parte de cero y crea
  capacidad nueva (sin deltas sobre specs existentes).
- Dependencias declaradas en `CHANGES.md`: C-03 (auth/RBAC/auditoría) y C-04
  (catálogos + pacientes). Para este ciclo el spec se diseña **standalone y
  testeable con Node 24** (lógica de dominio pura + contrato API), asumiendo
  las entidades de C-04 como prerrequisito de implementación, no como código
  existente.

## Fuentes leídas (relevo)

- `knowledge-base/04_modelo_de_datos.md` §turnos (EXCLUDE, índices, estados).
- `knowledge-base/06_funcionalidades.md` §US-001/US-002 (criterios CA-1/CA-2).
- `knowledge-base/05_reglas_de_negocio.md` §RN-AG-02/03/GL-01/02.
- `knowledge-base/07_flujos_principales.md` §Flujo 4 (cancelación → auto-oferta).
- `docs/discovery/checklist-discovery.md` §3/§5.
- `CHANGES.md` §C-05 (scope, governance CRÍTICO, migración 003).
- `.atl/skill-registry.md` (compact rules aplicables, ver Propose).

## Conclusión del Explore

El change es proponible: problema crítico y acotado, reglas verificables en DB
(constraint EXCLUDE), sin código previo que condicione el diseño. Alcance de
este ciclo: solo dominio + API de turnos con anti-solape; UI de agenda queda
como follow-up explícito (ver proposal.md Non-Goals implícito en Impact).
