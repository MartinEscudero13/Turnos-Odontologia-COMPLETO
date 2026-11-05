import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { StatusBadge } from '../components/StatusBadge';
import {
  cancelar,
  catalogo,
  consultarReserva,
  disponibilidad,
  emitirVerificacion,
  reprogramar,
  type Hueco,
  type ReservaCreada,
  type ReservaPropia,
} from '../reservaPublicaClient';
import {
  ahoraConOffset,
  esGestionable,
  estadoVisible,
  formatearDuracion,
  formatearFechaHora,
  formatearHora,
} from '../reservaPublicaFormat';

type EstadoPagina = 'cargando' | 'listo' | 'no-encontrado' | 'error';
type Accion = 'cancelando' | 'reprogramando' | null;

interface EstadoNavegacion {
  reserva?: ReservaCreada;
}

const MENSAJE_RECEPCION =
  'No podemos gestionar este turno online: falta la anticipación mínima. Gestioná este turno en el consultorio.';

function mensajeDeEspera(segundos: number | undefined): string {
  return segundos !== undefined
    ? `Hiciste muchos intentos seguidos. Volvé en ${segundos} segundos.`
    : 'Hiciste muchos intentos seguidos. Volvé en unos minutos.';
}

function copiarConFallback(texto: string): boolean {
  const area = document.createElement('textarea');
  area.value = texto;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.opacity = '0';
  document.body.appendChild(area);
  area.select();
  const copiado = document.execCommand('copy');
  document.body.removeChild(area);
  return copiado;
}

export function GestionTurnoPage(): JSX.Element {
  const { tokenTenant = '', token = '' } = useParams();
  const navegacion = useLocation().state as EstadoNavegacion | null;
  const reservaCreada = navegacion?.reserva ?? null;

  const [estadoPagina, setEstadoPagina] = useState<EstadoPagina>('cargando');
  const [errorPagina, setErrorPagina] = useState<string | null>(null);
  const [reserva, setReserva] = useState<ReservaPropia | null>(null);
  const [nombrePrestacion, setNombrePrestacion] = useState<string | null>(null);

  const [accion, setAccion] = useState<Accion>(null);
  const [confirmandoCancelacion, setConfirmandoCancelacion] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [bajoUmbral, setBajoUmbral] = useState(false);

  const [modoReprogramar, setModoReprogramar] = useState(false);
  const [huecosNuevos, setHuecosNuevos] = useState<Hueco[]>([]);
  const [cargandoHuecos, setCargandoHuecos] = useState(false);
  const [errorHuecos, setErrorHuecos] = useState<string | null>(null);

  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    let vigente = true;
    setEstadoPagina('cargando');

    void Promise.all([consultarReserva(tokenTenant, token), catalogo(tokenTenant)]).then(
      ([turno, catalogoPublico]) => {
        if (!vigente) {
          return;
        }
        if (!turno.ok || turno.data === undefined) {
          setEstadoPagina(turno.status === 404 ? 'no-encontrado' : 'error');
          setErrorPagina(turno.error ?? 'No pudimos consultar el turno.');
          return;
        }
        setReserva(turno.data);
        if (catalogoPublico.ok && catalogoPublico.data !== undefined) {
          const encontrada = catalogoPublico.data.prestaciones.find(
            (item) => item.id === turno.data?.prestacion,
          );
          setNombrePrestacion(encontrada?.nombre ?? null);
        }
        setEstadoPagina('listo');
      },
    );

    return () => {
      vigente = false;
    };
  }, [tokenTenant, token]);

  async function copiarToken(): Promise<void> {
    try {
      if (navigator.clipboard !== undefined && navigator.clipboard.writeText !== undefined) {
        await navigator.clipboard.writeText(token);
      } else if (!copiarConFallback(token)) {
        throw new Error('sin portapapeles');
      }
      setCopiado(true);
      setErrorAccion(null);
    } catch {
      setErrorAccion('No pudimos copiar el código. Copialo manualmente desde el recuadro.');
    }
  }

  async function confirmarCancelacion(): Promise<void> {
    setAccion('cancelando');
    setErrorAccion(null);

    const verificacion = await emitirVerificacion(tokenTenant, { accion: 'cancelar' });
    if (!verificacion.ok || verificacion.data === undefined) {
      setAccion(null);
      setErrorAccion(
        verificacion.status === 429
          ? mensajeDeEspera(verificacion.retryAfterSeconds)
          : (verificacion.error ?? 'No pudimos verificar la cancelación.'),
      );
      return;
    }

    const result = await cancelar(tokenTenant, token, {
      verificacionId: verificacion.data.verificacionId,
    });
    setAccion(null);

    if (!result.ok || result.data === undefined) {
      if (result.status === 403) {
        setBajoUmbral(true);
        setConfirmandoCancelacion(false);
        setErrorAccion(MENSAJE_RECEPCION);
        return;
      }
      setErrorAccion(
        result.status === 429
          ? mensajeDeEspera(result.retryAfterSeconds)
          : (result.error ?? 'No pudimos cancelar el turno.'),
      );
      return;
    }

    setReserva(result.data);
    setConfirmandoCancelacion(false);
  }

  async function cargarHuecosNuevos(prestacionId: string): Promise<void> {
    setCargandoHuecos(true);
    setErrorHuecos(null);
    setHuecosNuevos([]);
    const result = await disponibilidad(tokenTenant, {
      prestacion: prestacionId,
      desde: ahoraConOffset(),
    });
    setCargandoHuecos(false);
    if (!result.ok) {
      setErrorHuecos(
        result.status === 429
          ? mensajeDeEspera(result.retryAfterSeconds)
          : (result.error ?? 'No pudimos cargar horarios nuevos.'),
      );
      return;
    }
    setHuecosNuevos(result.data ?? []);
  }

  function abrirReprogramar(): void {
    if (reserva === null) {
      return;
    }
    setModoReprogramar(true);
    setErrorAccion(null);
    setErrorHuecos(null);
    setConfirmandoCancelacion(false);
    void cargarHuecosNuevos(reserva.prestacion);
  }

  async function elegirNuevoHueco(hueco: Hueco): Promise<void> {
    setAccion('reprogramando');
    setErrorAccion(null);

    const verificacion = await emitirVerificacion(tokenTenant, { accion: 'reprogramar' });
    if (!verificacion.ok || verificacion.data === undefined) {
      setAccion(null);
      setErrorAccion(
        verificacion.status === 429
          ? mensajeDeEspera(verificacion.retryAfterSeconds)
          : (verificacion.error ?? 'No pudimos verificar la reprogramación.'),
      );
      return;
    }

    const result = await reprogramar(tokenTenant, token, {
      nuevoInicio: hueco.inicio,
      verificacionId: verificacion.data.verificacionId,
    });
    setAccion(null);

    if (!result.ok || result.data === undefined) {
      if (result.status === 403) {
        setBajoUmbral(true);
        setModoReprogramar(false);
        setErrorAccion(MENSAJE_RECEPCION);
        return;
      }
      if (result.status === 409) {
        setErrorAccion('Ese horario ya no está libre. Elegí otro de la lista.');
        if (reserva !== null) {
          void cargarHuecosNuevos(reserva.prestacion);
        }
        return;
      }
      setErrorAccion(
        result.status === 429
          ? mensajeDeEspera(result.retryAfterSeconds)
          : (result.error ?? 'No pudimos reprogramar el turno.'),
      );
      return;
    }

    setReserva(result.data);
    setModoReprogramar(false);
    setHuecosNuevos([]);
  }

  if (estadoPagina === 'cargando') {
    return (
      <section className="reserva-page">
        <p className="reserva-status" role="status" aria-live="polite" aria-busy="true">
          Buscando tu turno…
        </p>
      </section>
    );
  }

  if (estadoPagina === 'no-encontrado') {
    return (
      <section className="error-state" aria-labelledby="turno-inexistente">
        <p className="eyebrow">404 / turno inexistente</p>
        <h1 id="turno-inexistente">No encontramos ese turno.</h1>
        <p>
          El código puede estar mal copiado, el turno ya pasó o fue cancelado. Si necesitás
          gestionarlo, comunicate con el consultorio.
        </p>
        <Link className="button button-primary" to="/">
          Volver al inicio
        </Link>
      </section>
    );
  }

  if (estadoPagina === 'error' || reserva === null) {
    return (
      <section className="error-state" aria-labelledby="turno-error">
        <p className="eyebrow">No pudimos consultar el turno</p>
        <h1 id="turno-error">Probá de nuevo en un momento.</h1>
        <p>{errorPagina ?? 'Revisá tu conexión y volvé a intentar.'}</p>
        <Link className="button button-secondary" to="/">
          Volver al inicio
        </Link>
      </section>
    );
  }

  const estado = estadoVisible(reserva.estado);
  const gestionable = esGestionable(reserva.estado) && !bajoUmbral;
  const sillon =
    reservaCreada !== null && reservaCreada.tokenPublico === token
      ? reservaCreada.sillonId
      : null;
  const prestacionVisible = nombrePrestacion ?? reserva.prestacion;

  return (
    <section className="reserva-page" aria-labelledby="mi-turno-title">
      <header className="reserva-heading">
        <p className="eyebrow">Mi turno</p>
        <h1 id="mi-turno-title">Tu turno.</h1>
        <p className="page-description">
          Guardá el código de gestión: es lo único que necesitás para cancelar o reprogramar.
        </p>
      </header>

      <div className="reserva-grid">
        <div className="reserva-columna">
          <div className="ficha" aria-live="polite">
            <div className="ficha-topline">
              <span>Mi turno</span>
              <StatusBadge tone={estado.tono}>{estado.etiqueta}</StatusBadge>
            </div>

            <div className="chosen">
              <strong>
                {prestacionVisible} · {formatearFechaHora(reserva.inicio)}
              </strong>
              <span className="muted">
                {formatearDuracion(reserva.inicio, reserva.fin)}
                {sillon !== null ? ` · Sillón ${sillon}` : ''}
              </span>
            </div>

            <div className="token-card">
              <div>
                <span className="muted">Código de gestión</span>
                <p className="token-value">{token}</p>
              </div>
              <Button
                variant="secondary"
                className="button-small"
                onClick={() => void copiarToken()}
              >
                Copiar código
              </Button>
            </div>
            <p className="field-message" role="status" aria-live="polite">
              {copiado ? 'Código copiado.' : ''}
            </p>

            {errorAccion !== null ? (
              <div className="form-error" role="alert" aria-live="assertive">
                <p>{errorAccion}</p>
              </div>
            ) : null}

            {gestionable ? (
              <div className="chosen">
                <span className="muted">Gestionar este turno</span>
                <div className="reserva-acciones">
                  <Button
                    variant="secondary"
                    disabled={accion !== null || modoReprogramar}
                    onClick={abrirReprogramar}
                  >
                    Reprogramar
                  </Button>
                  <Button
                    variant="danger"
                    disabled={accion !== null || modoReprogramar}
                    onClick={() => {
                      setErrorAccion(null);
                      setConfirmandoCancelacion(true);
                    }}
                  >
                    Cancelar turno
                  </Button>
                </div>
                <p className="field-message">
                  Podés cancelar o reprogramar hasta 24 h antes del turno. Después, contactá al
                  consultorio.
                </p>
              </div>
            ) : null}

            {confirmandoCancelacion && gestionable ? (
              <div className="form-error" role="alert">
                <p>¿Cancelás el turno del {formatearFechaHora(reserva.inicio)}?</p>
                <div className="reserva-acciones">
                  <Button
                    variant="danger"
                    className="button-small"
                    isLoading={accion === 'cancelando'}
                    onClick={() => void confirmarCancelacion()}
                  >
                    Sí, cancelar
                  </Button>
                  <Button
                    variant="secondary"
                    className="button-small"
                    disabled={accion !== null}
                    onClick={() => setConfirmandoCancelacion(false)}
                  >
                    No, volver
                  </Button>
                </div>
              </div>
            ) : null}

            {modoReprogramar && gestionable ? (
              <div className="reserva-reprogramar">
                <h2>Elegí un horario nuevo</h2>
                {cargandoHuecos ? (
                  <p className="reserva-status" role="status" aria-live="polite" aria-busy="true">
                    Buscando horarios disponibles…
                  </p>
                ) : null}
                {!cargandoHuecos && errorHuecos !== null ? (
                  <div className="form-error" role="alert">
                    <p>{errorHuecos}</p>
                    <Button
                      variant="secondary"
                      className="button-small"
                      onClick={() => void cargarHuecosNuevos(reserva.prestacion)}
                    >
                      Reintentar
                    </Button>
                  </div>
                ) : null}
                {!cargandoHuecos && errorHuecos === null && huecosNuevos.length === 0 ? (
                  <p className="muted">
                    No hay horarios nuevos disponibles. Probá más tarde o gestioná el turno en el
                    consultorio.
                  </p>
                ) : null}
                {!cargandoHuecos && huecosNuevos.length > 0 ? (
                  <div className="ruler">
                    <ul
                      className="slots"
                      role="listbox"
                      aria-label="Horarios disponibles para reprogramar"
                    >
                      {huecosNuevos.map((item) => (
                        <li key={`${item.inicio}-${item.profesionalId}-${item.sillonId}`}>
                          <button
                            type="button"
                            className="slot"
                            role="option"
                            aria-selected={false}
                            disabled={accion !== null}
                            onClick={() => void elegirNuevoHueco(item)}
                          >
                            <span className="slot-time">{formatearHora(item.inicio)}</span>
                            <span className="slot-meta">
                              {formatearDuracion(item.inicio, item.fin)}
                            </span>
                            <span className="slot-tag">Sillón {item.sillonId}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                <div className="reserva-acciones">
                  <Button
                    variant="quiet"
                    disabled={accion !== null}
                    onClick={() => {
                      setModoReprogramar(false);
                      setErrorHuecos(null);
                      setErrorAccion(null);
                    }}
                  >
                    ← Volver al turno
                  </Button>
                </div>
              </div>
            ) : null}
          </div>

          <div className="reserva-acciones">
            <Link className="button button-quiet" to={`/r/${encodeURIComponent(tokenTenant)}`}>
              ← Reservar otro turno
            </Link>
          </div>
        </div>

        <aside className="reserva-aside">
          <div className="aside-note">
            <p>
              <strong>El código es de un solo turno.</strong> Te sirve para cancelar o reprogramar,
              no para ver otros pacientes.
            </p>
          </div>
          <div className="aside-note">
            <p>
              <strong>Confirmación.</strong> La confirmación por WhatsApp llega en una versión
              próxima. Hoy alcanza con esta pantalla.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
