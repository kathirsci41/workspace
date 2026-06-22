import { apiUrl, requestJson } from './client';
import { debugLog } from './debugLog';
import type { BundleDocument, DocumentType, ExtractionActivityResponse, OcrRotationPreference } from '../types/api';

type DocumentMutationPayload = BundleDocument | {
  document?: BundleDocument;
  [key: string]: unknown;
};

function normalizeDocumentPayload(payload: DocumentMutationPayload): BundleDocument {
  return 'document' in payload && payload.document ? payload.document : payload as BundleDocument;
}

export function listBundleDocuments(bundleId: string): Promise<BundleDocument[]> {
  return requestJson<BundleDocument[]>(`/bundles/${bundleId}/documents`);
}

export function getDocument(documentId: string): Promise<BundleDocument> {
  return requestJson<BundleDocument>(`/documents/${documentId}`);
}

export async function uploadDocument(bundleId: string, documentType: DocumentType, file: File): Promise<BundleDocument> {
  debugLog('upload_started', { bundle_id: bundleId, document_type: documentType, filename: file.name });
  const form = new FormData();
  form.append('document_type', documentType);
  form.append('file', file);
  const response = await fetch(apiUrl(`/bundles/${bundleId}/documents`), { method: 'POST', body: form });
  if (!response.ok) {
    const text = await response.text();
    debugLog('api_request_failed', {
      method: 'POST',
      path: `/bundles/${bundleId}/documents`,
      status: response.status,
      request_id: response.headers.get('X-Request-ID'),
      error: text,
    });
    throw new Error(text);
  }
  const payload = await response.json();
  debugLog('upload_completed', { bundle_id: bundleId, document_id: payload.id, document_type: documentType });
  return payload;
}

const EXTRACTION_TIMEOUT_MS = 15 * 60 * 1000; // 15 minutes

export interface ExtractionRequestOptions {
  ocrRotationDegrees?: OcrRotationPreference;
}

function extractionRequestInit(options?: ExtractionRequestOptions): RequestInit & { timeoutMs: number } {
  const rotation = options?.ocrRotationDegrees;
  return {
    method: 'POST',
    timeoutMs: EXTRACTION_TIMEOUT_MS,
    body: JSON.stringify({
      ocr_rotation_degrees: rotation === undefined || rotation === 'auto' ? null : rotation,
    }),
  };
}

export function extractDocument(documentId: string, options?: ExtractionRequestOptions): Promise<BundleDocument> {
  debugLog('extraction_started', { document_id: documentId });
  return requestJson<DocumentMutationPayload>(`/documents/${documentId}/extract`, extractionRequestInit(options)).then((payload) => {
    debugLog('extraction_completed', { document_id: documentId });
    return normalizeDocumentPayload(payload);
  });
}

export function reextractDocument(documentId: string, options?: ExtractionRequestOptions): Promise<BundleDocument> {
  debugLog('extraction_started', { document_id: documentId, force: true });
  return requestJson<DocumentMutationPayload>(`/documents/${documentId}/re-extract`, extractionRequestInit(options)).then((payload) => {
    debugLog('extraction_completed', { document_id: documentId, force: true });
    return normalizeDocumentPayload(payload);
  });
}

export function getExtractionActivity(): Promise<ExtractionActivityResponse> {
  return requestJson<ExtractionActivityResponse>('/extractions/activity');
}

export function patchExtractedData(documentId: string, fields: Record<string, unknown>, reason: string): Promise<BundleDocument> {
  debugLog('manual_patch_started', { document_id: documentId, fields: Object.keys(fields), reason });
  return requestJson<DocumentMutationPayload>(`/documents/${documentId}/extracted-data`, {
    method: 'PATCH',
    body: JSON.stringify({ fields, actor: 'frontend', reason }),
  }).then((payload) => {
    debugLog('manual_patch_completed', { document_id: documentId, fields: Object.keys(fields), reason });
    return normalizeDocumentPayload(payload);
  });
}

export async function deleteDocument(documentId: string): Promise<void> {
  debugLog('document_delete_started', { document_id: documentId });
  const response = await fetch(apiUrl(`/documents/${documentId}`), { method: 'DELETE' });
  if (!response.ok) {
    const text = await response.text();
    debugLog('api_request_failed', {
      method: 'DELETE',
      path: `/documents/${documentId}`,
      status: response.status,
      request_id: response.headers.get('X-Request-ID'),
      error: text,
    });
    throw new Error(text || `Request failed: ${response.status}`);
  }
  debugLog('document_delete_completed', { document_id: documentId });
}

export function documentPreviewUrl(documentId: string): string {
  return apiUrl(`/documents/${documentId}/preview`);
}

export function documentPreviewPageUrl(documentId: string, page: number): string {
  return apiUrl(`/documents/${documentId}/preview/pages/${page}.png`);
}
