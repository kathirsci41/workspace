import apiClient from './client';
import type { Document, DocumentType } from '../types';

function transformDocument(data: Record<string, unknown>): Document {
  return {
    id: data.id as number,
    caseId: data.case_id as number,
    salesOrderId: data.sales_order_id as number | null,
    documentType: data.document_type as DocumentType,
    filename: data.filename as string,
    originalFilename: data.original_filename as string,
    referenceNumber: data.reference_number as string | null,
    storagePath: data.storage_path as string,
    fileSize: data.file_size as number,
    rotation: data.rotation as number,
    uploadedAt: data.uploaded_at as string,
    uploadedBy: data.uploaded_by as string,
  };
}

export async function uploadDocument(
  caseId: string,
  documentType: DocumentType,
  file: File,
  salesOrderId?: number,
  referenceNumber?: string
): Promise<Document> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('document_type', documentType);
  if (salesOrderId) {
    formData.append('sales_order_id', salesOrderId.toString());
  }
  if (referenceNumber) {
    formData.append('reference_number', referenceNumber);
  }

  const response = await apiClient.post(`/cases/${caseId}/documents`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  
  return {
    id: response.data.id,
    caseId: 0,
    salesOrderId: salesOrderId || null,
    documentType,
    filename: response.data.filename,
    originalFilename: file.name,
    referenceNumber: referenceNumber || null,
    storagePath: response.data.storage_path,
    fileSize: file.size,
    rotation: 0,
    uploadedAt: new Date().toISOString(),
    uploadedBy: 'Anonymous',
  };
}

export async function getDocuments(
  caseId: string,
  salesOrderId?: number,
  documentType?: DocumentType,
  month?: string
): Promise<Document[]> {
  const response = await apiClient.get(`/cases/${caseId}/documents`, {
    params: {
      sales_order_id: salesOrderId,
      document_type: documentType,
      month,
    },
  });
  return response.data.map(transformDocument);
}

export async function getDocument(documentId: number): Promise<Document> {
  const response = await apiClient.get(`/documents/${documentId}`);
  return transformDocument(response.data);
}

export function getDocumentPreviewUrl(documentId: number): string {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  return `${baseUrl}/api/documents/${documentId}/preview`;
}

export function getDocumentDownloadUrl(documentId: number): string {
  const baseUrl = import.meta.env.VITE_API_URL || '';
  return `${baseUrl}/api/documents/${documentId}/download`;
}

export async function rotateDocument(documentId: number, degrees: number): Promise<{ rotation: number }> {
  const response = await apiClient.post(`/documents/${documentId}/rotate`, { degrees });
  return { rotation: response.data.new_rotation };
}

export async function deleteDocument(documentId: number): Promise<void> {
  await apiClient.delete(`/documents/${documentId}`);
}
