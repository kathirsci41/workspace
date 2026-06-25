export type BundleStatus = 'OK' | 'REVIEW_REQUIRED' | 'MISMATCH' | 'MISSING_DOCUMENTS' | 'BLOCKED' | 'APPROVED' | 'CLOSED';
export type SectionStatus = 'PASS' | 'PARTIAL_PASS' | BundleStatus;
export type DocumentStatus = 'UPLOADED' | 'EXTRACTING' | 'PENDING_REVIEW' | 'VERIFIED' | 'EXTRACTION_FAILED' | 'REJECTED';
export type DocumentType = 'CUSTOMER_PO' | 'COMPANY_INVOICE' | 'COMPANY_DC' | 'COMPANY_PO' | 'VENDOR_INVOICE';
export type OcrRotationPreference = 'auto' | 0 | 90 | 180 | 270;

export interface FieldLocation {
  page: number | null;
  bbox: [number, number, number, number] | null;
  page_width?: number;
  page_height?: number;
  evidence_text: string | null;
  source: string;
  confidence: number | null;
}

export interface OrderBundle {
  id: string;
  bundle_number: string;
  customer_name: string | null;
  customer_po_no: string | null;
  so_no: string | null;
  status: BundleStatus | string;
  customer_delivery_status: SectionStatus | string;
  vendor_procurement_status: SectionStatus | string;
  computed_status?: BundleStatus | string | null;
  computed_customer_status?: SectionStatus | string | null;
  computed_vendor_status?: SectionStatus | string | null;
  status_computed_at?: string | null;
  dismissed_check_ids?: string[];
  created_at: string;
  updated_at: string;
}

export interface DocumentMetadata {
  id: string;
  document_id: string;
  status: string;
  extracted_data: Record<string, unknown>;
  diagnostics: Record<string, unknown>;
  field_confidences?: Record<string, number | null>;
  field_evidence?: Record<string, string | null>;
  field_locations?: Record<string, FieldLocation>;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  last_error: string | null;
}

export interface BundleDocument {
  id: string;
  order_bundle_id: string;
  document_type: DocumentType | string;
  filename: string;
  content_type: string | null;
  status: DocumentStatus | string;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  metadata: DocumentMetadata | null;
}

export type CheckSeverity = 'BLOCKER' | 'WARNING' | string;

export interface VerificationCheck {
  check_id: string;
  check_name: string;
  result: string;
  severity: CheckSeverity;
  left_document_type: string | null;
  left_document_id: string | null;
  left_value: unknown;
  right_document_type: string | null;
  right_document_id: string | null;
  right_value: unknown;
  message: string;
}

export interface VerificationIssue {
  code?: string;
  message?: string;
  document_id?: string | null;
  [key: string]: unknown;
}

export interface VerificationReference {
  label?: string;
  key?: string;
  value?: unknown;
  document_id?: string | null;
  document_type?: string | null;
  [key: string]: unknown;
}

export interface VerificationSummary {
  bundle_status: BundleStatus | string;
  customer_delivery_status: SectionStatus | string;
  vendor_procurement_status: SectionStatus | string;
  extracted_summary: Record<string, unknown>;
  connections?: Array<Record<string, unknown>>;
  checks: VerificationCheck[];
  issues: VerificationIssue[];
  documents?: Array<Record<string, unknown>>;
  references?: VerificationReference[];
  recommendation?: string | null;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  actor: string;
  document_id: string | null;
  order_bundle_id: string | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface ExtractionActivityJob {
  id: string;
  document_id: string;
  filename: string;
  provider: string;
  status: 'queued' | 'running' | string;
  stage: string;
  queued_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  queue_position: number | null;
  elapsed_ms: number;
}

export interface ExtractionActivityResponse {
  active: boolean;
  active_count: number;
  queue_count: number;
  active_jobs: ExtractionActivityJob[];
  queued_jobs: ExtractionActivityJob[];
}
