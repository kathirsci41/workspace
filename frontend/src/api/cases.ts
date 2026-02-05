import apiClient from './client';
import type { Case, CaseWithDetails, CreateCaseForm, SearchResponse } from '../types';

// Transform snake_case to camelCase for case responses
function transformCase(data: Record<string, unknown>): Case {
  return {
    id: data.id as number,
    caseId: data.case_id as string,
    opportunityId: data.opportunity_id as string,
    customerName: data.customer_name as string,
    caseType: data.case_type as Case['caseType'],
    status: data.status as Case['status'],
    notes: data.notes as string | null,
    createdAt: data.created_at as string,
    updatedAt: data.updated_at as string,
  };
}

export async function createCase(data: CreateCaseForm): Promise<Case> {
  const response = await apiClient.post('/cases', {
    opportunity_id: data.opportunityId,
    customer_name: data.customerName,
    case_type: data.caseType,
    notes: data.notes,
  });
  return transformCase(response.data);
}

export async function getCase(caseId: string): Promise<CaseWithDetails> {
  const response = await apiClient.get(`/cases/${caseId}`);
  const data = response.data;
  
  return {
    id: data.id,
    caseId: data.case_id,
    opportunityId: data.opportunity_id,
    customerName: data.customer_name,
    caseType: data.case_type,
    status: data.status,
    notes: data.notes,
    createdAt: data.created_at,
    updatedAt: data.updated_at,
    customerPo: data.customer_po ? transformDocument(data.customer_po) : null,
    salesOrders: data.sales_orders.map(transformSalesOrderWithDocs),
  };
}

export async function searchCases(query: string): Promise<Case[]> {
  const response = await apiClient.get<SearchResponse<Record<string, unknown>>>('/search', {
    params: { q: query, type: 'opportunity' },
  });
  return response.data.results.map(transformCase);
}

export async function updateCase(caseId: string, data: Partial<Case>): Promise<Case> {
  const response = await apiClient.patch(`/cases/${caseId}`, {
    customer_name: data.customerName,
    case_type: data.caseType,
    status: data.status,
    notes: data.notes,
  });
  return transformCase(response.data);
}

// Helper functions for transforming nested data
function transformDocument(data: Record<string, unknown>) {
  return {
    id: data.id as number,
    caseId: data.case_id as number,
    salesOrderId: data.sales_order_id as number | null,
    documentType: data.document_type as string,
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

function transformSalesOrderWithDocs(data: Record<string, unknown>) {
  return {
    id: data.id as number,
    caseId: data.case_id as number,
    soNumber: data.so_number as string,
    soMonth: data.so_month as string,
    createdAt: data.created_at as string,
    updatedAt: data.updated_at as string,
    documentCount: data.document_count as number,
    checklist: data.checklist as Record<string, boolean>,
    documents: (data.documents as Record<string, unknown>[]).map(transformDocument),
  };
}
