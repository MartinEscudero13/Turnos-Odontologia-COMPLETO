import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider, RequireSession } from './auth/AuthContext';
import { AppShell } from './layouts/AppShell';
import { AuthLayout } from './layouts/AuthLayout';
import { PublicLayout } from './layouts/PublicLayout';
import { AgendaPage } from './pages/app/AgendaPage';
import { CajaPage } from './pages/app/CajaPage';
import { CalendarioPage } from './pages/app/CalendarioPage';
import { ClinicaPage } from './pages/app/ClinicaPage';
import { ConfigPage } from './pages/app/ConfigPage';
import { DashboardPage } from './pages/app/DashboardPage';
import { ObrasSocialesPage } from './pages/app/ObrasSocialesPage';
import { PacientesPage } from './pages/app/PacientesPage';
import { SenasPage } from './pages/app/SenasPage';
import { WhatsAppPage } from './pages/app/WhatsAppPage';
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
          <Route path="app" element={<DashboardPage />} />
          <Route path="app/agenda" element={<AgendaPage />} />
          <Route path="app/pacientes" element={<PacientesPage />} />
          <Route path="app/clinica" element={<ClinicaPage />} />
          <Route path="app/caja" element={<CajaPage />} />
          <Route path="app/senas" element={<SenasPage />} />
          <Route path="app/whatsapp" element={<WhatsAppPage />} />
          <Route path="app/obras-sociales" element={<ObrasSocialesPage />} />
          <Route path="app/calendario" element={<CalendarioPage />} />
          <Route path="app/config" element={<ConfigPage />} />
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
