import { describe, expect, it } from 'vitest';
import { intervalosSolapan } from '../src/turnos/overlap.js';

const d = (s: string): Date => new Date(s);

describe('intervalosSolapan — half-open [inicio, fin)', () => {
  it('solape parcial falla (detecta solape)', () => {
    expect(
      intervalosSolapan(
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') },
        { inicio: d('2026-10-06T10:15:00-03:00'), fin: d('2026-10-06T10:45:00-03:00') },
      ),
    ).toBe(true);
  });

  it('solape total / contenido falla (detecta solape)', () => {
    expect(
      intervalosSolapan(
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T11:00:00-03:00') },
        { inicio: d('2026-10-06T10:15:00-03:00'), fin: d('2026-10-06T10:45:00-03:00') },
      ),
    ).toBe(true);
  });

  it('adyacencia exacta fin_A == inicio_B pasa (no hay solape)', () => {
    expect(
      intervalosSolapan(
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') },
        { inicio: d('2026-10-06T10:30:00-03:00'), fin: d('2026-10-06T11:00:00-03:00') },
      ),
    ).toBe(false);
  });

  it('intervalos disjuntos no solapan', () => {
    expect(
      intervalosSolapan(
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') },
        { inicio: d('2026-10-06T11:00:00-03:00'), fin: d('2026-10-06T11:30:00-03:00') },
      ),
    ).toBe(false);
  });

  it('es simétrico: solapa en ambos órdenes de argumentos', () => {
    const a = { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') };
    const b = { inicio: d('2026-10-06T10:15:00-03:00'), fin: d('2026-10-06T10:45:00-03:00') };
    expect(intervalosSolapan(a, b)).toBe(true);
    expect(intervalosSolapan(b, a)).toBe(true);
  });

  it('intervalos idénticos solapan', () => {
    const a = { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') };
    const b = { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') };
    expect(intervalosSolapan(a, b)).toBe(true);
  });

  it('adyacencia por el otro lado (inicio_A == fin_B) tampoco solapa', () => {
    expect(
      intervalosSolapan(
        { inicio: d('2026-10-06T10:30:00-03:00'), fin: d('2026-10-06T11:00:00-03:00') },
        { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') },
      ),
    ).toBe(false);
  });

  it('intervalo vacío [t, t) no solapa con nada', () => {
    const vacio = { inicio: d('2026-10-06T10:15:00-03:00'), fin: d('2026-10-06T10:15:00-03:00') };
    const normal = { inicio: d('2026-10-06T10:00:00-03:00'), fin: d('2026-10-06T10:30:00-03:00') };
    expect(intervalosSolapan(vacio, normal)).toBe(false);
    expect(intervalosSolapan(normal, vacio)).toBe(false);
  });
});
