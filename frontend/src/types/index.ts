// ─── Enums as string unions ───

export type DocumentType =
  | 'CUSTOMER_PO'
  | 'VENDOR_DC'
  | 'VENDOR_INVOICE'
  | 'COMPANY_DC'
  | 'COMPANY_INVOICE'
  | 'POD';

export type DocumentStatus =
  | 'UPLOADED'
  | 'EXTRACTING'
  | 'PENDING_REVIEW'
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
  notes: string | null;
  created_at: string;
  updated_at: string;
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
  metadata: DocumentMetadata | null;
  created_at: string;
  updated_at: string;
}

export interface ChainSlot {
  status: string;
  document_id: string | null;
  ref_no: string | null;
  uploaded_at: string | null;
  confidence: number | null;
}

export interface ChainStatus {
  po_id: string;
  po_number: string;
  completeness_pct: number;
  chain: Record<string, ChainSlot | null>;
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
  'VENDOR_DC',
  'VENDOR_INVOICE',
  'COMPANY_DC',
  'COMPANY_INVOICE',
  'POD',
];

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  VENDOR_DC: 'Vendor DC',
  VENDOR_INVOICE: 'Vendor Invoice',
  COMPANY_DC: 'Company DC',
  COMPANY_INVOICE: 'Company Invoice',
  POD: 'POD',
};

export const DOC_TYPE_SHORT: Record<DocumentType, string> = {
  CUSTOMER_PO: 'PO',
  VENDOR_DC: 'V.DC',
  VENDOR_INVOICE: 'V.Inv',
  COMPANY_DC: 'C.DC',
  COMPANY_INVOICE: 'C.Inv',
  POD: 'POD',
};
