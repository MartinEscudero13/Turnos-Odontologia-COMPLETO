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

export interface MeResponse {
  id: string;
  tenant_id: string;
  nombre: string;
  email: string;
  rol: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

export async function meRequest(
  accessToken: string,
  fetchImpl: typeof fetch = fetch,
): Promise<ApiResult<MeResponse>> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/auth/me`, {
      headers: { Accept: 'application/json', Authorization: `Bearer ${accessToken}` },
    });
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok || !isRecord(body)) {
      return { ok: false, error: 'No pudimos leer el perfil de la sesión.' };
    }
    if (
      typeof body.id !== 'string' ||
      typeof body.tenant_id !== 'string' ||
      typeof body.email !== 'string' ||
      typeof body.rol !== 'string'
    ) {
      return { ok: false, error: 'Perfil de sesión inválido.' };
    }
    return {
      ok: true,
      data: {
        id: body.id,
        tenant_id: body.tenant_id,
        nombre: typeof body.nombre === 'string' ? body.nombre : body.email,
        email: body.email,
        rol: body.rol,
      },
    };
  } catch {
    return { ok: false, error: 'No pudimos conectar con el servidor.' };
  }
}

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
      const detalle =
        isRecord(body) && typeof body.detalle === 'string'
          ? body.detalle
          : isRecord(body) && typeof body.detail === 'string'
            ? body.detail
            : isRecord(body) &&
                isRecord(body.error) &&
                typeof body.error.message === 'string'
              ? body.error.message
              : isRecord(body) && typeof body.message === 'string'
                ? body.message
                : null;
      return {
        ok: false,
        error: detalle ?? 'No pudimos iniciar sesión con esos datos.',
        status: response.status,
      };
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
