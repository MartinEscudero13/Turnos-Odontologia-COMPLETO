import { Link } from 'react-router-dom';

export function Brand({ to = '/' }: { to?: string }): JSX.Element {
  return (
    <Link className="brand" to={to} aria-label="Turnos-Odontologia, ir al inicio">
      <span className="brand-mark" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span className="brand-name">
        turnos<span>.</span>
      </span>
    </Link>
  );
}
