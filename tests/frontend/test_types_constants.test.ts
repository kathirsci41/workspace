/**
 * Unit tests for types/index.ts constants.
 *
 * Covers:
 *   - CHAIN_ORDER     : exactly 6 types in the correct order
 *   - DOC_TYPE_LABELS : every DocumentType has a human-readable label
 *   - DOC_TYPE_SHORT  : every DocumentType has a short display code
 *   - No missing or duplicate entries across all three
 */

import { describe, it, expect } from 'vitest';
import {
  CHAIN_ORDER,
  DOC_TYPE_LABELS,
  DOC_TYPE_SHORT,
  type DocumentType,
} from '../../frontend/src/types/index';

const ALL_TYPES: DocumentType[] = [
  'CUSTOMER_PO',
  'COMPANY_PO',
  'VENDOR_DC',
  'VENDOR_INVOICE',
  'COMPANY_DC',
  'COMPANY_INVOICE',
];

// ── CHAIN_ORDER ──────────────────────────────────────────────────────────────

describe('CHAIN_ORDER', () => {
  it('has exactly 6 entries', () => {
    expect(CHAIN_ORDER).toHaveLength(6);
  });

  it('contains all 6 document types', () => {
    for (const type of ALL_TYPES) {
      expect(CHAIN_ORDER).toContain(type);
    }
  });

  it('has no duplicates', () => {
    const unique = new Set(CHAIN_ORDER);
    expect(unique.size).toBe(CHAIN_ORDER.length);
  });

  it('starts with CUSTOMER_PO (first in chain)', () => {
    expect(CHAIN_ORDER[0]).toBe('CUSTOMER_PO');
  });

  it('ends with COMPANY_INVOICE (last in chain)', () => {
    expect(CHAIN_ORDER[CHAIN_ORDER.length - 1]).toBe('COMPANY_INVOICE');
  });

  it('has correct order: C.PO → PO → V.DC → V.Inv → C.DC → C.Inv', () => {
    expect(CHAIN_ORDER).toEqual([
      'CUSTOMER_PO',
      'COMPANY_PO',
      'VENDOR_DC',
      'VENDOR_INVOICE',
      'COMPANY_DC',
      'COMPANY_INVOICE',
    ]);
  });
});

// ── DOC_TYPE_LABELS ───────────────────────────────────────────────────────────

describe('DOC_TYPE_LABELS', () => {
  it('has a label for every document type', () => {
    for (const type of ALL_TYPES) {
      expect(DOC_TYPE_LABELS[type]).toBeTruthy();
    }
  });

  it('has no extra keys beyond the 6 types', () => {
    expect(Object.keys(DOC_TYPE_LABELS)).toHaveLength(6);
  });

  it('all labels are non-empty strings', () => {
    for (const label of Object.values(DOC_TYPE_LABELS)) {
      expect(typeof label).toBe('string');
      expect(label.length).toBeGreaterThan(0);
    }
  });

  it('CUSTOMER_PO label is human-readable', () => {
    expect(DOC_TYPE_LABELS['CUSTOMER_PO']).toBe('Customer PO');
  });

  it('COMPANY_INVOICE label is human-readable', () => {
    expect(DOC_TYPE_LABELS['COMPANY_INVOICE']).toBe('Company Invoice');
  });
});

// ── DOC_TYPE_SHORT ────────────────────────────────────────────────────────────

describe('DOC_TYPE_SHORT', () => {
  it('has a short code for every document type', () => {
    for (const type of ALL_TYPES) {
      expect(DOC_TYPE_SHORT[type]).toBeTruthy();
    }
  });

  it('has no extra keys beyond the 6 types', () => {
    expect(Object.keys(DOC_TYPE_SHORT)).toHaveLength(6);
  });

  it('all short codes are 2–5 characters', () => {
    for (const code of Object.values(DOC_TYPE_SHORT)) {
      expect(code.length).toBeGreaterThanOrEqual(2);
      expect(code.length).toBeLessThanOrEqual(5);
    }
  });

  it('CUSTOMER_PO short code is C.PO', () => {
    expect(DOC_TYPE_SHORT['CUSTOMER_PO']).toBe('C.PO');
  });

  it('COMPANY_INVOICE short code is C.Inv', () => {
    expect(DOC_TYPE_SHORT['COMPANY_INVOICE']).toBe('C.Inv');
  });

  it('no two types share the same short code', () => {
    const codes = Object.values(DOC_TYPE_SHORT);
    const unique = new Set(codes);
    expect(unique.size).toBe(codes.length);
  });
});
