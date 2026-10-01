import { calcularFin } from './fin.js';
import { intervalosSolapan } from './overlap.js';
import {
  ESTADOS_NO_BLOQUEANTES,
  type Alternativa,
  type Intervalo,
  type TurnoEstado,
} from './types.js';

export interface HuecoOcupado {
  readonly tenantId: string;
  readonly profesionalId: string;
  readonly sillonId: string;
  readonly inicio: Date;
  readonly fin: Date;
  readonly estado: TurnoEstado;
  readonly sobreturno: boolean;
}

export interface BuscarAlternativasArgs {
  readonly desde: Date;
  readonly duracionMin: number;
  readonly tenantId: string;
  readonly profesionalId: string;
  readonly sillonId: string;
  readonly ocupados: readonly HuecoOcupado[];
  readonly bloqueos?: readonly Intervalo[];
  readonly cantidad?: number;
}

const PASO_MINUTOS = 15;
const HORIZONTE_DIAS = 30;

/**
 * Un turno existente bloquea un hueco solo si: mismo tenant, mismo
 * profesional O mismo sillón, estado activo y no es sobreturno.
 * Espeja el predicado parcial del EXCLUDE de la migración 003.
 */
export function esBloqueante(
  o: HuecoOcupado,
  tenantId: string,
  profesionalId: string,
  sillonId: string,
): boolean {
  if (o.tenantId !== tenantId) return false;
  if (o.profesionalId !== profesionalId && o.sillonId !== sillonId) return false;
  if (ESTADOS_NO_BLOQUEANTES.has(o.estado)) return false;
  if (o.sobreturno) return false;
  return true;
}

/**
 * Selector de N alternativas (default 3): grilla de 15 min desde `desde`,
 * primer candidato = `desde` exacto, orden cronológico, ≤ cantidad.
 * Formato ISO UTC (la persistencia es timestamptz, D3).
 */
export function buscarAlternativas(args: BuscarAlternativasArgs): Alternativa[] {
  const cantidad = args.cantidad ?? 3;
  const bloqueos = args.bloqueos ?? [];
  const relevantes = args.ocupados.filter((o) =>
    esBloqueante(o, args.tenantId, args.profesionalId, args.sillonId),
  );
  const resultado: Alternativa[] = [];
  const limite = args.desde.getTime() + HORIZONTE_DIAS * 86_400_000;
  let cursor = new Date(args.desde.getTime());
  while (resultado.length < cantidad && cursor.getTime() < limite) {
    const fin = calcularFin(cursor, args.duracionMin);
    const candidato: Intervalo = { inicio: cursor, fin };
    const choca =
      relevantes.some((o) => intervalosSolapan(candidato, o)) ||
      bloqueos.some((b) => intervalosSolapan(candidato, b));
    if (!choca) {
      resultado.push({ inicio: cursor.toISOString(), fin: fin.toISOString() });
    }
    cursor = new Date(cursor.getTime() + PASO_MINUTOS * 60_000);
  }
  return resultado;
}
