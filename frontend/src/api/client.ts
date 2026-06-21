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

export function extractErrorMessage(rawBody: string, status: number): string {
  if (rawBody) {
    try {
      const parsed = JSON.parse(rawBody);
      const detail = parsed?.detail ?? parsed?.message;
      if (typeof detail === 'string' && detail.trim()) return detail;
      if (Array.isArray(detail) && detail.length) {
        const first = detail[0];
        if (typeof first?.msg === 'string') return first.msg;
      }
    } catch {
      // not JSON — fall through to raw text
    }
    return rawBody;
  }
  return `Request failed: ${status}`;
}

export async function requestJson<T>(path: string, init?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs, ...fetchInit } = init ?? {};
  const signal = timeoutMs != null ? AbortSignal.timeout(timeoutMs) : undefined;
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...fetchInit,
      signal,
      headers: fetchInit?.body instanceof FormData ? fetchInit.headers : { 'Content-Type': 'application/json', ...fetchInit?.headers },
    });
  } catch (networkError) {
    debugLog('api_request_network_error', { method: init?.method ?? 'GET', path, error: String(networkError) });
    throw new Error('Unable to reach the server. Please check that the backend is running and try again.');
  }
  if (!response.ok) {
    const text = await response.text();
    debugLog('api_request_failed', {
      method: init?.method ?? 'GET',
      path,
      status: response.status,
      request_id: response.headers.get('X-Request-ID'),
      error: text,
    });
    throw new Error(extractErrorMessage(text, response.status));
  }
  return response.json();
}
