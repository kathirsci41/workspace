export { documentTypeLabel } from './documentTypes';

export function formatValue(value: unknown, fieldName = ''): string {
  if (value === undefined || value === null || value === '') return '-';
  if (typeof value === 'number') {
    return isCurrencyField(fieldName)
      ? new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
      : new Intl.NumberFormat('en-IN').format(value);
  }
  if (Array.isArray(value)) {
    return value.length ? value.map((entry) => formatValue(entry, fieldName)).join(', ') : '-';
  }
  if (typeof value === 'object') {
    return JSON.stringify(value);
  }
  return String(value);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-IN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

export function fieldLabel(value: string): string {
  const labels: Record<string, string> = {
    customer_po_no: 'Customer PO Number',
    customer_po_date: 'Customer PO Date',
    customer_order_no: 'Customer Order Number',
    po_reference: 'PO Reference',
    primary_ref_no: 'Primary Reference',
    invoice_no: 'Invoice Number',
    invoice_number: 'Invoice Number',
    invoice_date: 'Invoice Date',
    vendor_invoice_no: 'Vendor Invoice Number',
    vendor_invoice_date: 'Vendor Invoice Date',
    vendor_po_no: 'Vendor PO Number',
    vendor_po_date: 'Vendor PO Date',
    vendor_po_total: 'Vendor PO Total',
    vendor_invoice_total: 'Vendor Invoice Total',
    po_number: 'PO Number',
    po_date: 'PO Date',
    so_no: 'SO Number',
    so_number: 'SO Number',
    dc_no: 'Delivery Challan Number',
    dc_number: 'Delivery Challan Number',
    dc_date: 'Delivery Challan Date',
    customer_name: 'Customer Name',
    vendor_name: 'Vendor Name',
    taxable_amount: 'Taxable Amount',
    subtotal_amount: 'Subtotal Amount',
    tax_amount: 'Tax Amount',
    net_amount: 'Net Amount',
    total_amount: 'Total Amount',
    grand_total: 'Grand Total',
    invoice_total: 'Invoice Total',
    difference: 'Difference',
    estimated_amount: 'Delivery Challan Amount',
    total_quantity: 'Total Quantity',
    mode_of_bill: 'Mode of Billing',
    part_shipment_allowed: 'Partial Shipment',
    customer_address: 'Customer Address',
    billing_address: 'Billing Address',
    delivery_address: 'Delivery Address',
    bill_to_name: 'Bill To',
    ship_to_name: 'Ship To',
    vendor_gstin: 'Vendor GSTIN',
    gstin: 'GSTIN',
    irn: 'IRN',
    ack_no: 'Acknowledgement Number',
    extraction_source: 'Extraction Source',
  };
  if (labels[value]) return labels[value];
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .replace(/\bPo\b/g, 'PO')
    .replace(/\bSo\b/g, 'SO')
    .replace(/\bDc\b/g, 'DC')
    .replace(/\bGstin\b/g, 'GSTIN')
    .replace(/\bIrn\b/g, 'IRN');
}

function isCurrencyField(fieldName: string): boolean {
  return /amount|total|tax|net|subtotal|grand|billing|coverage|difference|delta/i.test(fieldName);
}
