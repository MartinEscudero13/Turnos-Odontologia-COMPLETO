import type { ReactNode } from 'react';

interface StatusBadgeProps {
  tone: 'success' | 'pending' | 'danger' | 'neutral';
  children: ReactNode;
}

export function StatusBadge({ tone, children }: StatusBadgeProps): JSX.Element {
  return <span className={`status-badge status-${tone}`}>{children}</span>;
}
