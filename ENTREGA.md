# ENTREGA — TP2 «Integrar una skill propia y un MCP al proyecto odontológico»

**Proyecto**: Turnos-Odontologia (SaaS de agenda odontológica, multi-tenant) · **Fecha de corte**: 2026-11-03
**Método**: adaptación de la pieza equivalente hecha en el proyecto hermano
(SDD-Active_Stack-main) al dominio de este repo

## Integrantes

| Integrante | Rol |
|---|---|
| Martin Escudero | Diseño de la skill, adaptación + revisión crítica de C-06, evidencias |
| Lautaro Naranjo | Integración de la skill y del MCP, documentación, `mcp.json.example` |

## Enlaces

| Dato | Valor |
|---|---|
| Repositorio | `MartinEscudero13/Turnos-Odontologia-COMPLETO` |
| Ficha de investigación | [`docs/skills-mcp/investigacion.md`](docs/skills-mcp/investigacion.md) |
| Informe de aplicación | [`docs/skills-mcp/aplicacion.md`](docs/skills-mcp/aplicacion.md) |
| Evidencias | [`docs/skills-mcp/evidencias/`](docs/skills-mcp/evidencias/) (01–04 + snapshot antes/después) |
| Change preparado | [`openspec/changes/c-06-reserva-online-publica`](openspec/changes/c-06-reserva-online-publica/) |

## Requisitos y estado

| Requisito del enunciado | Estado | Evidencia / detalle |
|---|---|---|
| Ambiente configurado y funcional | ✅ | `py` (Python 3.14), `pytest`, `opencode` 2.2.0, `openspec` CLI; suite previa verde (104) |
| Skill propia creada y versionada | ✅ | `.opencode/skills/revisor-escenarios-turnos/SKILL.md` |
| Skill creada con una skill creadora / procedimiento reconocido | ✅ | Adaptación con la metodología de `skill-creator`; fuente versionada en `docs/skills-mcp/vendor/skill-creator/` |
| Skill adaptada al dominio del proyecto | ✅ | Vocabulario RN-AG/AU/CJ/CL/GL/IN/OS/RE/SE; reglas duras citadas de `AGENTS.md`; 10 preguntas abiertas de la KB cruzadas |
| Registro de la skill (nombre, propósito, uso) | ✅ | `.atl/skill-registry.md` § *Project Skills* + Compact Rules |
| Instrucciones del agente actualizadas y coherentes | ✅ | `AGENTS.md` = `CLAUDE.md` (idénticos); fila de *Proyecto*, § *Skill propia*, § *MCP: Context7*, paso 4 del flujo |
| MCP conectado y al menos una herramienta real ejecutada | ✅ | `opencode mcp list`; `resolve-library-id` + `query-docs` (ver evidencia 03) |
| MCP documentado (requisitos, config, verificación, troubleshooting) | ✅ | `README.md` § *MCP: Context7* + `docs/skills-mcp/mcp.json.example` |
| MCP documentado como integración, no como skill | ✅ | `AGENTS.md` § *MCP: Context7* (fuera del registry) |
| Change pendiente preparado con SDD (proposal/design/spec/tasks) | ✅ | `openspec/changes/c-06-reserva-online-publica/` (proposal, design, spec `reserva-publica`, tasks) |
| ≥3 escenarios verificables | ✅ | **48 escenarios** en 10 requirements |
| Tareas con la forma de verificación de cada escenario | ✅ | **50 tareas**, cada una con el nombre exacto del test que la verifica |
| Regras del change revisadas contra la KB | ✅ | Revisión con la skill (`revision.md`); sin valores abiertos inventados (`CANCEL_ANTICIPACION_H`, `RESERVA_TTL_H`… quedan como config/OQ) |
| Omisión/error que pasó desapercibido **antes** (antes y después) | ✅ | 4 BLOQUEANTES detectados y corregidos: tenant ausente en rutas, verificación sin emisor, escenarios caducos por reloj real, rechazo bajo umbral sin auditoría |
| Change NO marcado implementado/verificado/archivado | ✅ | `CHANGES.md` → C-06 en `[ ]` "**preparado**"; `openspec validate --strict` en verde |
| Ficha de investigación ≤2 páginas | ✅ | `investigacion.md` (82 líneas) |
| Informe de aplicación ≤2 páginas | ✅ | `aplicacion.md` (~80 líneas) |
| Evidencias de uso de skill y MCP | ✅ | `evidencias/01` … `/04` |
| Historial de commits | ⏳ | Antes de este TP, el repo llevaba historia limpia (`8f0c5d0`). Los cambios del TP2 **aún no están commiteados** (regla dura: commit sólo con pedido explícito). Ver "Cómo cerrar" abajo |
| Video ≤5 min | ⏳ | Se entrega fuera del repo |
| Datos ficticios y sin secretos | ✅ | `Paciente Demo`, teléfono ficticio `+5491130551234`; `mcp.json.example` sin token; sin PHI; auditoría de `docs/skills-mcp/` sin coincidencias |

## Cómo cerrar el TP2 (trabajo restante)

1. **Commit** de todo lo anterior (pedido explícito del dueño). Sugerencia de commits, conventional, sin coautoría IA:
   - `feat(skill): revisor-escenarios-turnos adaptada al dominio`
   - `docs(mcp): Context7 documentada + ejemplo de config`
   - `feat(opsx): prepara c-06-reserva-online-publica (sin implementar)`
2. **Push** a `main` y actualizar este documento con el hash.
3. **Video** ≤5 min: recorrido discovery → KB → primera spec auditada (4 bloqueantes) → evidencia MCP.
4. (No ejecutado) Implementar C-06: el TP exige el change **preparado**, por eso no se implementó.

## Reproducir

```bash
cd C:\Users\tinch\Desktop\Turnos-Odontologia
py -m pytest tests/ -q
openspec validate c-06-reserva-online-publica --strict
cd docs\skills-mcp\vendor\skill-creator && py scripts\quick_validate.py ..\..\..\.opencode\skills\revisor-escenarios-turnos
opencode mcp list
```

Esperado: **104 passed** · `Change ... is valid` (exit 0, sin warnings) · `Skill is valid!` · `context7 connected`.
