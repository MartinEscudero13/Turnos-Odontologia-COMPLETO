import { isRecord, type ApiResult } from './healthClient';

/** Prestación del catálogo público (`GET .../catalogo`, allow-list). */
export interface PrestacionPublica {
  id: string;
  nombre: string;
  duracionMin: number;
}

/** Profesional activo del catálogo público. */
export interface ProfesionalPublico {
  id: string;
  nombre: string;
}

/** Catálogo público del tenant: solo nombres, duración e ids opacos. */
export interface CatalogoPublico {
  prestaciones: PrestacionPublica[];
  profesionales: ProfesionalPublico[];
}

/** Hueco libre devuelto por `GET .../disponibilidad`. */
export interface Hueco {
  inicio: string;
  fin: string;
  profesionalId: string;
  sillonId: string;
}

/**
 * Alternativa de un `409`. El contrato solo envía `inicio`/`fin`; no se
 * completan `profesionalId`/`sillonId` para no inventar datos.
 */
export interface AlternativaHueco {
  inicio: string;
  fin: string;
}

/** Turno propio devuelto por el `201` de reserva. */
export interface ReservaCreada {
  turnoId: string;
  estado: string;
  inicio: string;
  fin: string;
  origen: string;
  prestacion: string;
  sillonId: string;
  tokenPublico: string;
}

/** Turno propio consultado/gestionado con el token público. */
export interface ReservaPropia {
  turnoId: string;
  estado: string;
  inicio: string;
  fin: string;
  prestacion: string;
  tokenPublico: string;
}

/** Verificación anti-spam single-use. */
export interface Verificacion {
  verificacionId: string;
  expiraAt: string;
  canal: string;
}

/** Cuerpo de error del dominio público. */
export interface ErrorPublico {
  detalle: string;
  alternativas: AlternativaHueco[];
}

/** Resultado del cliente público, con metadatos extra del contrato. */
export interface ReservaApiResult<T> extends ApiResult<T> {
  alternativas?: AlternativaHueco[];
  retryAfterSeconds?: number;
}

export interface ReservaPayload {
  prestacion: string;
  profesional: string;
  inicio: string;
  nombre: string;
  telefono: string;
  verificacionId: string;
}

export interface DisponibilidadQuery {
  prestacion: string;
  profesional?: string;
  desde: string;
}

export type AccionPublica = 'reservar' | 'cancelar' | 'reprogramar';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

function texto(valor: unknown): string | null {
  return typeof valor === 'string' && valor.length > 0 ? valor : null;
}

function numero(valor: unknown): number | null {
  return typeof valor === 'number' && Number.isFinite(valor) ? valor : null;
}

function mensajePorStatus(status: number): string {
  switch (status) {
    case 403:
      return 'La verificación no es válida o venció.';
    case 404:
      return 'No encontramos el recurso pedido.';
    case 409:
      return 'Ese horario ya no está disponible.';
    case 422:
      return 'Revisá los datos enviados e intentá nuevamente.';
    case 429:
      return 'Hiciste muchos intentos seguidos.';
    default:
      return 'No pudimos completar la operación.';
  }
}

function mapearPrestacion(valor: unknown): PrestacionPublica | null {
  if (!isRecord(valor)) {
    return null;
  }
  const id = texto(valor.id);
  const nombre = texto(valor.nombre);
  const duracionMin = numero(valor.duracion_min);
  if (id === null || nombre === null || duracionMin === null) {
    return null;
  }
  return { id, nombre, duracionMin };
}

function mapearProfesional(valor: unknown): ProfesionalPublico | null {
  if (!isRecord(valor)) {
    return null;
  }
  const id = texto(valor.id);
  const nombre = texto(valor.nombre);
  if (id === null || nombre === null) {
    return null;
  }
  return { id, nombre };
}

function mapearHueco(valor: unknown): Hueco | null {
  if (!isRecord(valor)) {
    return null;
  }
  const inicio = texto(valor.inicio);
  const fin = texto(valor.fin);
  const profesionalId = texto(valor.profesional_id);
  const sillonId = texto(valor.sillon_id);
  if (inicio === null || fin === null || profesionalId === null || sillonId === null) {
    return null;
  }
  return { inicio, fin, profesionalId, sillonId };
}

function mapearAlternativa(valor: unknown): AlternativaHueco | null {
  if (!isRecord(valor)) {
    return null;
  }
  const inicio = texto(valor.inicio);
  const fin = texto(valor.fin);
  if (inicio === null || fin === null) {
    return null;
  }
  return { inicio, fin };
}

function mapearReservaCreada(valor: unknown): ReservaCreada | null {
  if (!isRecord(valor)) {
    return null;
  }
  const turnoId = texto(valor.turno_id);
  const estado = texto(valor.estado);
  const inicio = texto(valor.inicio);
  const fin = texto(valor.fin);
  const origen = texto(valor.origen);
  const prestacion = texto(valor.prestacion);
  const sillonId = texto(valor.sillon_id);
  const tokenPublico = texto(valor.token_publico);
  if (
    turnoId === null ||
    estado === null ||
    inicio === null ||
    fin === null ||
    origen === null ||
    prestacion === null ||
    sillonId === null ||
    tokenPublico === null
  ) {
    return null;
  }
  return { turnoId, estado, inicio, fin, origen, prestacion, sillonId, tokenPublico };
}

function mapearReservaPropia(valor: unknown): ReservaPropia | null {
  if (!isRecord(valor)) {
    return null;
  }
  const turnoId = texto(valor.turno_id);
  const estado = texto(valor.estado);
  const inicio = texto(valor.inicio);
  const fin = texto(valor.fin);
  const prestacion = texto(valor.prestacion);
  const tokenPublico = texto(valor.token_publico);
  if (
    turnoId === null ||
    estado === null ||
    inicio === null ||
    fin === null ||
    prestacion === null ||
    tokenPublico === null
  ) {
    return null;
  }
  return { turnoId, estado, inicio, fin, prestacion, tokenPublico };
}

function mapearLista<T>(valor: unknown, mapear: (item: unknown) => T | null): T[] {
  if (!Array.isArray(valor)) {
    return [];
  }
  const resultado: T[] = [];
  for (const item of valor) {
    const mapeado = mapear(item);
    if (mapeado !== null) {
      resultado.push(mapeado);
    }
  }
  return resultado;
}

async function leerCuerpo(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

async function leerError(
  response: Response,
): Promise<{ detalle: string; alternativas: AlternativaHueco[]; retryAfterSeconds?: number }> {
  const body = await leerCuerpo(response);
  const detalle =
    isRecord(body) && typeof body.detalle === 'string' && body.detalle.length > 0
      ? body.detalle
      : mensajePorStatus(response.status);
  const alternativas =
    isRecord(body) && Array.isArray(body.alternativas)
      ? mapearLista(body.alternativas, mapearAlternativa)
      : [];
  const retryHeader = response.headers.get('Retry-After');
  const retryNumero = retryHeader === null ? Number.NaN : Number(retryHeader);
  return {
    detalle,
    alternativas,
    ...(Number.isFinite(retryNumero) && retryNumero > 0
      ? { retryAfterSeconds: retryNumero }
      : {}),
  };
}

function basePublica(tokenTenant: string): string {
  return `${apiBaseUrl}/publico/${encodeURIComponent(tokenTenant)}`;
}

function errorDeRed<T>(): ReservaApiResult<T> {
  return {
    ok: false,
    error: 'No pudimos conectar con el servidor. Revisá tu conexión y volvé a intentar.',
  };
}

/** `GET /api/publico/{tokenTenant}/catalogo` con allow-list estricta. */
export async function catalogo(
  tokenTenant: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<CatalogoPublico>> {
  try {
    const response = await fetchImpl(`${basePublica(tokenTenant)}/catalogo`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      const { detalle, retryAfterSeconds } = await leerError(response);
      return { ok: false, status: response.status, error: detalle, retryAfterSeconds };
    }
    const body = await leerCuerpo(response);
    if (!isRecord(body)) {
      return { ok: false, error: 'Respuesta inválida del catálogo público.' };
    }
    return {
      ok: true,
      data: {
        prestaciones: mapearLista(body.prestaciones, mapearPrestacion),
        profesionales: mapearLista(body.profesionales, mapearProfesional),
      },
    };
  } catch {
    return errorDeRed();
  }
}

/** `GET /api/publico/{tokenTenant}/disponibilidad` — huecos reales del servidor. */
export async function disponibilidad(
  tokenTenant: string,
  query: DisponibilidadQuery,
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<Hueco[]>> {
  const params = new URLSearchParams({
    prestacion: query.prestacion,
    desde: query.desde,
  });
  if (query.profesional !== undefined && query.profesional.length > 0) {
    params.set('profesional', query.profesional);
  }
  try {
    const response = await fetchImpl(
      `${basePublica(tokenTenant)}/disponibilidad?${params.toString()}`,
      { headers: { Accept: 'application/json' } },
    );
    if (!response.ok) {
      const { detalle, retryAfterSeconds } = await leerError(response);
      return { ok: false, status: response.status, error: detalle, retryAfterSeconds };
    }
    const body = await leerCuerpo(response);
    if (!Array.isArray(body)) {
      return { ok: false, error: 'Respuesta inválida de disponibilidad.' };
    }
    return { ok: true, data: mapearLista(body, mapearHueco) };
  } catch {
    return errorDeRed();
  }
}

/** `POST /api/publico/{tokenTenant}/verificacion` — verificación single-use. */
export async function emitirVerificacion(
  tokenTenant: string,
  payload: { accion: AccionPublica },
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<Verificacion>> {
  try {
    const response = await fetchImpl(`${basePublica(tokenTenant)}/verificacion`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ accion: payload.accion }),
    });
    if (!response.ok) {
      const { detalle, retryAfterSeconds } = await leerError(response);
      return { ok: false, status: response.status, error: detalle, retryAfterSeconds };
    }
    const body = await leerCuerpo(response);
    if (!isRecord(body)) {
      return { ok: false, error: 'Respuesta inválida de verificación.' };
    }
    const verificacionId = texto(body.verificacion_id);
    const expiraAt = texto(body.expira_at);
    const canal = texto(body.canal);
    if (verificacionId === null || expiraAt === null || canal === null) {
      return { ok: false, error: 'Respuesta inválida de verificación.' };
    }
    return { ok: true, data: { verificacionId, expiraAt, canal } };
  } catch {
    return errorDeRed();
  }
}

/** `POST /api/publico/{tokenTenant}/reservas` — payload strict de C-06. */
export async function reservar(
  tokenTenant: string,
  payload: ReservaPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<ReservaCreada>> {
  try {
    const response = await fetchImpl(`${basePublica(tokenTenant)}/reservas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        prestacion: payload.prestacion,
        profesional: payload.profesional,
        inicio: payload.inicio,
        nombre: payload.nombre,
        telefono: payload.telefono,
        verificacion_id: payload.verificacionId,
      }),
    });
    if (!response.ok) {
      const { detalle, alternativas, retryAfterSeconds } = await leerError(response);
      return {
        ok: false,
        status: response.status,
        error: detalle,
        alternativas,
        retryAfterSeconds,
      };
    }
    const body = await leerCuerpo(response);
    const reserva = mapearReservaCreada(body);
    if (reserva === null) {
      return { ok: false, error: 'Respuesta inválida de la reserva.' };
    }
    return { ok: true, data: reserva };
  } catch {
    return errorDeRed();
  }
}

/** `GET /api/publico/{tokenTenant}/reservas/{token}` — solo el turno propio. */
export async function consultarReserva(
  tokenTenant: string,
  token: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<ReservaPropia>> {
  try {
    const response = await fetchImpl(
      `${basePublica(tokenTenant)}/reservas/${encodeURIComponent(token)}`,
      { headers: { Accept: 'application/json' } },
    );
    if (!response.ok) {
      const { detalle, retryAfterSeconds } = await leerError(response);
      return { ok: false, status: response.status, error: detalle, retryAfterSeconds };
    }
    const reserva = mapearReservaPropia(await leerCuerpo(response));
    if (reserva === null) {
      return { ok: false, error: 'Respuesta inválida del turno.' };
    }
    return { ok: true, data: reserva };
  } catch {
    return errorDeRed();
  }
}

/** `POST .../reservas/{token}/cancelacion` con verificación single-use. */
export async function cancelar(
  tokenTenant: string,
  token: string,
  payload: { verificacionId: string },
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<ReservaPropia>> {
  try {
    const response = await fetchImpl(
      `${basePublica(tokenTenant)}/reservas/${encodeURIComponent(token)}/cancelacion`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ verificacion_id: payload.verificacionId }),
      },
    );
    if (!response.ok) {
      const { detalle, retryAfterSeconds } = await leerError(response);
      return { ok: false, status: response.status, error: detalle, retryAfterSeconds };
    }
    const reserva = mapearReservaPropia(await leerCuerpo(response));
    if (reserva === null) {
      return { ok: false, error: 'Respuesta inválida de la cancelación.' };
    }
    return { ok: true, data: reserva };
  } catch {
    return errorDeRed();
  }
}

/**
 * `POST .../reservas/{token}/reprogramacion` con verificación single-use.
 * El backend responde `{ original, nuevo }`; se devuelve el turno nuevo con el
 * mismo token de gestión.
 */
export async function reprogramar(
  tokenTenant: string,
  token: string,
  payload: { nuevoInicio: string; verificacionId: string },
  fetchImpl: typeof fetch = fetch,
): Promise<ReservaApiResult<ReservaPropia>> {
  try {
    const response = await fetchImpl(
      `${basePublica(tokenTenant)}/reservas/${encodeURIComponent(token)}/reprogramacion`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({
          nuevo_inicio: payload.nuevoInicio,
          verificacion_id: payload.verificacionId,
        }),
      },
    );
    if (!response.ok) {
      const { detalle, alternativas, retryAfterSeconds } = await leerError(response);
      return {
        ok: false,
        status: response.status,
        error: detalle,
        alternativas,
        retryAfterSeconds,
      };
    }
    const body = await leerCuerpo(response);
    if (!isRecord(body)) {
      return { ok: false, error: 'Respuesta inválida de la reprogramación.' };
    }
    const reserva = mapearReservaPropia(body.nuevo);
    if (reserva === null) {
      return { ok: false, error: 'Respuesta inválida de la reprogramación.' };
    }
    return { ok: true, data: reserva };
  } catch {
    return errorDeRed();
  }
}
