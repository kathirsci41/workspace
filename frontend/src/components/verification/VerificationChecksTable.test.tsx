import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { VerificationChecksTable } from './VerificationChecksTable';
import type { VerificationCheck } from '../../types/api';


describe('VerificationChecksTable', () => {
  it('renders repeated per-document check ids without duplicate React keys', () => {
    const checks: VerificationCheck[] = [
      {
        check_id: 'VENDOR_NAME_MATCH',
        check_name: 'Vendor name match',
        result: 'PASS',
        severity: 'WARNING',
        left_document_type: 'VENDOR_PO',
        left_document_id: 'vendor-po',
        left_value: 'REDINGTON LIMITED',
        right_document_type: 'VENDOR_INVOICE',
        right_document_id: 'vendor-invoice-1',
        right_value: 'REDINGTON LIMITED',
        message: 'Vendor names compared.',
      },
      {
        check_id: 'VENDOR_NAME_MATCH',
        check_name: 'Vendor name match',
        result: 'PASS',
        severity: 'WARNING',
        left_document_type: 'VENDOR_PO',
        left_document_id: 'vendor-po',
        left_value: 'REDINGTON LIMITED',
        right_document_type: 'VENDOR_INVOICE',
        right_document_id: 'vendor-invoice-2',
        right_value: 'REDINGTON LIMITED',
        message: 'Vendor names compared.',
      },
    ];
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined);

    render(
      <MemoryRouter>
        <VerificationChecksTable
          bundleId="bundle-1"
          checks={checks}
          selectedCheckId={null}
          onSelect={vi.fn()}
        />
      </MemoryRouter>,
    );

    expect(consoleError.mock.calls.flat().join(' ')).not.toContain('same key');
    consoleError.mockRestore();
  });
});
