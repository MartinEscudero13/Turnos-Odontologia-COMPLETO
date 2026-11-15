import { useState, type FormEvent } from 'react';
import { cajaApi } from '../../api';
import { useAuth } from '../../auth/AuthContext';
import { errorMessage, hoyISO, useLoad } from '../../hooks';
import { Button } from '../../components/Button';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section, Select, money } from '../../components/ui';

export function CajaPage(): JSX.Element {
  const { session } = useAuth();
  const [fecha, setFecha] = useState(hoyISO());
  const dia = useLoad(() => cajaApi.dia(fecha), [fecha]);
  const [monto, setMonto] = useState('15000');
  const [medio, setMedio] = useState('EFECTIVO');
  const [tipo, setTipo] = useState('INGRESO');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function accion(task: () => Promise<unknown>): Promise<void> {
    setError(null);
    setBusy(true);
    try {
      await task();
      dia.reload();
    } catch (cause) {
      setError(errorMessage(cause));
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    void accion(() =>
      cajaApi.registrar({
        monto: Math.round(Number(monto)),
        medio,
        tipo,
        fecha,
      }),
    );
  }

  const totales = dia.data?.totales_vigentes;

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-10"
        title="Caja"
        description="Movimientos del día, totales por medio y cierre inmutable."
        actions={
          <StatusBadge tone={dia.data?.estado === 'cerrado' ? 'danger' : 'success'}>
            {dia.data?.estado ?? '—'}
          </StatusBadge>
        }
      />
      <ErrorNotice error={error ?? dia.error} />

      <Section title="Día operativo">
        <Field
          label="Fecha"
          type="date"
          value={fecha}
          onChange={(event) => setFecha(event.target.value)}
        />
      </Section>

      <div className="stat-grid">
        <div className="stat">
          <span className="stat-label">Efectivo</span>
          <strong className="stat-value">{money(totales?.efectivo ?? 0)}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Transferencia</span>
          <strong className="stat-value">{money(totales?.transferencia ?? 0)}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Mercado Pago</span>
          <strong className="stat-value">{money(totales?.mp ?? 0)}</strong>
        </div>
        <div className="stat">
          <span className="stat-label">Obra social</span>
          <strong className="stat-value">{money(totales?.os ?? 0)}</strong>
        </div>
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
                  fecha,
                }),
              )
            }
          >
            Cerrar día
          </Button>
        }
      >
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
          ]}
        />
      </Section>
    </div>
  );
}
