import { useState, useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, AlertCircle, Plus } from 'lucide-react';
import Modal from '../common/Modal';
import Button from '../common/Button';
import { useUploadDocument } from '../../hooks/useDocuments';
import { DOCUMENT_TYPE_LABELS, DocumentType, SO_DOCUMENT_TYPES } from '../../types';
import type { SalesOrderWithDocuments } from '../../types';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  caseId: string;
  salesOrders: SalesOrderWithDocuments[];
  onSuccess: () => void;
  onCreateSO: () => void;
}

export default function UploadModal({
  isOpen,
  onClose,
  caseId,
  salesOrders,
  onSuccess,
  onCreateSO,
}: UploadModalProps) {
  const [documentType, setDocumentType] = useState<DocumentType>('CUSTOMER_PO');
  const [salesOrderId, setSalesOrderId] = useState<number | undefined>();
  const [referenceNumber, setReferenceNumber] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);

  const { mutate: uploadDocument, isPending } = useUploadDocument(caseId);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    if (acceptedFiles.length > 0) {
      const selectedFile = acceptedFiles[0];
      if (!selectedFile.name.toLowerCase().endsWith('.pdf')) {
        setError('Only PDF files are allowed');
        return;
      }
      setFile(selectedFile);
      setError(null);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    multiple: false,
  });

  const handleSubmit = () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    if (documentType !== 'CUSTOMER_PO' && !salesOrderId) {
      setError('Please select a Sales Order');
      return;
    }

    uploadDocument(
      {
        documentType,
        file,
        salesOrderId: documentType === 'CUSTOMER_PO' ? undefined : salesOrderId,
        referenceNumber: referenceNumber || undefined,
      },
      {
        onSuccess: () => {
          resetForm();
          onSuccess();
        },
        onError: (err) => {
          setError(err.message);
        },
      }
    );
  };

  const resetForm = () => {
    setDocumentType('CUSTOMER_PO');
    setSalesOrderId(undefined);
    setReferenceNumber('');
    setFile(null);
    setError(null);
  };

  const handleClose = () => {
    resetForm();
    onClose();
  };

  // Get storage path preview
  const getStoragePathPreview = () => {
    if (!file) return null;
    
    if (documentType === 'CUSTOMER_PO') {
      return `/nas/cases/${caseId}/CUSTOMER_PO/`;
    }
    
    const selectedSO = salesOrders.find((so) => so.id === salesOrderId);
    if (selectedSO) {
      return `/nas/cases/${caseId}/${selectedSO.soMonth}/SO-${selectedSO.soNumber}/${documentType}/`;
    }
    
    return null;
  };

  const isSORequired = documentType !== 'CUSTOMER_PO';

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Upload Document" size="lg">
      <div className="space-y-4">
        {/* Error message */}
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-50 text-red-700 rounded-md">
            <AlertCircle className="h-5 w-5 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Document Type */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Document Type
          </label>
          <select
            value={documentType}
            onChange={(e) => {
              setDocumentType(e.target.value as DocumentType);
              if (e.target.value === 'CUSTOMER_PO') {
                setSalesOrderId(undefined);
              }
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="CUSTOMER_PO">{DOCUMENT_TYPE_LABELS.CUSTOMER_PO}</option>
            {SO_DOCUMENT_TYPES.map((type) => (
              <option key={type} value={type}>
                {DOCUMENT_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </div>

        {/* Sales Order (hidden for Customer PO) */}
        {isSORequired && (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Sales Order <span className="text-red-500">*</span>
            </label>
            {salesOrders.length === 0 ? (
              <div className="p-4 bg-gray-50 rounded-md text-center">
                <p className="text-gray-500 mb-2">No sales orders available</p>
                <Button variant="secondary" size="sm" onClick={onCreateSO}>
                  <Plus className="h-4 w-4 mr-1" />
                  Create Sales Order
                </Button>
              </div>
            ) : (
              <select
                value={salesOrderId || ''}
                onChange={(e) => setSalesOrderId(Number(e.target.value) || undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="">Select a Sales Order...</option>
                {salesOrders.map((so) => (
                  <option key={so.id} value={so.id}>
                    SO-{so.soNumber} ({formatMonth(so.soMonth)})
                  </option>
                ))}
              </select>
            )}
          </div>
        )}

        {/* Reference Number */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Reference Number <span className="text-gray-400">(optional)</span>
          </label>
          <input
            type="text"
            value={referenceNumber}
            onChange={(e) => setReferenceNumber(e.target.value)}
            placeholder="e.g., INV-2026-001"
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
        </div>

        {/* File Dropzone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            File <span className="text-red-500">*</span>
          </label>
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
              isDragActive
                ? 'border-primary-500 bg-primary-50'
                : file
                ? 'border-green-500 bg-green-50'
                : 'border-gray-300 hover:border-gray-400'
            }`}
          >
            <input {...getInputProps()} />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileText className="h-8 w-8 text-green-600" />
                <div className="text-left">
                  <p className="font-medium text-gray-900">{file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.size / 1024).toFixed(1)} KB
                  </p>
                </div>
              </div>
            ) : (
              <>
                <Upload className="h-10 w-10 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-600">
                  Drag & drop a PDF file here, or click to select
                </p>
                <p className="text-sm text-gray-400 mt-1">Only PDF files are allowed</p>
              </>
            )}
          </div>
        </div>

        {/* Storage Path Preview */}
        {getStoragePathPreview() && (
          <div className="p-3 bg-gray-50 rounded-md">
            <p className="text-xs text-gray-500 mb-1">Storage Path:</p>
            <code className="text-sm text-gray-700">{getStoragePathPreview()}</code>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-4 border-t">
          <Button variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} isLoading={isPending}>
            Upload Document
          </Button>
        </div>
      </div>
    </Modal>
  );
}

function formatMonth(monthStr: string): string {
  const [year, month] = monthStr.split('-');
  const date = new Date(parseInt(year), parseInt(month) - 1);
  return date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
}
