import { useState, useEffect } from 'react';
import { Loader2, Check, X as XIcon } from 'lucide-react';
import { verifyMetadata, rejectMetadata } from '../../api/extraction';
import { getDocumentPreviewUrl } from '../../api/documents';
import { FIELD_LABELS } from '../../config/fieldLabels';
import type { ExtractionResponse } from '../../api/extraction';

interface ReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  extraction: ExtractionResponse;
  docType: string;
  documentId: number;
  onVerified: () => void;
}

export default function ReviewModal({
  isOpen,
  onClose,
  extraction,
  docType,
  documentId,
  onVerified,
}: ReviewModalProps) {
  const [editedData, setEditedData] = useState<Record<string, string>>({});
  const [verifying, setVerifying] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (extraction?.extracted_data) {
      // Convert all values to strings for form editing
      const stringified: Record<string, string> = {};
      for (const [k, v] of Object.entries(extraction.extracted_data)) {
        stringified[k] = v != null ? String(v) : '';
      }
      setEditedData(stringified);
    }
  }, [extraction]);

  if (!isOpen) return null;

  const labels = FIELD_LABELS[docType] || {};

  const handleFieldChange = (key: string, value: string) => {
    setEditedData((prev) => ({ ...prev, [key]: value }));
  };

  const handleVerify = async () => {
    setVerifying(true);
    setError(null);
    try {
      await verifyMetadata(extraction.metadata_id, {
        extracted_data: editedData,
        primary_ref_no: extraction.primary_ref_no || undefined,
        doc_date: extraction.doc_date || undefined,
        verified_by: 'current_user', // TODO: replace with auth context
      });
      onVerified();
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Verification failed';
      setError(message);
    } finally {
      setVerifying(false);
    }
  };

  const handleReject = async () => {
    setRejecting(true);
    setError(null);
    try {
      await rejectMetadata(extraction.metadata_id);
      onClose();
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : 'Rejection failed';
      setError(message);
    } finally {
      setRejecting(false);
    }
  };

  const confidenceColor = (score: number | null) => {
    if (score == null) return 'text-gray-500';
    if (score >= 80) return 'text-green-600';
    if (score >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  const previewUrl = getDocumentPreviewUrl(documentId);

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-full items-center justify-center p-4">
        {/* Backdrop */}
        <div
          className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
          onClick={onClose}
        />

        {/* Modal */}
        <div className="relative bg-white rounded-xl shadow-2xl max-w-5xl w-full max-h-[90vh] overflow-hidden flex flex-col">
          {/* Header */}
          <div className="px-6 py-4 border-b bg-gray-50 flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">
                Review Extracted Metadata
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Document Type:{' '}
                <span className="font-medium">{docType.replace(/_/g, ' ')}</span>
                {' | '}Confidence:{' '}
                <span
                  className={`font-medium ${confidenceColor(extraction.confidence_score)}`}
                >
                  {extraction.confidence_score != null
                    ? `${extraction.confidence_score.toFixed(1)}%`
                    : 'N/A'}
                </span>
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-1 hover:bg-gray-200 rounded-full transition-colors"
            >
              <XIcon className="h-5 w-5 text-gray-500" />
            </button>
          </div>

          {/* Body — split view */}
          <div className="flex-1 overflow-y-auto p-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left: Document Preview */}
              <div className="border rounded-lg overflow-hidden bg-gray-100">
                <div className="p-2 bg-gray-200 text-sm font-medium text-gray-600">
                  Document Preview
                </div>
                <iframe
                  src={previewUrl}
                  className="w-full h-96 lg:h-[500px]"
                  title="Document Preview"
                />
              </div>

              {/* Right: Extracted Fields (Editable) */}
              <div>
                <h3 className="text-sm font-semibold text-gray-600 mb-4 uppercase tracking-wide">
                  Extracted Fields
                </h3>

                <div className="space-y-4">
                  {Object.entries(editedData).map(([key, value]) => (
                    <div key={key}>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        {labels[key] || key}
                      </label>
                      <input
                        type="text"
                        value={value}
                        onChange={(e) => handleFieldChange(key, e.target.value)}
                        className={`w-full px-3 py-2 border rounded-lg text-sm
                          focus:ring-2 focus:ring-blue-500 focus:border-blue-500
                          ${!value ? 'border-red-300 bg-red-50' : 'border-gray-300'}`}
                        placeholder={`Enter ${labels[key] || key}`}
                      />
                      {!value && (
                        <p className="text-xs text-red-500 mt-1">
                          Not found — please fill manually
                        </p>
                      )}
                    </div>
                  ))}
                </div>

                {/* Primary ref & date (read-only summary) */}
                {(extraction.primary_ref_no || extraction.doc_date) && (
                  <div className="mt-6 p-3 bg-gray-50 rounded-lg">
                    <p className="text-xs font-medium text-gray-500 mb-1">
                      Auto-detected summary
                    </p>
                    {extraction.primary_ref_no && (
                      <p className="text-sm text-gray-700">
                        Ref: <span className="font-mono">{extraction.primary_ref_no}</span>
                      </p>
                    )}
                    {extraction.doc_date && (
                      <p className="text-sm text-gray-700">
                        Date: <span className="font-mono">{extraction.doc_date}</span>
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="px-6 py-2 bg-red-50 text-red-600 text-sm">
              {error}
            </div>
          )}

          {/* Footer — Actions */}
          <div className="px-6 py-4 border-t bg-gray-50 flex justify-between">
            <button
              onClick={handleReject}
              disabled={rejecting}
              className="px-4 py-2 border border-red-300 text-red-600
                rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50"
            >
              {rejecting ? 'Rejecting…' : 'Reject & Re-extract'}
            </button>

            <div className="flex gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-gray-600
                  rounded-lg hover:bg-gray-100 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleVerify}
                disabled={verifying}
                className="px-6 py-2 bg-green-600 text-white rounded-lg
                  hover:bg-green-700 transition-colors disabled:opacity-50
                  flex items-center gap-2"
              >
                {verifying ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Check className="h-4 w-4" />
                )}
                {verifying ? 'Saving…' : 'Verify & Save'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
