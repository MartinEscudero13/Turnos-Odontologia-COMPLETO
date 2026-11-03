# TP «skill propia + MCP» — carpeta `docs/skills-mcp/`

Índice de los artefactos de la parte MCP del trabajo práctico. El detalle de uso está en la sección
[«MCP: Context7»](../../README.md#mcp-context7) del README principal.

| Archivo / carpeta | Qué es | Estado |
|---|---|---|
| [`investigacion.md`](investigacion.md) | Ficha de investigación (≤2 páginas): qué es MCP, skill vs. MCP, por qué Context7 para este stack, alternativas descartadas, límites/riesgos y cómo se verifica la conexión | ✅ listo |
| [`aplicacion.md`](aplicacion.md) | Informe de aplicación: qué se hizo con la skill y el MCP, archivos tocados, antes/después, revisión crítica y limitaciones | ✅ listo |
| [`mcp.json.example`](mcp.json.example) | Fragmento de configuración del servidor `context7` listo para copiar al `opencode.json` del cliente. Sin token, sin credenciales, sin datos de entorno | ✅ listo |
| [`vendor/skill-creator/`](vendor/skill-creator/) | Copia versionada de la skill creadora (Apache-2.0, incluye `LICENSE.txt`) como referencia reproducible. No se modifica; la skill se instala fuera del repo | ✅ listo |
| [`evidencias/`](evidencias/) | `01` skill creadora (validación estructural), `02` descubrimiento en sesión limpia, `03` MCP (conexión + llamada real), `04` revisión crítica antes/después, y el snapshot de la spec previa a la revisión | ✅ listo |

## Notas

- **La configuración viva no está en el repo**: vive en `~/.config/opencode/opencode.json` (en Windows,
  `C:\Users\<usuario>\.config\opencode\opencode.json`). Este repo versiona únicamente el **ejemplo**.
- **Sin secretos ni PHI**: ningún archivo de esta carpeta contiene tokens, API keys, URLs con credenciales
  ni nombres o teléfonos de pacientes. Si en algún momento se usa una API key de Context7, va en `.env`
  (nunca al repo).
- **No es una skill**: Context7 es una integración MCP; no se registra en el skill registry ni se carga con
  la herramienta `skill`.
- **C-06** sigue en estado `[ ]` (**preparado, no implementado**); ver
  `openspec/changes/c-06-reserva-online-publica/`.
