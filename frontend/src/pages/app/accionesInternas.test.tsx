import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AuthProvider } from '../../auth/AuthContext';
import { AgendaPage } from './AgendaPage';
import { CajaPage } from './CajaPage';
import { CalendarioPage } from './CalendarioPage';
import { ClinicaPage } from './ClinicaPage';
import { ConfigPage } from './ConfigPage';
import { ObrasSocialesPage } from './ObrasSocialesPage';

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function renderPage(node: JSX.Element): void {
  render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>{node}</AuthProvider>
    </MemoryRouter>,
  );
}

function guardarSesion(): void {
  window.localStorage.setItem(
    'turnos.demo.session',
    JSON.stringify({
      accessToken: 'token-demo',
      refreshToken: 'refresh-demo',
      tokenType: 'bearer',
      tenantSlug: 'demo',
      email: 'admin@demo.test',
      nombre: 'Admin Demo',
      actor: { tenantId: 'tenant-1', userId: 'user-1', rol: 'ADMIN' },
      demo: false,
    }),
  );
}

function llamada(url: string, method: string): boolean {
  return vi
    .mocked(fetch)
    .mock.calls.some(
      ([input, init]) =>
        String(input) === url && ((init?.method ?? 'GET') === method),
    );
}

afterEach(() => {
  cleanup();
  window.localStorage.clear();
  vi.unstubAllGlobals();
});

describe('acciones de agenda', () => {
  it('confirma un turno pendiente desde la grilla', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/turnos')) {
          return json([
            {
              id: 'turno-1',
              profesional_id: 'prof-1',
              sillon_id: 'sillon-1',
              paciente_id: 'pac-1',
              prestacion_id: 'prest-1',
              inicio: '2026-11-20T13:00:00Z',
              fin: '2026-11-20T13:30:00Z',
              estado: 'PENDIENTE',
              origen: 'RECEPCION',
              sobreturno: false,
            },
          ]);
        }
        if (url.endsWith('/confirmar')) return json({ id: 'turno-1', estado: 'CONFIRMADO' });
        if (url.endsWith('/api/pacientes')) {
          return json([{ id: 'pac-1', nombre: 'Paciente Demo', telefono: '+5491100000000' }]);
        }
        if (url.endsWith('/api/profesionales')) {
          return json([{ id: 'prof-1', nombre: 'Dra. Demo', especialidad: 'Odontología' }]);
        }
        if (url.endsWith('/api/sillones')) return json([]);
        if (url.endsWith('/api/prestaciones')) {
          return json([
            { id: 'prest-1', nombre: 'Consulta', duracion_min: 30, precio_base: 10000 },
          ]);
        }
        return json(null, 404);
      }),
    );

    renderPage(<AgendaPage />);

    const boton = await screen.findByRole('button', { name: 'Confirmar' });
    fireEvent.click(boton);

    await waitFor(() => expect(llamada('/api/turnos/turno-1/confirmar', 'POST')).toBe(true));
  });
});

describe('acciones de clínica', () => {
  it('muestra líneas anidadas y acepta una sin decisión', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.includes('/aceptar')) {
          return json({
            presupuesto_id: 'pres-1',
            estado: 'ACEPTADO',
            actor_id: 'user-1',
            linea_id: 'linea-1',
            acepta: true,
            fecha: '2026-11-17T10:00:00Z',
            canal: 'mostrador',
            medio: null,
          });
        }
        if (url.includes('/api/presupuestos?paciente_id=pac-1')) {
          return json([
            {
              id: 'pres-1',
              paciente_id: 'pac-1',
              estado: 'VIGENTE',
              vence_en: '2026-12-17T10:00:00Z',
              creado_en: '2026-11-17T10:00:00Z',
              lineas: [
                {
                  linea: {
                    id: 'linea-1',
                    presupuesto_id: 'pres-1',
                    prestacion_id: 'prest-1',
                    monto: 10000,
                    cobertura_os: 4000,
                    a_cargo_paciente: 6000,
                    pieza_fdi: null,
                    hallazgo_id: null,
                  },
                  aceptacion: null,
                },
              ],
            },
          ]);
        }
        if (url.includes('/api/pacientes/pac-1/ficha')) {
          return json({ id: 'ficha-1', paciente_id: 'pac-1', creado_en: '2026-11-17T10:00:00Z' });
        }
        if (url.includes('/api/consentimientos')) {
          return json([
            {
              id: 'cons-1',
              paciente_id: 'pac-1',
              timestamp: '2026-11-17T10:00:00Z',
              canal: 'mostrador',
              creado_en: '2026-11-17T10:00:00Z',
            },
          ]);
        }
        if (url.includes('/api/evoluciones') || url.includes('/api/odontograma')) return json([]);
        if (url.endsWith('/api/pacientes')) {
          return json([{ id: 'pac-1', nombre: 'Paciente Demo', telefono: '+5491100000000' }]);
        }
        if (url.endsWith('/api/profesionales')) {
          return json([{ id: 'prof-1', nombre: 'Dra. Demo', especialidad: 'Odontología' }]);
        }
        if (url.endsWith('/api/prestaciones')) {
          return json([
            {
              id: 'prest-1',
              nombre: 'Consulta',
              duracion_min: 30,
              precio_base: 10000,
            },
          ]);
        }
        void init;
        return json(null, 404);
      }),
    );

    render(
      <MemoryRouter
        initialEntries={['/app/clinica?paciente=pac-1']}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AuthProvider>
          <ClinicaPage />
        </AuthProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByText('Consulta')).toBeInTheDocument();
    const aceptar = await screen.findByRole('button', { name: 'Aceptar' });
    fireEvent.click(aceptar);

    await waitFor(() =>
      expect(llamada('/api/presupuestos/pres-1/aceptar', 'POST')).toBe(true),
    );
  });
});

describe('acciones de caja', () => {
  it('cobra un pendiente desde la grilla', async () => {
    guardarSesion();
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.includes('/api/caja/pendientes/pend-1/cobrar')) {
          return json({ pendiente: { id: 'pend-1' }, movimiento: { id: 'mov-1' } }, 201);
        }
        if (url.includes('/api/caja/pendientes')) {
          return json([
            {
              id: 'pend-1',
              fecha: '2026-11-16',
              presupuesto_id: 'pres-1',
              linea_id: 'linea-1',
              monto_centavos: 4000,
              actor_id: 'user-1',
              turno_id: null,
              creado_en: '2026-11-16T10:00:00Z',
              resuelto_en: null,
              movimiento_id: null,
            },
          ]);
        }
        if (url.includes('/api/caja/movimientos')) {
          return json({
            fecha: '2026-11-16',
            estado: 'abierto',
            movimientos: [],
            pendientes: [],
            ajustes: [],
            totales_vigentes: { efectivo: 0, transferencia: 0, mp: 0, os: 0 },
            totales_cierre: null,
            difieren_del_cierre: false,
          });
        }
        if (url.includes('/api/caja/cierres')) return json([]);
        if (url.includes('/api/caja/reportes')) {
          return json({
            desde: '2026-11-01',
            hasta: '2026-11-16',
            fuente: 'movimientos_vigentes',
            totales: { efectivo: 0, transferencia: 0, mp: 0, os: 0 },
            por_dia: [],
            cierres: 0,
            movimientos_anulados: 0,
          });
        }
        return json(null, 404);
      }),
    );

    renderPage(<CajaPage />);

    const boton = await screen.findByRole('button', { name: 'Cobrar efectivo' });
    fireEvent.click(boton);

    await waitFor(() =>
      expect(llamada('/api/caja/pendientes/pend-1/cobrar', 'POST')).toBe(true),
    );
  });
});

describe('acciones de obras sociales', () => {
  it('desactiva una obra social', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/obras-sociales/os-1')) {
          return json({ id: 'os-1', nombre: 'OS Demo', activa: false });
        }
        if (url.endsWith('/api/obras-sociales')) {
          return json([{ id: 'os-1', nombre: 'OS Demo', activa: true }]);
        }
        if (url.includes('/api/coberturas')) return json([]);
        if (url.includes('/api/liquidaciones')) return json([]);
        if (url.endsWith('/api/pacientes')) return json([]);
        if (url.endsWith('/api/prestaciones')) return json([]);
        return json(null, 404);
      }),
    );

    renderPage(<ObrasSocialesPage />);

    const boton = await screen.findByRole('button', { name: 'Desactivar' });
    fireEvent.click(boton);

    await waitFor(() => expect(llamada('/api/obras-sociales/os-1', 'PATCH')).toBe(true));
  });
});

describe('acciones de calendario', () => {
  it('desconecta un calendario', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/calendar/links/link-1')) {
          return json({ id: 'link-1', estado: 'DESCONECTADO' });
        }
        if (url.endsWith('/api/calendar/links')) {
          return json([
            {
              id: 'link-1',
              profesional_id: 'prof-1',
              gcal_calendar_id: 'demo@example.test',
              estado: 'CONECTADO',
              ultima_sync: null,
            },
          ]);
        }
        if (url.includes('/api/calendar/bloqueos')) return json([]);
        if (url.endsWith('/api/profesionales')) return json([]);
        if (url.endsWith('/api/turnos')) return json([]);
        return json(null, 404);
      }),
    );

    renderPage(<CalendarioPage />);

    const boton = await screen.findByRole('button', { name: 'Desconectar' });
    fireEvent.click(boton);

    await waitFor(() => expect(llamada('/api/calendar/links/link-1', 'DELETE')).toBe(true));
  });
});

describe('acciones de configuración', () => {
  it('desactiva un usuario del tenant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/tenant/usuarios/user-2')) {
          return json({
            id: 'user-2',
            nombre: 'Recepción Demo',
            email: 'recepcion@demo.test',
            rol: 'RECEPCION',
            activo: false,
          });
        }
        if (url.endsWith('/api/tenant/usuarios')) {
          return json([
            {
              id: 'user-2',
              nombre: 'Recepción Demo',
              email: 'recepcion@demo.test',
              rol: 'RECEPCION',
              activo: true,
            },
          ]);
        }
        if (url.endsWith('/api/tenant/config')) return json({});
        return json(null, 404);
      }),
    );

    renderPage(<ConfigPage />);

    const boton = await screen.findByRole('button', { name: 'Desactivar' });
    fireEvent.click(boton);

    await waitFor(() =>
      expect(llamada('/api/tenant/usuarios/user-2', 'PATCH')).toBe(true),
    );
  });
});
