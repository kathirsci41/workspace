import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getSalesOrders, createSalesOrder, searchSalesOrders } from '../api/salesOrders';
import type { CreateSOForm } from '../types';

export function useSalesOrders(caseId: string, month?: string) {
  return useQuery({
    queryKey: ['salesOrders', caseId, month],
    queryFn: () => getSalesOrders(caseId, month),
    enabled: !!caseId,
  });
}

export function useSearchSalesOrders(soNumber: string) {
  return useQuery({
    queryKey: ['salesOrders', 'search', soNumber],
    queryFn: () => searchSalesOrders(soNumber),
    enabled: soNumber.length >= 3,
  });
}

export function useCreateSalesOrder(caseId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateSOForm) => createSalesOrder(caseId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      queryClient.invalidateQueries({ queryKey: ['salesOrders', caseId] });
    },
  });
}
