import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getMetadata, verifyMetadata, rejectMetadata, reExtract } from '@/api/extraction';

export function useMetadata(docId: string) {
  return useQuery({
    queryKey: ['metadata', docId],
    queryFn: () => getMetadata(docId),
    enabled: !!docId,
  });
}

export function useVerifyMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      editedData,
    }: {
      documentId: string;
      editedData: Record<string, unknown>;
    }) => verifyMetadata(documentId, editedData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useRejectMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => rejectMetadata(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useReExtract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => reExtract(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}
