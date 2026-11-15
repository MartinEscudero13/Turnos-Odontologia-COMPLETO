import { useCallback, useEffect, useState } from 'react';
import { ApiError } from './api';

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.codigo ? `${error.message} (${error.codigo})` : error.message;
  }
  if (error instanceof Error) return error.message;
  return 'Ocurrió un error inesperado.';
}

export function useLoad<T>(
  loader: () => Promise<T>,
  deps: unknown[],
): {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    loader()
      .then((value) => {
        if (active) setData(value);
      })
      .catch((cause: unknown) => {
        if (active) setError(errorMessage(cause));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((value) => value + 1), []);
  return { data, error, loading, reload };
}

export function hoyISO(): string {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60_000).toISOString().slice(0, 10);
}

export function enDias(dias: number, hora = 10): string {
  const date = new Date();
  date.setDate(date.getDate() + dias);
  date.setHours(hora, 0, 0, 0);
  return date.toISOString();
}
