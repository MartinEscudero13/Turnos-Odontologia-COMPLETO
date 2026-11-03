# Ficha de investigación — MCP (Model Context Protocol)

**Proyecto**: Turnos-Odontologia · **Alcance**: integración MCP del TP «skill propia + MCP» · **Fecha**: 03/11/2026
**Stack sobre el que se decide**: FastAPI 0.115.0 · SQLAlchemy 2.0.35 · Pydantic 2.13.4 · Alembic 1.19.1 · PostgreSQL 15+ (`backend/requirements.txt`).

---

## 1. Qué es MCP

MCP es un estándar abierto para conectar aplicaciones de IA con sistemas externos: fuentes de datos, herramientas y flujos de trabajo. El cliente (opencode, en este repo) se conecta a un **servidor MCP**, descubre las herramientas que ese servidor expone y las ofrece al agente como tools normales. El transporte puede ser remoto (HTTP) o local (proceso hijo por stdio).

La consecuencia práctica: una capacidad nueva (leer documentación, consultar un servicio, manejar un navegador) se agrega **sin escribir código en el repo**, solo registrando el servidor en la configuración del cliente.

## 2. Skill vs. MCP

| | Skill | Servidor MCP |
|---|---|---|
| Qué es | Instrucciones y workflow en `SKILL.md` + recursos de apoyo | Endpoint o proceso que expone herramientas, prompts y recursos |
| Dónde vive | En el repo (`.opencode/skills/<nombre>/`) o instalada global | Fuera del repo (remoto) o como proceso local |
| Quién hace el trabajo | El agente, siguiendo el procedimiento escrito | El servidor; el agente solo invoca sus tools |
| Se versiona | Sí, junto con el código | No: se versiona solo el **ejemplo** de configuración |
| Ejemplo en este proyecto | Las skills del registry mapeadas en `AGENTS.md` (p. ej. `supabase-postgres-best-practices`) | Context7 (documentación de librerías) |

Un MCP no reemplaza una skill: Context7 trae documentación, pero no sabe qué reglas de negocio (RN-XX) ni qué change corresponde. Eso sigue estando en `knowledge-base/` y en las skills.

## 3. Por qué Context7 para este stack

Context7 indexa documentación de librerías y la sirve bajo demanda con dos herramientas: `resolve-library-id` (nombre → ID) y `query-docs` (fragmentos y ejemplos para un ID). Verificado el 03/11/2026 contra el servidor real: las cinco librerías del stack resuelven.

| Librería del stack | ID que devuelve Context7 | Para qué la usaríamos |
|---|---|---|
| FastAPI | `/websites/fastapi_tiangolo` | `Depends`, `BackgroundTasks`, manejo de errores HTTP en `/api/turnos` |
| SQLAlchemy 2.0 | `/sqlalchemy/sqlalchemy` | sesiones, `Session.begin()`, `select()`, expiración y rollback |
| Pydantic v2 | `/pydantic/pydantic` | `field_validator`, `model_config`, modos strict en el borde API |
| Alembic | `/websites/alembic_sqlalchemy` | `op.create_table`, `op.execute` para EXCLUDE/RLS, `downgrade` |
| PostgreSQL 15 | `/websites/postgresql` | constraint de exclusión, RLS, índices parciales |

Ventaja concreta: el `design.md` del próximo change puede citar comportamiento actual de la librería en vez de la memoria del modelo, que está congelada. Además, para Pydantic el índice lista la versión `v2.13.4` —el pin exacto del repo—, así que se puede pedir documentación de esa versión en lugar de la última.

## 4. Alternativas evaluadas

| Opción | Qué aportaría | Por qué no se eligió |
|---|---|---|
| **Context7** | Documentación de librerías dentro del contexto | **Elegida**: responde el insumo que falta al escribir `design.md`/specs, sin permisos peligrosos |
| Playwright MCP | Automatizar un navegador real (clicks, formularios, snapshots) | Todavía no hay frontend implementado en el repo (C-05 es backend) y suma un navegador headless al entorno. [NO VERIFICADO] capacidades y requisitos exactos: haría falta leer `playwright.dev/docs/getting-started-mcp` |
| GitHub MCP | Issues, PRs y CI del repo | El flujo del TP no depende de issues y el remoto recién se publica al cierre. [NO VERIFICADO] alcance del servidor oficial: haría falta revisar `github.com/github/github-mcp-server` |
| Postgres MCP | Consultar la base viva desde el agente | Riesgo de PHI y de queries destructivas; además C-05 corre sin Postgres (ver `README.md`). [NO VERIFICADO] si el servidor permite modo solo lectura: haría falta leer su documentación |
| Filesystem MCP | Leer archivos fuera del workspace | Redundante: el agente ya lee el repo; ampliar el perímetro de lectura choca con las reglas de datos y secretos |

## 5. Límites y riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Solo lectura de documentación pública | Bajo | No puede modificar el repo ni la base; no se le pide ejecutar acciones |
| Dependencia de red | Medio | Si el servidor no responde, el trabajo sigue con la KB y el código; el MCP apoya, no bloquea build ni tests |
| Versiones de docs ≠ pin real | Medio | Pedir la versión explícita. Contraejemplo real: SQLAlchemy lista `rel_2_0_55` pero no el pin `2.0.35`; hay que contrastar con el entorno |
| PHI y credenciales | Alto | Nunca enviar datos de pacientes, `.env`, tokens ni dumps; solo nombres de librerías y preguntas técnicas (regla dura de `AGENTS.md`) |
| Límite de peticiones anónimo | Bajo | La conexión funciona sin API key (verificado). [NO VERIFICADO] el número del límite: no está en la página de API keys; haría falta verlo en el dashboard de Context7 |
| Respuesta incompleta o desactualizada | Medio | Toda decisión de dominio sale de `knowledge-base/`; Context7 solo respalda APIs |

## 6. Cómo se verifica que está conectado

```bash
opencode mcp list
# ✓ context7  connected
```

Después, una llamada real: pedir `resolve-library-id` con `FastAPI` y luego `query-docs` sobre `/websites/fastapi_tiangolo`. Si devuelve texto, el servidor está operativo (verificado el 03/11/2026). Si la lista muestra `needs authentication`, se resuelve con `opencode mcp auth context7`.

> En opencode v2.2.0 (la instalada acá) **no existe** `opencode mcp debug`: devuelve `Unknown subcommand "debug"` y `opencode mcp --help` solo lista `list`, `add`, `auth` y `logout` (verificado). [NO VERIFICADO] si otras versiones lo exponen.

## 7. Fuentes

| Fuente | URL |
|---|---|
| Especificación MCP (introducción) | `modelcontextprotocol.io/docs/getting-started/intro` |
| Context7 — clientes y herramientas | `context7.com/docs/resources/all-clients` |
| Context7 — API keys | `context7.com/docs/howto/api-keys` |
| opencode — MCP servers | `opencode.ai/v2/docs/mcp-servers` |
| opencode — configuración y precedencia | `opencode.ai/v2/docs/config` |

**No verificado en esta ficha**: límite numérico anónimo de Context7; capacidades de Playwright, GitHub y Postgres MCP (se compararon por propósito, no se instalaron); disponibilidad de `opencode mcp debug` en versiones distintas de la 2.2.0. Ninguna de esas ausencias cambia la decisión: Context7 es el único que cubre la necesidad detectada sin permisos sobre datos ni infraestructura.
