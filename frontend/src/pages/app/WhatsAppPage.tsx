import { useState, type FormEvent } from 'react';
import { catalogoApi, whatsappApi } from '../../api';
import { errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section, Select, fecha } from '../../components/ui';

function toneFor(estado: string): 'success' | 'pending' | 'danger' | 'neutral' {
  if (estado === 'ENTREGADO' || estado === 'LEIDO' || estado === 'ENVIADO') return 'success';
  if (estado === 'FALLIDO') return 'danger';
  if (estado === 'PENDIENTE') return 'pending';
  return 'neutral';
}

export function WhatsAppPage(): JSX.Element {
  const mensajes = useLoad(() => whatsappApi.mensajes(), []);
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const [pacienteId, setPacienteId] = useState('');
  const [motivo, setMotivo] = useState('Control post-tratamiento');
  const [fechaObjetivo, setFechaObjetivo] = useState('2027-01-15');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  function handleRecall(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        whatsappApi.recall({
          paciente_id: pacienteId,
          motivo,
          fecha_objetivo: fechaObjetivo,
        }),
      () => mensajes.reload(),
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-13"
        title="WhatsApp"
        description="Recordatorios, confirmación/cancelación por Twilio y recall clínico."
        actions={<StatusBadge tone="pending">{mensajes.data?.length ?? 0} mensajes</StatusBadge>}
      />
      <ErrorNotice error={error ?? mensajes.error ?? pacientes.error} />

      <div className="two-columns">
        <Section title="Recordatorios" description="Busca turnos dentro de la anticipación configurada.">
          <div className="form-actions">
            <Button
              isLoading={busy}
              onClick={() =>
                void accion(() => whatsappApi.programar(), () => mensajes.reload())
              }
            >
              Programar recordatorios
            </Button>
            <Button
              variant="secondary"
              isLoading={busy}
              onClick={() =>
                void accion(() => whatsappApi.procesar(), () => mensajes.reload())
              }
            >
              Procesar reintentos
            </Button>
          </div>
        </Section>

        <Section title="Recall clínico" description="Separado de campañas de marketing.">
          <form className="form-grid" onSubmit={handleRecall}>
            <Select
              label="Paciente"
              value={pacienteId}
              onChange={setPacienteId}
              options={[
                { value: '', label: 'Elegí un paciente' },
                ...(pacientes.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
              ]}
            />
            <Field
              label="Motivo clínico"
              value={motivo}
              onChange={(event) => setMotivo(event.target.value)}
            />
            <Field
              label="Fecha objetivo"
              type="date"
              value={fechaObjetivo}
              onChange={(event) => setFechaObjetivo(event.target.value)}
            />
            <div className="form-actions">
              <Button type="submit" isLoading={busy}>
                Enviar recall
              </Button>
            </div>
          </form>
        </Section>
      </div>

      <Section title="Mensajes">
        <DataTable
          rows={mensajes.data ?? []}
          keyOf={(mensaje) => mensaje.id}
          empty="Sin mensajes todavía."
          columns={[
            { header: 'Plantilla', cell: (m) => m.plantilla },
            { header: 'Canal', cell: (m) => m.canal },
            {
              header: 'Estado',
              cell: (m) => <StatusBadge tone={toneFor(m.estado)}>{m.estado}</StatusBadge>,
            },
            { header: 'Intento', cell: (m) => m.intentos, align: 'right' },
            { header: 'Respuesta', cell: (m) => m.respuesta ?? '—' },
            { header: 'Creado', cell: (m) => fecha(m.creado_en) },
          ]}
        />
      </Section>
    </div>
  );
}
