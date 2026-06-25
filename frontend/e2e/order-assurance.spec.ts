/**
 * Order Assurance — End-to-End Playwright Tests
 *
 * Run:
 *   npx playwright install chromium   (first time only)
 *   npx playwright test e2e/order-assurance.spec.ts --headed
 *
 * Requires app running:
 *   .\scripts\run-local.ps1
 */

import { test, expect, Page } from '@playwright/test';

const BASE = 'http://localhost:5180';
const API  = 'http://localhost:8100/api';

// ─── helpers ─────────────────────────────────────────────────────────────────

async function waitForApp(page: Page) {
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 15_000 });
}

async function createOrder(page: Page, name: string): Promise<string> {
  await page.goto(`${BASE}/bundles`);
  await page.getByRole('button', { name: 'Create Order' }).click();
  // Scope to dialog to avoid strict-mode collision with the Sort dropdown
  // (whose option text "Bundle name" partially matches getByLabel without scoping)
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Bundle name').fill(name);
  await dialog.getByRole('button', { name: 'Create verification bundle' }).click();
  // Wait for redirect to bundle overview
  await page.waitForURL(/\/bundles\/[a-f0-9-]+\/overview/, { timeout: 10_000 });
  return page.url().match(/\/bundles\/([a-f0-9-]+)\//)?.[1] ?? '';
}

// ─── Suite 1: App loads ───────────────────────────────────────────────────────

test.describe('App shell', () => {
  test('loads home page and shows Orders link', async ({ page }) => {
    await waitForApp(page);
    await expect(page).toHaveTitle(/Order Assurance/i);
    await expect(page.getByRole('heading', { name: 'Orders' })).toBeVisible();
  });

  test('navigates to /bundles and renders Orders page', async ({ page }) => {
    await page.goto(`${BASE}/bundles`);
    await expect(page.getByRole('heading', { name: /orders/i })).toBeVisible();
    // KPI cards should appear
    await expect(page.getByText(/total orders/i)).toBeVisible();
  });

  test('shows empty state when no orders exist', async ({ page }) => {
    await page.goto(`${BASE}/bundles`);
    // Wait for data to load (avoids false-negative during async fetch)
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500);
    // Either a table row OR an empty-state message should be present
    const hasRow = await page.locator('table tbody tr').count() > 0;
    if (!hasRow) {
      await expect(page.getByText('No orders found')).toBeVisible();
    }
  });
});

// ─── Suite 2: Create Order ────────────────────────────────────────────────────

test.describe('Create Order', () => {
  test('opens modal, fills name, creates order', async ({ page }) => {
    await page.goto(`${BASE}/bundles`);
    await page.getByRole('button', { name: 'Create Order' }).click();

    // Modal visible
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('heading', { name: /create order/i })).toBeVisible();

    // Fill and submit — scope to dialog to avoid strict-mode collision
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Bundle name').fill('E2E-Test-Order-01');
    await dialog.getByRole('button', { name: 'Create verification bundle' }).click();

    // Redirected to overview
    await page.waitForURL(/\/bundles\/[a-f0-9-]+\/overview/, { timeout: 10_000 });
    await expect(page.getByText(/E2E-Test-Order-01/i)).toBeVisible();
  });

  test('submit is disabled when name is blank', async ({ page }) => {
    await page.goto(`${BASE}/bundles`);
    await page.getByRole('button', { name: 'Create Order' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    // The submit button is HTML-disabled when the input is empty
    const submitBtn = page.getByRole('button', { name: 'Create verification bundle' });
    await expect(submitBtn).toBeDisabled();
    // Dialog stays open
    await expect(page.getByRole('dialog')).toBeVisible();
  });

  test('cancel closes modal without creating', async ({ page }) => {
    await page.goto(`${BASE}/bundles`);
    const before = await page.locator('table tbody tr').count();
    await page.getByRole('button', { name: 'Create Order' }).click();
    await page.getByRole('button', { name: 'Cancel' }).click();
    await expect(page.getByRole('dialog')).not.toBeVisible();
    const after = await page.locator('table tbody tr').count();
    expect(after).toBe(before);
  });
});

// ─── Suite 3: Order Overview page ────────────────────────────────────────────

test.describe('Order Overview', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Overview-Test');
    await page.close();
  });

  test('shows KPI cards', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    await expect(page.getByLabel('Order overview KPIs')).toBeVisible();
    await expect(page.getByText(/overall status/i)).toBeVisible();
    await expect(page.getByText(/documents uploaded/i)).toBeVisible();
    await expect(page.getByText(/extraction progress/i)).toBeVisible();
  });

  test('shows Document Inventory section', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    await expect(page.getByRole('heading', { name: /document inventory/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /manage documents/i })).toBeVisible();
  });

  test('Approve Order button is present and clickable', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    const btn = page.getByRole('button', { name: /approve order/i });
    await expect(btn).toBeVisible();
    await btn.click();
    // Should toggle to Revoke Approval
    await expect(page.getByRole('button', { name: /revoke approval/i })).toBeVisible({ timeout: 5_000 });
    // Toggle back
    await page.getByRole('button', { name: /revoke approval/i }).click();
    await expect(page.getByRole('button', { name: /approve order/i })).toBeVisible({ timeout: 5_000 });
  });

  test('workflow tabs are present', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    const tabs = ['Overview', 'Documents', 'Extraction Review', 'Review Results', 'Open Issues', 'Export', 'Audit'];
    for (const tab of tabs) {
      await expect(page.getByRole('link', { name: tab })).toBeVisible();
    }
  });
});

// ─── Suite 4: Documents tab ───────────────────────────────────────────────────

test.describe('Documents tab', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Docs-Test');
    await page.close();
  });

  test('renders document slot grid', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/documents`);
    await expect(page.getByRole('heading', { name: /documents in order/i })).toBeVisible();
    // 5 required document types
    const slots = ['Customer PO', 'Company Invoice', 'Company DC', 'Company PO', 'Vendor Invoice'];
    for (const slot of slots) {
      await expect(page.getByText(new RegExp(slot, 'i'))).toBeVisible();
    }
  });

  test('shows upload button for each slot', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/documents`);
    const uploadBtns = page.getByRole('button', { name: /upload/i });
    await expect(uploadBtns.first()).toBeVisible();
  });
});

// ─── Suite 5: Extraction Review page ─────────────────────────────────────────

test.describe('Extraction Review page', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Extraction-Test');
    await page.close();
  });

  test('loads without error', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/extraction`);
    await expect(page.getByRole('heading', { name: /extraction review/i })).toBeVisible();
    await expect(page.getByText(/documents in order/i)).toBeVisible();
  });

  test('document selector dropdown is present', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/extraction`);
    await expect(page.getByRole('combobox').or(page.locator('select'))).toBeVisible();
  });
});

// ─── Suite 6: Review Results page ────────────────────────────────────────────

test.describe('Review Results page', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Review-Test');
    await page.close();
  });

  test('loads without error', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/verification`);
    await expect(page.getByRole('heading', { name: /review results/i })).toBeVisible();
  });

  test('shows verification summary section', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/verification`);
    // Either results or an empty state
    const hasResults = await page.getByText(/customer side/i).isVisible().catch(() => false);
    const hasEmpty = await page.getByText(/no verification/i).isVisible().catch(() => false);
    expect(hasResults || hasEmpty).toBe(true);
  });
});

// ─── Suite 7: Open Issues page ───────────────────────────────────────────────

test.describe('Open Issues page', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Issues-Test');
    await page.close();
  });

  test('loads without error', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/issues`);
    await expect(page.getByRole('heading', { name: /open issues/i })).toBeVisible();
  });

  test('status filter dropdown is present', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/issues`);
    // Open / Dismissed / All filter
    await expect(page.locator('select, [role="listbox"]').first()).toBeVisible();
  });

  test('issue detail panel shows placeholder when nothing selected', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/issues`);
    await expect(page.getByText(/select an issue/i)).toBeVisible();
  });
});

// ─── Suite 8: Export page ────────────────────────────────────────────────────

test.describe('Export page', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Export-Test');
    await page.close();
  });

  test('loads without error', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await expect(page.getByRole('heading', { name: /export/i })).toBeVisible();
  });

  test('export button is present', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/exports`);
    await expect(page.getByRole('button', { name: /download|export/i })).toBeVisible();
  });
});

// ─── Suite 9: Audit Trail page ───────────────────────────────────────────────

test.describe('Audit Trail', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Audit-Test');
    await page.close();
  });

  test('loads without error', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/audit`);
    await expect(page.getByRole('heading', { name: /audit/i })).toBeVisible();
  });

  test('shows empty state for new order', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/audit`);
    await expect(page.getByText(/no manual corrections/i)).toBeVisible();
  });
});

// ─── Suite 10: Navigation + breadcrumbs ──────────────────────────────────────

test.describe('Navigation', () => {
  let bundleId: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    bundleId = await createOrder(page, 'E2E-Nav-Test');
    await page.close();
  });

  test('breadcrumb Orders link returns to list', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    await page.getByRole('link', { name: /^orders$/i }).click();
    await expect(page).toHaveURL(/\/bundles$/);
  });

  test('workflow tab links work', async ({ page }) => {
    await page.goto(`${BASE}/bundles/${bundleId}/overview`);
    await page.getByRole('link', { name: 'Documents' }).click();
    await expect(page).toHaveURL(new RegExp(`/bundles/${bundleId}/documents`));
  });

  test('unknown route redirects gracefully', async ({ page }) => {
    await page.goto(`${BASE}/bundles/00000000-0000-0000-0000-000000000000/overview`);
    // Should either show an error state or redirect, not crash
    const crashed = await page.getByText(/something went wrong|unhandled/i).isVisible().catch(() => false);
    expect(crashed).toBe(false);
  });
});

// ─── Suite 11: API health ─────────────────────────────────────────────────────

test.describe('Backend API', () => {
  test('health endpoint returns ok', async ({ request }) => {
    const res = await request.get(`${API}/health`);
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body).toMatchObject({ status: 'ok' });
  });

  test('GET /api/bundles returns array', async ({ request }) => {
    const res = await request.get(`${API}/bundles`);
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
  });

  test('POST /api/bundles creates order', async ({ request }) => {
    const res = await request.post(`${API}/bundles`, {
      data: { bundle_number: 'E2E-API-Test-' + Date.now() },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body).toHaveProperty('id');
    expect(body).toHaveProperty('status');
  });

  test('GET /api/bundles/:id returns order', async ({ request }) => {
    // Create first
    const create = await request.post(`${API}/bundles`, {
      data: { bundle_number: 'E2E-API-Get-' + Date.now() },
    });
    const { id } = await create.json();
    const res = await request.get(`${API}/bundles/${id}`);
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body.id).toBe(id);
  });

  test('PATCH /api/bundles/:id/status to APPROVED', async ({ request }) => {
    const create = await request.post(`${API}/bundles`, {
      data: { bundle_number: 'E2E-Approve-' + Date.now() },
    });
    const { id } = await create.json();
    const res = await request.patch(`${API}/bundles/${id}/status`, {
      data: { status: 'APPROVED' },
    });
    expect(res.ok()).toBe(true);
    const body = await res.json();
    expect(body.status).toBe('APPROVED');
  });
});
