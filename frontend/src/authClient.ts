import { isRecord, type ApiResult } from './healthClient';

export interface LoginPayload {
  tenantSlug: string;
  email: string;
  password: string;
}

export interface SessionTokens {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

export async function loginRequest(
  payload: LoginPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<ApiResult<SessionTokens>> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({
        tenant_slug: payload.tenantSlug,
        email: payload.email,
        password: payload.password,
      }),
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const message =
        isRecord(body) && typeof body.detail === 'string'
          ? body.detail
          : 'No pudimos iniciar sesión con esos datos.';
      return { ok: false, error: message, status: response.status };
    }
    if (
      !isRecord(body) ||
      typeof body.access_token !== 'string' ||
      typeof body.refresh_token !== 'string'
    ) {
      return { ok: false, error: 'Respuesta de autenticación inválida.' };
    }
    return {
      ok: true,
      data: {
        accessToken: body.access_token,
        refreshToken: body.refresh_token,
        tokenType: typeof body.token_type === 'string' ? body.token_type : 'bearer',
      },
    };
  } catch {
    return { ok: false, error: 'No pudimos conectar con el servidor.' };
  }
}
