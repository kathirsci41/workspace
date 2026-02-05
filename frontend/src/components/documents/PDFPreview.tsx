import { useState } from 'react';
import { X, RotateCw, Download, Trash2, Loader2 } from 'lucide-react';
import { getDocumentPreviewUrl, getDocumentDownloadUrl } from '../../api/documents';
import { useRotateDocument, useDeleteDocument } from '../../hooks/useDocuments';
import { DOCUMENT_TYPE_LABELS } from '../../types';
import type { Document } from '../../types';
import Button from '../common/Button';

interface PDFPreviewProps {
  document: Document;
  onClose: () => void;
  caseId: string;
}

export default function PDFPreview({ document, onClose, caseId }: PDFPreviewProps) {
  const [rotation, setRotation] = useState(document.rotation || 0);
  const [isDeleting, setIsDeleting] = useState(false);

  const { mutate: rotateDocument, isPending: isRotating } = useRotateDocument(caseId);
  const { mutate: deleteDocument, isPending: isDeletePending } = useDeleteDocument(caseId);

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
          <p className="text-sm text-gray-500">
            {DOCUMENT_TYPE_LABELS[document.documentType as keyof typeof DOCUMENT_TYPE_LABELS]}
            {document.referenceNumber && ` • ${document.referenceNumber}`}
          </p>
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
    </div>
  );
}
