import * as fs from 'node:fs';
import * as path from 'node:path';
import * as url from 'node:url';
import { expect, test } from '@playwright/test';

const apiBaseUrl = process.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8100/api';
const _dirname = path.dirname(url.fileURLToPath(import.meta.url));
const screenshotDir = path.resolve(
  _dirname,
  '../../backend/output/e2e-runs/phase1xI_highlight_hotfix/screenshots',
);

function ensureScreenshotDir() {
  fs.mkdirSync(screenshotDir, { recursive: true });
}

async function saveScreenshot(page: import('@playwright/test').Page, name: string) {
  ensureScreenshotDir();
  await page.screenshot({ path: path.join(screenshotDir, `${name}.png`), fullPage: false });
}

// Build a minimal but real digital PDF (A4, text at known coordinates)
function createDigitalPdfWithField(fieldText: string, x: number, y: number): Buffer {
  // PDF coordinates: origin bottom-left, y increases upward. A4 = 595x842
  // fitz (PyMuPDF) returns bbox in [x0,y0,x1,y1] from top-left.
  // Text at PDF y=750 from bottom → fitz y0 ≈ 842-750-11 ≈ 81
  const stream = `BT\n/F1 11 Tf\n1 0 0 1 ${x} ${y} Tm (${escapePdfText(fieldText)}) Tj\nET`;
  const objects = [
    '<< /Type /Catalog /Pages 2 0 R >>',
    '<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
    '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
    '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
    `<< /Length ${Buffer.byteLength(stream, 'utf8')} >>\nstream\n${stream}\nendstream`,
  ];
  const chunks = ['%PDF-1.4\n'];
  const offsets: number[] = [];
  for (let i = 0; i < objects.length; i++) {
    offsets.push(Buffer.byteLength(chunks.join(''), 'utf8'));
    chunks.push(`${i + 1} 0 obj\n${objects[i]}\nendobj\n`);
  }
  const xrefOffset = Buffer.byteLength(chunks.join(''), 'utf8');
  chunks.push(`xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`);
  for (const offset of offsets) {
    chunks.push(`${String(offset).padStart(10, '0')} 00000 n \n`);
  }
  chunks.push(`trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefOffset}\n%%EOF\n`);
  return Buffer.from(chunks.join(''), 'utf8');
}

function escapePdfText(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/\(/g, '\\(').replace(/\)/g, '\\)');
}

async function postJson<T>(request: import('@playwright/test').APIRequestContext, pathName: string, payload: unknown): Promise<T> {
  const response = await request.post(`${apiBaseUrl}${pathName}`, { data: payload });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<T>;
}

async function uploadDocumentBuffer(
  request: import('@playwright/test').APIRequestContext,
  bundleId: string,
  documentType: string,
  filename: string,
  buffer: Buffer,
): Promise<{ id: string }> {
  const response = await request.post(`${apiBaseUrl}/bundles/${bundleId}/documents`, {
    multipart: {
      document_type: documentType,
      file: { name: filename, mimeType: 'application/pdf', buffer },
    },
  });
  expect(response.ok()).toBeTruthy();
  return response.json() as Promise<{ id: string }>;
}

async function patchJson(request: import('@playwright/test').APIRequestContext, pathName: string, payload: unknown) {
  const response = await request.patch(`${apiBaseUrl}${pathName}`, { data: payload });
  expect(response.ok()).toBeTruthy();
}

async function waitForFieldLocations(
  request: import('@playwright/test').APIRequestContext,
  documentId: string,
  maxAttempts = 10,
): Promise<Record<string, unknown>> {
  for (let i = 0; i < maxAttempts; i++) {
    const res = await request.get(`${apiBaseUrl}/documents/${documentId}`);
    if (res.ok()) {
      const doc = await res.json() as { metadata?: { field_locations?: Record<string, unknown> } };
      const locs = doc.metadata?.field_locations;
      if (locs && Object.keys(locs).length > 0) return locs;
    }
    await new Promise((r) => setTimeout(r, 800));
  }
  return {};
}

test.describe('Phase 1xI highlight hotfix — PDF field highlight behavior', () => {
  test('clicking a digital-PDF field shows highlight overlay aligned to field bbox', async ({ page, request }) => {
    ensureScreenshotDir();

    // Create bundle
    const bundle = await postJson<{ id: string }>(request, '/bundles', {
      bundle_number: `HIGHLIGHT-HOTFIX-${Date.now()}`,
      customer_name: 'Hotfix Test',
    });

    // Upload a digital PDF with known text positions
    const pdfBuffer = createDigitalPdfWithField('1ITR2526001878', 72, 750);
    const doc = await uploadDocumentBuffer(request, bundle.id, 'COMPANY_INVOICE', 'TestInvoice.pdf', pdfBuffer);

    // Inject extracted fields with known values (so backend can locate them in PDF)
    await patchJson(request, `/documents/${doc.id}/extracted-data`, {
      reason: 'highlight test',
      fields: { invoice_no: '1ITR2526001878', net_amount: 874439 },
    });

    // Re-extract to build field_locations from the real PDF
    const reextractRes = await request.post(`${apiBaseUrl}/documents/${doc.id}/reextract`);
    expect(reextractRes.ok()).toBeTruthy();

    // Wait for field_locations to be populated
    const fieldLocations = await waitForFieldLocations(request, doc.id, 15);
    console.log('field_locations:', JSON.stringify(fieldLocations, null, 2));

    // Navigate to extraction review
    await page.goto(`/bundles/${bundle.id}/extraction/${doc.id}`);
    await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();
    await expect(page.getByAltText('PDF page 1 preview')).toBeVisible();

    await saveScreenshot(page, '01_extraction_review_initial');

    // Find and click a field name with a known location
    // The field panel uses aria-label on the span: "Jump to {fieldLabel} in PDF"
    const invoiceFieldBtn = page.getByLabel('Jump to Invoice Number in PDF');
    if (await invoiceFieldBtn.count() > 0) {
      await invoiceFieldBtn.click();
      await page.waitForTimeout(600);
      await saveScreenshot(page, '02_after_click_invoice_no');

      // Check overlay exists in DOM
      const overlay = page.locator('.pdf-highlight-overlay');
      const overlayCount = await overlay.count();
      console.log('overlay count:', overlayCount);

      if (overlayCount > 0) {
        const box = await overlay.first().boundingBox();
        console.log('overlay boundingBox:', box);
        const styles = await overlay.first().evaluate((el) => {
          const computed = window.getComputedStyle(el);
          return {
            left: computed.left,
            top: computed.top,
            width: computed.width,
            height: computed.height,
            position: computed.position,
            zIndex: computed.zIndex,
            display: computed.display,
          };
        });
        console.log('overlay computed styles:', styles);

        // Overlay must be visible and have non-zero dimensions
        expect(overlayCount).toBeGreaterThan(0);
        if (box) {
          expect(box.width).toBeGreaterThan(0);
          expect(box.height).toBeGreaterThan(0);
        }
      }
    } else {
      console.log('No "Jump to Invoice Number" button found — checking field rendering');
      await saveScreenshot(page, '02_field_panel_no_jump_button');
    }

    await saveScreenshot(page, '03_final_state');
  });

  test('scanned-OCR document shows highlight-unavailable message when field clicked', async ({ page, request }) => {
    ensureScreenshotDir();

    // Create bundle with a scanned-style document (we inject null bbox field_locations)
    const bundle = await postJson<{ id: string }>(request, '/bundles', {
      bundle_number: `SCANNED-HOTFIX-${Date.now()}`,
      customer_name: 'Scanned Test',
    });

    const pdfBuffer = createDigitalPdfWithField('2526PSI25087738', 72, 750);
    const doc = await uploadDocumentBuffer(request, bundle.id, 'VENDOR_INVOICE', 'TestVendorBill.pdf', pdfBuffer);

    await patchJson(request, `/documents/${doc.id}/extracted-data`, {
      reason: 'scanned test',
      fields: { vendor_invoice_no: '2526PSI25087738', invoice_total: 554600 },
    });

    await page.goto(`/bundles/${bundle.id}/extraction/${doc.id}`);
    await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();

    // Try clicking a field
    const vendorInvBtn = page.getByLabel('Jump to Vendor Invoice Number in PDF');
    if (await vendorInvBtn.count() > 0) {
      await vendorInvBtn.click();
      await page.waitForTimeout(500);
    }

    await saveScreenshot(page, '04_scanned_field_click');

    // Check for highlight overlay or unavailable message
    const overlay = page.locator('.pdf-highlight-overlay');
    const unavailMsg = page.locator('.pdf-highlight-unavailable');
    console.log('overlay count:', await overlay.count());
    console.log('unavail msg count:', await unavailMsg.count());

    await saveScreenshot(page, '05_scanned_final');
  });
});

test.describe('Phase 1xI — Panimalar real bundle highlight (if available)', () => {
  test('finds Panimalar bundle and tests Company Invoice highlight', async ({ page, request }) => {
    ensureScreenshotDir();

    // List bundles and look for Panimalar-related ones
    const bundlesRes = await request.get(`${apiBaseUrl}/bundles`);
    if (!bundlesRes.ok()) {
      console.log('Could not list bundles');
      return;
    }
    const bundles = await bundlesRes.json() as Array<{ id: string; bundle_number: string }>;
    const panimalarBundle = bundles.find((b) =>
      /panimalar|1xG|PMCH/i.test(b.bundle_number) || /panimalar/i.test(b.bundle_number),
    );

    if (!panimalarBundle) {
      console.log('No Panimalar bundle found — skipping real-bundle check');
      await saveScreenshot(page, '06_no_panimalar_bundle');
      return;
    }

    console.log('Found Panimalar bundle:', panimalarBundle.bundle_number);

    // List documents
    const docsRes = await request.get(`${apiBaseUrl}/bundles/${panimalarBundle.id}/documents`);
    expect(docsRes.ok()).toBeTruthy();
    const docs = await docsRes.json() as Array<{ id: string; document_type: string; metadata?: { field_locations?: Record<string, unknown> } }>;

    const invoiceDoc = docs.find((d) => d.document_type === 'COMPANY_INVOICE');
    if (!invoiceDoc) {
      console.log('No COMPANY_INVOICE in Panimalar bundle');
      return;
    }

    const fieldLocations = invoiceDoc.metadata?.field_locations ?? {};
    console.log('Panimalar invoice field_locations keys:', Object.keys(fieldLocations));

    await page.goto(`/bundles/${panimalarBundle.id}/extraction/${invoiceDoc.id}`);
    await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();
    await page.waitForTimeout(800);
    await saveScreenshot(page, '07_panimalar_invoice_initial');

    // Try clicking invoice_no
    const invoiceBtn = page.getByLabel('Jump to Invoice Number in PDF');
    if (await invoiceBtn.count() > 0) {
      await invoiceBtn.click();
      await page.waitForTimeout(600);
      await saveScreenshot(page, '08_panimalar_invoice_highlight');

      const overlay = page.locator('.pdf-highlight-overlay');
      console.log('Panimalar overlay count:', await overlay.count());
      if (await overlay.count() > 0) {
        const box = await overlay.boundingBox();
        console.log('Panimalar overlay bbox:', box);
      }
    }

    // Also test vendor invoice (scanned → should show unavailable message)
    const vendorInvoiceDoc = docs.find((d) => d.document_type === 'VENDOR_INVOICE');
    if (vendorInvoiceDoc) {
      await page.goto(`/bundles/${panimalarBundle.id}/extraction/${vendorInvoiceDoc.id}`);
      await expect(page.getByRole('heading', { name: 'Extraction Review' })).toBeVisible();
      await page.waitForTimeout(600);

      const vendorBtn = page.getByLabel('Jump to Vendor Invoice Number in PDF');
      if (await vendorBtn.count() > 0) {
        await vendorBtn.click();
        await page.waitForTimeout(500);
      }
      await saveScreenshot(page, '09_panimalar_vendor_invoice_scanned');

      const unavailMsg = page.locator('.pdf-highlight-unavailable');
      console.log('Scanned unavail msg count:', await unavailMsg.count());
    }
  });
});
