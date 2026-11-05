import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  cancelar,
  catalogo,
  consultarReserva,
  disponibilidad,
  emitirVerificacion,
  reprogramar,
  reservar,
} from './reservaPublicaClient';

type FetchMock = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

function crearFetch(handler: FetchMock): typeof fetch {
  return vi.fn(handler) as unknown as typeof fetch;
}

function primerRequest(fetchMock: typeof fetch): { url: string; init: RequestInit | undefined } {
  const calls = (fetchMock as unknown as { mock: { calls: [RequestInfo | URL, RequestInit?][] } }).mock
    .calls;
  const [input, init] = calls[0];
  return { url: String(input), init };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('reservaPublicaClient', () => {
  it('mapea el catálogo con allow-list y descarta claves extra', async () => {
    const fetchMock = crearFetch(async () =>
      jsonResponse({
        tenant_id: 'T1',
        prestaciones: [
          { id: 'PREST-30', nombre: 'Consulta', duracion_min: 30, precio_base: 1000 },
        ],
        profesionales: [{ id: 'P1', nombre: 'Dra. Demo', email: 'demo@test' }],
      }),
    );

    const result = await catalogo('T1', fetchMock);

    expect(result.ok).toBe(true);
    expect(result.data).toEqual({
      prestaciones: [{ id: 'PREST-30', nombre: 'Consulta', duracionMin: 30 }],
      profesionales: [{ id: 'P1', nombre: 'Dra. Demo' }],
    });
    expect(primerRequest(fetchMock).url).toBe('/api/publico/T1/catalogo');
  });

  it('mapea los huecos de disponibilidad con allow-list', async () => {
    const fetchMock = crearFetch(async () =>
      jsonResponse([
        {
          inicio: '2026-10-06T09:00:00-03:00',
          fin: '2026-10-06T09:30:00-03:00',
          profesional_id: 'P1',
          sillon_id: 'S1',
          paciente_id: 'PAC-1',
          paciente_nombre: 'Otro Paciente',
        },
      ]),
    );

    const result = await disponibilidad('T1', {
      prestacion: 'PREST-30',
      desde: '2026-10-06T08:00:00-03:00',
    }, fetchMock);

    expect(result.ok).toBe(true);
    expect(result.data).toEqual([
      {
        inicio: '2026-10-06T09:00:00-03:00',
        fin: '2026-10-06T09:30:00-03:00',
        profesionalId: 'P1',
        sillonId: 'S1',
      },
    ]);
    const { url } = primerRequest(fetchMock);
    expect(url).toContain('/api/publico/T1/disponibilidad?');
    expect(url).toContain('prestacion=PREST-30');
    expect(url).toContain('desde=');
    expect(url).not.toContain('paciente');
  });

  it('mapea 409 de reservar con alternativas y detalle', async () => {
    const fetchMock = crearFetch(async () =>
      jsonResponse(
        {
          detalle: 'El horario ya no está disponible.',
          alternativas: [{ inicio: '2026-10-06T09:30:00-03:00', fin: '2026-10-06T10:00:00-03:00' }],
        },
        409,
      ),
    );

    const result = await reservar(
      'T1',
      {
        prestacion: 'PREST-30',
        profesional: 'P1',
        inicio: '2026-10-06T09:00:00-03:00',
        nombre: 'Paciente Demo',
        telefono: '+54 9 11 0000 0000',
        verificacionId: 'VER-1',
      },
      fetchMock,
    );

    expect(result.ok).toBe(false);
    expect(result.status).toBe(409);
    expect(result.alternativas).toEqual([
      { inicio: '2026-10-06T09:30:00-03:00', fin: '2026-10-06T10:00:00-03:00' },
    ]);
    expect(result.error).toBe('El horario ya no está disponible.');
  });

  it('envía el payload de reserva en snake_case y sin claves extra', async () => {
    const fetchMock = crearFetch(async () =>
      jsonResponse(
        {
          turno_id: 'TURNO-1',
          estado: 'PENDIENTE',
          inicio: '2026-10-06T09:00:00-03:00',
          fin: '2026-10-06T09:30:00-03:00',
          origen: 'PUBLICO',
          prestacion: 'PREST-30',
          sillon_id: 'S1',
          token_publico: 'TOK-1',
          paciente_id: 'PAC-1',
        },
        201,
      ),
    );

    const result = await reservar(
      'T1',
      {
        prestacion: 'PREST-30',
        profesional: 'P1',
        inicio: '2026-10-06T09:00:00-03:00',
        nombre: 'Paciente Demo',
        telefono: '+54 9 11 0000 0000',
        verificacionId: 'VER-1',
      },
      fetchMock,
    );

    expect(result.ok).toBe(true);
    expect(result.data?.tokenPublico).toBe('TOK-1');
    const { init } = primerRequest(fetchMock);
    expect(init?.method).toBe('POST');
    expect(JSON.parse(String(init?.body))).toEqual({
      prestacion: 'PREST-30',
      profesional: 'P1',
      inicio: '2026-10-06T09:00:00-03:00',
      nombre: 'Paciente Demo',
      telefono: '+54 9 11 0000 0000',
      verificacion_id: 'VER-1',
    });
  });

  it('mapea verificación, consulta, cancelación y reprogramación', async () => {
    const respuestas: Array<() => Response> = [
      () => jsonResponse({ verificacion_id: 'VER-1', expira_at: '2026-10-06T09:10:00-03:00', canal: 'captcha' }, 201),
      () =>
        jsonResponse({
          turno_id: 'TURNO-1',
          estado: 'PENDIENTE',
          inicio: '2026-10-06T09:00:00-03:00',
          fin: '2026-10-06T09:30:00-03:00',
          prestacion: 'PREST-30',
          token_publico: 'TOK-1',
        }),
      () =>
        jsonResponse({
          turno_id: 'TURNO-1',
          estado: 'CANCELADO',
          inicio: '2026-10-06T09:00:00-03:00',
          fin: '2026-10-06T09:30:00-03:00',
          prestacion: 'PREST-30',
          token_publico: 'TOK-1',
        }),
      () =>
        jsonResponse({
          original: {
            turno_id: 'TURNO-1',
            estado: 'REPROGRAMADO',
            inicio: '2026-10-06T09:00:00-03:00',
            fin: '2026-10-06T09:30:00-03:00',
            prestacion: 'PREST-30',
            token_publico: 'TOK-1',
          },
          nuevo: {
            turno_id: 'TURNO-2',
            estado: 'PENDIENTE',
            inicio: '2026-10-06T10:00:00-03:00',
            fin: '2026-10-06T10:30:00-03:00',
            prestacion: 'PREST-30',
            token_publico: 'TOK-1',
          },
        }),
    ];
    const fetchMock = crearFetch(async () => respuestas.shift()?.() ?? jsonResponse({}, 500));

    const verificacion = await emitirVerificacion('T1', { accion: 'reservar' }, fetchMock);
    expect(verificacion.data).toEqual({
      verificacionId: 'VER-1',
      expiraAt: '2026-10-06T09:10:00-03:00',
      canal: 'captcha',
    });

    const consulta = await consultarReserva('T1', 'TOK-1', fetchMock);
    expect(consulta.data?.estado).toBe('PENDIENTE');

    const cancelada = await cancelar('T1', 'TOK-1', { verificacionId: 'VER-2' }, fetchMock);
    expect(cancelada.data?.estado).toBe('CANCELADO');

    const reprogramada = await reprogramar(
      'T1',
      'TOK-1',
      { nuevoInicio: '2026-10-06T10:00:00-03:00', verificacionId: 'VER-3' },
      fetchMock,
    );
    expect(reprogramada.data?.inicio).toBe('2026-10-06T10:00:00-03:00');
    expect(reprogramada.data?.turnoId).toBe('TURNO-2');
  });

  it('mapea 429 con Retry-After sin reintentar', async () => {
    const fetchMock = crearFetch(async () =>
      jsonResponse({ detalle: 'Demasiadas solicitudes.' }, 429, { 'Retry-After': '120' }),
    );

    const result = await reservar(
      'T1',
      {
        prestacion: 'PREST-30',
        profesional: 'P1',
        inicio: '2026-10-06T09:00:00-03:00',
        nombre: 'Paciente Demo',
        telefono: '+54 9 11 0000 0000',
        verificacionId: 'VER-1',
      },
      fetchMock,
    );

    expect(result.ok).toBe(false);
    expect(result.status).toBe(429);
    expect(result.retryAfterSeconds).toBe(120);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('no loguea token, nombre ni teléfono', async () => {
    const spies = (['log', 'warn', 'error', 'info', 'debug'] as const).map((metodo) =>
      vi.spyOn(console, metodo).mockImplementation(() => undefined),
    );
    const fetchMock = crearFetch(async () =>
      jsonResponse(
        {
          turno_id: 'TURNO-1',
          estado: 'PENDIENTE',
          inicio: '2026-10-06T09:00:00-03:00',
          fin: '2026-10-06T09:30:00-03:00',
          origen: 'PUBLICO',
          prestacion: 'PREST-30',
          sillon_id: 'S1',
          token_publico: 'TOK-SECRETO',
        },
        201,
      ),
    );

    await reservar(
      'T1',
      {
        prestacion: 'PREST-30',
        profesional: 'P1',
        inicio: '2026-10-06T09:00:00-03:00',
        nombre: 'Paciente Demo',
        telefono: '+54 9 11 0000 0000',
        verificacionId: 'VER-1',
      },
      fetchMock,
    );

    expect(spies.every((spy) => spy.mock.calls.length === 0)).toBe(true);
  });
});
