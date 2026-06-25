import { Navigate, useParams } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { dismissCheck, getBundle, undismissCheck } from '../api/bundles';
import { listBundleDocuments } from '../api/documents';
import { getVerificationSummary } from '../api/verification';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { IssueDetailPanel } from '../components/issues/IssueDetailPanel';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { deriveIssues, documentLabel, type DerivedIssue, type IssueSeverity } from '../lib/build1';
import type { BundleDocument, OrderBundle, VerificationSummary } from '../types/api';

type SeverityFilter = 'All' | IssueSeverity;
type StatusFilter = 'open' | 'dismissed' | 'all';

export function IssuesPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <IssuesContent bundleId={bundleId} />;
}

function IssuesContent({ bundleId }: { bundleId: string }) {
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const documents = useAsyncResource<BundleDocument[]>(() => listBundleDocuments(bundleId), [bundleId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const issues = deriveIssues(summary.data, documents.data ?? [], bundleId);
  const [severity, setSeverity] = useState<SeverityFilter>('All');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('open');
  const [documentType, setDocumentType] = useState('All');
  const [category, setCategory] = useState('All');
  const [selectedIssue, setSelectedIssue] = useState<DerivedIssue | null>(null);
  const [isDismissing, setIsDismissing] = useState(false);
  const [dismissError, setDismissError] = useState<string | null>(null);

  const dismissedIds = bundle.data?.dismissed_check_ids ?? [];

  const visibleIssues = useMemo(() => issues.filter((issue) => {
    const dismissed = dismissedIds.includes(issue.id);
    const matchesStatus =
      statusFilter === 'all'
      || (statusFilter === 'open' && !dismissed)
      || (statusFilter === 'dismissed' && dismissed);
    return (
      matchesStatus
      && (severity === 'All' || issue.severity === severity)
      && (documentType === 'All' || issue.documentType === documentType)
      && (category === 'All' || issue.category === category)
    );
  }), [issues, severity, statusFilter, documentType, category, dismissedIds]);

  const activeIssue = selectedIssue ?? visibleIssues[0] ?? null;
  const documentTypes = Array.from(new Set(issues.map((issue) => issue.documentType).filter(Boolean))) as string[];
  const categories = Array.from(new Set(issues.map((issue) => issue.category)));
  const openCount = issues.filter((i) => !dismissedIds.includes(i.id)).length;
  const dismissedCount = dismissedIds.length;

  async function handleDismiss(issue: DerivedIssue) {
    setIsDismissing(true);
    setDismissError(null);
    try {
      await dismissCheck(bundleId, issue.id);
      await bundle.reload();
      if (selectedIssue?.id === issue.id) setSelectedIssue(null);
    } catch (err) {
      setDismissError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsDismissing(false);
    }
  }

  async function handleUndismiss(issue: DerivedIssue) {
    setIsDismissing(true);
    setDismissError(null);
    try {
      await undismissCheck(bundleId, issue.id);
      await bundle.reload();
    } catch (err) {
      setDismissError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsDismissing(false);
    }
  }

  return (
    <AppShell
      bundleId={bundleId}
      title="Open Issues"
      subtitle={bundle.data?.bundle_number ?? 'Action queue for items that need review.'}
      breadcrumbs={[{ label: 'Orders', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Open Issues' }]}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? documents.error ?? summary.error ?? dismissError} />
      {documents.isLoading || summary.isLoading ? <LoadingState label="Loading issues..." /> : null}

      <section className="kpi-grid" aria-label="Issue KPIs">
        <KpiCard label="Total Issues" value={issues.length} tone={issues.length ? 'danger' : 'success'} />
        <KpiCard label="Open" value={openCount} tone={openCount ? 'danger' : 'success'} />
        <KpiCard label="Dismissed" value={dismissedCount} tone={dismissedCount ? 'warning' : 'neutral'} />
        <KpiCard label="Critical" value={issues.filter((issue) => issue.severity === 'Critical').length} tone="danger" />
      </section>

      <section className="panel">
        <div className="controls-row">
          <label>
            Status
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}>
              <option value="open">Open</option>
              <option value="dismissed">Dismissed</option>
              <option value="all">All</option>
            </select>
          </label>
          <label>
            Severity
            <select value={severity} onChange={(event) => setSeverity(event.target.value as SeverityFilter)}>
              <option>All</option>
              <option>Critical</option>
              <option>Warning</option>
              <option>Info</option>
            </select>
          </label>
          <label>
            Document
            <select value={documentType} onChange={(event) => setDocumentType(event.target.value)}>
              <option>All</option>
              {documentTypes.map((type) => <option key={type} value={type}>{documentLabel(type)}</option>)}
            </select>
          </label>
          <label>
            Category
            <select value={category} onChange={(event) => setCategory(event.target.value)}>
              <option>All</option>
              {categories.map((item) => <option key={item}>{item}</option>)}
            </select>
          </label>
        </div>
      </section>

      <div className="content-grid content-grid--detail issues-layout">
        <section className="panel">
          <div className="section-header">
            <div>
              <h2>Action Queue</h2>
              <p className="muted">{visibleIssues.length} item{visibleIssues.length === 1 ? '' : 's'} in this view.</p>
            </div>
          </div>
          <div className="issue-card-list">
            {visibleIssues.map((issue) => {
              const dismissed = dismissedIds.includes(issue.id);
              return (
                <button
                  key={issue.id}
                  type="button"
                  className={`issue-card ${activeIssue?.id === issue.id ? 'is-selected' : ''} ${dismissed ? 'is-dismissed' : ''}`}
                  onClick={() => setSelectedIssue(issue)}
                >
                  <span className={`severity-pill severity-pill--${issue.severity.toLowerCase()}`}>{issue.severity}</span>
                  {dismissed && <span className="issue-card__dismissed-tag">Dismissed</span>}
                  <strong>{issue.title}</strong>
                  <span>{issue.message}</span>
                  <span className="muted">{issue.relatedDocuments.join(', ') || documentLabel(issue.documentType)}</span>
                </button>
              );
            })}
            {visibleIssues.length === 0 ? <p className="muted">No issues match the selected filters.</p> : null}
          </div>
        </section>
        <IssueDetailPanel
          issue={activeIssue}
          isDismissed={activeIssue ? dismissedIds.includes(activeIssue.id) : false}
          isDismissing={isDismissing}
          onDismiss={handleDismiss}
          onUndismiss={handleUndismiss}
        />
      </div>
    </AppShell>
  );
}
