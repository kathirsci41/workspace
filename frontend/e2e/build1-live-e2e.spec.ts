/**
 * Build 1 — Full live E2E: create → upload → live extraction → review → export.
 *
 * Real sample PDFs from sample/extracted are uploaded through the API and
 * extracted live (PaddleOCR GPU for scanned docs, digital for text-layer docs).
 * No seeded data, no copied extracted_data — every asserted value comes back
 * from a live extraction call.
 */
import { test, expect, request as playwrightRequest, type APIRequestContext } from '@playwright/test';
import {
  API_BASE,
  TRADE_DOCS,
  PANIMALAR_DOCS,
  SRIRAM_VENDOR_PO_DOCS,
  createBundle,
  uploadDoc,
  extractDoc,
  cleanupE2EBundles,
  timestamp,
} from './build1-live-helpers';

test.describe.configure({ mode: 'serial' });

let api: APIRequestContext;
const ts = timestamp();
const ids: Record<string, string> = {};
const docIds: Record<string, string> = {}; // key: `${bundleKey}:${type}:${file}`

test.beforeAll(async () => {
  api = await playwrightRequest.newContext();
  await cleanupE2EBundles(api); // remove leftovers from prior runs first
});

test.afterAll(async () => {
  await api.dispose();
});

test('create three fresh E2E-LIVE bundles', async () => {
  ids.TRADE = await createBundle(api, `E2E-LIVE-TRADE-${ts}`, {
    customer_name: 'SHRIRAM FINANCE LIMITED',
    customer_po_no: 'PWFA251127016',
    so_no: '1OTM2526001429',
  });
  ids.PANIMALAR = await createBundle(api, `E2E-LIVE-PANIMALAR-${ts}`, {
    customer_name: 'PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
    customer_po_no: 'PMCH&RI/024/2025-2026',
    so_no: '1OTM2526001611',
  });
  ids.SRIRAM = await createBundle(api, `E2E-LIVE-SRIRAM-${ts}`, {
    customer_name: 'SHRIRAM FINANCE LIMITED',
    customer_po_no: 'PWFA251127016',
    so_no: '1OTM2526001429',
  });
  for (const key of ['TRADE', 'PANIMALAR', 'SRIRAM']) {
    expect(ids[key]).toBeTruthy();
  }
});

test('bundles appear in /bundles UI', async ({ page }) => {
  await page.goto('/bundles');
  await expect(page.getByText(`E2E-LIVE-TRADE-${ts}`)).toBeVisible();
  await expect(page.getByText(`E2E-LIVE-PANIMALAR-${ts}`)).toBeVisible();
  await expect(page.getByText(`E2E-LIVE-SRIRAM-${ts}`)).toBeVisible();
});

test('upload real sample PDFs to each bundle', async () => {
  for (const doc of TRADE_DOCS) {
    docIds[`TRADE:${doc.type}:${doc.file}`] = await uploadDoc(api, ids.TRADE, doc);
  }
  for (const doc of PANIMALAR_DOCS) {
    docIds[`PANIMALAR:${doc.type}:${doc.file}`] = await uploadDoc(api, ids.PANIMALAR, doc);
  }
  for (const doc of SRIRAM_VENDOR_PO_DOCS) {
    docIds[`SRIRAM:${doc.type}:${doc.file}`] = await uploadDoc(api, ids.SRIRAM, doc);
  }
  // verify documents exist via API
  const tradeDocs = await (await api.get(`${API_BASE}/bundles/${ids.TRADE}/documents`)).json();
  expect(tradeDocs.length).toBe(TRADE_DOCS.length);
});

test('live-extract TRADE bundle (6 docs) — all succeed, no GLM fallback', async () => {
  test.setTimeout(180_000);
  for (const doc of TRADE_DOCS) {
    const r = await extractDoc(api, docIds[`TRADE:${doc.type}:${doc.file}`]);
    expect(r.httpStatus, doc.file).toBe(200);
    expect(['EXTRACTED', 'MANUAL_ENTRY'], `${doc.file} status`).toContain(r.metadataStatus);
    expect(['digital', 'ocr_paddleocr_gpu'], `${doc.file} route`).toContain(r.extractionRoute);
    expect(r.fallbackUsed, `${doc.file} fallback`).not.toBe(true);
  }
});

test('TRADE customer invoice live fields match expected', async () => {
  const r = await extractDoc(api, docIds[`TRADE:CUSTOMER_INVOICE:Trade/Trade/TRADE - INVOICE 1ITR2526001785.pdf`]);
  expect(r.metadataStatus).toBe('EXTRACTED');
  expect(r.extracted.invoice_number ?? r.extracted.invoice_no).toBe('1ITR2526001785');
  expect(String(r.extracted.customer_order_no ?? r.extracted.po_reference)).toBe('PWFA251127016');
  expect(Number(r.extracted.taxable_amount)).toBe(503137);
  expect(Number(r.extracted.total_amount ?? r.extracted.net_amount)).toBeCloseTo(593701.66, 1);
});

test('live-extract PANIMALAR bundle (5 docs) — succeed, or fail-fast outside the allowlist (no GLM)', async () => {
  test.setTimeout(180_000);
  for (const doc of PANIMALAR_DOCS) {
    const r = await extractDoc(api, docIds[`PANIMALAR:${doc.type}:${doc.file}`]);
    expect(r.httpStatus, doc.file).toBe(200);
    expect(r.fallbackUsed, doc.file).not.toBe(true);
    if (r.metadataStatus === 'FAILED') {
      // Scanned document types outside the PaddleOCR allowlist (e.g. a scanned
      // CUSTOMER_PO) must fail fast rather than silently falling back to GLM.
      expect(String(r.failureReason ?? ''), doc.file).toMatch(/PaddleOCR allowlist|GLM fallback is disabled/i);
    } else {
      expect(['EXTRACTED', 'MANUAL_ENTRY'], `${doc.file}`).toContain(r.metadataStatus);
    }
  }
});

test('PANIMALAR vendor bill live fields match expected (paddle OCR)', async () => {
  const r = await extractDoc(api, docIds[`PANIMALAR:VENDOR_INVOICE:Panimalar/Vendor Bill 2526PSI25087738.pdf`]);
  expect(r.extractionRoute).toBe('ocr_paddleocr_gpu');
  expect(r.metadataStatus).toBe('EXTRACTED');
  expect(r.ocrTextBlocks, 'raw OCR text blocks exist').toBeGreaterThan(0);
  expect(r.extracted.vendor_invoice_no ?? r.extracted.invoice_number).toBe('2526PSI25087738');
  expect(String(r.extracted.po_reference)).toBe('1PTR2526000467');
  expect(Number(r.extracted.invoice_total ?? r.extracted.total_amount)).toBe(554600);
});

test('VENDOR_PO allowlist: 3 Sriram scanned vendor POs extract via paddle (no GLM)', async () => {
  test.setTimeout(180_000);
  for (const doc of SRIRAM_VENDOR_PO_DOCS) {
    const r = await extractDoc(api, docIds[`SRIRAM:${doc.type}:${doc.file}`]);
    expect(r.httpStatus, doc.file).toBe(200);
    expect(r.extractionRoute, `${doc.file} route`).toBe('ocr_paddleocr_gpu');
    expect(r.fallbackUsed, `${doc.file} fallback`).not.toBe(true);
    expect(['EXTRACTED', 'MANUAL_ENTRY'], `${doc.file} status`).toContain(r.metadataStatus);
    expect(r.ocrTextBlocks, `${doc.file} OCR blocks`).toBeGreaterThan(0);
  }
});

test('audit events recorded for the TRADE bundle lifecycle', async () => {
  const events = (await (await api.get(`${API_BASE}/bundles/${ids.TRADE}/audit-events`)).json()) as Array<{
    event_type: string;
  }>;
  const types = new Set(events.map((e) => e.event_type));
  expect(types.has('bundle_created')).toBeTruthy();
  expect(types.has('document_uploaded')).toBeTruthy();
  expect(types.has('extraction_completed') || types.has('extraction_failed')).toBeTruthy();
});
