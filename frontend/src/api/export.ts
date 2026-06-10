import { apiUrl } from './client';
import { debugLog } from './debugLog';

export async function exportVerificationReport(bundleId: string): Promise<void> {
  debugLog('export_started', { bundle_id: bundleId });
  const response = await fetch(apiUrl(`/bundles/${bundleId}/export.xlsx`));
  if (!response.ok) {
    const text = await response.text();
    debugLog('api_request_failed', {
      method: 'GET',
      path: `/bundles/${bundleId}/export.xlsx`,
      status: response.status,
      request_id: response.headers.get('X-Request-ID'),
      error: text,
    });
    throw new Error(text);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = contentDispositionFilename(response.headers.get('Content-Disposition'))
    ?? `order-assurance-${bundleId}-verification-report.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  debugLog('export_completed', { bundle_id: bundleId, size_bytes: blob.size });
}

export function contentDispositionFilename(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const encoded = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (encoded?.[1]) {
    return sanitizeDownloadName(decodeURIComponent(encoded[1].trim()));
  }
  const quoted = /filename="([^"]+)"/i.exec(header);
  if (quoted?.[1]) {
    return sanitizeDownloadName(quoted[1]);
  }
  const plain = /filename=([^;]+)/i.exec(header);
  if (plain?.[1]) {
    return sanitizeDownloadName(plain[1].trim());
  }
  return null;
}

function sanitizeDownloadName(filename: string): string | null {
  const value = filename.replace(/\\/g, '/').split('/').pop()?.trim();
  return value || null;
}
