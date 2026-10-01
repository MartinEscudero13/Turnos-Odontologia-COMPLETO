import { describe, expect, it } from 'vitest';
import { SEED_TEST, seedTestSql } from '../prisma/seed-test.js';

describe('seed ficticio de test (2.4)', () => {
  it('expone 1 tenant + profesional + sillón + prestación 30 min, sin PHI', () => {
    expect(SEED_TEST.tenantId).toBe('tenant-demo-c05');
    expect(SEED_TEST.prestacion.duracionMin).toBe(30);
    expect(SEED_TEST.profesionalId).toBeTruthy();
    expect(SEED_TEST.sillonId).toBeTruthy();
    // Sin datos personales reales: valores marcados como ficticios.
    expect(JSON.stringify(SEED_TEST).toLowerCase()).toMatch(/demo|ficticio/);
  });

  it('es idempotente: dos llamadas generan el mismo SQL con ON CONFLICT DO NOTHING', () => {
    const a = seedTestSql();
    const b = seedTestSql();
    expect(a).toBe(b);
    expect(a).toMatch(/ON CONFLICT.*DO NOTHING/is);
    expect(a).toMatch(/app\.tenant_id/);
  });
});
