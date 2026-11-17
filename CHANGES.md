# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **Turnos-Odontologia** (SaaS multi-tenant argentino: agenda odontológica + reserva online + WhatsApp + Mercado Pago + obras sociales).
> Cada change es atómico: un agente puede implementarlo en una sesión (~4-6 horas).
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**

## Progreso al 2026-11-17

| | |
|---|---|
| Archivados | **23** — C-01 … C-17 y F-01 … F-06 |
| Pendientes | Ninguno bloqueante; video de entrega y validación real de WhatsApp (Twilio o Meta) |
| Migraciones | 001 → 012 aplicadas y reversibles contra PostgreSQL real |
| Suite | 837 passed + 53 skipped local · 890 passed + 0 skipped con `C02_DATABASE_URL` |
| Frontend | SPA interno C-05…C-17 + landing pública F-02 · 39 tests, lint/typecheck/build |

Los routers de C-05…C-16 están montados en `create_app` sobre adaptadores en memoria; la deuda de
integración es la persistencia SQL de esos dominios, no el montaje.

---

## Cómo usar este documento

1. Identificar el change a implementar (verificar que sus dependencias están en `openspec/changes/archive/`).
2. Leer los docs de la knowledge-base indicados en "Leer antes".
3. Ejecutar `/opsx:propose <nombre-del-change>`.
4. Al terminar el change, archivarlo con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en este archivo.

---

## Árbol de dependencias

```
C-01 foundation-setup
  └── C-02 core-models-multitenant
        └── C-03 auth-rbac-auditoria               ← desbloquea TODO lo demás
              └── C-04 catalogos-pacientes-base
                    │
                    ├── C-05 turnos-anti-solape    ← corazón del sistema
                    │     ├── C-06 reserva-online-publica
                    │     │     └── C-07 lista-espera-auto-oferta
                    │     │           ├── C-11 senas-mercadopago   ← + C-10
                    │     │           └── C-13 whatsapp-recordatorios
                    │     │                 └── C-15 admin-plataforma-exportacion
                    │     ├── C-10 caja-cierre-diario             ← paralelo con C-06
                    │     ├── C-12 obras-sociales-liquidacion     ← paralelo con C-06
                    │     └── C-14 google-calendar-sync           ← paralelo con C-06
                    │
                    └── C-08 ficha-clinica-consentimiento         ← paralelo con C-05
                          └── C-09 odontograma-presupuesto
```

### Paralelismo por fase

> Cada "gate" es un punto de sincronización. Los changes dentro de un grupo pueden ejecutarse en paralelo.

```
GATE 0: ninguna
  → C-01 foundation-setup (solo)

GATE 1: C-01 ✓
  → C-02 core-models-multitenant (solo)

GATE 2: C-02 ✓
  → C-03 auth-rbac-auditoria (solo)

GATE 3: C-03 ✓
  → C-04 catalogos-pacientes-base (solo — todo lo demás referencia sus entidades)

GATE 4: C-04 ✓                        ← PRIMER FORK (2 ramas)
  → C-05 turnos-anti-solape           [Agente A — Backend Core]
  → C-08 ficha-clinica-consentimiento [Agente B — Backend Aux/Clínica]

GATE 5: C-05 ✓ (+ C-08 en curso)       ← SEGUNDO FORK (4 paralelos)
  → C-06 reserva-online-publica       [Agente A — depende C-05]
  → C-10 caja-cierre-diario           [Agente B — depende C-05]
  → C-12 obras-sociales-liquidacion   [Agente C — depende C-04 + C-05]
  → C-14 google-calendar-sync         [Agente C — si C-12 ✓, depende solo C-05]
  → C-09 odontograma-presupuesto      [Agente B — si C-08 ✓, depende C-08]

GATE 6: C-06 ✓
  → C-07 lista-espera-auto-oferta     [Agente A — depende C-05 + C-06]

GATE 7: C-07 + C-10 ✓                 ← TERCER FORK (2 paralelos)
  → C-11 senas-mercadopago            [Agente A — depende C-05 + C-07 + C-10]
  → C-13 whatsapp-recordatorios       [Agente B — depende C-05 + C-07]

GATE 8: C-11 + C-12 + C-13 ✓
  → C-15 admin-plataforma-exportacion (solo — cierra el sistema)
```

### Camino crítico (8 changes — mínimo irreducible)

```
C-01 → C-02 → C-03 → C-04 → C-05 → C-06 → C-10 → C-15
```

> `C-11` (señas Mercado Pago) es el último alternativo para producción con pagos online (*): `… → C-07 → C-11*`.
> No incluye `C-13`/`C-14` (integraciones al final, regla 6) ni `C-09` (clínica profunda) ni refactors visuales.

### Plan óptimo con 3 agentes

```
Paso │ Agente A (Backend Core)      │ Agente B (Backend Aux)            │ Agente C (Frontend/Integraciones)
─────┼──────────────────────────────┼───────────────────────────────────┼────────────────────────────────────
  1  │ C-01 foundation-setup        │ —                                 │ —
  2  │ C-02 core-models-multitenant │ —                                 │ —
  3  │ C-03 auth-rbac-auditoria     │ —                                 │ —
  4  │ C-04 catalogos-pacientes     │ —                                 │ —
  5  │ C-05 turnos-anti-solape      │ C-08 ficha-clinica                │ —
  6  │ C-06 reserva-online          │ C-10 caja-cierre                  │ C-12 obras-sociales
  7  │ C-07 lista-espera            │ C-09 odontograma-presupuesto      │ C-14 google-calendar-sync
  8  │ C-11 senas-mercadopago       │ C-13 whatsapp-recordatorios       │ —
  9  │ C-15 admin-plataforma        │ —                                 │ —
```

---

## FASE 0 — Cimientos

### [C-01] `foundation-setup`
- **Estado**: `[x]` completado (2026-11-03; verificable y testeable; 114 tests, ruff/mypy verdes, Compose y DB smoke, `openspec validate c-01-foundation-setup --strict` en verde) + archivado en `openspec/changes/archive/2026-11-03-c-01-foundation-setup/`
- **Verificación**: [`docs/foundation/verification-report.md`](docs/foundation/verification-report.md) — frontend, backend, migraciones Alembic, Compose, secretos y smoke test.
- **Nota**: migraciones 001/002 son placeholders de ordenamiento; su DDL corresponde a C-02/C-04.
- **Scope**: Scaffolding desacoplado backend + frontend + infraestructura base (US transversales, DD-01)
  - `backend/` FastAPI: `app/routers|models|schemas|core|workers`, SQLAlchemy + Alembic inicializados, `GET /api/health`
  - `frontend/` React + TS + Vite (`src/`), `docker-compose.yml` (api + web + db PostgreSQL 15 + redis)
  - Python 3.12+, React 18+, `.env.example` con `DATABASE_URL, REDIS_URL, JWT_SECRET, MP_*, WA_*, GCAL_*, APP_URL, RESERVA_TTL_H, SENA_TTL_H, CANCEL_ANTICIPACION_H`
  - Docker Compose + CI paralela (lint + typecheck + tests)
  - `backend/app/core` con settings, logger estructurado (sin PHI), db client, exceptions, schemas Pydantic base
- **Dependencias**: ninguna
- **Governance**: BAJO
- **Leer antes**:
  - `knowledge-base/01_vision_y_objetivos.md` §Alcance v1.0
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-01

---

### [C-02] `core-models-multitenant`
- **Estado**: `[x]` completado (2026-11-03; 130 tests, RLS real con rol no-owner, migración 001 upgrade/downgrade/re-upgrade, seed idempotente, ruff/mypy verdes) + archivado en `openspec/changes/archive/2026-11-03-c-02-core-models-multitenant/`
- **Verificación**: [`docs/foundation/verification-c02.md`](docs/foundation/verification-c02.md)
- **Nota**: 002 sigue como placeholder para C-04; el catálogo de sillón/prestaciones se materializa allí desde los parámetros del seed.
- **Scope**: Núcleo multi-tenant + RLS + seed de tenant nuevo (base de RN-AG-05, RN-AU-02)
  - Modelos: `Tenant(id, nombre, slug unique, plan, activo)`, `Usuario(tenant_id, email, password_hash, rol enum ADMIN/RECEPCION/ODONTOLOGO, two_factor, activo)` con `UNIQUE(tenant_id, email)`
  - Tabla `auditoria` append-only `(tenant_id, actor_id, accion, entidad, entidad_id, antes/después jsonb, at)` + revoke UPDATE/DELETE
  - Helper `tenant_id` NOT NULL + política RLS `tenant_id = current_setting('app.tenant_id')` reutilizable por todas las migraciones futuras
  - Migración 001: tenants, usuarios, auditoria + RLS
  - Seed por tenant: roles, estados de turno, medios de pago, 1 sillón ("Sillón 1"), prestaciones base (Consulta, Limpieza), plantillas WA, parámetros (anticipación 24 h, política de seña)
  - Tests: fuga cross-tenant (query sin tenant no ve datos ajenos), seed idempotente
- **Dependencias**: C-01
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §tenants, §usuarios, §mensajes_wa / recordatorios / auditoria
  - `knowledge-base/04_modelo_de_datos.md` §Seed data inicial
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-05, §RN-AU-02

---

## FASE 1 — Identidad y auditoría

### [C-03] `auth-rbac-auditoria`
- **Estado**: `[x]` completado (2026-11-03; 152 tests, login/refresh/logout/me, 2FA, RBAC y RLS de refresh tokens verificados) + archivado en `openspec/changes/archive/2026-11-03-c-03-auth-rbac-auditoria/`
- **Verificación**: [`docs/foundation/verification-c03.md`](docs/foundation/verification-c03.md)
- **Scope**: Autenticación + RBAC (tenant, rol) + auditoría enforced en API (US-051 parcial: CA-1, CA-2; RN-AU-01/02/05)
  - `POST /api/auth/login` — Argon2/bcrypt, JWT access corto + refresh rotado, rate limiting 5/60s por IP+email
  - `POST /api/auth/refresh`, `POST /api/auth/logout`, `GET /api/auth/me`; 2FA exigible para roles internos
  - Dependencia FastAPI: exige `(tenant_id, rol)` según matriz `03_actores_y_roles.md` + RLS como segunda barrera
  - `backend/app/core/audit`: helper append-only usado por agenda/caja/señas/presupuestos/accesos (quién/qué/cuándo/antes/después)
  - Teléfono E.164, montos en centavos, validación Pydantic en borde API
  - Tests: login/refresh/logout, matriz RBAC por rol, fuga cross-tenant por rol, audit contiene antes/después
- **Dependencias**: C-02
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-01, §RN-AU-02, §RN-AU-05
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/06_funcionalidades.md` §US-051

---

## FASE 2 — Catálogos y agenda

> `C-05` y `C-08` pueden proponerse en paralelo tras `C-04`. `C-04` debe archivarse antes que cualquier otro change de esta fase.

### [C-04] `catalogos-pacientes-base`
- **Estado**: `[x]` completado (2026-11-03; 159 tests, RLS real de catálogo, migración 002 reversible, seed idempotente) + archivado en `openspec/changes/archive/2026-11-03-c-04-catalogos-pacientes-base/`
- **Verificación**: [`docs/foundation/verification-c04.md`](docs/foundation/verification-c04.md)
- **Scope**: Catálogos del tenant + pacientes base que todo el dominio referencia (US-003; RN-AG-01/04/06, RN-RE-05)
  - Modelos: `Profesional(usuario_id?, nombre, especialidad, matricula?, color_agenda, activo)`, `Sillon(nombre, activo)`, `Prestacion(nombre, duracion_min, precio_base, requiere_sena, monto_sena?, activa)`, `ProfesionalPrestacion` (N—N habilidad), `HorarioSemanal(dia, desde, hasta)`, `Bloqueo(desde, hasta, motivo)`
  - Modelo `Paciente(nombre, dni_cifrado?, telefono E.164, email?, obra_social_id?, nro_afiliado?, consentimiento_ok)` con `UNIQUE(tenant_id, dni)` e índice `(tenant_id, telefono)`; vinculación por teléfono existente
  - Endpoints CRUD: `/api/profesionales`, `/api/sillones`, `/api/prestaciones`, `/api/pacientes` (base, sin ficha clínica)
  - Regla: duración variable por prestación; intersección horario profesional × consultorio; bloqueos restan disponibilidad
  - Migración 002: todas las tablas del scope + RLS
  - Tests: CRUD por rol, aislamiento multi-tenant, teléfono duplicado vincula ficha
- **Dependencias**: C-03
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §profesionales, §sillones, §prestaciones, §pacientes
  - `knowledge-base/06_funcionalidades.md` §US-003
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-01, §RN-AG-04, §RN-AG-06, §RN-RE-05
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos

---

### [C-05] `turnos-anti-solape`
- **Estado**: `[x]` completado (2026-09-30, apply `1193b77` — tests 79/79 en verde) + **reimplementado en Python el 2026-10-02** (spec intacto; suite 104/104 en verde con `py -m pytest tests/ -q`; implementación TS eliminada del árbol con `git rm`, conservada en historia git). Detalle: `openspec/changes/archive/2026-10-01-c-05-turnos-anti-solape/reimplementacion-python.md`.
- **Scope**: Turnos con anti-solapamiento real en DB + agenda día/semana de recepción (US-001, US-002; RN-AG-02/03, RN-GL-01/02)
  - Modelo `Turno(tenant, profesional, sillon, paciente, prestacion, inicio, fin calculado, estado PENDIENTE/CONFIRMADO/PRESENTE/AUSENTE/CANCELADO/REPROGRAMADO, sobreturno=false, origen RECEPCION/ONLINE/LISTA_ESPERA, token_publico?, sena_id?)`
  - Constraints EXCLUDE anti-solape por `(tenant, profesional)` y `(tenant, sillon)` en `[inicio, fin)` con `estado NOT IN (CANCELADO, REPROGRAMADO)` y `sobreturno=false`
  - Endpoints: `CRUD /api/turnos`, `POST /api/turnos/:id/sobreturno` (motivo obligatorio + auditoría), `POST /api/turnos/:id/cancelar|reprogramar`
  - UI SPA `/agenda`: vista día/semana por profesional y sillón, colores por estado, drag&drop con confirmación que revalida solape en servidor, bloqueos ocultan slots; slot tomado → 409 + 3 alternativas
  - Migración 003: turnos + EXCLUDE + índices `(tenant, profesional, inicio)`, `(tenant, sillon, inicio)`, `(tenant, estado)`
  - Tests (rojos primero): solape profesional falla, solape sillón falla, sobreturno exige motivo y audita, concurrencia doble-reserva solo una confirma
- **Dependencias**: C-03, C-04
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §turnos
  - `knowledge-base/06_funcionalidades.md` §US-001, §US-002
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AG-02, §RN-AG-03, §RN-GL-01, §RN-GL-02
  - `knowledge-base/07_flujos_principales.md` §Flujo 4

---

## FASE 3 — Reserva online y lista de espera

### [C-06] `reserva-online-publica`
- **Estado**: `[x]` completado (2026-11-05; 48 tests nuevos, suite 203 passed + 4 skipped, ruff/mypy verdes, `openspec validate --strict` en verde) + archivado en `openspec/changes/archive/2026-11-05-c-06-reserva-online-publica/`
- **Scope**: Reserva por link sin login + cancelar/reprogramar con anticipación (US-010, US-011; RN-RE-01/02/03/05, RN-GL-02)
  - `GET /api/publico/{tokenTenant}/disponibilidad?prestacion=&profesional=&desde=` — slots reales servidor-side (profesional × sillón × duración − bloqueos), scoped por token de tenant
  - `POST /api/publico/{tokenTenant}/reservas` — crea turno PENDIENTE + token público; identificación liviana nombre + teléfono (DD-06), rate-limit + captcha/OTP liviano anti-spam
  - Rutas públicas `/r/:tokenTenant` (landing reserva, mobile-first) con confirmación inmediata; `cancelar|reprogramar` valida anticipación mínima configurable (default 24 h, `CANCEL_ANTICIPACION_H`); debajo del umbral deriva a recepción auditada
  - Caso slot tomado entre pasos → 409 + 3 alternativas
  - Tests: slots excluyen bloqueos/solapes, reserva vincula paciente por teléfono, anticipación enforced, rate-limit bloquea abuso
- **Dependencias**: C-05
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-010, §US-011
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/05_reglas_de_negocio.md` §RN-RE-01, §RN-RE-02, §RN-RE-03, §RN-RE-05
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-06

---

### [C-07] `lista-espera-auto-oferta`
- **Estado**: `[x]` completado (2026-11-05; 42 tests nuevos, suite 250 passed + 4 skipped, ruff/mypy verdes, `openspec validate --strict` en verde) + archivado en `openspec/changes/archive/2026-11-05-c-07-lista-espera-auto-oferta/`
- **Scope**: Lista de espera con auto-oferta de huecos liberados y expiración (US-012; RN-RE-04)
  - Modelos: `ListaEspera(tenant, paciente, prestacion, profesional_pref?, ventana_horaria?, estado PENDIENTE/OFRECIDO/CONVERTIDO/VENCIDO)` + `Ofertas(hueco_turno_id?, expira_at, estado)`
  - Endpoints: `/api/lista-espera` (alta, baja, listar compatible) + worker auto-oferta: hueco liberado se ofrece a lista compatible ordenada (prioridad/fecha) ANTES de publicarse general
  - Oferta con expiración (ej. 2 h): primer aceptante ocupa el hueco (revalida solape C-05); si vence pasa al siguiente; si nadie acepta → slot público
  - Cancelación por cualquier canal (recepción, link, WA) dispara el worker
  - Migración 005: lista_espera + ofertas + RLS
  - Tests: orden de oferta, expiración rota al siguiente, aceptante ocupa hueco, sin lista → slot público
- **Dependencias**: C-05, C-06
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §lista_espera (+ ofertas)
  - `knowledge-base/06_funcionalidades.md` §US-012
  - `knowledge-base/05_reglas_de_negocio.md` §RN-RE-04
  - `knowledge-base/07_flujos_principales.md` §Flujo 4

---

## FASE 4 — Clínica y presupuesto

> `C-08` corre en paralelo con `C-05` tras `C-04`. `C-09` requiere `C-08` archivado.

### [C-08] `ficha-clinica-consentimiento`
- **Estado**: `[x]` completado (2026-11-06; 46 tests nuevos, suite 296 passed + 4 skipped, ruff/mypy verdes, `openspec validate --strict` en verde) + archivado en `openspec/changes/archive/2026-11-06-c-08-ficha-clinica-consentimiento/`
- **Scope**: Ficha clínica mínima con consentimiento previo y evoluciones inmutables (US-030; RN-CL-03/04, RN-AU-03)
  - Modelos: `Ficha(paciente 1—1)`, `Evolucion(tenant, paciente, profesional, fecha, texto, firma_hash?)` append-only (corrección = nueva evolución), `Adjunto(ficha, tipo Rx/foto, storage ref)`, `Consentimiento(paciente, timestamp, canal móvil)`
  - Endpoints: `/api/pacientes/:id/ficha`, `/api/evoluciones`, `/api/adjuntos`, `/api/consentimientos` (firma en móvil)
  - Regla: sin consentimiento firmado → bloquea clínica, permite solo agenda; nada de PHI en logs ni mensajes
  - Migración 006: fichas, evoluciones, adjuntos, consentimientos + RLS
  - Tests: evolución no editable (UPDATE rechazado), sin consentimiento bloquea POST clínico pero no agenda, adjunto scoped por tenant
- **Dependencias**: C-04
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §odontograma_hallazgos / evoluciones / presupuestos
  - `knowledge-base/06_funcionalidades.md` §US-030
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-03, §RN-CL-04, §RN-AU-03
  - `knowledge-base/07_flujos_principales.md` §Flujo 3

---

### [C-09] `odontograma-presupuesto`
- **Estado**: `[x]` completado (2026-11-12; backend + contratos + migración 007 + tests; 416 passed + 10 skipped en suite local, 426 passed + 0 skipped con PostgreSQL real `C02_DATABASE_URL`, `openspec validate c-09-odontograma-presupuesto --strict` en verde) + archivado en `openspec/changes/archive/2026-11-12-c-09-odontograma-presupuesto/`
- **Nota UI**: la UI del odontograma/presupuesto quedó **diferida a `C-09-UI`** (tareas `D.1–D.9`); C-09 v1 no toca `frontend/` (verificado por el test de gate 10.5).
- **Migración**: `007_odontograma_presupuesto` **aplicada** (`odontograma_hallazgos`, `presupuestos`, `presupuesto_lineas`, `aceptaciones`, RLS forzada fail-closed, CHECK de grilla FDI y suma de línea).
- **Scope**: Odontograma FDI con historial → presupuesto por pieza con aceptación parcial e imputación (US-031, US-032; RN-CL-01/02, RN-OS-01)
  - Modelo `OdontogramaHallazgo(tenant, paciente, pieza_fdi 11–48, superficie?, hallazgo, fecha, profesional, resuelto bool)` con historial por pieza
  - Modelos: `Presupuesto(tenant, paciente, estado BORRADOR/VIGENTE/PARCIAL/ACEPTADO/VENCIDO)` + `PresupuestoLinea(pieza_fdi?, prestacion, monto, cobertura_os, a_cargo_paciente)` + `Aceptacion(linea, acepta, fecha, canal)`
  - UI odontograma FDI + botón "derivar a presupuesto" (hallazgo → línea en 1 clic); sistema aplica cobertura OS si existe, si no 100% particular visible
  - Endpoints: `/api/odontograma`, `/api/presupuestos`, `POST /api/presupuestos/:id/aceptar` (parcial/total); lo aceptado genera turnos (C-05) e imputación a caja (C-10); lo pendiente → recupero/recall
  - Migración 007: odontograma_hallazgos, presupuestos, líneas, aceptaciones + RLS
  - Tests: FDI fuera de 11–48 rechazado, aceptación parcial imputa solo líneas aceptadas, transacción hallazgo+presupuesto atómica
- **Dependencias**: C-04, C-08
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §odontograma_hallazgos / evoluciones / presupuestos
  - `knowledge-base/06_funcionalidades.md` §US-031, §US-032
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CL-01, §RN-CL-02, §RN-OS-01
  - `knowledge-base/07_flujos_principales.md` §Flujo 3

---

## FASE 5 — Caja, señas y obras sociales

> `C-10`, `C-12` y `C-14` pueden proponerse en paralelo tras `C-05`. `C-11` requiere `C-07` + `C-10` archivados.

### [C-10] `caja-cierre-diario`
- **Estado**: `[x]` completado (2026-11-13; backend + contratos + migración 008 + delta specs alineadas; 552 passed + 27 skipped en suite local, 579 passed + 0 skipped con PostgreSQL real `C02_DATABASE_URL`, `mypy` (84 archivos) / `ruff check .` / `openspec validate --all --strict` en verde) + archivado en `openspec/changes/archive/2026-11-13-c-10-caja-cierre-diario/`
  - **Migración 008 aplicada y reversible**: `movimientos_caja`, `cierres_diarios`, `cobros_pendientes`, `ajustes_post_cierre`, `cuentas_por_cobrar_os` (RLS forzada fail-closed), verificada contra PostgreSQL real.
  - **Diferido a `C-10-UI`**: la UI SPA `/caja` (tasks §12 `D.1–D.8`) no se implementó; C-10 no declara requirements de UI.
  - **Limitación declarada**: la prohibición de escribir en un día cerrado es de aplicación (servicio + `pg_advisory_xact_lock` por `(tenant, fecha)`), **no** un trigger de base que bloquee un `INSERT` SQL directo; sólo `UPDATE`/`DELETE` de cierres y movimientos están bloqueados en la base.
- **Scope**: Caja multi-medio con cierre diario obligatorio y reportes base (US-040; RN-CJ-01/02/03)
  - Modelos: `MovimientoCaja(tenant, fecha, medio EFECTIVO/TRANSFERENCIA/MP/OS, monto centavos, tipo INGRESO/EGRESO, turno_id?, usuario_id, anulado + motivo)`, `CierreDiario UNIQUE(tenant, fecha)` con totales por medio, diferencia, responsable, cerrado_at
  - Endpoints: `GET /api/caja/movimientos?fecha=`, `POST /api/caja/movimientos`, `POST /api/caja/cierre` (diferencia 0 o motivo con observación auditable), anulación con motivo + movimiento compensatorio (nunca borrado; post-cierre exige compensatorio)
  - UI SPA `/caja` (**diferida a `C-10-UI`**): movimientos por medio, carga de efectivo real vs sistema, reportes base
  - Migración 008: movimientos_caja, cierres_diarios, cobros_pendientes, ajustes_post_cierre, cuentas_por_cobrar_os + RLS
  - Tests: cierre con diferencia exige motivo, día sin responsable no cierra, anulación post-cierre crea compensatorio sin editar cierre
- **Dependencias**: C-03, C-05
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §senas / pagos_mp / movimientos / cierres
  - `knowledge-base/06_funcionalidades.md` §US-040
  - `knowledge-base/05_reglas_de_negocio.md` §RN-CJ-01, §RN-CJ-02, §RN-CJ-03
  - `knowledge-base/07_flujos_principales.md` §Flujo 5

---

### [C-11] `senas-mercadopago`
- **Estado**: `[x]` completado (2026-11-13; backend + contratos + migración 009 + delta specs alineadas; 678 passed + 42 skipped en suite local, 720 passed + 0 skipped con PostgreSQL real `C02_DATABASE_URL`, `mypy` (101 archivos) / `ruff check .` / `openspec validate --all --strict` en verde) + archivado en `openspec/changes/archive/2026-11-13-c-11-senas-mercadopago/`
  - **Migración 009 aplicada y reversible**: `senas`, `pagos_mp` + `prestaciones.sena_modo`/`sena_valor` (RLS forzada fail-closed, `mp_payment_id` y `token_hash` únicos globales), verificada contra PostgreSQL real.
  - **Diferido a `C-11-UI`**: la página `/pagar/:tokenSena` y la vista de la seña en agenda (tasks §12); C-11 no declara requirements de UI.
  - **Limitaciones declaradas**: (1) el `INGRESO` de la seña queda con `tramo=NULL` porque `ServicioCaja.registrar_movimiento` no expone ese parámetro — corregirlo es un cambio en C-10; (2) el access log del servidor HTTP puede registrar el token público aunque el log de la aplicación lo redacta; (3) la devolución es un estado contable: el reintegro en Mercado Pago es manual y requiere un responsable operativo asignado.
- **Scope**: Seña online atada a reserva con liberación automática y webhook idempotente (US-041; RN-SE-01/02/03/04/05) — ✅ PO-01 resuelta: default por tenant + override opcional por prestación (`docs/decisiones-po.md`); quedan provisionales monto/% y anticipación de cancelación (24 h)
  - Modelos: `Sena(tenant, turno unique?, monto, estado PENDIENTE/ACREDITADA/LIBERADA/APLICADA/DEVUELTA, mp_preference_id, expira_at SENA_TTL_H)` + `PagoMP(mp_payment_id unique, sena, monto, estado, raw_json, received_at)`
  - Flujo: prestación con `requiere_sena` → seña PENDIENTE + preferencia MP → `/pagar/:tokenSena` → webhook `POST /api/webhooks/mercadopago` idempotente (duplicado → 200 sin efecto) → ACREDITADA → turno CONFIRMADO; expira sin pago → turno liberado + dispara auto-oferta (C-07)
  - Política de cancelación visible al reservar; seña visible en agenda con estado; MP caído → reserva PENDIENTE + reintento/backoff (RN-IN-03)
  - Migración 009: senas, pagos_mp + RLS
  - Tests: webhook duplicado no duplica, expiración libera turno y ofrece a lista, seña se aplica al cobro (C-10)
- **Dependencias**: C-05, C-07, C-10
- **Governance**: CRITICO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §senas / pagos_mp / movimientos / cierres
  - `knowledge-base/06_funcionalidades.md` §US-041
  - `knowledge-base/05_reglas_de_negocio.md` §RN-SE-01 → §RN-SE-05
  - `knowledge-base/07_flujos_principales.md` §Flujo 1
  - `knowledge-base/10_preguntas_abiertas.md` §PO-01 (IN-02)

---

### [C-12] `obras-sociales-liquidacion`
- **Estado**: `[x]` completado (2026-11-15; catálogo de obras sociales, coberturas por OS × prestación, cálculo de tramos con tope, liquidación por período de turnos atendidos, cierre inmutable y export CSV; migración 010 con RLS; adaptador de cobertura para C-09) + archivado en `openspec/changes/archive/2026-11-15-c-12-obras-sociales-liquidacion/`
- **Verificación**: [`docs/foundation/verification-c-12-obras-sociales.md`](docs/foundation/verification-c-12-obras-sociales.md)
- **Límite**: sin validación realtime (PO-04), sin aranceles por OS (PO-08: el monto base es `prestaciones.precio_base`) y sin UI de configuración.
- **Scope**: Cobertura OS configurable por tenant + liquidación presentable (US-042; RN-OS-01/02/03, DD-04)
  - Modelos: `ObraSocial(tenant, nombre, activa)`, `Cobertura(tenant, obra_social, prestacion, porcentaje/monto, tope?)`, `Liquidacion(tenant, obra_social, periodo, estado, total)` + líneas por turno atendido con OS
  - Endpoints: `/api/obras-sociales`, `/api/coberturas`, `/api/liquidaciones` (por período, exportable); UI etiquetada "configurada, no validada en vivo"
  - Seed: 3–5 OS comunes por tenant (nombres, sin aranceles reales); validación realtime SOAP/WS explícitamente fuera (fase 2)
  - Migración 010: obras_sociales, coberturas, liquidaciones + RLS
  - Tests: cobertura OS × prestación calcula a-cargo-paciente, liquidación agrupa solo turnos atendidos del período
- **Dependencias**: C-04, C-05
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §obras_sociales / coberturas / liquidaciones
  - `knowledge-base/06_funcionalidades.md` §US-042
  - `knowledge-base/05_reglas_de_negocio.md` §RN-OS-01, §RN-OS-02, §RN-OS-03
  - `knowledge-base/09_decisiones_y_supuestos.md` §DD-04

---

## FASE 6 — Integraciones

### [C-13] `whatsapp-recordatorios`
- **Estado**: `[x]` completado (2026-11-16; recordatorios, webhook Twilio con firma, respuestas SI/NO, fallback email y recall; migración **012**) + archivado en `openspec/changes/archive/2026-11-16-c-13-whatsapp-recordatorios/`
- **Verificación**: [`docs/foundation/verification-c-13-whatsapp.md`](docs/foundation/verification-c-13-whatsapp.md)
- **Proveedor**: Twilio WhatsApp Sandbox y **Meta WhatsApp Cloud API** (número de prueba) detrás del mismo puerto; `WA_PROVIDER=fake|twilio|meta`. Producción requiere número propio y plantillas aprobadas (PO-03 fase 2).
- **Scope aplicado**:
  - Modelo `mensajes_wa` con estados, canal, intentos, respuesta y `provider_message_id` único.
  - Recordatorios idempotentes por turno+plantilla; programación por endpoint (el cron queda para el worker).
  - Webhook `POST /api/webhooks/whatsapp`: firma Twilio, estados de entrega y respuesta `SI`/`NO`; `NO` dispara C-07.
  - Fallback email (adaptador de log hasta configurar SMTP) y cola de reintentos.
  - Recall sanitario separado del marketing.
- **Límite**: sandbox sólo envía a números unidos y la sesión dura 24 h; no es producción.
- **Dependencias**: C-05, C-07
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-020, §US-021, §US-052
  - `knowledge-base/07_flujos_principales.md` §Flujo 2
  - `knowledge-base/05_reglas_de_negocio.md` §RN-IN-01, §RN-IN-03
  - `knowledge-base/11_integraciones.md` §WhatsApp
  - `knowledge-base/10_preguntas_abiertas.md` §PO-03

---

### [C-14] `google-calendar-sync`
- **Estado**: `[x]` completado (2026-11-15; link OAuth por profesional, push idempotente de turnos, pull de eventos externos como bloqueo informativo, conflicto a favor del sistema, cola con backoff y token revocado sin romper la agenda; migración **011** renumerada mientras C-13 estaba bloqueado) + archivado en `openspec/changes/archive/2026-11-15-c-14-google-calendar-sync/`
- **Verificación**: [`docs/foundation/verification-c-14-google-calendar.md`](docs/foundation/verification-c-14-google-calendar.md)
- **Límite**: OAuth y Google Calendar simulados con adaptador fake; los bloqueos externos no alteran la disponibilidad de C-06 en v1; sin UI ni cron propio.
- **Scope**: Sync bidireccional con Google Calendar por profesional, sistema como fuente de verdad (US-050; RN-IN-02/03)
  - Modelo `CalendarLink(profesional, gcal_calendar_id, oauth_ref, ultima_sync, estado)`; OAuth2 por profesional (`GCAL_CLIENT_ID/SECRET`)
  - Push: turno creado/modificado/cancelado → evento GCal; pull: webhook/polling → evento externo se refleja como bloqueo informativo no-reservable
  - Conflicto: gana el sistema, se re-oferta el hueco (C-07) y se avisa al profesional; token revocado → aviso + agenda interna intacta; GCal caído → cola con reintento
  - Endpoints: `/api/calendar/oauth`, `/api/calendar/webhook`
  - Migración 012: calendar_links + RLS
  - Tests: crear turno pushea evento, evento externo bloquea slot, conflicto lo gana el sistema, token revocado no rompe agenda
- **Dependencias**: C-05
- **Governance**: MEDIO
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` §US-050
  - `knowledge-base/07_flujos_principales.md` §Flujo 6
  - `knowledge-base/05_reglas_de_negocio.md` §RN-IN-02, §RN-IN-03
  - `knowledge-base/11_integraciones.md` §Google Calendar

---

## FASE 7 — Administración y plataforma

### [C-15] `admin-plataforma-exportacion`
- **Estado**: `[x]` completado (2026-11-15 el núcleo; 2026-11-16 se cierran superadmin, respaldo, ocupación y UI vía **C-16**) + archivado en `openspec/changes/archive/2026-11-15-c-15-admin-exportacion/`
- **Verificación**: [`docs/foundation/verification-c-15-admin.md`](docs/foundation/verification-c-15-admin.md)
- **Cierre posterior**: el KPI de ocupación vive en `admin-tenant`; el superadmin cross-tenant y el respaldo se operan con `tools/superadmin.py` y `tools/backup.py` (capability `operacion`). La UI de configuración ya está en el SPA.
- **Scope**: Cierre del sistema: usuarios/config del tenant, exportación 1-clic, respaldo y superadmin (US-051 parcial: CA-3 + resto; RN-AU-04)
  - `/api/tenants/*`: alta/configuración del consultorio (admin tenant + superadmin plataforma sin acceso a PHI salvo intervención auditada)
  - Usuarios del tenant CRUD + config tenant (seña, anticipación cancelación, recordatorios) — UI SPA `/config`
  - `GET /api/exportacion`: CSV/Excel + JSON del tenant en 1 clic; respaldo diario declarado (job + documentación); sin lock-in
  - Reportes/KPIs vara DentalSoft: ocupación, ausentismo, facturación por profesional, % reservas online, huecos reasignados < 2 h
  - Tests: exportación contiene todo el tenant y nada ajeno, superadmin no lee clínica sin auditoría, config del tenant aísla parámetros
- **Dependencias**: C-10, C-12, C-13
- **Governance**: ALTO
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §Actores del sistema
  - `knowledge-base/06_funcionalidades.md` §US-051
  - `knowledge-base/05_reglas_de_negocio.md` §RN-AU-04
  - `knowledge-base/01_vision_y_objetivos.md` §Métricas de éxito
  - `knowledge-base/10_preguntas_abiertas.md` §PO-10

### [C-16] `cierre-operativo`
- **Estado**: `[x]` completado (2026-11-16; transiciones de agenda, acciones de caja y presupuesto, toggles de OS/usuarios, desconexión de calendario, KPI de ocupación, superadmin y respaldo por CLI; sin migración nueva) + archivado en `openspec/changes/archive/2026-11-16-c-16-cierre-operativo/`
- **Verificación**: [`docs/foundation/verification-c-16-cierre-operativo.md`](docs/foundation/verification-c-16-cierre-operativo.md)
- **Scope aplicado**:
  - Agenda: `CONFIRMADO`, `PRESENTE`, `AUSENTE` con auditoría y botones por estado.
  - Presupuesto: aceptar/rechazar; la aceptación imputa el tramo del paciente a caja vía `ImputacionCaja`.
  - Caja: anular con motivo, cobrar pendientes, cierres y reportes por rango.
  - OS / usuarios: activar/desactivar; liquidación con detalle; calendario con desconexión.
  - `ocupacion_pct` en KPIs (minutos ocupados / capacidad semanal).
  - `tools/superadmin.py` y `tools/backup.py` + servicio Compose `backup`.
- **Leer antes**: `knowledge-base/05_reglas_de_negocio.md` (§RN-AG-02, RN-CJ-03, RN-AU-04) y `knowledge-base/08_arquitectura_propuesta.md`.

### [C-17] `proveedor-meta`
- **Estado**: `[x]` completado (2026-11-17; adaptador oficial Meta WhatsApp Cloud API, webhook con `X-Hub-Signature-256`, estados y respuestas por `context.id` o teléfono; sin migración nueva) + archivado en `openspec/changes/archive/2026-11-17-c-17-proveedor-meta/`
- **Verificación**: [`docs/foundation/verification-c-13-whatsapp.md`](docs/foundation/verification-c-13-whatsapp.md)
- **Scope aplicado**:
  - `WA_PROVIDER=meta` con `META_WA_TOKEN`, `META_PHONE_NUMBER_ID`, `META_VERIFY_TOKEN`, `META_APP_SECRET`, `META_API_VERSION`.
  - `GET/POST /api/webhooks/whatsapp/meta` con verificación y firma fail-closed.
  - Aplanado de `statuses`/`messages` y reutilización de `ServicioWhatsApp`.
  - Resolución de respuestas por teléfono; también corrige el webhook de Twilio.
- **Leer antes**: `knowledge-base/11_integraciones.md` §WhatsApp y `knowledge-base/05_reglas_de_negocio.md` §RN-IN-01/03.
---

## Cambios transversales (fuera del roadmap C-01…C-15)

### [F-01] `frontend-visual-foundation`
- **Estado**: `[x]` completado (2026-11-03; sistema visual, router, home, login, shell protegido, 404, skill `visual-turnos`, MCP Figma/Stitch documentado y screenshots 375/768/1440) + archivado en `openspec/changes/archive/2026-11-03-frontend-visual-foundation/`
- **Verificación**: [`docs/design/screenshots/README.md`](docs/design/screenshots/README.md) y [`docs/design/README.md`](docs/design/README.md)
- **Alcance**: fundación visual; las páginas de negocio (agenda, pacientes, reserva, caja, reportes) quedan como changes por página.

### [F-02] `reserva-publica-landing`
- **Estado**: `[x]` completado (2026-11-05; landing pública `/r/:tokenTenant` mobile-first, catálogo público `GET /api/publico/{tokenTenant}/catalogo`, reserva con verificación captcha placeholder, gestión por token, estados 403/404/409/422/429, a11y AA y screenshots 375/768/1440) + archivado en `openspec/changes/archive/2026-11-05-f-02-reserva-publica-landing/`
- **Verificación**: `py -m pytest tests/ -q`, `npm run lint`, `npm run typecheck`, `npm test`, `npm run build` y `openspec validate --strict` en verde; capturas en `openspec/changes/f-02-reserva-publica-landing/mockups/previews/`
- **Alcance**: consume el contrato de C-06 y agrega el enabler backend de catálogo (OQ-F1). Pendiente declarado: proveedor real de captcha, confirmación WA/email (C-13) y wiring SQLAlchemy real del backend (D9 de C-06).
### [F-03] `demo-api-integration`
- **Estado**: `[x]` completado (2026-11-15; C-05/C-06 montados en `create_app`, catálogo demo disponible, flujo público catálogo → disponibilidad → reserva con token verificado por HTTP) + archivado en `openspec/changes/archive/2026-11-15-demo-api-integration/`
- **Verificación**: [`docs/foundation/verification-demo-api.md`](docs/foundation/verification-demo-api.md)
- **Límite**: estado C-05/C-06 en memoria; C-07…C-11 siguen sin montar y la persistencia SQL sigue limitada a auth/catálogos.
### [F-04] `demo-api-dominios`
- **Estado**: `[x]` completado (2026-11-15; C-07 lista de espera, C-10 caja y C-11 señas montados en `create_app` sobre adaptadores en memoria; la reserva pública crea la seña cuando la regla demo la exige; handler global de `TurnoError` para conservar 403/404/409) + archivado en `openspec/changes/archive/2026-11-15-demo-api-dominios/`
- **Verificación**: [`docs/foundation/verification-demo-api-dominios.md`](docs/foundation/verification-demo-api-dominios.md)
- **Límite**: todo el estado de la demo es en memoria y se pierde al reiniciar; C-08/C-09 siguen sin montar; el webhook de Mercado Pago responde `503` porque no hay secreto real.
### [F-05] `demo-api-clinica`
- **Estado**: `[x]` completado (2026-11-15; C-08 ficha clínica y C-09 odontograma/presupuesto montados en `create_app` sobre adaptadores en memoria; consentimiento compartido entre ficha, evolución, hallazgos y líneas clínicas; presupuestos y líneas compartidos entre odontograma y presupuesto) + archivado en `openspec/changes/archive/2026-11-15-demo-api-clinica/`
- **Verificación**: [`docs/foundation/verification-demo-api-clinica.md`](docs/foundation/verification-demo-api-clinica.md)
- **Límite**: estado clínico en memoria; la aceptación de presupuesto no escribe en caja (imputación simulada); sin cobertura de obra social ni UI clínica.
### [F-06] `frontend-interno`
- **Estado**: `[x]` completado (2026-11-15; SPA `/app` con agenda, pacientes, clínica, caja, señas, obras sociales, calendario y configuración; login persistente con credenciales demo; cliente API tipado con actor/JWT; seed demo y servicio `migrate` en Compose) + archivado en `openspec/changes/archive/2026-11-15-frontend-interno/`
- **Verificación**: [`docs/foundation/verification-frontend-interno.md`](docs/foundation/verification-frontend-interno.md)
- **Límite**: C-13 y las acciones operativas se completaron en C-16; la edición avanzada de entidades y la persistencia SQL del camino de la API siguen declaradas como deuda.
