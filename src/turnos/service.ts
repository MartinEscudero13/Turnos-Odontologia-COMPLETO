import { buscarAlternativas } from './alternativas.js';
import { calcularFin, finClienteValido } from './fin.js';
import { liberaHueco, transicionValida } from './estados.js';
import {
  actualizarTurnoSchema,
  crearTurnoSchema,
  motivoSchema,
  reprogramarSchema,
} from './schemas.js';
import type {
  Alternativa,
  AuditoriaEntrada,
  Turno,
  TurnoEstado,
  TurnoOrigen,
} from './types.js';

/**
 * Servicio de turnos — implementa tasks 3.1–3.4 sobre el dominio standalone.
 * Espeja en memoria el contrato de la migración 003: fin calculado
 * servidor-side, anti-solape por (tenant, profesional) y (tenant, sillón)
 * con half-open [inicio, fin), finales y sobreturnos que no bloquean,
 * RLS (todo filtra por tenant) y auditoría append-only.
 * La garantía real ante concurrencia vive en el EXCLUDE de la DB (D1);
 * acá se replica el predicado para paridad de comportamiento.
 */

export type Rol = 'PACIENTE' | 'ODONTOLOGO' | 'RECEPCION' | 'ADMIN';

export interface Actor {
  readonly tenantId: string;
  readonly rol: Rol;
  readonly userId: string;
  readonly profesionalId?: string;
}

export interface ErrorApi {
  readonly ok: false;
  readonly codigo: 403 | 404 | 409 | 422;
  readonly mensaje: string;
  readonly alternativas?: Alternativa[];
}

export interface OkApi<T> {
  readonly ok: true;
  readonly valor: T;
}

export type Resultado<T> = OkApi<T> | ErrorApi;

const ANTICIPACION_DEFAULT_MS = 24 * 3_600_000;

function err(
  codigo: ErrorApi['codigo'],
  mensaje: string,
  alternativas?: Alternativa[],
): ErrorApi {
  return alternativas === undefined
    ? { ok: false, codigo, mensaje }
    : { ok: false, codigo, mensaje, alternativas };
}

export class ServicioTurnos {
  private readonly turnos = new Map<string, Turno>();
  private readonly auditoriaLog: AuditoriaEntrada[] = [];
  private siguienteId = 1;
  private readonly anticipacionMinMs: number;

  constructor(opts?: { readonly anticipacionMinMs?: number }) {
    this.anticipacionMinMs = opts?.anticipacionMinMs ?? ANTICIPACION_DEFAULT_MS;
  }

  // ---- 3.1 CRUD ----

  crear(actor: Actor, input: unknown): Resultado<Turno> {
    const parsed = crearTurnoSchema.safeParse(input);
    if (!parsed.success) return err(422, 'payload inválido');
    const data = parsed.data;
    const permiso = this.puedeCrear(actor, data);
    if (permiso !== null) return permiso;
    if (data.sobreturno === true) {
      const m = motivoSchema.safeParse({ motivo: data.motivoSobreturno ?? '' });
      if (!m.success) return err(422, 'sobreturno exige motivo no vacío');
    }
    const inicio = new Date(data.inicio);
    let fin: Date;
    try {
      fin = calcularFin(inicio, data.duracionMin);
    } catch {
      return err(422, 'duracion_min inválida');
    }
    if (data.finCliente !== undefined) {
      if (!finClienteValido(inicio, data.duracionMin, new Date(data.finCliente))) {
        return err(422, 'fin provisto difiere del cálculo servidor-side');
      }
    }
    const esSobre = data.sobreturno === true;
    if (!esSobre) {
      const choque = this.haySolape(actor.tenantId, data.profesionalId, data.sillonId, inicio, fin, null);
      if (choque) {
        return err(409, 'hueco ocupado', this.alternativas(actor.tenantId, data, inicio));
      }
    }
    const turno: Turno = {
      id: `turno-${this.siguienteId++}`,
      tenantId: actor.tenantId,
      profesionalId: data.profesionalId,
      sillonId: data.sillonId,
      pacienteId: data.pacienteId,
      prestacionId: data.prestacionId,
      inicio,
      fin,
      estado: 'PENDIENTE',
      sobreturno: esSobre,
      ...(data.motivoSobreturno !== undefined ? { motivoSobreturno: data.motivoSobreturno } : {}),
      origen: data.origen ?? 'RECEPCION',
    };
    this.turnos.set(turno.id, turno);
    if (esSobre) {
      this.auditar(turno, 'SOBRETURNO', actor.userId, data.motivoSobreturno ?? '', null, 'PENDIENTE');
    }
    return { ok: true, valor: turno };
  }

  listar(actor: Actor): Resultado<Turno[]> {
    const todos = [...this.turnos.values()].filter((t) => t.tenantId === actor.tenantId);
    if (actor.rol === 'PACIENTE') {
      return { ok: true, valor: todos.filter((t) => t.pacienteId === actor.userId) };
    }
    return { ok: true, valor: todos };
  }

  obtener(actor: Actor, id: string): Resultado<Turno> {
    const t = this.turnos.get(id);
    if (t === undefined || t.tenantId !== actor.tenantId) return err(404, 'turno no encontrado');
    if (actor.rol === 'PACIENTE' && t.pacienteId !== actor.userId) return err(404, 'turno no encontrado');
    return { ok: true, valor: t };
  }

  actualizar(actor: Actor, id: string, patch: unknown): Resultado<Turno> {
    const parsed = actualizarTurnoSchema.safeParse(patch);
    if (!parsed.success) return err(422, 'solo pacienteId es actualizable');
    const actual = this.obtener(actor, id);
    if (!actual.ok) return actual;
    if (actor.rol === 'PACIENTE') return err(403, 'paciente no actualiza turnos');
    if (!this.puedeEscribir(actor, actual.valor)) return err(403, 'fuera de tu agenda');
    if (liberaHueco(actual.valor.estado)) return err(422, 'turno en estado final no editable');
    const actualizado: Turno = { ...actual.valor, pacienteId: parsed.data.pacienteId };
    this.turnos.set(id, actualizado);
    return { ok: true, valor: actualizado };
  }

  // ---- 3.2 sobreturno sobre turno existente ----

  sobreturno(actor: Actor, id: string, body: unknown): Resultado<Turno> {
    const parsed = motivoSchema.safeParse(body);
    if (!parsed.success) return err(422, 'sobreturno exige motivo no vacío');
    const actual = this.obtener(actor, id);
    if (!actual.ok) return actual;
    if (actor.rol === 'PACIENTE') return err(403, 'paciente no crea sobreturnos');
    if (!this.puedeEscribir(actor, actual.valor)) return err(403, 'fuera de tu agenda');
    if (liberaHueco(actual.valor.estado)) return err(422, 'turno en estado final');
    const marcado: Turno = {
      ...actual.valor,
      sobreturno: true,
      motivoSobreturno: parsed.data.motivo,
    };
    this.turnos.set(id, marcado);
    this.auditar(marcado, 'SOBRETURNO', actor.userId, parsed.data.motivo, actual.valor.estado, actual.valor.estado);
    return { ok: true, valor: marcado };
  }

  // ---- 3.3 cancelar / reprogramar ----

  cancelar(actor: Actor, id: string, opts?: { readonly ahora?: Date }): Resultado<Turno> {
    const actual = this.obtener(actor, id);
    if (!actual.ok) return actual;
    if (!this.puedeEscribir(actor, actual.valor)) return err(403, 'sin permiso sobre este turno');
    if (!transicionValida(actual.valor.estado, 'CANCELADO')) {
      return err(422, `transición ${actual.valor.estado} → CANCELADO ilegal`);
    }
    const ahora = opts?.ahora ?? new Date();
    if (this.bajoAnticipacion(actual.valor, ahora) && !this.esRecepcion(actor)) {
      return err(403, 'bajo anticipación mínima: solo recepción');
    }
    const cancelado: Turno = { ...actual.valor, estado: 'CANCELADO' };
    this.turnos.set(id, cancelado);
    this.auditar(cancelado, 'CANCELADO', actor.userId, undefined, actual.valor.estado, 'CANCELADO');
    return { ok: true, valor: cancelado };
  }

  reprogramar(
    actor: Actor,
    id: string,
    body: unknown,
    opts?: { readonly ahora?: Date },
  ): Resultado<{ readonly original: Turno; readonly nuevo: Turno }> {
    const parsed = reprogramarSchema.safeParse(body);
    if (!parsed.success) return err(422, 'nuevoInicio inválido');
    const actual = this.obtener(actor, id);
    if (!actual.ok) return actual;
    if (!this.puedeEscribir(actor, actual.valor)) return err(403, 'sin permiso sobre este turno');
    if (!transicionValida(actual.valor.estado, 'REPROGRAMADO')) {
      return err(422, `transición ${actual.valor.estado} → REPROGRAMADO ilegal`);
    }
    const ahora = opts?.ahora ?? new Date();
    if (this.bajoAnticipacion(actual.valor, ahora) && !this.esRecepcion(actor)) {
      return err(403, 'bajo anticipación mínima: solo recepción');
    }
    const duracion = parsed.data.duracionMin ?? this.duracionDe(actual.valor);
    const nuevoInicio = new Date(parsed.data.nuevoInicio);
    let nuevoFin: Date;
    try {
      nuevoFin = calcularFin(nuevoInicio, duracion);
    } catch {
      return err(422, 'duracion_min inválida');
    }
    // Revalidación servidor-side ANTES de mutar (atomicidad).
    const choque = this.haySolape(
      actual.valor.tenantId,
      actual.valor.profesionalId,
      actual.valor.sillonId,
      nuevoInicio,
      nuevoFin,
      actual.valor.id,
    );
    if (choque) {
      return err(409, 'destino ocupado', this.alternativas(actual.valor.tenantId, {
        profesionalId: actual.valor.profesionalId,
        sillonId: actual.valor.sillonId,
        duracionMin: duracion,
      }, nuevoInicio, actual.valor.id));
    }
    const original: Turno = { ...actual.valor, estado: 'REPROGRAMADO' };
    const nuevo: Turno = {
      ...actual.valor,
      id: `turno-${this.siguienteId++}`,
      inicio: nuevoInicio,
      fin: nuevoFin,
      estado: 'PENDIENTE',
      sobreturno: false,
    };
    this.turnos.set(id, original);
    this.turnos.set(nuevo.id, nuevo);
    this.auditar(original, 'REPROGRAMADO', actor.userId, undefined, actual.valor.estado, 'REPROGRAMADO');
    return { ok: true, valor: { original, nuevo } };
  }

  // ---- auditoría append-only (4.3) ----

  auditoria(actor: Actor, turnoId?: string): Resultado<AuditoriaEntrada[]> {
    if (actor.rol === 'PACIENTE') return err(403, 'paciente sin acceso a auditoría');
    let entradas = this.auditoriaLog;
    if (actor.rol === 'ODONTOLOGO') {
      entradas = entradas.filter((e) => {
        const t = this.turnos.get(e.turnoId);
        return t !== undefined && t.profesionalId === actor.profesionalId;
      });
    } else {
      entradas = entradas.filter((e) => e.tenantId === actor.tenantId);
    }
    if (turnoId !== undefined) entradas = entradas.filter((e) => e.turnoId === turnoId);
    return { ok: true, valor: [...entradas] };
  }

  // ---- helpers ----

  private puedeCrear(actor: Actor, data: { profesionalId: string; pacienteId: string; sobreturno?: boolean | undefined }): ErrorApi | null {
    if (actor.rol === 'PACIENTE') {
      if (data.pacienteId !== actor.userId) return err(403, 'paciente solo crea sus turnos');
      if (data.sobreturno === true) return err(403, 'paciente no crea sobreturnos');
      return null;
    }
    if (actor.rol === 'ODONTOLOGO' && data.profesionalId !== actor.profesionalId) {
      return err(403, 'odontólogo solo agenda propia');
    }
    return null;
  }

  private puedeEscribir(actor: Actor, turno: Turno): boolean {
    if (actor.rol === 'ADMIN' || actor.rol === 'RECEPCION') return true;
    if (actor.rol === 'ODONTOLOGO') return turno.profesionalId === actor.profesionalId;
    return turno.pacienteId === actor.userId;
  }

  private esRecepcion(actor: Actor): boolean {
    return actor.rol === 'RECEPCION' || actor.rol === 'ADMIN';
  }

  private bajoAnticipacion(turno: Turno, ahora: Date): boolean {
    return turno.inicio.getTime() - ahora.getTime() < this.anticipacionMinMs;
  }

  private duracionDe(turno: Turno): number {
    return Math.round((turno.fin.getTime() - turno.inicio.getTime()) / 60_000);
  }

  /** Espeja el predicado parcial del EXCLUDE 003 (D1/D2). */
  private haySolape(
    tenantId: string,
    profesionalId: string,
    sillonId: string,
    inicio: Date,
    fin: Date,
    excluirId: string | null,
  ): boolean {
    const msI = inicio.getTime();
    const msF = fin.getTime();
    if (msI >= msF) return true;
    for (const t of this.turnos.values()) {
      if (t.id === excluirId) continue;
      if (t.tenantId !== tenantId) continue;
      if (t.profesionalId !== profesionalId && t.sillonId !== sillonId) continue;
      if (liberaHueco(t.estado)) continue;
      if (t.sobreturno) continue;
      // half-open [inicio, fin)
      if (msI < t.fin.getTime() && t.inicio.getTime() < msF) return true;
    }
    return false;
  }

  private alternativas(
    tenantId: string,
    data: { profesionalId: string; sillonId: string; duracionMin: number },
    desde: Date,
    excluirId?: string,
  ): Alternativa[] {
    const ocupados = [...this.turnos.values()]
      .filter((t) => excluirId === undefined || t.id !== excluirId)
      .map((t) => ({
        tenantId: t.tenantId,
        profesionalId: t.profesionalId,
        sillonId: t.sillonId,
        inicio: t.inicio,
        fin: t.fin,
        estado: t.estado as TurnoEstado,
        sobreturno: t.sobreturno,
      }));
    return buscarAlternativas({
      desde,
      duracionMin: data.duracionMin,
      tenantId,
      profesionalId: data.profesionalId,
      sillonId: data.sillonId,
      ocupados,
    });
  }

  private auditar(
    turno: Turno,
    accion: AuditoriaEntrada['accion'],
    actor: string,
    motivo: string | undefined,
    antes: TurnoEstado | null,
    despues: TurnoEstado,
  ): void {
    const entrada: AuditoriaEntrada = {
      turnoId: turno.id,
      tenantId: turno.tenantId,
      accion,
      actor,
      ...(motivo !== undefined ? { motivo } : {}),
      antes,
      despues,
      registradoEn: new Date().toISOString(),
    };
    this.auditoriaLog.push(entrada);
  }
}

export type { TurnoEstado, TurnoOrigen };
