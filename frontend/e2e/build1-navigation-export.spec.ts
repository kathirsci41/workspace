/**
 * Build 1 — page navigation, button coverage, and export download.
 *
 * Creates a small E2E-LIVE bundle (digital Trade docs — fast extraction),
 * walks every bundle page, asserts the key controls are present (without
 * clicking destructive actions), and downloads the Excel report.
 */
import { test, expect, request as playwrightRequest, type APIRequestContext } from '@playwright/test';
import fs from 'fs';
import {
  createBundle,
  uploadDoc,
  extractDoc,
  cleanupE2EBundles,
  timestamp,
  type SampleDoc,
} from './build1-live-helpers';

test.describe.configure({ mode: 'serial' });

let api: APIRequestContext;
let bundleId: string;
const ts = timestamp();

const DOCS: SampleDoc[] = [
  { file: 'Trade/Trade/TRADE - CUSTOMER PO.pdf', type: 'CUSTOMER_PO' },
  { file: 'Trade/Trade/TRADE - INVOICE 1ITR2526001785.pdf', type: 'CUSTOMER_INVOICE' },
  { file: 'Trade/Trade/TRADE - VENDOR BILL -C190224826.pdf', type: 'VENDOR_INVOICE' },
];

test.beforeAll(async () => {
  test.setTimeout(180_000);
  api = await playwrightRequest.newContext();
  bundleId = await createBundle(api, `E2E-LIVE-NAVEXP-${ts}`, {
    customer_name: 'SHRIRAM FINANCE LIMITED',
    customer_po_no: 'PWFA251127016',
    so_no: '1OTM2526001429',
  });
  for (const doc of DOCS) {
    const docId = await uploadDoc(api, bundleId, doc);
    await extractDoc(api, docId);
  }
});

test.afterAll(async () => {
  await cleanupE2EBundles(api);
  await api.dispose();
});

test('documents page shows cards and key controls', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/documents`);
  await expect(page.getByRole('button', { name: /upload document/i }).first()).toBeVisible();
  await expect(page.getByText('TRADE - CUSTOMER PO.pdf')).toBeVisible();
  // Review / Preview are links, Re-extract / Delete are buttons (visible only, not clicked).
  await expect(page.getByRole('link', { name: /^review/i }).first()).toBeVisible();
  await expect(page.getByRole('link', { name: /^preview/i }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /re-extract/i }).first()).toBeVisible();
  await expect(page.getByRole('button', { name: /^delete/i }).first()).toBeVisible();
});

test('extraction review page shows extracted fields', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/extraction`);
  await expect(page.getByText(/Extraction Review/i).first()).toBeVisible();
  await expect(page.getByText(/Extracted Fields/i).first()).toBeVisible();
  await expect(page.getByText('PWFA251127016').first()).toBeVisible();
});

test('verification (review results) page loads', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/verification`);
  await expect(page.getByText(/Review Results/i).first()).toBeVisible();
  await expect(page.getByText(/Total Checks/i).first()).toBeVisible();
});

test('issues page loads', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/issues`);
  await expect(page.locator('body')).toContainText(/issue/i);
});

test('audit page loads', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/audit`);
  await expect(page.locator('body')).toContainText(/audit/i);
});

test('export page loads and downloads the Excel report', async ({ page }) => {
  await page.goto(`/bundles/${bundleId}/exports`);
  await expect(page.getByText(/Document Coverage/i).first()).toBeVisible();
  const downloadButton = page.getByRole('button', { name: /download excel/i }).first();
  await expect(downloadButton).toBeVisible();
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    downloadButton.click(),
  ]);
  const suggested = download.suggestedFilename();
  expect(suggested).toMatch(/\.xlsx$/i);
  const stream = await download.path();
  expect(stream && fs.existsSync(stream)).toBeTruthy();
});
