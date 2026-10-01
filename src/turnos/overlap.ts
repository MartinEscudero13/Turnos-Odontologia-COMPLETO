import type { Intervalo } from './types.js';

/**
 * Detecta solape entre dos intervalos half-open [inicio, fin).
 * Adyacencia exacta (fin_A == inicio_B) NO es solape por construcción.
 */
export function intervalosSolapan(a: Intervalo, b: Intervalo): boolean {
  // Rango vacío [t, t): en PG tstzrange es empty y && da false. Se replica acá.
  if (a.inicio.getTime() >= a.fin.getTime()) return false;
  if (b.inicio.getTime() >= b.fin.getTime()) return false;
  return a.inicio.getTime() < b.fin.getTime() && b.inicio.getTime() < a.fin.getTime();
}
