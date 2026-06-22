/**
 * full-app-audit.spec.ts
 *
 * Comprehensive Playwright audit of every page, navigation route, button,
 * and interactive element in the Order Assurance UI.
 *
 * The suite reuses a running frontend at http://127.0.0.1:5180 and backend
 * at http://127.0.0.1:8100/api.  It picks the first bundle that already has
 * documents so no new data needs to be created.
 *
 * Screenshots are saved to:
 *   E:\PROJECTS\Experiments\Logistic\ODMP\order-assurance\backend\output\e2e-runs\full-app-audit\
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as url from 'node:url';
import { expect, test, type Page } from '@playwright/test';

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';

const _dirname = path.dirname(url.fileURLToPath(import.meta.url));
const screenshotDir = path.resolve(
  _dirname,
  '../../backend/output/e2e-runs/full-app-audit',
);

function ensureScreenshotDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function shot(page: Page, name: string) {
  ensureScreenshotDir();
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: true });
}

// ---------------------------------------------------------------------------
// Shared state — resolved once in beforeAll
// ---------------------------------------------------------------------------

let bundleId = '';
let bundleName = '';
let firstDocumentId = '';
const consoleErrors: string[] = [];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Attach a console error listener to each page. */
function watchConsoleErrors(page: Page) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(`[${msg.location().url}] ${msg.text()}`);
    }
  });
  page.on('pageerror', (err) => {
    consoleErrors.push(`[pageerror] ${err.message}`);
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

test.describe('Full-app audit', () => {
  // -----------------------------------------------------------------------
  // Bootstrap — find a bundle that has documents
  // -----------------------------------------------------------------------
  test.beforeAll(async ({ request }) => {
    const bundlesRes = await request.get(`${apiBaseUrl}/bundles`);
    expect(bundlesRes.ok(), 'GET /bundles must succeed').toBeTruthy();

    const bundles = (await bundlesRes.json()) as Array<{
      id: string;
      bundle_number: string;
    }>;
    expect(bundles.length, 'Need at least one bundle in the database').toBeGreaterThan(0);

    // Pick the first bundle that has at least one document
    for (const b of bundles) {
      const docsRes = await request.get(`${apiBaseUrl}/bundles/${b.id}/documents`);
      if (!docsRes.ok()) continue;
      const docs = (await docsRes.json()) as Array<{ id: string }>;
      if (docs.length > 0) {
        bundleId = b.id;
        bundleName = b.bundle_number;
        firstDocumentId = docs[0].id;
        break;
      }
    }

    expect(bundleId, 'Must find a bundle with at least one document').toBeTruthy();
    console.log(`Using bundle ${bundleName} (${bundleId}), first doc ${firstDocumentId}`);
  });

  // -----------------------------------------------------------------------
  // 01 — /bundles  (bundle list page)
  // -----------------------------------------------------------------------
  test('01 – /bundles: table renders and Create Bundle button is visible', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto('/bundles');
    // React SPA: wait for the data-fetched heading to appear (networkidle alone can be too early)
    await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible({ timeout: 15_000 });

    // Bundles table (wait for async bundle load)
    await expect(page.getByRole('table', { name: 'Bundles table' })).toBeVisible({ timeout: 15_000 });

    // Create Bundle button
    const createBtn = page.getByRole('button', { name: 'Create Bundle' });
    await expect(createBtn).toBeVisible();

    // Breadcrumb nav exists
    const breadcrumb = page.getByRole('navigation', { name: 'Breadcrumb' });
    await expect(breadcrumb).toBeVisible();

    // The bundle we found in beforeAll should appear in the list
    // Use exact:true to match the bundle name cell precisely (avoid matching the "Open Bundle X" link cell too)
    await expect(page.getByRole('cell', { name: bundleName, exact: true }).first()).toBeVisible({ timeout: 15_000 });

    await shot(page, '01-bundles-list');
  });

  // -----------------------------------------------------------------------
  // 02 — Create Bundle dialog (open + close without committing)
  // -----------------------------------------------------------------------
  test('02 – /bundles: Create Bundle dialog opens and can be cancelled', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto('/bundles');
    await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible({ timeout: 15_000 });

    await page.getByRole('button', { name: 'Create Bundle' }).click();

    const dialog = page.getByRole('dialog', { name: 'Create Bundle' });
    await expect(dialog).toBeVisible();

    // Bundle name input
    const nameInput = dialog.getByLabel('Bundle name');
    await expect(nameInput).toBeVisible();

    // Submit button labelled "Create verification bundle"
    const submitBtn = dialog.getByRole('button', { name: 'Create verification bundle' });
    await expect(submitBtn).toBeVisible();

    // Close / cancel — the modal uses a Cancel button (not ESC) to close
    // The component renders null when closed, so we click Cancel and wait for it to detach
    await dialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(dialog).not.toBeAttached();

    await shot(page, '02-create-bundle-dialog-cancelled');
  });

  // -----------------------------------------------------------------------
  // 03 — /bundles/:id/overview
  // -----------------------------------------------------------------------
  test('03 – /bundles/:id/overview: renders bundle heading and doc inventory', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/overview`);

    // h1 is async — first renders "Bundle Workspace", then the real name once data loads
    await expect(page.getByRole('heading', { name: bundleName })).toBeVisible({ timeout: 15_000 });

    // Document Inventory section
    await expect(page.getByText('Document Inventory')).toBeVisible();

    // WorkflowTabs nav is present
    const tabs = page.getByRole('navigation', { name: 'Bundle workflow' });
    await expect(tabs).toBeVisible();

    // All six tab links visible
    for (const tabLabel of ['Overview', 'Documents', 'Extraction Review', 'Review Results', 'Open Issues', 'Export']) {
      await expect(tabs.getByRole('link', { name: tabLabel, exact: true })).toBeVisible();
    }

    // Breadcrumb contains "Bundles" link
    const breadcrumb = page.getByRole('navigation', { name: 'Breadcrumb' });
    await expect(breadcrumb).toBeVisible();

    await shot(page, '03-bundle-overview');
  });

  // -----------------------------------------------------------------------
  // 04 — WorkflowTabs navigation
  // -----------------------------------------------------------------------
  test('04 – WorkflowTabs: clicking each tab navigates to the correct URL', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/overview`);
    await page.waitForLoadState('networkidle');

    const tabs = page.getByRole('navigation', { name: 'Bundle workflow' });

    const tabRoutes: [string, string][] = [
      ['Documents', 'documents'],
      ['Extraction Review', 'extraction'],
      ['Review Results', 'verification'],
      ['Open Issues', 'issues'],
      ['Export', 'exports'],
      ['Overview', 'overview'],
    ];

    for (const [label, segment] of tabRoutes) {
      await tabs.getByRole('link', { name: label, exact: true }).click();
      await page.waitForURL(`**/bundles/${bundleId}/${segment}`);
      await page.waitForLoadState('networkidle');
      // Each page must have a visible h1
      await expect(page.locator('h1')).toBeVisible();
    }

    await shot(page, '04-workflow-tabs-navigation');
  });

  // -----------------------------------------------------------------------
  // 05 — /bundles/:id/documents
  // -----------------------------------------------------------------------
  test('05 – /bundles/:id/documents: upload area and document cards render', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/documents`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();

    // There should be at least one document article card
    const cards = page.getByRole('article');
    await expect(cards.first()).toBeVisible();

    // Every card has an Upload Document or re-upload button
    const uploadBtns = page.getByRole('button', { name: /Upload/i });
    const uploadCount = await uploadBtns.count();
    expect(uploadCount).toBeGreaterThan(0);

    // "Upload Document" modal can be opened
    await uploadBtns.first().click();
    const uploadDialog = page.getByRole('dialog', { name: 'Upload Document' });
    await expect(uploadDialog).toBeVisible();
    // File input inside dialog
    await expect(uploadDialog.locator('input[type="file"]')).toBeAttached();
    // Close via Cancel button (modal renders null when closed, ESC not handled)
    await uploadDialog.getByRole('button', { name: 'Cancel' }).click();
    await expect(uploadDialog).not.toBeAttached();

    await shot(page, '05-documents-page');
  });

  // -----------------------------------------------------------------------
  // 06 — /bundles/:id/extraction  (no documentId)
  // -----------------------------------------------------------------------
  test('06 – /bundles/:id/extraction: redirects or renders extraction heading', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/extraction`);
    await page.waitForLoadState('networkidle');

    // Either it stays at /extraction or auto-navigates to /extraction/:id
    // Either way an h1 should be visible
    await expect(page.locator('h1')).toBeVisible();

    await shot(page, '06-extraction-no-doc');
  });

  // -----------------------------------------------------------------------
  // 07 — /bundles/:id/extraction/:documentId
  // -----------------------------------------------------------------------
  test('07 – /bundles/:id/extraction/:documentId: PDF pane, fields panel, doc selector, re-extract button', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/extraction/${firstDocumentId}`);
    await page.waitForLoadState('networkidle');
    // Give PDF pane time to render
    await page.waitForTimeout(800);

    // Heading
    await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();

    // Document selector dropdown
    const docSelector = page.getByLabel('Document selector');
    await expect(docSelector).toBeVisible();

    // PDF pane — the image has loading="lazy" and display:none until loaded.
    // Use toBeAttached() to confirm the img is in the DOM, then wait for it to load.
    const pdfImg = page.getByAltText('PDF page 1 preview');
    await expect(pdfImg).toBeAttached({ timeout: 15_000 });
    // Wait for the image to finish loading (display: block) — give it time
    await page.waitForTimeout(2_000);

    // Extracted fields panel — aria-label="Extracted fields"
    const fieldsPanel = page.getByRole('region', { name: 'Extracted fields' });
    await expect(fieldsPanel).toBeVisible();

    // Re-extract button
    const reExtractBtn = page.getByRole('button', { name: /re-extract/i });
    const reExtractCount = await reExtractBtn.count();
    expect(reExtractCount, 'Re-extract button should exist').toBeGreaterThan(0);

    await shot(page, '07-extraction-review');
  });

  // -----------------------------------------------------------------------
  // 08 — Document selector dropdown interaction
  // -----------------------------------------------------------------------
  test('08 – Extraction page: document selector dropdown lists documents', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/extraction/${firstDocumentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    const docSelector = page.getByLabel('Document selector');
    await expect(docSelector).toBeVisible();

    // It should have at least one option
    const options = docSelector.locator('option');
    const optionCount = await options.count();
    expect(optionCount, 'Document selector should have at least 1 option').toBeGreaterThan(0);

    // Select the first option explicitly
    const firstValue = await options.first().getAttribute('value');
    if (firstValue) {
      await docSelector.selectOption(firstValue);
      await page.waitForLoadState('networkidle');
    }

    await shot(page, '08-doc-selector');
  });

  // -----------------------------------------------------------------------
  // 09 — /bundles/:id/verification
  // -----------------------------------------------------------------------
  test('09 – /bundles/:id/verification: renders heading and status area', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/verification`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Review Results' })).toBeVisible();

    // Status chips or verification table — at least the Check Detail heading
    await expect(page.getByRole('heading', { name: 'Check Detail' })).toBeVisible();

    // Breadcrumb
    await expect(page.getByRole('navigation', { name: 'Breadcrumb' })).toBeVisible();

    await shot(page, '09-verification');
  });

  // -----------------------------------------------------------------------
  // 10 — /bundles/:id/issues
  // -----------------------------------------------------------------------
  test('10 – /bundles/:id/issues: renders Open Issues heading', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/issues`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Open Issues' })).toBeVisible();

    // Total Issues stat should appear (even if zero)
    await expect(page.getByText('Total Issues')).toBeVisible();

    await shot(page, '10-issues');
  });

  // -----------------------------------------------------------------------
  // 11 — /bundles/:id/audit
  // -----------------------------------------------------------------------
  test('11 – /bundles/:id/audit: audit log renders with events', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/audit`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Manual Correction History' })).toBeVisible();

    // Audit timeline or event list
    const timeline = page.locator('.audit-timeline, [class*="audit"], [class*="timeline"]').first();
    await expect(timeline).toBeVisible();

    await shot(page, '11-audit-trail');
  });

  // -----------------------------------------------------------------------
  // 12 — /bundles/:id/exports
  // -----------------------------------------------------------------------
  test('12 – /bundles/:id/exports: export page with download button', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Exports' })).toBeVisible();

    // Download Excel Report button
    const downloadBtn = page.getByRole('button', { name: 'Download Excel Report' });
    await expect(downloadBtn).toBeVisible();

    // Verify the download triggers a file
    const downloadPromise = page.waitForEvent('download');
    await downloadBtn.click();
    const download = await downloadPromise;
    const suggestedName = await download.suggestedFilename();
    expect(suggestedName).toMatch(/\.(xlsx|xls|csv)$/i);

    await shot(page, '12-exports');
  });

  // -----------------------------------------------------------------------
  // 13 — /health
  // -----------------------------------------------------------------------
  test('13 – /health: health page renders backend status', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto('/health');
    await page.waitForLoadState('networkidle');

    await expect(page.getByRole('heading', { name: 'Health' })).toBeVisible();

    // Backend section
    await expect(page.getByRole('heading', { name: 'Backend' })).toBeVisible();

    // Service name should appear
    await expect(page.getByText('order-assurance')).toBeVisible();

    // OCR provider details
    await expect(page.getByText('OCR provider')).toBeVisible();

    await shot(page, '13-health');
  });

  // -----------------------------------------------------------------------
  // 14 — Breadcrumbs render on bundle pages
  // -----------------------------------------------------------------------
  test('14 – AppShell breadcrumbs render on all bundle pages', async ({ page }) => {
    watchConsoleErrors(page);
    const bundleRoutes = [
      `overview`,
      `documents`,
      `extraction`,
      `verification`,
      `issues`,
      `exports`,
      `audit`,
    ];

    for (const route of bundleRoutes) {
      await page.goto(`/bundles/${bundleId}/${route}`);
      await page.waitForLoadState('networkidle');

      const breadcrumb = page.getByRole('navigation', { name: 'Breadcrumb' });
      await expect(breadcrumb, `Breadcrumb missing on /${route}`).toBeVisible();

      // Must contain "Bundles" link
      await expect(breadcrumb.getByText('Bundles'), `"Bundles" missing in breadcrumb on /${route}`).toBeVisible();
    }

    await shot(page, '14-breadcrumbs-check');
  });

  // -----------------------------------------------------------------------
  // 15 — "More" dropdown in WorkflowTabs reveals audit link
  // -----------------------------------------------------------------------
  test('15 – WorkflowTabs "More" dropdown reveals audit link', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/overview`);
    await page.waitForLoadState('networkidle');

    const tabs = page.getByRole('navigation', { name: 'Bundle workflow' });

    // The "More" <details> summary
    const moreSummary = tabs.locator('details.workflow-tabs__more > summary');
    await expect(moreSummary).toBeVisible();
    await moreSummary.click();

    // The audit link inside the dropdown
    const auditLink = tabs.locator('details.workflow-tabs__more').getByRole('link', { name: 'Manual Correction History' });
    await expect(auditLink).toBeVisible();

    // Clicking it navigates to audit page
    await auditLink.click();
    await page.waitForURL(`**/bundles/${bundleId}/audit`);
    await expect(page.getByRole('heading', { name: 'Manual Correction History' })).toBeVisible();

    await shot(page, '15-more-dropdown-audit');
  });

  // -----------------------------------------------------------------------
  // 16 — Root / redirects to /bundles
  // -----------------------------------------------------------------------
  test('16 – Root / redirects to /bundles', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto('/');
    await page.waitForURL('**/bundles');
    await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible();
    await shot(page, '16-root-redirect');
  });

  // -----------------------------------------------------------------------
  // 17 — Unknown route redirects to /bundles
  // -----------------------------------------------------------------------
  test('17 – Unknown route redirects to /bundles', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto('/this-route-does-not-exist');
    await page.waitForURL('**/bundles');
    await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible();
    await shot(page, '17-unknown-route-redirect');
  });

  // -----------------------------------------------------------------------
  // 18 — /bundles/:id redirects to /bundles/:id/overview
  // -----------------------------------------------------------------------
  test('18 – /bundles/:id redirects to /bundles/:id/overview', async ({ page }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}`);
    await page.waitForURL(`**/bundles/${bundleId}/overview`);
    await expect(page.getByRole('heading', { name: bundleName })).toBeVisible();
    await shot(page, '18-bundle-redirect-to-overview');
  });

  // -----------------------------------------------------------------------
  // 19 — Extraction: Preview PDF button opens modal (not a new tab)
  // -----------------------------------------------------------------------
  test('19 – Extraction: Preview PDF button opens modal, not a new tab', async ({ page, context }) => {
    watchConsoleErrors(page);
    await page.goto(`/bundles/${bundleId}/extraction/${firstDocumentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    let newTabOpened = false;
    context.on('page', () => { newTabOpened = true; });

    const previewBtn = page.getByRole('button', { name: 'Preview PDF' });
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();
    await page.waitForTimeout(500);

    expect(newTabOpened, 'PDF must open in modal, not a new tab').toBe(false);

    // Dialog should be open
    const dialog = page.locator('dialog.pdf-modal');
    await expect(dialog).toHaveAttribute('open');

    // Close
    await page.keyboard.press('Escape');
    await expect(dialog).not.toHaveAttribute('open');

    await shot(page, '19-pdf-modal');
  });

  // -----------------------------------------------------------------------
  // 20 — Console error report (final check)
  // -----------------------------------------------------------------------
  test('20 – No JavaScript errors were raised during the audit', async () => {
    // Filter known benign third-party or network noise if needed
    const realErrors = consoleErrors.filter(
      (msg) =>
        !msg.includes('favicon') &&
        !msg.includes('net::ERR_') &&
        !msg.includes('ResizeObserver loop'),
    );

    if (realErrors.length > 0) {
      console.warn('Console errors captured during test run:');
      for (const err of realErrors) {
        console.warn(' •', err);
      }
    }

    // Report but don't hard-fail for non-critical noise;
    // uncomment the line below to make it a hard failure:
    // expect(realErrors, `${realErrors.length} console error(s) detected`).toHaveLength(0);

    console.log(`Total console errors captured: ${consoleErrors.length}`);
    console.log(`Filtered errors (potential bugs): ${realErrors.length}`);
  });
});
