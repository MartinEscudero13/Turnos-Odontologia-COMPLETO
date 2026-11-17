import { useState, type FormEvent } from 'react';
import { cajaApi, type CierreCaja } from '../../api';
import { useAuth } from '../../auth/AuthContext';
import { errorMessage, hoyISO, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import {
  DataTable,
  ErrorNotice,
  Section,
  Select,
  Stat,
  fecha,
  money,
  soloFecha,
} from '../../components/ui';

function inicioMes(): string {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
}

function totalesCierre(cierre: CierreCaja): number {
  return (
    cierre.totales.total_efectivo +
    cierre.totales.total_transferencia +
    cierre.totales.total_mp +
    cierre.totales.total_os_cobrado
  );
}

export function CajaPage(): JSX.Element {
  const { session } = useAuth();
  const [fechaDia, setFechaDia] = useState(hoyISO());
  const dia = useLoad(() => cajaApi.dia(fechaDia), [fechaDia]);
  const pendientes = useLoad(() => cajaApi.pendientes(fechaDia), [fechaDia]);
  const [desde, setDesde] = useState(inicioMes());
  const [hasta, setHasta] = useState(hoyISO());
  const cierres = useLoad(() => cajaApi.cierres(desde, hasta), [desde, hasta]);
  const reporte = useLoad(() => cajaApi.reporte(desde, hasta), [desde, hasta]);

  const [monto, setMonto] = useState('15000');
  const [medio, setMedio] = useState('EFECTIVO');
  const [tipo, setTipo] = useState('INGRESO');
  const [motivo, setMotivo] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function reloadDia(): void {
    dia.reload();
    pendientes.reload();
  }

  async function accion(task: () => Promise<unknown>, after: () => void = reloadDia): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await task();
      after();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function revisarRango(): void {
    cierres.reload();
    reporte.reload();
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(() =>
      cajaApi.registrar({
        monto: Math.round(Number(monto)),
        medio,
        tipo,
        fecha: fechaDia,
      }),
    );
  }

  function anular(movimientoId: string): void {
    if (!motivo.trim()) {
      setError('Ingresá un motivo para anular el movimiento.');
      return;
    }
    void accion(() => cajaApi.anular(movimientoId, motivo.trim()), () => {
      setMotivo('');
      reloadDia();
    });
  }

  const totales = dia.data?.totales_vigentes;
  const totalReporte =
    (reporte.data?.totales.efectivo ?? 0) +
    (reporte.data?.totales.transferencia ?? 0) +
    (reporte.data?.totales.mp ?? 0) +
    (reporte.data?.totales.os ?? 0);

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-10"
        title="Caja"
        description="Movimientos del día, cobros pendientes, cierre inmutable y reportes por rango."
        actions={
          <StatusBadge tone={dia.data?.estado === 'cerrado' ? 'danger' : 'success'}>
            {dia.data?.estado ?? '—'}
          </StatusBadge>
        }
      />
      <ErrorNotice
        error={
          error ??
          dia.error ??
          pendientes.error ??
          cierres.error ??
          reporte.error
        }
      />

      <Section title="Día operativo">
        <Field
          label="Fecha"
          type="date"
          value={fechaDia}
          onChange={(event) => setFechaDia(event.target.value)}
        />
      </Section>

      <div className="stat-grid">
        <Stat label="Efectivo" value={money(totales?.efectivo ?? 0)} />
        <Stat label="Transferencia" value={money(totales?.transferencia ?? 0)} />
        <Stat label="Mercado Pago" value={money(totales?.mp ?? 0)} />
        <Stat label="Obra social" value={money(totales?.os ?? 0)} />
      </div>

      <Section title="Registrar movimiento">
        <form className="form-grid" onSubmit={handleSubmit}>
          <Field
            label="Monto en centavos"
            type="number"
            value={monto}
            onChange={(event) => setMonto(event.target.value)}
            hint="15000 = $150,00"
          />
          <Select
            label="Medio"
            value={medio}
            onChange={setMedio}
            options={[
              { value: 'EFECTIVO', label: 'Efectivo' },
              { value: 'TRANSFERENCIA', label: 'Transferencia' },
              { value: 'MP', label: 'Mercado Pago' },
              { value: 'OS', label: 'Obra social' },
            ]}
          />
          <Select
            label="Tipo"
            value={tipo}
            onChange={setTipo}
            options={[
              { value: 'INGRESO', label: 'Ingreso' },
              { value: 'EGRESO', label: 'Egreso' },
            ]}
          />
          <div className="form-actions">
            <Button type="submit" isLoading={busy}>
              Registrar
            </Button>
          </div>
        </form>
      </Section>

      <Section
        title="Movimientos"
        actions={
          <Button
            variant="secondary"
            isLoading={busy}
            disabled={dia.data?.estado === 'cerrado'}
            onClick={() =>
              void accion(() =>
                cajaApi.cerrar({
                  efectivo_contado: totales?.efectivo ?? 0,
                  responsable_id: session?.actor.userId ?? '',
                  fecha: fechaDia,
                }),
              )
            }
          >
            Cerrar día
          </Button>
        }
      >
        <Field
          label="Motivo de anulación"
          value={motivo}
          onChange={(event) => setMotivo(event.target.value)}
          hint="Obligatorio para anular un movimiento (RN-CJ-03)."
        />
        <DataTable
          rows={dia.data?.movimientos ?? []}
          keyOf={(movimiento) => movimiento.id}
          empty="Sin movimientos para la fecha."
          columns={[
            { header: 'Medio', cell: (m) => m.medio },
            { header: 'Tipo', cell: (m) => m.tipo },
            { header: 'Monto', cell: (m) => money(m.monto), align: 'right' },
            {
              header: 'Estado',
              cell: (m) => (
                <StatusBadge tone={m.anulado ? 'danger' : 'success'}>
                  {m.anulado ? 'Anulado' : 'Vigente'}
                </StatusBadge>
              ),
            },
            {
              header: 'Acciones',
              align: 'right',
              cell: (m) =>
                m.anulado ? (
                  <span className="muted">—</span>
                ) : (
                  <Button
                    variant="quiet"
                    disabled={dia.data?.estado === 'cerrado'}
                    onClick={() => anular(m.id)}
                  >
                    Anular
                  </Button>
                ),
            },
          ]}
        />
      </Section>

      <Section
        title="Cobros pendientes"
        description="Líneas de presupuesto aceptadas que todavía no se cobraron."
        actions={<StatusBadge tone="pending">{pendientes.data?.length ?? 0}</StatusBadge>}
      >
        <DataTable
          rows={pendientes.data ?? []}
          keyOf={(p) => p.id}
          empty="Sin cobros pendientes para la fecha."
          columns={[
            { header: 'Fecha', cell: (p) => soloFecha(p.fecha) },
            { header: 'Monto', cell: (p) => money(p.monto_centavos), align: 'right' },
            {
              header: 'Acciones',
              align: 'right',
              cell: (p) => (
                <div className="row-actions">
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() => void accion(() => cajaApi.cobrar(p.id, 'EFECTIVO'))}
                  >
                    Cobrar efectivo
                  </Button>
                  <Button
                    variant="quiet"
                    isLoading={busy}
                    onClick={() => void accion(() => cajaApi.cobrar(p.id, 'TRANSFERENCIA'))}
                  >
                    Cobrar transferencia
                  </Button>
                </div>
              ),
            },
          ]}
        />
      </Section>

      <Section
        title="Cierres y reportes"
        description="Rango de consulta para cierres inmutables y facturación neta."
        actions={
          <Button variant="secondary" onClick={revisarRango}>
            Actualizar rango
          </Button>
        }
      >
        <div className="form-grid">
          <Field
            label="Desde"
            type="date"
            value={desde}
            onChange={(event) => setDesde(event.target.value)}
          />
          <Field
            label="Hasta"
            type="date"
            value={hasta}
            onChange={(event) => setHasta(event.target.value)}
          />
        </div>

        <div className="stat-grid">
          <Stat label="Total neto del rango" value={money(totalReporte)} />
          <Stat label="Cierres" value={reporte.data?.cierres ?? 0} />
          <Stat
            label="Movimientos anulados"
            value={reporte.data?.movimientos_anulados ?? 0}
          />
          <Stat label="Fuente" value={reporte.data?.fuente ?? '—'} />
        </div>

        <DataTable
          rows={reporte.data?.por_dia ?? []}
          keyOf={(d) => d.fecha}
          empty="Sin movimientos en el rango."
          columns={[
            { header: 'Fecha', cell: (d) => soloFecha(d.fecha) },
            { header: 'Efectivo', cell: (d) => money(d.efectivo), align: 'right' },
            { header: 'Transferencia', cell: (d) => money(d.transferencia), align: 'right' },
            { header: 'MP', cell: (d) => money(d.mp), align: 'right' },
            { header: 'OS', cell: (d) => money(d.os), align: 'right' },
            { header: 'Movimientos', cell: (d) => d.movimientos, align: 'right' },
          ]}
        />

        <DataTable
          rows={cierres.data ?? []}
          keyOf={(c) => c.id}
          empty="Sin cierres en el rango."
          columns={[
            { header: 'Fecha', cell: (c) => soloFecha(c.fecha) },
            { header: 'Total', cell: (c) => money(totalesCierre(c)), align: 'right' },
            { header: 'Contado', cell: (c) => money(c.efectivo_contado), align: 'right' },
            {
              header: 'Diferencia',
              align: 'right',
              cell: (c) => (
                <StatusBadge tone={c.diferencia === 0 ? 'success' : 'danger'}>
                  {money(c.diferencia)}
                </StatusBadge>
              ),
            },
            { header: 'Cerrado', cell: (c) => fecha(c.cerrado_at) },
          ]}
        />
      </Section>
    </div>
  );
}
