import { useEffect, useState } from 'react';
import { fetchHealth, type HealthPayload } from './healthClient';

export function App(): JSX.Element {
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;

    fetchHealth().then((result) => {
      if (!isMounted) return;
      if (result.ok && result.data) {
        setHealth(result.data);
      } else {
        setError(result.error ?? 'Health check no disponible');
      }
      setIsLoading(false);
    });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <main aria-labelledby="page-title">
      <section className="panel">
        <p className="eyebrow">Fundación SaaS</p>
        <h1 id="page-title">Turnos-Odontologia</h1>
        <p className="subtitle">
          Agenda multi-profesional con aislamiento por tenant, reserva pública y arquitectura lista para crecer.
        </p>
        <div className="health-card" aria-live="polite">
          <p>Estado de la API</p>
          {isLoading && <p>Verificando servicios…</p>}
          {health && (
            <p className="health-success">
              {health.service} está {health.status} · v{health.version}
            </p>
          )}
          {error && (
            <p className="health-error" role="alert">
              API no disponible: {error}
            </p>
          )}
        </div>
        <p className="meta">
          El endpoint de salud es público y no contiene datos de pacientes. Configuración mediante
          <code> VITE_API_BASE_URL</code>.
        </p>
      </section>
    </main>
  );
}
