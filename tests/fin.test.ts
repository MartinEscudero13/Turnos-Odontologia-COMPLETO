import { describe, expect, it } from 'vitest';
import { calcularFin, finClienteValido } from '../src/turnos/fin.js';

const d = (s: string): Date => new Date(s);

describe('calcularFin — fin = inicio + prestacion.duracion_min', () => {
  it('prestación 30 min: 10:00 → 10:30', () => {
    expect(calcularFin(d('2026-10-06T10:00:00-03:00'), 30)).toEqual(
      d('2026-10-06T10:30:00-03:00'),
    );
  });

  it('prestación 45 min: 09:00 → 09:45', () => {
    expect(calcularFin(d('2026-10-06T09:00:00-03:00'), 45)).toEqual(
      d('2026-10-06T09:45:00-03:00'),
    );
  });

  it('prestación 60 min: 10:00 → 11:00', () => {
    expect(calcularFin(d('2026-10-06T10:00:00-03:00'), 60)).toEqual(
      d('2026-10-06T11:00:00-03:00'),
    );
  });

  it('fin de cliente idéntico al cálculo se acepta', () => {
    expect(
      finClienteValido(
        d('2026-10-06T10:00:00-03:00'),
        30,
        d('2026-10-06T10:30:00-03:00'),
      ),
    ).toBe(true);
  });

  it('fin de cliente distinto al cálculo se rechaza', () => {
    expect(
      finClienteValido(
        d('2026-10-06T10:00:00-03:00'),
        30,
        d('2026-10-06T11:00:00-03:00'),
      ),
    ).toBe(false);
  });

  it('diferencia de 1 minuto también se rechaza', () => {
    expect(
      finClienteValido(
        d('2026-10-06T10:00:00-03:00'),
        30,
        d('2026-10-06T10:31:00-03:00'),
      ),
    ).toBe(false);
  });

  it('duración inválida (0, negativa, no entera) lanza error', () => {
    const inicio = d('2026-10-06T10:00:00-03:00');
    expect(() => calcularFin(inicio, 0)).toThrow();
    expect(() => calcularFin(inicio, -30)).toThrow();
    expect(() => calcularFin(inicio, 22.5)).toThrow();
  });

  it('cruce de medianoche: 23:45 + 30 min → 00:15 del día siguiente', () => {
    expect(calcularFin(d('2026-10-06T23:45:00-03:00'), 30)).toEqual(
      d('2026-10-07T00:15:00-03:00'),
    );
  });
});
