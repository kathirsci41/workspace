import * as fs from 'node:fs';
import * as path from 'node:path';
import * as url from 'node:url';
import { expect, test } from '@playwright/test';

const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';
const _dirname = path.dirname(url.fileURLToPath(import.meta.url));
const screenshotDir = path.resolve(
  _dirname,
  '../../backend/output/e2e-runs/phase1xJ_ux_audit/screenshots',
);

function ensureDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function shot(page: import('@playwright/test').Page, name: string) {
  ensureDir();
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: false });
}

async function findBundle(
  request: import('@playwright/test').APIRequestContext,
): Promise<{ id: string; bundle_number: string } | null> {
  const res = await request.get(`${apiBaseUrl}/bundles`);
  if (!res.ok()) return null;
  const bundles = (await res.json()) as Array<{ id: string; bundle_number: string }>;
  return (
    bundles.find((b) => /panimalar|PMCH|trade|1xG/i.test(b.bundle_number))
    ?? bundles.find((b) => !b.bundle_number.startsWith('HIGHLIGHT') && !b.bundle_number.startsWith('OA-') && !b.bundle_number.startsWith('SCANNED'))
    ?? bundles[0]
    ?? null
  );
}

async function findDocumentOfType(
  request: import('@playwright/test').APIRequestContext,
  bundleId: string,
  docType: string,
): Promise<{ id: string } | null> {
  const res = await request.get(`${apiBaseUrl}/bundles/${bundleId}/documents`);
  if (!res.ok()) return null;
  const docs = (await res.json()) as Array<{ id: string; document_type: string }>;
  return docs.find((d) => d.document_type === docType) ?? docs[0] ?? null;
}

test.describe('Phase 1xJ UX audit screenshots', () => {
  test('01 – Bundles page', async ({ page }) => {
    await page.goto('/bundles');
    await page.waitForLoadState('networkidle');
    await shot(page, '01_bundles_page');
    await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible();
  });

  test('02 – Bundle Overview page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/overview`);
    await page.waitForLoadState('networkidle');
    await shot(page, '02_bundle_overview');
    await expect(page.getByRole('heading', { name: bundle.bundle_number })).toBeVisible();
  });

  test('03 – Documents page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/documents`);
    await page.waitForLoadState('networkidle');
    await shot(page, '03_documents_page');
    await expect(page.getByRole('heading', { name: 'Documents' })).toBeVisible();
  });

  test('04 – Extraction Review split-pane layout', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    const doc = await findDocumentOfType(request, bundle.id, 'COMPANY_INVOICE');
    const navPath = doc
      ? `/bundles/${bundle.id}/extraction/${doc.id}`
      : `/bundles/${bundle.id}/extraction`;
    await page.goto(navPath);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    // Take screenshot of the split-pane layout
    await shot(page, '04_extraction_review_split_pane');
    await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();

    // Verify PDF pane and fields pane are both visible without page scroll
    const pdfPane = page.locator('.pdf-pane');
    const fieldsPane = page.locator('.fields-panel-wrap');
    await expect(pdfPane).toBeVisible();
    await expect(fieldsPane).toBeVisible();

    // Verify helper text is present
    const hint = page.locator('.fields-hint');
    if (await hint.count() > 0) {
      await expect(hint).toContainText('Click a field name');
      console.log('Helper text visible:', await hint.textContent());
    }

    // Verify review-grid has constrained height (not a full-page scroll layout)
    const gridBox = await page.locator('.review-grid').boundingBox();
    const viewport = page.viewportSize();
    if (gridBox && viewport) {
      console.log(`review-grid height: ${gridBox.height}px, viewport: ${viewport.height}px`);
      // Grid should NOT exceed viewport height (it should be constrained)
      expect(gridBox.height).toBeLessThanOrEqual(viewport.height);
    }
  });

  test('05 – Extraction Review with field highlight', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    const doc = await findDocumentOfType(request, bundle.id, 'COMPANY_INVOICE');
    if (!doc) {
      test.skip(true, 'No COMPANY_INVOICE document');
      return;
    }

    await page.goto(`/bundles/${bundle.id}/extraction/${doc.id}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    // Try to click a field to trigger highlight
    const jumpBtn = page.getByLabel(/Jump to .+ in PDF/i).first();
    if (await jumpBtn.count() > 0) {
      await jumpBtn.click();
      await page.waitForTimeout(600);
    }

    await shot(page, '05_extraction_review_field_highlight');

    const overlay = page.locator('.pdf-highlight-overlay');
    if (await overlay.count() > 0) {
      const box = await overlay.boundingBox();
      console.log('Highlight overlay bounds:', box);
    }
  });

  test('06 – Verification / Review Results page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/verification`);
    await page.waitForLoadState('networkidle');
    await shot(page, '06_verification_page');
    await expect(page.getByRole('heading', { name: 'Review Results' })).toBeVisible();
  });

  test('07 – Issues page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/issues`);
    await page.waitForLoadState('networkidle');
    await shot(page, '07_issues_page');
    await expect(page.getByRole('heading', { name: 'Open Issues' })).toBeVisible();
  });

  test('08 – Audit Trail page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/audit`);
    await page.waitForLoadState('networkidle');
    await shot(page, '08_audit_trail');
    await expect(page.getByRole('heading', { name: 'Manual Correction History' })).toBeVisible();
  });

  test('09 – Exports page', async ({ page, request }) => {
    const bundle = await findBundle(request);
    if (!bundle) {
      test.skip(true, 'No bundle available');
      return;
    }
    await page.goto(`/bundles/${bundle.id}/exports`);
    await page.waitForLoadState('networkidle');
    await shot(page, '09_exports_page');
    await expect(page.getByRole('heading', { name: 'Exports' })).toBeVisible();
    // Verify the gratuitous "no export history" section is gone
    const emptyHistoryText = page.getByText('No export history available');
    expect(await emptyHistoryText.count()).toBe(0);
  });

  test('10 – Health page', async ({ page }) => {
    await page.goto('/health');
    await page.waitForLoadState('networkidle');
    await shot(page, '10_health_page');
    await expect(page.getByRole('heading', { name: 'Health' })).toBeVisible();
  });
});
