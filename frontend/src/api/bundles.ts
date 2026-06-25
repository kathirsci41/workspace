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

export function patchBundleStatus(bundleId: string, newStatus: string): Promise<OrderBundle> {
  return requestJson<OrderBundle>(`/bundles/${bundleId}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status: newStatus }),
  });
}

export function dismissCheck(bundleId: string, checkId: string): Promise<OrderBundle> {
  return requestJson<OrderBundle>(`/bundles/${bundleId}/dismiss-check/${encodeURIComponent(checkId)}`, { method: 'POST' });
}

export function undismissCheck(bundleId: string, checkId: string): Promise<OrderBundle> {
  return requestJson<OrderBundle>(`/bundles/${bundleId}/dismiss-check/${encodeURIComponent(checkId)}`, { method: 'DELETE' });
}

export async function deleteBundle(bundleId: string): Promise<void> {
  const response = await fetch(apiUrl(`/bundles/${bundleId}`), { method: 'DELETE' });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(extractErrorMessage(text, response.status));
  }
}
