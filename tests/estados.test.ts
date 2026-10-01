import { describe, expect, it } from 'vitest';
import { liberaHueco, transicionValida } from '../src/turnos/estados.js';

describe('máquina de estados del turno', () => {
  it('PENDIENTE → CONFIRMADO es legal', () => {
    expect(transicionValida('PENDIENTE', 'CONFIRMADO')).toBe(true);
  });

  it('CONFIRMADO → PRESENTE y → AUSENTE son legales', () => {
    expect(transicionValida('CONFIRMADO', 'PRESENTE')).toBe(true);
    expect(transicionValida('CONFIRMADO', 'AUSENTE')).toBe(true);
  });

  it('PENDIENTE/CONFIRMADO → CANCELADO y → REPROGRAMADO son legales', () => {
    expect(transicionValida('PENDIENTE', 'CANCELADO')).toBe(true);
    expect(transicionValida('PENDIENTE', 'REPROGRAMADO')).toBe(true);
    expect(transicionValida('CONFIRMADO', 'CANCELADO')).toBe(true);
    expect(transicionValida('CONFIRMADO', 'REPROGRAMADO')).toBe(true);
  });

  it('transiciones ilegales: PRESENTE → CONFIRMADO, CANCELADO → CONFIRMADO, AUSENTE → PRESENTE', () => {
    expect(transicionValida('PRESENTE', 'CONFIRMADO')).toBe(false);
    expect(transicionValida('CANCELADO', 'CONFIRMADO')).toBe(false);
    expect(transicionValida('AUSENTE', 'PRESENTE')).toBe(false);
  });

  it('CANCELADO y REPROGRAMADO liberan el hueco; los demás no', () => {
    expect(liberaHueco('CANCELADO')).toBe(true);
    expect(liberaHueco('REPROGRAMADO')).toBe(true);
    expect(liberaHueco('PENDIENTE')).toBe(false);
    expect(liberaHueco('CONFIRMADO')).toBe(false);
    expect(liberaHueco('PRESENTE')).toBe(false);
  });

  it('auto-transiciones y salidas desde finales son ilegales', () => {
    expect(transicionValida('PENDIENTE', 'PENDIENTE')).toBe(false);
    expect(transicionValida('CONFIRMADO', 'CONFIRMADO')).toBe(false);
    expect(transicionValida('REPROGRAMADO', 'PENDIENTE')).toBe(false);
    expect(transicionValida('CANCELADO', 'REPROGRAMADO')).toBe(false);
    expect(transicionValida('PRESENTE', 'CANCELADO')).toBe(false);
  });

  it('PENDIENTE no salta directo a PRESENTE/AUSENTE', () => {
    expect(transicionValida('PENDIENTE', 'PRESENTE')).toBe(false);
    expect(transicionValida('PENDIENTE', 'AUSENTE')).toBe(false);
  });
});
