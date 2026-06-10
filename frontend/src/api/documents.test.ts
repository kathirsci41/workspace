import { afterEach, describe, expect, it, vi } from 'vitest';
import { patchExtractedData, uploadDocument } from './documents';

const documentPayload = {
  id: 'doc-1',
  order_bundle_id: 'bundle-1',
  document_type: 'VENDOR_INVOICE',
  filename: 'vendor.pdf',
  content_type: 'application/pdf',
  status: 'PENDING_REVIEW',
  last_error: null,
  created_at: '2026-02-13T00:00:00Z',
  updated_at: '2026-02-13T00:01:00Z',
  metadata: null,
};

describe('documents api', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('normalizes manual patch envelopes and sends the required reason', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ document: documentPayload, metadata: null }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const updated = await patchExtractedData('doc-1', { invoice_total: 554601 }, 'connection verification');

    expect(updated).toEqual(documentPayload);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8100/api/documents/doc-1/extracted-data',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({
          fields: { invoice_total: 554601 },
          actor: 'frontend',
          reason: 'connection verification',
        }),
      }),
    );
  });

  it('uploads PDFs using backend multipart field names', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(documentPayload), {
        status: 201,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const file = new File(['%PDF-1.4'], 'vendor.pdf', { type: 'application/pdf' });
    const uploaded = await uploadDocument('bundle-1', 'VENDOR_INVOICE', file);

    expect(uploaded).toEqual(documentPayload);
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8100/api/bundles/bundle-1/documents',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      }),
    );
    const form = fetchMock.mock.calls[0][1].body as FormData;
    expect(form.get('document_type')).toBe('VENDOR_INVOICE');
    expect(form.get('file')).toBe(file);
  });
});
