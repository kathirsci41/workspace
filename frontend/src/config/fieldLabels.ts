/**
 * Human-readable labels for each extracted field, keyed by document type.
 * Used in the ReviewModal to display friendly names instead of raw keys.
 */
export const FIELD_LABELS: Record<string, Record<string, string>> = {
  CUSTOMER_PO: {
    ref_no: 'Reference No',
    po_no: 'PO Number',
    reference_no: 'Quotation / Additional Ref No',
    po_date: 'PO Date',
  },
  VENDOR_INVOICE: {
    invoice_no: 'Invoice Number',
    our_order: 'Our Order Ref',
    invoice_date: 'Invoice Date',
    customer: 'Customer Name',
    def_pmnt: 'Payment Terms',
    ack_no: 'Acknowledgement No (IRN)',
    ack_date: 'Acknowledgement Date',
    customer_po_no: 'Customer PO Number',
  },
  VENDOR_DC: {
    dc_no: 'DC Number',
    customer_order_no: 'Customer Order No',
    dc_date: 'DC Date',
    so_no: 'Sales Order No',
  },
  COMPANY_INVOICE: {
    invoice_no: 'Invoice Number',
    customer_order_no: 'Customer Order No',
    so_no: 'Sales Order No',
    invoice_date: 'Invoice Date',
    customer_order_date: 'Customer Order Date',
    acct_manager: 'Account Manager',
  },
  COMPANY_DC: {
    dc_no: 'DC Number',
    customer_order_no: 'Customer Order No',
    dc_date: 'DC Date',
    so_no: 'Sales Order No',
  },
  POD: {
    pod_no: 'POD / Receipt Number',
    delivery_date: 'Delivery Date',
    receiver_name: 'Received By',
    dc_ref_no: 'DC Reference No',
    so_no: 'Sales Order No',
  },
  PURCHASE_BILL: {
    purchase_bill_no: 'Purchase Bill No',
    po_no: 'PO Number',
    bill_no: 'Bill Number',
    date: 'Date',
    due_date: 'Due Date',
    bill_date: 'Bill Date',
  },
};
