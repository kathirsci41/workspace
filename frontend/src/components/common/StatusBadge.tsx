import { statusLabel, statusTone } from '../../lib/build1';

export function StatusBadge({ status, label }: { status: string | null | undefined; label?: string }) {
  const visibleLabel = label ?? statusLabel(status);
  return (
    <span className={`status-badge status-badge--${statusTone(status)}`} aria-label={`Status ${visibleLabel}`}>
      {visibleLabel}
    </span>
  );
}
