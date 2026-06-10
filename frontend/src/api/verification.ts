import { requestJson } from './client';
import type { VerificationSummary } from '../types/api';

export function getVerificationSummary(bundleId: string): Promise<VerificationSummary> {
  return requestJson<VerificationSummary>(`/bundles/${bundleId}/verification-summary`);
}
