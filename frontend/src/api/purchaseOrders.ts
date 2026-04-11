import client from './client';
import type { PurchaseOrder, PaginatedResponse, ChainStatus, Document, POProfile } from '@/types';

export async function getPurchaseOrders(
  page = 1,
  per_page = 20,
  filters?: {
    customer_id?: string;
    status?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    sort_order?: string;
    chain_filter?: string;
    missing_doc_type?: string;
  }
): Promise<PaginatedResponse<PurchaseOrder>> {
  const params: Record<string, unknown> = { page, per_page, ...filters };
  const { data } = await client.get('/api/v1/purchase-orders', { params });
  return data;
}

export async function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  const { data } = await client.get(`/api/v1/purchase-orders/${id}`);
  return data;
}

export async function createPO(body: {
  po_number: string;
  customer_id: string;
  po_date?: string;
  total_amount?: number;
  currency?: string;
  notes?: string;
}): Promise<PurchaseOrder> {
  const { data } = await client.post('/api/v1/purchase-orders', body);
  return data;
}

export async function updatePO(
  id: string,
  body: Partial<PurchaseOrder>
): Promise<PurchaseOrder> {
  const { data } = await client.patch(`/api/v1/purchase-orders/${id}`, body);
  return data;
}

export async function getChainStatus(poId: string): Promise<ChainStatus> {
  const { data } = await client.get(
    `/api/v1/purchase-orders/${poId}/chain-status`
  );
  return data;
}

export async function deletePO(id: string): Promise<void> {
  await client.delete(`/api/v1/purchase-orders/${id}`);
}

export async function closeOrder(id: string, note?: string): Promise<PurchaseOrder> {
  const { data } = await client.post(`/api/v1/purchase-orders/${id}/close`, { note: note ?? null });
  return data;
}

export async function getDocumentsForPO(poId: string): Promise<Document[]> {
  const { data } = await client.get(
    `/api/v1/purchase-orders/${poId}/documents`
  );
  return data.items ?? data;
}

export async function getPOProfile(poId: string): Promise<POProfile> {
  const { data } = await client.get(`/api/v1/purchase-orders/${poId}/profile`);
  return data;
}

export interface ChainStatusResponse {
  chain_status: 'incomplete' | 'complete' | 'verified' | 'mismatch';
  missing_slots: string[];
  missing_vendor_invoices: string[];
  reference_checks: Array<{
    document_type: string;
    check: string;
    result: 'pass' | 'mismatch' | 'skip';
  }>;
  billing: {
    overall: string;
    stages?: Array<{
      stage: number;
      expected_amount: number;
      invoiced_amount: number;
      status: string;
    }>;
  };
}

export async function getChainValidation(poId: string): Promise<ChainStatusResponse> {
  const { data } = await client.get(`/api/v1/purchase-orders/${poId}/chain`);
  return data;
}

export async function updateSoNumber(poId: string, soNumber: string): Promise<void> {
  await client.patch(`/api/v1/purchase-orders/${poId}/so-number`, { so_number: soNumber });
}

export async function exportPOAsExcel(
  poId: string,
  poNumber: string,
  mode: 'single' | 'separate' = 'separate'
): Promise<void> {
  const response = await client.get(
    `/api/v1/purchase-orders/${poId}/export?mode=${mode}`,
    { responseType: 'blob' }
  );
  const suffix = mode === 'single' ? '_consolidated' : '';
  const today = new Date().toISOString().split('T')[0];
  const url = window.URL.createObjectURL(response.data as Blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `PO_${poNumber}${suffix}_${today}.xlsx`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}
