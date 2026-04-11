import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { ArrowLeft, Loader2, Trash2, PenLine, Check, X, AlertTriangle, BarChart2, Download } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { useQueryClient } from '@tanstack/react-query';
import { usePurchaseOrder, useChainStatus, useDeletePO } from '@/hooks/usePurchaseOrders';
import { exportPOAsExcel, getChainValidation, updateSoNumber } from '@/api/purchaseOrders';
import type { ChainStatusResponse } from '@/api/purchaseOrders';
import { useReExtract, useCreateManualEntry } from '@/hooks/useExtraction';
import { useDeleteDocument } from '@/hooks/useDocuments';
import Breadcrumb from '@/components/Breadcrumb';
import ChainStatusBar from '@/components/ChainStatusBar';
import { ChainTimeline } from '@/components/ChainTimeline/ChainTimeline';
import type { ChainSlot as TimelineSlot } from '@/components/ChainTimeline/ChainTimeline';
import { ReferenceValidationPanel } from '@/components/ReferenceValidationPanel/ReferenceValidationPanel';
import { BillingCompletenessPanel } from '@/components/BillingCompletenessPanel/BillingCompletenessPanel';
import DocumentCard from '@/components/DocumentCard';
import PDFPreviewPanel from '@/components/PDFPreviewPanel';
import UploadZone from '@/components/UploadZone';
import ReviewModal from '@/components/ReviewModal';
import type { ChainSlot as ApiChainSlot, ChainStatus, DocumentType } from '@/types';
import { CHAIN_ORDER } from '@/types';
import clsx from 'clsx';

function buildSlots(
  missingSlots: string[],
  onUpload: (type: string) => void,
  onView: (type: string) => void,
): TimelineSlot[] {
  const SLOT_LABELS: Record<string, string> = {
    CUSTOMER_PO:           'Customer PO',
    COMPANY_PO:            'Vendor PO',
    VENDOR_INVOICE:        'Vendor Invoice',
    COMPANY_DC:            'Company DC',
    COMPANY_INVOICE:       'Company Invoice',
    INSTALLATION_REPORT:   'Installation Report',
  };
  return Object.keys(SLOT_LABELS).map(type => ({
    docType:  type,
    label:    SLOT_LABELS[type],
    state:    missingSlots.includes(type) ? 'waiting' : 'verified',
    onUpload: (_label: string) => onUpload(type),
    onView:   (_label: string) => onView(type),
  }));
}

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const highlightDocId = searchParams.get('highlight');
  const reviewParam = searchParams.get('review');
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const showToast = useToast();

  const { data: po, isLoading: poLoading } = usePurchaseOrder(id!);
  const chainStatusQuery = useChainStatus(id!);
  const chainData = chainStatusQuery.data as ChainStatus | undefined;
  const chainLoading = chainStatusQuery.isLoading;
  const reExtractMutation = useReExtract();
  const deleteMutation = useDeleteDocument();
  const deletePOMutation = useDeletePO();
  const manualEntryMutation = useCreateManualEntry();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(highlightDocId);
  const [uploadType, setUploadType] = useState<DocumentType | null>(null);
  const [reviewDocId, setReviewDocId] = useState<string | null>(null);
  const [editDocId, setEditDocId] = useState<string | null>(null);

  // SO number inline edit
  const [soEditing, setSoEditing] = useState(false);
  const [soInput, setSoInput]     = useState('');

  // Chain validation (reference checks, billing, missing slots)
  const [chainValidation, setChainValidation] = useState<ChainStatusResponse | null>(null);

  // Confirm dialogs
  const [reExtractConfirm, setReExtractConfirm] = useState<string | null>(null); // docId
  const [deleteDocConfirm, setDeleteDocConfirm] = useState<string | null>(null); // docId
  const [deletePOConfirm, setDeletePOConfirm]   = useState(false);

  const [exporting, setExporting] = useState(false);

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportPOAsExcel(id!, po!.po_number, 'separate');
    } catch {
      showToast('Export failed. Please try again.', 'error');
    } finally {
      setExporting(false);
    }
  };

  // Track previous extracting state to detect completion
  const prevExtractingRef = useRef(false);

  // Find selected slot for preview metadata
  const selectedEntry = chainData
    ? (() => {
        for (const [docType, slots] of Object.entries(chainData.chain as Record<string, ApiChainSlot[]>)) {
          const found = slots.find((s: ApiChainSlot) => s.document_id === selectedDocId);
          if (found) return [docType, found] as const;
        }
        return undefined;
      })()
    : undefined;
  const selectedSlot = selectedEntry ? selectedEntry[1] : null;
  const selectedDocType = selectedEntry ? (selectedEntry[0] as DocumentType) : null;

  // Auto-refetch chain status when extracting
  const hasExtracting = chainData
    ? Object.values(chainData.chain as Record<string, ApiChainSlot[]>).some((slots) =>
        slots.some((s: ApiChainSlot) => s.status === 'EXTRACTING' || s.status === 'UPLOADED')
      )
    : false;

  useEffect(() => {
    // Show toast when extraction finishes
    if (prevExtractingRef.current && !hasExtracting && chainData) {
      const allSlots = Object.values(chainData.chain as Record<string, ApiChainSlot[]>).flat();
      const hasFailed       = allSlots.some((s: ApiChainSlot) => s.status === 'EXTRACTION_FAILED');
      const hasPendingModel = allSlots.some((s: ApiChainSlot) => s.status === 'PENDING_MODEL');
      const hasPending      = allSlots.some((s: ApiChainSlot) => s.status === 'PENDING_REVIEW');

      if (hasFailed && !hasPending)
        showToast('Extraction failed — open the document to enter manually.', 'error');
      else if (hasFailed && hasPending)
        showToast('Extraction finished — one or more documents need attention.', 'warn');
      else if (hasPendingModel)
        showToast('AI model unavailable — document will retry when service is back.', 'warn');
      else if (hasPending)
        showToast('Extraction complete — documents are ready to review.', 'success');
    }
    prevExtractingRef.current = hasExtracting;
  }, [hasExtracting, chainData]);

  useEffect(() => {
    if (!hasExtracting) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
      queryClient.invalidateQueries({ queryKey: ['purchaseOrder', id] });
    }, 3000);
    return () => clearInterval(interval);
  }, [hasExtracting, id, queryClient]);

  // Scroll to and highlight document card when navigated from search results
  useEffect(() => {
    if (!highlightDocId || !chainData) return;
    const el = document.getElementById(highlightDocId);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightDocId, chainData]);

  useEffect(() => {
    if (reviewParam && !reviewDocId) {
      setReviewDocId(reviewParam);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // only on mount

  // Fetch chain validation whenever PO id changes
  useEffect(() => {
    if (!id) return;
    getChainValidation(id).then(setChainValidation).catch(console.error);
  }, [id]);

  const handleSoSaveAndValidate = async () => {
    if (!id) return;
    try {
      await updateSoNumber(id, soInput.trim());
      setSoEditing(false);
      const updated = await getChainValidation(id);
      setChainValidation(updated);
      // Also refresh the PO data so the displayed SO badge updates
      queryClient.invalidateQueries({ queryKey: ['purchaseOrder', id] });
    } catch {
      showToast('Failed to save SO number. Please try again.', 'error');
    }
  };

  if (poLoading || chainLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={32} className="animate-spin text-gray-400" />
      </div>
    );
  }

  if (!po) {
    return (
      <div className="text-center py-20 text-gray-400">
        Purchase order not found.
      </div>
    );
  }

  const handleReExtract = (docId: string) => {
    setReExtractConfirm(docId);
  };

  const confirmReExtract = () => {
    if (!reExtractConfirm) return;
    reExtractMutation.mutate(reExtractConfirm, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
        setReExtractConfirm(null);
        showToast('Re-extraction started — document will update shortly.', 'info');
      },
      onError: () => {
        setReExtractConfirm(null);
        showToast('Failed to start re-extraction. Please try again.', 'error');
      },
    });
  };

  const handleDelete = (docId: string) => {
    setDeleteDocConfirm(docId);
  };

  const confirmDeleteDoc = () => {
    if (!deleteDocConfirm) return;
    deleteMutation.mutate(deleteDocConfirm, {
      onSuccess: () => {
        if (selectedDocId === deleteDocConfirm) setSelectedDocId(null);
        queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
        setDeleteDocConfirm(null);
      },
      onError: () => setDeleteDocConfirm(null),
    });
  };

  const handleDeletePO = () => setDeletePOConfirm(true);

  const confirmDeletePO = () => {
    deletePOMutation.mutate(id!, {
      onSuccess: () => navigate('/purchase-orders'),
    });
  };

  const handleManualEntry = (docId: string) => {
    manualEntryMutation.mutate(docId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
        setReviewDocId(docId);
        showToast('Manual entry mode — fill in the fields from the document.', 'info');
      },
      onError: () => {
        showToast('Could not open manual entry. Please try again.', 'error');
      },
    });
  };

  // Extract error messages
  const actionError = reExtractMutation.isError || deleteMutation.isError || manualEntryMutation.isError
    ? (() => {
        const err = (reExtractMutation.error || deleteMutation.error || manualEntryMutation.error) as any;
        const detail = err?.response?.data?.detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
        return err?.message || 'Operation failed. Please try again.';
      })()
    : '';

  const statusColors: Record<string, string> = {
    INITIATED: 'bg-gray-100 text-gray-700',
    IN_PROGRESS: 'bg-blue-100 text-blue-700',
    NEAR_COMPLETE: 'bg-amber-100 text-amber-700',
    COMPLETE: 'bg-green-100 text-green-700',
    CANCELLED: 'bg-red-100 text-red-700',
  };

  const timelineSlots = chainValidation
    ? buildSlots(
        chainValidation.missing_slots,
        (type) => setUploadType(type as DocumentType),
        (type) => {
          const firstSlot = (chainData?.chain as Record<string, ApiChainSlot[]> | undefined)?.[type]?.[0];
          if (firstSlot?.document_id) setSelectedDocId(firstSlot.document_id);
        },
      )
    : [];
  const fallbackCompletenessPct = timelineSlots.length > 0
    ? Math.round((timelineSlots.filter((slot) => slot.state === 'verified').length / timelineSlots.length) * 100)
    : 0;
  const chainCompletenessPct = chainValidation?.completeness_pct ?? fallbackCompletenessPct;
  const referenceChecks = chainValidation?.reference_checks.map((check) => ({
    ...check,
    extracted: check.extracted,
    expected: check.expected,
  })) ?? [];

  return (
    <div className="flex flex-col gap-4 h-full">
      {/* Breadcrumb */}
      {po && (
        <Breadcrumb items={[
          { label: 'Purchase Orders', to: '/purchase-orders' },
          { label: po.po_number },
        ]} />
      )}

      {/* Header */}
      <div className="flex items-center gap-4 flex-wrap">
        <button
          onClick={() => navigate(-1)}
          className="p-2 hover:bg-gray-100 rounded-lg"
        >
          <ArrowLeft size={20} />
        </button>
        <div className="flex-1 min-w-0">
          <h2 className="text-2xl font-bold truncate">{po.po_number}</h2>
          <p className="text-sm text-gray-500">
            {po.customer_name ?? po.customer_sky_id ?? ''}{' '}
            {po.customer_sky_id ? `(${po.customer_sky_id})` : ''}
          </p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <Link
            to={`/purchase-orders/${id}/profile`}
            className="flex items-center gap-1.5 text-sm text-blue-600 border border-blue-200 px-3 py-1.5 rounded-lg hover:bg-blue-50"
          >
            <BarChart2 size={14} /> View Profile
          </Link>
          <button
            onClick={handleExport}
            disabled={exporting}
            title="Export PO data to Excel"
            className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50"
          >
            <Download size={14} className={exporting ? 'animate-bounce' : ''} />
            {exporting ? 'Exporting…' : 'Export'}
          </button>
          <button
            onClick={handleDeletePO}
            disabled={deletePOMutation.isPending}
            className="flex items-center gap-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 px-3 py-1.5 rounded-lg border border-red-200 disabled:opacity-50"
            title="Delete this PO and all documents"
          >
            <Trash2 size={14} />
            {deletePOMutation.isPending ? 'Deleting…' : 'Delete PO'}
          </button>
          <span
            className={clsx(
              'text-xs font-medium px-3 py-1 rounded-full',
              statusColors[po.status] ?? 'bg-gray-100 text-gray-700'
            )}
          >
            {po.status.replace('_', ' ')}
          </span>
          {po.total_amount != null && (
            <span className="text-sm font-medium text-gray-700">
              {po.currency} {po.total_amount.toLocaleString()}
            </span>
          )}

          {/* SO Number badge + inline edit */}
          {soEditing ? (
            <div className="flex items-center gap-1">
              <input
                type="text"
                value={soInput}
                onChange={(e) => setSoInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    handleSoSaveAndValidate();
                  }
                  if (e.key === 'Escape') setSoEditing(false);
                }}
                placeholder="SO number"
                autoFocus
                className="text-xs px-2 py-1 border rounded-lg w-36 focus:ring-2 focus:ring-blue-400 focus:outline-none"
              />
              <button
                onClick={handleSoSaveAndValidate}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
                title="Save"
              >
                <Check size={14} />
              </button>
              <button
                onClick={() => setSoEditing(false)}
                className="p-1 text-gray-400 hover:bg-gray-100 rounded"
              >
                <X size={14} />
              </button>
            </div>
          ) : (
            <button
              onClick={() => { setSoInput(po.so_number ?? ''); setSoEditing(true); }}
              className={clsx(
                'inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full border',
                po.so_number
                  ? 'bg-green-50 text-green-700 border-green-200 hover:bg-green-100'
                  : 'bg-amber-50 text-amber-700 border-amber-200 hover:bg-amber-100'
              )}
              title="Click to edit SO number"
            >
              <PenLine size={11} />
              {po.so_number ? `SO: ${po.so_number}` : 'SO: Not set'}
            </button>
          )}
        </div>
      </div>

      {/* Chain Status Bar */}
      {chainData && <ChainStatusBar chain={chainData.chain} />}

      {/* Chain complete banner */}
      {chainData?.completeness_pct === 100 && (
        <ChainCompleteBanner poId={id!} profilePath={`/purchase-orders/${id}/profile`} />
      )}

      {/* Chain validation status banner */}
      {chainValidation && (
        <div className={clsx(
          'rounded-lg p-3 border flex items-center justify-between',
          chainValidation.chain_status === 'mismatch'  ? 'bg-red-50 border-red-200' :
          chainValidation.chain_status === 'complete' || chainValidation.chain_status === 'verified'
            ? 'bg-green-50 border-green-200' :
          'bg-amber-50 border-amber-200'
        )}>
          <div>
            <p className={clsx(
              'text-sm font-semibold',
              chainValidation.chain_status === 'mismatch'  ? 'text-red-800' :
              chainValidation.chain_status === 'complete' || chainValidation.chain_status === 'verified'
                ? 'text-green-800' : 'text-amber-800'
            )}>
              {chainValidation.chain_status === 'complete' || chainValidation.chain_status === 'verified'
                ? '✓ Chain Complete'
                : chainValidation.chain_status === 'mismatch'
                ? '✗ Reference Mismatch'
                : '⚠ Chain Incomplete'}
            </p>
            {chainValidation.missing_slots.length > 0 && (
              <p className="text-xs text-gray-500 mt-0.5">
                Missing: {chainValidation.missing_slots.map(s => s.replace(/_/g, ' ')).join(' · ')}
              </p>
            )}
            <p className="text-xs text-gray-500 mt-0.5">{chainCompletenessPct}% complete</p>
          </div>
        </div>
      )}

      {/* Two-column chain validation view */}
      {chainValidation && (
        <div className="grid grid-cols-3 gap-4">
          <div className="col-span-2 bg-slate-900 border border-slate-800 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-slate-200 mb-4">Document Chain</h3>
            <ChainTimeline slots={timelineSlots} />
          </div>
          <div className="flex flex-col gap-4">
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Reference Validation</h3>
              <ReferenceValidationPanel checks={referenceChecks} />
            </div>
            <div className="bg-slate-900 border border-slate-800 rounded-lg p-4">
              <h3 className="text-sm font-semibold text-slate-200 mb-3">Billing</h3>
              <BillingCompletenessPanel
                billing={chainValidation.billing}
                poTotal={po.total_amount}
                billingType={(po as any).billing_type ?? 'full'}
              />
            </div>
          </div>
        </div>
      )}

      {/* Action error banner */}
      {actionError && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 flex items-center justify-between">
          <span>{typeof actionError === 'string' ? actionError : JSON.stringify(actionError)}</span>
          <button
            onClick={() => {
              reExtractMutation.reset();
              deleteMutation.reset();
              manualEntryMutation.reset();
            }}
            className="text-red-500 hover:text-red-700 text-xs font-medium ml-4"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Left: Document Cards */}
        <div className="w-[55%] space-y-3 overflow-y-auto pr-1">
          {CHAIN_ORDER.map((docType) => {
            const slots: ApiChainSlot[] = chainData?.chain?.[docType] ?? [];
            return (
              <div key={docType} className="space-y-2">
                {slots.length === 0 ? (
                  /* No documents yet – show empty card */
                  <DocumentCard
                    documentType={docType}
                    slot={null}
                    isSelected={false}
                    onSelect={(docId) => setSelectedDocId(docId)}
                    onUpload={() => setUploadType(docType)}
                    onReview={(docId) => setReviewDocId(docId)}
                    onReExtract={handleReExtract}
                    onDelete={handleDelete}
                    onManualEntry={handleManualEntry}
                    onEdit={(docId) => setEditDocId(docId)}
                  />
                ) : (
                  <>
                    {slots.map((slot, idx) => (
                      <DocumentCard
                        key={slot.document_id ?? `${docType}-${idx}`}
                        documentType={docType}
                        slot={slot}
                        isSelected={
                          selectedDocId != null &&
                          slot.document_id === selectedDocId
                        }
                        highlighted={slot.document_id === highlightDocId}
                        onSelect={(docId) => setSelectedDocId(docId)}
                        onUpload={() => setUploadType(docType)}
                        onReview={(docId) => setReviewDocId(docId)}
                        onReExtract={handleReExtract}
                        onDelete={handleDelete}
                        onManualEntry={handleManualEntry}
                        onEdit={(docId) => setEditDocId(docId)}
                        showLabel={idx === 0}
                        docIndex={slots.length > 1 ? idx + 1 : undefined}
                      />
                    ))}
                    {/* Always show "Add another" button when docs exist */}
                    <button
                      onClick={() => setUploadType(docType)}
                      className="w-full border-2 border-dashed border-gray-300 hover:border-blue-400 rounded-lg py-2 text-xs text-gray-400 hover:text-blue-600 transition-colors"
                    >
                      + Add another
                    </button>
                  </>
                )}
              </div>
            );
          })}
        </div>

        {/* Right: PDF Preview */}
        <div className="w-[45%] min-w-0">
          <PDFPreviewPanel
            documentId={selectedDocId}
            refNumber={selectedSlot?.ref_no}
            documentType={selectedDocType}
          />
        </div>
      </div>

      {/* Upload modal */}
      {uploadType && (
        <UploadZone
          poId={id!}
          documentType={uploadType}
          onSuccess={() => {
            setUploadType(null);
            queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
          }}
          onClose={() => setUploadType(null)}
        />
      )}

      {/* Review modal */}
      {reviewDocId && (
        <ReviewModal
          documentId={reviewDocId}
          onClose={() => setReviewDocId(null)}
          onVerified={() => {
            setReviewDocId(null);
            queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
            queryClient.invalidateQueries({ queryKey: ['documents', 'status', 'PENDING_REVIEW'] });
            showToast('Document verified and saved.', 'success');
          }}
        />
      )}

      {/* Edit fields modal (VERIFIED documents) */}
      {editDocId && (
        <ReviewModal
          documentId={editDocId}
          mode="edit"
          onClose={() => setEditDocId(null)}
          onVerified={() => {}}
          onSaved={() => {
            setEditDocId(null);
            queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
            showToast('Changes saved successfully.', 'success');
          }}
        />
      )}

      {/* Re-extract confirmation modal */}
      {reExtractConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="flex items-center gap-3 text-amber-700">
              <AlertTriangle size={20} />
              <h3 className="font-semibold text-base">Re-extract this document?</h3>
            </div>
            <p className="text-sm text-gray-600">
              This will re-run AI extraction and <strong>overwrite any manual corrections</strong> you have made. This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setReExtractConfirm(null)}
                className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmReExtract}
                disabled={reExtractMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-amber-600 rounded-lg hover:bg-amber-700 disabled:opacity-50"
              >
                {reExtractMutation.isPending ? 'Re-extracting…' : 'Yes, Re-extract'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete PO confirmation modal */}
      {deletePOConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="flex items-center gap-3 text-red-700">
              <Trash2 size={20} />
              <h3 className="font-semibold text-base">Delete PO "{po.po_number}"?</h3>
            </div>
            <p className="text-sm text-gray-600">
              This will permanently delete this PO and all{' '}
              <strong>{Object.values(chainData?.chain ?? {}).flat().length} uploaded document(s)</strong>.
              This cannot be undone.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeletePOConfirm(false)}
                className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeletePO}
                disabled={deletePOMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deletePOMutation.isPending ? 'Deleting…' : 'Yes, Delete PO'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete document confirmation modal */}
      {deleteDocConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full mx-4 space-y-4">
            <div className="flex items-center gap-3 text-red-700">
              <Trash2 size={20} />
              <h3 className="font-semibold text-base">Delete this document?</h3>
            </div>
            <p className="text-sm text-gray-600">
              This will permanently delete the document. You can re-upload after.
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setDeleteDocConfirm(null)}
                className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={confirmDeleteDoc}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Yes, Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

function ChainCompleteBanner({ poId, profilePath }: { poId: string; profilePath: string }) {
  const bannerKey = `chain-complete-dismissed-${poId}`;
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(bannerKey) === '1'; } catch { return false; }
  });
  if (dismissed) return null;
  return (
    <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
      <span className="text-sm text-green-800 font-medium">
        ✓ All documents complete —{' '}
        <Link to={profilePath} className="underline hover:text-green-900">View Profile →</Link>
      </span>
      <button
        onClick={() => {
          try { sessionStorage.setItem(bannerKey, '1'); } catch {}
          setDismissed(true);
        }}
        className="text-green-600 hover:text-green-800 ml-4"
      >
        <X size={16} />
      </button>
    </div>
  );
}

