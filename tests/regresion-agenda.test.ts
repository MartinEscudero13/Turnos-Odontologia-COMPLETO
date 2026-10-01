import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const P2 = '99999999-9999-4999-8999-999999999999';
const S1 = '22222222-2222-4222-8222-222222222222';
const S2 = '88888888-8888-4888-8888-888888888888';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };
const LEJOS = new Date('2026-10-01T10:00:00-03:00');

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

/**
 * 4.1 Regresión agenda — condición de merge (regla dura AGENTS.md).
 * Cubre los 11 escenarios del spec a nivel servicio.
 */
describe('4.1 regresión agenda', () => {
  it('solape por profesional falla y solape por sillón falla', () => {
    const svc = new ServicioTurnos();
    expect(svc.crear(recepcion, base('2026-10-06T10:00:00-03:00')).ok).toBe(true);
    // Mismo profesional, distinto sillón, 10:15–10:45.
    const porProf = svc.crear(
      recepcion,
      base('2026-10-06T10:15:00-03:00', { sillonId: S2, pacienteId: 'p-b' }),
    );
    expect(porProf.ok).toBe(false);
    if (!porProf.ok) expect(porProf.codigo).toBe(409);
    // Mismo sillón, distinto profesional, 11:00–11:30 vs 11:15–11:45.
    const svc2 = new ServicioTurnos();
    expect(svc2.crear(recepcion, base('2026-10-06T11:00:00-03:00')).ok).toBe(true);
    const porSillon = svc2.crear(
      recepcion,
      base('2026-10-06T11:15:00-03:00', { profesionalId: P2, pacienteId: 'p-c' }),
    );
    expect(porSillon.ok).toBe(false);
    if (!porSillon.ok) expect(porSillon.codigo).toBe(409);
  });

  it('adyacencia exacta (fin_A == inicio_B) pasa', () => {
    const svc = new ServicioTurnos();
    expect(svc.crear(recepcion, base('2026-10-06T10:00:00-03:00')).ok).toBe(true);
    const ady = svc.crear(recepcion, base('2026-10-06T10:30:00-03:00', { pacienteId: 'p-b' }));
    expect(ady.ok).toBe(true);
    if (!ady.ok) return;
    expect(ady.valor.estado).toBe('PENDIENTE');
  });

  it('cancelado y reprogramado no bloquean (hueco reutilizable)', () => {
    const svc = new ServicioTurnos();
    const a = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    expect(svc.cancelar(recepcion, a.valor.id, { ahora: LEJOS }).ok).toBe(true);
    expect(svc.crear(recepcion, base('2026-10-06T10:00:00-03:00', { pacienteId: 'p-b' })).ok).toBe(
      true,
    );
    const svc2 = new ServicioTurnos();
    const b = svc2.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(b.ok).toBe(true);
    if (!b.ok) return;
    const rep = svc2.reprogramar(
      recepcion,
      b.valor.id,
      { nuevoInicio: '2026-10-06T14:00:00-03:00' },
      { ahora: LEJOS },
    );
    expect(rep.ok).toBe(true);
    expect(
      svc2.crear(recepcion, base('2026-10-06T10:00:00-03:00', { pacienteId: 'p-c' })).ok,
    ).toBe(true);
    // …y el reprogramado a las 14:00 sigue bloqueando su nuevo horario.
    expect(
      svc2.crear(recepcion, base('2026-10-06T14:00:00-03:00', { pacienteId: 'p-d' })).ok,
    ).toBe(false);
  });

  it('sobreturno sin motivo falla y con motivo persiste auditado', () => {
    const svc = new ServicioTurnos();
    expect(svc.crear(recepcion, base('2026-10-06T10:00:00-03:00')).ok).toBe(true);
    const sinMotivo = svc.crear(
      recepcion,
      base('2026-10-06T10:15:00-03:00', { pacienteId: 'p-b', sobreturno: true }),
    );
    expect(sinMotivo.ok).toBe(false);
    if (!sinMotivo.ok) expect(sinMotivo.codigo).toBe(422);
    const conMotivo = svc.crear(
      recepcion,
      base('2026-10-06T10:15:00-03:00', {
        pacienteId: 'p-b',
        sobreturno: true,
        motivoSobreturno: 'urgencia con dolor',
      }),
    );
    expect(conMotivo.ok).toBe(true);
    if (!conMotivo.ok) return;
    expect(conMotivo.valor.sobreturno).toBe(true);
    const audit = svc.auditoria(recepcion, conMotivo.valor.id);
    expect(audit.ok && audit.ok ? audit.valor.length : -1).toBe(1);
  });

  it('turno válido se crea con fin calculado y tenant ajeno no interfiere', () => {
    const svc = new ServicioTurnos();
    const r = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.valor.fin.toISOString()).toBe('2026-10-06T13:30:00.000Z');
    const otro: Actor = { tenantId: 'tenant-otro', rol: 'RECEPCION', userId: 'r2' };
    expect(svc.crear(otro, base('2026-10-06T10:00:00-03:00')).ok).toBe(true);
  });
});
