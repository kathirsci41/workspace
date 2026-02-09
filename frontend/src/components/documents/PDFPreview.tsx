import { useState, useEffect } from 'react';
import { X, RotateCw, Download, Trash2, Loader2 } from 'lucide-react';
import { getDocumentPreviewUrl, getDocumentDownloadUrl } from '../../api/documents';
import { getMetadata } from '../../api/extraction';
import { useRotateDocument, useDeleteDocument } from '../../hooks/useDocuments';
import { DOCUMENT_TYPE_LABELS } from '../../types';
import type { Document } from '../../types';
import type { ExtractionResponse, ExtractionStatus } from '../../api/extraction';
import Button from '../common/Button';
import ExtractButton from '../extraction/ExtractButton';
import StatusBadge from '../extraction/StatusBadge';
import ReviewModal from '../extraction/ReviewModal';

interface PDFPreviewProps {
  document: Document;
  onClose: () => void;
  caseId: string;
}

export default function PDFPreview({ document, onClose, caseId }: PDFPreviewProps) {
  const [rotation, setRotation] = useState(document.rotation || 0);
  const [isDeleting, setIsDeleting] = useState(false);

  // Phase 2: Extraction state
  const [extractionStatus, setExtractionStatus] = useState<ExtractionStatus | null>(null);
  const [extractionResult, setExtractionResult] = useState<ExtractionResponse | null>(null);
  const [isReviewOpen, setIsReviewOpen] = useState(false);

  const { mutate: rotateDocument, isPending: isRotating } = useRotateDocument(caseId);
  const { mutate: deleteDocument, isPending: isDeletePending } = useDeleteDocument(caseId);

  // Fetch existing metadata status when document changes
  useEffect(() => {
    let cancelled = false;
    setExtractionStatus(null);
    setExtractionResult(null);

    getMetadata(document.id)
      .then((meta) => {
        if (!cancelled) {
          setExtractionStatus(meta.status);
        }
      })
      .catch(() => {
        // No metadata yet — that's fine
        if (!cancelled) setExtractionStatus(null);
      });

    return () => { cancelled = true; };
  }, [document.id]);

  const handleExtractionComplete = (result: ExtractionResponse) => {
    setExtractionStatus(result.status);
    setExtractionResult(result);
    // Auto-open review modal if extraction succeeded
    if (result.status === 'EXTRACTED') {
      setIsReviewOpen(true);
    }
  };

  const handleVerified = () => {
    setExtractionStatus('VERIFIED');
    setExtractionResult(null);
  };

  const handleRotate = () => {
    const newRotation = (rotation + 90) % 360;
    rotateDocument(
      { documentId: document.id, degrees: 90 },
      {
        onSuccess: () => {
          setRotation(newRotation);
        },
      }
    );
  };

  const handleDelete = () => {
    if (window.confirm('Are you sure you want to delete this document?')) {
      setIsDeleting(true);
      deleteDocument(document.id, {
        onSuccess: () => {
          onClose();
        },
        onError: () => {
          setIsDeleting(false);
        },
      });
    }
  };

  const previewUrl = getDocumentPreviewUrl(document.id);

  return (
    <div className="w-[500px] bg-white border-l border-gray-200 flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div className="min-w-0">
          <h3 className="font-medium text-gray-900 truncate">
            {document.originalFilename}
          </h3>
          <div className="flex items-center gap-2 mt-0.5">
            <p className="text-sm text-gray-500">
              {DOCUMENT_TYPE_LABELS[document.documentType as keyof typeof DOCUMENT_TYPE_LABELS]}
              {document.referenceNumber && ` • ${document.referenceNumber}`}
            </p>
            <StatusBadge status={extractionStatus} />
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 hover:bg-gray-100 rounded-full flex-shrink-0"
        >
          <X className="h-5 w-5 text-gray-500" />
        </button>
      </div>

      {/* PDF Viewer */}
      <div className="flex-1 bg-gray-200 relative overflow-hidden">
        <iframe
          src={previewUrl}
          className="w-full h-full"
          style={{
            transform: `rotate(${rotation}deg)`,
            transformOrigin: 'center center',
          }}
          title={document.originalFilename}
        />
        {isRotating && (
          <div className="absolute inset-0 bg-black bg-opacity-20 flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-white" />
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200">
        <div className="flex items-center gap-2">
          <ExtractButton
            documentId={document.id}
            currentStatus={extractionStatus}
            onExtractionComplete={handleExtractionComplete}
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRotate}
            disabled={isRotating}
          >
            <RotateCw className={`h-4 w-4 mr-1 ${isRotating ? 'animate-spin' : ''}`} />
            Rotate
          </Button>
          <a
            href={getDocumentDownloadUrl(document.id)}
            download
            className="inline-flex items-center px-3 py-1.5 text-sm text-gray-700 hover:bg-gray-100 rounded-md"
          >
            <Download className="h-4 w-4 mr-1" />
            Download
          </a>
        </div>
        <Button
          variant="danger"
          size="sm"
          onClick={handleDelete}
          isLoading={isDeleting || isDeletePending}
        >
          <Trash2 className="h-4 w-4 mr-1" />
          Delete
        </Button>
      </div>

      {/* Phase 2: Review Modal */}
      {extractionResult && (
        <ReviewModal
          isOpen={isReviewOpen}
          onClose={() => {
            setIsReviewOpen(false);
            // Re-fetch metadata to update status after verify/reject
            getMetadata(document.id)
              .then((meta) => setExtractionStatus(meta.status))
              .catch(() => setExtractionStatus(null));
            setExtractionResult(null);
          }}
          extraction={extractionResult}
          docType={document.documentType}
          documentId={document.id}
          onVerified={handleVerified}
        />
      )}
    </div>
  );
}
