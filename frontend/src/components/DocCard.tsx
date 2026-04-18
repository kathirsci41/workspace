import { useState, useRef, useEffect } from 'react';
import { MoreHorizontal } from 'lucide-react';
import type { ChainSlot } from '@/types';
import clsx from 'clsx';

interface Props {
  label: string;
  slot: ChainSlot | null;
  onUpload: () => void;
  onReview: (docId: string) => void;
  onView: (docId: string) => void;
  onReExtract: (docId: string) => void;
  onEditFields: (docId: string) => void;
  onDelete: (docId: string) => void;
}

const STATUS_BORDER: Record<string, string> = {
  VERIFIED:          'border-l-green-400',
  PENDING_REVIEW:    'border-l-amber-400',
  EXTRACTION_FAILED: 'border-l-red-400',
  EXTRACTING:        'border-l-blue-400',
  UPLOADED:          'border-l-blue-400',
  missing:           'border-l-[--veil]',
};

const STATUS_TAG: Record<string, { label: string; cls: string }> = {
  VERIFIED:          { label: '✓ Verified',   cls: 'bg-green-100 text-green-700' },
  PENDING_REVIEW:    { label: '⚠ Review',     cls: 'bg-amber-100 text-amber-700' },
  EXTRACTION_FAILED: { label: '✗ Failed',     cls: 'bg-red-100 text-red-700'    },
  EXTRACTING:        { label: '⟳ Extracting', cls: 'bg-blue-100 text-blue-700'  },
  UPLOADED:          { label: '⟳ Processing', cls: 'bg-blue-100 text-blue-700'  },
  missing:           { label: '— Missing',    cls: 'bg-gray-100 text-gray-500'  },
};

export default function DocCard({
  label, slot,
  onUpload, onReview, onView, onReExtract, onEditFields, onDelete,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const status = slot?.status ?? 'missing';
  const docId  = slot?.document_id ?? null;
  const borderKey = STATUS_BORDER[status] ?? 'border-l-[--veil]';
  const tag = STATUS_TAG[status] ?? STATUS_TAG.missing;
  const isMissing = !slot || !docId;

  return (
    <div
      className={clsx(
        'flex items-center gap-3 bg-white rounded-lg border border-[--veil] border-l-4 px-4 py-3',
        borderKey,
        isMissing && 'bg-gray-50 border-dashed',
      )}
    >
      <span className="text-lg flex-shrink-0 w-6 text-center">
        {isMissing ? '📭' : status === 'PENDING_REVIEW' ? '📋' : '📄'}
      </span>

      <div className="flex-1 min-w-0">
        <div className={clsx('text-sm font-bold', isMissing && 'text-gray-400')}>{label}</div>
        <div className="font-mono text-[10px] text-gray-500">
          {slot?.ref_no ?? (isMissing ? 'Not uploaded' : '—')}
        </div>
      </div>

      <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full flex-shrink-0', tag.cls)}>
        {tag.label}
      </span>

      {isMissing && (
        <button
          onClick={onUpload}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-[--accent] text-[--accent] bg-[#eef2ff] hover:bg-[--accent] hover:text-white transition-colors flex-shrink-0"
        >
          + Upload
        </button>
      )}
      {!isMissing && status === 'PENDING_REVIEW' && (
        <button
          onClick={() => onReview(docId!)}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 transition-colors flex-shrink-0"
        >
          Review →
        </button>
      )}
      {!isMissing && status === 'VERIFIED' && (
        <button
          onClick={() => onView(docId!)}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-[--veil] text-gray-600 bg-white hover:bg-gray-50 transition-colors flex-shrink-0"
        >
          View →
        </button>
      )}

      {!isMissing && docId && (
        <div className="relative flex-shrink-0" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(v => !v)}
            className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 transition-colors"
            aria-label="More actions"
          >
            <MoreHorizontal size={14} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-[--veil] rounded-lg shadow-lg z-20 overflow-hidden">
              {(status === 'VERIFIED' || status === 'PENDING_REVIEW') && (
                <button
                  className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                  onClick={() => { setMenuOpen(false); onEditFields(docId); }}
                >
                  ✏ Edit Fields
                </button>
              )}
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                onClick={() => { setMenuOpen(false); onView(docId); }}
              >
                👁 View PDF
              </button>
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                onClick={() => { setMenuOpen(false); onReExtract(docId); }}
              >
                ↺ Re-extract
              </button>
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-red-50 text-red-600"
                onClick={() => { setMenuOpen(false); onDelete(docId); }}
              >
                🗑 Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
