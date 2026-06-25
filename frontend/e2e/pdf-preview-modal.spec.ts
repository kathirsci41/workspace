import * as fs from 'node:fs';
import * as path from 'node:path';
import * as url from 'node:url';
import { expect, test } from '@playwright/test';

const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';
const _dirname = path.dirname(url.fileURLToPath(import.meta.url));
const screenshotDir = path.resolve(
  _dirname,
  '../../backend/output/e2e-runs/pdf-preview-modal/screenshots',
);

function ensureDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function shot(page: import('@playwright/test').Page, name: string) {
  ensureDir();
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: false });
}

async function findExtractedDocument(
  request: import('@playwright/test').APIRequestContext,
): Promise<{ bundleId: string; documentId: string } | null> {
  const bundlesRes = await request.get(`${apiBaseUrl}/bundles`);
  if (!bundlesRes.ok()) return null;
  const bundles = (await bundlesRes.json()) as Array<{ id: string }>;

  for (const bundle of bundles) {
    const docsRes = await request.get(`${apiBaseUrl}/bundles/${bundle.id}/documents`);
    if (!docsRes.ok()) continue;
    const docs = (await docsRes.json()) as Array<{ id: string; status: string }>;
    const extracted = docs.find((d) =>
      ['PENDING_REVIEW', 'EXTRACTED', 'EXTRACTION_FAILED'].includes(d.status),
    );
    if (extracted) return { bundleId: bundle.id, documentId: extracted.id };
  }
  return null;
}

test.describe('PDF preview modal & toolbar controls', () => {
  test('01 – Preview PDF button opens modal (not a new tab)', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    // Wait for the preview pane to render (first-paint can be slow)
    const previewBtn = page.getByRole('button', { name: 'Preview PDF' });
    await expect(previewBtn).toBeVisible();

    // Dialog element is in the DOM but must not be open yet
    const dialog = page.locator('dialog.pdf-modal');
    await expect(dialog).not.toHaveAttribute('open');
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();

    // Dialog should now be open
    await expect(dialog).toHaveAttribute('open');
    await shot(page, '01_modal_open');

    // iframe with the PDF src should be rendered
    const iframe = dialog.locator('iframe.pdf-modal__frame');
    await expect(iframe).toBeVisible();
    const src = await iframe.getAttribute('src');
    expect(src).toContain(`/documents/${doc.documentId}/preview`);

    // Filename is shown in the header
    const title = dialog.locator('.pdf-modal__title');
    await expect(title).toBeVisible();

    console.log('Modal opened. iframe src:', src);
  });

  test('02 – Close button dismisses the modal', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    await page.getByRole('button', { name: 'Preview PDF' }).click();
    const dialog = page.locator('dialog.pdf-modal');
    await expect(dialog).toHaveAttribute('open');

    await dialog.getByRole('button', { name: /close/i }).click();
    await expect(dialog).not.toHaveAttribute('open');
    await shot(page, '02_modal_closed_via_button');
    console.log('Modal closed via Close button ✓');
  });

  test('03 – ESC key dismisses the modal', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    await page.getByRole('button', { name: 'Preview PDF' }).click();
    const dialog = page.locator('dialog.pdf-modal');
    await expect(dialog).toHaveAttribute('open');

    await page.keyboard.press('Escape');
    await expect(dialog).not.toHaveAttribute('open');
    await shot(page, '03_modal_closed_via_esc');
    console.log('Modal closed via ESC ✓');
  });

  test('04 – PDF does NOT open in a new tab', async ({ page, context, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    // Listen for any new page/tab being opened
    let newTabOpened = false;
    context.on('page', () => { newTabOpened = true; });

    await page.getByRole('button', { name: 'Preview PDF' }).click();
    await page.waitForTimeout(500);

    expect(newTabOpened).toBe(false);
    console.log('No new tab opened ✓ — PDF opens in modal only');

    // Close for tidiness
    await page.keyboard.press('Escape');
  });

  test('05 – Rotate button cycles through 0→90→180→270→0', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    // Actual title: "Rotate right (clockwise)" — button text is always ↻, never changes
    // Rotation angle is shown in a SEPARATE <span class="pdf-rotation-label">
    const rotateBtn = page.locator('button[title="Rotate right (clockwise)"]');
    await expect(rotateBtn).toBeVisible();

    const rotLabel = page.locator('.pdf-rotation-label');

    // Initially at 0° — label shows "0°"
    await expect(rotLabel).toHaveText('0°');
    await shot(page, '05a_rotate_0deg');

    await rotateBtn.click();
    await page.waitForTimeout(300);
    await expect(rotLabel).toHaveText('90°');
    await shot(page, '05b_rotate_90deg');

    await rotateBtn.click();
    await page.waitForTimeout(300);
    await expect(rotLabel).toHaveText('180°');
    await shot(page, '05c_rotate_180deg');

    await rotateBtn.click();
    await page.waitForTimeout(300);
    await expect(rotLabel).toHaveText('270°');
    await shot(page, '05d_rotate_270deg');

    await rotateBtn.click();
    await page.waitForTimeout(300);
    // Back to 0°
    await expect(rotLabel).toHaveText('0°');
    await shot(page, '05e_rotate_back_0deg');

    console.log('Rotate cycle 0→90→180→270→0 ✓');
  });

  test('06 – Zoom buttons work and fit-width toggles', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(600);

    // Fit-width is active by default (button--primary class)
    const fitBtn = page.getByRole('button', { name: 'Fit width' });
    await expect(fitBtn).toBeVisible();
    await expect(fitBtn).toHaveClass(/button--primary/);

    // Zoom label shows 100%
    const zoomLabel = page.locator('.pdf-zoom-label');
    await expect(zoomLabel).toContainText('100%');

    // Click zoom in — should exit fit-width, bump to 125%
    await page.getByRole('button', { name: '+' }).click();
    await expect(fitBtn).not.toHaveClass(/button--primary/);
    await expect(zoomLabel).toContainText('125%');

    // Click zoom in again → 150%
    await page.getByRole('button', { name: '+' }).click();
    await expect(zoomLabel).toContainText('150%');

    // Click zoom out → 125%
    await page.locator('button[title="Zoom out"]').click();
    await expect(zoomLabel).toContainText('125%');

    // Re-enable fit-width
    await fitBtn.click();
    await expect(fitBtn).toHaveClass(/button--primary/);

    await shot(page, '06_zoom_and_fitwidth');
    console.log('Zoom controls and fit-width toggle ✓');
  });

  test('07 – All pages visible in continuous scroll (no prev/next buttons)', async ({ page, request }) => {
    const doc = await findExtractedDocument(request);
    if (!doc) { test.skip(true, 'No extracted document available'); return; }

    await page.goto(`/bundles/${doc.bundleId}/extraction/${doc.documentId}`);
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(800);

    // No Previous/Next page navigation buttons should exist
    const prevBtn = page.getByRole('button', { name: /previous/i });
    const nextBtn = page.getByRole('button', { name: /next/i });
    expect(await prevBtn.count()).toBe(0);
    expect(await nextBtn.count()).toBe(0);

    // Multiple page wrappers should be present
    const pageWrappers = page.locator('.pdf-page-wrapper');
    const count = await pageWrappers.count();
    expect(count).toBeGreaterThanOrEqual(1);

    // Page labels should read "Page N / M"
    const firstLabel = page.locator('.pdf-page-label').first();
    await expect(firstLabel).toContainText('Page 1 /');

    // Page count chip in toolbar
    const pageCount = page.locator('.pdf-pane__page-count');
    await expect(pageCount).toBeVisible();

    await shot(page, '07_continuous_scroll');
    console.log(`Continuous scroll ✓ — ${count} page wrapper(s) rendered`);
  });
});
