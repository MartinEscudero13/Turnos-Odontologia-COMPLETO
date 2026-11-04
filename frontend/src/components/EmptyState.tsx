import type { ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}): JSX.Element {
  return (
    <section className="empty-state">
      <span className="empty-state-mark" aria-hidden="true">
        09:00
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {action}
    </section>
  );
}
