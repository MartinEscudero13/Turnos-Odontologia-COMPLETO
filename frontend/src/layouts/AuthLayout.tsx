import { Outlet, Link } from 'react-router-dom';
import { Brand } from '../components/Brand';

export function AuthLayout(): JSX.Element {
  return (
    <div className="shell-auth">
      <a className="skip-link" href="#main">
        Saltar al contenido
      </a>
      <aside className="auth-story">
        <Brand to="/" />
        <p className="eyebrow">Acceso al consultorio</p>
        <h2>La agenda no debería depender de la memoria de alguien.</h2>
        <p>
          Entrá al panel para gestionar la agenda, los pacientes, la historia clínica y la caja.
          La reserva pública también está disponible para tus pacientes.
        </p>
        <ul className="auth-facts">
          <li>
            <span>01</span> Aislamiento por tenant
          </li>
          <li>
            <span>02</span> Roles para recepción y odontología
          </li>
          <li>
            <span>03</span> Anti-solape en base de datos
          </li>
          <li>
            <span>04</span> Reserva pública y ficha clínica
          </li>
        </ul>
        <Link className="quiet-link" to="/">
          Volver al inicio
        </Link>
      </aside>
      <main id="main" className="auth-main">
        <Outlet />
      </main>
    </div>
  );
}
