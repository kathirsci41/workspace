import clsx from 'clsx';
import {
  FileText, Upload, RotateCcw, Eye, ClipboardCheck,
  Trash2, PenLine, Zap, Camera, AlertTriangle,
} from 'lucide-react';
import type { ChainSlot, DocumentType } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';
import { friendlyExtractionError } from '@/utils/extractionErrors';

interface Props {
  documentType: DocumentType;
  slot: ChainSlot | null;
  isSelected: boolean;
  onSelect: (documentId: string) => void;
  onUpload: () => void;
  onReview: (documentId: string) => void;
  onReExtract: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  onManualEntry: (documentId: string) => void;
  onEdit?: (documentId: string) => void;
  /** When false, hides the doc-type label (used for 2nd+ card in a multi-doc group) */
  showLabel?: boolean;
  /** If set, shows "#n" next to the label to distinguish docs */
  docIndex?: number;
  /** When true, renders a yellow highlight ring (used for deep-link from search) */
  highlighted?: boolean;
}

export default function DocumentCard({
  documentType,
  slot,
  isSelected,
  onSelect,
  onUpload,
  onReview,
  onReExtract,
  onDelete,
  onManualEntry,
  onEdit,
  showLabel = true,
  docIndex,
  highlighted = false,
}: Props) {
  const status = slot?.status ?? 'empty';

  const borderColor = {
    empty: 'border-gray-300',
    UPLOADED: 'border-blue-300',
    EXTRACTING: 'border-blue-400',
    PENDING_REVIEW: 'border-amber-400',
    PENDING_MODEL: 'border-orange-300',
    VERIFIED: 'border-green-400',
    EXTRACTION_FAILED: 'border-red-400',
    REJECTED: 'border-red-400',
  }[status] ?? 'border-gray-300';

  const borderStyle = status === 'empty' ? 'border-dashed' : 'border-solid';

  return (
    <div
      id={slot?.document_id ?? undefined}
      className={clsx(
        'rounded-lg border-2 p-4 transition-all',
        borderStyle,
        borderColor,
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        highlighted && 'ring-2 ring-yellow-400 shadow-lg',
        status === 'empty' ? 'cursor-default' : 'cursor-pointer hover:shadow-sm'
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
          {showLabel && (
            <span className="text-sm font-semibold">
              {DOC_TYPE_LABELS[documentType]}
              {docIndex != null && (
                <span className="text-xs text-gray-400 font-normal ml-1">
                  #{docIndex}
                </span>
              )}
            </span>
          )}
          {!showLabel && docIndex != null && (
            <span className="text-xs text-gray-400 font-medium">
              #{docIndex}
            </span>
          )}
        </div>
        {/* Status icon */}
        {status === 'VERIFIED' && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            Verified
          </span>
        )}
        {status === 'PENDING_REVIEW' && (
          slot?.slot_message?.includes('SO number') ? (
            <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium" title={slot.slot_message}>
              Waiting for SO
            </span>
          ) : (
            <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
              Pending Review
            </span>
          )
        )}
        {status === 'EXTRACTING' && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium animate-pulse">
            Extracting
          </span>
        )}
        {status === 'PENDING_MODEL' && (
          <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">
            Service Unavailable
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
        <div className="text-center py-5">
          <Upload size={24} className="mx-auto mb-2 text-gray-300" />
          <p className="text-sm text-gray-400 mb-3">No document uploaded yet</p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onUpload();
            }}
            className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium border border-blue-200 hover:border-blue-400 px-3 py-1.5 rounded-lg transition-colors"
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

      {/* Pending model state */}
      {status === 'PENDING_MODEL' && (
        <div className="py-2">
          <p className="text-sm text-orange-700">Extraction service is offline.</p>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot?.document_id) onReExtract(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              <RotateCcw size={14} />
              Retry
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot?.document_id) onManualEntry(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium"
            >
              <PenLine size={14} />
              Manual Entry
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot?.document_id) onDelete(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600"
            >
              <Trash2 size={14} />
            </button>
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
              {slot.ref_no ?? '—'}
            </p>

            {/* ── Confidence + route + validation row ─────────────── */}
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {slot.confidence != null && (
                <span
                  className={clsx(
                    'text-xs font-medium',
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

              {/* ── NEW Phase 1: route badge ─────────────────────── */}
              {slot.extraction_route === 'digital' && (
                <span
                  title="Extracted programmatically — no OCR used"
                  className="inline-flex items-center gap-0.5 text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <Zap size={10} />
                  digital
                </span>
              )}
              {slot.extraction_route === 'scanned' && (
                <span
                  title="Extracted via OCR from scanned image"
                  className="inline-flex items-center gap-0.5 text-xs text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <Camera size={10} />
                  scanned
                </span>
              )}

              {/* ── NEW Phase 6: validation error indicator ──────── */}
              {slot.has_validation_errors && (
                <span
                  title="Math or date validation failed — review required"
                  className="inline-flex items-center gap-0.5 text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <AlertTriangle size={10} />
                  check math
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
                  Review & Verify
                </button>
              )}
              {status === 'VERIFIED' && onEdit && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (slot.document_id) onEdit(slot.document_id);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
                >
                  <PenLine size={14} />
                  Edit Fields
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
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (slot.document_id) onDelete(slot.document_id);
                }}
                className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600"
                title="Delete & Re-upload"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        )}

      {/* Failed/Rejected state */}
      {(status === 'EXTRACTION_FAILED' || status === 'REJECTED') && slot && (
        <div>
          <p className="text-sm text-red-600 truncate" title={slot.slot_message ?? undefined}>
            {status === 'REJECTED'
              ? 'Rejected by reviewer'
              : friendlyExtractionError(slot.slot_message)}
          </p>
          <div className="flex items-center gap-2 mt-3">
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
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onManualEntry(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium"
            >
              <PenLine size={14} />
              Manual Entry
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onDelete(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600"
              title="Delete & Re-upload"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
