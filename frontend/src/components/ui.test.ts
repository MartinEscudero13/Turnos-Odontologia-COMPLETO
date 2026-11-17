import { describe, expect, it } from 'vitest';
import { soloFecha } from './ui';

describe('formato de fechas', () => {
  it('trata YYYY-MM-DD como día local, sin corrimiento de huso', () => {
    // Si se parseara como UTC, en Argentina mostraría el día anterior.
    expect(soloFecha('2026-11-16')).toContain('16/11');
  });
});
