import { debugLog } from './debugLog';

const configuredApiBaseUrl =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_ORDER_ASSURANCE_API_URL ??
  'http://127.0.0.1:8100/api';

export function normalizeApiBaseUrl(value: string): string {
  const normalized = value.trim().replace(/\/+$/, '');
  if (!normalized) return '/api';
  return normalized.endsWith('/api') ? normalized : `${normalized}/api`;
}

export const apiBaseUrl = normalizeApiBaseUrl(configuredApiBaseUrl);

export function apiUrl(path: string, baseUrl = apiBaseUrl): string {
  const base = normalizeApiBaseUrl(baseUrl);
  const normalizedPath = `/${path.replace(/^\/+/, '')}`.replace(/^\/api(?=\/|$)/, '');
  return `${base}${normalizedPath}`;
}

export async function getHealth(): Promise<{ status: string; service: string }> {
  const response = await fetch(apiUrl('/health'));
  if (!response.ok) {
    throw new Error(`Health check failed: ${response.status}`);
  }
  return response.json();
}

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers },
  });
  if (!response.ok) {
    const text = await response.text();
    debugLog('api_request_failed', {
      method: init?.method ?? 'GET',
      path,
      status: response.status,
      request_id: response.headers.get('X-Request-ID'),
      error: text,
    });
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json();
}
