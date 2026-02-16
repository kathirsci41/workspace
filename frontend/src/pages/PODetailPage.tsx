import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Loader2 } from 'lucide-react';
import { useQueryClient } from '@tanstack/react-query';
import { usePurchaseOrder, useChainStatus } from '@/hooks/usePurchaseOrders';
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
  const manualEntryMutation = useCreateManualEntry();

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [uploadType, setUploadType] = useState<DocumentType | null>(null);
  const [reviewDocId, setReviewDocId] = useState<string | null>(null);

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
    if (!hasExtracting) return;
    const interval = setInterval(() => {
      queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
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
    reExtractMutation.mutate(docId, {
      onSuccess: () => {
        queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
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
        <div className="flex items-center gap-3">
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
          }}
        />
      )}
    </div>
  );
}
