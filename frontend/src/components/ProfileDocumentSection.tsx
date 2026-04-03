import { useState, useEffect, useRef } from 'react';
import { Eye, EyeOff, Download, FileDown, ChevronDown, ChevronRight } from 'lucide-react';
import type { POProfileDocumentSlot, POProfileDocument } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';
import { getPreviewUrl, getDownloadUrl } from '@/api/documents';
import { exportPOAsExcel } from '@/api/purchaseOrders';
import PDFViewer from '@/components/PDFViewer';

interface Props {
  slot: POProfileDocumentSlot;
  poId: string;
}

const STATUS_BORDER: Record<string, string> = {
  VERIFIED: 'border-l-green-500',
  PENDING_REVIEW: 'border-l-amber-400',
  EXTRACTION_FAILED: 'border-l-red-500',
  PENDING_MODEL: 'border-l-red-400',
  UPLOADED: 'border-l-blue-400',
  EXTRACTING: 'border-l-blue-400',
  empty: 'border-l-gray-300',
};

const STATUS_BADGE: Record<string, string> = {
  VERIFIED: 'bg-green-100 text-green-700',
  PENDING_REVIEW: 'bg-amber-100 text-amber-700',
  EXTRACTION_FAILED: 'bg-red-100 text-red-700',
  PENDING_MODEL: 'bg-red-100 text-red-600',
  UPLOADED: 'bg-blue-100 text-blue-700',
  EXTRACTING: 'bg-blue-100 text-blue-700',
  empty: 'bg-gray-100 text-gray-500',
};

function humanise(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function confidenceColour(val: number): string {
  if (val >= 0.8) return 'text-green-600';
  if (val >= 0.5) return 'text-amber-600';
  return 'text-red-500';
}

// ── Single document card ─────────────────────────────────────────────────────

interface DocCardProps {
  doc: POProfileDocument;
  docType: string;
  poId: string;
  defaultExpanded: boolean;
  showTypeLabel?: boolean;
}

function DocumentCard({ doc, docType, poId, defaultExpanded, showTypeLabel = false }: DocCardProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showPreview, setShowPreview] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [showExportMenu, setShowExportMenu] = useState(false);
  const exportMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!showExportMenu) return;
    const handler = (e: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(e.target as Node)) {
        setShowExportMenu(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [showExportMenu]);

  const handleExport = async (mode: 'single' | 'separate') => {
    setShowExportMenu(false);
    setExporting(true);
    try {
      await exportPOAsExcel(poId, doc.primary_ref_no ?? 'PO', mode);
    } finally {
      setExporting(false);
    }
  };

  const borderClass = STATUS_BORDER[doc.status] ?? 'border-l-gray-300';
  const badgeClass = STATUS_BADGE[doc.status] ?? 'bg-gray-100 text-gray-500';
  const statusLabel = doc.status.replace(/_/g, ' ');

  const previewUrl = getPreviewUrl(doc.document_id);
  const downloadUrl = getDownloadUrl(doc.document_id);

  const fields: [string, unknown][] = doc.extracted_data
    ? Object.entries(doc.extracted_data)
        .filter(([k]) => !k.startsWith('_'))
        .map(([k, v]): [string, unknown] => {
          // Corrections store arrays as JSON strings — parse them back for display
          if (typeof v === 'string' && v.trimStart().startsWith('[')) {
            try { const p = JSON.parse(v); if (Array.isArray(p)) return [k, p]; } catch {}
          }
          return [k, v];
        })
    : [];

  const verifiedDate = doc.verified_at
    ? new Date(doc.verified_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
    : null;

  const uploadedDate = doc.uploaded_at
    ? new Date(doc.uploaded_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
    : null;

  return (
    <div className={`bg-white border border-gray-200 rounded-lg border-l-4 ${borderClass} overflow-hidden`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
        <div className="flex items-center gap-2 flex-wrap">
          {showTypeLabel && (
            <button
              onClick={() => setExpanded(v => !v)}
              className="flex items-center gap-1 text-sm font-semibold text-gray-700 uppercase tracking-wide hover:text-gray-900"
            >
              {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {doc.primary_ref_no ?? doc.original_filename ?? doc.filename ?? 'Document'}
            </button>
          )}
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass}`}>{statusLabel}</span>
          {doc.confidence_score != null && (
            <span className={`text-xs font-medium ${confidenceColour(doc.confidence_score > 1 ? doc.confidence_score / 100 : doc.confidence_score)}`}>
              {doc.confidence_score > 1 ? Math.round(doc.confidence_score) : Math.round(doc.confidence_score * 100)}% confidence
            </span>
          )}
          {doc.extraction_route && (
            <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded">
              {doc.extraction_route === 'digital' ? 'Digital' : 'Scanned'}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          <button
            onClick={() => setShowPreview((v) => !v)}
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            {showPreview ? <EyeOff size={13} /> : <Eye size={13} />}
            {showPreview ? 'Hide PDF' : 'Preview'}
          </button>
          <a
            href={downloadUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800"
          >
            <Download size={13} /> Download
          </a>
          {docType === 'CUSTOMER_PO' && (
            <div className="relative" ref={exportMenuRef}>
              <button
                onClick={() => setShowExportMenu(v => !v)}
                disabled={exporting}
                className="flex items-center gap-1 text-xs text-green-700 hover:text-green-900 disabled:opacity-50"
                title="Export full PO as Excel"
              >
                <FileDown size={13} />
                {exporting ? 'Exporting…' : 'Export'}
                <ChevronDown size={11} />
              </button>
              {showExportMenu && (
                <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded shadow-lg z-20 min-w-[140px]">
                  <button
                    onClick={() => handleExport('single')}
                    className="w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-50 border-b border-gray-100"
                  >
                    Single Sheet
                  </button>
                  <button
                    onClick={() => handleExport('separate')}
                    className="w-full text-left px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
                  >
                    Separate Sheets
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {expanded && (
        <>
          {/* Sub-header: dates */}
          <div className="px-4 py-1.5 bg-gray-50 border-b border-gray-100 flex flex-wrap gap-4 text-xs text-gray-500">
            {uploadedDate && <span>Uploaded {uploadedDate}</span>}
            {verifiedDate && <span>Verified {verifiedDate}</span>}
            {doc.original_filename && <span className="truncate max-w-xs">{doc.original_filename}</span>}
          </div>

          {/* Fields grid */}
          {fields.length > 0 ? (
            <div className="px-4 py-3 space-y-3">
              {/* Short scalar fields — 2-column grid */}
              <div className="grid grid-cols-2 gap-x-6 gap-y-2">
                {fields
                  .filter(([, value]) => !Array.isArray(value) && String(value ?? '').length < 120)
                  .map(([key, value]) => {
                    const conf = doc.field_confidences?.[key];
                    return (
                      <div key={key}>
                        <div className="text-xs text-gray-400">{humanise(key)}</div>
                        <div className={`text-xs font-mono ${conf != null ? confidenceColour(conf) : 'text-gray-800'}`}>
                          {value != null && value !== '' ? String(value) : '—'}
                        </div>
                      </div>
                    );
                  })}
              </div>
              {/* Long text fields — full width */}
              {fields
                .filter(([, value]) => !Array.isArray(value) && String(value ?? '').length >= 120)
                .map(([key, value]) => (
                  <div key={key}>
                    <div className="text-xs text-gray-400 mb-1">{humanise(key)}</div>
                    <div className="text-xs text-gray-700 whitespace-pre-wrap leading-relaxed bg-gray-50 rounded px-3 py-2 border border-gray-100">
                      {value != null && value !== '' ? String(value) : '—'}
                    </div>
                  </div>
                ))}
              {/* Array fields — compact tables */}
              {fields
                .filter(([, value]) => Array.isArray(value) && (value as unknown[]).length > 0)
                .map(([key, value]) => {
                  const items = value as Record<string, unknown>[];
                  const cols = Object.keys(items[0] ?? {});
                  return (
                    <div key={key}>
                      <div className="text-xs text-gray-400 mb-1">{humanise(key)}</div>
                      <div className="overflow-x-auto">
                        <table className="w-full text-xs border-collapse">
                          <thead>
                            <tr className="bg-gray-50">
                              {cols.map((col) => (
                                <th key={col} className="text-left text-gray-500 font-medium px-2 py-1 border border-gray-200 whitespace-nowrap">
                                  {humanise(col)}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {items.map((item, idx) => (
                              <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                                {cols.map((col) => (
                                  <td key={col} className="px-2 py-1 border border-gray-200 text-gray-800 font-mono">
                                    {item[col] != null && item[col] !== '' ? String(item[col]) : '—'}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  );
                })}
            </div>
          ) : (
            <p className="px-4 py-3 text-xs text-gray-400">No extracted fields.</p>
          )}

          {/* Inline PDF viewer */}
          {showPreview && (
            <div className="border-t border-gray-100" style={{ height: '520px' }}>
              <PDFViewer url={previewUrl} />
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Slot wrapper ─────────────────────────────────────────────────────────────

export function ProfileDocumentSection({ slot, poId }: Props) {
  const docLabel = DOC_TYPE_LABELS[slot.document_type as keyof typeof DOC_TYPE_LABELS] ?? slot.document_type;
  const borderClass = STATUS_BORDER[slot.status] ?? 'border-l-gray-300';
  const badgeClass = STATUS_BADGE[slot.status] ?? 'bg-gray-100 text-gray-500';

  if (slot.status === 'empty' || slot.documents.length === 0) {
    return (
      <div className={`border border-dashed border-gray-300 rounded-lg p-4 border-l-4 ${borderClass}`}>
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-gray-400 uppercase tracking-wide">{docLabel}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass}`}>Not uploaded</span>
        </div>
        <p className="text-xs text-gray-400 mt-2">Not yet uploaded</p>
      </div>
    );
  }

  // Single document — render directly (no extra wrapper, no visual change)
  if (slot.documents.length === 1) {
    return (
      <div>
        {/* Slot type label */}
        <div className="flex items-center gap-2 mb-1 px-1">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{docLabel}</span>
        </div>
        <DocumentCard
          doc={slot.documents[0]}
          docType={slot.document_type}
          poId={poId}
          defaultExpanded={true}
          showTypeLabel={false}
        />
      </div>
    );
  }

  // Multiple documents — show slot header + collapsible cards
  return (
    <div className="space-y-2">
      <div className={`flex items-center gap-2 px-1`}>
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{docLabel}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${badgeClass}`}>
          {slot.documents.length} documents
        </span>
      </div>
      {slot.documents.map((doc, idx) => (
        <DocumentCard
          key={doc.document_id}
          doc={doc}
          docType={slot.document_type}
          poId={poId}
          defaultExpanded={idx === 0}
          showTypeLabel={true}
        />
      ))}
    </div>
  );
}
