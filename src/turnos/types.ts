/** Tipos de dominio — C-05 turnos-anti-solape. Datos ficticios en tests. */

export type TurnoEstado =
  | 'PENDIENTE'
  | 'CONFIRMADO'
  | 'PRESENTE'
  | 'AUSENTE'
  | 'CANCELADO'
  | 'REPROGRAMADO';

export type TurnoOrigen = 'RECEPCION' | 'RESERVA_ONLINE' | 'LISTA_ESPERA';

export interface Turno {
  readonly id: string;
  readonly tenantId: string;
  readonly profesionalId: string;
  readonly sillonId: string;
  readonly pacienteId: string;
  readonly prestacionId: string;
  readonly inicio: Date;
  readonly fin: Date;
  readonly estado: TurnoEstado;
  readonly sobreturno: boolean;
  readonly motivoSobreturno?: string;
  readonly origen: TurnoOrigen;
  readonly tokenPublico?: string;
}

/** Intervalo half-open [inicio, fin). */
export interface Intervalo {
  readonly inicio: Date;
  readonly fin: Date;
}

export interface Alternativa {
  readonly inicio: string;
  readonly fin: string;
}

export interface AuditoriaEntrada {
  readonly turnoId: string;
  readonly tenantId: string;
  readonly accion: 'CREADO' | 'SOBRETURNO' | 'CANCELADO' | 'REPROGRAMADO';
  readonly actor: string;
  readonly motivo?: string;
  readonly antes: TurnoEstado | null;
  readonly despues: TurnoEstado;
  readonly registradoEn: string;
}

/** Estados que liberan el hueco (no bloquean anti-solape). */
export const ESTADOS_NO_BLOQUEANTES: ReadonlySet<TurnoEstado> = new Set([
  'CANCELADO',
  'REPROGRAMADO',
]);
