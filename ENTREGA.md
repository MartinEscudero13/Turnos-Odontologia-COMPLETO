# ENTREGA — TP2 «Integrar una skill propia y un MCP al proyecto odontológico»

**Proyecto**: Turnos-Odontologia (SaaS de agenda odontológica, multi-tenant) · **Fecha de corte del TP2**: 2026-11-03
**Método**: adaptación al dominio de este repo de la pieza equivalente del proyecto hermano
(SDD-Active_Stack-main)

> **Nota de estado (actualizada 2026-11-13)**: este documento registra la entrega del **TP2** tal como se
> presentó el 2026-11-03. El proyecto siguió avanzando: C-06 a C-11, F-02 y la fase de caja/señas ya están
> implementados, verificados y archivados (13 changes archivados, 678 tests verdes). Donde una fila diga
> "preparado, no implementado" o "pendiente", se conserva el estado del corte y se aclara el estado real
> entre corchetes. El estado vigente del proyecto vive en el [`README.md`](README.md) y en [`CHANGES.md`](CHANGES.md).

## Integrantes

| Integrante | GitHub | Rol en esta entrega |
|---|---|---|
| Martin Escudero | `MartinEscudero13` | Fundación, C-01 a C-04, C-05; verificación técnica y documentación de la base |
| Lautaro Naranjo | `lauty-naranjo` | C-06 `reserva-online-publica`; integración de la skill propia y del MCP Context7; documentación y evidencias |

> El alcance completo y la aclaración sobre las entregas anteriores están en [`AUTHORS.md`](AUTHORS.md).

## Enlaces

| Dato | Valor |
|---|---|
| Repositorio | `MartinEscudero13/Turnos-Odontologia-COMPLETO` (rama `master`) |
| Ficha de investigación | [`docs/skills-mcp/investigacion.md`](docs/skills-mcp/investigacion.md) |
| Informe de aplicación | [`docs/skills-mcp/aplicacion.md`](docs/skills-mcp/aplicacion.md) |
| Evidencias | [`docs/skills-mcp/evidencias/`](docs/skills-mcp/evidencias/) (01–04 + snapshot antes/después) |
| Change preparado | [`openspec/changes/archive/2026-11-05-c-06-reserva-online-publica`](openspec/changes/archive/2026-11-05-c-06-reserva-online-publica/) — implementado y archivado el 2026-11-05 |
| C-01 archivado | `openspec/changes/archive/2026-11-03-c-01-foundation-setup/` |
| Verificación de C-01 | [`docs/foundation/verification-report.md`](docs/foundation/verification-report.md) |

## Requisitos y estado

| Requisito del enunciado | Estado | Evidencia / detalle |
|---|---|---|
| Ambiente configurado y funcional | ✅ | Python 3.14, Node 24, Docker Compose, `pytest`, `opencode` 2.2.0, `openspec` CLI |
| Skill propia creada y versionada | ✅ | `.opencode/skills/revisor-escenarios-turnos/SKILL.md` |
| Skill creada con una skill creadora / procedimiento reconocido | ✅ | Metodología de `skill-creator`; fuente versionada en `docs/skills-mcp/vendor/skill-creator/` |
| Skill adaptada al dominio del proyecto | ✅ | Vocabulario RN-AG/AU/CJ/CL/GL/IN/OS/RE/SE; reglas duras de `AGENTS.md`; preguntas abiertas de la KB |
| Registro de la skill (nombre, propósito, uso) | ✅ | `.atl/skill-registry.md` § *Project Skills* + Compact Rules |
| Instrucciones del agente actualizadas y coherentes | ✅ | `AGENTS.md` = `CLAUDE.md`; fila de *Proyecto*, § *Skill propia*, § *MCP: Context7*, paso 4 del flujo |
| MCP conectado y al menos una herramienta real ejecutada | ✅ | `opencode mcp list`; `resolve-library-id` + `query-docs` (evidencia 03) |
| MCP documentado (requisitos, config, verificación, troubleshooting) | ✅ | `README.md` § *MCP: Context7* + `docs/skills-mcp/mcp.json.example` |
| MCP documentado como integración, no como skill | ✅ | `AGENTS.md` § *MCP: Context7* (fuera del registry) |
| Change pendiente preparado con SDD (proposal/design/spec/tasks) | ✅ | `openspec/changes/c-06-reserva-online-publica/` (proposal, design, spec `reserva-publica`, tasks) — **implementado y archivado el 2026-11-05** |
| ≥3 escenarios verificables | ✅ | **48 escenarios** en 10 requirements |
| Tareas con la forma de verificación de cada escenario | ✅ | **50 tareas**, cada una con el nombre exacto del test que la verifica |
| Reglas del change revisadas contra la KB | ✅ | Revisión con la skill (`revision.md`); sin valores abiertos inventados |
| Omisión/error detectado antes con antes/después | ✅ | 4 BLOQUEANTES: tenant ausente en rutas, verificación sin emisor, escenarios caducos por reloj real, rechazo bajo umbral sin auditoría |
| Change NO marcado implementado/verificado/archivado | ✅ | `CHANGES.md` → C-06 en `[ ]` "**preparado**"; `openspec validate --strict` en verde |
| Ficha de investigación ≤2 páginas | ✅ | `investigacion.md` (82 líneas) |
| Informe de aplicación ≤2 páginas | ✅ | `aplicacion.md` (~80 líneas) |
| Evidencias de uso de skill y MCP | ✅ | `evidencias/01` … `/04` |
| Historial de commits | ✅ | `dfa16ca` (skill/MCP), `b975a71` (C-06), `8ec3a9a` (C-01 + infra), pusheados a `master` |
| Video ≤5 min | ⏳ | Se entrega fuera del repo |
| Datos ficticios y sin secretos | ✅ | `Paciente Demo`, `+5491130551234`; `mcp.json.example` sin token; `tools/secret_scan.py` OK |
| C-01 completo (base del proyecto) | ✅ | 114 tests, ruff/mypy, frontend, Compose, Alembic y smoke de API/web verificados |

## Estado de cierre

1. **Commits y push del TP2**: completados en `master` (`8f0c5d0..8ec3a9a`).
2. **C-01**: implementado, verificado y archivado.
3. **C-02 a C-04**: implementados y archivados el 2026-11-03 (C-03 auth/RLS y C-04 catálogos quedaron cerrados ese mismo día).
4. **C-06**: preparado en el corte del TP2 e **implementado y archivado el 2026-11-05**. Después se cerraron C-07 (2026-11-05), C-08 (2026-11-06), C-09 (2026-11-12), C-10 y C-11 (2026-11-13).
5. **Video**: pendiente, se entrega fuera del repositorio.
6. **Estado vigente**: 13 changes archivados, migraciones 001–009 verificadas contra PostgreSQL real, 678 tests verdes local y 720 con `C02_DATABASE_URL`. Ver [`README.md`](README.md).

## Reproducir

```bash
git clone https://github.com/MartinEscudero13/Turnos-Odontologia-COMPLETO.git
cd Turnos-Odontologia-COMPLETO
py -m pip install -r requirements-dev.txt
py -m pytest tests/                       # 678 passed, 42 skipped
py -m ruff check .
py -m mypy --config-file pyproject.toml
openspec validate --all --strict

cd frontend
npm ci
npm run lint && npm run typecheck && npm test && npm run build
```

Compose (con Docker activo):

```bash
docker compose config --quiet
docker compose up -d --build
curl --fail http://localhost:8000/api/health   # {"status":"UP",...}
docker compose down
```

Resultados esperados al 2026-11-13: **678 passed + 42 skipped**, lint/typecheck en verde,
`openspec validate --all --strict` sin fallos (15/15), `Skill is valid!`, `context7 connected` y health
`UP`. Para correr los 42 tests que requieren base viva, ver
[`README.md` § Tests](README.md#suite-completa-con-postgresql-real).
