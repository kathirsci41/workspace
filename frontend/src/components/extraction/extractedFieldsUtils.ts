export type RawFieldMeta = { source?: string; confidence?: number };

type FieldEntry = [string, unknown];

const CRITICAL_FIELDS_BY_DOC_TYPE: Record<string, readonly string[]> = {
  CUSTOMER_PO: ['customer_po_no', 'po_number', 'customer_po_date', 'customer_name', 'grand_total', 'subtotal_amount', 'tax_amount'],
  COMPANY_INVOICE: ['invoice_no', 'invoice_number', 'invoice_date', 'customer_order_no', 'so_no', 'so_number', 'net_amount', 'taxable_amount', 'tax_amount'],
  COMPANY_DC: ['dc_no', 'dc_number', 'dc_date', 'customer_order_no', 'so_no', 'so_number', 'total_quantity'],
  COMPANY_PO: ['vendor_po_no', 'vendor_po_date', 'vendor_name', 'net_amount', 'subtotal_amount', 'tax_amount'],
  VENDOR_INVOICE: ['vendor_invoice_no', 'vendor_invoice_date', 'vendor_name', 'po_reference', 'invoice_total', 'subtotal_amount', 'tax_amount'],
};

export function criticalFieldsForDocType(docType: string): ReadonlySet<string> {
  const keys = CRITICAL_FIELDS_BY_DOC_TYPE[docType.toUpperCase()];
  return keys ? new Set(keys) : new Set();
}

export function isNeedsReviewSource(source: string | undefined): boolean {
  if (!source) return false;
  return source === 'needs_review' || source.startsWith('suspicious_');
}

export function sourceLabel(source: string | undefined): string | null {
  if (!source) return null;
  if (source === 'needs_review') return 'Needs Review';
  if (source.startsWith('suspicious_')) return 'Suspicious';
  if (source === 'fallback_largest') return 'Estimated';
  if (source === 'filename_fallback') return 'From Filename';
  if (source === 'model_layer2') return 'AI Extracted';
  return null;
}

export function groupFieldsByDocType(
  fields: FieldEntry[],
  docType: string,
  rawFieldMeta: Record<string, RawFieldMeta>,
): Array<{ label: string; variant?: string; fields: FieldEntry[] }> {
  const criticalKeys = criticalFieldsForDocType(docType);
  const flagged = (field: string) => isNeedsReviewSource(rawFieldMeta[field]?.source);

  const groups = [
    { label: 'Needs Review', variant: 'warning', fields: fields.filter(([f]) => flagged(f)) },
    { label: 'Critical Fields', variant: 'critical', fields: fields.filter(([f]) => criticalKeys.size > 0 && criticalKeys.has(f) && !flagged(f)) },
    { label: 'Supporting Fields', variant: undefined, fields: fields.filter(([f]) => !criticalKeys.has(f) && !flagged(f)) },
  ];
  return groups.filter((g) => g.fields.length > 0);
}
