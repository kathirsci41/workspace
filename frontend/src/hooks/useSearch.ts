import { useQuery } from '@tanstack/react-query';
import { globalSearch, advancedSearch } from '@/api/search';

export function useSearch(query: string, page = 1, per_page = 20) {
  return useQuery({
    queryKey: ['search', query, page, per_page],
    queryFn: () => globalSearch(query, page, per_page),
    enabled: query.length >= 2,
  });
}

export function useAdvancedSearch(
  params: {
    invoice_no?: string;
    dc_no?: string;
    po_no?: string;
    so_no?: string;
    customer_name?: string;
    document_type?: string;
    date_from?: string;
    date_to?: string;
  },
  enabled: boolean
) {
  return useQuery({
    queryKey: ['advancedSearch', params],
    queryFn: () => advancedSearch(params),
    enabled,
  });
}

export function useAddressSearch(
  delivery_address: string,
  extra?: { customer_name?: string; document_type?: string },
  enabled = true
) {
  return useQuery({
    queryKey: ['addressSearch', delivery_address, extra],
    queryFn: () => advancedSearch({ delivery_address, ...extra }),
    enabled: enabled && delivery_address.length >= 3,
  });
}
