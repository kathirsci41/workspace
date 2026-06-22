import { apiUrl, extractErrorMessage, requestJson } from './client';
import type { OrderBundle } from '../types/api';

export interface BundleCreatePayload {
  bundle_number: string;
  customer_name?: string;
  customer_po_no?: string;
  so_no?: string;
}

export function listBundles(): Promise<OrderBundle[]> {
  return requestJson<OrderBundle[]>('/bundles');
}

export function getBundle(bundleId: string): Promise<OrderBundle> {
  return requestJson<OrderBundle>(`/bundles/${bundleId}`);
}

export function createBundle(payload: BundleCreatePayload): Promise<OrderBundle> {
  return requestJson<OrderBundle>('/bundles', { method: 'POST', body: JSON.stringify(payload) });
}

export async function deleteBundle(bundleId: string): Promise<void> {
  const response = await fetch(apiUrl(`/bundles/${bundleId}`), { method: 'DELETE' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(extractErrorMessage(text, response.status));
  }
}
