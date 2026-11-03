# Evidencia 03 — MCP Context7: conexión y uso real

**Fecha**: 2026-11-03 · **Repo**: Turnos-Odontologia

## Qué es

Context7 (Upstash) es el MCP elegido para este proyecto. Expone documentación actualizada de librerías; es una
**integración**, no una skill, y por eso no se registra en `.atl/skill-registry.md`.

## Configuración

El repo versiona sólo el ejemplo (`docs/skills-mcp/mcp.json.example`); la config viva de la máquina está en
`~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "context7": { "type": "remote", "url": "https://mcp.context7.com/mcp", "enabled": true }
  }
}
```

Precedencia: proyecto > global. Sin token en el repo ("sin secretos en el repo", regla dura del `AGENTS.md`); la clave, de usarse, vive en `.env`.

## Verificación

```bash
opencode mcp list
```

reporta el servidor **conectado** (verificado en esta máquina). El cliente lo lista como `context7 connected`.

## Llamada real hecha en esta sesión

1. `resolve-library-id({ libraryName: "FastAPI", query: "dependency injection and response models for a public reservation endpoint" })`
   devuelvió, entre otros, `/websites/fastapi_tiangolo` (benchmark score 76.58, 4.326 snippets, reputación alta).
2. `query-docs({ libraryId: "/websites/fastapi_tiangolo", language: "Python",
    query: "How to declare a POST endpoint that returns 201 and validates the response with response_model" })`
   devolvió **4.841 caracteres** de documentación, incluido el patrón
   `@app.post("/items/", response_model=Item)` → relevante para el contrato público de C-06.

Relevancia concreta: el patrón `response_model` es el que el `design.md` de C-06 D8 usará para el DTO de
respuesta público (allow-list, sin campos ajenos).

## Qué se descartó

- **Playwright MCP / GitHub MCP / Postgres MCP**: no instalados; sus capacidades no están verificadas en este repo
  y no hacen falta para el TP. Si se usan, hay que repetir este mismo bloque de evidencia.

## Limitaciones y honestidad

- `opencode mcp debug` **no existe** en opencode 2.2.0 (`Unknown subcommand "debug"`; sólo `list`, `add`, `auth`,
  `logout`). El procedimiento vigente es `opencode mcp list`. No se finge una verificación imposible.
- Límite de peticiones anónimas de Context7: **[NO VERIFICADO]** (ver `investigacion.md`).
- Context7 documenta software, no nuestro código: las RN y la spec propias salen de la KB, no del MCP.

## Uso seguro

Nunca se le envían datos de pacientes, PHI ni credenciales: sólo nombres de librerías y consultas de API.
