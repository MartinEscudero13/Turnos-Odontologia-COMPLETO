import { Link } from 'react-router-dom';
import { adminApi, catalogoApi } from '../../api';
import { useLoad } from '../../hooks';
import { ErrorNotice, Section, Stat, money } from '../../components/ui';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';

function mes(): { desde: string; hasta: string } {
  const now = new Date();
  const desde = new Date(now.getFullYear(), now.getMonth(), 1);
  const hasta = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return {
    desde: desde.toISOString().slice(0, 10),
    hasta: hasta.toISOString().slice(0, 10),
  };
}

export function DashboardPage(): JSX.Element {
  const rango = mes();
  const kpis = useLoad(() => adminApi.kpis(rango.desde, rango.hasta), []);
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const profesionales = useLoad(() => catalogoApi.profesionales(), []);

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Panel del consultorio"
        title="Resumen operativo"
        description="KPIs del mes, accesos directos y estado de los módulos."
        actions={<StatusBadge tone="success">Demo en línea</StatusBadge>}
      />

      <ErrorNotice error={kpis.error ?? pacientes.error ?? profesionales.error} />

      <div className="stat-grid">
        <Stat label="Turnos del mes" value={kpis.data?.total_turnos ?? '—'} />
        <Stat label="Ausentismo" value={`${kpis.data?.ausentismo_pct ?? 0}%`} />
        <Stat label="Ocupación" value={`${kpis.data?.ocupacion_pct ?? 0}%`} />
        <Stat label="Reserva online" value={`${kpis.data?.reservas_online_pct ?? 0}%`} />
        <Stat label="Reasignados < 2 h" value={kpis.data?.reasignados_2h ?? '—'} />
        <Stat label="Pacientes" value={pacientes.data?.length ?? '—'} />
        <Stat label="Profesionales" value={profesionales.data?.length ?? '—'} />
      </div>

      <div className="dashboard-grid">
        <Section title="Facturación por profesional" description="Movimientos de ingreso no anulados.">
          {kpis.data && kpis.data.facturacion_por_profesional.length > 0 ? (
            <ul className="plain-list">
              {kpis.data.facturacion_por_profesional.map(([profesional, total]) => (
                <li key={profesional}>
                  <span>
                    {profesionales.data?.find((p) => p.id === profesional)?.nombre ??
                      profesional.slice(0, 8)}
                  </span>{' '}
                  · {money(total)}
                </li>
              ))}
            </ul>
          ) : (
            <p className="table-empty">Sin movimientos imputados a turnos en el período.</p>
          )}
        </Section>

        <Section title="Accesos directos">
          <div className="quick-grid">
            <Link className="quick-link" to="/app/agenda">
              <strong>Agenda</strong>
              <span>Crear y cancelar turnos</span>
            </Link>
            <Link className="quick-link" to="/app/pacientes">
              <strong>Pacientes</strong>
              <span>Alta y datos de contacto</span>
            </Link>
            <Link className="quick-link" to="/app/clinica">
              <strong>Clínica</strong>
              <span>Ficha, odontograma y presupuesto</span>
            </Link>
            <Link className="quick-link" to="/app/caja">
              <strong>Caja</strong>
              <span>Movimientos y cierre del día</span>
            </Link>
            <Link className="quick-link" to="/app/obras-sociales">
              <strong>Obras sociales</strong>
              <span>Coberturas y liquidaciones</span>
            </Link>
            <Link className="quick-link" to="/app/whatsapp">
              <strong>WhatsApp</strong>
              <span>Recordatorios, respuestas y recall</span>
            </Link>
            <Link className="quick-link" to="/app/config">
              <strong>Configuración</strong>
              <span>Usuarios, exportación y KPIs</span>
            </Link>
          </div>
        </Section>
      </div>
    </div>
  );
}
