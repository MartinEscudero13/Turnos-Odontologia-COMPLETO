import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Brand } from '../components/Brand';
import { Button } from '../components/Button';
import { useAuth } from '../auth/AuthContext';

const futureNav = ['Pacientes', 'Catálogos', 'Caja', 'Reportes'];

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
          <NavLink className={({ isActive }) => `nav-item${isActive ? ' is-active' : ''}`} to="/app">
            <span aria-hidden="true">09:00</span> Agenda
          </NavLink>
          {futureNav.map((label) => (
            <span className="nav-item is-disabled" key={label} aria-disabled="true">
              <span aria-hidden="true">—</span> {label}
            </span>
          ))}
        </nav>
        <div className="rail-footer">
          <p>{session?.email}</p>
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
