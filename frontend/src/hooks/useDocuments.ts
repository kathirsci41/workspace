import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  getDocuments, 
  uploadDocument, 
  rotateDocument, 
  deleteDocument 
} from '../api/documents';
import type { DocumentType } from '../types';

export function useDocuments(
  caseId: string,
  salesOrderId?: number,
  documentType?: DocumentType,
  month?: string
) {
  return useQuery({
    queryKey: ['documents', caseId, salesOrderId, documentType, month],
    queryFn: () => getDocuments(caseId, salesOrderId, documentType, month),
    enabled: !!caseId,
  });
}

export function useUploadDocument(caseId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({
      documentType,
      file,
      salesOrderId,
      referenceNumber,
    }: {
      documentType: DocumentType;
      file: File;
      salesOrderId?: number;
      referenceNumber?: string;
    }) => uploadDocument(caseId, documentType, file, salesOrderId, referenceNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
    },
  });
}

export function useRotateDocument(caseId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: ({ documentId, degrees }: { documentId: number; degrees: number }) =>
      rotateDocument(documentId, degrees),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
    },
  });
}

export function useDeleteDocument(caseId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (documentId: number) => deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
      queryClient.invalidateQueries({ queryKey: ['documents', caseId] });
    },
  });
}
