import { useState } from 'react';
import { senasApi } from '../../api';
import { hoyISO, useLoad } from '../../hooks';
import { Field } from '../../components/Field';
import { PageHeader } from '../../components/PageHeader';
import { StatusBadge } from '../../components/StatusBadge';
import { DataTable, ErrorNotice, Section, fecha, money } from '../../components/ui';

function haceDias(dias: number): string {
  const date = new Date();
  date.setDate(date.getDate() - dias);
  return date.toISOString().slice(0, 10);
}

export function SenasPage(): JSX.Element {
  const [desde, setDesde] = useState(haceDias(60));
  const [hasta, setHasta] = useState(hoyISO());
  const senas = useLoad(() => senasApi.listar(desde, hasta), [desde, hasta]);

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="C-11"
        title="Señas"
        description="Estado de las señas del período. El cobro real se hace en Mercado Pago."
        actions={<StatusBadge tone="pending">{senas.data?.length ?? 0} señas</StatusBadge>}
      />
      <ErrorNotice error={senas.error} />

      <Section title="Período">
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
      </Section>

      <Section title="Señas del período">
        <DataTable
          rows={senas.data ?? []}
          keyOf={(sena) => sena.sena_id}
          empty="Sin señas en el período."
          columns={[
            {
              header: 'Turno',
              cell: (s) => (s.turno ? fecha(s.turno.inicio) : s.turno_id.slice(0, 8)),
            },
            { header: 'Monto', cell: (s) => money(s.monto_centavos), align: 'right' },
            {
              header: 'Estado',
              cell: (s) => (
                <StatusBadge
                  tone={
                    s.estado === 'ACREDITADA' || s.estado === 'APLICADA'
                      ? 'success'
                      : s.estado === 'DEVUELTA' || s.estado === 'LIBERADA'
                        ? 'danger'
                        : 'pending'
                  }
                >
                  {s.estado}
                </StatusBadge>
              ),
            },
            { header: 'Preferencia', cell: (s) => s.preferencia_estado },
          ]}
        />
      </Section>
    </div>
  );
}
