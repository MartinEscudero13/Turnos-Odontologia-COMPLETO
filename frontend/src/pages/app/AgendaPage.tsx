import { useState, type FormEvent } from 'react';
import { catalogoApi, turnosApi } from '../../api';
import { enDias, errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { DataTable, ErrorNotice, Section, Select, fecha } from '../../components/ui';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';

function toneFor(estado: string): 'success' | 'pending' | 'danger' | 'neutral' {
  if (estado === 'PRESENTE' || estado === 'CONFIRMADO') return 'success';
  if (estado === 'CANCELADO' || estado === 'AUSENTE') return 'danger';
  if (estado === 'PENDIENTE') return 'pending';
  return 'neutral';
}

export function AgendaPage(): JSX.Element {
  const turnos = useLoad(() => turnosApi.listar(), []);
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const profesionales = useLoad(() => catalogoApi.profesionales(), []);
  const sillones = useLoad(() => catalogoApi.sillones(), []);
  const prestaciones = useLoad(() => catalogoApi.prestaciones(), []);

  const [pacienteId, setPacienteId] = useState('');
  const [profesionalId, setProfesionalId] = useState('');
  const [sillonId, setSillonId] = useState('');
  const [prestacionId, setPrestacionId] = useState('');
  const [inicio, setInicio] = useState(enDias(1).slice(0, 16));
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  function nombrePaciente(id: string): string {
    return pacientes.data?.find((p) => p.id === id)?.nombre ?? id.slice(0, 8);
  }
  function nombreProfesional(id: string): string {
    return profesionales.data?.find((p) => p.id === id)?.nombre ?? id.slice(0, 8);
  }
  function nombrePrestacion(id: string): string {
    return prestaciones.data?.find((p) => p.id === id)?.nombre ?? id.slice(0, 8);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    const prestacion = prestaciones.data?.find((p) => p.id === prestacionId);
    if (!pacienteId || !profesionalId || !sillonId || !prestacion) {
      setError('Completá paciente, profesional, sillón y prestación.');
      return;
    }
    setSaving(true);
    try {
      await turnosApi.crear({
        paciente_id: pacienteId,
        profesional_id: profesionalId,
        sillon_id: sillonId,
        prestacion_id: prestacionId,
        duracion_min: prestacion.duracion_min,
        inicio: new Date(inicio).toISOString(),
      });
      turnos.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setSaving(false);
    }
  }

  async function transicion(task: () => Promise<unknown>): Promise<void> {
    setError(null);
    try {
      await task();
      turnos.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-05"
        title="Agenda"
        description="Turnos internos con anti-solape y cancelación con liberación de hueco."
        actions={<StatusBadge tone="pending">{turnos.data?.length ?? 0} turnos</StatusBadge>}
      />
      <ErrorNotice
        error={
          error ??
          turnos.error ??
          pacientes.error ??
          profesionales.error ??
          sillones.error ??
          prestaciones.error
        }
      />

      <Section title="Nuevo turno" description="La duración se toma de la prestación.">
        <form className="form-grid" onSubmit={handleSubmit}>
          <Select
            label="Paciente"
            value={pacienteId}
            onChange={setPacienteId}
            options={[
              { value: '', label: 'Elegí un paciente' },
              ...(pacientes.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
            ]}
          />
          <Select
            label="Prestación"
            value={prestacionId}
            onChange={setPrestacionId}
            options={[
              { value: '', label: 'Elegí una prestación' },
              ...(prestaciones.data ?? []).map((p) => ({
                value: p.id,
                label: `${p.nombre} · ${p.duracion_min} min`,
              })),
            ]}
          />
          <Select
            label="Profesional"
            value={profesionalId}
            onChange={setProfesionalId}
            options={[
              { value: '', label: 'Elegí un profesional' },
              ...(profesionales.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
            ]}
          />
          <Select
            label="Sillón"
            value={sillonId}
            onChange={setSillonId}
            options={[
              { value: '', label: 'Elegí un sillón' },
              ...(sillones.data ?? []).map((s) => ({ value: s.id, label: s.nombre })),
            ]}
          />
          <Field
            label="Inicio"
            type="datetime-local"
            value={inicio}
            onChange={(event) => setInicio(event.target.value)}
            required
          />
          <div className="form-actions">
            <Button type="submit" isLoading={saving}>
              Crear turno
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Turnos" description="Ordenados por fecha de creación del servicio.">
        <DataTable
          rows={turnos.data ?? []}
          keyOf={(turno) => turno.id}
          empty="No hay turnos todavía. Creá el primero arriba."
          columns={[
            { header: 'Inicio', cell: (t) => fecha(t.inicio) },
            { header: 'Paciente', cell: (t) => nombrePaciente(t.paciente_id) },
            { header: 'Prestación', cell: (t) => nombrePrestacion(t.prestacion_id) },
            { header: 'Profesional', cell: (t) => nombreProfesional(t.profesional_id) },
            {
              header: 'Estado',
              cell: (t) => <StatusBadge tone={toneFor(t.estado)}>{t.estado}</StatusBadge>,
            },
            {
              header: 'Acciones',
              align: 'right',
              cell: (t) => {
                const editable =
                  t.estado === 'PENDIENTE' || t.estado === 'CONFIRMADO';
                if (!editable) return <span className="muted">—</span>;
                return (
                  <div className="row-actions">
                    {t.estado === 'PENDIENTE' ? (
                      <Button
                        variant="quiet"
                        onClick={() => void transicion(() => turnosApi.confirmar(t.id))}
                      >
                        Confirmar
                      </Button>
                    ) : null}
                    {t.estado === 'CONFIRMADO' ? (
                      <>
                        <Button
                          variant="quiet"
                          onClick={() => void transicion(() => turnosApi.presente(t.id))}
                        >
                          Presente
                        </Button>
                        <Button
                          variant="quiet"
                          onClick={() => void transicion(() => turnosApi.ausente(t.id))}
                        >
                          Ausente
                        </Button>
                      </>
                    ) : null}
                    <Button
                      variant="quiet"
                      onClick={() => void transicion(() => turnosApi.cancelar(t.id))}
                    >
                      Cancelar
                    </Button>
                  </div>
                );
              },
            },
          ]}
        />
      </Section>
    </div>
  );
}
