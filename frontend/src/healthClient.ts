export interface HealthPayload {
  status: 'UP' | 'DOWN' | string;
  service: string;
  version: string;
}

export interface ApiResult<T> {
  ok: boolean;
  data?: T;
  error?: string;
}

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api';

export async function fetchHealth(
  fetchImpl: typeof fetch = fetch,
): Promise<ApiResult<HealthPayload>> {
  try {
    const response = await fetchImpl(`${apiBaseUrl}/health`, {
      headers: { Accept: 'application/json' },
    });
    if (!response.ok) {
      return { ok: false, error: `HTTP ${response.status}` };
    }
    const body: unknown = await response.json();
    if (!isRecord(body) || body.status !== 'UP') {
      return { ok: false, error: 'Respuesta inválida de /api/health' };
    }
    return {
      ok: true,
      data: {
        status: String(body.status),
        service: String(body.service),
        version: String(body.version),
      },
    };
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Error de red desconocido';
    return { ok: false, error: message };
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}
