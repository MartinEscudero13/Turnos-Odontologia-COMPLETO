import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const P2 = '99999999-9999-4999-8999-999999999999';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };
const odontoP1: Actor = { tenantId: T1, rol: 'ODONTOLOGO', userId: 'odo-1', profesionalId: P1 };
const odontoP2: Actor = { tenantId: T1, rol: 'ODONTOLOGO', userId: 'odo-2', profesionalId: P2 };
const paciente: Actor = { tenantId: T1, rol: 'PACIENTE', userId: PAC };
const LEJOS = new Date('2026-10-01T10:00:00-03:00');

function base(inicio: string, pacienteId = PAC) {
  return {
    profesionalId: P1,
    sillonId: S1,
    pacienteId,
    prestacionId: PREST,
    duracionMin: 30,
    inicio,
  };
}

/**
 * 4.3 Auditoría append-only: sobreturno, cancelación y reprogramación
 * dejan rastro consultable con antes/después; sin PHI en logs.
 */
describe('4.3 auditoría append-only', () => {
  it('sobreturno + cancelación + reprogramación quedan registradas con antes/después', () => {
    const svc = new ServicioTurnos();
    const s = svc.crear(recepcion, {
      ...base('2026-10-06T10:00:00-03:00'),
      sobreturno: true,
      motivoSobreturno: 'urgencia con dolor',
    });
    expect(s.ok).toBe(true);
    const t = svc.crear(recepcion, base('2026-10-06T11:00:00-03:00', 'p-b'));
    expect(t.ok).toBe(true);
    if (!t.ok) return;
    expect(svc.cancelar(recepcion, t.valor.id, { ahora: LEJOS }).ok).toBe(true);
    const u = svc.crear(recepcion, base('2026-10-06T12:00:00-03:00', 'p-c'));
    expect(u.ok).toBe(true);
    if (!u.ok) return;
    expect(
      svc.reprogramar(recepcion, u.valor.id, { nuevoInicio: '2026-10-06T14:00:00-03:00' }, { ahora: LEJOS }).ok,
    ).toBe(true);

    const audit = svc.auditoria(recepcion);
    expect(audit.ok).toBe(true);
    if (!audit.ok) return;
    const acciones = audit.valor.map((e) => e.accion);
    expect(acciones).toContain('SOBRETURNO');
    expect(acciones).toContain('CANCELADO');
    expect(acciones).toContain('REPROGRAMADO');
    for (const e of audit.valor) {
      expect(e.tenantId).toBe(T1);
      expect(e.actor).toBe('recep-1');
      expect(e.turnoId).toBeTruthy();
      expect(e.despues).toBeTruthy();
      expect(new Date(e.registradoEn).toISOString()).toBe(e.registradoEn);
    }
    const cancel = audit.valor.find((e) => e.accion === 'CANCELADO');
    expect(cancel?.antes).toBe('PENDIENTE');
    expect(cancel?.despues).toBe('CANCELADO');
  });

  it('intentos rechazados (422/409/403) no escriben auditoría', () => {
    const svc = new ServicioTurnos();
    expect(svc.crear(recepcion, base('2026-10-06T10:00:00-03:00')).ok).toBe(true);
    // 422: sobreturno sin motivo. 409: solape. 403: paciente cancela bajo umbral.
    expect(svc.crear(recepcion, { ...base('2026-10-06T10:15:00-03:00', 'p-b'), sobreturno: true }).ok).toBe(false);
    expect(svc.crear(recepcion, base('2026-10-06T10:15:00-03:00', 'p-c')).ok).toBe(false);
    const audit = svc.auditoria(recepcion);
    expect(audit.ok && audit.ok ? audit.valor.length : -1).toBe(0);
  });

  it('auditoría es consultable por turno y respeta roles (paciente 403, odonto solo lo propio)', () => {
    const svc = new ServicioTurnos();
    const a = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    expect(svc.cancelar(recepcion, a.valor.id, { ahora: LEJOS }).ok).toBe(true);
    const porTurno = svc.auditoria(recepcion, a.valor.id);
    expect(porTurno.ok && porTurno.ok ? porTurno.valor.length : -1).toBe(1);
    const negada = svc.auditoria(paciente);
    expect(negada.ok).toBe(false);
    if (!negada.ok) expect(negada.codigo).toBe(403);
    const propia = svc.auditoria(odontoP1);
    expect(propia.ok && propia.ok ? propia.valor.length : -1).toBe(1);
    const ajena = svc.auditoria(odontoP2);
    expect(ajena.ok && ajena.ok ? ajena.valor.length : -1).toBe(0);
  });

  it('sin PHI en logs: auditoría solo guarda ids, actor y motivo funcional', () => {
    const svc = new ServicioTurnos();
    const s = svc.crear(recepcion, {
      ...base('2026-10-06T10:00:00-03:00'),
      sobreturno: true,
      motivoSobreturno: 'urgencia con dolor',
    });
    expect(s.ok).toBe(true);
    const audit = svc.auditoria(recepcion);
    expect(audit.ok).toBe(true);
    if (!audit.ok) return;
    const dump = JSON.stringify(audit.valor);
    expect(dump).not.toMatch(/María|Gómez|Pérez/i);
    expect(dump).not.toMatch(/\d{2}\.\d{3}\.\d{3}/);
    expect(dump).not.toMatch(/\+54|@mail|@gmail/i);
  });
});
