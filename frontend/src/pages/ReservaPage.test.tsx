import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useParams } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ReservaPage } from './ReservaPage';

const CATALOGO = {
  prestaciones: [
    { id: 'PREST-30', nombre: 'Consulta', duracion_min: 30 },
    { id: 'PREST-45', nombre: 'Limpieza', duracion_min: 45 },
  ],
  profesionales: [{ id: 'P1', nombre: 'Dra. Demo' }],
};

const HUECOS = [
  {
    inicio: '2026-10-06T09:00:00-03:00',
    fin: '2026-10-06T09:30:00-03:00',
    profesional_id: 'P1',
    sillon_id: 'S1',
  },
  {
    inicio: '2026-10-06T10:00:00-03:00',
    fin: '2026-10-06T10:30:00-03:00',
    profesional_id: 'P1',
    sillon_id: 'S2',
  },
];

const RESERVA_CREADA = {
  turno_id: 'TURNO-1',
  estado: 'PENDIENTE',
  inicio: '2026-10-06T09:00:00-03:00',
  fin: '2026-10-06T09:30:00-03:00',
  origen: 'PUBLICO',
  prestacion: 'PREST-30',
  sillon_id: 'S1',
  token_publico: 'TOK-1',
};

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

function catalogoOk(): [string, Responder] {
  return ['/catalogo', async () => jsonResponse(CATALOGO)];
}

function disponibilidadOk(huecos: unknown = HUECOS): [string, Responder] {
  return ['/disponibilidad', async () => jsonResponse(huecos)];
}

function verificacionOk(): [string, Responder] {
  return [
    '/verificacion',
    async () =>
      jsonResponse(
        { verificacion_id: 'VER-1', expira_at: '2026-10-06T09:10:00-03:00', canal: 'captcha' },
        201,
      ),
  ];
}

function DestinoGestion(): JSX.Element {
  const { token } = useParams();
  return <p>Gestión del turno {token}</p>;
}

function renderReserva(path = '/r/T1'): void {
  render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/r/:tokenTenant" element={<ReservaPage />} />
        <Route path="/r/:tokenTenant/turno/:token" element={<DestinoGestion />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function elegirPrestacion(): Promise<void> {
  fireEvent.click(await screen.findByRole('button', { name: /Consulta/ }));
  await screen.findByRole('option', { name: /09:00/ });
}

async function elegirHuecoYContinuar(): Promise<void> {
  fireEvent.click(screen.getByRole('option', { name: /09:00/ }));
  fireEvent.click(screen.getByRole('button', { name: /Continuar con nombre y teléfono/i }));
  await screen.findByLabelText('Nombre');
}

async function completarFormulario(): Promise<void> {
  fireEvent.change(screen.getByLabelText('Nombre'), { target: { value: 'Paciente Demo' } });
  fireEvent.change(screen.getByLabelText('Teléfono'), {
    target: { value: '+54 9 11 0000 0000' },
  });
  fireEvent.click(screen.getByRole('checkbox', { name: /No soy un robot/i }));
  await waitFor(() =>
    expect(screen.getByRole('button', { name: /Reservar turno/i })).toBeEnabled(),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ReservaPage', () => {
  it('muestra las prestaciones del catálogo con nombre, duración y profesional', async () => {
    instalarFetch([catalogoOk()]);
    renderReserva();

    expect(await screen.findByText('Consulta')).toBeInTheDocument();
    expect(screen.getByText('Limpieza')).toBeInTheDocument();
    expect(screen.getByText('30 min')).toBeInTheDocument();
    expect(screen.getByText('45 min')).toBeInTheDocument();
    expect(screen.getByText(/Dra\. Demo/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Consulta/ })).toHaveClass('prest-option');
  });

  it('con catálogo vacío muestra una salida sin habilitar reservas', async () => {
    instalarFetch([
      ['/catalogo', async () => jsonResponse({ prestaciones: [], profesionales: [] })],
    ]);
    renderReserva();

    expect(
      await screen.findByRole('heading', { name: /todavía no publicó prestaciones/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Volver al inicio/i })).toHaveAttribute('href', '/');
    expect(screen.queryByRole('button', { name: /Reservar turno/i })).not.toBeInTheDocument();
  });

  it('con tokenTenant inexistente muestra enlace inválido sin datos', async () => {
    instalarFetch([['/catalogo', async () => jsonResponse({ detalle: 'recurso no encontrado' }, 404)]]);
    renderReserva('/r/NO-EXISTE');

    expect(
      await screen.findByRole('heading', { name: /no corresponde a un consultorio activo/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText('Consulta')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Reservar turno/i })).not.toBeInTheDocument();
  });

  it('renderiza los huecos como franjas horarias con hora y duración', async () => {
    instalarFetch([catalogoOk(), disponibilidadOk()]);
    renderReserva();
    await elegirPrestacion();

    const manana = screen.getByRole('option', { name: /09:00/ });
    const diez = screen.getByRole('option', { name: /10:00/ });
    expect(manana).toHaveClass('slot');
    expect(manana).toHaveTextContent('30 min');
    expect(diez).toBeInTheDocument();
  });

  it('sin huecos muestra estado vacío con salida', async () => {
    instalarFetch([catalogoOk(), disponibilidadOk([])]);
    renderReserva();
    fireEvent.click(await screen.findByRole('button', { name: /Consulta/ }));

    expect(await screen.findByRole('heading', { name: /No hay horarios disponibles/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Elegir otra prestación/i })).toBeInTheDocument();
  });

  it('anuncia la carga de huecos y no habilita la reserva', async () => {
    let resolver: ((respuesta: Response) => void) | undefined;
    const pendiente = new Promise<Response>((resolve) => {
      resolver = resolve;
    });
    instalarFetch([catalogoOk(), ['/disponibilidad', async () => pendiente]]);
    renderReserva();

    fireEvent.click(await screen.findByRole('button', { name: /Consulta/ }));

    const estado = await screen.findByRole('status');
    expect(estado).toHaveAttribute('aria-busy', 'true');
    expect(estado).toHaveTextContent(/Buscando horarios disponibles/i);
    expect(screen.queryByRole('button', { name: /Reservar turno/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Continuar/i })).not.toBeInTheDocument();

    resolver?.(jsonResponse(HUECOS));
    await screen.findByRole('option', { name: /09:00/ });
  });

  it('muestra el formulario con labels persistentes y autocmplete correcto', async () => {
    instalarFetch([catalogoOk(), disponibilidadOk()]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();

    const nombre = screen.getByLabelText('Nombre');
    const telefono = screen.getByLabelText('Teléfono');
    expect(nombre).toHaveAttribute('autocomplete', 'name');
    expect(telefono).toHaveAttribute('type', 'tel');
    expect(telefono).toHaveAttribute('inputmode', 'tel');
    expect(telefono).toHaveAttribute('autocomplete', 'tel');
    expect(screen.getByRole('button', { name: /Reservar turno/i })).toBeDisabled();
  });

  it('emite la verificación y envía el verificacion_id al reservar', async () => {
    let cuerpoReserva: unknown = null;
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      verificacionOk(),
      [
        '/reservas',
        async (_url, init) => {
          cuerpoReserva = JSON.parse(String(init?.body));
          return jsonResponse(RESERVA_CREADA, 201);
        },
      ],
    ]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();
    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));

    expect(await screen.findByText(/Gestión del turno TOK-1/)).toBeInTheDocument();
    expect(cuerpoReserva).toMatchObject({
      prestacion: 'PREST-30',
      profesional: 'P1',
      inicio: '2026-10-06T09:00:00-03:00',
      nombre: 'Paciente Demo',
      telefono: '+54 9 11 0000 0000',
      verificacion_id: 'VER-1',
    });
  });

  it('con 422 asocia el error al teléfono y no navega', async () => {
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      verificacionOk(),
      ['/reservas', async () => jsonResponse({ detalle: 'Teléfono inválido', alternativas: [] }, 422)],
    ]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();
    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));

    await waitFor(() =>
      expect(screen.getByLabelText('Teléfono')).toHaveAttribute('aria-invalid', 'true'),
    );
    expect(screen.getByText(/Revisá el teléfono/i)).toBeInTheDocument();
    expect(screen.queryByText(/Gestión del turno/i)).not.toBeInTheDocument();
  });

  it('con 403 de verificación inválida permite reintentar sin crear turno', async () => {
    let verificaciones = 0;
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      [
        '/verificacion',
        async () => {
          verificaciones += 1;
          return jsonResponse(
            {
              verificacion_id: `VER-${verificaciones}`,
              expira_at: '2026-10-06T09:10:00-03:00',
              canal: 'captcha',
            },
            201,
          );
        },
      ],
      ['/reservas', async () => jsonResponse({ detalle: 'verificación vencida', alternativas: [] }, 403)],
    ]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();
    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/verificación/i);
    fireEvent.click(screen.getByRole('button', { name: /Reintentar la verificación/i }));
    await waitFor(() => expect(verificaciones).toBe(2));
    expect(screen.queryByText(/Gestión del turno/i)).not.toBeInTheDocument();
  });

  it('con 409 muestra hasta tres alternativas seleccionables sin crear turno', async () => {
    const alternativas = [
      { inicio: '2026-10-06T09:30:00-03:00', fin: '2026-10-06T10:00:00-03:00' },
      { inicio: '2026-10-06T11:00:00-03:00', fin: '2026-10-06T11:30:00-03:00' },
      { inicio: '2026-10-06T12:00:00-03:00', fin: '2026-10-06T12:30:00-03:00' },
      { inicio: '2026-10-06T13:00:00-03:00', fin: '2026-10-06T13:30:00-03:00' },
    ];
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      verificacionOk(),
      [
        '/reservas',
        async () => jsonResponse({ detalle: 'El horario ya no está libre.', alternativas }, 409),
      ],
    ]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();
    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));

    const lista = await screen.findByRole('listbox', { name: /alternativos/i });
    expect(lista).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /09:30/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /11:00/ })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: /12:00/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /13:00/ })).not.toBeInTheDocument();
    expect(screen.queryByText(/Gestión del turno/i)).not.toBeInTheDocument();
  });

  it('con 429 respeta Retry-After sin reintentar solo', async () => {
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      verificacionOk(),
      [
        '/reservas',
        async () => jsonResponse({ detalle: 'Demasiadas solicitudes.' }, 429, { 'Retry-After': '120' }),
      ],
    ]);
    renderReserva();
    await elegirPrestacion();
    await elegirHuecoYContinuar();
    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/120 segundos/i);
    expect(screen.getByRole('button', { name: /Reservar turno/i })).toBeEnabled();
  });

  it('no muestra nombres ni teléfonos de terceros en las franjas', async () => {
    instalarFetch([
      catalogoOk(),
      disponibilidadOk([
        {
          ...HUECOS[0],
          paciente_nombre: 'Otro Paciente',
          telefono: '+54 9 11 1111 1111',
        },
      ]),
    ]);
    renderReserva();
    await elegirPrestacion();

    expect(screen.queryByText(/Otro Paciente/)).not.toBeInTheDocument();
    expect(screen.queryByText(/1111 1111/)).not.toBeInTheDocument();
  });

  it('usa targets accesibles y anuncia los estados asíncronos', async () => {
    instalarFetch([
      catalogoOk(),
      disponibilidadOk(),
      verificacionOk(),
      ['/reservas', async () => jsonResponse({ detalle: 'Teléfono inválido', alternativas: [] }, 422)],
    ]);
    renderReserva();
    await elegirPrestacion();

    const slot = screen.getByRole('option', { name: /09:00/ });
    expect(slot).toHaveClass('slot');
    fireEvent.click(slot);
    fireEvent.click(screen.getByRole('button', { name: /Continuar con nombre y teléfono/i }));

    expect(screen.getByLabelText('Nombre')).toBeInTheDocument();
    expect(screen.getByLabelText('Teléfono')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: /No soy un robot/i })).toBeInTheDocument();

    await completarFormulario();
    fireEvent.click(screen.getByRole('button', { name: /Reservar turno/i }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/No pudimos reservar/i);
  });
});
