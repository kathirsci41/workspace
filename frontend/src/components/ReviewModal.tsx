import { useState, useEffect } from 'react';
import { X, Check, Ban, Loader2, PenLine } from 'lucide-react';
import { useMetadata, useVerifyMetadata, useRejectMetadata, useFieldTemplate } from '@/hooks/useExtraction';
import { getPreviewUrl } from '@/api/documents';
import clsx from 'clsx';

interface Props {
  documentId: string;
  onClose: () => void;
  onVerified: () => void;
}

export default function ReviewModal({ documentId, onClose, onVerified }: Props) {
  const { data: metadata, isLoading } = useMetadata(documentId);
  const verifyMutation = useVerifyMetadata();
  const rejectMutation = useRejectMetadata();

  // Check if extracted data is empty/missing
  const isDataEmpty = !metadata?.extracted_data || Object.keys(metadata.extracted_data).length === 0;
  const { data: template } = useFieldTemplate(documentId, isDataEmpty && !isLoading);

  const [formData, setFormData] = useState<Record<string, string>>({});
  const [isManualMode, setIsManualMode] = useState(false);

  useEffect(() => {
    if (metadata?.extracted_data && Object.keys(metadata.extracted_data).length > 0) {
      const initial: Record<string, string> = {};
      for (const [key, value] of Object.entries(metadata.extracted_data)) {
        initial[key] = value != null ? String(value) : '';
      }
      setFormData(initial);
      setIsManualMode(
        metadata.model_version === 'manual' ||
        Object.values(metadata.extracted_data).every((v) => v === null || v === '')
      );
    } else if (template?.fields) {
      // Populate from template with empty values for manual entry
      const initial: Record<string, string> = {};
      for (const key of Object.keys(template.fields)) {
        initial[key] = '';
      }
      setFormData(initial);
      setIsManualMode(true);
    }
  }, [metadata, template]);

  const handleVerify = () => {
    // Convert form values back to appropriate types
    const editedData: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(formData)) {
      if (value === '') {
        editedData[key] = null;
      } else if (!isNaN(Number(value)) && key.includes('amount') || key.includes('count') || key.includes('quantity') || key.includes('subtotal') || key.includes('tax')) {
        editedData[key] = Number(value);
      } else if (key === 'signature_present') {
        editedData[key] = value === 'true';
      } else {
        editedData[key] = value;
      }
    }

    verifyMutation.mutate(
      { documentId, editedData },
      { onSuccess: onVerified }
    );
  };

  const handleReject = () => {
    rejectMutation.mutate(documentId, { onSuccess: onClose });
  };

  const formatLabel = (key: string) =>
    key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase());

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <Loader2 size={32} className="animate-spin text-white" />
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60">
      <div className="m-auto bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] max-w-7xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold">
              {isManualMode ? 'Manual Data Entry' : 'Review Extracted Data'}
            </h3>
            {metadata && (
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs text-gray-500 uppercase">
                  {metadata.document_type?.replace(/_/g, ' ')}
                </span>
                {metadata.confidence_score != null && (
                  <span
                    className={clsx(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      metadata.confidence_score >= 80
                        ? 'bg-green-100 text-green-700'
                        : metadata.confidence_score >= 50
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-red-100 text-red-700'
                    )}
                  >
                    Confidence: {metadata.confidence_score}%
                  </span>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content - split view */}
        <div className="flex-1 flex min-h-0">
          {/* Left: PDF preview */}
          <div className="w-1/2 border-r border-gray-200">
            <iframe
              src={getPreviewUrl(documentId)}
              className="w-full h-full border-0"
              title="Document Preview"
            />
          </div>

          {/* Right: Form fields */}
          <div className="w-1/2 flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 space-y-3">
              {isManualMode && Object.keys(formData).length > 0 && (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3 flex items-center gap-2 mb-2">
                  <PenLine size={16} />
                  Manual entry mode — fill in the fields from the document on the left, then click Verify.
                </div>
              )}
              {Object.entries(formData).map(([key, value]) => (
                <div key={key}>
                  <label className="block text-xs font-medium text-gray-500 mb-1">
                    {formatLabel(key)}
                    {template?.field_descriptions?.[key] && (
                      <span className="ml-1 text-gray-400 font-normal">
                        — {template.field_descriptions[key]}
                      </span>
                    )}
                  </label>
                  {key === 'signature_present' ? (
                    <select
                      value={value}
                      onChange={(e) =>
                        setFormData((f) => ({
                          ...f,
                          [key]: e.target.value,
                        }))
                      }
                      className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    >
                      <option value="">Unknown</option>
                      <option value="true">Yes</option>
                      <option value="false">No</option>
                    </select>
                  ) : (
                    <input
                      type="text"
                      value={value}
                      onChange={(e) =>
                        setFormData((f) => ({
                          ...f,
                          [key]: e.target.value,
                        }))
                      }
                      placeholder={`Enter ${formatLabel(key).toLowerCase()}`}
                      className={clsx(
                        'w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none',
                        value ? 'border-gray-300' : 'border-red-200 bg-red-50'
                      )}
                    />
                  )}
                </div>
              ))}
              {Object.keys(formData).length === 0 && !isLoading && (
                <p className="text-sm text-gray-400 py-8 text-center">
                  No extraction data or template available. Try re-extracting the document.
                </p>
              )}
            </div>

            {/* Action buttons */}
            <div className="px-6 py-4 border-t border-gray-200 space-y-2">
              {(verifyMutation.isError || rejectMutation.isError) && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
                  {(() => {
                    const err = (verifyMutation.error || rejectMutation.error) as any;
                    const detail = err?.response?.data?.detail;
                    if (typeof detail === 'string') return detail;
                    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
                    return err?.message || 'Operation failed. Please try again.';
                  })()}
                </div>
              )}
              <div className="flex items-center justify-end gap-3">
              <button
                onClick={handleReject}
                disabled={rejectMutation.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50"
              >
                <Ban size={16} />
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleVerify}
                disabled={verifyMutation.isPending}
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                <Check size={16} />
                {verifyMutation.isPending ? 'Verifying...' : 'Verify'}
              </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
