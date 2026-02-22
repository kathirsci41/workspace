import client from './client';
import type { PurchaseOrder, PaginatedResponse, ChainStatus, Document } from '@/types';

export async function getPurchaseOrders(
  page = 1,
  per_page = 20,
  filters?: { customer_id?: string; status?: string; search?: string }
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

export async function getDocumentsForPO(poId: string): Promise<Document[]> {
  const { data } = await client.get(
    `/api/v1/purchase-orders/${poId}/documents`
  );
  return data.items ?? data;
}
