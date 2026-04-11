// ─── Enums as string unions ───

export type DocumentType =
  | 'CUSTOMER_PO'
  | 'COMPANY_PO'
  | 'VENDOR_DC'
  | 'VENDOR_INVOICE'
  | 'COMPANY_DC'
  | 'COMPANY_INVOICE';

export type DocumentStatus =
  | 'UPLOADED'
  | 'EXTRACTING'
  | 'PENDING_REVIEW'
  | 'PENDING_MODEL'
  | 'VERIFIED'
  | 'EXTRACTION_FAILED'
  | 'REJECTED';

export type POStatus =
  | 'INITIATED'
  | 'IN_PROGRESS'
  | 'NEAR_COMPLETE'
  | 'COMPLETE'
  | 'CANCELLED';

export type MetadataStatus =
  | 'PENDING'
  | 'EXTRACTED'
  | 'VERIFIED'
  | 'FAILED';

// ── NEW: extraction route from hybrid router ──────────────────────
export type ExtractionRoute = 'digital' | 'scanned' | null;

// ─── Data Interfaces ───

export interface Customer {
  id: string;
  customer_id: string;
  name: string;
  contact_email: string | null;
  gst_number: string | null;
  address: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  customer_id: string;
  customer_name?: string;
  customer_sky_id?: string;
  po_date: string | null;
  expected_delivery_date: string | null;
  total_amount: number | null;
  currency: string;
  status: POStatus;
  chain_completeness: number;
  so_number: string | null;
  notes: string | null;
  fulfillment_type: 'procurement' | 'stock';
  items_verified: boolean;
  order_scenario: 'unknown' | 'procurement' | 'stock' | 'drop_ship' | 'service_amc';
  gst_type: 'unknown' | 'igst' | 'cgst_sgst';
  invoice_split: boolean;
  manually_completed: boolean;
  completed_at: string | null;
  completion_note: string | null;
  billing_type?: 'full' | 'staged' | 'recurring';
  created_at: string;
  updated_at: string;
}

// Returned by the verify endpoint — extends DocumentMetadata with SO prompt fields
export interface VerifyResponse extends DocumentMetadata {
  requires_so_entry: boolean;
  verification_pending: boolean;   // true = doc stayed PENDING_REVIEW (SO not set yet)
  so_mismatch_message: string | null; // set when SO in doc doesn't match PO SO
  po_id: string | null;
  po_so_number: string | null;
}

export interface DocumentMetadata {
  id: string;
  document_id: string;
  document_type: DocumentType;
  extracted_data: Record<string, unknown> | null;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  doc_date: string | null;
  total_amount: number | null;
  confidence_score: number | null;
  status: MetadataStatus;
  extraction_attempts: number;
  last_error: string | null;
  extracted_at: string | null;
  verified_at: string | null;
  model_version: string | null;
  processing_time_ms: number | null;
  raw_ocr_text: string | null;

  // ── NEW Phase 5: per-field confidence scores from LayoutLMv3 ────
  field_confidences: Record<string, number> | null;

  // ── NEW Phase 7: extraction version (increments on re-extract) ───
  extraction_version: number | null;

  // ── NEW Phase 1: which pipeline processed this doc ───────────────
  extraction_route: ExtractionRoute;
}

export interface Document {
  id: string;
  po_id: string;
  document_type: DocumentType;
  original_filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  checksum: string;
  page_count: number | null;
  status: DocumentStatus;
  po_number: string;
  customer_name: string;
  po_so_number: string | null;
  metadata: DocumentMetadata | null;
  created_at: string;
  updated_at: string;
  days_pending?: number | null;
}

export interface ChainSlot {
  status: string;
  document_id: string | null;
  ref_no: string | null;
  uploaded_at: string | null;
  confidence: number | null;
  has_validation_errors?: boolean;
  required?: boolean;
  optional?: boolean;
  extraction_route?: ExtractionRoute;
  slot_message?: string | null;    // Why this slot is pending/failed
}

export interface ChainStatus {
  po_id: string;
  po_number: string;
  completeness_pct: number;
  chain: Record<string, ChainSlot[]>;
}

// ── NEW: correction payload sent to POST /corrections ────────────
export interface FieldCorrection {
  field: string;
  corrected_value: string | null;
}

export interface SearchResult {
  result_type: 'customer' | 'purchase_order' | 'document';
  id: string;
  ref_number: string;
  display_name: string;
  document_type: DocumentType | null;
  po_number: string | null;
  po_id?: string | null;
  customer_name: string | null;
  confidence: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

// ─── Ordered chain types ───

export const CHAIN_ORDER: DocumentType[] = [
  'CUSTOMER_PO',
  'COMPANY_PO',
  'VENDOR_DC',
  'VENDOR_INVOICE',
  'COMPANY_DC',
  'COMPANY_INVOICE',
];

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  COMPANY_PO: 'Company PO',
  VENDOR_DC: 'Vendor DC',
  VENDOR_INVOICE: 'Vendor Invoice',
  COMPANY_DC: 'Company DC',
  COMPANY_INVOICE: 'Company Invoice',
};

export const DOC_TYPE_SHORT: Record<DocumentType, string> = {
  CUSTOMER_PO: 'C.PO',
  COMPANY_PO: 'PO',
  VENDOR_DC: 'V.DC',
  VENDOR_INVOICE: 'V.Inv',
  COMPANY_DC: 'C.DC',
  COMPANY_INVOICE: 'C.Inv',
};

// PO Profile types

export interface POProfileDocument {
  document_id: string;
  status: string;
  filename: string | null;
  original_filename: string | null;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  doc_date: string | null;
  total_amount: number | null;
  confidence_score: number | null;
  field_confidences: Record<string, number> | null;
  extraction_route: string | null;
  extracted_data: Record<string, unknown> | null;
  verified_at: string | null;
  uploaded_at: string | null;
}

export interface POProfileDocumentSlot {
  document_type: string;
  status: string;  // 'empty' | 'not_applicable' | DocumentStatus value
  documents: POProfileDocument[];
  required: boolean;
  optional: boolean;
}

export interface POProfileDiscrepancy {
  type: string;
  doc_type: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface POProfileTimelineEvent {
  event_type: string;
  doc_type: string;
  timestamp: string;
  detail: string | null;
}

export interface FieldComparison {
  field_label: string;
  source_doc: string;
  source_value: string | null;
  compared_doc: string;
  compared_value: string | null;
  match: boolean | null;
  note: string | null;
}

export interface VendorGroup {
  vendor_po_ref: string;
  vendor_name: string | null;
  completeness_pct: number;
  slots: POProfileDocumentSlot[];
}

export interface ItemComparison {
  sr_no: string | null;
  description: string | null;
  part_no: string | null;
  source_doc: string;
  source_qty: number | null;
  compared_doc: string;
  compared_qty: number | null;
  qty_match: boolean | null;
  source_price?: number | null;
  compared_price?: number | null;
  price_match?: boolean | null;
}

export interface ItemMatch {
  sr_no: string | null;
  description: string | null;
  matched_part_no: string | null;
  confidence: number;
  match_type: 'exact' | 'ai' | 'unmatched';
}

export interface ParsedAddress {
  pin_code: string | null;
  city: string | null;
  state: string | null;
  full_address: string | null;
}

export interface POProfile {
  po_id: string;
  po_number: string;
  customer_name: string;
  customer_sky_id: string;
  so_number: string | null;
  po_date: string | null;
  total_amount: number | null;
  status: string;
  chain_completeness: number;
  chain_completeness_display: string | null;  // "72.5%" | "—" when scenario unknown
  fulfillment_type: 'procurement' | 'stock';
  order_scenario: 'unknown' | 'procurement' | 'stock' | 'drop_ship' | 'service_amc';
  gst_type: 'unknown' | 'igst' | 'cgst_sgst';
  invoice_split: boolean;
  manually_completed: boolean;
  completed_at: string | null;
  completion_note: string | null;
  created_at: string;
  slots: POProfileDocumentSlot[];
  timeline: POProfileTimelineEvent[];
  discrepancies: POProfileDiscrepancy[];
  cross_references: Record<string, string[]>;
  vendor_groups: VendorGroup[];
  items_verified: boolean;
  field_comparisons: FieldComparison[];
  item_comparisons: ItemComparison[];
  item_matches: ItemMatch[];
  delivery_address_parsed: ParsedAddress | null;
}
