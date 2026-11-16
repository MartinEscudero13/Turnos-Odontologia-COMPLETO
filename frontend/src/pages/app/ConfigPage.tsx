import { useEffect, useState, type FormEvent } from 'react';
import { adminApi, apiBlob, type Kpis, type UsuarioAdmin } from '../../api';
import { errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section, Select, Stat, money } from '../../components/ui';

function mes(): { desde: string; hasta: string } {
  const now = new Date();
  const desde = new Date(now.getFullYear(), now.getMonth(), 1);
  const hasta = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return { desde: desde.toISOString().slice(0, 10), hasta: hasta.toISOString().slice(0, 10) };
}

export function ConfigPage(): JSX.Element {
  const config = useLoad(() => adminApi.config(), []);
  const usuarios = useLoad(() => adminApi.usuarios(), []);
  const rango = mes();
  const [kpis, setKpis] = useState<Kpis | null>(null);

  const [anticipacion, setAnticipacion] = useState('24');
  const [senaModo, setSenaModo] = useState('PORCENTAJE');
  const [senaValor, setSenaValor] = useState('30');
  const [recordatorios, setRecordatorios] = useState(false);

  const [nombre, setNombre] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rol, setRol] = useState('RECEPCION');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!config.data) return;
    const data = config.data;
    if (typeof data.anticipacion_cancelacion_h === 'number') {
      setAnticipacion(String(data.anticipacion_cancelacion_h));
    }
    if (typeof data.sena_modo === 'string') setSenaModo(data.sena_modo);
    if (typeof data.sena_valor === 'number') setSenaValor(String(data.sena_valor));
    if (typeof data.recordatorios_habilitados === 'boolean') {
      setRecordatorios(data.recordatorios_habilitados);
    }
  }, [config.data]);

  async function accion(task: () => Promise<unknown>, after?: () => void): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await task();
      after?.();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function handleConfig(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        adminApi.actualizarConfig({
          anticipacion_cancelacion_h: Number(anticipacion),
          sena_modo: senaModo,
          sena_valor: Number(senaValor),
          recordatorios_habilitados: recordatorios,
        }),
      () => config.reload(),
    );
  }

  function handleUsuario(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () => adminApi.crearUsuario({ nombre, email, password, rol }),
      () => {
        setNombre('');
        setEmail('');
        usuarios.reload();
      },
    );
  }

  async function descargar(formato: 'json' | 'csv'): Promise<void> {
    setError(null);
    try {
      const blob = await apiBlob(adminApi.exportUrl(formato));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `export-tenant.${formato}`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-15"
        title="Configuración"
        description="Parámetros del tenant, usuarios, exportación y KPIs base."
        actions={<StatusBadge tone="pending">Admin</StatusBadge>}
      />
      <ErrorNotice error={error ?? config.error ?? usuarios.error} />

      <Section title="Parámetros del consultorio">
        <form className="form-grid" onSubmit={handleConfig}>
          <Field
            label="Anticipación de cancelación (h)"
            type="number"
            value={anticipacion}
            onChange={(event) => setAnticipacion(event.target.value)}
          />
          <Select
            label="Modo de seña"
            value={senaModo}
            onChange={setSenaModo}
            options={[
              { value: 'SIN_SENA', label: 'Sin seña' },
              { value: 'PORCENTAJE', label: 'Porcentaje' },
              { value: 'MONTO_FIJO', label: 'Monto fijo' },
            ]}
          />
          <Field
            label="Valor de seña"
            type="number"
            value={senaValor}
            onChange={(event) => setSenaValor(event.target.value)}
          />
          <label className="check-field">
            <input
              type="checkbox"
              checked={recordatorios}
              onChange={(event) => setRecordatorios(event.target.checked)}
            />
            Recordatorios habilitados (WhatsApp pendiente)
          </label>
          <div className="form-actions">
            <Button type="submit" isLoading={busy}>
              Guardar configuración
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Usuarios del tenant">
        <form className="form-grid" onSubmit={handleUsuario}>
          <Field
            label="Nombre"
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
          />
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            hint="Mínimo 8 caracteres."
          />
          <Select
            label="Rol"
            value={rol}
            onChange={setRol}
            options={[
              { value: 'ADMIN', label: 'Admin' },
              { value: 'RECEPCION', label: 'Recepción' },
              { value: 'ODONTOLOGO', label: 'Odontólogo' },
            ]}
          />
          <div className="form-actions">
            <Button type="submit" isLoading={busy}>
              Crear usuario
            </Button>
          </div>
        </form>
        <DataTable
          rows={usuarios.data ?? []}
          keyOf={(usuario: UsuarioAdmin) => usuario.id}
          empty="Sin usuarios."
          columns={[
            { header: 'Nombre', cell: (u) => u.nombre },
            { header: 'Email', cell: (u) => u.email },
            { header: 'Rol', cell: (u) => u.rol },
            {
              header: 'Estado',
              cell: (u) => (
                <StatusBadge tone={u.activo ? 'success' : 'danger'}>
                  {u.activo ? 'Activo' : 'Inactivo'}
                </StatusBadge>
              ),
            },
          ]}
        />
      </Section>

      <Section title="Exportación 1-clic" description="JSON o CSV del tenant, sin secretos.">
        <div className="form-actions">
          <Button variant="secondary" onClick={() => void descargar('json')}>
            Descargar JSON
          </Button>
          <Button variant="secondary" onClick={() => void descargar('csv')}>
            Descargar CSV
          </Button>
        </div>
      </Section>

      <Section
        title="KPIs del mes"
        actions={
          <Button
            variant="secondary"
            isLoading={busy}
            onClick={() =>
              void accion(async () => {
                setKpis(await adminApi.kpis(rango.desde, rango.hasta));
              })
            }
          >
            Calcular
          </Button>
        }
      >
        {kpis ? (
          <>
            <div className="stat-grid">
              <Stat label="Turnos" value={kpis.total_turnos} />
              <Stat label="Ausentismo" value={`${kpis.ausentismo_pct}%`} />
              <Stat label="Online" value={`${kpis.reservas_online_pct}%`} />
              <Stat label="Reasignados < 2 h" value={kpis.reasignados_2h} />
            </div>
            <ul className="plain-list">
              {Object.entries(kpis.turnos_por_estado).map(([estado, total]) => (
                <li key={estado}>
                  {estado}: <strong>{total}</strong>
                </li>
              ))}
              {kpis.facturacion_por_profesional.map(([profesional, total]) => (
                <li key={profesional}>
                  {profesional.slice(0, 8)}: <strong>{money(total)}</strong>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="table-empty">Todavía no calculaste los KPIs.</p>
        )}
      </Section>
    </div>
  );
}
