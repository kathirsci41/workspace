import { forwardRef } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FolderOpen,
  CheckCircle2,
  Circle,
} from 'lucide-react';
import DocumentTable from './DocumentTable';
import type { SalesOrderWithDocuments, Document } from '../../types';
import { SO_DOCUMENT_TYPES, DOCUMENT_TYPE_LABELS } from '../../types';

interface SalesOrderCardProps {
  salesOrder: SalesOrderWithDocuments;
  isExpanded: boolean;
  onToggle: () => void;
  onViewDocument: (doc: Document) => void;
  typeFilter?: string;
}

const SalesOrderCard = forwardRef<HTMLDivElement, SalesOrderCardProps>(
  ({ salesOrder, isExpanded, onToggle, onViewDocument, typeFilter }, ref) => {
    const completedCount = Object.values(salesOrder.checklist).filter(Boolean).length;
    const totalCount = Object.keys(salesOrder.checklist).length;
    const isComplete = completedCount === totalCount;

    // Filter documents by type if filter is set
    const filteredDocuments = typeFilter
      ? salesOrder.documents.filter((doc) => doc.documentType === typeFilter)
      : salesOrder.documents;

    return (
      <div
        ref={ref}
        className={`bg-white rounded-lg border ${
          isExpanded ? 'border-primary-300 ring-1 ring-primary-100' : 'border-gray-200'
        }`}
      >
        {/* Header */}
        <button
          onClick={onToggle}
          className="w-full px-4 py-3 flex items-center justify-between hover:bg-gray-50 rounded-t-lg"
        >
          <div className="flex items-center gap-3">
            {isExpanded ? (
              <ChevronDown className="h-5 w-5 text-gray-500" />
            ) : (
              <ChevronRight className="h-5 w-5 text-gray-500" />
            )}
            <FolderOpen className="h-5 w-5 text-primary-600" />
            <div className="text-left">
              <span className="font-medium text-gray-900">
                SO-{salesOrder.soNumber}
              </span>
              <span className="ml-2 text-sm text-gray-500">
                ({formatMonth(salesOrder.soMonth)})
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Completion status */}
            <div
              className={`flex items-center gap-1 text-sm ${
                isComplete ? 'text-green-600' : 'text-amber-600'
              }`}
            >
              {isComplete ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <Circle className="h-4 w-4" />
              )}
              <span>
                {completedCount}/{totalCount}
              </span>
            </div>
          </div>
        </button>

        {/* Expanded Content */}
        {isExpanded && (
          <div className="border-t border-gray-100 p-4">
            {/* Checklist */}
            <div className="flex flex-wrap gap-3 mb-4 pb-4 border-b border-gray-100">
              {SO_DOCUMENT_TYPES.map((type) => (
                <div
                  key={type}
                  className={`flex items-center gap-1 text-sm ${
                    salesOrder.checklist[type as keyof typeof salesOrder.checklist]
                      ? 'text-green-600'
                      : 'text-gray-400'
                  }`}
                >
                  {salesOrder.checklist[type as keyof typeof salesOrder.checklist] ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <Circle className="h-4 w-4" />
                  )}
                  <span>{getShortLabel(type)}</span>
                </div>
              ))}
            </div>

            {/* Documents Table */}
            {filteredDocuments.length > 0 ? (
              <DocumentTable
                documents={filteredDocuments}
                onView={onViewDocument}
              />
            ) : (
              <p className="text-center text-gray-400 py-4">
                No documents {typeFilter ? `of type "${DOCUMENT_TYPE_LABELS[typeFilter as keyof typeof DOCUMENT_TYPE_LABELS]}"` : ''}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }
);

SalesOrderCard.displayName = 'SalesOrderCard';

export default SalesOrderCard;

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}

function getShortLabel(type: string): string {
  const shortLabels: Record<string, string> = {
    VENDOR_INVOICE: 'VI',
    VENDOR_DC: 'VD',
    COMPANY_INVOICE: 'CI',
    COMPANY_DC: 'CD',
    POD: 'POD',
  };
  return shortLabels[type] || type;
}
