// Document types
export type DocumentType =
  | 'CUSTOMER_PO'
  | 'VENDOR_INVOICE'
  | 'VENDOR_DC'
  | 'COMPANY_INVOICE'
  | 'COMPANY_DC'
  | 'POD';

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  VENDOR_INVOICE: 'Vendor Invoice',
  VENDOR_DC: 'Vendor DC',
  COMPANY_INVOICE: 'Company Invoice',
  COMPANY_DC: 'Company DC',
  POD: 'Proof of Delivery',
};

export const SO_DOCUMENT_TYPES: DocumentType[] = [
  'VENDOR_INVOICE',
  'VENDOR_DC',
  'COMPANY_INVOICE',
  'COMPANY_DC',
  'POD',
];

// Case types
export type CaseType = 'HARDWARE' | 'SERVICES';
export type CaseStatus = 'OPEN' | 'IN_PROGRESS' | 'CLOSED';

export interface Case {
  id: number;
  caseId: string;
  opportunityId: string;
  customerName: string;
  caseType: CaseType;
  status: CaseStatus;
  notes: string | null;
  createdAt: string;
  updatedAt: string;
}

// Sales Order types
export interface SalesOrderChecklist {
  VENDOR_INVOICE: boolean;
  VENDOR_DC: boolean;
  COMPANY_INVOICE: boolean;
  COMPANY_DC: boolean;
  POD: boolean;
}

export interface SalesOrder {
  id: number;
  caseId: number;
  soNumber: string;
  soMonth: string; // "2026-01" - FIXED at creation
  createdAt: string;
  updatedAt: string;
  documentCount: number;
  checklist: SalesOrderChecklist;
}

export interface SalesOrderWithDocuments extends SalesOrder {
  documents: Document[];
}

// Document types
export interface Document {
  id: number;
  caseId: number;
  salesOrderId: number | null; // null ONLY for Customer PO
  documentType: DocumentType;
  filename: string;
  originalFilename: string;
  referenceNumber: string | null;
  storagePath: string;
  fileSize: number;
  rotation: number;
  uploadedAt: string;
  uploadedBy: string;
}

// Case with full details
export interface CaseWithDetails extends Case {
  customerPo: Document | null;
  salesOrders: SalesOrderWithDocuments[];
}

// SO Search Result
export interface SOSearchResult {
  soNumber: string;
  soMonth: string;
  caseId: string;
  opportunityId: string;
  customerName: string;
  documentCount: number;
  checklist: SalesOrderChecklist;
  folderPath: string;
  documents: Document[];
}

// API Response types
export interface SearchResponse<T> {
  results: T[];
  type: string;
}

export interface StatsResponse {
  cases: {
    total: number;
    open: number;
    in_progress: number;
    closed: number;
  };
  sales_orders: {
    total: number;
  };
  documents: {
    total: number;
    by_type: Record<string, number>;
    total_size_bytes: number;
    total_size_mb: number;
    recent_uploads_7d: number;
  };
}

export interface AuditLog {
  id: number;
  caseId: number | null;
  documentId: number | null;
  salesOrderId: number | null;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  createdAt: string;
}

export interface AuditLogsResponse {
  total: number;
  limit: number;
  offset: number;
  logs: AuditLog[];
}

// Form types
export interface CreateCaseForm {
  opportunityId: string;
  customerName: string;
  caseType: CaseType;
  notes?: string;
}

export interface CreateSOForm {
  soNumber: string;
  soMonth: string;
}

export interface UploadDocumentForm {
  documentType: DocumentType;
  salesOrderId?: number;
  referenceNumber?: string;
  file: File;
}
