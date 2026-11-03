import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';

const healthPayload = {
  status: 'UP',
  service: 'turnos-api',
  version: '0.1.0',
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('App foundation shell', () => {
  it('renders the API status returned by /api/health', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify(healthPayload), {
          status: 200,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    );

    render(<App />);

    expect(screen.queryByText(/Verificando servicios/i)).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/turnos-api está UP/i)).toBeInTheDocument());
  });

  it('shows a safe message when health fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response('invalid', { status: 503 })),
    );

    render(<App />);

    expect(await screen.findByRole('alert')).toHaveTextContent(/API no disponible: HTTP 503/i);
  });
});
