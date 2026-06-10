import { Navigate, useParams } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { listAuditEvents } from '../api/audit';
import { getBundle } from '../api/bundles';
import { AuditTimeline } from '../components/audit/AuditTimeline';
import { ErrorState } from '../components/common/ErrorState';
import { LoadingState } from '../components/common/LoadingState';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { documentLabel, identifierLabel } from '../lib/build1';
import { fieldLabel, formatDateTime, formatValue } from '../lib/format';
import type { AuditEvent, OrderBundle } from '../types/api';

export function AuditTrailPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <AuditTrailContent bundleId={bundleId} />;
}

function AuditTrailContent({ bundleId }: { bundleId: string }) {
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const audit = useAsyncResource<AuditEvent[]>(() => listAuditEvents(bundleId), [bundleId]);
  const [eventType, setEventType] = useState('All');
  const [documentType, setDocumentType] = useState('All');
  const [selectedEvent, setSelectedEvent] = useState<AuditEvent | null>(null);
  const eventTypes = Array.from(new Set((audit.data ?? []).map((event) => event.event_type)));
  const documentTypes = Array.from(new Set((audit.data ?? []).map((event) => String(event.payload?.document_type ?? '')).filter(Boolean)));
  const visibleEvents = useMemo(() => (audit.data ?? []).filter((event) => (
    (eventType === 'All' || event.event_type === eventType)
    && (documentType === 'All' || String(event.payload?.document_type ?? '') === documentType)
  )), [audit.data, eventType, documentType]);
  const activeEvent = selectedEvent ?? visibleEvents[0] ?? null;
  const changes = Array.isArray(activeEvent?.payload?.changes) ? activeEvent?.payload?.changes as Array<Record<string, unknown>> : [];

  return (
    <AppShell
      bundleId={bundleId}
      title="Manual Correction History"
      subtitle={bundle.data?.bundle_number ?? 'Field-level correction history.'}
      breadcrumbs={[{ label: 'Bundles', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Manual Correction History' }]}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? audit.error} />
      {audit.isLoading ? <LoadingState label="Loading audit trail..." /> : null}

      <section className="note-card" aria-label="Manual correction scope">
        This section records manual corrections. Upload, extraction, review, and export events are available in system logs.
      </section>

      <section className="panel">
        <div className="controls-row">
          <label>
            Correction type
            <select value={eventType} onChange={(event) => setEventType(event.target.value)}>
              <option>All</option>
              {eventTypes.map((type) => <option key={type} value={type}>{identifierLabel(type)}</option>)}
            </select>
          </label>
          <label>
            Document
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              <option>All</option>
              {documentTypes.map((type) => <option key={type} value={type}>{documentLabel(type)}</option>)}
            </select>
          </label>
        </div>
      </section>

      <div className="content-grid content-grid--detail">
        <section className="panel">
          {visibleEvents.length ? (
            <AuditTimeline events={visibleEvents} selectedId={activeEvent?.id ?? null} onSelect={setSelectedEvent} />
          ) : (
            <p className="muted">No manual corrections recorded.</p>
          )}
        </section>
        <aside className="detail-panel audit-detail-panel" aria-label="Manual correction detail">
          <h2>Correction Detail</h2>
          {activeEvent ? (
            <>
              <h3>{identifierLabel(activeEvent.event_type).replace('Manual Extracted Data Patched', 'Manual Correction')}</h3>
              <dl className="detail-list">
                <div>
                  <dt>Timestamp</dt>
                  <dd>{formatDateTime(activeEvent.created_at)}</dd>
                </div>
                <div>
                  <dt>Actor</dt>
                  <dd>{activeEvent.actor}</dd>
                </div>
                <div>
                  <dt>Document</dt>
                  <dd>{documentLabel(String(activeEvent.payload?.document_type ?? ''))}</dd>
                </div>
                <div>
                  <dt>Reason</dt>
                  <dd>{formatValue(activeEvent.payload?.reason)}</dd>
                </div>
              </dl>
              {changes.length ? (
                <div className="data-table-wrap">
                <table className="data-table audit-changes-table" aria-label="Manual correction changes">
                  <thead>
                    <tr>
                      <th>Field</th>
                      <th>Before</th>
                      <th>After</th>
                    </tr>
                  </thead>
                  <tbody>
                    {changes.map((change, index) => (
                      <tr key={`${String(change.field)}-${index}`}>
                        <td>{fieldLabel(String(change.field ?? '-'))}</td>
                        <td className="value-cell">{formatValue(change.old_value)}</td>
                        <td className="value-cell">{formatValue(change.new_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                </div>
              ) : null}
            </>
          ) : (
            <p className="muted">Select a manual correction to see details.</p>
          )}
        </aside>
      </div>
    </AppShell>
  );
}
