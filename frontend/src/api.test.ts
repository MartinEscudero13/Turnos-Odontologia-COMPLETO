import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, setApiContext } from './api';

afterEach(() => {
  setApiContext({ actor: null, token: null });
  vi.unstubAllGlobals();
});

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

describe('refresh de sesión', () => {
  it('renueva el token una vez y reintenta el request', async () => {
    const onSession = vi.fn();
    const onUnauthorized = vi.fn();
    setApiContext({
      actor: { tenantId: 't1', userId: 'u1', rol: 'ADMIN' },
      token: 'viejo',
      refreshToken: 'refresh-viejo',
      tenantSlug: 'demo',
      onSession,
      onUnauthorized,
    });

    let pacientes = 0;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/auth/refresh')) {
          return json({ access_token: 'nuevo', refresh_token: 'refresh-nuevo', token_type: 'bearer' });
        }
        if (url.endsWith('/api/pacientes')) {
          pacientes += 1;
          return pacientes === 1 ? json({ detalle: 'Token inválido' }, 401) : json([]);
        }
        return json(null, 404);
      }),
    );

    const resultado = await api<unknown[]>('/api/pacientes');

    expect(resultado).toEqual([]);
    expect(pacientes).toBe(2);
    expect(onSession).toHaveBeenCalledWith({
      accessToken: 'nuevo',
      refreshToken: 'refresh-nuevo',
    });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('cierra la sesión si el refresh falla', async () => {
    const onUnauthorized = vi.fn();
    setApiContext({
      actor: { tenantId: 't1', userId: 'u1', rol: 'ADMIN' },
      token: 'viejo',
      refreshToken: 'refresh-viejo',
      tenantSlug: 'demo',
      onUnauthorized,
    });

    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith('/api/auth/refresh')) return json({ detalle: 'Refresh vencido' }, 401);
        return json({ detalle: 'Token inválido' }, 401);
      }),
    );

    await expect(api('/api/pacientes')).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).toHaveBeenCalledTimes(1);
  });
});
