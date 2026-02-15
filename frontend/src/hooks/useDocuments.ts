import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadDocument, getDocument, deleteDocument } from '@/api/documents';
import type { DocumentType } from '@/types';

export function useUploadDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      poId,
      file,
      documentType,
    }: {
      poId: string;
      file: File;
      documentType: DocumentType;
    }) => uploadDocument(poId, file, documentType),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: ['documents', variables.poId],
      });
      queryClient.invalidateQueries({
        queryKey: ['chainStatus', variables.poId],
      });
    },
  });
}

export function useDocument(id: string) {
  return useQuery({
    queryKey: ['document', id],
    queryFn: () => getDocument(id),
    enabled: !!id,
  });
}

export function useDeleteDocument() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
    },
  });
}
