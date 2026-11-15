import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { loginRequest, meRequest, type LoginPayload, type SessionTokens } from '../authClient';
import { setApiContext, type Actor, type Rol } from '../api';
import type { ApiResult } from '../healthClient';

const STORAGE_KEY = 'turnos.demo.session';

export interface Session extends SessionTokens {
  tenantSlug: string;
  email: string;
  nombre: string;
  actor: Actor;
  demo: boolean;
}

interface AuthContextValue {
  session: Session | null;
  login: (payload: LoginPayload) => Promise<ApiResult<Session>>;
  loginDemo: () => Promise<ApiResult<Session>>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function readStoredSession(): Session | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    const candidate = parsed as Partial<Session>;
    if (
      typeof candidate.accessToken !== 'string' ||
      typeof candidate.email !== 'string' ||
      !candidate.actor ||
      typeof candidate.actor.tenantId !== 'string'
    ) {
      return null;
    }
    return candidate as Session;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }): JSX.Element {
  const [session, setSession] = useState<Session | null>(() => readStoredSession());

  useEffect(() => {
    setApiContext({
      actor: session?.actor ?? null,
      token: session?.accessToken ?? null,
    });
  }, [session]);

  const value = useMemo<AuthContextValue>(() => {
    async function login(payload: LoginPayload): Promise<ApiResult<Session>> {
      const result = await loginRequest(payload);
      if (!result.ok || !result.data) {
        return { ok: false, error: result.error, status: result.status };
      }
      const me = await meRequest(result.data.accessToken);
      if (!me.ok || !me.data) {
        return { ok: false, error: me.error ?? 'No pudimos leer el perfil.' };
      }
      const actor: Actor = {
        tenantId: me.data.tenant_id,
        userId: me.data.id,
        rol: me.data.rol as Rol,
      };
      const next: Session = {
        ...result.data,
        tenantSlug: payload.tenantSlug,
        email: me.data.email,
        nombre: me.data.nombre,
        actor,
        demo: false,
      };
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setSession(next);
      return { ok: true, data: next };
    }

    return {
      session,
      login,
      async loginDemo() {
        return login({
          tenantSlug: 'demo',
          email: 'admin@demo.test',
          password: 'demo1234',
        });
      },
      logout() {
        window.localStorage.removeItem(STORAGE_KEY);
        setSession(null);
      },
    };
  }, [session]);

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
