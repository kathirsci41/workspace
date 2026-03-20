import { Download, FileText } from 'lucide-react';
import { getPreviewUrl, getDownloadUrl } from '@/api/documents';
import PDFViewer from '@/components/PDFViewer';

interface Props {
  documentId: string | null;
  refNumber?: string | null;
  documentType?: string | null;
}

export default function PDFPreviewPanel({
  documentId,
  refNumber,
  documentType,
}: Props) {
  if (!documentId) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 h-full flex flex-col items-center justify-center text-gray-400 p-8">
        <FileText size={48} className="mb-3" />
        <p className="text-sm">Select a document to preview</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200">
        <div>
          {documentType && (
            <span className="text-xs text-gray-500 uppercase">
              {documentType.replace(/_/g, ' ')}
            </span>
          )}
          {refNumber && (
            <p className="text-sm font-medium font-mono">{refNumber}</p>
          )}
        </div>
        <a
          href={getDownloadUrl(documentId)}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
        >
          <Download size={14} />
          Download
        </a>
      </div>
      {/* PDF viewer */}
      <div className="flex-1 min-h-0">
        <PDFViewer url={getPreviewUrl(documentId)} />
      </div>
    </div>
  );
}
