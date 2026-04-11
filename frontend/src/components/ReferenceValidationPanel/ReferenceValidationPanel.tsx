interface Check {
  document_type: string;
  check: string;
  result: 'pass' | 'mismatch' | 'skip';
  extracted?: string;
  expected?: string;
}

interface Props {
  checks: Check[];
}

const CHECK_LABELS: Record<string, string> = {
  so_consistency: 'SO number match',
  cpo_reference:  'CPO reference match',
  vpo_reference:  'VPO reference match',
};

const RESULT_ICON: Record<string, string> = {
  pass: 'PASS',
  mismatch: 'FAIL',
  skip: 'SKIP',
};

const RESULT_CLASS: Record<string, string> = {
  pass:     'text-green-400',
  mismatch: 'text-red-400',
  skip:     'text-slate-500',
};

export function ReferenceValidationPanel({ checks }: Props) {
  if (!checks.length) {
    return <p className="text-xs text-slate-500">No documents to validate yet.</p>;
  }
  return (
    <div className="flex flex-col divide-y divide-slate-800">
      {checks.map((c, i) => (
        <div key={i} className="flex items-start gap-3 py-2">
          <span className="text-sm mt-0.5 flex-shrink-0">{RESULT_ICON[c.result] ?? '?'}</span>
          <div>
            <p className="text-xs font-medium text-slate-200">
              {c.document_type.replace(/_/g, ' ')} - {CHECK_LABELS[c.check] ?? c.check}
            </p>
            {c.extracted != null && c.expected != null && (
              <p className="text-xs text-slate-500">
                extracted: '{c.extracted}'  expected: '{c.expected}'
              </p>
            )}
            <p className={`text-xs ${RESULT_CLASS[c.result] ?? 'text-slate-400'}`}>
              {c.result.toUpperCase()}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
