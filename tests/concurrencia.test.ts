import { describe, expect, it } from 'vitest';
import { ServicioTurnos, type Actor } from '../src/turnos/service.js';

const T1 = 'tenant-demo-c05';
const P1 = '11111111-1111-4111-8111-111111111111';
const S1 = '22222222-2222-4222-8222-222222222222';
const PAC = '33333333-3333-4333-8333-333333333333';
const PREST = '44444444-4444-4444-8444-444444444444';

const recepcion: Actor = { tenantId: T1, rol: 'RECEPCION', userId: 'recep-1' };

function intento(svc: ServicioTurnos, pacienteId: string) {
  return svc.crear(recepcion, {
    profesionalId: P1,
    sillonId: S1,
    pacienteId,
    prestacionId: PREST,
    duracionMin: 30,
    inicio: '2026-10-06T10:00:00-03:00',
  });
}

/**
 * 4.2 Doble-reserva simultánea: solo una confirma, la otra recibe 409.
 * La garantía real ante carreras vive en el EXCLUDE de la migración 003
 * (D1); acá se verifica 50 rondas sin flakiness sobre el servicio que
 * replica el mismo predicado.
 */
describe('4.2 concurrencia doble-reserva', () => {
  it('dos inserciones al mismo hueco: 1 ok + 1 con 409 (×50 rondas)', () => {
    for (let ronda = 0; ronda < 50; ronda++) {
      const svc = new ServicioTurnos();
      const [a, b] = [intento(svc, `pac-a-${ronda}`), intento(svc, `pac-b-${ronda}`)];
      const oks = [a, b].filter((r) => r.ok).length;
      const conflicts = [a, b].filter((r) => !r.ok && r.codigo === 409).length;
      expect(oks).toBe(1);
      expect(conflicts).toBe(1);
      const lista = svc.listar(recepcion);
      expect(lista.ok && lista.ok ? lista.valor.length : -1).toBe(1);
    }
  });

  it('tres competidores al mismo hueco: 1 ok + 2 con 409', () => {
    const svc = new ServicioTurnos();
    const resultados = [intento(svc, 'x'), intento(svc, 'y'), intento(svc, 'z')];
    expect(resultados.filter((r) => r.ok).length).toBe(1);
    expect(resultados.filter((r) => !r.ok && r.codigo === 409).length).toBe(2);
  });

  it('huecos distintos no compiten: ambos confirman', () => {
    const svc = new ServicioTurnos();
    const a = intento(svc, 'x');
    const b = svc.crear(recepcion, {
      profesionalId: P1,
      sillonId: S1,
      pacienteId: 'y',
      prestacionId: PREST,
      duracionMin: 30,
      inicio: '2026-10-06T10:30:00-03:00',
    });
    expect(a.ok && b.ok).toBe(true);
  });
});
