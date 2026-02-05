import { useState, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Upload,
  ChevronLeft,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { useCase } from '../../hooks/useCases';
import Sidebar from '../layout/Sidebar';
import CustomerPOSection from './CustomerPOSection';
import SalesOrderCard from './SalesOrderCard';
import Filters from './Filters';
import UploadModal from '../documents/UploadModal';
import CreateSOModal from '../sales-orders/CreateSOModal';
import PDFPreview from '../documents/PDFPreview';
import Button from '../common/Button';
import type { Document as DocType, SalesOrderWithDocuments } from '../../types';

export default function CasePage() {
  const { caseId } = useParams<{ caseId: string }>();
  const { data: caseData, isLoading, error, refetch } = useCase(caseId || '');

  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isCreateSOModalOpen, setIsCreateSOModalOpen] = useState(false);
  const [selectedSOId, setSelectedSOId] = useState<number | undefined>();
  const [previewDocument, setPreviewDocument] = useState<DocType | null>(null);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [monthFilter, setMonthFilter] = useState<string>('');

  const soCardRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  if (!caseId) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-500">No case ID provided</p>
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

  if (error || !caseData) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertCircle className="h-12 w-12 text-red-500" />
        <p className="text-gray-700">Failed to load case</p>
        <p className="text-sm text-gray-500">{error?.message}</p>
        <Link to="/" className="text-primary-600 hover:underline">
          ← Back to search
        </Link>
      </div>
    );
  }

  // Filter sales orders by month
  const filteredSalesOrders = monthFilter
    ? caseData.salesOrders.filter((so) => so.soMonth === monthFilter)
    : caseData.salesOrders;

  // Get unique months for filter
  const availableMonths = [...new Set(caseData.salesOrders.map((so) => so.soMonth))].sort();

  const handleSelectSO = (soId: number) => {
    setSelectedSOId(soId);
    // Scroll to the SO card
    const cardRef = soCardRefs.current.get(soId);
    if (cardRef) {
      cardRef.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const handleViewDocument = (doc: DocType) => {
    setPreviewDocument(doc);
  };

  const handleUploadSuccess = () => {
    setIsUploadModalOpen(false);
    refetch();
  };

  const handleCreateSOSuccess = () => {
    setIsCreateSOModalOpen(false);
    refetch();
  };

  return (
    <div className="flex h-[calc(100vh-73px)]">
      {/* Sidebar */}
      <Sidebar
        customerPo={caseData.customerPo}
        salesOrders={caseData.salesOrders}
        onAddSO={() => setIsCreateSOModalOpen(true)}
        onSelectSO={handleSelectSO}
        onViewCustomerPO={() => caseData.customerPo && handleViewDocument(caseData.customerPo)}
        selectedSOId={selectedSOId}
      />

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Link
                to="/"
                className="flex items-center text-gray-500 hover:text-gray-700"
              >
                <ChevronLeft className="h-5 w-5" />
              </Link>
              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {caseData.opportunityId} - {caseData.customerName}
                </h1>
                <p className="text-sm text-gray-500">
                  {caseData.caseId} • {caseData.caseType} •{' '}
                  <span
                    className={`${
                      caseData.status === 'OPEN'
                        ? 'text-green-600'
                        : caseData.status === 'IN_PROGRESS'
                        ? 'text-yellow-600'
                        : 'text-gray-600'
                    }`}
                  >
                    {caseData.status}
                  </span>
                </p>
              </div>
            </div>
            <Button onClick={() => setIsUploadModalOpen(true)}>
              <Upload className="h-4 w-4 mr-2" />
              Upload Document
            </Button>
          </div>
        </div>

        {/* Filters */}
        <Filters
          typeFilter={typeFilter}
          monthFilter={monthFilter}
          onTypeChange={setTypeFilter}
          onMonthChange={setMonthFilter}
          onClear={() => {
            setTypeFilter('');
            setMonthFilter('');
          }}
          availableMonths={availableMonths}
        />

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Customer PO Section */}
          <CustomerPOSection
            customerPo={caseData.customerPo}
            onView={handleViewDocument}
            onUpload={() => setIsUploadModalOpen(true)}
          />

          {/* Sales Orders */}
          <div className="mt-8">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Sales Orders</h2>
              <span className="text-sm text-gray-500">
                {filteredSalesOrders.length} of {caseData.salesOrders.length} orders
              </span>
            </div>

            {filteredSalesOrders.length === 0 ? (
              <div className="text-center py-12 bg-gray-50 rounded-lg border border-dashed border-gray-300">
                <p className="text-gray-500 mb-4">No sales orders found</p>
                <Button
                  variant="secondary"
                  onClick={() => setIsCreateSOModalOpen(true)}
                >
                  Create First Sales Order
                </Button>
              </div>
            ) : (
              <div className="space-y-4">
                {filteredSalesOrders.map((so) => (
                  <SalesOrderCard
                    key={so.id}
                    ref={(el) => {
                      if (el) soCardRefs.current.set(so.id, el);
                    }}
                    salesOrder={so}
                    isExpanded={selectedSOId === so.id}
                    onToggle={() =>
                      setSelectedSOId(selectedSOId === so.id ? undefined : so.id)
                    }
                    onViewDocument={handleViewDocument}
                    typeFilter={typeFilter}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* PDF Preview Panel */}
      {previewDocument && (
        <PDFPreview
          document={previewDocument}
          onClose={() => setPreviewDocument(null)}
          caseId={caseId}
        />
      )}

      {/* Modals */}
      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        caseId={caseId}
        salesOrders={caseData.salesOrders}
        onSuccess={handleUploadSuccess}
        onCreateSO={() => {
          setIsUploadModalOpen(false);
          setIsCreateSOModalOpen(true);
        }}
      />

      <CreateSOModal
        isOpen={isCreateSOModalOpen}
        onClose={() => setIsCreateSOModalOpen(false)}
        caseId={caseId}
        onSuccess={handleCreateSOSuccess}
      />
    </div>
  );
}
