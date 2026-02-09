import apiClient from './client';

// ── Types ────────────────────────────────────────────────────────────

export type ExtractionStatus = 'PENDING' | 'EXTRACTED' | 'VERIFIED' | 'FAILED';

export interface ExtractionResponse {
  metadata_id: number;
  status: ExtractionStatus;
  extracted_data: Record<string, unknown>;
  confidence_score: number | null;
  primary_ref_no: string | null;
  doc_date: string | null;
  message: string;
}

export interface MetadataResponse {
  id: number;
  document_id: number;
  document_path: string;
  doc_type: string;
  primary_ref_no: string | null;
  doc_date: string | null;
  extracted_data: Record<string, unknown>;
  confidence_score: number | null;
  status: ExtractionStatus;
  raw_ocr_text: string | null;
  extracted_at: string | null;
  verified_by: string | null;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface VerifyRequest {
  extracted_data: Record<string, unknown>;
  primary_ref_no?: string;
  doc_date?: string;
  verified_by: string;
}

// ── API calls ────────────────────────────────────────────────────────

/** Trigger AI metadata extraction for a document. */
export async function triggerExtraction(
  documentId: number,
  forceReExtract: boolean = false,
): Promise<ExtractionResponse> {
  const response = await apiClient.post(
    `/documents/${documentId}/extract`,
    { force_re_extract: forceReExtract },
  );
  return response.data;
}

/** Get existing metadata for a document. */
export async function getMetadata(
  documentId: number,
): Promise<MetadataResponse> {
  const response = await apiClient.get(
    `/documents/${documentId}/metadata`,
  );
  return response.data;
}

/** Verify (approve / edit) extracted metadata. */
export async function verifyMetadata(
  metadataId: number,
  request: VerifyRequest,
): Promise<MetadataResponse> {
  const response = await apiClient.put(
    `/metadata/${metadataId}/verify`,
    request,
  );
  return response.data;
}

/** Reject metadata and allow re-extraction. */
export async function rejectMetadata(
  metadataId: number,
): Promise<MetadataResponse> {
  const response = await apiClient.put(
    `/metadata/${metadataId}/reject`,
  );
  return response.data;
}

// ── Document Reference Search ────────────────────────────────────────

export interface DocRefSearchResult {
  metadata_id: number;
  document_id: number;
  doc_type: string;
  primary_ref_no: string | null;
  doc_date: string | null;
  extracted_data: Record<string, unknown>;
  confidence_score: number | null;
  status: ExtractionStatus;
  filename: string;
  matched_fields: string[];
  so_number: string | null;
  so_month: string | null;
  case_id: string | null;
  opportunity_id: string | null;
  customer_name: string | null;
}

/** Search documents by any extracted reference (invoice no, PO no, DC no, etc.). */
export async function searchByDocRef(
  query: string,
): Promise<DocRefSearchResult[]> {
  const response = await apiClient.get('/metadata/search', {
    params: { q: query },
  });
  return response.data.results;
}
