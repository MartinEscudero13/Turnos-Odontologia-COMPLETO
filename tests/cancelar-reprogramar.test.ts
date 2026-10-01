import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';
import { intervalosSolapan } from '../src/turnos/overlap.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };
const admin: Actor = { tenantId: T1, rol: 'ADMIN', userId: 'admin-1' };
const paciente: Actor = { tenantId: T1, rol: 'PACIENTE', userId: PAC };
const odontoP1: Actor = { tenantId: T1, rol: 'ODONTOLOGO', userId: 'odo-1', profesionalId: P1 };

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

const LEJOS = new Date('2026-10-01T10:00:00-03:00');

describe('3.3 cancelar / reprogramar — anticipación, 409 y atomicidad', () => {
  it('cancelación con anticipación (48 h) → CANCELADO + audita + libera hueco', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const c = svc.cancelar(recepcion, creado.valor.id, { ahora: LEJOS });
    expect(c.ok).toBe(true);
    if (!c.ok) return;
    expect(c.valor.estado).toBe('CANCELADO');
    const audit = svc.auditoria(recepcion, creado.valor.id);
    const e = audit.ok && audit.ok ? audit.valor[0] : null;
    expect(e?.accion).toBe('CANCELADO');
    expect(e?.antes).toBe('PENDIENTE');
    expect(e?.despues).toBe('CANCELADO');
    const reuso = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00', 'otro-paciente'));
    expect(reuso.ok).toBe(true);
  });

  it('debajo del umbral (24 h) el paciente recibe 403 y solo recepción cancela', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(paciente, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const tarde = new Date('2026-10-05T12:00:00-03:00'); // 22 h antes
    const intento = svc.cancelar(paciente, creado.valor.id, { ahora: tarde });
    expect(intento.ok).toBe(false);
    if (!intento.ok) expect(intento.codigo).toBe(403);
    const aunActivo = svc.obtener(recepcion, creado.valor.id);
    expect(aunActivo.ok && aunActivo.ok ? aunActivo.valor.estado : '').toBe('PENDIENTE');
    const porRecep = svc.cancelar(recepcion, creado.valor.id, { ahora: tarde });
    expect(porRecep.ok).toBe(true);
    const audit = svc.auditoria(recepcion, creado.valor.id);
    expect(audit.ok && audit.ok ? audit.valor.length : -1).toBe(1);
  });

  it('anticipación configurable: con 1 h de mínimo el paciente sí cancela a 22 h', () => {
    const svc = new ServicioTurnos({ anticipacionMinMs: 3_600_000 });
    const creado = svc.crear(paciente, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const tarde = new Date('2026-10-05T12:00:00-03:00');
    const c = svc.cancelar(paciente, creado.valor.id, { ahora: tarde });
    expect(c.ok).toBe(true);
  });

  it('cancelar estado final (PRESENTE) → 422', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const c = svc.cancelar(admin, creado.valor.id, { ahora: LEJOS });
    expect(c.ok).toBe(true);
    const otra = svc.cancelar(admin, creado.valor.id, { ahora: LEJOS });
    expect(otra.ok).toBe(false);
    if (!otra.ok) expect(otra.codigo).toBe(422);
  });

  it('reprogramar mueve a REPROGRAMADO + crea nuevo, y libera el hueco original', () => {
    const svc = new ServicioTurnos();
    const creado = svc.crear(odontoP1, base('2026-10-06T10:00:00-03:00'));
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const r = svc.reprogramar(
      odontoP1,
      creado.valor.id,
      { nuevoInicio: '2026-10-06T14:00:00-03:00' },
      { ahora: LEJOS },
    );
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.valor.original.estado).toBe('REPROGRAMADO');
    expect(r.valor.nuevo.inicio.toISOString()).toBe('2026-10-06T17:00:00.000Z');
    expect(r.valor.nuevo.estado).toBe('PENDIENTE');
    const reuso = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00', 'otro-paciente'));
    expect(reuso.ok).toBe(true);
    const choqueNuevo = svc.crear(recepcion, base('2026-10-06T14:00:00-03:00', 'tercer-paciente'));
    expect(choqueNuevo.ok).toBe(false);
  });

  it('reprogramar a destino ocupado → 409 + original intacto (atomicidad)', () => {
    const svc = new ServicioTurnos();
    const a = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    const b = svc.crear(recepcion, base('2026-10-06T14:00:00-03:00', 'otro-paciente'));
    expect(a.ok && b.ok).toBe(true);
    if (!a.ok) return;
    const r = svc.reprogramar(
      recepcion,
      a.valor.id,
      { nuevoInicio: '2026-10-06T14:15:00-03:00' },
      { ahora: LEJOS },
    );
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.codigo).toBe(409);
    expect(r.alternativas).toHaveLength(3);
    const intacto = svc.obtener(recepcion, a.valor.id);
    expect(intacto.ok && intacto.ok ? intacto.valor.inicio.toISOString() : '').toBe(
      '2026-10-06T13:00:00.000Z',
    );
    expect(intacto.ok && intacto.ok ? intacto.valor.estado : '').toBe('PENDIENTE');
    const lista = svc.listar(recepcion);
    expect(lista.ok && lista.ok ? lista.valor.length : -1).toBe(2);
  });

  it('reprogramar con body inválido → 422 y original intacto', () => {
    const svc = new ServicioTurnos();
    const a = svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    const r = svc.reprogramar(recepcion, a.valor.id, { nuevoInicio: 'no-fecha' }, { ahora: LEJOS });
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.codigo).toBe(422);
    const intacto = svc.obtener(recepcion, a.valor.id);
    expect(intacto.ok && intacto.ok ? intacto.valor.estado : '').toBe('PENDIENTE');
  });

  it('alternativas del 409 son huecos reales: no solapan y están ordenadas', () => {
    const svc = new ServicioTurnos();
    svc.crear(recepcion, base('2026-10-06T10:00:00-03:00'));
    svc.crear(recepcion, base('2026-10-06T14:00:00-03:00', 'otro-paciente'));
    const a = svc.listar(recepcion);
    expect(a.ok).toBe(true);
    if (!a.ok) return;
    const primero = a.valor[0];
    if (!primero) return;
    const r = svc.reprogramar(
      recepcion,
      primero.id,
      { nuevoInicio: '2026-10-06T14:15:00-03:00' },
      { ahora: LEJOS },
    );
    expect(r.ok).toBe(false);
    if (r.ok || !r.alternativas) return;
    const alts = r.alternativas.map((x) => ({ inicio: new Date(x.inicio), fin: new Date(x.fin) }));
    for (const alt of alts) {
      for (const t of a.valor) {
        expect(intervalosSolapan(alt, { inicio: t.inicio, fin: t.fin })).toBe(false);
      }
    }
    expect(alts[0]!.inicio.getTime()).toBeLessThan(alts[1]!.inicio.getTime());
    expect(alts[1]!.inicio.getTime()).toBeLessThan(alts[2]!.inicio.getTime());
  });
});
