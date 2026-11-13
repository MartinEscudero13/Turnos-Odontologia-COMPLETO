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

## Alcance vigente (actualizado 2026-11-13)

- **C-01 a C-11, F-01 y F-02**: implementados, verificados y archivados (13 changes).
  - Martin Escudero: fundación C-01 a C-04, C-05 `turnos-anti-solape` y verificación técnica de la base.
  - Lautaro Naranjo: C-06 `reserva-online-publica` y la pieza de skill propia + MCP del TP2.
  - C-07 a C-11 se cerraron en la fase posterior al TP2, con el mismo flujo SDD.
- **Pendientes del roadmap**:
  - **C-12 `obras-sociales-liquidacion`** — sin empezar.
  - **C-13 `whatsapp-recordatorios`** — bloqueado por PO-03 (no hay proveedor/BSP definido).
  - **C-14 `google-calendar-sync`** — sin empezar.
  - **C-15 `admin-plataforma-exportacion`** — sin empezar.
- **Deudas declaradas**: UI de C-09/C-10/C-11 diferida a `C-09-UI`, `C-10-UI` y `C-11-UI` (changes sin crear),
  y montaje de los routers de C-05…C-11 en `create_app` pendiente. Detalle en
  [`README.md` § Límites declarados](README.md#límites-declarados-del-alcance).
- **Guía de continuación para Lautaro**: [`docs/equipo/guia-lautaro.md`](docs/equipo/guia-lautaro.md).

## Autoría de commits

La configuración local de Git de este checkout usa una identidad genérica
(`turnos-odontologia <turnos-odontologia@local>`). Para que GitHub asocie los commits a
cada integrante, cada uno debe configurar su nombre y email de GitHub antes de commitear.
No se reescribió el historial existente.
