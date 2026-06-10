import type { DocumentType } from '../types/api';

export const DOCUMENT_TYPES: DocumentType[] = [
  'CUSTOMER_PO',
  'COMPANY_INVOICE',
  'COMPANY_DC',
  'COMPANY_PO',
  'VENDOR_INVOICE',
];

export const DOCUMENT_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  COMPANY_INVOICE: 'Company Invoice',
  COMPANY_DC: 'Company Delivery Challan / DC',
  COMPANY_PO: 'Company PO to Vendor',
  VENDOR_INVOICE: 'Vendor Invoice',
};

export function isDocumentType(value: string | null | undefined): value is DocumentType {
  return DOCUMENT_TYPES.includes(value as DocumentType);
}

export function documentTypeLabel(value: string | null | undefined): string {
  if (!value) {
    return '-';
  }
  return isDocumentType(value) ? DOCUMENT_TYPE_LABELS[value] : value.replace(/_/g, ' ');
}

export function guessDocumentType(filename: string): DocumentType | null {
  const lowerName = filename.toLowerCase();
  const normalized = lowerName.replace(/[^a-z0-9]+/g, ' ').trim();

  const hasVendor = hasWord(normalized, 'vendor');
  const hasCustomer = hasWord(normalized, 'customer');
  const hasPo = hasWord(normalized, 'po');

  if ((hasVendor && normalized.includes('bill')) || normalized.includes('vendor invoice')) {
    return 'VENDOR_INVOICE';
  }

  if ((hasVendor && hasPo) || (normalized.includes('purchase order') && hasVendor)) {
    return 'COMPANY_PO';
  }

  if (
    normalized.includes('delivery')
    || normalized.includes('challan')
    || hasWord(normalized, 'dc')
    || lowerName.includes('dnt')
  ) {
    return 'COMPANY_DC';
  }

  if ((hasCustomer && normalized.includes('invoice')) || normalized.includes('tax invoice')) {
    return 'COMPANY_INVOICE';
  }

  if ((hasCustomer && hasPo) || normalized.includes('customer order')) {
    return 'CUSTOMER_PO';
  }

  return null;
}

function hasWord(value: string, word: string): boolean {
  return value.split(/\s+/).includes(word);
}
