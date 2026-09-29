# Modelo de Datos

> Regla raíz multi-tenant: **todas** las tablas de negocio llevan `tenant_id` NOT NULL con FK a `tenants` y política RLS `tenant_id = current_setting('app.tenant_id')`. Ninguna query de negocio corre sin tenant. Datos de ejemplo FICTICIOS.

## Dominios

- **Tenancy/identidad**: tenants, usuarios, roles, sesiones, auditoría.
- **Agenda**: profesionales, sillones, horarios, bloqueos, turnos, sobreturnos, lista de espera.
- **Clínica**: pacientes, fichas, odontograma (hallazgos), evoluciones, adjuntos, consentimientos.
- **Comercial**: prestaciones, presupuestos (+ líneas), aceptaciones, señas.
- **Caja/OS**: movimientos de caja, cierres, obras sociales, coberturas, liquidaciones.
- **Integración**: mensajes WA, pagos MP, vínculos Google Calendar, recordatorios.

## ERD (textual)

```
tenants 1──N usuarios, profesionales, sillones, prestaciones, pacientes, obras_sociales
profesionales N──N prestaciones (habilidad) · 1──N horarios_semanales, bloqueos
turnos: (tenant, profesional, sillón, paciente, prestación, inicio, fin, estado, sobreturno=false)
  └─ constraint: sin solape por (tenant, profesional) ni por (tenant, sillón) salvo sobreturno=true auditado
pacientes 1──1 fichas 1──N evoluciones, odontograma_hallazgos, presupuestos, consentimientos
presupuestos 1──N presupuesto_lineas (pieza FDI + prestación + cobertura OS) ──N aceptaciones
senas 1──1 turnos (opcional), 1──N pagos_mp (webhook idempotente por payment_id)
caja: movimientos (tenant, fecha, medio, monto, turno?, usuario) ──N cierres_diarios
lista_espera (tenant, paciente, prestación, preferencia) ──ofertas──► turnos liberados
mensajes_wa (tenant, paciente, turno, plantilla, estado, message_id) · calendar_links (profesional ↔ gcal)
auditoria (tenant, actor, acción, entidad, antes/después, timestamp) — append-only
```

## Entidades (principales)

### tenants
- Atributos: `id uuid PK`, `nombre`, `slug unique`, `plan`, `activo bool`, `created_at`.
- Relaciones: raíz 1──N de todo el negocio. Índices: `slug unique`.

### usuarios
- Atributos: `id`, `tenant_id FK`, `nombre`, `email unique por tenant`, `password_hash` (bcrypt/argon2), `rol enum(PACIENTE? no — interno: ODONTOLOGO, RECEPCION, ADMIN)`, `two_factor bool`, `activo`.
- Constraints: `UNIQUE(tenant_id, email)`. Índices: `(tenant_id, rol)`.

### profesionales
- Atributos: `id`, `tenant_id`, `usuario_id FK?` (puede no tener login), `nombre`, `especialidad`, `matricula?`, `color_agenda`, `activo`.
- Relaciones: N──N `profesional_prestacion`; 1──N `horarios_semanales(dia, desde, hasta)`, `bloqueos(desde, hasta, motivo)`, `calendar_links`.

### sillones
- Atributos: `id`, `tenant_id`, `nombre` ("Sillón 1", "Box 2"), `activo`. (Recurso anti-solape junto a profesional.)

### prestaciones
- Atributos: `id`, `tenant_id`, `nombre` ("Limpieza", "Conducto"), `duracion_min`, `precio_base`, `requiere_sena bool`, `monto_sena?`, `especialidades?`, `activa`.
- Índices: `(tenant_id, activa)`.

### pacientes
- Atributos: `id`, `tenant_id`, `nombre_ficticio`, `dni_cifrado?`, `telefono` (canal WA), `email?`, `obra_social_id?`, `nro_afiliado?`, `consentimiento_ok bool`, `created_at`.
- Constraints: `UNIQUE(tenant_id, dni)` donde aplique; teléfono normalizado E.164. Índices: `(tenant_id, telefono)`.

### turnos
- Atributos: `id`, `tenant_id`, `profesional_id`, `sillon_id`, `paciente_id`, `prestacion_id`, `inicio timestamptz`, `fin` (= inicio + duración), `estado enum(PENDIENTE, CONFIRMADO, PRESENTE, AUSENTE, CANCELADO, REPROGRAMADO)`, `sobreturno bool default false`, `origen enum(RECEPCION, ONLINE, LISTA_ESPERA)`, `token_publico uuid?`, `sena_id?`.
- Constraints: **EXCLUDE anti-solape** por `(tenant_id, profesional_id)` y por `(tenant_id, sillon_id)` con rango `[inicio, fin)` donde `estado NOT IN (CANCELADO, REPROGRAMADO)` y `sobreturno = false`; sobreturno exige `motivo` + actor en auditoría.
- Índices: `(tenant_id, profesional_id, inicio)`, `(tenant_id, sillon_id, inicio)`, `(tenant_id, estado)`.

### lista_espera (+ ofertas)
- Atributos: `id`, `tenant_id`, `paciente_id`, `prestacion_id`, `profesional_pref?`, `ventana_horaria?`, `estado(PENDIENTE, OFRECIDO, CONVERTIDO, VENCIDO)`; `ofertas(hueco_turno_id?, expira_at, estado)`.

### odontograma_hallazgos / evoluciones / presupuestos
- `odontograma_hallazgos`: `id`, `tenant_id`, `paciente_id`, `pieza_fdi (11–48)`, `superficie?`, `hallazgo`, `fecha`, `profesional_id`, `resuelto bool`.
- `evoluciones`: `id`, `tenant_id`, `paciente_id`, `profesional_id`, `fecha`, `texto`, `firma_hash?`.
- `presupuestos`: `id`, `tenant_id`, `paciente_id`, `estado(BORRADOR, VIGENTE, PARCIAL, ACEPTADO, VENCIDO)`; `presupuesto_lineas(presupuesto_id, pieza_fdi?, prestacion_id, monto, cobertura_os, a_cargo_paciente)`; `aceptaciones(linea_id, acepta bool, fecha, canal)`.

### senas / pagos_mp / movimientos / cierres
- `senas`: `id`, `tenant_id`, `turno_id unique?`, `monto`, `estado(PENDIENTE, ACREDITADA, LIBERADA, APLICADA, DEVUELTA)`, `mp_preference_id`, `expira_at`.
- `pagos_mp`: `mp_payment_id unique` (idempotencia), `sena_id`, `monto`, `estado`, `raw_json`, `received_at`.
- `movimientos_caja`: `id`, `tenant_id`, `fecha`, `medio(EFECTIVO, TRANSFERENCIA, MP, OS)`, `monto`, `tipo(INGRESO, EGRESO)`, `turno_id?`, `usuario_id`, `anulado bool + motivo`.
- `cierres_diarios`: `UNIQUE(tenant_id, fecha)`, `totales por medio`, `diferencia`, `responsable`, `cerrado_at`.

### obras_sociales / coberturas / liquidaciones
- `obras_sociales`: `id`, `tenant_id NULL?` (catálogo por tenant en v1), `nombre` ("OSDE", "Swiss Medical"...), `activa`.
- `coberturas`: `(tenant_id, obra_social_id, prestacion_id, porcentaje/monto, tope?)`.
- `liquidaciones`: `id`, `tenant_id`, `obra_social_id`, `periodo`, `estado`, `total`; líneas por turno atendido con OS.

### mensajes_wa / recordatorios / auditoria
- `mensajes_wa`: `id`, `tenant_id`, `paciente_id`, `turno_id?`, `plantilla`, `estado(ENVIADO, ENTREGADO, LEIDO, FALLIDO)`, `provider_message_id unique?`.
- `auditoria`: append-only `(tenant_id, actor_id, accion, entidad, entidad_id, antes jsonb, despues jsonb, at)`; sin UPDATE/DELETE (revoke).

## Seed data inicial

- Por tenant nuevo: roles (ADMIN/RECEPCION/ODONTOLOGO), estados de turno, medios de pago, 1 sillón ("Sillón 1"), prestaciones base (Consulta, Limpieza — duración/precio editables), plantillas WA (confirmación, recordatorio 24 h, cancelación, auto-oferta), parámetros (anticipación cancelación default 24 h, política de seña).
- Superadmin: catálogo de prestaciones sugeridas y 3–5 OS comunes (nombres, sin aranceles reales — los carga cada tenant).
