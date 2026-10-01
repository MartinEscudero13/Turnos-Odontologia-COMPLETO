/**
 * Seed ficticio de test — task 2.4. Datos 100 % ficticios (sin PHI),
 * reutilizable en tests. Idempotente vía ON CONFLICT DO NOTHING.
 * Fija app.tenant_id para operar bajo RLS como un tenant real.
 */

export interface SeedTest {
  readonly tenantId: string;
  readonly profesionalId: string;
  readonly sillonId: string;
  readonly pacienteId: string;
  readonly prestacion: { readonly id: string; readonly duracionMin: number };
}

export const SEED_TEST: SeedTest = {
  tenantId: 'tenant-demo-c05',
  profesionalId: '11111111-1111-4111-8111-111111111111',
  sillonId: '22222222-2222-4222-8222-222222222222',
  pacienteId: '33333333-3333-4333-8333-333333333333',
  prestacion: {
    id: '44444444-4444-4444-8444-444444444444',
    duracionMin: 30,
  },
};

export function seedTestSql(): string {
  const s = SEED_TEST;
  return [
    `SELECT set_config('app.tenant_id', '${s.tenantId}', false);`,
    `INSERT INTO turnos (id, tenant_id, profesional_id, sillon_id, paciente_id, prestacion_id, inicio, fin, estado, sobreturno, origen)`,
    `VALUES ('55555555-5555-4555-8555-555555555555', '${s.tenantId}', '${s.profesionalId}', '${s.sillonId}', '${s.pacienteId}', '${s.prestacion.id}', '2026-10-06T13:00:00Z', '2026-10-06T13:30:00Z', 'PENDIENTE', false, 'RECEPCION')`,
    `ON CONFLICT (id) DO NOTHING;`,
    `-- Seed ficticio demo c05: sin datos personales reales (sin PHI).`,
  ].join('\n');
}
