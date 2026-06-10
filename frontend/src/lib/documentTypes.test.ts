import { describe, expect, it } from 'vitest';
import { guessDocumentType } from './documentTypes';

describe('guessDocumentType', () => {
  it.each([
    ['Customer Invoice 1ITR2526001878.pdf', 'COMPANY_INVOICE'],
    ['DC 1DNT2526DC3100.pdf', 'COMPANY_DC'],
    ['Vendor PO 1PTR2526000467.pdf', 'COMPANY_PO'],
    ['AMC - VENDOR BILL - ...pdf', 'VENDOR_INVOICE'],
    ['Customer PO_.pdf', 'CUSTOMER_PO'],
    ['2526PSI25087738.pdf', null],
  ] as const)('classifies %s as %s', (filename, expectedType) => {
    expect(guessDocumentType(filename)).toBe(expectedType);
  });
});
