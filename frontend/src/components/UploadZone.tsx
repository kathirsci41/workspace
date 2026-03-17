import { useCallback } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';
import { Upload, Loader2, AlertCircle } from 'lucide-react';
import { useUploadDocument } from '@/hooks/useDocuments';
import type { DocumentType } from '@/types';

interface Props {
  poId: string;
  documentType: DocumentType;
  onSuccess: () => void;
  onClose: () => void;
}

// Accepted MIME types — PDF only (scanned or digital). Must match backend ALLOWED_MIME_TYPES.
const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
};

export default function UploadZone({
  poId,
  documentType,
  onSuccess,
  onClose,
}: Props) {
  const uploadMutation = useUploadDocument();
  const onDrop = useCallback(
    (accepted: File[], _rejected: FileRejection[]) => {
      if (accepted.length === 0) return;
      uploadMutation.mutate(
        { poId, file: accepted[0], documentType },
        { onSuccess: () => { onSuccess(); } }
      );
    },
    [poId, documentType, uploadMutation, onSuccess]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_TYPES,
      maxFiles: 1,
    });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">
          Upload {documentType.replace(/_/g, ' ')}
        </h3>

        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center py-10 text-gray-500">
            <Loader2 size={32} className="animate-spin mb-3" />
            <p className="text-sm">Uploading...</p>
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg py-12 px-6 text-center cursor-pointer transition-colors ${
              isDragReject
                ? 'border-red-400 bg-red-50'
                : isDragActive
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-blue-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload
              size={32}
              className={`mx-auto mb-3 ${isDragReject ? 'text-red-400' : 'text-gray-400'}`}
            />
            <p className="text-sm text-gray-600">
              {isDragReject
                ? 'This file type is not accepted'
                : isDragActive
                  ? 'Drop the file here'
                  : 'Drag & drop here, or click to browse'}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Accepted: PDF only (scanned or digital)
            </p>
          </div>
        )}

        {/* Server-side error (including 415 from backend) */}
        {uploadMutation.isError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 mt-3">
            <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
            <span>
              {(() => {
                const err = uploadMutation.error as any;
                const detail = err?.response?.data?.detail;
                if (typeof detail === 'string') return detail;
                if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
                return err?.message || 'Upload failed. Please try again.';
              })()}
            </span>
          </div>
        )}

        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
