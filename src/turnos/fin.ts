/**
 * Cálculo de fin de turno — D3: fin = inicio + prestacion.duracion_min,
 * calculado servidor-side. El fin del cliente se ignora/valida.
 */
export function calcularFin(inicio: Date, duracionMin: number): Date {
  if (!Number.isInteger(duracionMin) || duracionMin <= 0) {
    throw new Error(`duracion_min inválida: ${duracionMin}`);
  }
  return new Date(inicio.getTime() + duracionMin * 60_000);
}

/**
 * El fin provisto por el cliente solo es válido si coincide EXACTAMENTE
 * con el cálculo servidor-side; cualquier diferencia se rechaza.
 */
export function finClienteValido(inicio: Date, duracionMin: number, finCliente: Date): boolean {
  return calcularFin(inicio, duracionMin).getTime() === finCliente.getTime();
}
