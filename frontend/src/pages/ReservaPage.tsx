import { useEffect, useState, type FormEvent } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { EmptyState } from '../components/EmptyState';
import { Field } from '../components/Field';
import { StatusBadge } from '../components/StatusBadge';
import {
  catalogo,
  disponibilidad,
  emitirVerificacion,
  reservar,
  type AlternativaHueco,
  type CatalogoPublico,
  type Hueco,
  type PrestacionPublica,
  type ProfesionalPublico,
} from '../reservaPublicaClient';
import {
  ahoraConOffset,
  formatearDuracion,
  formatearFechaHora,
  formatearHora,
} from '../reservaPublicaFormat';

type EstadoEnlace = 'cargando' | 'listo' | 'invalido' | 'error';
type Paso = 'catalogo' | 'huecos' | 'formulario';

const MENSAJE_ENLACE_INVALIDO = 'Este enlace no corresponde a un consultorio activo.';

function mensajeDeEspera(segundos: number | undefined): string {
  return segundos !== undefined
    ? `Hiciste muchos intentos seguidos. Volvé en ${segundos} segundos.`
    : 'Hiciste muchos intentos seguidos. Volvé en unos minutos.';
}

export function ReservaPage(): JSX.Element {
  const { tokenTenant = '' } = useParams();
  const navigate = useNavigate();

  const [estadoEnlace, setEstadoEnlace] = useState<EstadoEnlace>('cargando');
  const [errorEnlace, setErrorEnlace] = useState<string | null>(null);
  const [intentoCatalogo, setIntentoCatalogo] = useState(0);
  const [datosCatalogo, setDatosCatalogo] = useState<CatalogoPublico | null>(null);

  const [profesional, setProfesional] = useState<ProfesionalPublico | null>(null);
  const [prestacion, setPrestacion] = useState<PrestacionPublica | null>(null);
  const [paso, setPaso] = useState<Paso>('catalogo');

  const [huecos, setHuecos] = useState<Hueco[]>([]);
  const [cargandoHuecos, setCargandoHuecos] = useState(false);
  const [errorHuecos, setErrorHuecos] = useState<string | null>(null);
  const [hueco, setHueco] = useState<Hueco | null>(null);

  const [nombre, setNombre] = useState('');
  const [telefono, setTelefono] = useState('');
  const [verificacionId, setVerificacionId] = useState<string | null>(null);
  const [verificando, setVerificando] = useState(false);
  const [errorVerificacion, setErrorVerificacion] = useState<string | null>(null);

  const [enviando, setEnviando] = useState(false);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [errorTelefono, setErrorTelefono] = useState<string | null>(null);
  const [alternativas, setAlternativas] = useState<AlternativaHueco[]>([]);

  useEffect(() => {
    let vigente = true;
    setEstadoEnlace('cargando');
    setErrorEnlace(null);

    void catalogo(tokenTenant).then((result) => {
      if (!vigente) {
        return;
      }
      if (!result.ok) {
        setEstadoEnlace(result.status === 404 ? 'invalido' : 'error');
        setErrorEnlace(result.error ?? 'No pudimos cargar el consultorio.');
        return;
      }
      const data = result.data ?? { prestaciones: [], profesionales: [] };
      setDatosCatalogo(data);
      setProfesional(data.profesionales[0] ?? null);
      setEstadoEnlace('listo');
    });

    return () => {
      vigente = false;
    };
  }, [tokenTenant, intentoCatalogo]);

  async function cargarHuecos(
    prestacionElegida: PrestacionPublica,
    profesionalElegido: ProfesionalPublico | null,
  ): Promise<void> {
    setCargandoHuecos(true);
    setErrorHuecos(null);
    setHuecos([]);
    const result = await disponibilidad(tokenTenant, {
      prestacion: prestacionElegida.id,
      ...(profesionalElegido !== null ? { profesional: profesionalElegido.id } : {}),
      desde: ahoraConOffset(),
    });
    setCargandoHuecos(false);
    if (!result.ok) {
      if (result.status === 404) {
        setEstadoEnlace('invalido');
        return;
      }
      if (result.status === 429) {
        setErrorHuecos(mensajeDeEspera(result.retryAfterSeconds));
        return;
      }
      setErrorHuecos(result.error ?? 'No pudimos cargar los horarios.');
      return;
    }
    setHuecos(result.data ?? []);
  }

  function elegirPrestacion(prestacionElegida: PrestacionPublica): void {
    setPrestacion(prestacionElegida);
    setPaso('huecos');
    setHueco(null);
    setAlternativas([]);
    setErrorGeneral(null);
    setErrorTelefono(null);
    setErrorVerificacion(null);
    setVerificacionId(null);
    void cargarHuecos(prestacionElegida, profesional);
  }

  function elegirProfesional(profesionalElegido: ProfesionalPublico): void {
    setProfesional(profesionalElegido);
    if (prestacion !== null) {
      void cargarHuecos(prestacion, profesionalElegido);
    }
  }

  async function solicitarVerificacion(): Promise<void> {
    setVerificando(true);
    setErrorVerificacion(null);
    const result = await emitirVerificacion(tokenTenant, { accion: 'reservar' });
    setVerificando(false);
    if (!result.ok) {
      setVerificacionId(null);
      setErrorVerificacion(
        result.status === 429
          ? mensajeDeEspera(result.retryAfterSeconds)
          : (result.error ?? 'No pudimos verificar que no sos un robot.'),
      );
      return;
    }
    setVerificacionId(result.data?.verificacionId ?? null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (
      enviando ||
      prestacion === null ||
      profesional === null ||
      hueco === null ||
      verificacionId === null
    ) {
      return;
    }
    setEnviando(true);
    setErrorGeneral(null);
    setErrorTelefono(null);
    setAlternativas([]);

    const result = await reservar(tokenTenant, {
      prestacion: prestacion.id,
      profesional: profesional.id,
      inicio: hueco.inicio,
      nombre: nombre.trim(),
      telefono: telefono.trim(),
      verificacionId,
    });
    setEnviando(false);

    if (result.ok && result.data !== undefined) {
      navigate(
        `/r/${encodeURIComponent(tokenTenant)}/turno/${encodeURIComponent(result.data.tokenPublico)}`,
        { state: { reserva: result.data } },
      );
      return;
    }

    switch (result.status) {
      case 403:
        setVerificacionId(null);
        setErrorGeneral(
          'La verificación venció o ya se usó. Reintentá la verificación para reservar.',
        );
        break;
      case 404:
        setEstadoEnlace('invalido');
        break;
      case 409:
        setAlternativas((result.alternativas ?? []).slice(0, 3));
        setErrorGeneral(
          'Ese horario ya no está libre. Elegí una de las alternativas para reintentar.',
        );
        break;
      case 422:
        setErrorTelefono('Revisá el teléfono: usá el formato +54 9 11 0000 0000.');
        break;
      case 429:
        setErrorGeneral(mensajeDeEspera(result.retryAfterSeconds));
        break;
      default:
        setErrorGeneral(result.error ?? 'No pudimos completar la reserva.');
    }
  }

  function elegirAlternativa(alternativa: AlternativaHueco): void {
    if (hueco === null) {
      return;
    }
    setHueco({ ...hueco, inicio: alternativa.inicio, fin: alternativa.fin });
    setAlternativas([]);
    setErrorGeneral(null);
  }

  if (estadoEnlace === 'cargando') {
    return (
      <section className="reserva-page">
        <p className="reserva-status" role="status" aria-live="polite" aria-busy="true">
          Buscando las prestaciones del consultorio…
        </p>
      </section>
    );
  }

  if (estadoEnlace === 'invalido') {
    return (
      <section className="error-state" aria-labelledby="enlace-invalido">
        <p className="eyebrow">404 / enlace inválido</p>
        <h1 id="enlace-invalido">{MENSAJE_ENLACE_INVALIDO}</h1>
        <p>
          El link puede estar mal copiado o el consultorio ya no publica reservas online. Pedí el
          link actualizado y volvé a intentar.
        </p>
        <Link className="button button-primary" to="/">
          Volver al inicio
        </Link>
        <p className="error-mark" aria-hidden="true">
          404
        </p>
      </section>
    );
  }

  if (estadoEnlace === 'error' || datosCatalogo === null) {
    return (
      <section className="reserva-page">
        <EmptyState
          title="No pudimos cargar el consultorio"
          description={errorEnlace ?? 'Revisá tu conexión y volvé a intentar.'}
          action={
            <Button variant="secondary" onClick={() => setIntentoCatalogo((valor) => valor + 1)}>
              Reintentar
            </Button>
          }
        />
      </section>
    );
  }

  if (datosCatalogo.prestaciones.length === 0) {
    return (
      <section className="reserva-page">
        <EmptyState
          title="El consultorio todavía no publicó prestaciones"
          description="Cuando publique sus prestaciones vas a poder reservar desde este mismo enlace."
          action={
            <Link className="button button-secondary" to="/">
              Volver al inicio
            </Link>
          }
        />
      </section>
    );
  }

  if (datosCatalogo.profesionales.length === 0) {
    return (
      <section className="reserva-page">
        <EmptyState
          title="El consultorio todavía no publicó profesionales disponibles"
          description="No hay con quién reservar en este momento. Probá más tarde o comunicate con el consultorio."
          action={
            <Link className="button button-secondary" to="/">
              Volver al inicio
            </Link>
          }
        />
      </section>
    );
  }

  const titulo =
    paso === 'formulario'
      ? 'Nombre, teléfono y una verificación.'
      : 'Elegí la prestación y mirá los horarios.';
  const resumen =
    prestacion !== null && hueco !== null
      ? `${prestacion.nombre} · ${formatearFechaHora(hueco.inicio)}`
      : '';

  return (
    <section className="reserva-page" aria-labelledby="reserva-title">
      <header className="reserva-heading">
        <p className="eyebrow">Reservá tu turno</p>
        <h1 id="reserva-title">{titulo}</h1>
        <p className="page-description">
          Los horarios que ves son reales y se actualizan al confirmar. Sin llamar, sin login.
        </p>
      </header>

      <div className="reserva-grid">
        <div className="reserva-columna">
          {paso === 'catalogo' ? (
            <section aria-labelledby="prestacion-title" className="reserva-paso">
              <h2 id="prestacion-title">1 · Prestación</h2>
              <ul className="prest-list" aria-label="Prestaciones disponibles">
                {datosCatalogo.prestaciones.map((item) => (
                  <li key={item.id}>
                    <button
                      type="button"
                      className="prest-option"
                      aria-pressed={prestacion?.id === item.id}
                      onClick={() => elegirPrestacion(item)}
                    >
                      <span>
                        <span className="prest-name">{item.nombre}</span>
                        <span className="prest-meta">{item.duracionMin} min</span>
                      </span>
                      <span className="prest-marker" aria-hidden="true">
                        Elegir
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
              {datosCatalogo.profesionales.length > 1 ? (
                <div className="prest-profesionales" role="group" aria-label="Profesional">
                  <p className="field-label">Profesional</p>
                  {datosCatalogo.profesionales.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="prest-option"
                      aria-pressed={profesional?.id === item.id}
                      onClick={() => elegirProfesional(item)}
                    >
                      <span className="prest-name">{item.nombre}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="muted">Profesional: {profesional?.nombre}</p>
              )}
            </section>
          ) : null}

          {paso === 'huecos' && prestacion !== null ? (
            <section aria-labelledby="huecos-title" className="reserva-paso">
              <div className="ficha">
                <div className="ficha-topline">
                  <span>
                    {prestacion.nombre} · {prestacion.duracionMin} min
                  </span>
                  <StatusBadge tone="success">Horarios reales</StatusBadge>
                </div>

                <h2 id="huecos-title">2 · Elegí un horario</h2>

                {cargandoHuecos ? (
                  <p className="reserva-status" role="status" aria-live="polite" aria-busy="true">
                    Buscando horarios disponibles…
                  </p>
                ) : null}

                {!cargandoHuecos && errorHuecos !== null ? (
                  <div className="form-error" role="alert" aria-live="assertive">
                    <p>{errorHuecos}</p>
                    <Button
                      variant="secondary"
                      className="button-small"
                      onClick={() => void cargarHuecos(prestacion, profesional)}
                    >
                      Reintentar
                    </Button>
                  </div>
                ) : null}

                {!cargandoHuecos && errorHuecos === null && huecos.length === 0 ? (
                  <EmptyState
                    title="No hay horarios disponibles"
                    description="Probá con otra prestación o volvé a intentar más tarde."
                    action={
                      <div className="reserva-acciones">
                        <Button variant="secondary" onClick={() => setPaso('catalogo')}>
                          Elegir otra prestación
                        </Button>
                        <Button
                          variant="quiet"
                          onClick={() => void cargarHuecos(prestacion, profesional)}
                        >
                          Volver a intentar
                        </Button>
                      </div>
                    }
                  />
                ) : null}

                {!cargandoHuecos && huecos.length > 0 ? (
                  <div className="ruler">
                    <ul
                      className="slots"
                      role="listbox"
                      aria-label={`Horarios disponibles para ${prestacion.nombre}`}
                    >
                      {huecos.map((item) => {
                        const seleccionado = hueco?.inicio === item.inicio;
                        return (
                          <li key={`${item.inicio}-${item.profesionalId}-${item.sillonId}`}>
                            <button
                              type="button"
                              className={`slot ${seleccionado ? 'is-selected' : ''}`.trim()}
                              role="option"
                              aria-selected={seleccionado}
                              onClick={() => setHueco(item)}
                            >
                              <span className="slot-time">{formatearHora(item.inicio)}</span>
                              <span className="slot-meta">
                                {formatearDuracion(item.inicio, item.fin)}
                              </span>
                              <span className="slot-tag">Sillón {item.sillonId}</span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                ) : null}

                {hueco !== null && !cargandoHuecos ? (
                  <div className="chosen">
                    <span className="muted">Tu elección</span>
                    <strong>{resumen}</strong>
                    <span className="muted">
                      La hora se reserva al confirmar. Si se ocupa, te ofrecemos alternativas.
                    </span>
                  </div>
                ) : null}
              </div>

              {hueco !== null ? (
                <Button className="button-full" onClick={() => setPaso('formulario')}>
                  Continuar con nombre y teléfono
                </Button>
              ) : null}
            </section>
          ) : null}

          {paso === 'formulario' && prestacion !== null && hueco !== null ? (
            <section aria-labelledby="formulario-title" className="reserva-paso">
              <div className="ficha reserva-formulario">
                <div className="ficha-topline">
                  <span>Resumen</span>
                  <StatusBadge tone="pending">Pendiente</StatusBadge>
                </div>
                <h2 id="formulario-title">3 · Tus datos</h2>
                <div className="chosen">
                  <strong>{resumen}</strong>
                  <span className="muted">
                    {prestacion.duracionMin} min · Sillón {hueco.sillonId}
                  </span>
                </div>

                <form className="reserva-form" onSubmit={handleSubmit} noValidate>
                  <Field
                    label="Nombre"
                    autoComplete="name"
                    value={nombre}
                    onChange={(event) => setNombre(event.target.value)}
                    required
                  />
                  <Field
                    label="Teléfono"
                    type="tel"
                    inputMode="tel"
                    autoComplete="tel"
                    placeholder="+54 9 11 0000 0000"
                    hint="Lo usamos para confirmar tu turno. No lo compartimos."
                    error={errorTelefono ?? undefined}
                    value={telefono}
                    onChange={(event) => setTelefono(event.target.value)}
                    required
                  />

                  <div className="field">
                    <span className="field-label" id="verificacion-label">
                      Verificación
                    </span>
                    <div
                      className="captcha"
                      aria-busy={verificando}
                      aria-labelledby="verificacion-label"
                    >
                      <label className="captcha-check">
                        <input
                          type="checkbox"
                          checked={verificacionId !== null}
                          disabled={verificando}
                          onChange={(event) => {
                            if (!event.target.checked) {
                              setVerificacionId(null);
                              return;
                            }
                            void solicitarVerificacion();
                          }}
                        />
                        <span>No soy un robot</span>
                      </label>
                      <span className="tbd">captcha (TBD)</span>
                    </div>
                    <p className="field-message">
                      Una verificación liviana de un solo uso, para evitar reservas automáticas.
                    </p>
                    {verificando ? (
                      <p className="field-message" role="status" aria-live="polite">
                        Verificando…
                      </p>
                    ) : null}
                    {errorVerificacion !== null ? (
                      <p className="field-message error" role="alert">
                        {errorVerificacion}
                      </p>
                    ) : null}
                  </div>

                  {errorGeneral !== null ? (
                    <div className="form-error" role="alert" aria-live="assertive">
                      <p>{errorGeneral}</p>
                      {errorGeneral.includes('verificación') ? (
                        <Button
                          variant="secondary"
                          className="button-small"
                          onClick={() => void solicitarVerificacion()}
                        >
                          Reintentar la verificación
                        </Button>
                      ) : null}
                    </div>
                  ) : null}

                  {alternativas.length > 0 ? (
                    <div className="ruler" aria-live="polite">
                      <ul className="slots" role="listbox" aria-label="Horarios alternativos">
                        {alternativas.map((alternativa) => (
                          <li key={alternativa.inicio}>
                            <button
                              type="button"
                              className="slot"
                              role="option"
                              aria-selected={false}
                              onClick={() => elegirAlternativa(alternativa)}
                            >
                              <span className="slot-time">
                                {formatearHora(alternativa.inicio)}
                              </span>
                              <span className="slot-meta">
                                {formatearDuracion(alternativa.inicio, alternativa.fin)}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}

                  {errorTelefono !== null ? (
                    <p className="sr-only" role="alert">
                      No pudimos reservar. Revisá el campo teléfono.
                    </p>
                  ) : null}

                  <Button
                    type="submit"
                    className="button-full"
                    isLoading={enviando}
                    disabled={
                      nombre.trim().length === 0 ||
                      telefono.trim().length === 0 ||
                      verificacionId === null
                    }
                  >
                    Reservar turno
                  </Button>
                </form>

                <div className="reserva-acciones">
                  <Button variant="quiet" onClick={() => setPaso('huecos')}>
                    ← Volver a los horarios
                  </Button>
                </div>
              </div>
            </section>
          ) : null}
        </div>

        <aside className="reserva-aside">
          <div className="aside-note">
            <p>
              <strong>Sin login.</strong> Solo tu nombre, tu teléfono y una verificación para
              reservar.
            </p>
          </div>
          <div className="aside-note">
            <p>
              <strong>Gestión con código.</strong> Al confirmar recibís un código para cancelar o
              reprogramar hasta 24 h antes.
            </p>
          </div>
        </aside>
      </div>
    </section>
  );
}
