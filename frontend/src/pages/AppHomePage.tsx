import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { EmptyState } from '../components/EmptyState';
import { HealthIndicator } from '../components/HealthIndicator';
import { PageHeader } from '../components/PageHeader';
import { StatusBadge } from '../components/StatusBadge';

export function AppHomePage(): JSX.Element {
  const { session } = useAuth();
  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Panel del consultorio"
        title="Agenda"
        description="La base visual está lista. La agenda real llega con el change de turnos y reserva."
        actions={<StatusBadge tone="pending">Fundación visual</StatusBadge>}
      />
      <div className="dashboard-grid">
        <section className="dashboard-primary">
          <EmptyState
            title="Todavía no hay turnos para mostrar"
            description="Cuando conectemos la agenda, acá vas a ver el día completo por profesional y sillón, con conflictos y alternativas."
            action={
              <Link className="button button-secondary" to="/">
                Volver al inicio
              </Link>
            }
          />
        </section>
        <aside className="dashboard-aside">
          <div className="info-card">
            <p className="eyebrow">Sesión actual</p>
            <p className="session-email">{session?.email}</p>
            <p className="muted">Tenant: {session?.tenantSlug}</p>
          </div>
          <div className="info-card">
            <p className="eyebrow">Estado</p>
            <HealthIndicator />
            <p className="muted">La UI no consulta datos clínicos en esta fundación.</p>
          </div>
          <div className="info-card info-card-accent">
            <p className="eyebrow">Próximas páginas</p>
            <ul className="plain-list">
              <li>Agenda operativa</li>
              <li>Pacientes y ficha base</li>
              <li>Catálogos del consultorio</li>
              <li>Reserva pública</li>
            </ul>
          </div>
        </aside>
      </div>
    </div>
  );
}
