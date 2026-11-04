import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { loginRequest, type LoginPayload, type SessionTokens } from '../authClient';
import type { ApiResult } from '../healthClient';

export interface Session extends SessionTokens {
  tenantSlug: string;
  email: string;
}

interface AuthContextValue {
  session: Session | null;
  login: (payload: LoginPayload) => Promise<ApiResult<Session>>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [session, setSession] = useState<Session | null>(null);

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      async login(payload) {
        const result = await loginRequest(payload);
        if (!result.ok || !result.data) {
          return { ok: false, error: result.error, status: result.status };
        }
        const next: Session = {
          ...result.data,
          tenantSlug: payload.tenantSlug,
          email: payload.email,
        };
        setSession(next);
        return { ok: true, data: next };
      },
      logout() {
        setSession(null);
      },
    }),
    [session],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe usarse dentro de AuthProvider');
  }
  return context;
}

export function RequireSession(): JSX.Element {
  const { session } = useAuth();
  const location = useLocation();
  if (!session) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}
