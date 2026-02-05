import apiClient from './client';
import type { SalesOrder, CreateSOForm, SOSearchResult } from '../types';

function transformSalesOrder(data: Record<string, unknown>): SalesOrder {
  return {
    id: data.id as number,
    caseId: data.case_id as number,
    soNumber: data.so_number as string,
    soMonth: data.so_month as string,
    createdAt: data.created_at as string,
    updatedAt: data.updated_at as string,
    documentCount: data.document_count as number,
    checklist: data.checklist as SalesOrder['checklist'],
  };
}

export async function createSalesOrder(caseId: string, data: CreateSOForm): Promise<SalesOrder> {
  const response = await apiClient.post(`/cases/${caseId}/sales-orders`, {
    so_number: data.soNumber,
    so_month: data.soMonth,
  });
  return transformSalesOrder(response.data);
}

export async function getSalesOrders(caseId: string, month?: string): Promise<SalesOrder[]> {
  const response = await apiClient.get(`/cases/${caseId}/sales-orders`, {
    params: month ? { month } : undefined,
  });
  return response.data.map(transformSalesOrder);
}

export async function searchSalesOrders(soNumber: string): Promise<SOSearchResult[]> {
  const response = await apiClient.get('/sales-orders/search', {
    params: { so_number: soNumber },
  });
  
  return response.data.results.map((item: Record<string, unknown>) => ({
    soNumber: item.so_number,
    soMonth: item.so_month,
    caseId: item.case_id,
    opportunityId: item.opportunity_id,
    customerName: item.customer_name,
    documentCount: item.document_count,
    checklist: item.checklist,
    folderPath: item.folder_path,
    documents: (item.documents as Record<string, unknown>[]).map((doc) => ({
      id: doc.id,
      caseId: doc.case_id,
      salesOrderId: doc.sales_order_id,
      documentType: doc.document_type,
      filename: doc.filename,
      originalFilename: doc.original_filename,
      referenceNumber: doc.reference_number,
      storagePath: doc.storage_path,
      fileSize: doc.file_size,
      rotation: doc.rotation,
      uploadedAt: doc.uploaded_at,
      uploadedBy: doc.uploaded_by,
    })),
  }));
}

export async function getSalesOrder(soId: number): Promise<SalesOrder> {
  const response = await apiClient.get(`/sales-orders/${soId}`);
  return transformSalesOrder(response.data);
}
