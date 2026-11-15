import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { catalogoApi } from '../../api';
import { errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section } from '../../components/ui';

export function PacientesPage(): JSX.Element {
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('+54911');
  const [email, setEmail] = useState('');
  const [consentimiento, setConsentimiento] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await catalogoApi.crearPaciente({
        nombre,
        telefono,
        email: email || undefined,
        consentimiento_ok: consentimiento,
      });
      setNombre('');
      setEmail('');
      pacientes.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-04"
        title="Pacientes"
        description="Datos ficticios de demo. El teléfono debe estar en formato E.164."
        actions={<StatusBadge tone="pending">{pacientes.data?.length ?? 0} pacientes</StatusBadge>}
      />
      <ErrorNotice error={error ?? pacientes.error} />

      <Section title="Alta de paciente">
        <form className="form-grid" onSubmit={handleSubmit}>
          <Field
            label="Nombre"
            value={nombre}
            onChange={(event) => setNombre(event.target.value)}
            placeholder="Paciente Demo"
            required
          />
          <Field
            label="Teléfono"
            value={telefono}
            onChange={(event) => setTelefono(event.target.value)}
            hint="Formato +54911..."
            required
          />
          <Field
            label="Email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="opcional@demo.test"
          />
          <label className="check-field">
            <input
              type="checkbox"
              checked={consentimiento}
              onChange={(event) => setConsentimiento(event.target.checked)}
            />
            Consentimiento informado firmado
          </label>
          <div className="form-actions">
            <Button type="submit" isLoading={saving}>
              Crear paciente
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Listado">
        <DataTable
          rows={pacientes.data ?? []}
          keyOf={(paciente) => paciente.id}
          empty="No hay pacientes. Creá el primero arriba."
          columns={[
            { header: 'Nombre', cell: (p) => p.nombre },
            { header: 'Teléfono', cell: (p) => <span className="mono">{p.telefono}</span> },
            { header: 'Email', cell: (p) => p.email ?? '—' },
            {
              header: 'Consentimiento',
              cell: (p) => (
                <StatusBadge tone={p.consentimiento_ok ? 'success' : 'pending'}>
                  {p.consentimiento_ok ? 'Firmado' : 'Pendiente'}
                </StatusBadge>
              ),
            },
            {
              header: '',
              align: 'right',
              cell: (p) => (
                <Link className="button button-quiet" to={`/app/clinica?paciente=${p.id}`}>
                  Abrir clínica
                </Link>
              ),
            },
          ]}
        />
      </Section>
    </div>
  );
}
