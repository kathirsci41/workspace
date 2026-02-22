import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPurchaseOrders,
  getPurchaseOrder,
  createPO,
  deletePO,
  getChainStatus,
  getDocumentsForPO,
} from '@/api/purchaseOrders';

export function usePurchaseOrders(
  page = 1,
  per_page = 20,
  filters?: { customer_id?: string; status?: string; search?: string }
) {
  return useQuery({
    queryKey: ['purchaseOrders', page, per_page, filters],
    queryFn: () => getPurchaseOrders(page, per_page, filters),
  });
}

export function usePurchaseOrder(id: string) {
  return useQuery({
    queryKey: ['purchaseOrder', id],
    queryFn: () => getPurchaseOrder(id),
    enabled: !!id,
  });
}

export function useCreatePO() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createPO,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchaseOrders'] });
    },
  });
}

export function useDeletePO() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deletePO,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchaseOrders'] });
    },
  });
}

export function useChainStatus(poId: string) {
  return useQuery({
    queryKey: ['chainStatus', poId],
    queryFn: () => getChainStatus(poId),
    enabled: !!poId,
  });
}

export function useDocumentsForPO(poId: string) {
  return useQuery({
    queryKey: ['documents', poId],
    queryFn: () => getDocumentsForPO(poId),
    enabled: !!poId,
  });
}
