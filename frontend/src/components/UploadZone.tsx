import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, Loader2 } from 'lucide-react';
import { useUploadDocument } from '@/hooks/useDocuments';
import type { DocumentType } from '@/types';

interface Props {
  poId: string;
  documentType: DocumentType;
  onSuccess: () => void;
  onClose: () => void;
}

export default function UploadZone({
  poId,
  documentType,
  onSuccess,
  onClose,
}: Props) {
  const uploadMutation = useUploadDocument();

  const onDrop = useCallback(
    (files: File[]) => {
      if (files.length === 0) return;
      uploadMutation.mutate(
        { poId, file: files[0], documentType },
        {
          onSuccess: () => {
            onSuccess();
          },
        }
      );
    },
    [poId, documentType, uploadMutation, onSuccess]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
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
              isDragActive
                ? 'border-blue-500 bg-blue-50'
                : 'border-gray-300 hover:border-blue-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload size={32} className="mx-auto text-gray-400 mb-3" />
            <p className="text-sm text-gray-600">
              {isDragActive
                ? 'Drop the PDF here'
                : 'Drag & drop a PDF file here, or click to browse'}
            </p>
            <p className="text-xs text-gray-400 mt-1">Only .pdf files accepted</p>
          </div>
        )}

        {uploadMutation.isError && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 mt-3">
            {(() => {
              const err = uploadMutation.error as any;
              const detail = err?.response?.data?.detail;
              if (typeof detail === 'string') return detail;
              if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
              return err?.message || 'Upload failed. Please try again.';
            })()}
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
