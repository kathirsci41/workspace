import { useParams, Link } from 'react-router-dom';
import { ChevronLeft, FolderOpen, Loader2, AlertCircle, CheckCircle2, Circle } from 'lucide-react';
import { useSearchSalesOrders } from '../hooks/useSalesOrders';
import DocumentTable from '../components/case/DocumentTable';
import { SO_DOCUMENT_TYPES, DOCUMENT_TYPE_LABELS } from '../types';
import type { Document } from '../types';

export default function SOSearchResults() {
  const { soNumber } = useParams<{ soNumber: string }>();
  const { data: results, isLoading, error } = useSearchSalesOrders(soNumber || '');

  if (!soNumber) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No SO number provided</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-gray-700">Failed to search</p>
        <p className="text-sm text-gray-500">{error.message}</p>
        <Link to="/" className="text-primary-600 hover:underline">
          ← Back to search
        </Link>
      </div>
    );
  }

  const soData = results?.[0];

  if (!soData) {
    return (
      <div className="max-w-4xl mx-auto px-6 py-12">
        <Link to="/" className="flex items-center text-gray-500 hover:text-gray-700 mb-6">
          <ChevronLeft className="h-5 w-5" />
          Back to search
        </Link>
        <div className="text-center py-12">
          <FolderOpen className="h-16 w-16 text-gray-300 mx-auto mb-4" />
          <p className="text-gray-500">No sales order found with number "{soNumber}"</p>
        </div>
      </div>
    );
  }

  const completedCount = Object.values(soData.checklist).filter(Boolean).length;
  const totalCount = Object.keys(soData.checklist).length;

  return (
    <div className="max-w-5xl mx-auto px-6 py-8">
      {/* Back link */}
      <Link to="/" className="flex items-center text-gray-500 hover:text-gray-700 mb-6">
        <ChevronLeft className="h-5 w-5" />
        Back to search
      </Link>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <FolderOpen className="h-8 w-8 text-primary-600" />
              SO-{soData.soNumber}
            </h1>
            <p className="text-gray-500 mt-1">
              {formatMonth(soData.soMonth)} • {soData.customerName}
            </p>
            <div className="mt-2">
              <Link
                to={`/cases/${soData.caseId}`}
                className="text-primary-600 hover:underline text-sm"
              >
                View Case: {soData.opportunityId} ({soData.caseId})
              </Link>
            </div>
          </div>

          <div className="text-right">
            <div
              className={`flex items-center gap-2 text-lg font-medium ${
                completedCount === totalCount ? 'text-green-600' : 'text-amber-600'
              }`}
            >
              {completedCount === totalCount ? (
                <CheckCircle2 className="h-6 w-6" />
              ) : (
                <Circle className="h-6 w-6" />
              )}
              <span>
                {completedCount}/{totalCount} Complete
              </span>
            </div>
          </div>
        </div>

        {/* Checklist */}
        <div className="flex flex-wrap gap-4 mt-6 pt-6 border-t border-gray-100">
          {SO_DOCUMENT_TYPES.map((type) => (
            <div
              key={type}
              className={`flex items-center gap-2 px-3 py-2 rounded-md ${
                soData.checklist[type as keyof typeof soData.checklist]
                  ? 'bg-green-50 text-green-700'
                  : 'bg-gray-50 text-gray-400'
              }`}
            >
              {soData.checklist[type as keyof typeof soData.checklist] ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : (
                <Circle className="h-5 w-5" />
              )}
              <span>{DOCUMENT_TYPE_LABELS[type]}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Folder Path */}
      <div className="bg-gray-50 rounded-lg p-4 mb-6">
        <p className="text-sm text-gray-500 mb-1">Storage Path:</p>
        <code className="text-sm text-gray-700">{soData.folderPath}</code>
      </div>

      {/* Documents */}
      <div className="bg-white rounded-lg border border-gray-200 p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Documents ({soData.documents.length})
        </h2>

        {soData.documents.length > 0 ? (
          <DocumentTable
            documents={soData.documents as Document[]}
            onView={(doc) => window.open(`/api/documents/${doc.id}/preview`, '_blank')}
          />
        ) : (
          <div className="text-center py-8 text-gray-400">
            No documents uploaded yet
          </div>
        )}
      </div>
    </div>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
}
