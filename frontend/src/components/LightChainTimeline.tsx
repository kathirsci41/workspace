import { CHAIN_ORDER, DOC_TYPE_LABELS } from '@/types';
import type { ChainSlot } from '@/types';
import clsx from 'clsx';

interface Props {
  chain: Record<string, ChainSlot[]>;
  missingSlots: string[];
  referenceChecks: Array<{ document_type: string; result: string }>;
}

function slotState(
  docType: string,
  slots: ChainSlot[],
  missing: string[],
  refChecks: Array<{ document_type: string; result: string }>,
): 'verified' | 'missing' | 'pending' | 'mismatch' | 'extracting' {
  if (missing.includes(docType)) return 'missing';
  const slot = slots[0];
  if (!slot || !slot.document_id) return 'missing';
  if (slot.status === 'EXTRACTING' || slot.status === 'UPLOADED') return 'extracting';
  if (refChecks.some(r => r.document_type === docType && r.result === 'mismatch')) return 'mismatch';
  if (slot.status === 'PENDING_REVIEW') return 'pending';
  return 'verified';
}

const STATE: Record<string, { icon: string; borderClass: string; labelClass: string; statusText: string }> = {
  verified:   { icon: '✓', borderClass: 'border-green-400',                    labelClass: 'text-green-700', statusText: 'Verified'    },
  missing:    { icon: '—', borderClass: 'border-[--veil] border-dashed',        labelClass: 'text-gray-400',  statusText: 'Missing'     },
  pending:    { icon: '!', borderClass: 'border-amber-400',                     labelClass: 'text-amber-700', statusText: 'Review'      },
  mismatch:   { icon: '✗', borderClass: 'border-red-400',                       labelClass: 'text-red-700',   statusText: 'Mismatch'    },
  extracting: { icon: '⟳', borderClass: 'border-blue-400',                      labelClass: 'text-blue-700',  statusText: 'Extracting…' },
};

export function LightChainTimeline({ chain, missingSlots, referenceChecks }: Props) {
  return (
    <div className="grid grid-cols-6 gap-2">
      {CHAIN_ORDER.map((docType, i) => {
        const slots = chain[docType] ?? [];
        const state = slotState(docType, slots, missingSlots, referenceChecks);
        const cfg = STATE[state];
        const ref = slots[0]?.ref_no ?? null;

        return (
          <div key={docType} className="flex items-center gap-1">
            <div
              className={clsx(
                'flex-1 rounded-lg border bg-white p-2.5',
                cfg.borderClass,
                state === 'missing' && 'bg-gray-50',
              )}
            >
              <div className={clsx('text-xs font-bold', cfg.labelClass)}>{cfg.icon}</div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-gray-500 mt-1 leading-tight">
                {DOC_TYPE_LABELS[docType] ?? docType}
              </div>
              {ref && (
                <div className="font-mono text-[9px] text-gray-600 mt-0.5 truncate" title={ref}>
                  {ref}
                </div>
              )}
              <div className={clsx('text-[9px] font-semibold mt-1', cfg.labelClass)}>
                {cfg.statusText}
              </div>
            </div>
            {i < CHAIN_ORDER.length - 1 && (
              <span className="text-gray-300 text-xs flex-shrink-0">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
