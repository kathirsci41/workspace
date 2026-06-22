import { describe, expect, it } from 'vitest';
import {
  groupFieldsByDocType,
  isNeedsReviewSource,
  sourceLabel,
  criticalFieldsForDocType,
} from './extractedFieldsUtils';

describe('groupFieldsByDocType', () => {
  const emptyMeta = {};

  it('puts needs_review fields in the Needs Review group', () => {
    const fields: [string, unknown][] = [
      ['vendor_name', 'SUPREME'],
      ['vendor_invoice_no', '2526PSI25087738'],
    ];
    const rawMeta = {
      vendor_name: { source: 'needs_review' },
      vendor_invoice_no: { source: 'rules' },
    };
    const groups = groupFieldsByDocType(fields, 'VENDOR_INVOICE', rawMeta);

    const needsReview = groups.find((g) => g.label === 'Needs Review');
    expect(needsReview).toBeDefined();
    expect(needsReview!.fields.map(([f]) => f)).toContain('vendor_name');
    expect(needsReview!.fields.map(([f]) => f)).not.toContain('vendor_invoice_no');
  });

  it('puts suspicious_tax_amount fields in the Needs Review group', () => {
    const fields: [string, unknown][] = [
      ['tax_amount', 18],
      ['grand_total', 118000],
    ];
    const rawMeta = {
      tax_amount: { source: 'suspicious_tax_amount' },
      grand_total: { source: 'rules' },
    };
    const groups = groupFieldsByDocType(fields, 'CUSTOMER_PO', rawMeta);

    const needsReview = groups.find((g) => g.label === 'Needs Review');
    expect(needsReview).toBeDefined();
    expect(needsReview!.fields.map(([f]) => f)).toContain('tax_amount');
    expect(needsReview!.fields.map(([f]) => f)).not.toContain('grand_total');
  });

  it('puts doc-type critical fields in Critical Fields group (not in Needs Review)', () => {
    const fields: [string, unknown][] = [
      ['vendor_invoice_no', '2526PSI25087738'],
      ['vendor_invoice_date', '12-02-2026'],
      ['irn', 'abc123'],
    ];
    const groups = groupFieldsByDocType(fields, 'VENDOR_INVOICE', emptyMeta);

    const critical = groups.find((g) => g.label === 'Critical Fields');
    expect(critical).toBeDefined();
    expect(critical!.fields.map(([f]) => f)).toContain('vendor_invoice_no');
    expect(critical!.fields.map(([f]) => f)).toContain('vendor_invoice_date');
    expect(critical!.fields.map(([f]) => f)).not.toContain('irn');
  });

  it('puts non-critical non-flagged fields in Supporting Fields group', () => {
    const fields: [string, unknown][] = [
      ['vendor_invoice_no', '2526PSI25087738'],
      ['irn', 'abc123'],
      ['ack_no', '12345678'],
    ];
    const groups = groupFieldsByDocType(fields, 'VENDOR_INVOICE', emptyMeta);

    const supporting = groups.find((g) => g.label === 'Supporting Fields');
    expect(supporting).toBeDefined();
    expect(supporting!.fields.map(([f]) => f)).toContain('irn');
    expect(supporting!.fields.map(([f]) => f)).toContain('ack_no');
    expect(supporting!.fields.map(([f]) => f)).not.toContain('vendor_invoice_no');
  });

  it('omits empty groups from result', () => {
    const fields: [string, unknown][] = [['vendor_invoice_no', '2526PSI25087738']];
    const groups = groupFieldsByDocType(fields, 'VENDOR_INVOICE', emptyMeta);

    const labels = groups.map((g) => g.label);
    expect(labels).not.toContain('Needs Review');
    expect(labels).toContain('Critical Fields');
  });

  it('uses Supporting Fields for all fields when doc type is unknown', () => {
    const fields: [string, unknown][] = [['some_field', 'value']];
    const groups = groupFieldsByDocType(fields, 'UNKNOWN_TYPE', emptyMeta);

    const labels = groups.map((g) => g.label);
    expect(labels).not.toContain('Critical Fields');
    expect(labels).toContain('Supporting Fields');
  });
});

describe('isNeedsReviewSource', () => {
  it('returns true for needs_review source', () => {
    expect(isNeedsReviewSource('needs_review')).toBe(true);
  });

  it('returns true for suspicious_ prefixed sources', () => {
    expect(isNeedsReviewSource('suspicious_tax_amount')).toBe(true);
    expect(isNeedsReviewSource('suspicious_vendor_name')).toBe(true);
  });

  it('returns false for rules, digital_text, ocr', () => {
    expect(isNeedsReviewSource('rules')).toBe(false);
    expect(isNeedsReviewSource('digital_text')).toBe(false);
    expect(isNeedsReviewSource('ocr')).toBe(false);
  });
});

describe('sourceLabel', () => {
  it('returns human label for special sources', () => {
    expect(sourceLabel('needs_review')).toBe('Needs Review');
    expect(sourceLabel('suspicious_tax_amount')).toBe('Suspicious');
    expect(sourceLabel('fallback_largest')).toBe('Estimated');
    expect(sourceLabel('filename_fallback')).toBe('From Filename');
    expect(sourceLabel('model_layer2')).toBe('AI Extracted');
  });

  it('returns null for normal sources', () => {
    expect(sourceLabel('rules')).toBeNull();
    expect(sourceLabel('digital_text')).toBeNull();
    expect(sourceLabel('ocr')).toBeNull();
    expect(sourceLabel(undefined)).toBeNull();
  });
});

describe('criticalFieldsForDocType', () => {
  it('returns VENDOR_INVOICE critical fields', () => {
    const fields = criticalFieldsForDocType('VENDOR_INVOICE');
    expect(fields).toContain('vendor_invoice_no');
    expect(fields).toContain('vendor_invoice_date');
    expect(fields).toContain('po_reference');
    expect(fields).toContain('invoice_total');
  });

  it('returns CUSTOMER_PO critical fields', () => {
    const fields = criticalFieldsForDocType('CUSTOMER_PO');
    expect(fields).toContain('customer_po_no');
    expect(fields).toContain('grand_total');
  });

  it('returns empty set for unknown doc type', () => {
    expect(criticalFieldsForDocType('UNKNOWN').size).toBe(0);
  });
});
