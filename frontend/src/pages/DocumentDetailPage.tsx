import { useParams, useNavigate, Link } from 'react-router-dom';
import { Loader2, ExternalLink } from 'lucide-react';
import clsx from 'clsx';
import { useDocument } from '@/hooks/useDocuments';
import { getDownloadUrl } from '@/api/documents';
import PDFPreviewPanel from '@/components/PDFPreviewPanel';
import Breadcrumb from '@/components/Breadcrumb';

function DocStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    VERIFIED:          'bg-green-100 text-green-700',
    PENDING_REVIEW:    'bg-amber-100 text-amber-700',
    EXTRACTION_FAILED: 'bg-red-100 text-red-700',
    REJECTED:          'bg-red-100 text-red-600',
    EXTRACTING:        'bg-blue-100 text-blue-700',
    UPLOADED:          'bg-gray-100 text-gray-600',
  };
  return (
    <span className={clsx('text-xs font-medium px-2 py-1 rounded-full', colors[status] ?? 'bg-gray-100 text-gray-700')}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${Math.round(bytes / 1024)} KB`;
}

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { data: doc, isLoading, isError } = useDocument(id!);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 size={28} className="animate-spin text-gray-400" />
      </div>
    );
  }

  if (isError || !doc) {
    return (
      <div className="p-8 text-center">
        <p className="text-lg font-semibold text-gray-700 mb-2">Document not found</p>
        <p className="text-sm text-gray-400 mb-4">The document you are looking for does not exist or has been removed.</p>
        <Link to="/documents" className="text-sm text-blue-600 hover:underline">
          Back to Documents
        </Link>
      </div>
    );
  }

  const isPendingReview = doc.status === 'PENDING_REVIEW';

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-4">
      <Breadcrumb items={[
        { label: 'Documents', to: '/documents' },
        { label: doc.original_filename },
      ]} />

      <div className="flex gap-6 items-start">
        {/* Left: PDF preview */}
        <div className="flex-1 min-w-0" style={{ height: '75vh' }}>
          <PDFPreviewPanel
            documentId={id!}
            refNumber={doc.metadata?.primary_ref_no ?? null}
            documentType={doc.document_type}
          />
        </div>

        {/* Right: Metadata */}
        <div className="w-72 shrink-0 space-y-4">
          <div className="bg-white border border-gray-200 rounded-lg p-4 space-y-3">
            <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Document Info</h2>

            {/* Status */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Status</span>
              <DocStatusBadge status={doc.status} />
            </div>

            {/* Document type */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Type</span>
              <span className="text-xs font-medium text-gray-700">
                {doc.document_type.replace(/_/g, ' ')}
              </span>
            </div>

            {/* PO number */}
            {doc.po_number && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">PO Number</span>
                <Link
                  to={`/purchase-orders/${doc.po_id}`}
                  className="text-xs font-mono text-blue-600 hover:underline"
                >
                  {doc.po_number}
                </Link>
              </div>
            )}

            {/* Customer */}
            {doc.customer_name && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Customer</span>
                <span className="text-xs text-gray-700">{doc.customer_name}</span>
              </div>
            )}

            {/* Uploaded date */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">Uploaded</span>
              <span className="text-xs text-gray-700">
                {new Date(doc.created_at).toLocaleDateString()}
              </span>
            </div>

            {/* Days pending */}
            {isPendingReview && doc.days_pending != null && (
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500">Days pending</span>
                <span className={clsx('text-xs font-medium', doc.days_pending >= 3 ? 'text-red-600' : 'text-amber-600')}>
                  {doc.days_pending}d
                </span>
              </div>
            )}

            {/* File size */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-500">File size</span>
              <span className="text-xs text-gray-700">{formatFileSize(doc.file_size)}</span>
            </div>
          </div>

          {/* Actions */}
          <div className="flex flex-col gap-2">
            {isPendingReview && doc.po_id && (
              <button
                onClick={() =>
                  navigate(`/purchase-orders/${doc.po_id}?highlight=${id}&review=${id}`)
                }
                className="flex items-center justify-center gap-1.5 w-full bg-blue-600 text-white text-sm font-medium px-4 py-2 rounded-lg hover:bg-blue-700"
              >
                Review <ExternalLink size={14} />
              </button>
            )}
            <a
              href={getDownloadUrl(id!)}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-1.5 w-full border border-gray-300 text-gray-700 text-sm font-medium px-4 py-2 rounded-lg hover:bg-gray-50"
            >
              Download
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
