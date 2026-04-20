import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Download, Loader2 } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query';
import { usePurchaseOrder, useDeletePO } from '@/hooks/usePurchaseOrders';
import { exportPOAsExcel, getChainValidation, getChainStatus, updatePO } from '@/api/purchaseOrders';
import type { ChainStatus } from '@/types';
import { useReExtract } from '@/hooks/useExtraction';
import { useDeleteDocument } from '@/hooks/useDocuments';
import Breadcrumb from '@/components/Breadcrumb';
import { LightChainTimeline } from '@/components/LightChainTimeline';
import DocCard from '@/components/DocCard';
import OrderSettingsCard from '@/components/OrderSettingsCard';
import BillingTab from '@/components/BillingTab';
import PDFViewer from '@/components/PDFViewer';
import { getPreviewUrl, getDownloadUrl } from '@/api/documents';
import UploadZone from '@/components/UploadZone';
import ReviewModal from '@/components/ReviewModal';
import type { ChainSlot, DocumentType, PurchaseOrder } from '@/types';
import { CHAIN_ORDER, DOC_TYPE_LABELS } from '@/types';
import clsx from 'clsx';

type Tab = 'overview' | 'documents' | 'billing';

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const showToast = useToast();

  const [activeTab, setActiveTab]             = useState<Tab>('overview');
  const [uploadType, setUploadType]           = useState<DocumentType | null>(null);
  const [reviewDocId, setReviewDocId]         = useState<string | null>(null);
  const [editDocId, setEditDocId]             = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId]     = useState<string | null>(searchParams.get('highlight'));
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [reExtractConfirm, setReExtractConfirm] = useState<string | null>(null);
  const [deleteDocConfirm, setDeleteDocConfirm] = useState<string | null>(null);
  const [deletePOConfirm, setDeletePOConfirm]   = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data: po, isLoading: poLoading } = usePurchaseOrder(id!);

  // /chain — validation data (reference checks, billing, missing slots, completeness_pct)
  const chainQuery = useQuery({
    queryKey: ['chain-validation', id],
    queryFn: () => getChainValidation(id!),
    enabled: !!id,
  });
  const chainValidation = chainQuery.data ?? null;

  // /chain-status — document slot data (chain: Record<string, ChainSlot[]>)
  const chainSlotsQuery = useQuery({
    queryKey: ['chain-status', id],
    queryFn: () => getChainStatus(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data as ChainStatus | undefined;
      if (!data?.chain) return false;
      const extracting = Object.values(data.chain)
        .some(slots => slots.some(s => s.status === 'EXTRACTING' || s.status === 'UPLOADED'));
      return extracting ? 3000 : false;
    },
  });
  const chainSlotsData = chainSlotsQuery.data as ChainStatus | undefined;

  const reExtractMutation = useReExtract();
  const deleteMutation    = useDeleteDocument();
  const deletePOMutation  = useDeletePO();

  const updatePOMutation = useMutation({
    mutationFn: (patch: Partial<PurchaseOrder>) => updatePO(id!, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchaseOrder', id] });
      queryClient.invalidateQueries({ queryKey: ['chain-validation', id] });
      queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
      showToast('Saved', 'success');
    },
    onError: () => showToast('Save failed', 'error'),
  });

  // Auto-open review modal when ?review= param is set
  useEffect(() => {
    const reviewParam = searchParams.get('review');
    if (reviewParam) setReviewDocId(reviewParam);
  }, [searchParams]);

  // Toast when extraction polling completes
  const prevExtractingRef = useRef(false);
  const chainSlots = (chainSlotsData?.chain ?? {}) as Record<string, ChainSlot[]>;
  const hasExtracting = Object.values(chainSlots)
    .some(slots => slots.some(s => s.status === 'EXTRACTING' || s.status === 'UPLOADED'));

  useEffect(() => {
    if (prevExtractingRef.current && !hasExtracting && chainSlotsData) {
      const allSlots = Object.values(chainSlots).flat();
      if (allSlots.some(s => s.status === 'EXTRACTION_FAILED'))
        showToast('Extraction failed — open the document to enter manually.', 'error');
      else if (allSlots.some(s => s.status === 'PENDING_REVIEW'))
        showToast('Extraction complete — documents are ready to review.', 'success');
    }
    prevExtractingRef.current = hasExtracting;
  }, [hasExtracting, chainSlotsData]);

  const handleExport = async () => {
    setExporting(true);
    try { await exportPOAsExcel(id!, po!.po_number, 'separate'); }
    catch { showToast('Export failed', 'error'); }
    finally { setExporting(false); }
  };

  // Derived values
  const chain = chainSlots;
  const missingSlots    = chainValidation?.missing_slots ?? [];
  const referenceChecks = chainValidation?.reference_checks ?? [];
  const billedSoFar     = (chainValidation?.billing.stages ?? []).length > 0
    ? (chainValidation?.billing.stages ?? []).reduce((sum, s) => sum + (s.invoiced_amount ?? 0), 0)
    : (chainValidation?.billing.invoiced_total ?? 0);

  // Pending review count for Documents tab badge
  const pendingCount = Object.values(chain)
    .flat()
    .filter(s => s.status === 'PENDING_REVIEW')
    .length;

  // Find doc type for a given docId
  function findDocType(docId: string): string | null {
    for (const [dt, slots] of Object.entries(chain)) {
      if (slots.some(s => s.document_id === docId)) return dt;
    }
    return null;
  }

  function findDocTypeLabel(docId: string) {
    const dt = findDocType(docId);
    return dt ? (DOC_TYPE_LABELS[dt as DocumentType] ?? dt) : 'document';
  }

  function findDocFilename(docId: string): string | null {
    for (const slots of Object.values(chain)) {
      const found = slots.find(s => s.document_id === docId);
      if (found) return (found as any).filename ?? null;
    }
    return null;
  }

  const handleViewDoc = (docId: string) => {
    setSelectedDocId(docId);
    setSelectedDocType(findDocType(docId));
  };

  const invalidateChain = () => {
    queryClient.invalidateQueries({ queryKey: ['chain-validation', id] });
    queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
    queryClient.invalidateQueries({ queryKey: ['purchaseOrder', id] });
  };

  if (poLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-gray-400" size={28} />
      </div>
    );
  }
  if (!po) return <div className="p-8 text-gray-500">PO not found.</div>;

  return (
    <div className="flex flex-col bg-[--paper] min-h-full">

      {/* Breadcrumb */}
      <div className="bg-white border-b border-[--veil] px-6 py-2.5">
        <Breadcrumb items={[{ label: 'Purchase Orders', to: '/purchase-orders' }, { label: po.po_number }]} />
      </div>

      {/* ── PO Header ── */}
      <div className="bg-white border-b border-[--veil] px-6 py-4 flex items-start gap-4 flex-wrap">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1.5 flex-wrap">
            <span className="font-mono text-base font-bold text-[--accent]">{po.po_number}</span>
            <span className={clsx(
              'text-[10px] font-bold px-2.5 py-1 rounded-full border',
              po.status === 'COMPLETE'   ? 'bg-green-50 text-green-700 border-green-300'
              : po.status === 'CANCELLED' ? 'bg-red-50 text-red-700 border-red-300'
              : 'bg-amber-50 text-amber-700 border-amber-300',
            )}>
              ● {po.status.replace('_', ' ')}
            </span>
            {chainValidation && (
              <span className={clsx(
                'text-[10px] font-bold px-2.5 py-1 rounded-full border',
                (chainValidation.completeness_pct ?? 0) >= 100
                  ? 'bg-green-50 text-green-700 border-green-300'
                  : 'bg-blue-50 text-blue-700 border-blue-300',
              )}>
                ⬡ Chain {Math.round(chainValidation.completeness_pct ?? 0)}%
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <span className="font-medium text-[--ink]">{po.customer_name}</span>
            <span className="text-gray-300">·</span>
            <span className="font-bold text-[--ink]">₹{Number(po.total_amount ?? 0).toLocaleString('en-IN')}</span>
            {po.so_number && (
              <>
                <span className="text-gray-300">·</span>
                <span className="text-xs text-gray-500">SO: <span className="font-mono">{po.so_number}</span></span>
              </>
            )}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <Link
            to={`/purchase-orders/${id}/profile`}
            className="text-xs font-semibold px-3 py-2 rounded-lg border border-[--veil] text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ↗ Profile
          </Link>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="text-xs font-semibold px-3 py-2 rounded-lg border border-[--veil] text-gray-600 hover:bg-gray-50 transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
            Export
          </button>
        </div>
      </div>

      {/* ── Tab strip ── */}
      <div className="bg-white border-b border-[--veil] px-6 flex gap-0">
        {([
          ['overview',  'Overview',  null],
          ['documents', 'Documents', pendingCount > 0 ? pendingCount : null],
          ['billing',   'Billing',   null],
        ] as [Tab, string, number | null][]).map(([tab, label, badge]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-5 py-3 text-xs font-semibold border-b-2 -mb-px transition-colors flex items-center gap-1.5',
              activeTab === tab
                ? 'text-[--accent] border-[--accent]'
                : 'text-gray-400 border-transparent hover:text-[--ink]',
            )}
          >
            {label}
            {badge != null && (
              <span className="bg-amber-100 text-amber-700 text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                {badge}
              </span>
            )}
          </button>
        ))}
        <button
          onClick={() => setDeletePOConfirm(true)}
          className="ml-auto px-5 py-3 text-xs font-semibold text-red-400 hover:text-red-600 border-b-2 border-transparent -mb-px transition-colors"
        >
          Delete
        </button>
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 px-6 py-5 max-w-5xl w-full">

        {/* ══ OVERVIEW ══ */}
        {activeTab === 'overview' && (
          <div>
            <OrderSettingsCard
              scenario={po.order_scenario}
              billingType={po.billing_type ?? 'full'}
              billedSoFar={billedSoFar}
              milestoneCount={(po.billing_milestones ?? []).length}
              poTotal={Number(po.total_amount ?? 0)}
              gstType={po.gst_type ?? 'unknown'}
              invoiceSplit={po.invoice_split ?? false}
              itemsVerified={po.items_verified ?? false}
              onScenarioChange={val => updatePOMutation.mutate({ order_scenario: val })}
              onBillingTypeChange={val => updatePOMutation.mutate({ billing_type: val })}
              onGstTypeChange={val => updatePOMutation.mutate({ gst_type: val })}
              onInvoiceSplitChange={val => updatePOMutation.mutate({ invoice_split: val })}
              onItemsVerifiedChange={val => updatePOMutation.mutate({ items_verified: val })}
            />

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Document Chain
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="mb-5">
              <LightChainTimeline
                chain={chain}
                missingSlots={missingSlots}
                referenceChecks={referenceChecks}
              />
            </div>

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Reference Validation
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="flex flex-wrap gap-2 mb-5">
              {referenceChecks.length === 0 && (
                <span className="text-xs text-gray-400">No reference data — upload documents to validate</span>
              )}
              {referenceChecks.map((rc, i) => (
                <div key={i} className="relative group">
                  <span
                    className={clsx(
                      'text-xs font-medium px-3 py-1.5 rounded-lg border flex items-center gap-1.5 cursor-default',
                      rc.result === 'pass'     && 'bg-green-50 border-green-300 text-green-700',
                      rc.result === 'mismatch' && 'bg-red-50 border-red-300 text-red-700',
                      rc.result === 'skip' && rc.skip_reason === 'extraction_failed'
                        ? 'bg-orange-50 border-orange-200 text-orange-600'
                        : rc.result === 'skip' && 'bg-gray-50 border-gray-200 text-gray-400',
                    )}
                  >
                    {rc.result === 'pass' ? '✓' : rc.result === 'mismatch' ? '✗' : rc.skip_reason === 'extraction_failed' ? '⚠' : '○'}
                    {' '}{rc.check}
                  </span>
                  {(rc.result === 'mismatch' || (rc.result === 'skip' && rc.skip_reason === 'extraction_failed')) && (
                    <div className="absolute bottom-full left-0 mb-1.5 hidden group-hover:block z-30 w-64 bg-[--ink] text-white text-[10px] rounded-lg px-3 py-2 shadow-lg">
                      {rc.result === 'mismatch' && (
                        <>
                          <div className="font-bold mb-1">Mismatch</div>
                          <div>Extracted: <span className="font-mono">{rc.extracted ?? '—'}</span></div>
                          <div>Expected: <span className="font-mono">{rc.expected ?? '—'}</span></div>
                        </>
                      )}
                      {rc.result === 'skip' && rc.skip_reason === 'extraction_failed' && (
                        <div>Extraction failed — validate manually</div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Billing Summary
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="bg-white border border-[--veil] rounded-xl p-4">
              <div className="grid grid-cols-3 gap-3 mb-3">
                {[
                  { label: 'PO Total',      val: `₹${Number(po.total_amount ?? 0).toLocaleString('en-IN')}`, cls: '' },
                  { label: 'Billed So Far', val: `₹${billedSoFar.toLocaleString('en-IN')}`,                  cls: 'text-amber-700' },
                  { label: 'Outstanding',   val: `₹${Math.max(0, Number(po.total_amount ?? 0) - billedSoFar).toLocaleString('en-IN')}`, cls: 'text-red-600' },
                ].map(k => (
                  <div key={k.label} className="border border-[--veil] rounded-lg p-3">
                    <div className="text-[9px] font-bold uppercase tracking-wide text-gray-400">{k.label}</div>
                    <div className={clsx('text-sm font-bold mt-1', k.cls || 'text-[--ink]')}>{k.val}</div>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setActiveTab('billing')}
                className="text-xs font-semibold text-[--accent] hover:underline"
              >
                → View full billing detail
              </button>
            </div>
          </div>
        )}

        {/* ══ DOCUMENTS ══ */}
        {activeTab === 'documents' && (
          <div className="flex flex-col gap-2">
            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-1 flex items-center gap-2">
              {CHAIN_ORDER.length} Document Types
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            {CHAIN_ORDER.map(docType => {
              const slots = chain[docType] ?? [];
              const isMulti = docType !== 'CUSTOMER_PO';
              const label = DOC_TYPE_LABELS[docType] ?? docType;
              return (
                <div key={docType} className="flex flex-col gap-1.5">
                  {slots.length === 0 ? (
                    <DocCard
                      label={label}
                      slot={null}
                      onUpload={() => setUploadType(docType as DocumentType)}
                      onReview={docId => setReviewDocId(docId)}
                      onView={docId => handleViewDoc(docId)}
                      onReExtract={docId => setReExtractConfirm(docId)}
                      onEditFields={docId => setEditDocId(docId)}
                      onDelete={docId => setDeleteDocConfirm(docId)}
                    />
                  ) : (
                    <>
                      {slots.map((slot, i) => (
                        <DocCard
                          key={slot.document_id ?? i}
                          label={slots.length > 1 ? `${label} #${i + 1}` : label}
                          slot={slot}
                          onUpload={() => setUploadType(docType as DocumentType)}
                          onReview={docId => setReviewDocId(docId)}
                          onView={docId => handleViewDoc(docId)}
                          onReExtract={docId => setReExtractConfirm(docId)}
                          onEditFields={docId => setEditDocId(docId)}
                          onDelete={docId => setDeleteDocConfirm(docId)}
                        />
                      ))}
                      {isMulti && (
                        <button
                          onClick={() => setUploadType(docType as DocumentType)}
                          className="self-start text-xs font-medium text-[--accent] hover:underline pl-1"
                        >
                          + Add another {label}
                        </button>
                      )}
                    </>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* ══ BILLING ══ */}
        {activeTab === 'billing' && (
          <BillingTab
            po={po}
            chainValidation={chainValidation}
            onUpdate={patch => updatePOMutation.mutate(patch)}
          />
        )}
      </div>

      {/* ── PDF popup modal ── */}
      {selectedDocId && (() => {
        const previewUrl  = getPreviewUrl(selectedDocId);
        const downloadUrl = getDownloadUrl(selectedDocId);
        const label = selectedDocType
          ? (DOC_TYPE_LABELS[selectedDocType as DocumentType] ?? selectedDocType)
          : 'Document';
        const slot = Object.values(chain).flat().find(s => s.document_id === selectedDocId);
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
            onClick={() => setSelectedDocId(null)}
          >
            <div
              className="bg-white rounded-xl shadow-2xl flex flex-col"
              style={{ width: '90vw', height: '90vh' }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 shrink-0">
                <div>
                  <span className="font-semibold text-sm">{label}</span>
                  {slot?.ref_no && (
                    <span className="ml-2 font-mono text-xs text-gray-500">{slot.ref_no}</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <a
                    href={downloadUrl}
                    download
                    className="text-xs font-semibold text-[--accent] flex items-center gap-1 hover:underline"
                  >
                    <Download size={12} /> Download
                  </a>
                  <button
                    onClick={() => setSelectedDocId(null)}
                    className="text-gray-400 hover:text-gray-600 text-lg leading-none"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="flex-1 min-h-0">
                <PDFViewer url={previewUrl} />
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Upload modal ── */}
      {uploadType && (
        <UploadZone
          poId={id!}
          documentType={uploadType}
          onClose={() => setUploadType(null)}
          onSuccess={() => {
            setUploadType(null);
            invalidateChain();
          }}
        />
      )}

      {/* ── Review modal ── */}
      {reviewDocId && (
        <ReviewModal
          documentId={reviewDocId}
          mode="review"
          onClose={() => {
            setReviewDocId(null);
            invalidateChain();
          }}
          onVerified={() => {
            setReviewDocId(null);
            invalidateChain();
          }}
        />
      )}

      {/* ── Edit fields modal ── */}
      {editDocId && (
        <ReviewModal
          documentId={editDocId}
          mode="edit"
          onClose={() => setEditDocId(null)}
          onVerified={() => {
            setEditDocId(null);
            invalidateChain();
          }}
          onSaved={() => {
            setEditDocId(null);
            invalidateChain();
            showToast('Changes saved', 'success');
          }}
        />
      )}

      {/* ── Re-extract confirm ── */}
      {reExtractConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-[--ink] mb-1">
              Re-extract {findDocTypeLabel(reExtractConfirm)}?
            </h3>
            {findDocFilename(reExtractConfirm) && (
              <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">
                {findDocFilename(reExtractConfirm)}
              </p>
            )}
            <p className="text-sm text-gray-500 mb-4">
              The document will be reprocessed by the AI. Existing extracted data will be replaced.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setReExtractConfirm(null)}
                className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  reExtractMutation.mutate(reExtractConfirm, {
                    onSuccess: () => {
                      setReExtractConfirm(null);
                      invalidateChain();
                      showToast('Re-extraction queued', 'success');
                    },
                    onError: () => showToast('Re-extraction failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--accent] text-white rounded-lg hover:bg-[--accent]/90"
              >
                Re-extract
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete document confirm ── */}
      {deleteDocConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-[--ink] mb-1">
              Delete {findDocTypeLabel(deleteDocConfirm)}?
            </h3>
            {findDocFilename(deleteDocConfirm) && (
              <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">
                {findDocFilename(deleteDocConfirm)}
              </p>
            )}
            <p className="text-sm text-gray-500 mb-4">
              This will permanently delete the document. You can re-upload at any time.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeleteDocConfirm(null)}
                className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deleteMutation.mutate(deleteDocConfirm, {
                    onSuccess: () => {
                      setDeleteDocConfirm(null);
                      invalidateChain();
                      showToast('Document deleted', 'success');
                    },
                    onError: () => showToast('Delete failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--signal] text-white rounded-lg hover:bg-[--signal]/90"
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete PO confirm ── */}
      {deletePOConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-red-600 mb-2">Delete this Purchase Order?</h3>
            <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">
              {po.po_number}
            </p>
            <p className="text-sm text-gray-500 mb-4">
              This will permanently delete the PO and all associated documents. This cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setDeletePOConfirm(false)}
                className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  deletePOMutation.mutate(id!, {
                    onSuccess: () => navigate('/purchase-orders'),
                    onError: () => showToast('Delete failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--signal] text-white rounded-lg hover:bg-[--signal]/90"
              >
                Yes, Delete PO
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
