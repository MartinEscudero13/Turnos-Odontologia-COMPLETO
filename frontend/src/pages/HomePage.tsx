import { Link } from 'react-router-dom';
import { HealthIndicator } from '../components/HealthIndicator';
import { StatusBadge } from '../components/StatusBadge';

export function HomePage(): JSX.Element {
  return (
    <div className="home">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Agenda odontológica sin dobles reservas</p>
          <h1>
            El turno que el paciente ve
            <span className="hero-line">es el turno que existe.</span>
          </h1>
          <p className="hero-lede">
            Reserva 24/7, agenda multi-profesional y una regla de anti-solape que vive en la
            base de datos, no en la memoria de la recepción.
          </p>
          <div className="hero-actions">
            <Link className="button button-primary" to="/login">
              Ingresar al panel
            </Link>
            <a className="button button-secondary" href="#capacidades">
              Ver capacidades
            </a>
          </div>
          <div className="hero-status">
            <HealthIndicator />
            <span className="hero-status-note">Datos de demostración · sin PHI</span>
          </div>
        </div>

        <div className="appointment-board" aria-label="Ejemplo visual de un turno">
          <div className="board-topline">
            <span>Agenda / martes 06.10</span>
            <StatusBadge tone="success">Confirmado</StatusBadge>
          </div>
          <div className="slot-ruler" aria-hidden="true">
            {['09:00', '10:00', '11:00', '12:00'].map((time) => (
              <span key={time}>{time}</span>
            ))}
          </div>
          <div className="appointment-card">
            <div>
              <p className="eyebrow">Turno demo</p>
              <h2>Limpieza</h2>
              <p>Dra. Demo · Sillón 1</p>
            </div>
            <div className="appointment-time">
              <strong>10:30</strong>
              <span>30 min</span>
            </div>
          </div>
          <div className="slot-lines" aria-hidden="true">
            <span className="slot-free">09:00</span>
            <span className="slot-free">10:00</span>
            <span className="slot-taken">10:30</span>
            <span className="slot-free">11:00</span>
          </div>
          <p className="board-caption">La grilla no es decoración: representa disponibilidad real.</p>
        </div>
      </section>

      <section id="capacidades" className="capabilities" aria-labelledby="capabilities-title">
        <div className="section-intro">
          <p className="eyebrow">Lo que sostiene la promesa</p>
          <h2 id="capabilities-title">Menos coordinación manual. Más certeza.</h2>
        </div>
        <div className="capability-grid">
          <article>
            <span className="capability-index">01</span>
            <h3>Anti-solape real</h3>
            <p>Dos canales pueden intentar el mismo hueco. La restricción de base de datos decide quién gana.</p>
          </article>
          <article>
            <span className="capability-index">02</span>
            <h3>Un tenant, un mundo</h3>
            <p>El consultorio de al lado no ve tus pacientes, tus sillones ni tus horarios.</p>
          </article>
          <article>
            <span className="capability-index">03</span>
            <h3>Pensado para el celular</h3>
            <p>La reserva pública se usa con una mano; la recepción trabaja con teclado y densidad.</p>
          </article>
        </div>
      </section>

      <section className="closing-note">
        <p className="eyebrow">Fundación en progreso</p>
        <p>
          Esta pantalla es la base visual. La agenda, los pacientes y la reserva pública llegan
          como páginas verificables, sin inventar estados que el backend no tenga.
        </p>
      </section>
    </div>
  );
}
