import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };
const admin: Actor = { tenantId: T1, rol: 'ADMIN', userId: 'admin-1' };
const odontoP1: Actor = { tenantId: T1, rol: 'ODONTOLOGO', userId: 'odo-1', profesionalId: P1 };
const paciente: Actor = { tenantId: T1, rol: 'PACIENTE', userId: PAC };

function crearBase(sobreescribir: Record<string, unknown> = {}) {
  return {
    profesionalId: P1,
    sillonId: S1,
    pacienteId: PAC,
    prestacionId: PREST,
    duracionMin: 30,
    inicio: '2026-10-06T10:00:00-03:00',
    ...sobreescribir,
  };
}

describe('3.1 CRUD /api/turnos — contrato por rol', () => {
  it('recepción crea turno válido: PENDIENTE con fin calculado servidor-side', () => {
    const svc = new ServicioTurnos();
    const r = svc.crear(recepcion, crearBase());
    expect(r.ok).toBe(true);
    if (!r.ok) return;
    expect(r.valor.estado).toBe('PENDIENTE');
    expect(r.valor.inicio.toISOString()).toBe('2026-10-06T13:00:00.000Z');
    expect(r.valor.fin.toISOString()).toBe('2026-10-06T13:30:00.000Z');
    expect(r.valor.tenantId).toBe(T1);
  });

  it('fin de cliente distinto al cálculo se rechaza (422)', () => {
    const svc = new ServicioTurnos();
    const r = svc.crear(recepcion, crearBase({ finCliente: '2026-10-06T11:00:00-03:00' }));
    expect(r.ok).toBe(false);
    if (r.ok) return;
    expect(r.codigo).toBe(422);
  });

  it('fin de cliente idéntico al cálculo se acepta', () => {
    const svc = new ServicioTurnos();
    const r = svc.crear(recepcion, crearBase({ finCliente: '2026-10-06T10:30:00-03:00' }));
    expect(r.ok).toBe(true);
  });

  it('payload inválido (inicio no fecha, duración 0) → 422 por zod', () => {
    const svc = new ServicioTurnos();
    const r1 = svc.crear(recepcion, crearBase({ inicio: 'no-es-fecha' }));
    expect(r1.ok).toBe(false);
    if (!r1.ok) expect(r1.codigo).toBe(422);
    const r2 = svc.crear(recepcion, crearBase({ duracionMin: 0 }));
    expect(r2.ok).toBe(false);
    if (!r2.ok) expect(r2.codigo).toBe(422);
  });

  it('solape en creación → 409 y no persiste', () => {
    const svc = new ServicioTurnos();
    const primero = svc.crear(recepcion, crearBase());
    expect(primero.ok).toBe(true);
    const segundo = svc.crear(recepcion, crearBase({ inicio: '2026-10-06T10:15:00-03:00' }));
    expect(segundo.ok).toBe(false);
    if (segundo.ok) return;
    expect(segundo.codigo).toBe(409);
    const lista = svc.listar(recepcion);
    expect(lista.ok && lista.ok ? lista.valor : []).toHaveLength(1);
  });

  it('leer filtra por tenant: turno de T2 es 404 desde T1', () => {
    const svc = new ServicioTurnos();
    const otroTenant: Actor = { tenantId: 'tenant-otro', rol: 'RECEPCION', userId: 'r2' };
    const creado = svc.crear(otroTenant, crearBase());
    expect(creado.ok).toBe(true);
    if (!creado.ok) return;
    const visto = svc.obtener(recepcion, creado.valor.id);
    expect(visto.ok).toBe(false);
    if (!visto.ok) expect(visto.codigo).toBe(404);
    const lista = svc.listar(recepcion);
    expect(lista.ok && lista.ok ? lista.valor : [{ imposible: true }]).toHaveLength(0);
  });

  it('paciente solo crea sus propios turnos (otro pacienteId → 403)', () => {
    const svc = new ServicioTurnos();
    const ajeno = svc.crear(paciente, crearBase({ pacienteId: 'otro-paciente' }));
    expect(ajeno.ok).toBe(false);
    if (!ajeno.ok) expect(ajeno.codigo).toBe(403);
    const propio = svc.crear(paciente, crearBase());
    expect(propio.ok).toBe(true);
  });

  it('paciente no crea sobreturnos (403) ni actualiza (403)', () => {
    const svc = new ServicioTurnos();
    const sobre = svc.crear(paciente, crearBase({ sobreturno: true, motivoSobreturno: 'urgencia' }));
    expect(sobre.ok).toBe(false);
    if (!sobre.ok) expect(sobre.codigo).toBe(403);
    const base = svc.crear(recepcion, crearBase());
    expect(base.ok).toBe(true);
    if (!base.ok) return;
    const upd = svc.actualizar(paciente, base.valor.id, { pacienteId: PAC });
    expect(upd.ok).toBe(false);
    if (!upd.ok) expect(upd.codigo).toBe(403);
  });

  it('odontólogo escribe solo agenda propia (otro profesional → 403)', () => {
    const svc = new ServicioTurnos();
    const ajeno = svc.crear(odontoP1, crearBase({ profesionalId: 'prof-otro' }));
    expect(ajeno.ok).toBe(false);
    if (!ajeno.ok) expect(ajeno.codigo).toBe(403);
    const propio = svc.crear(odontoP1, crearBase());
    expect(propio.ok).toBe(true);
  });

  it('odontólogo lee agenda total (R) pero paciente solo sus turnos', () => {
    const svc = new ServicioTurnos();
    svc.crear(recepcion, crearBase());
    svc.crear(recepcion, crearBase({ inicio: '2026-10-06T11:00:00-03:00', pacienteId: 'otro-paciente' }));
    const vistaOdo = svc.listar(odontoP1);
    expect(vistaOdo.ok && vistaOdo.ok ? vistaOdo.valor.length : -1).toBe(2);
    const vistaPac = svc.listar(paciente);
    expect(vistaPac.ok && vistaPac.ok ? vistaPac.valor.length : -1).toBe(1);
    expect(vistaPac.ok && vistaPac.ok ? vistaPac.valor[0]?.pacienteId : '').toBe(PAC);
  });

  it('actualizar solo permite pacienteId: otro campo → 422, turno final → 422', () => {
    const svc = new ServicioTurnos();
    const base = svc.crear(recepcion, crearBase());
    expect(base.ok).toBe(true);
    if (!base.ok) return;
    const ok = svc.actualizar(recepcion, base.valor.id, { pacienteId: 'nuevo-paciente' });
    expect(ok.ok).toBe(true);
    if (!ok.ok) return;
    expect(ok.valor.pacienteId).toBe('nuevo-paciente');
    const prohibido = svc.actualizar(recepcion, base.valor.id, {
      pacienteId: 'x',
      profesionalId: 'prof-otro',
    });
    expect(prohibido.ok).toBe(false);
    if (!prohibido.ok) expect(prohibido.codigo).toBe(422);
    const cancel = svc.cancelar(admin, base.valor.id, { ahora: new Date('2026-10-01T10:00:00-03:00') });
    expect(cancel.ok).toBe(true);
    const sobreFinal = svc.actualizar(recepcion, base.valor.id, { pacienteId: 'z' });
    expect(sobreFinal.ok).toBe(false);
    if (!sobreFinal.ok) expect(sobreFinal.codigo).toBe(422);
  });

  it('obtener turno inexistente → 404', () => {
    const svc = new ServicioTurnos();
    const r = svc.obtener(recepcion, 'id-que-no-existe');
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.codigo).toBe(404);
  });
});
