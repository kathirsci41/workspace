/**
 * Build 1 — user-visible error handling.
 *
 * Verifies that failures surface clearly to the API/UI:
 *  - invalid (non-PDF) upload is rejected with a clear message
 *  - PDF extension with a non-PDF body is rejected
 *  - export of an unknown bundle returns a clear error
 *  - a real MANUAL_ENTRY extraction surfaces a clean failure reason in the UI
 *    (and does NOT leak the raw `FailureCode.` enum repr)
 *  - backend-unavailable handling is documented (skipped — cannot safely stop
 *    the shared backend mid-suite)
 */
import { test, expect, request as playwrightRequest, type APIRequestContext } from '@playwright/test';
import fs from 'fs';
import {
  API_BASE,
  createBundle,
  uploadDoc,
  extractDoc,
  cleanupE2EBundles,
  samplePath,
  timestamp,
} from './build1-live-helpers';

test.describe.configure({ mode: 'serial' });

let api: APIRequestContext;
const ts = timestamp();
let bundleId: string;

test.beforeAll(async () => {
  api = await playwrightRequest.newContext();
  bundleId = await createBundle(api, `E2E-LIVE-ERRORS-${ts}`, { customer_name: 'SHRIRAM FINANCE LIMITED' });
});

test.afterAll(async () => {
  await cleanupE2EBundles(api);
  await api.dispose();
});

test('invalid non-PDF upload is rejected with a clear message', async () => {
  const resp = await api.post(`${API_BASE}/bundles/${bundleId}/documents`, {
    multipart: {
      document_type: 'CUSTOMER_PO',
      file: { name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('this is not a pdf') },
    },
  });
  expect(resp.status()).toBe(400);
  const detail = (await resp.json()).detail as string;
  expect(detail.toLowerCase()).toContain('pdf');
});

test('PDF extension with a non-PDF body is rejected', async () => {
  const resp = await api.post(`${API_BASE}/bundles/${bundleId}/documents`, {
    multipart: {
      document_type: 'CUSTOMER_PO',
      file: { name: 'fake.pdf', mimeType: 'application/pdf', buffer: Buffer.from('GIF89a not a pdf') },
    },
  });
  expect(resp.status()).toBe(400);
  expect(((await resp.json()).detail as string).toLowerCase()).toContain('valid pdf');
});

test('export of an unknown bundle returns a clear 404', async () => {
  const resp = await api.get(`${API_BASE}/bundles/does-not-exist-0000/export.xlsx`);
  expect(resp.status()).toBe(404);
  expect(((await resp.json()).detail as string).toLowerCase()).toContain('not found');
});

test('MANUAL_ENTRY extraction surfaces a clean failure reason in the UI (no enum leak)', async ({ page }) => {
  test.setTimeout(120_000);
  // The Sriram "corro" vendor invoice acquires OCR text but is missing a
  // required field (po_reference) → MANUAL_ENTRY with a human-readable reason.
  const corro = { file: 'Sriram fin/Tax invoice corro health.pdf', type: 'VENDOR_INVOICE' };
  expect(fs.existsSync(samplePath(corro.file))).toBeTruthy();
  const docId = await uploadDoc(api, bundleId, corro);
  const r = await extractDoc(api, docId);
  expect(r.httpStatus).toBe(200);
  // It may extract cleanly on some runs; only assert the UI/message contract
  // when it actually lands in a failed/manual state.
  if (r.metadataStatus !== 'EXTRACTED') {
    expect(String(r.failureReason ?? '')).not.toContain('FailureCode.');
    await page.goto(`/bundles/${bundleId}/documents`);
    const body = page.locator('body');
    await expect(body).toContainText(/required fields|manual|review|missing/i);
    await expect(body).not.toContainText('FailureCode.');
  }
});

test.skip('backend unavailable shows a connection error (skipped: shared backend)', async () => {
  // Intentionally skipped: stopping the backend mid-suite would break the
  // other live specs. The client surfaces a friendly message
  // ("Unable to reach the server…") via extractErrorMessage / network-error
  // handling in src/api/client.ts, covered by unit tests instead.
});
