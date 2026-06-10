import { Link } from 'react-router-dom';
import type { DerivedIssue } from '../../lib/build1';

export function IssueDetailPanel({ issue }: { issue: DerivedIssue | null }) {
  return (
    <aside className="detail-panel" aria-label="Issue detail">
      <h2>Issue Detail</h2>
      {issue ? (
        <>
          <span className={`severity-pill severity-pill--${issue.severity.toLowerCase()}`}>{issue.severity}</span>
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
          <Link className="button button--primary" to={issue.actionPath}>{issue.actionLabel}</Link>
        </>
      ) : (
        <p className="muted">Select an issue to review details.</p>
      )}
    </aside>
  );
}
