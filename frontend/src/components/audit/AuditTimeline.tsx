import { documentLabel, identifierLabel } from '../../lib/build1';
import { fieldLabel, formatDateTime, formatValue } from '../../lib/format';
import type { AuditEvent } from '../../types/api';

export function AuditTimeline({ events, selectedId, onSelect }: { events: AuditEvent[]; selectedId: string | null; onSelect: (event: AuditEvent) => void }) {
  return (
    <div className="timeline" aria-label="Manual correction timeline">
      {events.map((event) => {
        const changes = Array.isArray(event.payload?.changes) ? event.payload.changes as Array<Record<string, unknown>> : [];
        return (
          <button
            key={event.id}
            type="button"
            className={`timeline-item ${selectedId === event.id ? 'is-selected' : ''}`}
            onClick={() => onSelect(event)}
          >
            <span>{formatDateTime(event.created_at)}</span>
            <strong>{identifierLabel(event.event_type).replace('Manual Extracted Data Patched', 'Manual Correction')}</strong>
            <span>{documentLabel(String(event.payload?.document_type ?? ''))}</span>
            {changes.length ? (
              <small>{changes.map((change) => `${fieldLabel(String(change.field ?? 'Field'))}: ${formatValue(change.old_value)} to ${formatValue(change.new_value)}`).join(', ')}</small>
            ) : (
              <small>{String(event.payload?.reason ?? event.actor)}</small>
            )}
          </button>
        );
      })}
    </div>
  );
}
