import { describe, expect, it } from 'vitest';
import { buscarAlternativas } from '../src/turnos/alternativas.js';
import type { HuecoOcupado } from '../src/turnos/alternativas.js';

const d = (s: string): Date => new Date(s);
const T1 = 't1';
const P1 = 'p1';
const S1 = 's1';

function ocupado(
  inicio: string,
  fin: string,
  extra: Partial<HuecoOcupado> = {},
): HuecoOcupado {
  return {
    tenantId: T1,
    profesionalId: P1,
    sillonId: S1,
    inicio: d(inicio),
    fin: d(fin),
    estado: 'CONFIRMADO',
    sobreturno: false,
    ...extra,
  };
}

describe('buscarAlternativas — 409 + 3 huecos', () => {
  it('sin ocupación devuelve 3 huecos ordenados desde el inicio pedido', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [],
    });
    expect(alts).toHaveLength(3);
    // Formato ISO UTC (persistencia timestamptz, D3): 10:00-03:00 = 13:00Z.
    expect(alts[0]).toEqual({
      inicio: '2026-10-06T13:00:00.000Z',
      fin: '2026-10-06T13:30:00.000Z',
    });
    expect(new Date(alts[0]?.inicio ?? '').getTime()).toBeLessThan(
      new Date(alts[1]?.inicio ?? '').getTime(),
    );
    expect(new Date(alts[1]?.inicio ?? '').getTime()).toBeLessThan(
      new Date(alts[2]?.inicio ?? '').getTime(),
    );
  });

  it('salta el hueco ocupado por el mismo profesional', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00')],
    });
    expect(alts).toHaveLength(3);
    expect(new Date(alts[0]?.inicio ?? '').getTime()).toBeGreaterThanOrEqual(
      d('2026-10-06T10:30:00-03:00').getTime(),
    );
  });

  it('turno cancelado no bloquea: el hueco se ofrece', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          estado: 'CANCELADO',
        }),
      ],
    });
    expect(alts[0]).toEqual({
      inicio: '2026-10-06T13:00:00.000Z',
      fin: '2026-10-06T13:30:00.000Z',
    });
  });

  it('bloqueo explícito (licencia/feriado) excluye el hueco', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [],
      bloqueos: [
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T12:00:00-03:00') },
      ],
    });
    expect(alts).toHaveLength(3);
    expect(new Date(alts[0]?.inicio ?? '').getTime()).toBeGreaterThanOrEqual(
      d('2026-10-06T12:00:00-03:00').getTime(),
    );
  });

  it('mismo horario en otro tenant no bloquea (aislamiento)', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          tenantId: 't2-otro-consultorio',
        }),
      ],
    });
    expect(alts[0]?.inicio).toBe('2026-10-06T13:00:00.000Z');
  });

  it('sobreturno y reprogramado existentes no bloquean', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          sobreturno: true,
        }),
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          estado: 'REPROGRAMADO',
        }),
      ],
    });
    expect(alts[0]?.inicio).toBe('2026-10-06T13:00:00.000Z');
  });

  it('ni mismo profesional ni mismo sillón → no bloquea', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          profesionalId: 'p-otro',
          sillonId: 's-otro',
        }),
      ],
    });
    expect(alts[0]?.inicio).toBe('2026-10-06T13:00:00.000Z');
  });

  it('solape por sillón con distinto profesional sí bloquea', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [
        ocupado('2026-10-06T10:00:00-03:00', '2026-10-06T10:30:00-03:00', {
          profesionalId: 'p-otro',
        }),
      ],
    });
    expect(new Date(alts[0]?.inicio ?? '').getTime()).toBeGreaterThanOrEqual(
      d('2026-10-06T10:30:00-03:00').getTime(),
    );
  });

  it('cantidad personalizada respeta el tope', () => {
    const alts = buscarAlternativas({
      desde: d('2026-10-06T10:00:00-03:00'),
      duracionMin: 30,
      tenantId: T1,
      profesionalId: P1,
      sillonId: S1,
      ocupados: [],
      cantidad: 1,
    });
    expect(alts).toHaveLength(1);
  });
});
