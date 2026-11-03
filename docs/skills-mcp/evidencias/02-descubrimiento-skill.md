# Evidencia 02 — Descubrimiento de la skill en una sesión limpia

**Fecha**: 2026-11-03 · **Repo**: Turnos-Odontologia

## Cómo se probó

Se abrió contexto nuevo para el agente, sin nombrar la skill, con esta consigna (resumida):

> "Auditá `openspec/changes/c-06-reserva-online-publica` antes de implementar: ¿falta algún escenario?,
> ¿quedó algún valor de dominio inventado?, ¿las tasks dicen cómo verificar cada escenario? No modifiques nada."

El agente recibió la ruta del change, la capability (`reserva-publica`) y las RN del scope de `CHANGES.md`
(RN-RE-01/02/03/05, RN-GL-02). **No se le indicó que usara ninguna skill.**

## Resultado observado

El agente, por su cuenta, abrió la skill versionada en el repo:

> "cargué la skill propia del repo `.opencode/skills/revisor-escenarios-turnos/SKILL.md`, tomé el scope de
> `CHANGES.md:211-227` ('Leer antes' + RN-RE-01/02/03/05, RN-GL-02) …"

y devolvió una auditoría que siguió exactamente el formato que la skill exige: **tabla de cobertura por RN
(la entrada "Feliz / Error de negocio / Borde / Concurrencia"), hallazgos con severidad y cita `archivo:línea`,
y sección "No verificado"**. Sin la skill, el encargo genérico "auditá la spec" no suele producir ese formato
ni una clasificación por severidad con trazabilidad a la KB.

Alcance de lo demostrado:

- La skill está registrada en `.atl/skill-registry.md` (sección *Project Skills*) y en `AGENTS.md`/`CLAUDE.md`
  con su instrucción de carga, así que el agente la encontró por la vía prevista.
- El hallazgo más relevante fue `BLOQUEANTE` ("la spec no tenía el tenant en las rutas de la API"), que ningún
  paseo genérico por la spec habría exigido: la skill lo detectó porque la matriz pide `aislamiento multi-tenant`
  como escenario obligatorio.

## Antes y después

| Sin la skill | Con la skill |
|---|---|
| "¿falta algún escenario?" → revisión por impresión general | matriz RN × (feliz/error/borde/concurrencia) |
| "¿valores inventados?" → difícil de acotar | contraste contra `10_preguntas_abiertas.md` |
| conclusiones sin trazabilidad | cada hallazgo con `archivo:línea` y severidad |

## Limitación

Una sola prueba de descubrimiento y una sola spec auditada. No prueba que la skill se cargue en otro cliente
(`Claude Code` / `Codex` tienen formatos de SKILL distintos; el frontmatter del repo es válido para opencode).
