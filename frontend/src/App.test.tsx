import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { App } from './App';
import { createBundle, getBundle, listBundles } from './api/bundles';
import { listAuditEvents } from './api/audit';
import {
  extractDocument,
  getDocument,
  listBundleDocuments,
  patchExtractedData,
  reextractDocument,
} from './api/documents';
import { exportVerificationReport } from './api/export';
import { getHealth } from './api/health';
import { getVerificationSummary } from './api/verification';
import type { AuditEvent, BundleDocument, OrderBundle, VerificationSummary } from './types/api';

vi.mock('./api/bundles', () => ({
  createBundle: vi.fn(),
  getBundle: vi.fn(),
  listBundles: vi.fn(),
}));

vi.mock('./api/documents', async () => {
  const actual = await vi.importActual<typeof import('./api/documents')>('./api/documents');
  return {
    ...actual,
    deleteDocument: vi.fn(),
    extractDocument: vi.fn(),
    getDocument: vi.fn(),
    listBundleDocuments: vi.fn(),
    patchExtractedData: vi.fn(),
    reextractDocument: vi.fn(),
    uploadDocument: vi.fn(),
  };
});

vi.mock('./api/verification', () => ({
  getVerificationSummary: vi.fn(),
}));

vi.mock('./api/audit', () => ({
  listAuditEvents: vi.fn(),
}));

vi.mock('./api/export', () => ({
  exportVerificationReport: vi.fn(),
}));

vi.mock('./api/health', () => ({
  getHealth: vi.fn(),
}));

const bundle: OrderBundle = {
  id: 'bundle-1',
  bundle_number: 'OA-001',
  customer_name: 'Panimalar Medical Hospital',
  customer_po_no: 'PMCH/024',
  so_no: '1OTM2526001611',
  status: 'REVIEW_REQUIRED',
  customer_delivery_status: 'MISMATCH',
  vendor_procurement_status: 'PASS',
  computed_status: 'MISMATCH',
  computed_customer_status: 'MISMATCH',
  computed_vendor_status: 'PASS',
  status_computed_at: '2026-02-13T10:00:00Z',
  created_at: '2026-02-13T09:00:00Z',
  updated_at: '2026-02-13T10:00:00Z',
};

const verifiedBundle: OrderBundle = {
  ...bundle,
  id: 'bundle-2',
  bundle_number: 'OA-002',
  status: 'OK',
  computed_status: 'OK',
  customer_delivery_status: 'PASS',
  vendor_procurement_status: 'PASS',
  computed_customer_status: 'PASS',
  computed_vendor_status: 'PASS',
};

const invoiceDocument: BundleDocument = {
  id: 'doc-invoice',
  order_bundle_id: 'bundle-1',
  document_type: 'COMPANY_INVOICE',
  filename: 'Customer Invoice 1ITR2526001878.pdf',
  content_type: 'application/pdf',
  status: 'PENDING_REVIEW',
  last_error: null,
  created_at: '2026-02-13T09:05:00Z',
  updated_at: '2026-02-13T09:20:00Z',
  metadata: {
    id: 'metadata-invoice',
    document_id: 'doc-invoice',
    status: 'EXTRACTED',
    extracted_data: {
      invoice_no: '1ITR2526001878',
      customer_order_no: 'PMCH/024',
      so_no: '1OTM2526001611',
      net_amount: 874439,
    },
    diagnostics: {
      page_count: 2,
      field_metadata: {
        invoice_no: { confidence: 0.92, source: 'digital_text' },
      },
    },
    field_confidences: { invoice_no: 0.92 },
    field_evidence: { invoice_no: 'Invoice No: 1ITR2526001878' },
    field_locations: {
      invoice_no: {
        page: 1,
        bbox: [10, 20, 120, 42],
        page_width: 800,
        page_height: 1000,
        evidence_text: 'Invoice No: 1ITR2526001878',
        source: 'digital_text',
        confidence: 0.92,
      },
    },
    primary_ref_no: '1ITR2526001878',
    po_ref_no: 'PMCH/024',
    last_error: null,
  },
};

const documents: BundleDocument[] = [
  invoiceDocument,
  {
    ...invoiceDocument,
    id: 'doc-dc',
    document_type: 'COMPANY_DC',
    filename: 'DC 1DNT2526DC3100.pdf',
    metadata: { ...invoiceDocument.metadata!, document_id: 'doc-dc', status: 'EXTRACTED', extracted_data: { dc_no: '1DNT2526DC3100' } },
  },
  {
    ...invoiceDocument,
    id: 'doc-vendor-po',
    document_type: 'COMPANY_PO',
    filename: 'Vendor PO 1PTR2526000467.pdf',
    metadata: { ...invoiceDocument.metadata!, document_id: 'doc-vendor-po', status: 'EXTRACTED', extracted_data: { vendor_po_no: '1PTR2526000467' } },
  },
  {
    ...invoiceDocument,
    id: 'doc-vendor-invoice',
    document_type: 'VENDOR_INVOICE',
    filename: 'Vendor Bill 2526PSI25087738.pdf',
    metadata: { ...invoiceDocument.metadata!, document_id: 'doc-vendor-invoice', status: 'EXTRACTED', extracted_data: { vendor_invoice_no: '2526PSI25087738' } },
  },
];

const summary: VerificationSummary = {
  bundle_status: 'MISMATCH',
  customer_delivery_status: 'MISMATCH',
  vendor_procurement_status: 'PASS',
  extracted_summary: {
    customer_po_no: 'PMCH/024',
    so_no: '1OTM2526001611',
    customer_name: 'Panimalar Medical Hospital',
    customer_invoice_numbers: ['1ITR2526001878'],
    dc_numbers: ['1DNT2526DC3100'],
    vendor_po_numbers: ['1PTR2526000467'],
    vendor_invoice_numbers: ['2526PSI25087738'],
    customer_total: 874439,
    vendor_total: 696200,
  },
  checks: [
    {
      check_id: 'INVOICE_DC_SO_MATCH',
      check_name: 'SO number matches between invoice and DC',
      result: 'MISMATCH',
      severity: 'BLOCKER',
      left_document_type: 'COMPANY_INVOICE',
      left_document_id: 'doc-invoice',
      left_value: '1OTM2526001611',
      right_document_type: 'COMPANY_DC',
      right_document_id: 'doc-dc',
      right_value: '1OTM2526009999',
      message: 'SO number matches between invoice and DC: values differ.',
    },
    {
      check_id: 'VENDOR_BILLING_COVERAGE',
      check_name: 'Vendor invoice total covers Vendor PO total',
      result: 'PASS',
      severity: 'BLOCKER',
      left_document_type: 'COMPANY_PO',
      left_document_id: 'doc-vendor-po',
      left_value: 696200,
      right_document_type: 'VENDOR_INVOICE',
      right_document_id: 'doc-vendor-invoice',
      right_value: 696200,
      message: 'Vendor billing coverage evaluated against matching invoice references.',
    },
  ],
  issues: [
    {
      code: 'CUSTOMER_PO_MISSING',
      message: 'Customer PO is absent or unreadable; invoice and DC checks were evaluated independently.',
      document_type: 'CUSTOMER_PO',
      document_id: null,
    },
  ],
  recommendation: 'Resolve blocking or mismatched document evidence before closure.',
};

const auditEvents: AuditEvent[] = [
  {
    id: 'audit-1',
    event_type: 'manual_extracted_data_patched',
    actor: 'frontend',
    document_id: 'doc-invoice',
    order_bundle_id: 'bundle-1',
    created_at: '2026-02-13T10:00:00Z',
    payload: {
      document_type: 'COMPANY_INVOICE',
      reason: 'corrected wrong value',
      changes: [{ field: 'so_no', old_value: '1OTM2526009999', new_value: '1OTM2526001611' }],
    },
  },
];

describe('Build 1 App', () => {
  beforeEach(() => {
    window.history.pushState({}, '', '/bundles');
    vi.mocked(listBundles).mockReset().mockResolvedValue([bundle, verifiedBundle]);
    vi.mocked(createBundle).mockReset().mockResolvedValue({ ...bundle, id: 'bundle-3', bundle_number: 'OA-003' });
    vi.mocked(getBundle).mockReset().mockResolvedValue(bundle);
    vi.mocked(listBundleDocuments).mockReset().mockResolvedValue(documents);
    vi.mocked(getDocument).mockReset().mockResolvedValue(invoiceDocument);
    vi.mocked(extractDocument).mockReset().mockResolvedValue(invoiceDocument);
    vi.mocked(reextractDocument).mockReset().mockResolvedValue(invoiceDocument);
    vi.mocked(patchExtractedData).mockReset().mockResolvedValue(invoiceDocument);
    vi.mocked(getVerificationSummary).mockReset().mockResolvedValue(summary);
    vi.mocked(listAuditEvents).mockReset().mockResolvedValue(auditEvents);
    vi.mocked(exportVerificationReport).mockReset().mockResolvedValue(undefined);
    vi.mocked(getHealth).mockReset().mockResolvedValue({
      status: 'ok',
      service: 'order-assurance',
      ocr: { provider: 'glm_ocr', model: 'glm-ocr:latest', reachable: false },
    });
  });

  it('renders the Build 1 bundle work queue from backend bundle data', async () => {
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Bundles' })).toBeInTheDocument();
    expect(screen.getByText('Total Bundles')).toBeInTheDocument();
    expect(screen.getAllByText('Needs Review').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Verified').length).toBeGreaterThan(0);
    expect(screen.getByText('Mismatches')).toBeInTheDocument();
    expect(screen.getByText('Missing Documents')).toBeInTheDocument();

    const row = screen.getByRole('row', { name: /OA-001/i });
    expect(within(row).getByText('Mismatch')).toBeInTheDocument();
    expect(within(row).getByRole('link', { name: 'Open Bundle OA-001' })).toHaveAttribute('href', '/bundles/bundle-1/overview');
  });

  it('creates a bundle with backend-supported fields and navigates to its workspace', async () => {
    render(<App />);

    await screen.findByRole('heading', { name: 'Bundles' });
    fireEvent.click(screen.getByRole('button', { name: 'Create Bundle' }));
    fireEvent.change(screen.getByLabelText('Bundle name'), { target: { value: 'OA-003' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create verification bundle' }));

    await waitFor(() => expect(createBundle).toHaveBeenCalledWith({ bundle_number: 'OA-003' }));
    await waitFor(() => expect(window.location.pathname).toBe('/bundles/bundle-3/overview'));
  });

  it('renders the canonical bundle overview route with bundle-scoped navigation', async () => {
    window.history.pushState({}, '', '/bundles/bundle-1/overview');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'OA-001' })).toBeInTheDocument();
    const workflow = screen.getByRole('navigation', { name: 'Bundle workflow' });
    expect(workflow.querySelector('a[href="/bundles/bundle-1/overview"]')).toBeInTheDocument();
    expect(workflow.querySelector('a[href="/bundles/bundle-1/documents"]')).toBeInTheDocument();
    expect(screen.queryByRole('complementary', { name: 'App navigation' })).not.toBeInTheDocument();
  });

  it('renders extraction review from a document-scoped path', async () => {
    window.history.pushState({}, '', '/bundles/bundle-1/extraction/doc-invoice');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Extraction Review' })).toBeInTheDocument();
    expect(screen.getByLabelText('Document selector')).toBeInTheDocument();
    expect(screen.getByAltText('PDF page 1 preview')).toHaveAttribute(
      'src',
      'http://127.0.0.1:8100/api/documents/doc-invoice/preview/pages/1.png',
    );
    expect(screen.getByText('Invoice Number')).toBeInTheDocument();
    expect(screen.getAllByText('1ITR2526001878').length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Correct Invoice Number' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Re-extract' })).toBeEnabled();
  });

  it('uses human document labels and separates document workflow statuses', async () => {
    window.history.pushState({}, '', '/bundles/bundle-1/documents');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Documents' })).toBeInTheDocument();
    expect(screen.queryByText('COMPANY_INVOICE')).not.toBeInTheDocument();
    expect(screen.queryByText('COMPANY_DC')).not.toBeInTheDocument();
    expect(screen.getAllByText('Document').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Extraction').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Review').length).toBeGreaterThan(0);
  });

  it('redirects the application root to the bundles work queue', async () => {
    window.history.pushState({}, '', '/');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Bundles' })).toBeInTheDocument();
    await waitFor(() => expect(window.location.pathname).toBe('/bundles'));
  });

  it('uses backend summary issues and missing document slots without duplicate check issues', async () => {
    window.history.pushState({}, '', '/bundles/bundle-1/issues');
    render(<App />);

    expect(await screen.findByRole('heading', { name: 'Open Issues' })).toBeInTheDocument();
    expect(screen.getAllByText('Customer PO Missing').length).toBeGreaterThan(0);
    expect(screen.queryByText('SO number differs between invoice and DC')).not.toBeInTheDocument();
    expect(screen.getByText('Missing Document: Customer PO')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Upload Customer PO' })).toHaveAttribute(
      'href',
      '/bundles/bundle-1/documents',
    );
  });

  it('paginates the bundle queue and hides known automated test bundles', async () => {
    const queueBundles = Array.from({ length: 12 }, (_, index) => ({
      ...bundle,
      id: `queue-${index}`,
      bundle_number: `OA-${String(index + 1).padStart(3, '0')}`,
      updated_at: new Date(Date.UTC(2026, 1, 13, 10, index)).toISOString(),
    }));
    vi.mocked(listBundles).mockResolvedValue([
      ...queueBundles,
      { ...bundle, id: 'smoke', bundle_number: 'UPLOAD-SMOKE-123' },
    ]);

    render(<App />);

    expect(await screen.findByText('Showing 1-10 of 12 bundles')).toBeInTheDocument();
    expect(screen.queryByText('UPLOAD-SMOKE-123')).not.toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Open Bundle/ })).toHaveLength(10);
    fireEvent.click(screen.getByRole('button', { name: 'Next page' }));
    expect(screen.getByText('Showing 11-12 of 12 bundles')).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /Open Bundle/ })).toHaveLength(2);
  });
});
