import { useQuery } from '@tanstack/react-query';
import { globalSearch } from '@/api/search';

export function useSearch(query: string, page = 1, per_page = 20) {
  return useQuery({
    queryKey: ['search', query, page, per_page],
    queryFn: () => globalSearch(query, page, per_page),
    enabled: query.length >= 2,
  });
}
