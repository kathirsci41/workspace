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
