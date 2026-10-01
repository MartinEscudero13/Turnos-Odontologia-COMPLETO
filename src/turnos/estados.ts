import { ESTADOS_NO_BLOQUEANTES, type TurnoEstado } from './types.js';

/**
 * Máquina de estados — task 1.4:
 * PENDIENTE → CONFIRMADO → PRESENTE / AUSENTE,
 * PENDIENTE / CONFIRMADO → CANCELADO / REPROGRAMADO (finales).
 */
const TRANSICIONES: Readonly<Record<TurnoEstado, readonly TurnoEstado[]>> = {
  PENDIENTE: ['CONFIRMADO', 'CANCELADO', 'REPROGRAMADO'],
  CONFIRMADO: ['PRESENTE', 'AUSENTE', 'CANCELADO', 'REPROGRAMADO'],
  PRESENTE: [],
  AUSENTE: [],
  CANCELADO: [],
  REPROGRAMADO: [],
};

export function transicionValida(desde: TurnoEstado, hacia: TurnoEstado): boolean {
  return TRANSICIONES[desde].includes(hacia);
}

/** Estados finales que liberan el hueco (espeja ESTADOS_NO_BLOQUEANTES). */
export function liberaHueco(estado: TurnoEstado): boolean {
  return ESTADOS_NO_BLOQUEANTES.has(estado);
}
