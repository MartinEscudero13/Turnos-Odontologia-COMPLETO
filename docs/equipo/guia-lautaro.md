# Guía de continuación — Lautaro Naranjo

> **Instrucción para OpenCode:** leé este archivo completo antes de actuar.
> **No implementes C-06 hasta que C-02, C-03 y C-04 estén implementados y archivados.**
> Antes de modificar archivos, resumí el plan y esperá confirmación.
> Tu alcance es C-06 y la pieza skill+MCP del TP2; no toques C-01 a C-04.

> Estado del repo al escribir esta guía: rama `master`, working tree limpio.
> La historia fue reescrita: si ya tenías un clone, **no hagas `git pull` directo**; seguí el paso 1.
> Verificá el HEAD actual con `git log -1 --oneline`.

## 1. Tu alcance

| Trabajo | Estado | Dueño |
|---|---|---|
| Discovery, knowledge base, fundación, C-01 a C-04 | C-01 completo; C-02 a C-04 pendientes | Martin Escudero |
| C-05 `turnos-anti-solape` | completado y archivado | Martin Escudero |
| Skill propia + MCP Context7 (TP2) | completado y pusheado | **Lautaro Naranjo** |
| C-06 `reserva-online-publica` | preparado, **no implementado** | **Lautaro Naranjo** |
| Video ≤5 min del TP2 | pendiente | **Lautaro Naranjo** |
| Implementar C-06 | bloqueado hasta C-02, C-03 y C-04 | Lautaro Naranjo |

**No implementes C-06 todavía.** Hoy no existen tenants, usuarios, RBAC ni catálogos/pacientes reales. Hacerlo antes dejaría el change colgado de stubs.

## 2. Actualizar tu copia

### Si ya tenías el repo clonado

La historia se reescribió y se hizo `force-push`; los hashes viejos no existen en `origin/master`.

```bash
git fetch origin
git reset --hard origin/master
```

### Si empezás de cero

```bash
git clone https://github.com/MartinEscudero13/Turnos-Odontologia-COMPLETO.git
cd Turnos-Odontologia-COMPLETO
```

La rama correcta es **`master`**.

## 3. Configurar tu identidad de Git

```bash
git config --local user.name "Lautaro Naranjo"
git config --local user.email "228012306+lauty-naranjo@users.noreply.github.com"
```

Verificá que tus dos commits aparezcan:

```bash
git log --oneline --author="Lautaro Naranjo"
```

Esperado:

```text
7debda4 docs(skill): integra revisor-escenarios-turnos y MCP Context7
346073e feat(opsx): prepara C-06 reserva online publica
```

## 4. Preparar el entorno

Requisitos: Python 3.12+, Node.js 20+, Docker Desktop.

```bash
py --version
node --version
docker compose version

py -m pip install -r requirements-dev.txt

cd frontend
npm ci
cd ..

cp .env.example .env
```

> Docker Compose publica PostgreSQL en **5433**, no en 5432, porque tu máquina puede tener otro PostgreSQL local.

## 5. Verificar que todo esté sano antes de tocar nada

```bash
py -m pytest tests/ -q
py -m ruff check .
py -m mypy --config-file pyproject.toml
openspec validate --all --strict

cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Esperado:

- **114 tests** de backend.
- `ruff`: `All checks passed!`
- `mypy`: `Success: no issues found`.
- OpenSpec: **3 passed, 0 failed**.
- Frontend: lint/typecheck/build OK y **2 tests**.
- `tools/secret_scan.py`: `secret scan: OK`.

Smoke con Docker abierto:

```bash
docker compose config --quiet
docker compose up -d --build
curl --fail http://localhost:8000/api/health
docker compose down
```

Esperado: `{"status":"UP","service":"turnos-api","version":"0.1.0"}`.

## 6. Leer antes de trabajar

Leé, en este orden:

1. [`AGENTS.md`](../../AGENTS.md) — reglas duras del proyecto.
2. [`AUTHORS.md`](../../AUTHORS.md) — alcance de cada integrante.
3. [`ENTREGA.md`](../../ENTREGA.md) — estado del TP2.
4. [`CHANGES.md`](../../CHANGES.md) §C-06 — alcance del change.
5. [`docs/skills-mcp/README.md`](../skills-mcp/README.md) — skill + MCP.
6. [`openspec/changes/c-06-reserva-online-publica/README.md`](../../openspec/changes/c-06-reserva-online-publica/README.md) — resumen del change.
7. [`openspec/changes/c-06-reserva-online-publica/revision.md`](../../openspec/changes/c-06-reserva-online-publica/revision.md) — revisión crítica y fixes.

## 7. Cómo trabajar con OpenCode en este repo

### Abrir el proyecto

Abrí OpenCode **dentro de la carpeta del repo**:

```bash
cd Turnos-Odontologia-COMPLETO
opencode
```

OpenCode toma automáticamente [`AGENTS.md`](../../AGENTS.md) como instrucciones del proyecto.
No hagas que el agente trabaje desde otra carpeta.

### Primer prompt recomendado

```text
Leé AGENTS.md, AUTHORS.md, CHANGES.md (sección C-06), docs/skills-mcp/README.md y
openspec/changes/c-06-reserva-online-publica/README.md.
No modifiques nada todavía. Resumime:
1) qué está completo,
2) qué está bloqueado,
3) cuál es el próximo change que puedo implementar yo.
```

### Usar la skill propia

La skill está en:

```text
.opencode/skills/revisor-escenarios-turnos/SKILL.md
```

Para invocarla, pedile explícitamente al agente:

```text
Cargá la skill revisor-escenarios-turnos y auditá la spec de
openspec/changes/c-06-reserva-online-publica con la capability reserva-publica
y las RN del scope: RN-RE-01/02/03/05 y RN-GL-02.
Solo reportá hallazgos; no edites la spec.
```

La skill **solo lee y reporta**: devuelve matriz RN × escenario, hallazgos con severidad y citas `archivo:línea`. Los fixes los hacés vos (o los pedís como tarea separada).

### Usar OpenSpec por CLI

En este repo no están versionados los comandos `/opsx:*` de OpenCode. Usá el CLI `openspec`:

```bash
openspec list --json
openspec status --change c-06-reserva-online-publica --json
openspec validate --all --strict
openspec instructions apply --change c-06-reserva-online-publica --json
```

Cuando C-02/C-03/C-04 estén completos y C-06 se pueda implementar:

```bash
openspec instructions apply --change c-06-reserva-online-publica --json
```

Después seguí las tareas de `tasks.md`, en orden TDD rojo-primero.

### MCP Context7

Es una **integración externa, no una skill**. Verificá que esté disponible:

```bash
opencode mcp list
```

Esperado: `context7 connected`.

Configuración de ejemplo (sin secretos): [`docs/skills-mcp/mcp.json.example`](../skills-mcp/mcp.json.example).
Usalo para documentación de librerías del stack, **nunca** para datos de pacientes, PHI ni credenciales.

### Reglas para el agente

- No commitear ni pushear sin pedido explícito.
- Datos ficticios siempre.
- Sin secretos ni PHI en código, tests, logs o prompts.
- Type hints en Python; `any` prohibido en TypeScript.
- Tests rojo-primero en agenda, pagos, caja, obras sociales y ventanas temporales.
- Antes de implementar C-06: correr `revisor-escenarios-turnos` y cerrar bloqueantes.

## 8. Qué hacer ahora (checklist)

- [ ] Actualizar/resetear el clone a `origin/master`.
- [ ] Configurar tu identidad de Git.
- [ ] Verificar tus dos commits con `git log --author="Lautaro Naranjo"`.
- [ ] Instalar dependencias backend/frontend.
- [ ] Correr la verificación completa del paso 5.
- [ ] Leer la documentación del paso 6.
- [ ] Revisar el estado del TP2 en `ENTREGA.md`.
- [ ] Grabar el video ≤5 min del TP2.
- [ ] Esperar a que Martin cierre C-02, C-03 y C-04.
- [ ] Recién entonces implementar C-06 con TDD y la skill de revisión.

## 9. Video del TP2 (pendiente)

Guion sugerido, ≤5 minutos:

1. Mostrar el repo y `AUTHORS.md` (30 s).
2. Explicar la skill propia y mostrar `.opencode/skills/revisor-escenarios-turnos/SKILL.md` (60 s).
3. Mostrar `docs/skills-mcp/` y `opencode mcp list` con `context7 connected` (45 s).
4. Mostrar la auditoría de C-06 y los 4 bloqueantes encontrados/corregidos (90 s).
5. Mostrar `C-06` preparado y no implementado, más `openspec validate --all --strict` (45 s).
6. Cierre: alcance y próximos pasos (30 s).

## 10. Comandos de emergencia

Si algo no arranca:

```bash
py -m pytest tests/ -q
py -m ruff check .
py -m mypy --config-file pyproject.toml
openspec validate --all --strict
docker compose config
```

Si el problema es Docker:

```bash
docker compose up -d db
docker compose logs db
docker compose down
```

Si el problema es el frontend:

```bash
cd frontend
rm -rf node_modules dist
npm ci
npm run lint
npm test
npm run build
```

Si tenés conflictos por la reescritura de historia:

```bash
git fetch origin
git reset --hard origin/master
```

No hagas `git push --force` ni `git commit --amend` sin hablarlo con Martin.

