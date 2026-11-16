# Equipo — Turnos-Odontologia

Trabajo práctico grupal de la Tecnicatura Universitaria en Programación (Metodología I).

| Integrante | GitHub | Alcance principal |
|---|---|---|
| **Martin Escudero** | `MartinEscudero13` | Discovery y knowledge base · fundación y roadmap · **C-01 a C-04** · **C-05 `turnos-anti-solape`** · verificación técnica de la fundación |
| **Lautaro Naranjo** | `lauty-naranjo` | **C-06 `reserva-online-publica`** · integración de la **skill propia `revisor-escenarios-turnos`** y del **MCP Context7** · documentación y evidencias del TP2 |

## Etapas anteriores

`docs/discovery/informe-discovery.md`, `docs/decisiones-skills.md` y `docs/reflexion.md`
documentan la **primera entrega individual de Martin Escudero** y se conservan tal como
fueron entregados. No deben reescribirse para reflejar el trabajo grupal posterior.

## Alcance vigente (actualizado 2026-11-16)

- **C-01 a C-15 y F-01 a F-06**: implementados, verificados y archivados (21 changes; C-15 en alcance parcial).
  - Martin Escudero: fundación C-01 a C-04, C-05 `turnos-anti-solape`, F-01 y verificación técnica.
  - Lautaro Naranjo: C-06 `reserva-online-publica` y la pieza de skill propia + MCP del TP2.
  - C-07 a C-15 y F-02 a F-06 se cerraron en la fase posterior al TP2, con el mismo flujo SDD.
- **UI interna completa** (F-06): agenda, pacientes, clínica, caja, señas, WhatsApp, obras sociales, calendario y configuración.
- **C-13**: cerrado con **Twilio WhatsApp Sandbox**; producción requiere número propio y plantillas aprobadas.
- **Deudas declaradas**: persistencia SQL real de los dominios demo, WhatsApp de producción, superadmin y KPI de ocupación.
  Detalle en [`README.md` § Límites declarados](README.md#límites-declarados-del-alcance).
- **Guía de continuación para Lautaro**: [`docs/equipo/guia-lautaro.md`](docs/equipo/guia-lautaro.md).

## Autoría de commits

La configuración local de Git de este checkout usa una identidad genérica
(`turnos-odontologia <turnos-odontologia@local>`). Para que GitHub asocie los commits a
cada integrante, cada uno debe configurar su nombre y email de GitHub antes de commitear.
No se reescribió el historial existente.
