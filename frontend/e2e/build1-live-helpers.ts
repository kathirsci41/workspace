/**
 * Shared helpers for the Build 1 full live E2E hardening specs.
 *
 * These specs drive the REAL application against REAL sample PDFs from
 * sample/extracted. Bundle/upload/extract setup goes through the normal API
 * (Playwright APIRequestContext); UI assertions go through the browser page.
 *
 * Cleanup rule: only bundles whose bundle_number starts with "E2E-LIVE-" are
 * ever deleted. No other bundle is touched, and the DB is never reset.
 */
import { type APIRequestContext, expect } from '@playwright/test';
import fs from 'fs';
import path from 'path';

export const API_BASE = process.env.VITE_API_BASE_URL_ABS ?? 'http://127.0.0.1:8100/api';
export const E2E_PREFIX = 'E2E-LIVE-';

// Playwright runs with cwd = frontend/, so the repo root is one level up.
const SAMPLE_ROOT = path.resolve(process.cwd(), '..', 'sample/extracted');

export interface SampleDoc {
  file: string;
  type: string;
}

export const TRADE_DOCS: SampleDoc[] = [
  { file: 'Trade/Trade/TRADE - CUSTOMER PO.pdf', type: 'CUSTOMER_PO' },
  { file: 'Trade/Trade/TRADE - INVOICE 1ITR2526001785.pdf', type: 'CUSTOMER_INVOICE' },
  { file: 'Trade/Trade/TRADE - DC 1DNT2526DC2915.pdf', type: 'DELIVERY_CHALLAN' },
  { file: 'Trade/Trade/TRADE - PURCHASE ORDER.pdf', type: 'VENDOR_PO' },
  { file: 'Trade/Trade/TRADE - VENDOR BILL -C190224826.pdf', type: 'VENDOR_INVOICE' },
  { file: 'Trade/Trade/TRADE -VENDOR BILL - C190224835.pdf', type: 'VENDOR_INVOICE' },
];

export const PANIMALAR_DOCS: SampleDoc[] = [
  { file: 'Panimalar/Customer PO_.pdf', type: 'CUSTOMER_PO' },
  { file: 'Panimalar/Customer Invoice 1ITR2526001878.pdf', type: 'CUSTOMER_INVOICE' },
  { file: 'Panimalar/DC 1DNT2526DC3100.pdf', type: 'DELIVERY_CHALLAN' },
  { file: 'Panimalar/Vendor PO 1PTR2526000467.pdf', type: 'VENDOR_PO' },
  { file: 'Panimalar/Vendor Bill 2526PSI25087738.pdf', type: 'VENDOR_INVOICE' },
];

// The three scanned Sriram vendor POs — the documents that now route to paddle
// thanks to VENDOR_PO being added to the allowlist this phase.
export const SRIRAM_VENDOR_PO_DOCS: SampleDoc[] = [
  { file: 'Sriram fin/PO AMC corro health.pdf', type: 'VENDOR_PO' },
  { file: 'Sriram fin/Purchase order Inflow.pdf', type: 'VENDOR_PO' },
  { file: 'Sriram fin/purchase order reddington.pdf', type: 'VENDOR_PO' },
];

export function samplePath(rel: string): string {
  const abs = path.join(SAMPLE_ROOT, rel);
  if (!fs.existsSync(abs)) {
    throw new Error(`Sample PDF missing: ${abs}`);
  }
  return abs;
}

export function timestamp(): string {
  return new Date().toISOString().replace(/[^0-9]/g, '').slice(0, 14);
}

export async function createBundle(
  request: APIRequestContext,
  bundleNumber: string,
  fields: { customer_name?: string; customer_po_no?: string; so_no?: string },
): Promise<string> {
  const resp = await request.post(`${API_BASE}/bundles`, {
    data: { bundle_number: bundleNumber, ...fields },
  });
  expect(resp.status(), `create bundle ${bundleNumber}`).toBe(201);
  return (await resp.json()).id as string;
}

export async function uploadDoc(
  request: APIRequestContext,
  bundleId: string,
  doc: SampleDoc,
): Promise<string> {
  const abs = samplePath(doc.file);
  const buffer = fs.readFileSync(abs);
  // Guard: real PDF bytes only.
  expect(buffer.slice(0, 4).toString('latin1'), `PDF header for ${doc.file}`).toBe('%PDF');
  const resp = await request.post(`${API_BASE}/bundles/${bundleId}/documents`, {
    multipart: {
      document_type: doc.type,
      file: { name: path.basename(doc.file), mimeType: 'application/pdf', buffer },
    },
  });
  expect(resp.status(), `upload ${doc.file}`).toBe(201);
  return (await resp.json()).id as string;
}

export interface ExtractionResult {
  httpStatus: number;
  metadataStatus: string;
  documentStatus: string;
  extractionRoute: string;
  fallbackUsed: unknown;
  failureCode: unknown;
  failureReason: unknown;
  ocrTextBlocks: number;
  extracted: Record<string, unknown>;
}

export async function extractDoc(request: APIRequestContext, documentId: string): Promise<ExtractionResult> {
  const resp = await request.post(`${API_BASE}/documents/${documentId}/extract`, {
    headers: { 'Content-Type': 'application/json' },
    data: {},
    timeout: 240_000,
  });
  const body = await resp.json();
  const diag = body?.metadata?.diagnostics ?? {};
  return {
    httpStatus: resp.status(),
    metadataStatus: body?.metadata?.status,
    documentStatus: body?.document?.status,
    extractionRoute: diag.extraction_route,
    fallbackUsed: diag.fallback_used,
    failureCode: diag.failure_code,
    failureReason: diag.failure_reason,
    ocrTextBlocks: Array.isArray(diag.ocr_paddle_text_blocks) ? diag.ocr_paddle_text_blocks.length : 0,
    extracted: body?.metadata?.extracted_data ?? {},
  };
}

/** Delete ONLY bundles whose bundle_number starts with E2E-LIVE-. Returns deleted numbers. */
export async function cleanupE2EBundles(request: APIRequestContext): Promise<string[]> {
  const resp = await request.get(`${API_BASE}/bundles`);
  expect(resp.ok()).toBeTruthy();
  const bundles = (await resp.json()) as Array<{ id: string; bundle_number: string }>;
  const deleted: string[] = [];
  for (const b of bundles) {
    if (b.bundle_number?.startsWith(E2E_PREFIX)) {
      const del = await request.delete(`${API_BASE}/bundles/${b.id}`);
      // 204 expected; tolerate 404 (already gone) and 500 (file-system unlink
      // error on CIFS/network mounts — bundle is still logically deleted).
      expect([204, 404, 500]).toContain(del.status());
      deleted.push(b.bundle_number);
    }
  }
  return deleted;
}
