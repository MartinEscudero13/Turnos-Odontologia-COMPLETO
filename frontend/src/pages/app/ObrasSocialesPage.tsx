import { useState, type FormEvent } from 'react';
import {
  apiBlob,
  catalogoApi,
  obrasSocialesApi,
  type Liquidacion,
} from '../../api';
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
  fecha,
  money,
  soloFecha,
} from '../../components/ui';

function mes(): { desde: string; hasta: string } {
  const now = new Date();
  const desde = new Date(now.getFullYear(), now.getMonth(), 1);
  const hasta = new Date(now.getFullYear(), now.getMonth() + 1, 1);
  return { desde: desde.toISOString().slice(0, 10), hasta: hasta.toISOString().slice(0, 10) };
}

export function ObrasSocialesPage(): JSX.Element {
  const obras = useLoad(() => obrasSocialesApi.listar(), []);
  const coberturas = useLoad(() => obrasSocialesApi.coberturas(), []);
  const liquidaciones = useLoad(() => obrasSocialesApi.liquidaciones(), []);
  const pacientes = useLoad(() => catalogoApi.pacientes(), []);
  const prestaciones = useLoad(() => catalogoApi.prestaciones(), []);

  const [nombre, setNombre] = useState('');
  const [obraId, setObraId] = useState('');
  const [prestacionId, setPrestacionId] = useState('');
  const [modo, setModo] = useState('PORCENTAJE');
  const [valor, setValor] = useState('50');
  const [tope, setTope] = useState('');
  const [pacienteId, setPacienteId] = useState('');
  const [tramo, setTramo] = useState<{
    precio_base_centavos: number;
    cobertura_os: number;
    a_cargo_paciente: number;
    origen: string;
    validada_en_vivo: boolean;
  } | null>(null);
  const [rango, setRango] = useState(mes());
  const [detalle, setDetalle] = useState<Liquidacion | null>(null);
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

  async function descargar(liquidacion: Liquidacion): Promise<void> {
    setError(null);
    try {
      const blob = await apiBlob(obrasSocialesApi.csvUrl(liquidacion.id));
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `liquidacion-${liquidacion.id}.csv`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(errorMessage(cause));
    }
  }

  function nombrePrestacion(id: string): string {
    return prestaciones.data?.find((p) => p.id === id)?.nombre ?? id.slice(0, 8);
  }

  function handleObra(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(() => obrasSocialesApi.crear(nombre), () => {
      setNombre('');
      obras.reload();
    });
  }

  function handleCobertura(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        obrasSocialesApi.configurar({
          obra_social_id: obraId,
          prestacion_id: prestacionId,
          modo,
          valor: Number(valor),
          tope_centavos: tope ? Number(tope) : null,
        }),
      () => coberturas.reload(),
    );
  }

  function handlePreview(): void {
    void accion(async () => {
      const result = await obrasSocialesApi.preview(pacienteId, prestacionId);
      setTramo(result);
    });
  }

  function handleLiquidacion(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(
      () =>
        obrasSocialesApi.generar({
          obra_social_id: obraId,
          desde: rango.desde,
          hasta: rango.hasta,
        }),
      () => liquidaciones.reload(),
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-12"
        title="Obras sociales"
        description="Cobertura configurada, no validada en vivo. Liquidación por período."
        actions={<StatusBadge tone="pending">{obras.data?.length ?? 0} OS</StatusBadge>}
      />
      <ErrorNotice
        error={
          error ??
          obras.error ??
          coberturas.error ??
          liquidaciones.error ??
          pacientes.error ??
          prestaciones.error
        }
      />

      <Section title="Obras sociales" description="Activar o desactivar sin borrar historial.">
        <DataTable
          rows={obras.data ?? []}
          keyOf={(obra) => obra.id}
          empty="Sin obras sociales."
          columns={[
            { header: 'Nombre', cell: (o) => o.nombre },
            {
              header: 'Estado',
              cell: (o) => (
                <StatusBadge tone={o.activa ? 'success' : 'danger'}>
                  {o.activa ? 'Activa' : 'Inactiva'}
                </StatusBadge>
              ),
            },
            {
              header: 'Acciones',
              align: 'right',
              cell: (o) => (
                <Button
                  variant="quiet"
                  isLoading={busy}
                  onClick={() =>
                    void accion(
                      () => obrasSocialesApi.cambiarEstado(o.id, !o.activa),
                      () => obras.reload(),
                    )
                  }
                >
                  {o.activa ? 'Desactivar' : 'Activar'}
                </Button>
              ),
            },
          ]}
        />
      </Section>

      <div className="two-columns">
        <Section title="Nueva obra social">
          <form className="form-grid" onSubmit={handleObra}>
            <Field
              label="Nombre"
              value={nombre}
              onChange={(event) => setNombre(event.target.value)}
              placeholder="OS Demo Nueva"
            />
            <div className="form-actions">
              <Button type="submit" isLoading={busy}>
                Crear OS
              </Button>
            </div>
          </form>
        </Section>

        <Section title="Configurar cobertura" description="Upsert por (OS × prestación).">
          <form className="form-grid" onSubmit={handleCobertura}>
            <Select
              label="Obra social"
              value={obraId}
              onChange={setObraId}
              options={[
                { value: '', label: 'Elegí una OS' },
                ...(obras.data ?? []).map((o) => ({ value: o.id, label: o.nombre })),
              ]}
            />
            <Select
              label="Prestación"
              value={prestacionId}
              onChange={setPrestacionId}
              options={[
                { value: '', label: 'Elegí una prestación' },
                ...(prestaciones.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
              ]}
            />
            <Select
              label="Modo"
              value={modo}
              onChange={setModo}
              options={[
                { value: 'PORCENTAJE', label: 'Porcentaje' },
                { value: 'MONTO', label: 'Monto fijo' },
              ]}
            />
            <Field
              label="Valor"
              type="number"
              value={valor}
              onChange={(event) => setValor(event.target.value)}
            />
            <Field
              label="Tope en centavos (opcional)"
              type="number"
              value={tope}
              onChange={(event) => setTope(event.target.value)}
            />
            <div className="form-actions">
              <Button type="submit" isLoading={busy}>
                Guardar cobertura
              </Button>
            </div>
          </form>
        </Section>
      </div>

      <Section title="Simular cobertura">
        <div className="form-grid">
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
              ...(prestaciones.data ?? []).map((p) => ({ value: p.id, label: p.nombre })),
            ]}
          />
          <div className="form-actions">
            <Button variant="secondary" isLoading={busy} onClick={handlePreview}>
              Calcular
            </Button>
          </div>
        </div>
        {tramo ? (
          <div className="stat-grid">
            <div className="stat">
              <span className="stat-label">Precio base</span>
              <strong className="stat-value">{money(tramo.precio_base_centavos)}</strong>
            </div>
            <div className="stat">
              <span className="stat-label">Cobertura OS</span>
              <strong className="stat-value">{money(tramo.cobertura_os)}</strong>
            </div>
            <div className="stat">
              <span className="stat-label">A cargo paciente</span>
              <strong className="stat-value">{money(tramo.a_cargo_paciente)}</strong>
            </div>
            <div className="stat">
              <span className="stat-label">Origen</span>
              <strong className="stat-value">{tramo.origen}</strong>
            </div>
          </div>
        ) : null}
      </Section>

      <Section title="Coberturas configuradas">
        <DataTable
          rows={coberturas.data ?? []}
          keyOf={(cobertura) => cobertura.id}
          empty="Sin coberturas configuradas."
          columns={[
            { header: 'OS', cell: (c) => obras.data?.find((o) => o.id === c.obra_social_id)?.nombre ?? c.obra_social_id.slice(0, 8) },
            { header: 'Prestación', cell: (c) => nombrePrestacion(c.prestacion_id) },
            { header: 'Modo', cell: (c) => c.modo },
            {
              header: 'Valor',
              cell: (c) => (c.modo === 'PORCENTAJE' ? `${c.valor}%` : money(c.valor)),
              align: 'right',
            },
            { header: 'Tope', cell: (c) => (c.tope_centavos ? money(c.tope_centavos) : '—'), align: 'right' },
          ]}
        />
      </Section>

      <Section title="Liquidaciones">
        <form className="form-grid" onSubmit={handleLiquidacion}>
          <Select
            label="Obra social"
            value={obraId}
            onChange={setObraId}
            options={[
              { value: '', label: 'Elegí una OS' },
              ...(obras.data ?? []).map((o) => ({ value: o.id, label: o.nombre })),
            ]}
          />
          <Field
            label="Desde"
            type="date"
            value={rango.desde}
            onChange={(event) => setRango({ ...rango, desde: event.target.value })}
          />
          <Field
            label="Hasta"
            type="date"
            value={rango.hasta}
            onChange={(event) => setRango({ ...rango, hasta: event.target.value })}
          />
          <div className="form-actions">
            <Button type="submit" isLoading={busy}>
              Generar
            </Button>
          </div>
        </form>
        <DataTable
          rows={liquidaciones.data ?? []}
          keyOf={(liquidacion) => liquidacion.id}
          empty="Sin liquidaciones."
          columns={[
            {
              header: 'OS',
              cell: (l) => obras.data?.find((o) => o.id === l.obra_social_id)?.nombre ?? l.obra_social_id.slice(0, 8),
            },
            { header: 'Período', cell: (l) => `${soloFecha(l.periodo_desde)} → ${soloFecha(l.periodo_hasta)}` },
            {
              header: 'Estado',
              cell: (l) => (
                <StatusBadge tone={l.estado === 'CERRADA' ? 'success' : 'pending'}>
                  {l.estado}
                </StatusBadge>
              ),
            },
            { header: 'Total', cell: (l) => money(l.total_centavos), align: 'right' },
            {
              header: '',
              align: 'right',
              cell: (l: Liquidacion) => (
                <div className="row-actions">
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() =>
                      void accion(async () => {
                        setDetalle(await obrasSocialesApi.detalle(l.id));
                      })
                    }
                  >
                    Detalle
                  </Button>
                  <Button variant="quiet" onClick={() => void descargar(l)}>
                    CSV
                  </Button>
                  {l.estado !== 'CERRADA' ? (
                    <Button
                      variant="quiet"
                      isLoading={busy}
                      onClick={() => void accion(() => obrasSocialesApi.cerrar(l.id), () => liquidaciones.reload())}
                    >
                      Cerrar
                    </Button>
                  ) : null}
                </div>
              ),
            },
          ]}
        />
      </Section>

      <Section
        title="Detalle de liquidación"
        description="Líneas incluidas en la liquidación seleccionada."
        actions={
          detalle ? (
            <Button variant="quiet" onClick={() => setDetalle(null)}>
              Limpiar
            </Button>
          ) : null
        }
      >
        {detalle ? (
          <>
            <p className="muted">
              {detalle.estado} · {soloFecha(detalle.periodo_desde)} →{' '}
              {soloFecha(detalle.periodo_hasta)} · {money(detalle.total_centavos)}
            </p>
            <DataTable
              rows={detalle.lineas}
              keyOf={(linea) => `${linea.turno_id}-${linea.fecha}`}
              empty="La liquidación no tiene líneas."
              columns={[
                { header: 'Turno', cell: (l) => l.turno_id.slice(0, 8) },
                { header: 'Fecha', cell: (l) => fecha(l.fecha) },
                {
                  header: 'Monto',
                  cell: (l) => money(l.monto_centavos),
                  align: 'right',
                },
              ]}
            />
          </>
        ) : (
          <p className="table-empty">Elegí una liquidación y tocá “Detalle”.</p>
        )}
      </Section>
    </div>
  );
}
