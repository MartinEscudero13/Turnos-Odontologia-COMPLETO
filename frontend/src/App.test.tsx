import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from './App';
import { AuthProvider } from './auth/AuthContext';

function renderRoute(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>,
  );
}

function mockFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/health')) {
        return new Response(JSON.stringify({ status: 'UP', service: 'turnos-api', version: '0.1.0' }), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        });
      }
      if (url.endsWith('/api/auth/login')) {
        return new Response(
          JSON.stringify({ access_token: 'access-demo', refresh_token: 'refresh-demo', token_type: 'bearer' }),
          { status: 200, headers: { 'content-type': 'application/json' } },
        );
      }
      return new Response('not found', { status: 404 });
    }),
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('visual foundation routes', () => {
  it('renders the public home with live API status', async () => {
    mockFetch();
    renderRoute('/');
    expect(screen.getByRole('heading', { name: /El turno que el paciente ve/i })).toBeInTheDocument();
    expect(await screen.findByText(/API operativa/i)).toBeInTheDocument();
  });

  it('redirects /app to login when there is no session', () => {
    mockFetch();
    renderRoute('/app');
    expect(screen.getByRole('heading', { name: /Tu agenda empieza acá/i })).toBeInTheDocument();
  });

  it('logs in and navigates to the protected shell', async () => {
    mockFetch();
    renderRoute('/login');
    fireEvent.change(screen.getByLabelText('Consultorio'), { target: { value: 'demo' } });
    fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'admin@demo.test' } });
    fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: 'correct-password' } });
    fireEvent.click(screen.getByRole('button', { name: /Entrar al panel/i }));

    await waitFor(() => expect(screen.getAllByText(/admin@demo.test/i).length).toBeGreaterThan(0));
    expect(screen.getAllByText(/Fundación visual/i).length).toBeGreaterThan(0);
  });

  it('shows a recoverable 404', () => {
    mockFetch();
    renderRoute('/ruta-inexistente');
    expect(screen.getByRole('heading', { name: /Ese turno no existe/i })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Volver al inicio/i })).toHaveAttribute('href', '/');
  });

  it('renders the public booking landing at /r/:tokenTenant', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/publico/T1/catalogo')) {
          return new Response(
            JSON.stringify({
              prestaciones: [{ id: 'PREST-30', nombre: 'Consulta', duracion_min: 30 }],
              profesionales: [{ id: 'P1', nombre: 'Dra. Demo' }],
            }),
            { status: 200, headers: { 'content-type': 'application/json' } },
          );
        }
        return new Response('not found', { status: 404 });
      }),
    );
    renderRoute('/r/T1');
    expect(
      await screen.findByRole('heading', { name: /Elegí la prestación y mirá los horarios/i }),
    ).toBeInTheDocument();
    expect(await screen.findByText('Consulta')).toBeInTheDocument();
  });
});
