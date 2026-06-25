import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { useMemo, useState } from 'react';
import { getBundle } from '../api/bundles';
import { getVerificationSummary } from '../api/verification';
import { ErrorState } from '../components/common/ErrorState';
import { KpiCard } from '../components/common/KpiCard';
import { LoadingState } from '../components/common/LoadingState';
import { StatusBadge } from '../components/common/StatusBadge';
import { AppShell } from '../components/layout/AppShell';
import { WorkflowTabs } from '../components/layout/WorkflowTabs';
import { VerificationChecksTable } from '../components/verification/VerificationChecksTable';
import { useAsyncResource } from '../hooks/useAsyncResource';
import { checkCategory, checkDisplayMessage, checkDisplayName, checkExplanation, checkImpactLabel, documentLabel, verificationMetrics, type CheckFilter } from '../lib/build1';
import { formatValue } from '../lib/format';
import type { OrderBundle, VerificationCheck, VerificationSummary } from '../types/api';

const filters: CheckFilter[] = ['All', 'Customer Side', 'Vendor Side', 'Amounts', 'References'];
const groupOrder: CheckFilter[] = ['Customer Side', 'Vendor Side', 'References', 'Amounts'];

export function VerificationPage() {
  const { bundleId } = useParams<{ bundleId: string }>();
  if (!bundleId) return <Navigate to="/bundles" replace />;
  return <VerificationContent bundleId={bundleId} />;
}

function VerificationContent({ bundleId }: { bundleId: string }) {
  const [searchParams] = useSearchParams();
  const bundle = useAsyncResource<OrderBundle>(() => getBundle(bundleId), [bundleId]);
  const summary = useAsyncResource<VerificationSummary>(() => getVerificationSummary(bundleId), [bundleId]);
  const [filter, setFilter] = useState<CheckFilter>('All');
  const metrics = verificationMetrics(summary.data);
  const checks = useMemo(() => {
    return (summary.data?.checks ?? []).filter((check) => filter === 'All' || checkCategory(check) === filter);
  }, [summary.data, filter]);
  const groupedChecks = useMemo(() => {
    return groupOrder
      .map((group) => ({ group, checks: checks.filter((check) => checkCategory(check) === group) }))
      .filter((group) => group.checks.length > 0);
  }, [checks]);
  const initialCheck = searchParams.get('check');
  const [selectedCheck, setSelectedCheck] = useState<VerificationCheck | null>(null);
  const activeCheck = selectedCheck
    ?? checks.find((check) => check.check_id === initialCheck)
    ?? firstIssueRelatedCheck(checks, summary.data)
    ?? checks.find((check) => check.result !== 'PASS')
    ?? checks[0]
    ?? null;
  const activeCheckPassed = activeCheck?.result === 'PASS';

  return (
    <AppShell
      bundleId={bundleId}
      title="Review Results"
      subtitle={bundle.data?.bundle_number ?? 'Cross-document comparison results.'}
      breadcrumbs={[{ label: 'Orders', href: '/bundles' }, { label: bundle.data?.bundle_number ?? bundleId, href: `/bundles/${bundleId}/overview` }, { label: 'Review Results' }]}
      actions={(
        <button
          className="button button--ghost"
          type="button"
          disabled={summary.isLoading}
          onClick={() => { void summary.reload(); }}
        >
          {summary.isLoading ? 'Refreshing…' : 'Refresh Results'}
        </button>
      )}
    >
      <WorkflowTabs bundleId={bundleId} />
      <ErrorState message={bundle.error ?? summary.error} />
      {summary.isLoading ? <LoadingState label="Loading verification checks..." /> : null}

      <section className="kpi-grid" aria-label="Review result KPIs">
        <KpiCard label="Total Checks" value={metrics.total} />
        <KpiCard label="Passed" value={metrics.passed} tone="success" />
        <KpiCard label="Mismatches" value={metrics.mismatches} tone="danger" />
        <KpiCard label="Missing Data" value={metrics.missingData} tone="danger" />
        <KpiCard label="Not Checked" value={metrics.notChecked} tone="warning" />
      </section>

      <section className="panel">
        <div className="segmented-control" role="tablist" aria-label="Review category filters">
          {filters.map((item) => (
            <button key={item} type="button" className={filter === item ? 'active' : ''} onClick={() => setFilter(item)}>{item}</button>
          ))}
        </div>
      </section>

      <div className="content-grid content-grid--detail verification-layout">
        <section className="panel">
          {filter === 'All' ? groupedChecks.map((group) => (
            <section className="verification-check-group" key={group.group} aria-label={group.group}>
              <h2>{group.group}</h2>
              <VerificationChecksTable bundleId={bundleId} checks={group.checks} selectedCheckId={activeCheck?.check_id ?? null} onSelect={setSelectedCheck} />
            </section>
          )) : (
            <VerificationChecksTable bundleId={bundleId} checks={checks} selectedCheckId={activeCheck?.check_id ?? null} onSelect={setSelectedCheck} />
          )}
        </section>
        <aside className="detail-panel" aria-label="Review check detail">
          <h2>Check Detail</h2>
          {activeCheck ? (
            <>
              <StatusBadge status={activeCheck.result} />
              <h3>{checkDisplayName(activeCheck)}</h3>
              <p>{checkDisplayMessage(activeCheck)}</p>
              <dl className="detail-list">
                <div>
                  <dt>Expected value/source</dt>
                  <dd>{formatValue(activeCheck.left_value, activeCheck.check_id)} from {documentLabel(activeCheck.left_document_type)}</dd>
                </div>
                <div>
                  <dt>Found value/source</dt>
                  <dd>{formatValue(activeCheck.right_value, activeCheck.check_id)} from {documentLabel(activeCheck.right_document_type)}</dd>
                </div>
                {!activeCheckPassed ? (
                  <div>
                    <dt>Impact if failed</dt>
                    <dd>{checkImpactLabel(activeCheck)}</dd>
                  </div>
                ) : null}
                <div>
                  <dt>{activeCheckPassed ? 'Result explanation' : 'What differs'}</dt>
                  <dd>{checkExplanation(activeCheck)}</dd>
                </div>
              </dl>
              <div className="button-row">
                {activeCheck.left_document_id ? <Link className="button button--ghost" to={`/bundles/${bundleId}/extraction/${activeCheck.left_document_id}`}>Review {documentLabel(activeCheck.left_document_type)}</Link> : null}
                {activeCheck.right_document_id ? <Link className="button button--ghost" to={`/bundles/${bundleId}/extraction/${activeCheck.right_document_id}`}>Review {documentLabel(activeCheck.right_document_type)}</Link> : null}
              </div>
              <details className="technical-details">
                <summary>Technical Details</summary>
                <dl className="detail-list">
                  <div>
                    <dt>Rule ID</dt>
                    <dd>{activeCheck.check_id}</dd>
                  </div>
                </dl>
              </details>
            </>
          ) : (
            <p className="muted">No verification checks returned.</p>
          )}
        </aside>
      </div>
    </AppShell>
  );
}

function firstIssueRelatedCheck(checks: VerificationCheck[], summary: VerificationSummary | null | undefined): VerificationCheck | null {
  const issueDocumentIds = new Set((summary?.issues ?? [])
    .map((issue) => typeof issue.document_id === 'string' ? issue.document_id : null)
    .filter((value): value is string => Boolean(value)));
  if (issueDocumentIds.size === 0) return null;
  return checks.find((check) => (
    check.result !== 'PASS'
    && (issueDocumentIds.has(String(check.left_document_id)) || issueDocumentIds.has(String(check.right_document_id)))
  )) ?? null;
}
