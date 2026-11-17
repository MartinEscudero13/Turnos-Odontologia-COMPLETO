import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { catalogoApi, clinicaApi, type Presupuesto } from '../../api';
import { errorMessage, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import {
  DataTable,
  ErrorNotice,
  Section,
  Select,
  TextArea,
  fecha,
  money,
  soloFecha,
} from '../../components/ui';

export function ClinicaPage(): JSX.Element {
  const [params, setParams] = useSearchParams();
  const pacienteId = params.get('paciente') ?? '';
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const profesionales = useLoad(() => catalogoApi.profesionales(), []);
  const prestaciones = useLoad(() => catalogoApi.prestaciones(), []);

  const ficha = useLoad(
    () => (pacienteId ? clinicaApi.ficha(pacienteId) : Promise.resolve(null)),
    [pacienteId],
  );
  const consentimientos = useLoad(
    () => (pacienteId ? clinicaApi.consentimientos(pacienteId) : Promise.resolve([])),
    [pacienteId],
  );
  const evoluciones = useLoad(
    () => (pacienteId ? clinicaApi.evoluciones(pacienteId) : Promise.resolve([])),
    [pacienteId],
  );
  const hallazgos = useLoad(
    () => (pacienteId ? clinicaApi.hallazgos(pacienteId) : Promise.resolve([])),
    [pacienteId],
  );
  const presupuestos = useLoad(
    () => (pacienteId ? clinicaApi.presupuestos(pacienteId) : Promise.resolve([])),
    [pacienteId],
  );

  const [profesionalId, setProfesionalId] = useState('');
  const [texto, setTexto] = useState('');
  const [pieza, setPieza] = useState('36');
  const [superficie, setSuperficie] = useState('OCLUSAL');
  const [hallazgo, setHallazgo] = useState('CARIES');
  const [prestacionId, setPrestacionId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const paciente = pacientes.data?.find((p) => p.id === pacienteId) ?? null;

  useEffect(() => {
    if (!profesionalId && profesionales.data && profesionales.data.length > 0) {
      setProfesionalId(profesionales.data[0].id);
    }
  }, [profesionalId, profesionales.data]);

  function reloadAll(): void {
    ficha.reload();
    consentimientos.reload();
    evoluciones.reload();
    hallazgos.reload();
    presupuestos.reload();
  }

  async function accion(task: () => Promise<unknown>): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await task();
      reloadAll();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function nombrePrestacion(id: string): string {
    return prestaciones.data?.find((p) => p.id === id)?.nombre ?? id.slice(0, 8);
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-08 / C-09"
        title="Clínica"
        description="Ficha, consentimiento, evoluciones, odontograma y presupuesto."
        actions={
          paciente ? (
            <StatusBadge tone="success">{paciente.nombre}</StatusBadge>
          ) : (
            <StatusBadge tone="pending">Elegí un paciente</StatusBadge>
          )
        }
      />
      <ErrorNotice
        error={
          error ??
          pacientes.error ??
          profesionales.error ??
          prestaciones.error ??
          (pacienteId ? consentimientos.error ?? evoluciones.error ?? hallazgos.error : null)
        }
      />

      <Section title="Paciente" description="El historial clínico se abre por paciente.">
        <Select
          label="Paciente"
          value={pacienteId}
          onChange={(value) => setParams(value ? { paciente: value } : {})}
          options={[
            { value: '', label: 'Elegí un paciente' },
            ...(pacientes.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
          ]}
        />
      </Section>

      {!pacienteId ? (
        <p className="table-empty">
          Elegí un paciente o creá uno en <Link to="/app/pacientes">Pacientes</Link>.
        </p>
      ) : (
        <>
          <div className="two-columns">
            <Section
              title="Consentimiento"
              description="Requisito previo a ficha, evolución y hallazgos (RN-AU-03)."
            >
              <p className="muted">
                {consentimientos.data && consentimientos.data.length > 0
                  ? `Firmado el ${soloFecha(consentimientos.data[0].timestamp)} (${consentimientos.data[0].canal})`
                  : 'Sin consentimiento registrado.'}
              </p>
              <Button
                variant="secondary"
                isLoading={busy}
                onClick={() =>
                  void accion(() =>
                    clinicaApi.crearConsentimiento({
                      paciente_id: pacienteId,
                      timestamp: new Date().toISOString(),
                      canal: 'mostrador',
                    }),
                  )
                }
              >
                Registrar consentimiento
              </Button>
            </Section>

            <Section title="Ficha clínica">
              <p className="muted">
                {ficha.data
                  ? `Ficha creada el ${soloFecha(ficha.data.creado_en)}`
                  : 'Todavía no hay ficha para este paciente.'}
              </p>
              <Button
                variant="secondary"
                isLoading={busy}
                onClick={() => void accion(() => clinicaApi.crearFicha(pacienteId))}
              >
                Crear ficha
              </Button>
            </Section>
          </div>

          <Section title="Evoluciones" description="Registro clínico append-only.">
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void accion(() =>
                  clinicaApi.crearEvolucion({
                    paciente_id: pacienteId,
                    profesional_id: profesionalId,
                    fecha: new Date().toISOString(),
                    texto,
                  }),
                );
                setTexto('');
              }}
            >
              <Select
                label="Profesional"
                value={profesionalId}
                onChange={setProfesionalId}
                options={[
                  { value: '', label: 'Elegí un profesional' },
                  ...(profesionales.data ?? []).map((p) => ({
                    value: p.id,
                    label: p.nombre,
                  })),
                ]}
              />
              <TextArea label="Evolución" value={texto} onChange={setTexto} />
              <div className="form-actions">
                <Button type="submit" isLoading={busy}>
                  Registrar evolución
                </Button>
              </div>
            </form>
            <DataTable
              rows={evoluciones.data ?? []}
              keyOf={(e) => e.id}
              empty="Sin evoluciones."
              columns={[
                { header: 'Fecha', cell: (e) => fecha(e.fecha) },
                { header: 'Texto', cell: (e) => e.texto },
              ]}
            />
          </Section>

          <Section title="Odontograma" description="Hallazgos FDI por pieza y superficie.">
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void accion(() =>
                  clinicaApi.crearHallazgo({
                    paciente_id: pacienteId,
                    pieza_fdi: Number(pieza),
                    superficie,
                    hallazgo,
                    fecha: new Date().toISOString(),
                    profesional_id: profesionalId,
                  }),
                );
              }}
            >
              <Field
                label="Pieza FDI"
                type="number"
                value={pieza}
                onChange={(event) => setPieza(event.target.value)}
              />
              <Field
                label="Superficie"
                value={superficie}
                onChange={(event) => setSuperficie(event.target.value)}
              />
              <Field
                label="Hallazgo"
                value={hallazgo}
                onChange={(event) => setHallazgo(event.target.value)}
              />
              <div className="form-actions">
                <Button type="submit" isLoading={busy}>
                  Registrar hallazgo
                </Button>
              </div>
            </form>
            <DataTable
              rows={hallazgos.data ?? []}
              keyOf={(h) => h.id}
              empty="Sin hallazgos."
              columns={[
                { header: 'Pieza', cell: (h) => h.pieza_fdi },
                { header: 'Superficie', cell: (h) => h.superficie ?? '—' },
                { header: 'Hallazgo', cell: (h) => h.hallazgo },
                {
                  header: 'Estado',
                  cell: (h) => (
                    <StatusBadge tone={h.resuelto ? 'success' : 'pending'}>
                      {h.resuelto ? 'Resuelto' : 'Abierto'}
                    </StatusBadge>
                  ),
                },
                {
                  header: 'Acciones',
                  align: 'right',
                  cell: (h) =>
                    h.resuelto ? (
                      <span className="muted">—</span>
                    ) : (
                      <Button
                        variant="quiet"
                        isLoading={busy}
                        onClick={() =>
                          void accion(() => clinicaApi.resolverHallazgo(h.id))
                        }
                      >
                        Resolver
                      </Button>
                    ),
                },
              ]}
            />
          </Section>

          <Section
            title="Presupuestos"
            description="Cobertura OS aplicada por línea y emisión con vencimiento."
            actions={
              <Button
                variant="secondary"
                isLoading={busy}
                onClick={() => void accion(() => clinicaApi.crearPresupuesto(pacienteId))}
              >
                Nuevo presupuesto
              </Button>
            }
          >
            <Select
              label="Prestación para agregar"
              value={prestacionId}
              onChange={setPrestacionId}
              options={[
                { value: '', label: 'Elegí una prestación' },
                ...(prestaciones.data ?? []).map((p) => ({
                  value: p.id,
                  label: `${p.nombre} · ${money(p.precio_base)}`,
                })),
              ]}
            />
            <div className="presupuesto-list">
              {(presupuestos.data ?? []).map((presupuesto) => (
                <PresupuestoCard
                  key={presupuesto.id}
                  presupuesto={presupuesto}
                  busy={busy}
                  nombrePrestacion={nombrePrestacion}
                  prestacionId={prestacionId}
                  onAddLine={() =>
                    void accion(() =>
                      clinicaApi.agregarLinea(presupuesto.id, {
                        prestacion_id: prestacionId,
                      }),
                    )
                  }
                  onEmit={() =>
                    void accion(() =>
                      clinicaApi.emitir(
                        presupuesto.id,
                        new Date(Date.now() + 30 * 86_400_000).toISOString(),
                      ),
                    )
                  }
                  onDecidir={(lineaId, acepta) =>
                    void accion(() =>
                      clinicaApi.decidir(presupuesto.id, {
                        linea_id: lineaId,
                        acepta,
                        canal: 'mostrador',
                        // Sin medio la aceptación deja un cobro pendiente en caja.
                        medio: null,
                      }),
                    )
                  }
                />
              ))}
              {(presupuestos.data ?? []).length === 0 ? (
                <p className="table-empty">Sin presupuestos. Creá uno.</p>
              ) : null}
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

function PresupuestoCard({
  presupuesto,
  busy,
  nombrePrestacion,
  prestacionId,
  onAddLine,
  onEmit,
  onDecidir,
}: {
  presupuesto: Presupuesto;
  busy: boolean;
  nombrePrestacion: (id: string) => string;
  prestacionId: string;
  onAddLine: () => void;
  onEmit: () => void;
  onDecidir: (lineaId: string, acepta: boolean) => void;
}): JSX.Element {
  const decidible =
    presupuesto.estado === 'VIGENTE' || presupuesto.estado === 'ACEPTADO';
  return (
    <article className="presupuesto-card">
      <header>
        <div>
          <strong>Presupuesto {presupuesto.id.slice(0, 8)}</strong>
          <p className="muted">Creado {soloFecha(presupuesto.creado_en)}</p>
        </div>
        <StatusBadge tone={presupuesto.estado === 'BORRADOR' ? 'pending' : 'success'}>
          {presupuesto.estado}
        </StatusBadge>
      </header>
      <DataTable
        rows={presupuesto.lineas}
        keyOf={(item) => item.linea.id}
        empty="Sin líneas."
        columns={[
          { header: 'Prestación', cell: (item) => nombrePrestacion(item.linea.prestacion_id) },
          { header: 'Monto', cell: (item) => money(item.linea.monto), align: 'right' },
          { header: 'OS', cell: (item) => money(item.linea.cobertura_os), align: 'right' },
          {
            header: 'Paciente',
            cell: (item) => money(item.linea.a_cargo_paciente),
            align: 'right',
          },
          {
            header: 'Decisión',
            align: 'right',
            cell: (item) => {
              if (item.aceptacion) {
                return (
                  <StatusBadge tone={item.aceptacion.acepta ? 'success' : 'danger'}>
                    {item.aceptacion.acepta ? 'Aceptada' : 'Rechazada'}
                  </StatusBadge>
                );
              }
              if (!decidible) return <span className="muted">—</span>;
              return (
                <div className="row-actions">
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() => onDecidir(item.linea.id, true)}
                  >
                    Aceptar
                  </Button>
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() => onDecidir(item.linea.id, false)}
                  >
                    Rechazar
                  </Button>
                </div>
              );
            },
          },
        ]}
      />
      <div className="form-actions">
        <Button
          variant="secondary"
          isLoading={busy}
          disabled={!prestacionId || presupuesto.estado !== 'BORRADOR'}
          onClick={onAddLine}
        >
          Agregar línea
        </Button>
        <Button
          variant="primary"
          isLoading={busy}
          disabled={presupuesto.lineas.length === 0 || presupuesto.estado !== 'BORRADOR'}
          onClick={onEmit}
        >
          Emitir 30 días
        </Button>
      </div>
    </article>
  );
}
