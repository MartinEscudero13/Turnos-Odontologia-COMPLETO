# Design — C-06 `reserva-online-publica`

> Estado: **preparado, no implementado**. Este documento decide el HOW; el QUÉ
> está en `specs/reserva-publica/spec.md` y el porqué en `proposal.md`.

## UI Mockups

- Decision: no (no UI) — C-06 es backend-only; la landing `/r/:tokenTenant` es un follow-up de frontend fuera del scope de este change (Non-Goals).
- Fecha: 2026-11-05

## Context

Stack real del repo: Python + FastAPI + SQLAlchemy 2 + Alembic + PostgreSQL 15
multi-tenant con RLS (`knowledge-base/09_decisiones_y_supuestos.md:5-10`, DD-01).
Lo implementado es C-05 (`backend/app/turnos/`, migración 003) con dominio puro
en memoria, borde Pydantic y actor por headers. C-03 (auth/RBAC/auditoría) y
C-04 (catálogos/pacientes, `backend/app/models/catalogos.py`) ya están
implementados y archivados, por lo que sus modelos/servicios son el destino real
de los puertos de C-06: el wiring SQLAlchemy de `CatalogoPort`/`PacientePort` ya
no está bloqueado.

Reglas duras aplicables (`AGENTS.md`): anti-solape sólo en DB (R3) con paridad en
el servicio, TDD rojo-primero en concurrencia/idempotencia/ventana (R4), sin
tests tautológicos (R5), sin PHI en logs, datos ficticios (R1), secretos en
`.env` (R2), sin commits sin pedido (R6), tipado estricto (R7).

## Goals / Non-Goals

**Goals:** disponibilidad pública indistinguible del motor de C-05; reserva sin
login con token por turno; cancelar/reprogramar con anticipación exacta;
anti-spam verificable; `409` + 3 alternativas; aislamiento por tenant y
privacidad de respuesta; trazabilidad append-only.

**Non-Goals:** UI `/r/:tokenTenant` (follow-up de frontend: el `frontend/` ya
existe y la fundación F-01 está archivada); envío de
WA/email (C-13); seña y preferencia MP (C-11); auto-oferta a lista de espera
(C-07); auth JWT (C-03); DDL nueva (la columna `turnos.token_publico` ya existe).

## Decisions

- **D1 — Disponibilidad 100% server-side, reusando el motor de C-05.**
  `GET /api/publico/{tokenTenant}/disponibilidad` recibe `prestacion`,
  `profesional` (opcional) y `desde`, y devuelve huecos calculados como
  `horario_profesional ∩ horario_consultorio − bloqueos − turnos activos`, con
  `fin = calcular_fin(inicio, prestacion.duracion_min)` y grilla
  `PASO_MINUTOS = 15` (`backend/app/turnos/alternativas.py:16`), en orden
  cronológico. `desde` abre una ventana de `PUBLIC_DISPONIBILIDAD_HORIZONTE_D`
  días (valor en OQ-5): la respuesta es una lista de rango, no un solo día.
  Los tests de disponibilidad fijan el reloj con `ahora=` (igual que C-05,
  `tests/test_cancelar_reprogramar.py:35`), para que `desde` nunca caiga en el
  pasado y el escenario no pase vacío (R5).
  Alternativas descartadas: (a) grilla armada por la SPA → viola
  RN-RE-01 y produce huecos falsos; (b) tabla de slots precalculada por cron →
  estado duplicado y stale; (c) exponer `ServicioTurnos.listar` y filtrar en el
  cliente → filtra el predicado de solape en el lugar equivocado.
  Trade-off: consulta más cara por request → índices `(tenant, profesional,
  inicio)` y `(tenant, sillón, inicio)` de la 003 (`:70-77`) y horizonte acotado
  (OQ-5).

- **D2 — Tenant resuelto por el path público; el token de turno no es
  credencial cross-tenant.** La superficie pública cuelga de
  `/api/publico/{tokenTenant}/...` y mapea 1:1 con la landing `/r/:tokenTenant`:
  `GET .../disponibilidad`, `POST .../verificacion`, `POST .../reservas`,
  `GET .../reservas/{token}` y `POST .../reservas/{token}/cancelacion` o
  `/reprogramacion`. Todo request público se resuelve primero a un `tenant_id`
  con `TenantPort.resolver(tokenTenant)`; el `token_publico` se busca **dentro**
  de ese tenant. Alternativas descartadas: (a) dejar `GET /api/disponibilidad` y
  `POST /api/reservas/publicas` sin segmento de tenant —como los enumera
  `03_actores_y_roles.md:35`— y resolver el tenant por query o header →
  spoofeable o ambiguo, y los escenarios de aislamiento no se pueden escribir;
  (b) token global autosuficiente (JWT con `tenant_id` embebido) → un token
  robado cruza tenants y hay que firmar/rotar; (c) `tenant_id` por header →
  trivial de spoofear.
  Trade-off: la URL pública lleva dos identificadores (tenant legible + token del
  turno); se acepta porque el tenant ya es visible en el link y el token del turno
  no se puede derivar de él.

- **D3 — Token público por turno, vivo mientras el turno es gestionable.**
  Token UUID v4 (no secuencial, mismo criterio que `gen_random_uuid` de la 003,
  `:27`), uno por turno, emitido al crear y transferido al turno nuevo al
  reprogramar. Expira **por estado**, no por reloj: deja de servir cuando el
  turno pasa a `CANCELADO`/`REPROGRAMADO`/`PRESENTE`/`AUSENTE` o cuando su
  `fin` ya pasó. Alternativas descartadas: (a) token con TTL corto
  (`RESERVA_TTL_H`) → rompe US-011 para turnos reservados con semanas de
  anticipación; (b) token por paciente reutilizable → una filtración expone toda
  la historia; (c) link mágico firmado con expiración → agrega rotación sin
  resolver el caso de uso.
  `RESERVA_TTL_H` (nombre existente, `knowledge-base/08_arquitectura_propuesta.md:56`)
  queda reservado a la **ventana de reserva pendiente** que consume C-11; su
  valor no está fijado (OQ-1). Gap declarado: el servicio de C-05 no expone
  `token_publico` (`backend/app/turnos/servicio.py:39-54`), así que C-06 mantiene
  el índice token→turno en `TokenRepositorio`; al persistir se escribe
  `turnos.token_publico` (003:41) respaldado por el índice único parcial
  (003:80-83). No se modifica C-05.

- **D4 — Identificación liviana nombre + teléfono E.164, sin login (DD-06,
  RN-RE-05).** `PacientePort.buscar_por_telefono()` primero; si existe, la reserva
  usa ese `paciente_id`; si no, `crear_minimo(nombre, telefono_e164)`. El teléfono
  se normaliza antes de buscar (RN-RE-05 + `08:42`); el fixture ficticio válido es
  `+54 9 11 0000 0000` ⇒ `+5491100000000`. La vinculación **no compara nombre**:
  qué hacer si el teléfono existe con otro nombre queda en **OQ-8**, y el spec no
  la exige ni la prohíbe. Alternativas descartadas:
  (a) login/OTP obligatorio de paciente → PO-06 abierta (`10:20`) y DD-06 lo
  posterga a post-v1; (b) email como identidad → el canal operativo del
  consultorio es el teléfono (`09:41`); (c) crear paciente siempre → duplica
  fichas y rompe la historia clínica.
  Trade-off: dos pacientes distintos pueden compartir teléfono (familia) → OQ-8.
  Deuda: la constraint `UNIQUE(tenant_id, telefono)` **ya existe** en
  `backend/app/models/catalogos.py` (UniqueConstraint
  `pacientes_tenant_telefono_unique`, C-04 archivado); C-06 cierra la carrera de
  alta con una sola transacción y lock por `(tenant_id, telefono)` y no agrega
  DDL nueva acá (D10).

- **D5 — Anti-spam en capas: rate-limit + verificación de un solo uso.**
  (1) Contador por `(tenant, ip)` y por `(tenant, accion)` sobre
  `ContadorPort` (Redis en producción, DD-08 `09:51-56`), ventana
  `PUBLIC_RATE_LIMIT_VENTANA_S`, tope `PUBLIC_RATE_LIMIT_MAX` → `429` con
  `Retry-After`; (2) verificación liviana single-use por acción, emitida por
  `POST /api/publico/{tokenTenant}/verificacion` (body `accion`) como
  `201 {verificacion_id, expira_at = ahora + PUBLIC_VERIFICACION_TTL_MIN, canal}`
  y exigida en reservar/cancelar/reprogramar, no en disponibilidad (RN-RE-02:
  "cada acción" son confirmar, cancelar y reprogramar); (3) el público nunca
  puede crear sobreturno (RN-AG-03). Alternativas
  descartadas: (a) sólo captcha → se resuelve con granjas de bots y no cubre
  cancelaciones; (b) sólo rate-limit → no cumple RN-RE-02 ("cada acción genera
  token/sms de verificación"); (c) cuentas de paciente → contradice DD-06.
  El valor de `canal` sale de `PUBLIC_ANTISPAM_MODO` y no se fija:
  proveedor/canal (captcha vs OTP; SMS vs WhatsApp) no está fijado por la KB
  (`03:35`, `05:17`, `09:42`, `05:59`): **OQ-2**. Umbrales: **OQ-3**.

- **D6 — Anticipación mínima reusando la comparación de C-05 (borde exacto
  acepta).** `ServicioTurnos._bajo_anticipacion` usa `delta_horas <
  anticipacion` (`servicio.py:364-372`), por lo que exactamente 24 h **no** es
  "bajo" y se acepta; un minuto menos sí. `CANCEL_ANTICIPACION_H` es el default
  global por env (`08:57`) y el tenant puede sobreescribirlo en su config
  (`03:29`, RN-RE-03); C-06 lee el valor efectivo del tenant y lo pasa como
  `anticipacion_min_horas`. **Todo test de anticipación inyecta `ahora=`**,
  como C-05 (`tests/test_cancelar_reprogramar.py:35`), y el escenario declara el
  reloj congelado; ningún test usa `datetime.now()` real, porque un escenario con
  fecha absoluta caduca con el calendario y empieza a fallar solo. Alternativas
  descartadas: (a) reimplementar la
  comparación en el router público → drift de regla; (b) validar en la SPA →
  esquivable; (c) bloquear toda cancelación pública y derivar siempre a
  recepción → vacía US-011.
  Trade-off: debajo del umbral el paciente no puede autogestionar → es
  exactamente lo que pide RN-RE-03, y el rechazo se audita (RN-RE-03).

- **D7 — `409` + 3 alternativas reusando `ConflictoSolape`, sin carrito ni
  lock temporal.** El flujo es un `POST` idempotente por intención: si el hueco
  ya no está libre, `ServicioTurnos.crear/reprogramar` lanza `ConflictoSolape`
  con `buscar_alternativas(...)` (`alternativas.py:58-81`, `cantidad=3`), que ya
  respeta bloqueos y turnos activos. Alternativas descartadas: (a) reserva
  optimista con lock de N minutos en Redis → estado extra, expiración y
  liberación por worker; C-05 ya cierra la carrera en DB (RN-AG-02); (b)
  reintento automático silencioso en otra hora → viola RN-GL-02 (el paciente
  debe elegir); (c) cola de espera del request → UX opaca en móvil.
  Trade-off: el paciente puede perder el hueco por unos segundos → el `409`
  devuelve alternativas inmediatamente reservables.

- **D8 — Aislamiento y privacidad por allow-list de DTO, no por serialización
  del ORM.** Los schemas públicos exponen sólo `inicio`, `fin`,
  `profesional_id`, `sillon_id` (disponibilidad) y `turno_id`, `estado`,
  `inicio`, `fin`, `token`, `prestacion` (reserva propia). Nunca
  `TurnoOut` (que incluye `tenant_id` y `paciente_id`,
  `backend/app/schemas/turno.py:71-87`), nunca nombre/teléfono de terceros,
  nunca datos clínicos. `404` uniforme para token inexistente y token de otro
  tenant (mismo body y mismo status). Logger estructurado con
  `tenant_id`/`turno_id`/`estado`; **nunca** nombre, teléfono, token ni PHI
  (RN-CL-04). Alternativas descartadas: (a) serializar la entidad y filtrar
  campos en el cliente → fuga por error humano; (b) `403` para tokens ajenos →
  confirma existencia (enumeración); (c) loggear el payload para debug → PHI en
  logs.

- **D9 — Puertos + adaptadores en memoria para no inventar datos ni bloquearse
  en C-04.** `CatalogoPort` (prestación, profesionales habilitados vía N—N,
  sillones activos, horario semanal del profesional y del consultorio, bloqueos),
  `PacientePort`, `TokenRepositorio`, `ContadorPort`, `VerificadorPort`,
  `NotificadorPort`, `AuditoriaPort`. Alternativas descartadas: (a) esperar a
  C-04 → no se puede preparar ni testear el change; (b) catálogos hardcodeados
  en el router → datos inventados y contradice RN-AU-01; (c) tocar C-05 para que
  lea catálogos → cambia un change archivado.
  Trade-off: dos implementaciones por puerto (memoria/real) → se paga con un
  test de contrato por puerto y una tarea de wiring explícita. **Estado real:**
  con C-03 y C-04 ya archivados, el wiring SQLAlchemy de `CatalogoPort`/
  `PacientePort` (y el `AuditoriaPort` real en `backend/app/core/audit`) ya está
  desbloqueado: el follow-up condicional de `tasks.md` ("cuando aterrice
  C-04/C-03") dejó de ser condicional.

- **D10 — Sin migración nueva; el estado anti-spam vive fuera de Postgres.**
  `turnos.token_publico` (003:41) + índice único parcial (003:80-83) alcanzan
  para el token. Contadores y desafíos van a Redis (`REDIS_URL`, `08:51`) con
  TTL, así que no hay tabla nueva y la migración 004 sigue reservada para C-07
  (`CHANGES.md:237`). Alternativas descartadas: (a) tabla `reservas_publicas` +
  `otp` → duplica estado y choca con el número de revisión de C-07; (b)
  `token_publico` con expiración en columna nueva → DDL para un dato derivable
  del estado.

- **D11 — `:tokenTenant` se resuelve con un puerto, hoy por `slug`.** El
  `slug` es único por tenant (`knowledge-base/04_modelo_de_datos.md:33`) y sirve
  como identificador público legible; `TenantPort.resolver(token_tenant)`
  devuelve `tenant_id` o `None` (→ `404`), y también exige `tenants.activo`.
  Alternativas: token aleatorio por tenant (más privacidad, link no legible) →
  **OQ-4** porque `03:33` lo llama `tokenTenant` y `04:33` sólo modela `slug`.
  Trade-off: un slug adivinable permite descubrir que el consultorio existe,
  pero no leer ni escribir nada sin token de turno.

## Preguntas abiertas (OQ-1..OQ-9)

> Ningún valor de esta tabla se fija en el spec: el spec nombra la config y el
> valor queda pendiente. Cuando se resuelva, se actualiza acá y en `.env.example`.

| OQ | Pregunta | Por qué no se fija acá | Respaldo |
|---|---|---|---|
| OQ-1 | ¿Cuántas horas vale `RESERVA_TTL_H` (ventana de reserva pendiente / sin seña)? | La KB sólo muestra `48` como **ejemplo** de la columna "Ejemplo", no como default contractual; el alcance de la seña sigue abierto | `08_arquitectura_propuesta.md:56`; `10_preguntas_abiertas.md:9,15`; `05_reglas_de_negocio.md:28` |
| OQ-2 | ¿La verificación liviana es captcha o OTP? ¿Por SMS o por WhatsApp? | La KB dice "captcha/OTP liviano" y "token/sms" sin elegir; RN-IN-01 descarta SMS sin proveedor real | `03_actores_y_roles.md:35`; `05_reglas_de_negocio.md:17,59`; `09_decisiones_y_supuestos.md:42`; `10_preguntas_abiertas.md:20` |
| OQ-3 | ¿Cuántas requests por ventana y por qué claves (IP / tenant / teléfono) tolera el rate-limit? | La KB exige rate-limit pero no da umbrales | `03_actores_y_roles.md:35`; `09_decisiones_y_supuestos.md:45` |
| OQ-4 | ¿`:tokenTenant` es el `slug` público o un token aleatorio por consultorio? | `03:33` lo llama `tokenTenant`; `04:33` sólo modela `slug unique` | `03_actores_y_roles.md:33`; `04_modelo_de_datos.md:33` |
| OQ-5 | ¿Cuál es el horizonte máximo de disponibilidad que puede pedir el link público? | La KB no lo fija; los 30 días de C-05 son sólo el horizonte de búsqueda de alternativas | `07_flujos_principales.md:8`; `backend/app/turnos/alternativas.py:17` |
| OQ-6 | ¿Hay anticipación mínima para **reservar** (lead time), además de la de cancelar? | RN-RE-03 sólo habla de cancelar/reprogramar; la KB no fija lead time de reserva | `05_reglas_de_negocio.md:18`; `06_funcionalidades.md:29-32` |
| OQ-7 | ¿La reserva pública exige seña antes de confirmar, y con qué monto/alcance? | Es el objeto de C-11; en C-06 el turno queda `PENDIENTE` | `05_reglas_de_negocio.md:24-28`; `10_preguntas_abiertas.md:9,15`; `CHANGES.md:30` |
| OQ-8 | Si el teléfono ya existe con otro nombre, ¿se vincula igual, se actualiza el nombre o se rechaza? ¿Se puede reservar para un tercero? | RN-RE-05 sólo dice "se vincula al paciente existente" | `05_reglas_de_negocio.md:20`; `04_modelo_de_datos.md:51-53` |
| OQ-9 | ¿Por qué canal sale la confirmación inmediata que pide US-010 CA-3 (WA / email)? | El envío pertenece a C-13, que depende de C-07 | `06_funcionalidades.md:26`; `11_integraciones.md:9`; `CHANGES.md:31,74` |

## Seams

Interfaces que C-06 **consume** (C-05, C-03 y C-04 ya archivados; C-13
inexistente) y las que **define** para no acoplarse. Firmas con type hints (R7).

```python
# --- C-05 real: backend/app/turnos/servicio.py ---
@dataclass(frozen=True)
class Actor:
    tenant_id: str
    rol: Literal["PACIENTE", "ODONTOLOGO", "RECEPCION", "ADMIN"]
    user_id: str
    profesional_id: str | None = None


class ServicioTurnos:
    def crear(
        self, actor: Actor, *, profesional_id: str, sillon_id: str,
        paciente_id: str, prestacion_id: str, inicio: datetime,
        duracion_min: int, fin_cliente: datetime | None = None,
        sobreturno: bool = False, motivo_sobreturno: str | None = None,
        origen: OrigenTurno = "RECEPCION",
    ) -> Turno: ...                      # servicio.py:123

    def obtener(self, actor: Actor, turno_id: str) -> Turno: ...          # :189
    def cancelar(self, actor: Actor, turno_id: str, *,
                 ahora: datetime | None = None) -> Turno: ...             # :231
    def reprogramar(self, actor: Actor, turno_id: str, *, nuevo_inicio: datetime,
                    duracion_min: int | None = None,
                    ahora: datetime | None = None) -> Reprogramacion: ... # :252
    def auditoria(self, actor: Actor,
                  turno_id: str | None = None) -> list[AuditoriaEntrada]: ...  # :316


class ConflictoSolape(TurnoError):     # codigo = 409, servicio.py:99-107
    alternativas: list[Alternativa]


# --- C-05 real: backend/app/turnos/alternativas.py ---
def buscar_alternativas(
    desde: datetime, duracion_min: int, tenant_id: str, profesional_id: str,
    sillon_id: str, ocupados: list[HuecoOcupado],
    bloqueos: list[tuple[datetime, datetime]] = (), cantidad: int = 3,
) -> list[Alternativa]: ...                                               # :58


# --- C-03 (ya archivado): JWT + RBAC + auditoría ---
def actor_desde_headers(x_tenant_id: str, x_user_id: str, x_rol: str,
                        x_profesional_id: str | None = None) -> Actor: ...  # routers/turnos.py:37
# C-06 NO usa esta dependencia en rutas públicas: un header X-Tenant-Id no
# puede cambiar el tenant resuelto por la ruta ni el rol del paciente.


# --- C-04 (ya archivado): puertos que C-06 define; se cablean a backend/app/models/catalogos.py ---
class CatalogoPort(Protocol):
    def prestacion(self, tenant_id: str, prestacion_id: str) -> Prestacion: ...
    def profesionales_habilitados(self, tenant_id: str,
                                  prestacion_id: str) -> Sequence[Profesional]: ...
    def sillones_activos(self, tenant_id: str) -> Sequence[Sillon]: ...
    def horario_profesional(self, tenant_id: str,
                            profesional_id: str) -> Sequence[HorarioSemanal]: ...
    def horario_consultorio(self, tenant_id: str) -> Sequence[HorarioSemanal]: ...
    def bloqueos(self, tenant_id: str, desde: datetime,
                 hasta: datetime) -> Sequence[Bloqueo]: ...


class PacientePort(Protocol):
    def buscar_por_telefono(self, tenant_id: str,
                            telefono_e164: str) -> Paciente | None: ...
    def crear_minimo(self, tenant_id: str, nombre: str,
                     telefono_e164: str) -> Paciente: ...


class TenantPort(Protocol):
    def resolver(self, token_tenant: str) -> str | None: ...   # tenant_id o None (404)


# --- C-06 define (adaptadores: memoria en tests, Redis/C-03 en producción) ---
class TokenRepositorio(Protocol):
    def emitir(self, tenant_id: str, turno_id: str) -> str: ...
    def resolver(self, tenant_id: str, token: str) -> TokenResuelto | None: ...
    def transferir(self, token: str, turno_nuevo_id: str) -> None: ...
    def revocar(self, token: str) -> None: ...


class ContadorPort(Protocol):
    def incrementar(self, clave: str, ventana_s: int) -> int: ...
    def ttl_s(self, clave: str) -> int: ...


class VerificadorPort(Protocol):
    def desafio(self, *, tenant_id: str, accion: AccionPublica,
                ip: str) -> DesafioPublico: ...
    def verificar(self, *, tenant_id: str, accion: AccionPublica,
                  prueba: str, ip: str) -> bool: ...


class NotificadorPort(Protocol):          # no-op hasta C-13
    def reserva_creada(self, *, tenant_id: str, turno_id: str) -> None: ...


class AuditoriaPort(Protocol):            # adapter real: backend/app/core/audit (C-03)
    def registrar(self, *, tenant_id: str, turno_id: str,
                  accion: AccionAuditada, actor: str,
                  antes: str | None, despues: str) -> None: ...
```

## Risks / Trade-offs

- [Hueco mostrado ≠ hueco real al confirmar] → `409` + 3 alternativas (D7) y
  EXCLUDE de la 003 como fuente de verdad; test de concurrencia obligatorio.
- [Enumeración de turnos por token] → UUID v4 no secuencial, `404` uniforme,
  rate-limit y sin token en logs (D3/D8).
- [Spam con teléfonos ficticios] → rate-limit + verificación single-use (D5);
  calibración pendiente (OQ-2/OQ-3).
- [Drift al integrar `CatalogoPort`/`PacientePort` con los modelos reales de
  C-04] → puertos + adaptadores en memoria (D9); riesgo de drift al integrar →
  test de contrato por puerto y wiring (ya desbloqueado con C-04 archivado).
- [El token vive más que la reserva pendiente] → vigencia por estado (D3):
  `CANCELADO`/`REPROGRAMADO`/`PRESENTE`/`AUSENTE` o `fin` pasado ⇒ `404`.
- [Zona horaria] → borde exige datetimes aware (`AwareDatetime`,
  `schemas/turno.py:25`), persistencia `timestamptz` (003:33-34); escenarios en
  `-03:00` para que el borde exacto no dependa del TZ del runner.
- [Rate-limit por IP detrás de proxy] → la IP se toma de la config del proxy, no
  del header crudo; se documenta en la tarea de borde.
- [Sin envío de confirmación (C-13)] → la respuesta HTTP confirma en pantalla y
  el evento queda encolado en el puerto no-op; deuda declarada D-C.
- [Parsear/telefonear como identidad] → normalización E.164 antes de buscar
  (D4) y `422` cuando no normaliza.

## Migration Plan

1. **Sin DDL**: no hay migración nueva. `turnos.token_publico` e índice único
   parcial ya existen (003:41, 80-83); la migración 004 queda para C-07
   (`CHANGES.md:237`).
2. Nuevos módulos: `backend/app/reservas/` (disponibilidad, tokens, antispam,
   servicio público, puertos), `backend/app/routers/reservas_publicas.py`,
   `backend/app/schemas/reserva.py`; tests en `tests/test_*` nuevos, sin tocar
   los existentes.
3. Config: sumar a `.env.example` (C-01, `CHANGES.md:114`) los nombres
   `PUBLIC_RATE_LIMIT_MAX`, `PUBLIC_RATE_LIMIT_VENTANA_S`,
   `PUBLIC_VERIFICACION_TTL_MIN`, `PUBLIC_DISPONIBILIDAD_HORIZONTE_D` y
   `PUBLIC_ANTISPAM_MODO`; `RESERVA_TTL_H` y `CANCEL_ANTICIPACION_H` ya están
   listados. Valores en OQ-1..OQ-5: no se inventan defaults.
4. Rollout: rutas públicas detrás de flag de config por tenant (apagado por
   defecto hasta cerrar OQ-2/OQ-3 y el wiring de C-04). Rollback = apagar el
   flag; no hay datos nuevos que migrar.
5. Verificación: `py -m pytest tests/ -q` (104 de C-05 + nuevos) y
   `openspec validate c-06-reserva-online-publica --strict`.

## Notas de implementación (no vinculantes)

- El actor de las rutas públicas se construye como
  `Actor(tenant_id=<resuelto>, rol="PACIENTE", user_id=<paciente_id>)`, que es
  exactamente lo que valida `_puede_crear` de C-05 (`servicio.py:340-351`). No se
  relaja ni se parchea RBAC.
- `origen="RESERVA_ONLINE"` ya es un valor válido del schema
  (`schemas/turno.py:14`) y del CHECK de la 003 (`:39-40`).
- La reprogramación reusa `ServicioTurnos.reprogramar`, que revalida solape
  **antes** de mutar (`servicio.py:279-296`): el original queda intacto ante
  `409`.
