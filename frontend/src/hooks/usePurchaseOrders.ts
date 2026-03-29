import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getPurchaseOrders,
  getPurchaseOrder,
  createPO,
  updatePO,
  deletePO,
  getChainStatus,
  getDocumentsForPO,
  getPOProfile,
} from '@/api/purchaseOrders';
import type { PurchaseOrder } from '@/types';

export function usePurchaseOrders(
  page = 1,
  per_page = 20,
  filters?: {
    customer_id?: string;
    status?: string;
    search?: string;
    date_from?: string;
    date_to?: string;
    sort_by?: string;
    sort_order?: string;
    chain_filter?: string;
    missing_doc_type?: string;
  }
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

export function useUpdatePO() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<PurchaseOrder> }) =>
      updatePO(id, body),
    onSuccess: (_data, { id }) => {
      queryClient.invalidateQueries({ queryKey: ['purchaseOrder', id] });
      queryClient.invalidateQueries({ queryKey: ['purchaseOrders'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus', id] });
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

export function usePOProfile(poId: string, enabled: boolean = true) {
  return useQuery({
    queryKey: ['poProfile', poId],
    queryFn: () => getPOProfile(poId),
    enabled: !!poId && enabled,
    staleTime: 30_000,
  });
}
