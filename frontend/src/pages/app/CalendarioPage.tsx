import { useState, type FormEvent } from 'react';
import { calendarioApi, catalogoApi, turnosApi } from '../../api';
import { enDias, errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section, Select, fecha } from '../../components/ui';

function haceDias(dias: number): string {
  const date = new Date();
  date.setDate(date.getDate() - dias);
  return date.toISOString();
}

function sumaDias(dias: number): string {
  const date = new Date();
  date.setDate(date.getDate() + dias);
  return date.toISOString();
}

/** ISO → valor local `YYYY-MM-DDTHH:mm` para `<input type="datetime-local">`. */
function aInputLocal(iso: string): string {
  const date = new Date(iso);
  const dos = (valor: number): string => String(valor).padStart(2, '0');
  return `${date.getFullYear()}-${dos(date.getMonth() + 1)}-${dos(
    date.getDate(),
  )}T${dos(date.getHours())}:${dos(date.getMinutes())}`;
}

export function CalendarioPage(): JSX.Element {
  const links = useLoad(() => calendarioApi.links(), []);
  const profesionales = useLoad(() => catalogoApi.profesionales(), []);
  const turnos = useLoad(() => turnosApi.listar(), []);

  const [profesionalId, setProfesionalId] = useState('');
  const [calendarId, setCalendarId] = useState('demo-calendar@example.test');
  const [oauthRef, setOauthRef] = useState('demo-oauth-ref');
  const [turnoId, setTurnoId] = useState('');
  const [linkId, setLinkId] = useState('');
  const [token, setToken] = useState('demo-oauth-ref');
  const [eventId, setEventId] = useState('externo-demo');
  const [desde, setDesde] = useState(haceDias(15));
  const [hasta, setHasta] = useState(sumaDias(30));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const bloqueos = useLoad(
    () => calendarioApi.bloqueos(desde, hasta),
    [desde, hasta],
  );

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

  function handleConectar(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        calendarioApi.conectar({
          profesional_id: profesionalId,
          gcal_calendar_id: calendarId,
          oauth_ref: oauthRef,
        }),
      () => links.reload(),
    );
  }

  function handlePush(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    const turno = turnos.data?.find((t) => t.id === turnoId);
    if (!turno) {
      setError('Elegí un turno.');
      return;
    }
    void accion(
      () =>
        calendarioApi.push({
          turno_id: turno.id,
          profesional_id: turno.profesional_id,
          inicio: turno.inicio,
          fin: turno.fin,
          estado: turno.estado,
        }),
      () => bloqueos.reload(),
    );
  }

  function handleWebhook(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        calendarioApi.webhook({
          link_id: linkId,
          token,
          event_id: eventId,
          inicio: enDias(2, 15),
          fin: enDias(2, 16),
          resumen: 'Evento externo demo',
        }),
      () => bloqueos.reload(),
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-14"
        title="Google Calendar"
        description="Push de turnos y bloqueos externos informativos. OAuth simulado en la demo."
        actions={<StatusBadge tone="pending">{links.data?.length ?? 0} links</StatusBadge>}
      />
      <ErrorNotice error={error ?? links.error ?? profesionales.error ?? turnos.error ?? bloqueos.error} />

      <div className="two-columns">
        <Section title="Conectar calendario">
          <form className="form-grid" onSubmit={handleConectar}>
            <Select
              label="Profesional"
              value={profesionalId}
              onChange={setProfesionalId}
              options={[
                { value: '', label: 'Elegí un profesional' },
                ...(profesionales.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
              ]}
            />
            <Field
              label="Calendar ID"
              value={calendarId}
              onChange={(event) => setCalendarId(event.target.value)}
            />
            <Field
              label="Referencia OAuth"
              value={oauthRef}
              onChange={(event) => setOauthRef(event.target.value)}
              hint="En la demo es un texto ficticio."
            />
            <div className="form-actions">
              <Button type="submit" isLoading={busy}>
                Conectar
              </Button>
            </div>
          </form>
        </Section>

        <Section title="Push de turno">
          <form className="form-grid" onSubmit={handlePush}>
            <Select
              label="Turno"
              value={turnoId}
              onChange={setTurnoId}
              options={[
                { value: '', label: 'Elegí un turno' },
                ...(turnos.data ?? []).map((t) => ({
                  value: t.id,
                  label: `${fecha(t.inicio)} · ${t.estado}`,
                })),
              ]}
            />
            <div className="form-actions">
              <Button type="submit" isLoading={busy}>
                Pushear a GCal
              </Button>
            </div>
          </form>
        </Section>
      </div>

      <Section title="Links conectados">
        <DataTable
          rows={links.data ?? []}
          keyOf={(link) => link.id}
          empty="Sin calendarios conectados."
          columns={[
            {
              header: 'Profesional',
              cell: (l) => profesionales.data?.find((p) => p.id === l.profesional_id)?.nombre ?? l.profesional_id.slice(0, 8),
            },
            { header: 'Calendario', cell: (l) => l.gcal_calendar_id },
            {
              header: 'Estado',
              cell: (l) => (
                <StatusBadge tone={l.estado === 'CONECTADO' ? 'success' : 'danger'}>
                  {l.estado}
                </StatusBadge>
              ),
            },
            { header: 'Última sync', cell: (l) => (l.ultima_sync ? fecha(l.ultima_sync) : '—') },
            {
              header: 'Acciones',
              align: 'right',
              cell: (l) =>
                l.estado === 'CONECTADO' ? (
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() =>
                      void accion(
                        () => calendarioApi.desconectar(l.id),
                        () => links.reload(),
                      )
                    }
                  >
                    Desconectar
                  </Button>
                ) : (
                  <span className="muted">—</span>
                ),
            },
          ]}
        />
      </Section>

      <Section title="Simular evento externo (webhook)">
        <form className="form-grid" onSubmit={handleWebhook}>
          <Select
            label="Link"
            value={linkId}
            onChange={setLinkId}
            options={[
              { value: '', label: 'Elegí un link' },
              ...(links.data ?? []).map((l) => ({ value: l.id, label: l.gcal_calendar_id })),
            ]}
          />
          <Field
            label="Token del link"
            value={token}
            onChange={(event) => setToken(event.target.value)}
          />
          <Field
            label="Event ID"
            value={eventId}
            onChange={(event) => setEventId(event.target.value)}
          />
          <div className="form-actions">
            <Button type="submit" isLoading={busy}>
              Enviar evento
            </Button>
          </div>
        </form>
      </Section>

      <Section title="Bloqueos externos" description="Rango de consulta.">
        <div className="form-grid">
          <Field
            label="Desde"
            type="datetime-local"
            value={aInputLocal(desde)}
            onChange={(event) => setDesde(new Date(event.target.value).toISOString())}
          />
          <Field
            label="Hasta"
            type="datetime-local"
            value={aInputLocal(hasta)}
            onChange={(event) => setHasta(new Date(event.target.value).toISOString())}
          />
          <div className="form-actions">
            <Button variant="secondary" onClick={() => bloqueos.reload()}>
              Actualizar
            </Button>
          </div>
        </div>
        <DataTable
          rows={bloqueos.data ?? []}
          keyOf={(evento) => evento.id}
          empty="Sin bloqueos en el rango."
          columns={[
            { header: 'Inicio', cell: (e) => fecha(e.inicio) },
            { header: 'Resumen', cell: (e) => e.resumen },
            {
              header: 'Estado',
              cell: (e) => (
                <StatusBadge tone={e.estado === 'CONFLICTO_SISTEMA' ? 'danger' : 'pending'}>
                  {e.estado}
                </StatusBadge>
              ),
            },
          ]}
        />
      </Section>
    </div>
  );
}
