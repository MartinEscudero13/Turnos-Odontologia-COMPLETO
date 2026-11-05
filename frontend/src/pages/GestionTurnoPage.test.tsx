import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { GestionTurnoPage } from './GestionTurnoPage';

const CATALOGO = {
  prestaciones: [{ id: 'PREST-30', nombre: 'Consulta', duracion_min: 30 }],
  profesionales: [{ id: 'P1', nombre: 'Dra. Demo' }],
};

const TURNO = {
  turno_id: 'TURNO-1',
  estado: 'PENDIENTE',
  inicio: '2026-10-06T09:00:00-03:00',
  fin: '2026-10-06T09:30:00-03:00',
  prestacion: 'PREST-30',
  token_publico: 'TOK-B',
};

const HUECOS = [
  {
    inicio: '2026-10-06T10:00:00-03:00',
    fin: '2026-10-06T10:30:00-03:00',
    profesional_id: 'P1',
    sillon_id: 'S2',
  },
];

type Responder = (url: string, init: RequestInit | undefined) => Response | Promise<Response>;

function jsonResponse(body: unknown, status = 200, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', ...headers },
  });
}

function instalarFetch(rutas: Array<[string, Responder]>): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const encontrada = rutas.find(([fragmento]) => url.includes(fragmento));
      if (!encontrada) {
        return jsonResponse({ detalle: 'ruta no simulada' }, 500);
      }
      return encontrada[1](url, init);
    }),
  );
}

function rutasBase(extra: Array<[string, Responder]> = []): Array<[string, Responder]> {
  return [
    ...extra,
    ['/catalogo', async () => jsonResponse(CATALOGO)],
    ['/reservas/TOK-B/reprogramacion', async () => jsonResponse({})],
    ['/reservas/TOK-B/cancelacion', async () => jsonResponse({})],
    ['/reservas/TOK-B', async () => jsonResponse(TURNO)],
  ];
}

function verificacionOk(accionEsperada?: string): [string, Responder] {
  return [
    '/verificacion',
    async (_url, init) => {
      const cuerpo = JSON.parse(String(init?.body)) as { accion?: string };
      if (accionEsperada && cuerpo.accion !== accionEsperada) {
        return jsonResponse({ detalle: 'acción inesperada' }, 422);
      }
      return jsonResponse(
        { verificacion_id: 'VER-G', expira_at: '2026-10-06T09:10:00-03:00', canal: 'captcha' },
        201,
      );
    },
  ];
}

function renderGestion(path = '/r/T1/turno/TOK-B'): void {
  render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/r/:tokenTenant/turno/:token" element={<GestionTurnoPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('GestionTurnoPage', () => {
  it('consulta y muestra el turno propio por token', async () => {
    instalarFetch(rutasBase());
    renderGestion();

    expect(await screen.findByText(/martes 06\.10/)).toBeInTheDocument();
    expect(screen.getByText(/09:00/)).toBeInTheDocument();
    expect(screen.getByText('Pendiente')).toBeInTheDocument();
    expect(screen.getByText(/Consulta/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Cancelar turno/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Reprogramar/i })).toBeInTheDocument();
  });

  it('cancela con anticipación y muestra el estado cancelado', async () => {
    instalarFetch([
      ...rutasBase([
        verificacionOk('cancelar'),
        [
          '/reservas/TOK-B/cancelacion',
          async () => jsonResponse({ ...TURNO, estado: 'CANCELADO' }),
        ],
      ]),
    ]);
    renderGestion();
    await screen.findByText(/martes 06\.10/);

    fireEvent.click(screen.getByRole('button', { name: /Cancelar turno/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Sí, cancelar/i }));

    expect(await screen.findByText('Cancelado')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reprogramar/i })).not.toBeInTheDocument();
  });

  it('reprograma con anticipación y muestra el horario nuevo', async () => {
    let cuerpo: unknown = null;
    instalarFetch([
      ...rutasBase([
        ['/disponibilidad', async () => jsonResponse(HUECOS)],
        verificacionOk('reprogramar'),
        [
          '/reservas/TOK-B/reprogramacion',
          async (_url, init) => {
            cuerpo = JSON.parse(String(init?.body));
            return jsonResponse({
              original: { ...TURNO, estado: 'REPROGRAMADO' },
              nuevo: {
                ...TURNO,
                turno_id: 'TURNO-2',
                inicio: '2026-10-06T10:00:00-03:00',
                fin: '2026-10-06T10:30:00-03:00',
              },
            });
          },
        ],
      ]),
    ]);
    renderGestion();
    await screen.findByText(/martes 06\.10/);

    fireEvent.click(screen.getByRole('button', { name: /Reprogramar/i }));
    fireEvent.click(await screen.findByRole('option', { name: /10:00/ }));

    await waitFor(() =>
      expect(screen.queryByRole('listbox', { name: /reprogramar/i })).not.toBeInTheDocument(),
    );
    expect(screen.getByText(/10:00/)).toBeInTheDocument();
    expect(cuerpo).toMatchObject({
      nuevo_inicio: '2026-10-06T10:00:00-03:00',
      verificacion_id: 'VER-G',
    });
  });

  it('bajo el umbral deriva a recepción sin mutar el horario', async () => {
    instalarFetch([
      ...rutasBase([
        verificacionOk('cancelar'),
        [
          '/reservas/TOK-B/cancelacion',
          async () => jsonResponse({ detalle: 'bajo anticipación', alternativas: [] }, 403),
        ],
      ]),
    ]);
    renderGestion();
    await screen.findByText(/martes 06\.10/);

    fireEvent.click(screen.getByRole('button', { name: /Cancelar turno/i }));
    fireEvent.click(await screen.findByRole('button', { name: /Sí, cancelar/i }));

    expect(
      await screen.findByText(/Gestioná este turno en el consultorio/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/09:00/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reprogramar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Cancelar turno/i })).not.toBeInTheDocument();
  });

  it('permite copiar el token de gestión por botón', async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    });
    instalarFetch(rutasBase());
    renderGestion();
    await screen.findByText(/martes 06\.10/);

    fireEvent.click(screen.getByRole('button', { name: /Copiar código/i }));

    expect(writeText).toHaveBeenCalledWith('TOK-B');
    expect(await screen.findByText(/Código copiado/i)).toBeInTheDocument();
  });

  it('solo muestra los datos del turno propio sin PHI de terceros', async () => {
    instalarFetch([
      ...rutasBase([
        [
          '/reservas/TOK-B',
          async () =>
            jsonResponse({
              ...TURNO,
              paciente_nombre: 'Otro Paciente',
              telefono: '+54 9 11 1111 1111',
              paciente_id: 'PAC-9',
            }),
        ],
      ]),
    ]);
    renderGestion();

    expect(await screen.findByText(/martes 06\.10/)).toBeInTheDocument();
    expect(screen.queryByText(/Otro Paciente/)).not.toBeInTheDocument();
    expect(screen.queryByText(/1111 1111/)).not.toBeInTheDocument();
    expect(screen.queryByText(/PAC-9/)).not.toBeInTheDocument();
  });
});
