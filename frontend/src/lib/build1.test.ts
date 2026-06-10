import { describe, expect, it } from 'vitest';
import {
  REQUIRED_DOCUMENT_SLOTS,
  buildDocumentSlots,
  bundleQueueMetrics,
  checkCategory,
  deriveIssues,
  extractionProgress,
  checkDisplayMessage,
  checkDisplayName,
  isAutomatedTestBundle,
  statusLabel,
  verificationMetrics,
} from './build1';
import type { BundleDocument, OrderBundle, VerificationSummary } from '../types/api';

const bundles: OrderBundle[] = [
  {
    id: 'bundle-1',
    bundle_number: 'OA-001',
    customer_name: null,
    customer_po_no: null,
    so_no: null,
    status: 'REVIEW_REQUIRED',
    customer_delivery_status: 'PASS',
    vendor_procurement_status: 'REVIEW_REQUIRED',
    computed_status: 'REVIEW_REQUIRED',
    created_at: '2026-02-13T09:00:00Z',
    updated_at: '2026-02-13T09:10:00Z',
  },
  {
    id: 'bundle-2',
    bundle_number: 'OA-002',
    customer_name: null,
    customer_po_no: null,
    so_no: null,
    status: 'OK',
    customer_delivery_status: 'PASS',
    vendor_procurement_status: 'PASS',
    computed_status: 'OK',
    created_at: '2026-02-13T09:00:00Z',
    updated_at: '2026-02-13T09:10:00Z',
  },
  {
    id: 'bundle-3',
    bundle_number: 'OA-003',
    customer_name: null,
    customer_po_no: null,
    so_no: null,
    status: 'MISSING_DOCUMENTS',
    customer_delivery_status: 'MISSING_DOCUMENTS',
    vendor_procurement_status: 'PASS',
    computed_status: 'MISSING_DOCUMENTS',
    created_at: '2026-02-13T09:00:00Z',
    updated_at: '2026-02-13T09:10:00Z',
  },
  {
    id: 'bundle-4',
    bundle_number: 'OA-004',
    customer_name: null,
    customer_po_no: null,
    so_no: null,
    status: 'MISMATCH',
    customer_delivery_status: 'MISMATCH',
    vendor_procurement_status: 'PASS',
    computed_status: 'MISMATCH',
    created_at: '2026-02-13T09:00:00Z',
    updated_at: '2026-02-13T09:10:00Z',
  },
];

const extractedDocument: BundleDocument = {
  id: 'doc-invoice',
  order_bundle_id: 'bundle-1',
  document_type: 'COMPANY_INVOICE',
  filename: 'invoice.pdf',
  content_type: 'application/pdf',
  status: 'PENDING_REVIEW',
  last_error: null,
  created_at: '2026-02-13T09:00:00Z',
  updated_at: '2026-02-13T09:10:00Z',
  metadata: {
    id: 'metadata-1',
    document_id: 'doc-invoice',
    status: 'EXTRACTED',
    extracted_data: { invoice_no: '1ITR2526001878' },
    diagnostics: {},
    field_confidences: {},
    field_evidence: {},
    field_locations: {},
    primary_ref_no: '1ITR2526001878',
    po_ref_no: null,
    last_error: null,
  },
};

const uploadedDocument: BundleDocument = {
  ...extractedDocument,
  id: 'doc-vendor-invoice',
  document_type: 'VENDOR_INVOICE',
  filename: 'vendor-invoice.pdf',
  status: 'UPLOADED',
  metadata: { ...extractedDocument.metadata!, id: 'metadata-2', document_id: 'doc-vendor-invoice', status: 'PENDING', extracted_data: {} },
};

const summary: VerificationSummary = {
  bundle_status: 'MISMATCH',
  customer_delivery_status: 'MISMATCH',
  vendor_procurement_status: 'REVIEW_REQUIRED',
  extracted_summary: {},
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
      message: 'Values differ.',
    },
    {
      check_id: 'VENDOR_BILLING_COVERAGE',
      check_name: 'Vendor invoice total covers Vendor PO total',
      result: 'REVIEW_REQUIRED',
      severity: 'WARNING',
      left_document_type: 'COMPANY_PO',
      left_document_id: 'doc-vendor-po',
      left_value: 696200,
      right_document_type: 'VENDOR_INVOICE',
      right_document_id: 'doc-vendor-invoice',
      right_value: 554600,
      message: 'Amounts differ or tax inclusion is unclear.',
    },
  ],
  issues: [
    {
      code: 'CUSTOMER_PO_MISSING',
      message: 'Customer PO is absent or unreadable.',
      document_type: 'CUSTOMER_PO',
      document_id: null,
    },
  ],
  recommendation: 'Resolve blocking or mismatched document evidence before closure.',
};

describe('Build 1 helpers', () => {
  it('uses the five backend-supported required document slots', () => {
    expect(REQUIRED_DOCUMENT_SLOTS).toEqual([
      { type: 'CUSTOMER_PO', label: 'Customer PO' },
      { type: 'COMPANY_INVOICE', label: 'Company Invoice' },
      { type: 'COMPANY_DC', label: 'Company Delivery Challan / DC' },
      { type: 'COMPANY_PO', label: 'Company PO to Vendor' },
      { type: 'VENDOR_INVOICE', label: 'Vendor Invoice' },
    ]);
  });

  it('maps backend statuses to honest Build 1 labels', () => {
    expect(statusLabel('REVIEW_REQUIRED')).toBe('Needs Review');
    expect(statusLabel('PENDING')).toBe('Extraction Pending');
    expect(statusLabel('EXTRACTED')).toBe('Extracted');
    expect(statusLabel('MISMATCH')).toBe('Mismatch');
    expect(statusLabel('MISSING_DOCUMENTS')).toBe('Missing Documents');
    expect(statusLabel('PASS')).toBe('Verification Passed');
    expect(statusLabel('OK')).toBe('Verification Passed');
  });

  it('computes queue metrics from bundle list data', () => {
    expect(bundleQueueMetrics(bundles)).toEqual({
      total: 4,
      needsReview: 1,
      verified: 1,
      mismatches: 1,
      missingDocuments: 1,
    });
  });

  it('builds slot inventory and extraction progress from document records', () => {
    const slots = buildDocumentSlots([extractedDocument, uploadedDocument]);

    expect(slots.find((slot) => slot.type === 'COMPANY_INVOICE')?.state).toBe('uploaded');
    expect(slots.find((slot) => slot.type === 'CUSTOMER_PO')?.state).toBe('missing');
    expect(extractionProgress([extractedDocument, uploadedDocument])).toEqual({
      total: 2,
      extracted: 1,
      pending: 1,
      failed: 0,
      confidenceAverage: null,
    });
  });

  it('classifies verification checks into Build 1 filters and metrics', () => {
    expect(checkCategory(summary.checks[0])).toBe('Customer Side');
    expect(checkCategory(summary.checks[1])).toBe('Amounts');
    expect(verificationMetrics(summary)).toEqual({
      total: 2,
      passed: 0,
      mismatches: 1,
      missingData: 0,
      notChecked: 1,
    });
  });

  it('uses backend summary issues without duplicating failed checks and adds missing slots', () => {
    const issues = deriveIssues(summary, [extractedDocument, uploadedDocument]);

    expect(issues.map((issue) => issue.title)).toContain('Customer PO Missing');
    expect(issues.map((issue) => issue.title)).not.toContain('SO number differs between invoice and DC');
    expect(issues.map((issue) => issue.title)).toContain('Missing Document: Customer PO');
    expect(issues.some((issue) => issue.severity === 'Critical')).toBe(true);
  });

  it('uses non-contradictory language for failed verification checks', () => {
    expect(checkDisplayName(summary.checks[0])).toBe('SO number differs between invoice and DC');
    expect(checkDisplayMessage(summary.checks[0])).toBe('Values differ.');
    expect(checkDisplayName(summary.checks[1])).toBe('Vendor invoice total is lower than Vendor PO total');
  });

  it('identifies known automated test bundles for the demo queue', () => {
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'OA-ACCEPT-123' })).toBe(true);
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'UPLOAD-SMOKE-123' })).toBe(true);
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'BUILD1-DEMO-123' })).toBe(true);
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'OA-PANIMALAR-1780795739222' })).toBe(true);
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'PANIMALAR-ORDER-1780795739222' })).toBe(true);
    expect(isAutomatedTestBundle({ ...bundles[0], bundle_number: 'OA-PANIMALAR-DEMO-123' })).toBe(false);
  });
});
