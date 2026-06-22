import { Link } from 'react-router-dom';
import { DataTable } from '../common/DataTable';
import { StatusBadge } from '../common/StatusBadge';
import { checkDisplayName, checkExplanation, checkImpactLabel, documentLabel, identifierLabel } from '../../lib/build1';
import { formatValue } from '../../lib/format';
import type { VerificationCheck } from '../../types/api';

export function VerificationChecksTable({
  bundleId,
  checks,
  selectedCheckId,
  onSelect,
}: {
  bundleId: string;
  checks: VerificationCheck[];
  selectedCheckId: string | null;
  onSelect: (check: VerificationCheck) => void;
}) {
  return (
    <DataTable label="Review checks" className="verification-table">
      <thead>
        <tr>
          <th>Review check</th>
          <th>Expected</th>
          <th>Found</th>
          <th>Status</th>
          <th>Impact if failed</th>
          <th>Action</th>
        </tr>
      </thead>
      <tbody>
        {checks.map((check, index) => (
          <tr key={checkRowKey(check, index)} className={selectedCheckId === check.check_id ? 'is-selected' : undefined}>
            <td>
              <button className="link-button" type="button" onClick={() => onSelect(check)}>
                {checkDisplayName(check)}
              </button>
              {check.result !== 'PASS' ? <span className="muted">{checkExplanation(check)}</span> : null}
            </td>
            <td>
              <span className="value-cell">{formatValue(check.left_value, check.check_id)}</span>
              <span className="muted">{documentLabel(check.left_document_type)}</span>
            </td>
            <td>
              <span className="value-cell">{formatValue(check.right_value, check.check_id)}</span>
              <span className="muted">{documentLabel(check.right_document_type)}</span>
            </td>
            <td><StatusBadge status={check.result} label={compactResultLabel(check.result)} /></td>
            <td className="verification-severity">{checkImpactLabel(check)}</td>
            <td>
              {check.left_document_id || check.right_document_id ? (
                <Link className="button button--ghost" to={`/bundles/${bundleId}/extraction/${check.left_document_id ?? check.right_document_id}`}>
                  Review
                </Link>
              ) : (
                <Link className="button button--ghost" to={`/bundles/${bundleId}/documents`}>Upload</Link>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}

function checkRowKey(check: VerificationCheck, index: number): string {
  return [
    check.check_id,
    check.left_document_id ?? 'no-left-document',
    check.right_document_id ?? 'no-right-document',
    index,
  ].join(':');
}

function compactResultLabel(result: string): string {
  if (result === 'PASS') return 'Passed';
  if (result === 'MISSING_DOCUMENTS') return 'Missing Data';
  if (['REVIEW_REQUIRED', 'PARTIAL_PASS', 'BLOCKED'].includes(result)) return 'Needs Review';
  return identifierLabel(result);
}
