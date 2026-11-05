import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireSession } from './auth/AuthContext';
import { AppShell } from './layouts/AppShell';
import { AuthLayout } from './layouts/AuthLayout';
import { PublicLayout } from './layouts/PublicLayout';
import { AppHomePage } from './pages/AppHomePage';
import { GestionTurnoPage } from './pages/GestionTurnoPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ReservaPage } from './pages/ReservaPage';

export function AppRoutes(): JSX.Element {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route index element={<HomePage />} />
        <Route path="r/:tokenTenant" element={<ReservaPage />} />
        <Route path="r/:tokenTenant/turno/:token" element={<GestionTurnoPage />} />
      </Route>
      <Route element={<AuthLayout />}>
        <Route path="login" element={<LoginPage />} />
      </Route>
      <Route element={<RequireSession />}>
        <Route element={<AppShell />}>
          <Route path="app" element={<AppHomePage />} />
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}

export function App(): JSX.Element {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
