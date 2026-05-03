import { AlertTriangle, CheckCircle } from 'lucide-react';
import type { POProfileDiscrepancy } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';

interface Props {
  discrepancies: POProfileDiscrepancy[];
  crossReferences: Record<string, string[]>;
}

export function ProfileDiscrepancyPanel({ discrepancies, crossReferences }: Props) {
  const hasDiscrepancies = discrepancies.length > 0;
  const hasCrossRefs = Object.keys(crossReferences).length > 0;

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-700">Cross-Reference Check</h3>

      {/* Discrepancy list or all-clear */}
      {!hasDiscrepancies ? (
        <div className="flex items-center gap-2 bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-700">
          <CheckCircle size={15} className="shrink-0" />
          All references consistent
        </div>
      ) : (
        <div className="space-y-2">
          {discrepancies.map((d, idx) => {
            const docLabel = DOC_TYPE_LABELS[d.doc_type as keyof typeof DOC_TYPE_LABELS] ?? d.doc_type;
            const isError = d.severity === 'error';
            return (
              <div
                key={idx}
                className={`flex items-start gap-2 rounded-lg px-3 py-2 text-xs ${
                  isError
                    ? 'bg-red-50 border border-red-200 text-red-700'
                    : 'bg-amber-50 border border-amber-200 text-amber-700'
                }`}
              >
                <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                <span>
                  <span className="font-medium">{docLabel}</span> — {d.message}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Cross-reference map */}
      {hasCrossRefs && (
        <div>
          <p className="text-xs text-gray-500 font-medium mb-2">PO References Found</p>
          <div className="space-y-1">
            {Object.entries(crossReferences).map(([docType, refs]) => {
              const label = DOC_TYPE_LABELS[docType as keyof typeof DOC_TYPE_LABELS] ?? docType;
              return (
                <div key={docType} className="flex items-center gap-2 text-xs">
                  <span className="text-gray-500 w-32 shrink-0">{label}</span>
                  <span className="text-gray-800 font-mono">{refs.join(', ')}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
