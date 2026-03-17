import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { uploadDocument, getDocument, deleteDocument, listDocuments } from '@/api/documents';
import type { DocumentType, DocumentStatus } from '@/types';

export function useDocumentsByStatus(status: DocumentStatus, page = 1, perPage = 50) {
  return useQuery({
    queryKey: ['documents', 'status', status, page],
    queryFn: () => listDocuments({ status }, page, perPage),
    staleTime: 10_000,
  });
}

export function useDocuments(
  filters?: {
    status?: string;
    document_type?: string;
    customer_id?: string;
    date_from?: string;
    date_to?: string;
  },
  page = 1,
  perPage = 50
) {
  return useQuery({
    queryKey: ['documents', 'list', filters, page],
    queryFn: () => listDocuments(filters, page, perPage),
    staleTime: 10_000,
  });
}

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
