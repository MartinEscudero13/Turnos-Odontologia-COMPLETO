/** Formato de fechas y estados de la reserva pública (sin dependencias). */

const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];

interface Partes {
  anio: number;
  mes: number;
  dia: number;
  hora: number;
  minuto: number;
}

function partes(iso: string): Partes | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(iso);
  if (match === null) {
    return null;
  }
  return {
    anio: Number(match[1]),
    mes: Number(match[2]),
    dia: Number(match[3]),
    hora: Number(match[4]),
    minuto: Number(match[5]),
  };
}

function dosDigitos(valor: number): string {
  return String(valor).padStart(2, '0');
}

/** Hora local del consultorio tomada del ISO (`09:00`). */
export function formatearHora(iso: string): string {
  const p = partes(iso);
  if (p === null) {
    return iso;
  }
  return `${dosDigitos(p.hora)}:${dosDigitos(p.minuto)}`;
}

/** `martes 06.10 · 09:00`, estable sin depender de la zona del navegador. */
export function formatearFechaHora(iso: string): string {
  const p = partes(iso);
  if (p === null) {
    return iso;
  }
  const diaSemana = DIAS[new Date(Date.UTC(p.anio, p.mes - 1, p.dia)).getUTCDay()] ?? '';
  return `${diaSemana} ${dosDigitos(p.dia)}.${dosDigitos(p.mes)} · ${formatearHora(iso)}`;
}

/** `30 min` a partir de `inicio`/`fin` reales del hueco. */
export function formatearDuracion(inicio: string, fin: string): string {
  const minutos = Math.round((Date.parse(fin) - Date.parse(inicio)) / 60000);
  return Number.isFinite(minutos) && minutos > 0 ? `${minutos} min` : '';
}

/** `ahora` como ISO con offset local, que es lo que acepta `desde`. */
export function ahoraConOffset(): string {
  const ahora = new Date();
  const offsetMinutos = -ahora.getTimezoneOffset();
  const signo = offsetMinutos >= 0 ? '+' : '-';
  const absoluto = Math.abs(offsetMinutos);
  const local = new Date(ahora.getTime() + offsetMinutos * 60000)
    .toISOString()
    .replace('Z', '');
  return `${local}${signo}${dosDigitos(Math.floor(absoluto / 60))}:${dosDigitos(absoluto % 60)}`;
}

export type TonoEstado = 'success' | 'pending' | 'danger' | 'neutral';

const ESTADOS: Record<string, { etiqueta: string; tono: TonoEstado }> = {
  PENDIENTE: { etiqueta: 'Pendiente', tono: 'pending' },
  CONFIRMADO: { etiqueta: 'Confirmado', tono: 'success' },
  CANCELADO: { etiqueta: 'Cancelado', tono: 'danger' },
  REPROGRAMADO: { etiqueta: 'Reprogramado', tono: 'neutral' },
  PRESENTE: { etiqueta: 'Presente', tono: 'success' },
  AUSENTE: { etiqueta: 'Ausente', tono: 'danger' },
};

export function estadoVisible(estado: string): { etiqueta: string; tono: TonoEstado } {
  return ESTADOS[estado] ?? { etiqueta: estado, tono: 'neutral' };
}

/** Estados en los que el token todavía permite consultar/cancelar/reprogramar. */
export function esGestionable(estado: string): boolean {
  return estado === 'PENDIENTE' || estado === 'CONFIRMADO';
}
