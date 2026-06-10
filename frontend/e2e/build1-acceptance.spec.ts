import { expect, test, type Page } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const artifactRoot = path.resolve('../..', 'tests/artifacts/order-assurance-acceptance');
const screenshotDir = path.join(artifactRoot, 'screenshots');
const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';

const documents = [
  {
    type: 'CUSTOMER_PO',
    label: 'Customer PO',
    filename: 'Customer PO PMCH-024.pdf',
    lines: [
      'Purchase Order No: PMCH&RI/024/2025-2026',
      'PO Date: 30/01/2026',
      'Customer Name: PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
      'Billing Address: Poonamallee Chennai',
      'Delivery Address: Poonamallee Chennai',
      'Subtotal: 741050',
      'Tax Amount: 133389',
      'Grand Total: 874439',
      'Total Quantity: 9',
    ],
  },
  {
    type: 'COMPANY_INVOICE',
    label: 'Company Invoice',
    filename: 'Company Invoice 1ITR2526001878.pdf',
    lines: [
      'Tax Invoice',
      'Invoice No',
      '1ITR2526001878',
      '1OTM2526001611',
      'PMCH&RI/024/2025-2026',
      'Invoice Date',
      '13/02/2026',
      'Customer Name & Detail',
      'PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
      'Nett Amount',
      '874439',
      '133389',
      '741050',
    ],
  },
  {
    type: 'COMPANY_DC',
    label: 'Company Delivery Challan / DC',
    filename: 'Company DC 1DNT2526DC3100.pdf',
    lines: [
      'Delivery Challan',
      '1DNT2526DC3100',
      'DC Date',
      '13/02/2026',
      '1OTM2526009999',
      'PMCH&RI/024/2025-2026',
      'Delivery To',
      'PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
      '741050',
      '741050',
      '9',
      'Total',
    ],
  },
  {
    type: 'COMPANY_PO',
    label: 'Company PO to Vendor',
    filename: 'Company PO 1PTR2526000467.pdf',
    lines: [
      'Purchase Order',
      '1PTR2526000467',
      'Order Date',
      '30/01/2026',
      'SUPREME COMPUTERS INDIA P LTD',
      'Vendor Name & Address',
      'NOT ALLOWED',
      'ON FULL DELIVERY',
      'Net Amount',
      '696200',
    ],
  },
  {
    type: 'VENDOR_INVOICE',
    label: 'Vendor Invoice',
    filename: 'Vendor Invoice 2526PSI25087738.pdf',
    lines: [
      'TAX INVOICE',
      'Invoice No: 2526PSI25087738',
      'Invoice Date: 12-02-2026',
      'Vendor Name: SUPREME COMPUTERS INDIA P LTD',
      'PO No: 1PTR2526000467',
      'Grand Total: 696200',
    ],
  },
] as const;

test('Build 1 full UI acceptance workflow', async ({ page, request }) => {
  test.setTimeout(180_000);
  fs.mkdirSync(screenshotDir, { recursive: true });
  fs.mkdirSync(path.join(artifactRoot, 'downloads'), { recursive: true });

  const bundleNumber = `PANIMALAR-ORDER-${Date.now()}`;

  await page.goto('/bundles');
  await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible();

  await page.getByRole('button', { name: 'Create Bundle' }).click();
  const createDialog = page.getByRole('dialog', { name: 'Create Bundle' });
  await createDialog.getByLabel('Bundle name').fill(bundleNumber);
  await createDialog.getByRole('button', { name: 'Create verification bundle' }).click();
  await page.waitForURL(/\/bundles\/[^/]+\/overview$/);

  const bundleId = page.url().split('/').at(-2);
  expect(bundleId).toBeTruthy();
  await expect(page.getByRole('heading', { name: bundleNumber })).toBeVisible();

  await page
    .getByRole('navigation', { name: 'Bundle workflow' })
    .getByRole('link', { name: 'Documents', exact: true })
    .click();
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();

  for (const document of documents) {
    await uploadThroughUi(page, document.label, document.filename, document.lines);
  }

  for (const document of documents) {
    const card = documentCard(page, document.label);
    const previewLink = card.getByRole('link', { name: 'Preview PDF' });
    const previewResponse = await request.get(await previewLink.getAttribute('href') ?? '');
    expect(previewResponse.ok()).toBeTruthy();
    expect(previewResponse.headers()['content-type']).toContain('application/pdf');
  }

  for (const document of documents) {
    const card = documentCard(page, document.label);
    await card.getByRole('button', { name: 'Run Extraction', exact: true }).click();
    await card.getByText('More', { exact: true }).click();
    await expect(card.getByRole('button', { name: 'Re-extract', exact: true })).toBeVisible({ timeout: 30_000 });
  }

  const companyInvoiceCard = documentCard(page, 'Company Invoice');
  await companyInvoiceCard.getByRole('button', { name: 'Re-extract', exact: true }).click();
  await expect(companyInvoiceCard.getByRole('button', { name: 'Re-extract', exact: true })).toBeVisible({ timeout: 30_000 });
  const documentsLayout = await page.evaluate(() => ({
    viewportWidth: window.innerWidth,
    pageWidth: document.documentElement.scrollWidth,
    maxBadgeHeight: Math.max(
      ...Array.from(document.querySelectorAll<HTMLElement>('.document-slot__header .status-badge'))
        .map((badge) => badge.getBoundingClientRect().height),
    ),
  }));
  expect(documentsLayout.pageWidth).toBeLessThanOrEqual(documentsLayout.viewportWidth);
  expect(documentsLayout.maxBadgeHeight).toBeLessThanOrEqual(32);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: screenshotPath('03-documents.png'), fullPage: true });

  const documentResponse = await request.get(`${apiBaseUrl}/bundles/${bundleId}/documents`);
  expect(documentResponse.ok()).toBeTruthy();
  const documentPayload = await documentResponse.json() as Array<{
    id: string;
    document_type: string;
    metadata?: { status?: string; extracted_data?: Record<string, unknown> };
  }>;
  expect(documentPayload).toHaveLength(5);
  expect(documentPayload.every((document) => document.metadata?.status === 'EXTRACTED')).toBeTruthy();

  const invoice = documentPayload.find((document) => document.document_type === 'COMPANY_INVOICE');
  expect(invoice?.metadata?.extracted_data?.invoice_number).toBe('1ITR2526001878');

  await companyInvoiceCard.getByRole('link', { name: 'Review Extraction', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();
  await expect(page.getByAltText('PDF page 1 preview')).toBeVisible();

  await page.getByRole('button', { name: 'Correct Invoice Number' }).first().click();
  const correctionDialog = page.getByRole('dialog', { name: 'Manual Correction' });
  await correctionDialog.getByLabel('Corrected value').fill('1ITR2526001888');
  await correctionDialog.getByLabel('Correction reason').selectOption('corrected wrong value');
  await correctionDialog.getByRole('button', { name: 'Save manual correction' }).click();
  await expect(correctionDialog).toBeHidden();
  await expect(page.getByRole('cell', { name: '1ITR2526001888', exact: true })).toBeVisible();
  await page.screenshot({ path: screenshotPath('04-extraction-review.png'), fullPage: true });

  const auditResponse = await request.get(`${apiBaseUrl}/bundles/${bundleId}/audit-events`);
  expect(auditResponse.ok()).toBeTruthy();
  const auditPayload = await auditResponse.json() as Array<{ event_type: string; payload?: Record<string, unknown> }>;
  expect(auditPayload.some((event) => event.event_type === 'manual_extracted_data_patched')).toBeTruthy();

  await page.goto(`/bundles/${bundleId}/verification`);
  await expect(page.getByRole('heading', { name: 'Review Results' })).toBeVisible();
  await expect(page.getByRole('table', { name: 'Review checks' }).first()).toBeVisible();
  const summaryResponse = await request.get(`${apiBaseUrl}/bundles/${bundleId}/verification-summary`);
  expect(summaryResponse.ok()).toBeTruthy();
  const summary = await summaryResponse.json() as { checks: Array<{ result: string }>; bundle_status: string };
  expect(summary.checks.length).toBeGreaterThan(0);
  expect(summary.checks.some((check) => check.result === 'MISMATCH')).toBeTruthy();
  await page.screenshot({ path: screenshotPath('05-verification.png'), fullPage: true });

  await page.goto(`/bundles/${bundleId}/issues`);
  await expect(page.getByRole('heading', { name: 'Open Issues' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Action Queue' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'SO number differs between invoice and DC' })).toBeVisible();
  await page.screenshot({ path: screenshotPath('06-issues.png'), fullPage: true });

  await page.goto(`/bundles/${bundleId}/audit`);
  await expect(page.getByRole('heading', { name: 'Manual Correction History' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Manual Correction', exact: true })).toBeVisible();
  await page.screenshot({ path: screenshotPath('07-audit.png'), fullPage: true });

  await page.goto(`/bundles/${bundleId}/exports`);
  await expect(page.getByRole('heading', { name: 'Exports' })).toBeVisible();
  await page.screenshot({ path: screenshotPath('08-exports.png'), fullPage: true });
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download Excel Report' }).click();
  const download = await downloadPromise;
  const downloadPath = path.join(artifactRoot, 'downloads', await download.suggestedFilename());
  await download.saveAs(downloadPath);
  expect(fs.statSync(downloadPath).size).toBeGreaterThan(1_000);

  await page.goto(`/bundles/${bundleId}/overview`);
  await expect(page.getByRole('heading', { name: bundleNumber })).toBeVisible();
  await page.screenshot({ path: screenshotPath('02-overview.png'), fullPage: true });

  await page.goto('/bundles');
  await expect(page.getByRole('table', { name: 'Bundles table' })).toBeVisible();
  await expect(page.getByRole('link', { name: `Open Bundle ${bundleNumber}` })).toHaveCount(0);
  await page.screenshot({ path: screenshotPath('01-bundles.png'), fullPage: true });
});

function documentCard(page: Page, label: string) {
  return page.getByRole('article').filter({ has: page.getByRole('heading', { name: label, exact: true }) });
}

async function uploadThroughUi(page: Page, label: string, filename: string, lines: readonly string[]) {
  const card = documentCard(page, label);
  await card.getByRole('button', { name: 'Upload Document', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Upload Document' });
  await dialog.locator('input[type="file"]').setInputFiles({
    name: filename,
    mimeType: 'application/pdf',
    buffer: createSimplePdf(lines),
  });
  await dialog.getByRole('button', { name: 'Upload', exact: true }).click();
  await expect(dialog).toBeHidden();
  await expect(card.getByText(filename, { exact: true })).toBeVisible();
}

function screenshotPath(filename: string): string {
  return path.join(screenshotDir, filename);
}

function createSimplePdf(lines: readonly string[]): Buffer {
  const textCommands = lines.map((line, index) => `1 0 0 1 72 ${760 - index * 18} Tm (${escapePdfText(line)}) Tj`).join('\n');
  const stream = `BT\n/F1 11 Tf\n${textCommands}\nET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(stream, 'utf8')} >>\nstream\n${stream}\nendstream`,
  ];
  const chunks = ['%PDF-1.4\n'];
  const offsets = [0];
  for (let index = 0; index < objects.length; index += 1) {
    offsets.push(Buffer.byteLength(chunks.join(''), 'utf8'));
    chunks.push(`${index + 1} 0 obj\n${objects[index]}\nendobj\n`);
  }
  const xrefOffset = Buffer.byteLength(chunks.join(''), 'utf8');
  chunks.push(`xref\n0 ${objects.length + 1}\n`);
  chunks.push('0000000000 65535 f \n');
  for (const offset of offsets.slice(1)) {
    chunks.push(`${String(offset).padStart(10, '0')} 00000 n \n`);
  }
  chunks.push(`trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`);
  return Buffer.from(chunks.join(''), 'utf8');
}

function escapePdfText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
}
