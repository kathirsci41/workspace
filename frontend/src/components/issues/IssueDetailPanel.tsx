import { Link } from 'react-router-dom';
import type { DerivedIssue } from '../../lib/build1';

export function IssueDetailPanel({
  issue,
  isDismissed = false,
  isDismissing = false,
  onDismiss,
  onUndismiss,
}: {
  issue: DerivedIssue | null;
  isDismissed?: boolean;
  isDismissing?: boolean;
  onDismiss?: (issue: DerivedIssue) => void;
  onUndismiss?: (issue: DerivedIssue) => void;
}) {
  return (
    <aside className="detail-panel" aria-label="Issue detail">
      <h2>Issue Detail</h2>
      {issue ? (
        <>
          <div className="issue-detail__header">
            <span className={`severity-pill severity-pill--${issue.severity.toLowerCase()}`}>{issue.severity}</span>
            {isDismissed && <span className="status-badge status-badge--neutral">Dismissed</span>}
          </div>
          <h3>{issue.title}</h3>
          <p>{issue.message}</p>
          <dl className="detail-list">
            <div>
              <dt>Why it matters</dt>
              <dd>{issue.whyItMatters}</dd>
            </div>
            <div>
              <dt>Expected</dt>
              <dd>{issue.expectedLabel}</dd>
            </div>
            <div>
              <dt>Found</dt>
              <dd>{issue.foundLabel}</dd>
            </div>
            <div>
              <dt>Difference</dt>
              <dd>{issue.differenceLabel}</dd>
            </div>
            <div>
              <dt>Recommended action</dt>
              <dd>{issue.recommendedAction}</dd>
            </div>
            <div>
              <dt>Related documents</dt>
              <dd>{issue.relatedDocuments.join(', ') || '-'}</dd>
            </div>
          </dl>
          <div className="button-row">
            <Link className="button button--primary" to={issue.actionPath}>{issue.actionLabel}</Link>
            {isDismissed ? (
              <button type="button" className="button button--ghost" disabled={isDismissing} onClick={() => onUndismiss?.(issue)}>
                {isDismissing ? 'Restoring…' : 'Restore Issue'}
              </button>
            ) : (
              <button type="button" className="button button--ghost" disabled={isDismissing} onClick={() => onDismiss?.(issue)}>
                {isDismissing ? 'Dismissing…' : 'Dismiss'}
              </button>
            )}
          </div>
        </>
      ) : (
        <p className="muted">Select an issue to review details.</p>
      )}
    </aside>
  );
}
