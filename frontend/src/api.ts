export type Rol = 'ADMIN' | 'RECEPCION' | 'ODONTOLOGO' | 'PACIENTE';

export interface Actor {
  tenantId: string;
  userId: string;
  rol: Rol;
  profesionalId?: string;
}

export interface ApiContext {
  actor: Actor | null;
  token: string | null;
}

let context: ApiContext = { actor: null, token: null };

export function setApiContext(next: ApiContext): void {
  context = next;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly codigo?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function actorHeaders(): Record<string, string> {
  if (!context.actor) return {};
  const headers: Record<string, string> = {
    'X-Tenant-Id': context.actor.tenantId,
    'X-User-Id': context.actor.userId,
    'X-Rol': context.actor.rol,
  };
  if (context.actor.profesionalId) {
    headers['X-Profesional-Id'] = context.actor.profesionalId;
  }
  return headers;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...actorHeaders(),
    ...(init.headers as Record<string, string> | undefined),
  };
  if (init.body) headers['Content-Type'] = 'application/json';
  if (context.token) headers.Authorization = `Bearer ${context.token}`;
  const response = await fetch(path, { ...init, headers });
  const text = await response.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const record = body as { detalle?: unknown; codigo?: unknown } | null;
    const detalle = record && typeof record.detalle === 'string' ? record.detalle : null;
    const codigo = record && typeof record.codigo === 'string' ? record.codigo : undefined;
    throw new ApiError(detalle ?? `Error ${response.status}`, response.status, codigo);
  }
  return body as T;
}

export async function apiBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = { ...actorHeaders() };
  if (context.token) headers.Authorization = `Bearer ${context.token}`;
  const response = await fetch(path, { headers });
  if (!response.ok) {
    throw new ApiError(`No pudimos descargar el archivo (${response.status})`, response.status);
  }
  return response.blob();
}

export function qs(params: Record<string, string | number | boolean | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

// ---------------------------------------------------------------------------
// Tipos de respuesta
// ---------------------------------------------------------------------------

export interface Profesional {
  id: string;
  nombre: string;
  especialidad: string;
  matricula: string | null;
  color_agenda: string;
  activo: boolean;
}

export interface Sillon {
  id: string;
  nombre: string;
  activo: boolean;
}

export interface Prestacion {
  id: string;
  nombre: string;
  duracion_min: number;
  precio_base: number;
  requiere_sena: boolean;
  monto_sena: number | null;
  activa: boolean;
}

export interface Paciente {
  id: string;
  nombre: string;
  telefono: string;
  email: string | null;
  nro_afiliado: string | null;
  consentimiento_ok: boolean;
}

export interface Turno {
  id: string;
  profesional_id: string;
  sillon_id: string;
  paciente_id: string;
  prestacion_id: string;
  inicio: string;
  fin: string;
  estado: string;
  origen: string;
  sobreturno: boolean;
}

export interface Ficha {
  id: string;
  paciente_id: string;
  creado_en: string;
}

export interface Evolucion {
  id: string;
  paciente_id: string;
  profesional_id: string;
  fecha: string;
  texto: string;
  creado_en: string;
}

export interface Consentimiento {
  id: string;
  paciente_id: string;
  timestamp: string;
  canal: string;
  creado_en: string;
}

export interface Hallazgo {
  id: string;
  paciente_id: string;
  pieza_fdi: number;
  superficie: string | null;
  hallazgo: string;
  fecha: string;
  profesional_id: string;
  resuelto: boolean;
}

export interface LineaPresupuesto {
  id: string;
  presupuesto_id: string;
  prestacion_id: string;
  monto: number;
  cobertura_os: number;
  a_cargo_paciente: number;
  pieza_fdi: number | null;
  hallazgo_id: string | null;
}

export interface AceptacionPresupuesto {
  id: string;
  linea_id: string;
  acepta: boolean;
  fecha: string;
  canal: string;
  medio: string | null;
}

export interface LineaDecisionPresupuesto {
  linea: LineaPresupuesto;
  aceptacion: AceptacionPresupuesto | null;
}

export interface PresupuestoResumen {
  id: string;
  paciente_id: string;
  estado: string;
  vence_en: string | null;
  creado_en: string;
}

export interface Presupuesto extends PresupuestoResumen {
  lineas: LineaDecisionPresupuesto[];
}

export interface Movimiento {
  id: string;
  fecha: string;
  medio: string;
  monto: number;
  tipo: string;
  turno_id: string | null;
  usuario_id: string;
  anulado: boolean;
}

export interface ConsultaDia {
  fecha: string;
  estado: string;
  movimientos: Movimiento[];
  pendientes: unknown[];
  ajustes: unknown[];
  totales_vigentes: { efectivo: number; transferencia: number; mp: number; os: number };
  totales_cierre: unknown | null;
  difieren_del_cierre: boolean;
}

export interface SenaInterna {
  sena_id: string;
  turno_id: string;
  turno: { inicio: string; fin: string; prestacion: string } | null;
  estado: string;
  monto_centavos: number;
  expira_at: string;
  preferencia_estado: string;
  obligaciones: unknown[];
}

export interface ObraSocial {
  id: string;
  nombre: string;
  activa: boolean;
}

export interface Cobertura {
  id: string;
  obra_social_id: string;
  prestacion_id: string;
  modo: string;
  valor: number;
  tope_centavos: number | null;
  validada_en_vivo: boolean;
}

export interface Tramo {
  precio_base_centavos: number;
  cobertura_os: number;
  a_cargo_paciente: number;
  origen: string;
  validada_en_vivo: boolean;
}

export interface Liquidacion {
  id: string;
  obra_social_id: string;
  periodo_desde: string;
  periodo_hasta: string;
  estado: string;
  total_centavos: number;
  creado_en: string;
  lineas: { turno_id: string; fecha: string; monto_centavos: number }[];
}

export interface CalendarLink {
  id: string;
  profesional_id: string;
  gcal_calendar_id: string;
  estado: string;
  ultima_sync: string | null;
}

export interface EventoCalendario {
  id: string;
  link_id: string;
  turno_id: string | null;
  gcal_event_id: string | null;
  origen: string;
  estado: string;
  inicio: string;
  fin: string;
  resumen: string;
}

export interface Kpis {
  desde: string;
  hasta: string;
  total_turnos: number;
  turnos_por_estado: Record<string, number>;
  ausentismo_pct: number;
  reservas_online_pct: number;
  facturacion_por_profesional: [string, number][];
  reasignados_2h: number;
  ocupacion_pct: number;
}

export type TenantConfig = Record<string, unknown>;

export interface UsuarioAdmin {
  id: string;
  nombre: string;
  email: string;
  rol: Rol;
  activo: boolean;
}

export type PlantillaWA = 'RECORDATORIO' | 'CONFIRMACION' | 'CANCELACION' | 'RECALL';
export type EstadoMensajeWA = 'PENDIENTE' | 'ENVIADO' | 'ENTREGADO' | 'LEIDO' | 'FALLIDO';

export interface MensajeWA {
  id: string;
  paciente_id: string;
  turno_id: string | null;
  plantilla: PlantillaWA;
  canal: 'WA' | 'EMAIL';
  estado: EstadoMensajeWA;
  provider_message_id: string | null;
  intentos: number;
  proximo_intento: string;
  cuerpo: string;
  respuesta: string | null;
  creado_en: string;
}

export interface EnvioWA {
  enviados: number;
  fallidos: number;
  mensajes: MensajeWA[];
}

export interface Pendiente {
  id: string;
  fecha: string;
  presupuesto_id: string;
  linea_id: string;
  monto_centavos: number;
  actor_id: string;
  turno_id: string | null;
  creado_en: string;
  resuelto_en: string | null;
  movimiento_id: string | null;
}

export interface TotalesCaja {
  efectivo: number;
  transferencia: number;
  mp: number;
  os: number;
}

export interface CierreCaja {
  id: string;
  fecha: string;
  totales: {
    total_efectivo: number;
    total_transferencia: number;
    total_mp: number;
    total_os_cobrado: number;
    total_os: number;
  };
  efectivo_contado: number;
  diferencia: number;
  responsable_id: string;
  motivo_diferencia: string | null;
  observacion: string | null;
  cerrado_at: string;
}

export interface DiaReporte {
  fecha: string;
  efectivo: number;
  transferencia: number;
  mp: number;
  os: number;
  movimientos: number;
}

export interface ReporteCaja {
  desde: string;
  hasta: string;
  fuente: string;
  totales: TotalesCaja;
  por_dia: DiaReporte[];
  cierres: number;
  movimientos_anulados: number;
}

export interface DecisionPresupuesto {
  presupuesto_id: string;
  estado: string;
  actor_id: string;
  linea_id: string;
  acepta: boolean;
  fecha: string;
  canal: string;
  medio: string | null;
}

// ---------------------------------------------------------------------------
// Catálogos y agenda
// ---------------------------------------------------------------------------

export const catalogoApi = {
  profesionales: () => api<Profesional[]>('/api/profesionales'),
  sillones: () => api<Sillon[]>('/api/sillones'),
  prestaciones: () => api<Prestacion[]>('/api/prestaciones'),
  pacientes: () => api<Paciente[]>('/api/pacientes'),
  crearPaciente: (body: {
    nombre: string;
    telefono: string;
    email?: string;
    consentimiento_ok?: boolean;
  }) =>
    api<Paciente>('/api/pacientes', { method: 'POST', body: JSON.stringify(body) }),
};

export const turnosApi = {
  listar: () => api<Turno[]>('/api/turnos'),
  crear: (body: {
    profesional_id: string;
    sillon_id: string;
    paciente_id: string;
    prestacion_id: string;
    duracion_min: number;
    inicio: string;
  }) => api<Turno>('/api/turnos', { method: 'POST', body: JSON.stringify(body) }),
  cancelar: (id: string) =>
    api<Turno>(`/api/turnos/${id}/cancelar`, { method: 'POST' }),
  confirmar: (id: string) =>
    api<Turno>(`/api/turnos/${id}/confirmar`, { method: 'POST' }),
  presente: (id: string) => api<Turno>(`/api/turnos/${id}/presente`, { method: 'POST' }),
  ausente: (id: string) => api<Turno>(`/api/turnos/${id}/ausente`, { method: 'POST' }),
  reprogramar: (id: string, body: { nuevo_inicio: string; duracion_min?: number }) =>
    api<{ original: Turno; nuevo: Turno }>(`/api/turnos/${id}/reprogramar`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};

// ---------------------------------------------------------------------------
// Clínica
// ---------------------------------------------------------------------------

export const clinicaApi = {
  ficha: (pacienteId: string) => api<Ficha>(`/api/pacientes/${pacienteId}/ficha`),
  crearFicha: (pacienteId: string) =>
    api<Ficha>(`/api/pacientes/${pacienteId}/ficha`, { method: 'POST' }),
  consentimientos: (pacienteId: string) =>
    api<Consentimiento[]>(`/api/consentimientos${qs({ paciente_id: pacienteId })}`),
  crearConsentimiento: (body: { paciente_id: string; timestamp: string; canal: string }) =>
    api<Consentimiento>('/api/consentimientos', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  evoluciones: (pacienteId: string) =>
    api<Evolucion[]>(`/api/evoluciones${qs({ paciente_id: pacienteId })}`),
  crearEvolucion: (body: {
    paciente_id: string;
    profesional_id: string;
    fecha: string;
    texto: string;
  }) => api<Evolucion>('/api/evoluciones', { method: 'POST', body: JSON.stringify(body) }),
  hallazgos: (pacienteId: string) =>
    api<Hallazgo[]>(`/api/odontograma${qs({ paciente_id: pacienteId })}`),
  crearHallazgo: (body: {
    paciente_id: string;
    pieza_fdi: number;
    superficie?: string;
    hallazgo: string;
    fecha: string;
    profesional_id: string;
  }) => api<Hallazgo>('/api/odontograma', { method: 'POST', body: JSON.stringify(body) }),
  presupuestos: (pacienteId: string) =>
    api<Presupuesto[]>(`/api/presupuestos${qs({ paciente_id: pacienteId })}`),
  crearPresupuesto: (pacienteId: string) =>
    api<PresupuestoResumen>('/api/presupuestos', {
      method: 'POST',
      body: JSON.stringify({ paciente_id: pacienteId }),
    }),
  agregarLinea: (presupuestoId: string, body: { prestacion_id: string; monto?: number }) =>
    api<LineaPresupuesto>(`/api/presupuestos/${presupuestoId}/lineas`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  emitir: (presupuestoId: string, venceEn: string) =>
    api<PresupuestoResumen>(`/api/presupuestos/${presupuestoId}/emitir`, {
      method: 'POST',
      body: JSON.stringify({ vence_en: venceEn }),
    }),
  decidir: (
    presupuestoId: string,
    body: {
      linea_id: string;
      acepta: boolean;
      canal: string;
      medio?: string | null;
    },
  ) =>
    api<DecisionPresupuesto>(`/api/presupuestos/${presupuestoId}/aceptar`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  resolverHallazgo: (hallazgoId: string) =>
    api<Hallazgo>(`/api/odontograma/${hallazgoId}/resolver`, { method: 'POST' }),
};

// ---------------------------------------------------------------------------
// Caja y señas
// ---------------------------------------------------------------------------

export const cajaApi = {
  dia: (fecha: string) => api<ConsultaDia>(`/api/caja/movimientos${qs({ fecha })}`),
  registrar: (body: {
    monto: number;
    medio: string;
    tipo: string;
    fecha: string;
  }) => api<Movimiento>('/api/caja/movimientos', { method: 'POST', body: JSON.stringify(body) }),
  cerrar: (body: {
    efectivo_contado: number;
    responsable_id: string;
    fecha: string;
    motivo_diferencia?: string;
    observacion?: string;
  }) => api<CierreCaja>('/api/caja/cierre', { method: 'POST', body: JSON.stringify(body) }),
  anular: (id: string, motivo: string) =>
    api<Movimiento>(`/api/caja/movimientos/${id}/anular`, {
      method: 'POST',
      body: JSON.stringify({ motivo }),
    }),
  pendientes: (fecha?: string) =>
    api<Pendiente[]>(`/api/caja/pendientes${qs({ fecha })}`),
  cobrar: (pendienteId: string, medio: string) =>
    api<{ pendiente: Pendiente; movimiento: Movimiento; ajuste: unknown | null }>(
      `/api/caja/pendientes/${pendienteId}/cobrar`,
      { method: 'POST', body: JSON.stringify({ medio }) },
    ),
  cierres: (desde: string, hasta: string) =>
    api<CierreCaja[]>(`/api/caja/cierres${qs({ desde, hasta })}`),
  reporte: (desde: string, hasta: string) =>
    api<ReporteCaja>(`/api/caja/reportes${qs({ desde, hasta })}`),
};

export const senasApi = {
  listar: (desde?: string, hasta?: string) =>
    api<SenaInterna[]>(`/api/senas${qs({ desde, hasta })}`),
};

// ---------------------------------------------------------------------------
// Obras sociales
// ---------------------------------------------------------------------------

export const obrasSocialesApi = {
  listar: () => api<ObraSocial[]>('/api/obras-sociales'),
  crear: (nombre: string) =>
    api<ObraSocial>('/api/obras-sociales', {
      method: 'POST',
      body: JSON.stringify({ nombre }),
    }),
  coberturas: (obraSocialId?: string) =>
    api<Cobertura[]>(`/api/coberturas${qs({ obra_social_id: obraSocialId })}`),
  configurar: (body: {
    obra_social_id: string;
    prestacion_id: string;
    modo: string;
    valor: number;
    tope_centavos?: number | null;
  }) => api<Cobertura>('/api/coberturas', { method: 'PUT', body: JSON.stringify(body) }),
  preview: (pacienteId: string, prestacionId: string) =>
    api<Tramo>(`/api/coberturas/preview${qs({
      paciente_id: pacienteId,
      prestacion_id: prestacionId,
    })}`),
  liquidaciones: () => api<Liquidacion[]>('/api/liquidaciones'),
  generar: (body: { obra_social_id: string; desde: string; hasta: string }) =>
    api<Liquidacion>('/api/liquidaciones', { method: 'POST', body: JSON.stringify(body) }),
  cerrar: (id: string) =>
    api<Liquidacion>(`/api/liquidaciones/${id}/cerrar`, { method: 'POST' }),
  detalle: (id: string) => api<Liquidacion>(`/api/liquidaciones/${id}`),
  cambiarEstado: (id: string, activa: boolean) =>
    api<ObraSocial>(`/api/obras-sociales/${id}`, {
      method: 'PATCH',
      body: JSON.stringify({ activa }),
    }),
  csvUrl: (id: string) => `/api/liquidaciones/${id}/export.csv`,
};

// ---------------------------------------------------------------------------
// Calendario
// ---------------------------------------------------------------------------

export const calendarioApi = {
  links: () => api<CalendarLink[]>('/api/calendar/links'),
  conectar: (body: { profesional_id: string; gcal_calendar_id: string; oauth_ref: string }) =>
    api<CalendarLink>('/api/calendar/oauth', { method: 'POST', body: JSON.stringify(body) }),
  push: (body: {
    turno_id: string;
    profesional_id: string;
    inicio: string;
    fin: string;
    estado: string;
  }) => api<{ estado: string; evento: EventoCalendario | null }>('/api/calendar/push', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  bloqueos: (desde: string, hasta: string) =>
    api<EventoCalendario[]>(`/api/calendar/bloqueos${qs({ desde, hasta })}`),
  webhook: (body: {
    link_id: string;
    token: string;
    event_id: string;
    inicio: string;
    fin: string;
    resumen: string;
  }) =>
    api<EventoCalendario>('/api/calendar/webhook', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  desconectar: (linkId: string) =>
    api<CalendarLink>(`/api/calendar/links/${linkId}`, { method: 'DELETE' }),
};

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export const adminApi = {
  config: () => api<TenantConfig>('/api/tenant/config'),
  actualizarConfig: (body: TenantConfig) =>
    api<TenantConfig>('/api/tenant/config', { method: 'PUT', body: JSON.stringify(body) }),
  usuarios: () => api<UsuarioAdmin[]>('/api/tenant/usuarios'),
  crearUsuario: (body: {
    nombre: string;
    email: string;
    password: string;
    rol: string;
  }) => api<UsuarioAdmin>('/api/tenant/usuarios', { method: 'POST', body: JSON.stringify(body) }),
  cambiarEstadoUsuario: (usuarioId: string, activo: boolean) =>
    api<UsuarioAdmin>(`/api/tenant/usuarios/${usuarioId}`, {
      method: 'PATCH',
      body: JSON.stringify({ activo }),
    }),
  exportUrl: (formato: 'json' | 'csv') => `/api/exportacion?formato=${formato}`,
  kpis: (desde: string, hasta: string) =>
    api<Kpis>(`/api/reportes/kpis${qs({ desde, hasta })}`),
};

// ---------------------------------------------------------------------------
// WhatsApp
// ---------------------------------------------------------------------------

export const whatsappApi = {
  programar: () =>
    api<EnvioWA>('/api/whatsapp/recordatorios/programar', { method: 'POST' }),
  procesar: () => api<EnvioWA>('/api/whatsapp/cola/procesar', { method: 'POST' }),
  mensajes: (turnoId?: string) =>
    api<MensajeWA[]>(`/api/whatsapp/mensajes${qs({ turno_id: turnoId })}`),
  recall: (body: { paciente_id: string; motivo: string; fecha_objetivo: string }) =>
    api<MensajeWA>('/api/whatsapp/recall', {
      method: 'POST',
      body: JSON.stringify(body),
    }),
};
