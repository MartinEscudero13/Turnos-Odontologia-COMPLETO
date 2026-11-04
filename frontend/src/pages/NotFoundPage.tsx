import { Link } from 'react-router-dom';
import { Brand } from '../components/Brand';

export function NotFoundPage(): JSX.Element {
  return (
    <div className="not-found">
      <Brand />
      <main className="not-found-main" id="main">
        <p className="eyebrow">404 / fuera de agenda</p>
        <h1>Ese turno no existe.</h1>
        <p>
          La página que buscás no está en esta versión del consultorio. Podés volver al inicio
          y seguir desde ahí.
        </p>
        <Link className="button button-primary" to="/">
          Volver al inicio
        </Link>
      </main>
      <p className="not-found-mark" aria-hidden="true">
        10:30
      </p>
    </div>
  );
}
