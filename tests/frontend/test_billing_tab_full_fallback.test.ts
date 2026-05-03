import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import BillingTab from '../../frontend/src/components/BillingTab';

describe('BillingTab', () => {
  it('shows invoiced_total for full billing when stages are empty', () => {
    const markup = renderToStaticMarkup(
      React.createElement(BillingTab, {
        po: {
          billing_type: 'full',
          billing_milestones: null,
          total_amount: 1000,
        } as any,
        chainValidation: {
          chain: {},
          chain_status: 'complete',
          missing_slots: [],
          missing_vendor_invoices: [],
          reference_checks: [],
          billing: {
            overall: 'complete',
            stages: [],
            invoiced_total: 750,
          },
        },
        onUpdate: () => {},
      })
    );

    expect(markup).toContain('₹750');
    expect(markup).toContain('₹250');
    expect(markup).not.toContain('No invoices uploaded yet');
  });
});
