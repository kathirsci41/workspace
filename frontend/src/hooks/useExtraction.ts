import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMetadata,
  verifyMetadata,
  rejectMetadata,
  reExtract,
  getFieldTemplate,
  createManualEntry,
  saveCorrections,   // NEW
} from '@/api/extraction';
import type { FieldCorrection } from '@/types';

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

export function useFieldTemplate(docId: string, enabled = false) {
  return useQuery({
    queryKey: ['fieldTemplate', docId],
    queryFn: () => getFieldTemplate(docId),
    enabled: !!docId && enabled,
  });
}

export function useCreateManualEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => createManualEntry(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

// ── NEW Phase 8 ───────────────────────────────────────────────────
export function useSaveCorrections() {
  return useMutation({
    mutationFn: ({
      documentId,
      corrections,
    }: {
      documentId: string;
      corrections: FieldCorrection[];
    }) => saveCorrections(documentId, corrections),
    // No cache invalidation needed — corrections are fire-and-forget.
    // The verify mutation that calls this will handle the invalidation.
  });
}
