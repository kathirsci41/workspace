import clsx from 'clsx';
import type { ChainSlot } from '@/types';
import { CHAIN_ORDER, DOC_TYPE_SHORT } from '@/types';

interface Props {
  chain: Record<string, ChainSlot | null>;
}

export default function ChainStatusBar({ chain }: Props) {

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5">
      <div className="flex items-center justify-between">
        {CHAIN_ORDER.map((docType, idx) => {
          const slot = chain[docType];
          const status = slot?.status ?? 'empty';
          const isLast = idx === CHAIN_ORDER.length - 1;

          return (
            <div key={docType} className="flex items-center flex-1">
              <div className="flex flex-col items-center">
                {/* Circle */}
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
                {/* Label */}
                <span className="text-[10px] text-gray-500 mt-1 font-medium">
                  {DOC_TYPE_SHORT[docType]}
                </span>
                {/* Confidence */}
                <span className="text-[10px] text-gray-400">
                  {slot?.confidence != null ? `${slot.confidence}%` : '\u00A0'}
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
