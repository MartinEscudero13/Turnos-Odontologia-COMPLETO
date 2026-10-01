import { describe, expect, it } from 'vitest';
import { intervalosSolapan } from '../src/turnos/overlap.js';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };

function base(inicio: string, extra: Record<string, unknown> = {}) {
  return {
    profesionalId: P1,
    sillonId: S1,
    pacienteId: PAC,
    prestacionId: PREST,
    duracionMin: 30,
    inicio,
    ...extra,
  };
}

describe('3.4 todo rechazo por solape devuelve 409 + 3 alternativas con formato 1.3', () => {
  it('crear solapado trae exactamente { inicio, fin } ISO por alternativa', () => {
    const svc = new ServicioTurnos();
    svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    const r = svc.crear(recepcion, base('2026-10-06T10:15:00-03:00', { pacienteId: 'otro' }));
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.codigo).toBe(409);
    expect(r.alternativas).toHaveLength(3);
    for (const a of r.alternativas ?? []) {
      expect(Object.keys(a).sort()).toEqual(['fin', 'inicio']);
      expect(new Date(a.inicio).toISOString()).toBe(a.inicio);
      expect(new Date(a.fin).toISOString()).toBe(a.fin);
      expect(new Date(a.fin).getTime() - new Date(a.inicio).getTime()).toBe(30 * 60_000);
    }
  });

  it('mismo formato en reprogramar a destino ocupado', () => {
    const svc = new ServicioTurnos();
    const a = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    svc.crear(recepcion, base('2026-10-06T14:00:00-03:00', { pacienteId: 'otro' }));
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    const r = svc.reprogramar(
      recepcion,
      a.valor.id,
      { nuevoInicio: '2026-10-06T14:15:00-03:00' },
      { ahora: new Date('2026-10-01T10:00:00-03:00') },
    );
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.codigo).toBe(409);
    expect(r.alternativas).toHaveLength(3);
    expect(Object.keys(r.alternativas?.[0] ?? {}).sort()).toEqual(['fin', 'inicio']);
  });

  it('alternativas del 409 no solapan con turnos activos y vienen ordenadas', () => {
    const svc = new ServicioTurnos();
    svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    const r = svc.crear(recepcion, base('2026-10-06T10:15:00-03:00', { pacienteId: 'otro' }));
    expect(r.ok).toBe(false);
    if (r.ok || !r.alternativas) return;
    const existentes = svc.listar(recepcion);
    expect(existentes.ok).toBe(true);
    if (!existentes.ok) return;
    const alts = r.alternativas.map((x) => ({ inicio: new Date(x.inicio), fin: new Date(x.fin) }));
    for (const alt of alts) {
      for (const t of existentes.valor) {
        expect(intervalosSolapan(alt, t)).toBe(false);
      }
    }
    const tiempos = alts.map((x) => x.inicio.getTime());
    expect([...tiempos].sort((x, y) => x - y)).toEqual(tiempos);
  });

  it('aislamiento: solape en otro tenant no genera 409', () => {
    const svc = new ServicioTurnos();
    svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    const otro: Actor = { tenantId: 'tenant-otro', rol: 'RECEPCION', userId: 'r2' };
    const r = svc.crear(otro, base('2026-10-06T10:15:00-03:00'));
    expect(r.ok).toBe(true);
  });
});
