import { buildDocumentSlots, deriveIssues, extractionProgress, verificationMetrics } from '../../lib/build1';
import type { BundleDocument, VerificationSummary } from '../../types/api';
import { StatusBadge } from '../common/StatusBadge';

export function ExportReadinessPanel({
  documents,
  summary,
}: {
  documents: BundleDocument[];
  summary: VerificationSummary | null;
}) {
  const slots = buildDocumentSlots(documents);
  const extraction = extractionProgress(documents);
  const verification = verificationMetrics(summary);
  const issues = deriveIssues(summary, documents);
  const unresolvedIssues = issues.length;

  return (
    <section className="panel" aria-label="Export readiness">
      <div className="section-header">
        <div>
          <h2>Export Readiness</h2>
          <p>{unresolvedIssues > 0 ? 'The report can be downloaded, but open review items will be included.' : 'Ready to download with the current review results.'}</p>
        </div>
        <StatusBadge status={unresolvedIssues > 0 ? 'REVIEW_REQUIRED' : 'PASS'} />
      </div>
      <div className="checklist-grid">
        <div>
          <h3>Document completeness</h3>
          <ul className="checklist">
            {slots.map((slot) => <li key={slot.type}>{slot.label}: {slot.document ? 'Uploaded' : 'Missing Document'}</li>)}
          </ul>
        </div>
        <div>
          <h3>Extraction completeness</h3>
          <ul className="checklist">
            <li>Extracted: {extraction.extracted}</li>
            <li>Extraction Pending: {extraction.pending}</li>
            <li>Failed: {extraction.failed}</li>
          </ul>
        </div>
        <div>
          <h3>Open Issues</h3>
          <ul className="checklist">
            <li>Open issues: {unresolvedIssues}</li>
            <li>Mismatches: {verification.mismatches}</li>
            <li>Missing data: {verification.missingData}</li>
          </ul>
        </div>
      </div>
    </section>
  );
}
