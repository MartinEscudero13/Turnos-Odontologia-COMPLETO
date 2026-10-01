import { z } from 'zod';

/** Borde API — validación zod, tipado estricto (regla dura: sin `any`). */

export const crearTurnoSchema = z.object({
  profesionalId: z.string().min(1),
  sillonId: z.string().min(1),
  pacienteId: z.string().min(1),
  prestacionId: z.string().min(1),
  duracionMin: z.number().int().positive(),
  inicio: z.string().datetime({ offset: true }),
  finCliente: z.string().datetime({ offset: true }).optional(),
  sobreturno: z.boolean().optional(),
  motivoSobreturno: z.string().optional(),
  origen: z.enum(['RECEPCION', 'RESERVA_ONLINE', 'LISTA_ESPERA']).optional(),
});

export type CrearTurnoInput = z.infer<typeof crearTurnoSchema>;

/** Solo pacienteId es actualizable; .strict() rechaza el resto con 422. */
export const actualizarTurnoSchema = z
  .object({ pacienteId: z.string().min(1) })
  .strict();

export const motivoSchema = z.object({ motivo: z.string().trim().min(1) }).strict();

export const reprogramarSchema = z
  .object({
    nuevoInicio: z.string().datetime({ offset: true }),
    duracionMin: z.number().int().positive().optional(),
  })
  .strict();
