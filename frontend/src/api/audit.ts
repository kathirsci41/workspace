import { requestJson } from './client';
import type { AuditEvent } from '../types/api';

export function listAuditEvents(bundleId: string): Promise<AuditEvent[]> {
  return requestJson<AuditEvent[]>(`/bundles/${bundleId}/audit-events`);
}
