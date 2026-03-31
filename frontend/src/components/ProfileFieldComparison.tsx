import { CheckCircle2, XCircle, MinusCircle } from 'lucide-react';
import type { FieldComparison } from '@/types';

interface Props {
  comparisons: FieldComparison[];
}

function MatchIcon({ match }: { match: boolean | null }) {
  if (match === true)  return <CheckCircle2 size={15} className="text-green-500 shrink-0 mt-0.5" />;
  if (match === false) return <XCircle       size={15} className="text-red-500   shrink-0 mt-0.5" />;
  return               <MinusCircle          size={15} className="text-gray-300   shrink-0 mt-0.5" />;
}

function docLabel(raw: string) {
  return raw.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ProfileFieldComparison({ comparisons }: Props) {
  if (!comparisons || comparisons.length === 0) return null;

  const mismatches = comparisons.filter((c) => c.match === false).length;
  const matches    = comparisons.filter((c) => c.match === true).length;
  const pending    = comparisons.filter((c) => c.match === null).length;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
          Cross-Document Field Comparison
        </h3>
        <div className="flex items-center gap-3 text-xs">
          {matches > 0 && (
            <span className="flex items-center gap-1 text-green-600">
              <CheckCircle2 size={12} /> {matches} match
            </span>
          )}
          {mismatches > 0 && (
            <span className="flex items-center gap-1 text-red-600">
              <XCircle size={12} /> {mismatches} mismatch
            </span>
          )}
          {pending > 0 && (
            <span className="flex items-center gap-1 text-gray-400">
              <MinusCircle size={12} /> {pending} pending
            </span>
          )}
        </div>
      </div>

      <div className="divide-y divide-gray-50">
        {comparisons.map((fc, i) => (
          <div key={i} className="py-2.5 flex items-start gap-2.5">
            <MatchIcon match={fc.match} />
            <div className="flex-1 min-w-0 space-y-1">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-medium text-gray-700">{fc.field_label}</span>
                {fc.note && (
                  <span className="text-xs text-gray-400">({fc.note})</span>
                )}
              </div>
              <div className="grid grid-cols-2 gap-x-4 text-xs">
                <div className="min-w-0">
                  <span className="text-gray-400">{docLabel(fc.source_doc)}: </span>
                  <span className={`font-mono ${fc.source_value ? 'text-gray-700' : 'text-gray-300 italic'}`}>
                    {fc.source_value ?? 'not found'}
                  </span>
                </div>
                <div className="min-w-0">
                  <span className="text-gray-400">{docLabel(fc.compared_doc)}: </span>
                  <span className={`font-mono ${fc.compared_value ? (fc.match === false ? 'text-red-600' : 'text-gray-700') : 'text-gray-300 italic'}`}>
                    {fc.compared_value ?? 'not found'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
