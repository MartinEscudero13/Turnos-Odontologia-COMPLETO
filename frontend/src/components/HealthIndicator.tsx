import { useEffect, useState } from 'react';
import { fetchHealth } from '../healthClient';
import { StatusBadge } from './StatusBadge';

type HealthState = 'loading' | 'up' | 'down';

export function HealthIndicator(): JSX.Element {
  const [state, setState] = useState<HealthState>('loading');

  useEffect(() => {
    let isMounted = true;
    fetchHealth().then((result) => {
      if (!isMounted) return;
      setState(result.ok ? 'up' : 'down');
    });
    return () => {
      isMounted = false;
    };
  }, []);

  if (state === 'loading') {
    return (
      <StatusBadge tone="neutral">
        <span className="status-dot" aria-hidden="true" /> Verificando API
      </StatusBadge>
    );
  }
  if (state === 'up') {
    return (
      <StatusBadge tone="success">
        <span className="status-dot" aria-hidden="true" /> API operativa
      </StatusBadge>
    );
  }
  return (
    <StatusBadge tone="danger">
      <span className="status-dot" aria-hidden="true" /> API no disponible
    </StatusBadge>
  );
}
