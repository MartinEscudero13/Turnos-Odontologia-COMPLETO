import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };
const odontoP1: Actor = { tenantId: T1, rol: 'ODONTOLOGO', userId: 'odo-1', profesionalId: P1 };

function base(inicio: string) {
  return {
    profesionalId: P1,
    sillonId: S1,
    pacienteId: PAC,
    prestacionId: PREST,
    duracionMin: 30,
    inicio,
  };
}

describe('3.2 POST /api/turnos/:id/sobreturno — motivo obligatorio + auditoría', () => {
  it('sobreturno en creación con motivo se persiste con flag y audita', () => {
    const svc = new ServicioTurnos();
    const r1 = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(r1.ok).toBe(true);
    const r2 = svc.crear(recepcion, {
      ...base('2026-10-06T10:15:00-03:00'),
      sobreturno: true,
      motivoSobreturno: 'urgencia con dolor',
    });
    expect(r2.ok).toBe(true);
    if (!r2.ok) return;
    expect(r2.valor.sobreturno).toBe(true);
    expect(r2.valor.motivoSobreturno).toBe('urgencia con dolor');
    const audit = svc.auditoria(recepcion, r2.valor.id);
    expect(audit.ok && audit.ok ? audit.valor.length : -1).toBe(1);
    const e = audit.ok && audit.ok ? audit.valor[0] : null;
    expect(e?.accion).toBe('SOBRETURNO');
    expect(e?.actor).toBe('recep-1');
    expect(e?.motivo).toBe('urgencia con dolor');
    expect(e?.antes).toBe(null);
    expect(e?.despues).toBe('PENDIENTE');
  });

  it('sobreturno sin motivo (ausente, vacío, blancos) → 422 y no persiste', () => {
    for (const motivo of [undefined, '', '   ']) {
      const svc = new ServicioTurnos();
      svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
      const input =
        motivo === undefined
          ? { ...base('2026-10-06T10:15:00-03:00'), sobreturno: true }
          : { ...base('2026-10-06T10:15:00-03:00'), sobreturno: true, motivoSobreturno: motivo };
      const r = svc.crear(recepcion, input);
      expect(r.ok).toBe(false);
      if (r.ok) continue;
      expect(r.codigo).toBe(422);
      const lista = svc.listar(recepcion);
      expect(lista.ok && lista.ok ? lista.valor.length : -1).toBe(1);
      const audit = svc.auditoria(recepcion);
      expect(audit.ok && audit.ok ? audit.valor.length : -1).toBe(0);
    }
  });

  it('marcar turno existente como sobreturno exige motivo y audita antes/después', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const sinMotivo = svc.sobreturno(recepcion, creado.valor.id, {});
    expect(sinMotivo.ok).toBe(false);
    if (!sinMotivo.ok) expect(sinMotivo.codigo).toBe(422);
    const vacio = svc.sobreturno(recepcion, creado.valor.id, { motivo: '' });
    expect(vacio.ok).toBe(false);
    const ok = svc.sobreturno(odontoP1, creado.valor.id, { motivo: 'dolor agudo' });
    expect(ok.ok).toBe(true);
    if (!ok.ok) return;
    expect(ok.valor.sobreturno).toBe(true);
    const audit = svc.auditoria(recepcion, creado.valor.id);
    const e = audit.ok && audit.ok ? audit.valor[0] : null;
    expect(e?.accion).toBe('SOBRETURNO');
    expect(e?.motivo).toBe('dolor agudo');
    expect(e?.antes).toBe('PENDIENTE');
  });

  it('turno marcado sobreturno ya no bloquea el hueco', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    svc.sobreturno(recepcion, creado.valor.id, { motivo: 'urgencia con dolor' });
    const libre = svc.crear(recepcion, {
      ...base('2026-10-06T10:15:00-03:00'),
      pacienteId: 'otro-paciente',
    });
    expect(libre.ok).toBe(true);
  });
});
