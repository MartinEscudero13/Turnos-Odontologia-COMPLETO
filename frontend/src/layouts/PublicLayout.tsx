import { Outlet, Link, useLocation } from 'react-router-dom';
import { Brand } from '../components/Brand';

export function PublicLayout(): JSX.Element {
  const { pathname } = useLocation();
  const esInicio = pathname === '/';

  return (
    <div className="shell-public">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <header className="public-header">
        <Brand />
        <nav className="public-nav" aria-label="Navegación pública">
          {esInicio ? (
            <a className="nav-link" href="#capacidades">
              Cómo funciona
            </a>
          ) : null}
          <Link className="button button-secondary button-small" to="/login">
            Ingresar al panel
          </Link>
        </nav>
      </header>
      <main id="main">
        <Outlet />
      </main>
      <footer className="public-footer">
        <Brand />
        <p>Agenda odontológica con anti-solape real. Datos de demo ficticios.</p>
        <p className="footer-meta">
          {esInicio ? 'v0.2 · Fundación visual' : 'Reserva online · sin login'}
        </p>
      </footer>
    </div>
  );
}
