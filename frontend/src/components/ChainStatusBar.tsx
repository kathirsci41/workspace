import clsx from 'clsx';
import type { ChainSlot } from '@/types';
import { CHAIN_ORDER, DOC_TYPE_SHORT } from '@/types';

interface Props {
  chain: Record<string, ChainSlot[]>;
}

/** Pick the representative status for a doc-type slot list */
function pickStatus(slots: ChainSlot[]): string {
  if (slots.length === 0) return 'empty';
  // Priority: VERIFIED > PENDING_REVIEW > EXTRACTING > UPLOADED > EXTRACTION_FAILED/REJECTED
  if (slots.some((s) => s.status === 'VERIFIED')) return 'VERIFIED';
  if (slots.some((s) => s.status === 'PENDING_REVIEW')) return 'PENDING_REVIEW';
  if (slots.some((s) => s.status === 'EXTRACTING')) return 'EXTRACTING';
  if (slots.some((s) => s.status === 'UPLOADED')) return 'UPLOADED';
  return slots[0].status; // fallback to latest
}

/** Pick the best confidence from verified/reviewed docs, else latest */
function pickConfidence(slots: ChainSlot[]): number | null {
  const verified = slots.filter((s) => s.status === 'VERIFIED' && s.confidence != null);
  if (verified.length > 0) return Math.max(...verified.map((s) => s.confidence!));
  return slots[0]?.confidence ?? null;
}

export default function ChainStatusBar({ chain }: Props) {

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between">
        {CHAIN_ORDER.map((docType, idx) => {
          const slots = chain[docType] ?? [];
          const status = pickStatus(slots);
          const confidence = pickConfidence(slots);
          const isLast = idx === CHAIN_ORDER.length - 1;

          return (
            <div key={docType} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                {/* Circle */}
                <div className="relative">
                  <div
                    className={clsx(
                      'w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border-2',
                      status === 'VERIFIED' &&
                        'bg-green-500 border-green-500 text-white',
                      status === 'PENDING_REVIEW' &&
                        'bg-amber-400 border-amber-400 text-white',
                      status === 'EXTRACTING' &&
                        'bg-blue-500 border-blue-500 text-white animate-pulse',
                      (status === 'EXTRACTION_FAILED' ||
                        status === 'REJECTED') &&
                        'bg-red-500 border-red-500 text-white',
                      status === 'UPLOADED' &&
                        'bg-blue-300 border-blue-300 text-white',
                      status === 'empty' &&
                        'bg-white border-gray-300 text-gray-400'
                    )}
                  >
                    {status === 'VERIFIED'
                      ? '\u2713'
                      : status === 'PENDING_REVIEW'
                        ? '!'
                        : status === 'EXTRACTING'
                          ? '\u25CF'
                          : status === 'EXTRACTION_FAILED' ||
                              status === 'REJECTED'
                            ? '\u2717'
                            : status === 'UPLOADED'
                              ? '\u2191'
                              : '\u25CB'}
                  </div>
                  {/* Count badge when multiple docs */}
                  {slots.length > 1 && (
                    <span className="absolute -top-1.5 -right-1.5 bg-gray-700 text-white text-[9px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                      {slots.length}
                    </span>
                  )}
                </div>
                {/* Label */}
                <span className="text-[10px] text-gray-500 mt-1 font-medium">
                  {DOC_TYPE_SHORT[docType]}
                </span>
                {/* Confidence */}
                <span className="text-[10px] text-gray-400">
                  {confidence != null ? `${confidence}%` : '\u00A0'}
                </span>
              </div>
              {/* Connector line */}
              {!isLast && (
                <div
                  className={clsx(
                    'flex-1 h-0.5 mx-1',
                    status !== 'empty' ? 'bg-green-300' : 'bg-gray-200'
                  )}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
