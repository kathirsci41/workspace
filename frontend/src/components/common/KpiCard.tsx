import type { ReactNode } from 'react';

export function KpiCard({ label, value, helper, tone = 'neutral' }: { label: string; value: ReactNode; helper?: ReactNode; tone?: 'success' | 'warning' | 'danger' | 'info' | 'neutral' }) {
  return (
    <article className={`kpi-card kpi-card--${tone}`}>
      <span className="kpi-card__label">{label}</span>
      <strong className="kpi-card__value">{value}</strong>
      {helper ? <span className="kpi-card__helper">{helper}</span> : null}
    </article>
  );
}
