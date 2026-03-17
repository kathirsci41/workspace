import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2, Trash2, PenLine, Check, X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { usePurchaseOrder, useChainStatus, useDeletePO, useUpdatePO } from '@/hooks/usePurchaseOrders';
import { useReExtract, useCreateManualEntry } from '@/hooks/useExtraction';
import { useDeleteDocument } from '@/hooks/useDocuments';
import ChainStatusBar from '@/components/ChainStatusBar';
import DocumentCard from '@/components/DocumentCard';
import PDFPreviewPanel from '@/components/PDFPreviewPanel';
import UploadZone from '@/components/UploadZone';
import ReviewModal from '@/components/ReviewModal';
import type { DocumentType } from '@/types';
import { CHAIN_ORDER } from '@/types';
import clsx from 'clsx';

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: po, isLoading: poLoading } = usePurchaseOrder(id!);
  const { data: chainData, isLoading: chainLoading } = useChainStatus(id!);
  const reExtractMutation = useReExtract();
  const deleteMutation = useDeleteDocument();
  const deletePOMutation = useDeletePO();
  const updatePOMutation = useUpdatePO();
  const manualEntryMutation = useCreateManualEntry();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [uploadType, setUploadType] = useState<DocumentType | null>(null);
  const [reviewDocId, setReviewDocId] = useState<string | null>(null);
  const [editDocId, setEditDocId] = useState<string | null>(null);

  // SO number inline edit
  const [soEditing, setSoEditing] = useState(false);
  const [soInput, setSoInput]     = useState('');

  // Confirm dialogs
  const [reExtractConfirm, setReExtractConfirm] = useState<string | null>(null); // docId
  const [deletePOConfirm, setDeletePOConfirm]   = useState(false);

  // Toast notification
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'warn' } | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string, type: 'success' | 'warn' = 'success') => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast({ msg, type });
    toastTimer.current = setTimeout(() => setToast(null), 4000);
  };

  // Track previous extracting state to detect completion
  const prevExtractingRef = useRef(false);

  // Find selected slot for preview metadata
  const selectedEntry = chainData
    ? (() => {
        for (const [docType, slots] of Object.entries(chainData.chain)) {
          const found = slots.find((s) => s.document_id === selectedDocId);
          if (found) return [docType, found] as const;
        }
        return undefined;
      })()
    : undefined;
  const selectedSlot = selectedEntry ? selectedEntry[1] : null;
  const selectedDocType = selectedEntry ? (selectedEntry[0] as DocumentType) : null;

  // Auto-refetch chain status when extracting
  const hasExtracting = chainData
    ? Object.values(chainData.chain).some((slots) =>
        slots.some((s) => s.status === 'EXTRACTING' || s.status === 'UPLOADED')
      )
    : false;

  useEffect(() => {
    // Show toast when extraction finishes
    if (prevExtractingRef.current && !hasExtracting && chainData) {
      const hasPending = Object.values(chainData.chain).some((slots) =>
        slots.some((s) => s.status === 'PENDING_REVIEW')
      );
      const hasFailed = Object.values(chainData.chain).some((slots) =>
        slots.some((s) => s.status === 'EXTRACTION_FAILED')
      );
      if (hasFailed) showToast('Extraction finished — one or more documents need attention.', 'warn');
      else if (hasPending) showToast('Extraction complete — documents are ready to review.');
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
      },
    });
  };

  const handleDelete = (docId: string) => {
    if (!window.confirm('Delete this document? You can re-upload after.')) return;
    deleteMutation.mutate(docId, {
      onSuccess: () => {
        if (selectedDocId === docId) setSelectedDocId(null);
        queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
      },
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

  return (
    <div className="flex flex-col gap-4">
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
                    updatePOMutation.mutate(
                      { id: id!, body: { so_number: soInput.trim() || null } },
                      { onSuccess: () => setSoEditing(false) }
                    );
                  }
                  if (e.key === 'Escape') setSoEditing(false);
                }}
                placeholder="SO number"
                autoFocus
                className="text-xs px-2 py-1 border rounded-lg w-36 focus:ring-2 focus:ring-blue-400 focus:outline-none"
              />
              <button
                onClick={() =>
                  updatePOMutation.mutate(
                    { id: id!, body: { so_number: soInput.trim() || null } },
                    { onSuccess: () => setSoEditing(false) }
                  )
                }
                disabled={updatePOMutation.isPending}
                className="p-1 text-green-600 hover:bg-green-50 rounded"
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
      <div className="flex gap-4" style={{ minHeight: '65vh' }}>
        {/* Left: Document Cards */}
        <div className="w-[55%] space-y-3 overflow-y-auto pr-1">
          {CHAIN_ORDER.map((docType) => {
            const slots = chainData?.chain?.[docType] ?? [];
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
        <div className="w-[45%]">
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
            showToast('Document verified successfully.');
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
            showToast('Changes saved successfully.');
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

      {/* Toast notification */}
      {toast && (
        <div
          className={clsx(
            'fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all',
            toast.type === 'success'
              ? 'bg-green-600 text-white'
              : 'bg-amber-500 text-white'
          )}
        >
          {toast.type === 'success'
            ? <CheckCircle2 size={16} />
            : <AlertTriangle size={16} />}
          {toast.msg}
          <button onClick={() => setToast(null)} className="ml-2 opacity-70 hover:opacity-100">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
