import client from './client';
import type { SearchResponse } from '@/types';

export async function globalSearch(
  query: string,
  page = 1,
  per_page = 20
): Promise<SearchResponse> {
  const { data } = await client.get('/api/v1/search', {
    params: { q: query, page, per_page },
  });
  return data;
}

export async function advancedSearch(params: {
  delivery_address?: string;
  customer_name?: string;
  invoice_no?: string;
  dc_no?: string;
  po_no?: string;
  so_no?: string;
  document_type?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  per_page?: number;
}): Promise<SearchResponse> {
  const { data } = await client.get('/api/v1/search/advanced', { params });
  return data;
}
