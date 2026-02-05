import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getCase, searchCases, createCase, updateCase } from '../api/cases';
import type { CreateCaseForm, Case } from '../types';

export function useCase(caseId: string) {
  return useQuery({
    queryKey: ['case', caseId],
    queryFn: () => getCase(caseId),
    enabled: !!caseId,
  });
}

export function useSearchCases(query: string) {
  return useQuery({
    queryKey: ['cases', 'search', query],
    queryFn: () => searchCases(query),
    enabled: query.length >= 2,
  });
}

export function useCreateCase() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: CreateCaseForm) => createCase(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] });
    },
  });
}

export function useUpdateCase(caseId: string) {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (data: Partial<Case>) => updateCase(caseId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['case', caseId] });
    },
  });
}
