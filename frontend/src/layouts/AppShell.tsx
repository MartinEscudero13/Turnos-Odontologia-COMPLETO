import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Brand } from '../components/Brand';
import { Button } from '../components/Button';
import { useAuth } from '../auth/AuthContext';

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV: NavItem[] = [
  { to: '/app', label: 'Resumen', icon: '▦' },
  { to: '/app/agenda', label: 'Agenda', icon: '09:00' },
  { to: '/app/pacientes', label: 'Pacientes', icon: '◎' },
  { to: '/app/clinica', label: 'Clínica', icon: '✚' },
  { to: '/app/caja', label: 'Caja', icon: '$' },
  { to: '/app/senas', label: 'Señas', icon: '◈' },
  { to: '/app/whatsapp', label: 'WhatsApp', icon: 'WA' },
  { to: '/app/obras-sociales', label: 'Obras sociales', icon: 'OS' },
  { to: '/app/calendario', label: 'Calendario', icon: '▤' },
  { to: '/app/config', label: 'Configuración', icon: '⚙' },
];

export function AppShell(): JSX.Element {
  const { session, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout(): void {
    logout();
    navigate('/login', { replace: true });
  }

  return (
    <div className="shell-app">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <aside className="app-rail">
        <Brand to="/app" />
        <p className="rail-context">{session?.tenantSlug}</p>
        <nav className="app-nav" aria-label="Navegación del panel">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              end={item.to === '/app'}
              className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`}
              to={item.to}
            >
              <span aria-hidden="true">{item.icon}</span> {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="rail-footer">
          <p>{session?.nombre}</p>
          <p className="muted">{session?.email}</p>
          <p className="muted">Rol: {session?.actor.rol}</p>
          <Button variant="quiet" onClick={handleLogout}>
            Cerrar sesión
          </Button>
        </div>
      </aside>
      <main id="main" className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
