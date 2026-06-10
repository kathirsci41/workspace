import { requestJson } from './client';

export interface HealthResponse {
  status: string;
  service: string;
  ocr?: {
    provider?: string;
    model?: string;
    reachable?: boolean;
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

export function getHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/health');
}
