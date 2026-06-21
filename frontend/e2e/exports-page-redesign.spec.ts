import { test, expect } from '@playwright/test';

const BASE = 'http://localhost:5173';

test.describe('Export Page — Redesign (Phase 1xK-A)', () => {
  let bundleId: string;

  test.beforeAll(async ({ request }) => {
    // Create a minimal test bundle
    const resp = await request.post(`${BASE.replace('5173', '8100')}/api/bundles`, {
      data: { bundle_number: 'EXPORT-TEST-1xK', customer_name: 'Export Test Co' },
    });
    expect(resp.ok()).toBeTruthy();
    bundleId = (await resp.json()).id;
  });

  test('export page shows KPI cards', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    // KPI grid should be present
    const kpiGrid = page.locator('.export-kpi-grid');
    await expect(kpiGrid).toBeVisible();

    // All 6 KPI cards
    const cards = kpiGrid.locator('.kpi-card');
    await expect(cards).toHaveCount(6);
  });

  test('export page shows main finding section', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const finding = page.locator('.export-finding');
    await expect(finding).toBeVisible();
    await expect(finding.locator('h2')).toHaveText('Main Finding');
  });

  test('export page shows document coverage table in Build 1 order', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const table = page.locator('.export-coverage-table');
    await expect(table).toBeVisible();

    const rows = table.locator('tbody tr');
    await expect(rows).toHaveCount(5);

    // Verify Build 1 order
    const labels = await rows.locator('.export-coverage-table__group').allTextContents();
    expect(labels[0]).toBe('Customer PO');
    expect(labels[1]).toBe('Vendor PO');
    expect(labels[2]).toBe('Vendor Bills');
    expect(labels[3]).toBe('Company DC');
    expect(labels[4]).toBe('Company Invoice');
  });

  test('export page shows header with bundle info', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const header = page.locator('.export-header');
    await expect(header).toBeVisible();
    await expect(header).toContainText('EXPORT-TEST-1xK');
  });

  test('download button is visible and enabled', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const btn = page.locator('.export-actions').getByRole('button', { name: /download excel report/i });
    await expect(btn).toBeVisible();
    await expect(btn).toBeEnabled();
  });

  test('view verification button navigates to verification page', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const btn = page.locator('.export-actions').getByRole('button', { name: /view verification/i });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page).toHaveURL(/\/verification/);
  });

  test('view documents button navigates to documents page', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await page.waitForLoadState('networkidle');

    const btn = page.locator('.export-actions').getByRole('button', { name: /view documents/i });
    await expect(btn).toBeVisible();
    await btn.click();
    await expect(page).toHaveURL(/\/documents/);
  });
});
