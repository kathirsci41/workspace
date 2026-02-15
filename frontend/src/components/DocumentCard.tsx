import clsx from 'clsx';
import { FileText, Upload, RotateCcw, Eye, ClipboardCheck } from 'lucide-react';
import type { ChainSlot, DocumentType } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';

interface Props {
  documentType: DocumentType;
  slot: ChainSlot | null;
  isSelected: boolean;
  onSelect: (documentId: string) => void;
  onUpload: () => void;
  onReview: (documentId: string) => void;
  onReExtract: (documentId: string) => void;
}

export default function DocumentCard({
  documentType,
  slot,
  isSelected,
  onSelect,
  onUpload,
  onReview,
  onReExtract,
}: Props) {
  const status = slot?.status ?? 'empty';

  const borderColor = {
    empty: 'border-gray-300',
    UPLOADED: 'border-blue-300',
    EXTRACTING: 'border-blue-400',
    PENDING_REVIEW: 'border-amber-400',
    VERIFIED: 'border-green-400',
    EXTRACTION_FAILED: 'border-red-400',
    REJECTED: 'border-red-400',
  }[status] ?? 'border-gray-300';

  return (
    <div
      className={clsx(
        'rounded-lg border-2 p-4 transition-all cursor-pointer',
        borderColor,
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        status !== 'empty' && 'hover:shadow-sm'
      )}
      onClick={() => {
        if (slot?.document_id) onSelect(slot.document_id);
      }}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <FileText
            size={18}
            className={clsx(
              status === 'VERIFIED'
                ? 'text-green-600'
                : status === 'PENDING_REVIEW'
                  ? 'text-amber-600'
                  : status === 'EXTRACTING' || status === 'UPLOADED'
                    ? 'text-blue-600'
                    : status === 'EXTRACTION_FAILED' || status === 'REJECTED'
                      ? 'text-red-600'
                      : 'text-gray-400'
            )}
          />
          <span className="text-sm font-semibold">
            {DOC_TYPE_LABELS[documentType]}
          </span>
        </div>
        {/* Status icon */}
        {status === 'VERIFIED' && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            Verified
          </span>
        )}
        {status === 'PENDING_REVIEW' && (
          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
            Review
          </span>
        )}
        {status === 'EXTRACTING' && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium animate-pulse">
            Extracting
          </span>
        )}
        {(status === 'EXTRACTION_FAILED' || status === 'REJECTED') && (
          <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
            {status === 'REJECTED' ? 'Rejected' : 'Failed'}
          </span>
        )}
      </div>

      {/* Empty state */}
      {status === 'empty' && (
        <div className="text-center py-3">
          <p className="text-sm text-gray-400 mb-2">Not uploaded yet</p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUpload();
            }}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            <Upload size={14} />
            Upload Document
          </button>
        </div>
      )}

      {/* Extracting state */}
      {status === 'EXTRACTING' && (
        <div className="py-2">
          <p className="text-sm text-gray-500 mb-2">Processing...</p>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-[loading_1.5s_ease-in-out_infinite] w-1/2" />
          </div>
        </div>
      )}

      {/* Has data states */}
      {(status === 'PENDING_REVIEW' ||
        status === 'VERIFIED' ||
        status === 'UPLOADED') &&
        slot && (
          <div>
            <p className="text-sm font-mono text-gray-700 truncate">
              {slot.ref_number ?? slot.filename ?? '—'}
            </p>
            <div className="flex items-center gap-3 mt-1 text-xs text-gray-500">
              {slot.confidence != null && (
                <span
                  className={clsx(
                    'font-medium',
                    slot.confidence >= 80
                      ? 'text-green-600'
                      : slot.confidence >= 50
                        ? 'text-amber-600'
                        : 'text-red-600'
                  )}
                >
                  {slot.confidence}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (slot.document_id) onSelect(slot.document_id);
                }}
                className="inline-flex items-center gap-1 text-xs text-gray-600 hover:text-blue-600"
              >
                <Eye size={14} />
                Preview
              </button>
              {status === 'PENDING_REVIEW' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (slot.document_id) onReview(slot.document_id);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium"
                >
                  <ClipboardCheck size={14} />
                  Review
                </button>
              )}
              {(status === 'VERIFIED' || status === 'PENDING_REVIEW') && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (slot.document_id) onReExtract(slot.document_id);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600"
                >
                  <RotateCcw size={14} />
                  Re-extract
                </button>
              )}
            </div>
          </div>
        )}

      {/* Failed/Rejected state */}
      {(status === 'EXTRACTION_FAILED' || status === 'REJECTED') && slot && (
        <div>
          <p className="text-sm text-red-600 truncate">
            {status === 'REJECTED' ? 'Rejected by reviewer' : 'Extraction failed'}
          </p>
          <div className="mt-3">
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onReExtract(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              <RotateCcw size={14} />
              Re-extract
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
