import client from './client';
import type { Customer, PaginatedResponse } from '@/types';

export async function getCustomers(
  page = 1,
  per_page = 20,
  search?: string
): Promise<PaginatedResponse<Customer>> {
  const params: Record<string, unknown> = { page, per_page };
  if (search) params.search = search;
  const { data } = await client.get('/api/v1/customers', { params });
  return data;
}

export async function getCustomer(id: string): Promise<Customer> {
  const { data } = await client.get(`/api/v1/customers/${id}`);
  return data;
}

export async function createCustomer(body: {
  customer_id: string;
  name: string;
  contact_email?: string;
  gst_number?: string;
}): Promise<Customer> {
  const { data } = await client.post('/api/v1/customers', body);
  return data;
}

export async function updateCustomer(
  id: string,
  body: Partial<{ name: string; contact_email: string; gst_number: string }>
): Promise<Customer> {
  const { data } = await client.patch(`/api/v1/customers/${id}`, body);
  return data;
}
