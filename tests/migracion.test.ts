import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';

const SQL_PATH = 'prisma/migrations/003_turnos_anti_solape/migration.sql';
const sql = readFileSync(SQL_PATH, 'utf8');

describe('migración 003 — turnos anti-solape (estructural)', () => {
  it('2.1: habilita btree_gist y crea tabla turnos con timestamptz', () => {
    expect(sql).toMatch(/CREATE EXTENSION IF NOT EXISTS\s+"?btree_gist"?/i);
    expect(sql).toMatch(/CREATE TABLE .*turnos/i);
    expect(sql).toMatch(/inicio\s+timestamptz\s+NOT NULL/i);
    expect(sql).toMatch(/fin\s+timestamptz\s+NOT NULL/i);
    expect(sql).toMatch(/tenant_id.*NOT NULL/i);
    expect(sql).toMatch(/sobreturno\s+boolean\s+NOT NULL\s+DEFAULT false/i);
    expect(sql).toMatch(/origen/i);
    expect(sql).toMatch(/token_publico/i);
  });

  it('2.2: dos EXCLUDE parciales (profesional y sillón) sobre tstzrange', () => {
    const excludes = sql.match(/ADD CONSTRAINT \S+ EXCLUDE USING gist/gi);
    expect(excludes).toHaveLength(2);
    expect(sql).toMatch(/tstzrange\s*\(\s*inicio\s*,\s*fin\s*\)\s*WITH\s*&&/i);
    expect(sql).toMatch(/profesional_id\s+WITH\s*=/i);
    expect(sql).toMatch(/sillon_id\s+WITH\s*=/i);
    // Predicado parcial: excluye finales y sobreturnos.
    expect(sql).toMatch(/WHERE.*CANCELADO.*REPROGRAMADO.*sobreturno/i);
  });

  it('2.3: tres índices y RLS por tenant_id', () => {
    expect(sql).toMatch(/CREATE INDEX.*tenant_id.*profesional_id.*inicio/is);
    expect(sql).toMatch(/CREATE INDEX.*tenant_id.*sillon_id.*inicio/is);
    expect(sql).toMatch(/CREATE INDEX.*tenant_id.*estado/is);
    expect(sql).toMatch(/ENABLE ROW LEVEL SECURITY/i);
    expect(sql).toMatch(/current_setting\s*\(\s*'app\.tenant_id'\s*\)/i);
  });

  it('integridad: fin > inicio, estados/orígenes cerrados, sobreturno exige motivo', () => {
    expect(sql).toMatch(/CHECK\s*\(\s*fin\s*>\s*inicio\s*\)/i);
    expect(sql).toMatch(/'PENDIENTE'.*'CONFIRMADO'.*'CANCELADO'.*'REPROGRAMADO'/is);
    expect(sql).toMatch(/sobreturno\s*=\s*false\s+OR\s+motivo_sobreturno\s+IS NOT NULL/i);
    expect(sql).toMatch(/DEFAULT\s+'PENDIENTE'/i);
  });

  it('token_publico opcional con unicidad parcial', () => {
    expect(sql).toMatch(/CREATE UNIQUE INDEX.*token_publico.*WHERE token_publico IS NOT NULL/is);
  });
});
