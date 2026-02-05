import { Eye, Download, Trash2, FileText } from 'lucide-react';
import { getDocumentDownloadUrl } from '../../api/documents';
import { DOCUMENT_TYPE_LABELS } from '../../types';
import type { Document } from '../../types';

interface DocumentTableProps {
  documents: Document[];
  onView: (doc: Document) => void;
  onDelete?: (doc: Document) => void;
}

export default function DocumentTable({ documents, onView, onDelete }: DocumentTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr className="text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
            <th className="px-3 py-2">Type</th>
            <th className="px-3 py-2">Filename</th>
            <th className="px-3 py-2">Reference</th>
            <th className="px-3 py-2">Size</th>
            <th className="px-3 py-2">Uploaded</th>
            <th className="px-3 py-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {documents.map((doc) => (
            <tr key={doc.id} className="hover:bg-gray-50">
              <td className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <FileText className="h-4 w-4 text-gray-400" />
                  <span className="text-sm text-gray-700">
                    {DOCUMENT_TYPE_LABELS[doc.documentType as keyof typeof DOCUMENT_TYPE_LABELS] || doc.documentType}
                  </span>
                </div>
              </td>
              <td className="px-3 py-2">
                <span className="text-sm text-gray-900 truncate max-w-xs block">
                  {doc.originalFilename}
                </span>
              </td>
              <td className="px-3 py-2">
                <span className="text-sm text-gray-500">
                  {doc.referenceNumber || '-'}
                </span>
              </td>
              <td className="px-3 py-2">
                <span className="text-sm text-gray-500">
                  {formatFileSize(doc.fileSize)}
                </span>
              </td>
              <td className="px-3 py-2">
                <span className="text-sm text-gray-500">
                  {formatDate(doc.uploadedAt)}
                </span>
              </td>
              <td className="px-3 py-2">
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => onView(doc)}
                    className="p-1.5 hover:bg-gray-100 rounded-md text-gray-500 hover:text-gray-700"
                    title="View"
                  >
                    <Eye className="h-4 w-4" />
                  </button>
                  <a
                    href={getDocumentDownloadUrl(doc.id)}
                    download
                    className="p-1.5 hover:bg-gray-100 rounded-md text-gray-500 hover:text-gray-700"
                    title="Download"
                  >
                    <Download className="h-4 w-4" />
                  </a>
                  {onDelete && (
                    <button
                      onClick={() => onDelete(doc)}
                      className="p-1.5 hover:bg-red-50 rounded-md text-gray-500 hover:text-red-600"
                      title="Delete"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}
