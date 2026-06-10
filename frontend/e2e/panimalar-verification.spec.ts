import { expect, test } from '@playwright/test';
import fs from 'fs';
import path from 'path';

const artifactRoot = path.resolve('../..', 'tests/artifacts/order-assurance-e2e');
const screenshotDir = path.join(artifactRoot, 'screenshots');
const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';

test('Build 1 Panimalar verification workflow surfaces backend data', async ({ page, request }) => {
  fs.mkdirSync(path.join(artifactRoot, 'api'), { recursive: true });
  fs.mkdirSync(screenshotDir, { recursive: true });

  const bundleNumber = `OA-PANIMALAR-${Date.now()}`;
  const bundle = await postJson<{ id: string; bundle_number: string }>(request, '/bundles', {
    bundle_number: bundleNumber,
    customer_name: 'PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
  });
  const bundleId = bundle.id;
  const invoice = await uploadDocument(request, bundleId, 'COMPANY_INVOICE', 'Customer Invoice 1ITR2526001878.pdf', [
    'Tax Invoice',
    'Invoice No 1ITR2526001878',
    'Customer Order PMCH/024',
    'SO 1OTM2526001611',
    'Nett Amount 874439',
  ]);
  await patchJson(request, `/documents/${invoice.id}/extracted-data`, {
    reason: 'field missing',
    fields: {
      invoice_no: '1ITR2526001878',
      customer_order_no: 'PMCH/024',
      so_no: '1OTM2526001611',
      customer_name: 'PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE',
      net_amount: 874439,
    },
  });

  const [documents, auditEvents, verification] = await Promise.all([
    request.get(`${apiBaseUrl}/bundles/${bundleId}/documents`),
    request.get(`${apiBaseUrl}/bundles/${bundleId}/audit-events`),
    request.get(`${apiBaseUrl}/bundles/${bundleId}/verification-summary`),
  ]);
  expect(documents.ok()).toBeTruthy();
  expect(auditEvents.ok()).toBeTruthy();
  expect(verification.ok()).toBeTruthy();

  const documentPayload = await documents.json();
  fs.writeFileSync(path.join(artifactRoot, 'api', 'documents.json'), JSON.stringify(documentPayload, null, 2));
  fs.writeFileSync(path.join(artifactRoot, 'api', 'audit-events.json'), JSON.stringify(await auditEvents.json(), null, 2));
  fs.writeFileSync(path.join(artifactRoot, 'api', 'verification-summary.json'), JSON.stringify(await verification.json(), null, 2));

  await page.goto('/bundles');
  await expect(page.getByRole('heading', { name: 'Bundles' })).toBeVisible();
  await expect(page.getByRole('link', { name: new RegExp(bundleNumber) })).toHaveCount(0);
  await page.screenshot({ path: path.join(screenshotDir, 'build1-bundles.png'), fullPage: true });

  await page.goto(`/bundles/${bundleId}/overview`);
  await expect(page.getByRole('heading', { name: bundleNumber })).toBeVisible();
  await expect(page.getByText('Document Inventory')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Review Results' })).toBeVisible();
  await page.screenshot({ path: path.join(screenshotDir, 'build1-overview.png'), fullPage: true });

  await page.goto(`/bundles/${bundleId}/documents`);
  await expect(page.getByRole('heading', { name: 'Documents', exact: true })).toBeVisible();
  await expect(page.getByText('Customer PO')).toBeVisible();
  await expect(page.getByText('Vendor Invoice')).toBeVisible();

  const firstDocumentId = documentPayload[0]?.id;
  expect(firstDocumentId).toBeTruthy();
  await page.goto(`/bundles/${bundleId}/extraction/${firstDocumentId}`);
  await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();
  await expect(page.getByLabel('Document selector')).toBeVisible();
  await expect(page.getByAltText('PDF page 1 preview')).toBeVisible();

  await page.goto(`/bundles/${bundleId}/verification`);
  await expect(page.getByRole('heading', { name: 'Review Results' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Check Detail' })).toBeVisible();
  await expect(page.getByText('No verification checks returned.')).toBeVisible();

  await page.goto(`/bundles/${bundleId}/issues`);
  await expect(page.getByRole('heading', { name: 'Open Issues' })).toBeVisible();
  await expect(page.getByText('Total Issues')).toBeVisible();

  await page.goto(`/bundles/${bundleId}/audit`);
  await expect(page.getByRole('heading', { name: 'Manual Correction History' })).toBeVisible();

  await page.goto(`/bundles/${bundleId}/exports`);
  await expect(page.getByRole('heading', { name: 'Exports' })).toBeVisible();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Download Excel Report' }).click();
  const download = await downloadPromise;
  await download.saveAs(path.join(artifactRoot, 'api', 'build1-ui-export.xlsx'));
});

async function uploadDocument(
  request: import('@playwright/test').APIRequestContext,
  bundleId: string,
  documentType: string,
  filename: string,
  lines: string[],
) {
  const response = await request.post(`${apiBaseUrl}/bundles/${bundleId}/documents`, {
    multipart: {
      document_type: documentType,
      file: {
        name: filename,
        mimeType: 'application/pdf',
        buffer: createSimplePdf(lines),
      },
    },
  });
  expect(response.ok()).toBeTruthy();
  return (await response.json()) as { id: string };
}

async function postJson<T>(request: import('@playwright/test').APIRequestContext, pathName: string, payload: unknown): Promise<T> {
  const response = await request.post(`${apiBaseUrl}${pathName}`, { data: payload });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<T>;
}

async function patchJson(request: import('@playwright/test').APIRequestContext, pathName: string, payload: unknown) {
  const response = await request.patch(`${apiBaseUrl}${pathName}`, { data: payload });
  expect(response.ok()).toBeTruthy();
}

function createSimplePdf(lines: string[]): Buffer {
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
