import { Link, Navigate, useParams } from 'react-router-dom';
import { useState } from 'react';
import { listAuditEvents } from '../api/audit';
import { getBundle } from '../api/bundles';
import { listBundleDocuments } from '../api/documents';
import { exportVerificationReport } from '../api/export';
import { getVerificationSummary } from '../api/verification';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { buildDocumentSlots, bundleStatus, documentExtractionStatus, documentReviewStatus, documentUploadStatus, extractionProgress, firstNextAction, identifierLabel, outcomeSummary, topIssues, verificationMetrics } from '../lib/build1';
import { formatDateTime, formatValue } from '../lib/format';
import type { AuditEvent, BundleDocument, OrderBundle, VerificationSummary } from '../types/api';

export function BundleOverviewPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <BundleOverviewContent bundleId={bundleId} />;
}

function BundleOverviewContent({ bundleId }: { bundleId: string }) {
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const audit = useAsyncResource<AuditEvent[]>(() => listAuditEvents(bundleId), [bundleId]);
  const [isExporting, setIsExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const docList = documents.data ?? [];
  const verification = verificationMetrics(summary.data);
  const extraction = extractionProgress(docList);
  const slots = buildDocumentSlots(docList);
  const nextAction = firstNextAction(summary.data, docList, bundleId);
  const outcome = outcomeSummary(summary.data, docList, bundleId);

  async function exportReport() {
    setIsExporting(true);
    setExportError(null);
    try {
      await exportVerificationReport(bundleId);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsExporting(false);
    }
  }

  return (
    <AppShell
      bundleId={bundleId}
      title={bundle.data?.bundle_number ?? 'Bundle Workspace'}
      subtitle={bundle.data ? (
        <span>
          <StatusBadge status={bundleStatus(bundle.data)} /> Created {formatDateTime(bundle.data.created_at)} Updated {formatDateTime(bundle.data.updated_at)}
        </span>
      ) : 'Loading bundle metadata...'}
      breadcrumbs={[{ label: 'Bundles', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId }]}
      actions={<button type="button" className="button button--primary" disabled={isExporting} onClick={exportReport}>{isExporting ? 'Exporting...' : 'Export Excel'}</button>}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? documents.error ?? summary.error ?? audit.error ?? exportError} />
      {bundle.isLoading || documents.isLoading || summary.isLoading ? <LoadingState label="Loading bundle workspace..." /> : null}

      <section className="outcome-card" aria-label="Outcome summary">
        <div>
          <p className="outcome-card__label">Outcome Summary</p>
          <StatusBadge status={outcome.status} />
          <h2>{outcome.title}</h2>
          <p>{outcome.reason}</p>
          <p className="outcome-card__next"><strong>Next recommended action:</strong> {outcome.nextAction}</p>
        </div>
        <Link className="button button--primary" to={outcome.actionPath}>{outcome.actionLabel}</Link>
      </section>

      <section className="kpi-grid" aria-label="Bundle overview KPIs">
        <KpiCard label="Overall Status" value={<StatusBadge status={summary.data?.bundle_status ?? (bundle.data ? bundleStatus(bundle.data) : null)} />} tone="info" />
        <KpiCard label="Documents uploaded" value={`${docList.length}/5`} helper={`${slots.filter((slot) => !slot.document).length} missing`} />
        <KpiCard label="Extraction progress" value={`${extraction.extracted}/${Math.max(extraction.total, 5)}`} helper={extraction.pending ? 'Extraction Pending' : 'Extracted'} tone={extraction.pending ? 'warning' : 'success'} />
        <KpiCard label="Review checks" value={verification.total} helper={`${verification.mismatches} mismatches`} tone={verification.mismatches ? 'danger' : 'success'} />
        <KpiCard label="Extraction confidence" value={extraction.confidenceAverage === null ? '-' : `${extraction.confidenceAverage}%`} helper="Average if available" />
      </section>

      <div className="content-grid content-grid--two">
        <section className="panel">
          <div className="section-header">
            <h2>Document Inventory</h2>
            <Link className="button button--ghost" to={`/bundles/${bundleId}/documents`}>Manage Documents</Link>
          </div>
          <div className="document-inventory-list">
            {slots.map((slot) => (
              <article key={slot.type} className="document-inventory-item">
                <div>
                  <strong>{slot.label}</strong>
                  <span className="muted">{slot.document?.filename ?? 'Not uploaded'}</span>
                </div>
                <div className="status-dimensions status-dimensions--compact">
                  <span><b>Document</b>{documentUploadStatus(slot.document)}</span>
                  <span><b>Extraction</b>{documentExtractionStatus(slot.document)}</span>
                  <span><b>Review</b>{documentReviewStatus(slot.document)}</span>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="panel">
          <h2>Next Action</h2>
          {nextAction ? (
            <>
              <span className={`severity-pill severity-pill--${nextAction.severity.toLowerCase()}`}>{nextAction.severity}</span>
              <h3>{nextAction.title}</h3>
              <p>{nextAction.message}</p>
              <Link className="button button--primary" to={nextAction.actionPath}>{nextAction.actionLabel}</Link>
            </>
          ) : (
            <EmptyState title="No immediate issues">Review verification details or export the current report.</EmptyState>
          )}
        </aside>
      </div>

      <section className="panel">
        <div className="section-header">
          <h2>Review Results</h2>
          <Link className="button button--ghost" to={`/bundles/${bundleId}/verification`}>View Review Results</Link>
        </div>
        {summary.data ? (
          <div className="summary-strip">
            <div><span>Customer side</span><StatusBadge status={summary.data.customer_delivery_status} /></div>
            <div><span>Vendor side</span><StatusBadge status={summary.data.vendor_procurement_status} /></div>
            <div><span>Recommendation</span><strong>{summary.data.recommendation || '-'}</strong></div>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Open Issues</h2>
          <Link className="button button--ghost" to={`/bundles/${bundleId}/issues`}>View Open Issues</Link>
        </div>
        {topIssues(summary.data, docList).length ? (
          <ul className="issue-list">
            {topIssues(summary.data, docList).map((issue) => (
              <li key={issue.id}>
                <strong>{issue.title}</strong>
                <span>{issue.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No open issues found">Verification Passed for the current checks.</EmptyState>
        )}
      </section>

      <section className="panel">
        <div className="section-header">
          <h2>Manual Correction History</h2>
          <Link className="button button--ghost" to={`/bundles/${bundleId}/audit`}>View Manual Corrections</Link>
        </div>
        {(audit.data ?? []).slice(0, 3).map((event) => (
          <p key={event.id}>{formatDateTime(event.created_at)} - {identifierLabel(event.event_type).replace('Manual Extracted Data Patched', 'Manual Correction')} - {formatValue(event.payload?.reason)}</p>
        ))}
        {!audit.isLoading && (audit.data ?? []).length === 0 ? <p className="muted">No manual corrections recorded.</p> : null}
      </section>
    </AppShell>
  );
}
