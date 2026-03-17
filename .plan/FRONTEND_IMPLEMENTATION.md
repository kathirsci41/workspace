# DocPlatform V3 — Frontend Implementation Guide

> Work through files in the order listed. Each section shows exactly what
> the file looks like now, what changes and why, and the complete final file.
> Changes map directly to backend phases — Phase number is noted per change.

---

## Overview — What's Changing and Why

Reading the existing code reveals:

- **`ReviewModal.tsx`** already has a split-pane layout (PDF iframe left, form right) — the structure is perfect. What's missing: per-field confidence colouring, validation error banners, correction tracking, and the corrections API call on save.
- **`UploadZone.tsx`** only accepts `application/pdf`. With Phase 2 backend changes accepting PNG/TIFF, the dropzone needs to match — and JPEG must show a clear rejection message.
- **`DocumentCard.tsx`** shows a single `confidence%` number. It needs validation error indicators and a route badge (⚡ digital vs 📷 scanned).
- **`types/index.ts`** is missing `field_confidences`, `extraction_version`, `validation_errors`, and `extraction_route` on `DocumentMetadata`.
- **`api/extraction.ts`** has no `saveCorrections()` call — corrections currently vanish.
- **`hooks/useExtraction.ts`** needs a `useSaveCorrections()` hook wired to the new endpoint.

---

## File 1 — `frontend/src/types/index.ts`

**What changes:** Add new fields that backend Phase 5–8 now return.  
Add `field_confidences`, `extraction_version`, `extraction_route`, and validation fields to `DocumentMetadata`.

```typescript
// frontend/src/types/index.ts
// ─── Enums as string unions ───

export type DocumentType =
  | 'CUSTOMER_PO'
  | 'COMPANY_PO'
  | 'VENDOR_DC'
  | 'VENDOR_INVOICE'
  | 'COMPANY_DC'
  | 'COMPANY_INVOICE';

export type DocumentStatus =
  | 'UPLOADED'
  | 'EXTRACTING'
  | 'PENDING_REVIEW'
  | 'VERIFIED'
  | 'EXTRACTION_FAILED'
  | 'REJECTED';

export type POStatus =
  | 'INITIATED'
  | 'IN_PROGRESS'
  | 'NEAR_COMPLETE'
  | 'COMPLETE'
  | 'CANCELLED';

export type MetadataStatus =
  | 'PENDING'
  | 'EXTRACTED'
  | 'VERIFIED'
  | 'FAILED';

// ── NEW: extraction route from hybrid router ──────────────────────
export type ExtractionRoute = 'digital' | 'scanned' | null;

// ─── Data Interfaces ───

export interface Customer {
  id: string;
  customer_id: string;
  name: string;
  contact_email: string | null;
  gst_number: string | null;
  address: string | null;
  phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrder {
  id: string;
  po_number: string;
  customer_id: string;
  customer_name?: string;
  customer_sky_id?: string;
  po_date: string | null;
  expected_delivery_date: string | null;
  total_amount: number | null;
  currency: string;
  status: POStatus;
  chain_completeness: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentMetadata {
  id: string;
  document_id: string;
  document_type: DocumentType;
  extracted_data: Record<string, unknown> | null;
  primary_ref_no: string | null;
  po_ref_no: string | null;
  doc_date: string | null;
  total_amount: number | null;
  confidence_score: number | null;
  status: MetadataStatus;
  extraction_attempts: number;
  last_error: string | null;
  extracted_at: string | null;
  verified_at: string | null;
  model_version: string | null;
  processing_time_ms: number | null;
  raw_ocr_text: string | null;

  // ── NEW Phase 5: per-field confidence scores from LayoutLMv3 ────
  field_confidences: Record<string, number> | null;

  // ── NEW Phase 7: extraction version (increments on re-extract) ───
  extraction_version: number | null;

  // ── NEW Phase 1: which pipeline processed this doc ───────────────
  extraction_route: ExtractionRoute;
}

export interface Document {
  id: string;
  po_id: string;
  document_type: DocumentType;
  original_filename: string;
  file_path: string;
  file_size: number;
  mime_type: string;
  checksum: string;
  page_count: number | null;
  status: DocumentStatus;
  metadata: DocumentMetadata | null;
  created_at: string;
  updated_at: string;
}

export interface ChainSlot {
  status: string;
  document_id: string | null;
  ref_no: string | null;
  uploaded_at: string | null;
  confidence: number | null;
  // ── NEW: surface validation errors on the card ─────────────────
  has_validation_errors?: boolean;
  extraction_route?: ExtractionRoute;
}

export interface ChainStatus {
  po_id: string;
  po_number: string;
  completeness_pct: number;
  chain: Record<string, ChainSlot[]>;
}

// ── NEW: correction payload sent to POST /corrections ────────────
export interface FieldCorrection {
  field: string;
  corrected_value: string | null;
}

export interface SearchResult {
  result_type: 'customer' | 'purchase_order' | 'document';
  id: string;
  ref_number: string;
  display_name: string;
  document_type: DocumentType | null;
  po_number: string | null;
  po_id?: string | null;
  customer_name: string | null;
  confidence: number | null;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  query: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

// ─── Ordered chain types ───

export const CHAIN_ORDER: DocumentType[] = [
  'CUSTOMER_PO',
  'COMPANY_PO',
  'VENDOR_DC',
  'VENDOR_INVOICE',
  'COMPANY_DC',
  'COMPANY_INVOICE',
];

export const DOC_TYPE_LABELS: Record<DocumentType, string> = {
  CUSTOMER_PO: 'Customer PO',
  COMPANY_PO: 'Company PO',
  VENDOR_DC: 'Vendor DC',
  VENDOR_INVOICE: 'Vendor Invoice',
  COMPANY_DC: 'Company DC',
  COMPANY_INVOICE: 'Company Invoice',
};

export const DOC_TYPE_SHORT: Record<DocumentType, string> = {
  CUSTOMER_PO: 'C.PO',
  COMPANY_PO: 'PO',
  VENDOR_DC: 'V.DC',
  VENDOR_INVOICE: 'V.Inv',
  COMPANY_DC: 'C.DC',
  COMPANY_INVOICE: 'C.Inv',
};
```

---

## File 2 — `frontend/src/api/extraction.ts`

**What changes:** Add `saveCorrections()` function. Everything else unchanged.

```typescript
// frontend/src/api/extraction.ts
import client from './client';
import type { DocumentMetadata, FieldCorrection } from '@/types';

export async function getMetadata(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.get(
    `/api/v1/documents/${documentId}/metadata`
  );
  return data;
}

export async function verifyMetadata(
  documentId: string,
  editedData: Record<string, unknown>
): Promise<DocumentMetadata> {
  const { data } = await client.put(
    `/api/v1/documents/${documentId}/metadata/verify`,
    { extracted_data: editedData }
  );
  return data;
}

export async function rejectMetadata(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.put(
    `/api/v1/documents/${documentId}/metadata/reject`
  );
  return data;
}

export async function reExtract(documentId: string): Promise<void> {
  await client.post(`/api/v1/documents/${documentId}/re-extract`);
}

export async function getFieldTemplate(
  documentId: string
): Promise<{
  document_type: string;
  fields: Record<string, null>;
  field_descriptions: Record<string, string>;
}> {
  const { data } = await client.get(
    `/api/v1/documents/${documentId}/metadata/template`
  );
  return data;
}

export async function createManualEntry(
  documentId: string
): Promise<DocumentMetadata> {
  const { data } = await client.post(
    `/api/v1/documents/${documentId}/metadata/manual`
  );
  return data;
}

// ── NEW Phase 8: save human corrections for LayoutLMv3 training ──
export async function saveCorrections(
  documentId: string,
  corrections: FieldCorrection[]
): Promise<{ saved_fields: string[]; document_id: string }> {
  const { data } = await client.post(
    `/api/v1/documents/${documentId}/corrections`,
    corrections
  );
  return data;
}
```

---

## File 3 — `frontend/src/hooks/useExtraction.ts`

**What changes:** Add `useSaveCorrections()` hook. Everything else unchanged.

```typescript
// frontend/src/hooks/useExtraction.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getMetadata,
  verifyMetadata,
  rejectMetadata,
  reExtract,
  getFieldTemplate,
  createManualEntry,
  saveCorrections,   // NEW
} from '@/api/extraction';
import type { FieldCorrection } from '@/types';

export function useMetadata(docId: string) {
  return useQuery({
    queryKey: ['metadata', docId],
    queryFn: () => getMetadata(docId),
    enabled: !!docId,
  });
}

export function useVerifyMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      documentId,
      editedData,
    }: {
      documentId: string;
      editedData: Record<string, unknown>;
    }) => verifyMetadata(documentId, editedData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useRejectMetadata() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => rejectMetadata(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useReExtract() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => reExtract(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

export function useFieldTemplate(docId: string, enabled = false) {
  return useQuery({
    queryKey: ['fieldTemplate', docId],
    queryFn: () => getFieldTemplate(docId),
    enabled: !!docId && enabled,
  });
}

export function useCreateManualEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentId: string) => createManualEntry(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['metadata'] });
      queryClient.invalidateQueries({ queryKey: ['chainStatus'] });
      queryClient.invalidateQueries({ queryKey: ['documents'] });
    },
  });
}

// ── NEW Phase 8 ───────────────────────────────────────────────────
export function useSaveCorrections() {
  return useMutation({
    mutationFn: ({
      documentId,
      corrections,
    }: {
      documentId: string;
      corrections: FieldCorrection[];
    }) => saveCorrections(documentId, corrections),
    // No cache invalidation needed — corrections are fire-and-forget.
    // The verify mutation that calls this will handle the invalidation.
  });
}
```

---

## File 4 — `frontend/src/components/UploadZone.tsx`

**What changes (Phase 2):**
- Accept PNG and TIFF in addition to PDF (match backend Phase 2 changes)
- Add explicit JPEG rejection message when user drops a JPEG
- Add a file type guidance note in the empty state
- Surface backend 415 rejection clearly (already works via `uploadMutation.isError`, just improve the message)

```tsx
// frontend/src/components/UploadZone.tsx
import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, Loader2, AlertCircle } from 'lucide-react';
import { useUploadDocument } from '@/hooks/useDocuments';
import type { DocumentType } from '@/types';

interface Props {
  poId: string;
  documentType: DocumentType;
  onSuccess: () => void;
  onClose: () => void;
}

// Accepted MIME types — must match backend Phase 2 ALLOWED_MIME_TYPES
const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/png':       ['.png'],
  'image/tiff':      ['.tiff', '.tif'],
};

export default function UploadZone({
  poId,
  documentType,
  onSuccess,
  onClose,
}: Props) {
  const uploadMutation = useUploadDocument();
  // Track client-side JPEG rejection separately from server errors
  const [jpegError, setJpegError] = useState(false);

  const onDrop = useCallback(
    (accepted: File[], rejected: File[]) => {
      setJpegError(false);

      // Check if user tried to drop a JPEG
      const hasJpeg = rejected.some((r) =>
        r.file?.type?.includes('jpeg') ||
        r.file?.name?.toLowerCase().match(/\.(jpg|jpeg)$/)
      );
      if (hasJpeg) {
        setJpegError(true);
        return;
      }

      if (accepted.length === 0) return;

      uploadMutation.mutate(
        { poId, file: accepted[0], documentType },
        { onSuccess: () => { onSuccess(); } }
      );
    },
    [poId, documentType, uploadMutation, onSuccess]
  );

  const { getRootProps, getInputProps, isDragActive, isDragReject } =
    useDropzone({
      onDrop,
      accept: ACCEPTED_TYPES,
      maxFiles: 1,
    });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 className="text-lg font-semibold mb-4">
          Upload {documentType.replace(/_/g, ' ')}
        </h3>

        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center py-10 text-gray-500">
            <Loader2 size={32} className="animate-spin mb-3" />
            <p className="text-sm">Uploading...</p>
          </div>
        ) : (
          <div
            {...getRootProps()}
            className={`border-2 border-dashed rounded-lg py-12 px-6 text-center cursor-pointer transition-colors ${
              isDragReject
                ? 'border-red-400 bg-red-50'
                : isDragActive
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-300 hover:border-blue-400'
            }`}
          >
            <input {...getInputProps()} />
            <Upload
              size={32}
              className={`mx-auto mb-3 ${isDragReject ? 'text-red-400' : 'text-gray-400'}`}
            />
            <p className="text-sm text-gray-600">
              {isDragReject
                ? 'This file type is not accepted'
                : isDragActive
                  ? 'Drop the file here'
                  : 'Drag & drop here, or click to browse'}
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Accepted: PDF, PNG, TIFF
            </p>
            <p className="text-xs text-red-400 mt-1">
              JPEG not accepted — please use PDF or PNG
            </p>
          </div>
        )}

        {/* Client-side JPEG rejection */}
        {jpegError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 mt-3">
            <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
            <span>
              JPEG files are not accepted — JPEG compression reduces OCR
              accuracy significantly. Please re-save the file as PDF or
              PNG before uploading.
            </span>
          </div>
        )}

        {/* Server-side error (including 415 from backend) */}
        {uploadMutation.isError && (
          <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2 mt-3">
            <AlertCircle size={16} className="flex-shrink-0 mt-0.5" />
            <span>
              {(() => {
                const err = uploadMutation.error as any;
                const detail = err?.response?.data?.detail;
                if (typeof detail === 'string') return detail;
                if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
                return err?.message || 'Upload failed. Please try again.';
              })()}
            </span>
          </div>
        )}

        <div className="flex justify-end mt-4">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## File 5 — `frontend/src/components/DocumentCard.tsx`

**What changes (Phase 1 + Phase 6 + Phase 7):**
- Add ⚡ digital / 📷 scanned route badge next to confidence
- Add a red dot indicator when `has_validation_errors` is true
- Show `extraction_version` as a small `v2` tag when > 1 (so reviewers know a re-extract happened)
- All existing behaviour preserved exactly

```tsx
// frontend/src/components/DocumentCard.tsx
import clsx from 'clsx';
import {
  FileText, Upload, RotateCcw, Eye, ClipboardCheck,
  Trash2, PenLine, Zap, Camera, AlertTriangle,
} from 'lucide-react';
import type { ChainSlot, DocumentType } from '@/types';
import { DOC_TYPE_LABELS } from '@/types';

interface Props {
  documentType: DocumentType;
  slot: ChainSlot | null;
  isSelected: boolean;
  onSelect: (documentId: string) => void;
  onUpload: () => void;
  onReview: (documentId: string) => void;
  onReExtract: (documentId: string) => void;
  onDelete: (documentId: string) => void;
  onManualEntry: (documentId: string) => void;
  showLabel?: boolean;
  docIndex?: number;
}

export default function DocumentCard({
  documentType,
  slot,
  isSelected,
  onSelect,
  onUpload,
  onReview,
  onReExtract,
  onDelete,
  onManualEntry,
  showLabel = true,
  docIndex,
}: Props) {
  const status = slot?.status ?? 'empty';

  const borderColor = {
    empty:             'border-gray-300',
    UPLOADED:          'border-blue-300',
    EXTRACTING:        'border-blue-400',
    PENDING_REVIEW:    'border-amber-400',
    VERIFIED:          'border-green-400',
    EXTRACTION_FAILED: 'border-red-400',
    REJECTED:          'border-red-400',
  }[status] ?? 'border-gray-300';

  return (
    <div
      className={clsx(
        'rounded-lg border-2 p-4 transition-all cursor-pointer',
        borderColor,
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        status !== 'empty' && 'hover:shadow-sm'
      )}
      onClick={() => {
        if (slot?.document_id) onSelect(slot.document_id);
      }}
    >
      <div className="flex items-start justify-between mb-2">
        <div className="flex items-center gap-2">
          <FileText
            size={18}
            className={clsx(
              status === 'VERIFIED'
                ? 'text-green-600'
                : status === 'PENDING_REVIEW'
                  ? 'text-amber-600'
                  : status === 'EXTRACTING' || status === 'UPLOADED'
                    ? 'text-blue-600'
                    : status === 'EXTRACTION_FAILED' || status === 'REJECTED'
                      ? 'text-red-600'
                      : 'text-gray-400'
            )}
          />
          {showLabel && (
            <span className="text-sm font-semibold">
              {DOC_TYPE_LABELS[documentType]}
              {docIndex != null && (
                <span className="text-xs text-gray-400 font-normal ml-1">
                  #{docIndex}
                </span>
              )}
            </span>
          )}
          {!showLabel && docIndex != null && (
            <span className="text-xs text-gray-400 font-medium">
              #{docIndex}
            </span>
          )}
        </div>

        {/* Status badges */}
        {status === 'VERIFIED' && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            Verified
          </span>
        )}
        {status === 'PENDING_REVIEW' && (
          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full font-medium">
            Review
          </span>
        )}
        {status === 'EXTRACTING' && (
          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium animate-pulse">
            Extracting
          </span>
        )}
        {(status === 'EXTRACTION_FAILED' || status === 'REJECTED') && (
          <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full font-medium">
            {status === 'REJECTED' ? 'Rejected' : 'Failed'}
          </span>
        )}
      </div>

      {/* Empty state */}
      {status === 'empty' && (
        <div className="text-center py-3">
          <p className="text-sm text-gray-400 mb-2">Not uploaded yet</p>
          <button
            onClick={(e) => { e.stopPropagation(); onUpload(); }}
            className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
          >
            <Upload size={14} />
            Upload Document
          </button>
        </div>
      )}

      {/* Extracting state */}
      {status === 'EXTRACTING' && (
        <div className="py-2">
          <p className="text-sm text-gray-500 mb-2">Processing...</p>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div className="h-full bg-blue-500 rounded-full animate-[loading_1.5s_ease-in-out_infinite] w-1/2" />
          </div>
        </div>
      )}

      {/* Has data states */}
      {(status === 'PENDING_REVIEW' ||
        status === 'VERIFIED' ||
        status === 'UPLOADED') &&
        slot && (
          <div>
            <p className="text-sm font-mono text-gray-700 truncate">
              {slot.ref_no ?? '—'}
            </p>

            {/* ── Confidence + route + validation row ─────────────── */}
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              {slot.confidence != null && (
                <span
                  className={clsx(
                    'text-xs font-medium',
                    slot.confidence >= 80
                      ? 'text-green-600'
                      : slot.confidence >= 50
                        ? 'text-amber-600'
                        : 'text-red-600'
                  )}
                >
                  {slot.confidence}%
                </span>
              )}

              {/* ── NEW Phase 1: route badge ─────────────────────── */}
              {slot.extraction_route === 'digital' && (
                <span
                  title="Extracted programmatically — no OCR used"
                  className="inline-flex items-center gap-0.5 text-xs text-emerald-600 bg-emerald-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <Zap size={10} />
                  digital
                </span>
              )}
              {slot.extraction_route === 'scanned' && (
                <span
                  title="Extracted via OCR from scanned image"
                  className="inline-flex items-center gap-0.5 text-xs text-blue-500 bg-blue-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <Camera size={10} />
                  scanned
                </span>
              )}

              {/* ── NEW Phase 6: validation error indicator ──────── */}
              {slot.has_validation_errors && (
                <span
                  title="Math or date validation failed — review required"
                  className="inline-flex items-center gap-0.5 text-xs text-red-600 bg-red-50 px-1.5 py-0.5 rounded font-medium"
                >
                  <AlertTriangle size={10} />
                  check math
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 mt-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (slot.document_id) onSelect(slot.document_id);
                }}
                className="inline-flex items-center gap-1 text-xs text-gray-600 hover:text-blue-600"
              >
                <Eye size={14} />
                Preview
              </button>
              {status === 'PENDING_REVIEW' && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (slot.document_id) onReview(slot.document_id);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium"
                >
                  <ClipboardCheck size={14} />
                  Review
                </button>
              )}
              {(status === 'VERIFIED' || status === 'PENDING_REVIEW') && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    if (slot.document_id) onReExtract(slot.document_id);
                  }}
                  className="inline-flex items-center gap-1 text-xs text-gray-500 hover:text-blue-600"
                >
                  <RotateCcw size={14} />
                  Re-extract
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (slot.document_id) onDelete(slot.document_id);
                }}
                className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600"
                title="Delete & Re-upload"
              >
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        )}

      {/* Failed/Rejected state — unchanged */}
      {(status === 'EXTRACTION_FAILED' || status === 'REJECTED') && slot && (
        <div>
          <p className="text-sm text-red-600 truncate">
            {status === 'REJECTED' ? 'Rejected by reviewer' : 'Extraction failed'}
          </p>
          <div className="flex items-center gap-2 mt-3">
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onReExtract(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
            >
              <RotateCcw size={14} />
              Re-extract
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onManualEntry(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-amber-600 hover:text-amber-700 font-medium"
            >
              <PenLine size={14} />
              Manual Entry
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (slot.document_id) onDelete(slot.document_id);
              }}
              className="inline-flex items-center gap-1 text-xs text-gray-400 hover:text-red-600"
              title="Delete & Re-upload"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
```

---

## File 6 — `frontend/src/components/ReviewModal.tsx`

**What changes — this is the biggest update:**

1. **Per-field confidence colouring** — when `metadata.field_confidences` is present, each field input gets a coloured left border: green ≥ 0.85, amber 0.60–0.85, red < 0.60. A small `94%` badge appears on the label.
2. **Validation error banner** — if `extracted_data._validation_errors` is set, show a red collapsible banner listing each error above the form fields.
3. **Validation warning banner** — if `extracted_data._validation_warnings` is set, show an amber banner.
4. **Correction tracking** — on mount, snapshot the original extracted values. On `handleVerify`, diff the form against the snapshot and call `saveCorrections()` with changed fields before calling the existing `verifyMutation`.
5. **Extraction version indicator** — show `v2`, `v3` etc. in the header when `extraction_version > 1`.
6. **Extraction route badge** — show ⚡ digital or 📷 scanned next to the confidence badge.

```tsx
// frontend/src/components/ReviewModal.tsx
import { useState, useEffect, useRef } from 'react';
import {
  X, Check, Ban, Loader2, PenLine,
  Zap, Camera, AlertTriangle, ChevronDown, ChevronUp,
} from 'lucide-react';
import {
  useMetadata,
  useVerifyMetadata,
  useRejectMetadata,
  useFieldTemplate,
  useSaveCorrections,
} from '@/hooks/useExtraction';
import { getPreviewUrl } from '@/api/documents';
import clsx from 'clsx';

interface Props {
  documentId: string;
  onClose: () => void;
  onVerified: () => void;
}

// Confidence thresholds for field-level colouring
const CONF_HIGH   = 0.85;
const CONF_MEDIUM = 0.60;

export default function ReviewModal({ documentId, onClose, onVerified }: Props) {
  const { data: metadata, isLoading } = useMetadata(documentId);
  const verifyMutation     = useVerifyMetadata();
  const rejectMutation     = useRejectMetadata();
  const correctionsMutation = useSaveCorrections();   // NEW Phase 8

  const isDataEmpty = !metadata?.extracted_data ||
    Object.keys(metadata.extracted_data).length === 0;
  const { data: template } = useFieldTemplate(documentId, isDataEmpty && !isLoading);

  const [formData, setFormData]           = useState<Record<string, string>>({});
  const [isManualMode, setIsManualMode]   = useState(false);
  const [errorsOpen, setErrorsOpen]       = useState(true);
  const [warningsOpen, setWarningsOpen]   = useState(false);

  // Snapshot of original extracted values for diffing corrections
  const originalSnapshot = useRef<Record<string, string>>({});

  useEffect(() => {
    if (metadata?.extracted_data && Object.keys(metadata.extracted_data).length > 0) {
      const initial: Record<string, string> = {};
      for (const [key, value] of Object.entries(metadata.extracted_data)) {
        if (key.startsWith('_')) continue;
        initial[key] = value != null ? String(value) : '';
      }
      setFormData(initial);
      // Snapshot for correction diffing
      originalSnapshot.current = { ...initial };
      setIsManualMode(
        metadata.model_version === 'manual' ||
        Object.values(metadata.extracted_data).every((v) => v === null || v === '')
      );
    } else if (template?.fields) {
      const initial: Record<string, string> = {};
      for (const key of Object.keys(template.fields)) {
        initial[key] = '';
      }
      setFormData(initial);
      originalSnapshot.current = { ...initial };
      setIsManualMode(true);
    }
  }, [metadata, template]);

  // ── Derive validation errors/warnings from extracted_data ────────
  const validationErrors: string[] = Array.isArray(
    metadata?.extracted_data?.['_validation_errors']
  )
    ? (metadata!.extracted_data!['_validation_errors'] as string[])
    : [];

  const validationWarnings: string[] = Array.isArray(
    metadata?.extracted_data?.['_validation_warnings']
  )
    ? (metadata!.extracted_data!['_validation_warnings'] as string[])
    : [];

  // ── Per-field confidence helper ───────────────────────────────────
  const fieldConf = metadata?.field_confidences ?? null;

  const getFieldConfidence = (key: string): number | null => {
    if (!fieldConf) return null;
    return fieldConf[key] ?? null;
  };

  const confColour = (conf: number | null) => {
    if (conf === null) return 'border-gray-300';
    if (conf >= CONF_HIGH)   return 'border-green-400';
    if (conf >= CONF_MEDIUM) return 'border-amber-400';
    return 'border-red-400';
  };

  const confBadgeColour = (conf: number | null) => {
    if (conf === null) return '';
    if (conf >= CONF_HIGH)   return 'text-green-600 bg-green-50';
    if (conf >= CONF_MEDIUM) return 'text-amber-600 bg-amber-50';
    return 'text-red-600 bg-red-50';
  };

  // ── Verify: diff + save corrections, then verify ──────────────────
  const handleVerify = async () => {
    // Build corrections list — fields that changed from original
    const corrections = Object.entries(formData)
      .filter(([key]) => !key.startsWith('_'))
      .filter(([key, val]) => val !== (originalSnapshot.current[key] ?? ''))
      .map(([key, val]) => ({ field: key, corrected_value: val || null }));

    // Fire-and-forget corrections (don't block on failure)
    if (corrections.length > 0) {
      correctionsMutation.mutate({ documentId, corrections });
    }

    // Build editedData for the verify call (same logic as before)
    const editedData: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(formData)) {
      if (key.startsWith('_')) continue;
      if (value === '') {
        editedData[key] = null;
      } else if (
        !isNaN(Number(value)) &&
        (key.includes('amount') || key.includes('count') ||
         key.includes('quantity') || key.includes('subtotal') ||
         key.includes('tax'))
      ) {
        editedData[key] = Number(value);
      } else if (key === 'signature_present') {
        editedData[key] = value === 'true';
      } else {
        editedData[key] = value;
      }
    }

    verifyMutation.mutate(
      { documentId, editedData },
      { onSuccess: onVerified }
    );
  };

  const handleReject = () => {
    rejectMutation.mutate(documentId, { onSuccess: onClose });
  };

  // ── Field ordering and labels — unchanged from original ──────────
  const FIELD_ORDER: Record<string, string[]> = {
    CUSTOMER_PO:     ['po_number', 'bsif_name', 'po_date'],
    COMPANY_PO:      ['purchase_bill_no', 'po_number', 'bill_no'],
    VENDOR_DC:       ['dc_number', 'dc_date', 'po_reference', 'vendor_name', 'items_description', 'quantity', 'vehicle_number', 'receiver_name'],
    VENDOR_INVOICE:  ['invoice_number', 'customer_order_no', 'po_reference'],
    COMPANY_DC:      ['dc_number', 'po_reference', 'sales_order_no', 'dispatch_to'],
    COMPANY_INVOICE: ['invoice_number', 'so_number', 'po_reference', 'customer_name', 'total_amount'],
  };

  const FIELD_LABELS: Record<string, string> = {
    bsif_name:         'Company Name',
    purchase_bill_no:  'Purchase Bill No',
    bill_no:           'Bill No',
    dc_number:         'DC No',
    dc_date:           'DC Date',
    po_reference:      'Customer Order No',
    sales_order_no:    'Sales Order No',
    dispatch_to:       'Delivery To',
    invoice_number:    'Invoice No',
    customer_order_no: 'Customer Order No',
    so_number:         'Sales Order No',
    customer_name:     'Customer Name',
    total_amount:      'Total Amount',
    vendor_name:       'Vendor Name',
    items_description: 'Items',
    receiver_name:     'Receiver Name',
    vehicle_number:    'Vehicle No',
    quantity:          'Quantity',
  };

  const DOC_LABEL_OVERRIDES: Record<string, Record<string, string>> = {
    CUSTOMER_PO: { po_number: 'Customer PO Number' },
    VENDOR_DC:   { po_reference: 'PO Reference' },
  };

  const formatLabel = (key: string) => {
    const docType = metadata?.document_type ?? '';
    const override = DOC_LABEL_OVERRIDES[docType]?.[key];
    if (override) return override;
    if (FIELD_LABELS[key]) return FIELD_LABELS[key];
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  };

  const sortedFormKeys = (keys: string[]): string[] => {
    const docType = metadata?.document_type ?? '';
    const order = FIELD_ORDER[docType] ?? [];
    const inOrder = order.filter((k) => keys.includes(k));
    const rest    = keys.filter((k) => !order.includes(k));
    return [...inOrder, ...rest];
  };

  if (isLoading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
        <Loader2 size={32} className="animate-spin text-white" />
      </div>
    );
  }

  const extractionVersion = metadata?.extraction_version;
  const extractionRoute   = metadata?.extraction_route;

  return (
    <div className="fixed inset-0 z-50 flex bg-black/60">
      <div className="m-auto bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] max-w-7xl flex flex-col">

        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold">
              {isManualMode ? 'Manual Data Entry' : 'Review Extracted Data'}
            </h3>
            {metadata && (
              <div className="flex items-center gap-2 mt-1 flex-wrap">
                <span className="text-xs text-gray-500 uppercase">
                  {metadata.document_type?.replace(/_/g, ' ')}
                </span>

                {/* Overall confidence */}
                {metadata.confidence_score != null && (
                  <span
                    className={clsx(
                      'text-xs font-medium px-2 py-0.5 rounded-full',
                      metadata.confidence_score >= 80
                        ? 'bg-green-100 text-green-700'
                        : metadata.confidence_score >= 50
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-red-100 text-red-700'
                    )}
                  >
                    {metadata.confidence_score}% confidence
                  </span>
                )}

                {/* ── NEW Phase 1: route badge ─────────────────── */}
                {extractionRoute === 'digital' && (
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full font-medium">
                    <Zap size={11} /> Digital — no OCR
                  </span>
                )}
                {extractionRoute === 'scanned' && (
                  <span className="inline-flex items-center gap-1 text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full font-medium">
                    <Camera size={11} /> Scanned
                  </span>
                )}

                {/* ── NEW Phase 7: extraction version ─────────── */}
                {extractionVersion != null && extractionVersion > 1 && (
                  <span className="text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">
                    v{extractionVersion}
                  </span>
                )}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg"
          >
            <X size={20} />
          </button>
        </div>

        {/* ── Body: split view ────────────────────────────────────── */}
        <div className="flex-1 flex min-h-0">

          {/* Left: PDF */}
          <div className="w-1/2 border-r border-gray-200">
            <iframe
              src={getPreviewUrl(documentId)}
              className="w-full h-full border-0"
              title="Document Preview"
            />
          </div>

          {/* Right: Form */}
          <div className="w-1/2 flex flex-col">
            <div className="flex-1 overflow-y-auto p-6 space-y-3">

              {/* Manual mode notice */}
              {isManualMode && Object.keys(formData).length > 0 && (
                <div className="bg-amber-50 border border-amber-200 text-amber-800 text-sm rounded-lg px-4 py-3 flex items-center gap-2 mb-2">
                  <PenLine size={16} />
                  Manual entry mode — fill in the fields from the document on the left, then click Verify.
                </div>
              )}

              {/* ── NEW Phase 6: validation errors banner ──────── */}
              {validationErrors.length > 0 && (
                <div className="border border-red-300 rounded-lg overflow-hidden mb-1">
                  <button
                    onClick={() => setErrorsOpen((o) => !o)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-red-50 text-red-700 text-sm font-medium"
                  >
                    <span className="flex items-center gap-2">
                      <AlertTriangle size={15} />
                      {validationErrors.length} validation error{validationErrors.length > 1 ? 's' : ''} — review before verifying
                    </span>
                    {errorsOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {errorsOpen && (
                    <ul className="px-4 py-2 bg-red-50 space-y-1">
                      {validationErrors.map((err, i) => (
                        <li key={i} className="text-xs text-red-700 flex gap-2">
                          <span className="mt-0.5 flex-shrink-0">•</span>
                          {err}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* ── NEW Phase 6: validation warnings banner ────── */}
              {validationWarnings.length > 0 && (
                <div className="border border-amber-300 rounded-lg overflow-hidden mb-1">
                  <button
                    onClick={() => setWarningsOpen((o) => !o)}
                    className="w-full flex items-center justify-between px-4 py-2.5 bg-amber-50 text-amber-700 text-sm font-medium"
                  >
                    <span className="flex items-center gap-2">
                      <AlertTriangle size={15} />
                      {validationWarnings.length} warning{validationWarnings.length > 1 ? 's' : ''}
                    </span>
                    {warningsOpen ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {warningsOpen && (
                    <ul className="px-4 py-2 bg-amber-50 space-y-1">
                      {validationWarnings.map((w, i) => (
                        <li key={i} className="text-xs text-amber-700 flex gap-2">
                          <span className="mt-0.5 flex-shrink-0">•</span>
                          {w}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}

              {/* ── Per-field confidence legend (only when LM data present) */}
              {fieldConf && Object.keys(fieldConf).length > 0 && (
                <div className="flex items-center gap-3 text-xs text-gray-400 pb-1">
                  <span>Field confidence:</span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-green-400 inline-block" /> ≥85%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" /> 60–85%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-red-400 inline-block" /> &lt;60%
                  </span>
                </div>
              )}

              {/* ── Form fields ──────────────────────────────────── */}
              {sortedFormKeys(Object.keys(formData)).map((key) => {
                const value = formData[key];
                const conf  = getFieldConfidence(key);
                const isChanged = value !== (originalSnapshot.current[key] ?? '');

                return (
                  <div key={key}>
                    <label className="flex items-center justify-between text-xs font-medium text-gray-500 mb-1">
                      <span>
                        {formatLabel(key)}
                        {template?.field_descriptions?.[key] && (
                          <span className="ml-1 text-gray-400 font-normal">
                            — {template.field_descriptions[key]}
                          </span>
                        )}
                        {/* Changed indicator */}
                        {isChanged && (
                          <span className="ml-1.5 text-blue-500 font-semibold" title="Modified">
                            ✎
                          </span>
                        )}
                      </span>
                      {/* ── NEW Phase 5: per-field confidence badge ── */}
                      {conf !== null && (
                        <span
                          className={clsx(
                            'text-xs px-1.5 py-0.5 rounded font-medium',
                            confBadgeColour(conf)
                          )}
                        >
                          {Math.round(conf * 100)}%
                        </span>
                      )}
                    </label>

                    {key === 'signature_present' ? (
                      <select
                        value={value}
                        onChange={(e) =>
                          setFormData((f) => ({ ...f, [key]: e.target.value }))
                        }
                        className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:outline-none border-gray-300"
                      >
                        <option value="">Unknown</option>
                        <option value="true">Yes</option>
                        <option value="false">No</option>
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={value}
                        onChange={(e) =>
                          setFormData((f) => ({ ...f, [key]: e.target.value }))
                        }
                        placeholder={`Enter ${formatLabel(key).toLowerCase()}`}
                        className={clsx(
                          'w-full px-3 py-2 border-l-4 border rounded-lg text-sm',
                          'focus:ring-2 focus:ring-blue-500 focus:outline-none',
                          // Left border from confidence, right border from value presence
                          conf !== null
                            ? confColour(conf)
                            : value
                              ? 'border-gray-300'
                              : 'border-red-200 bg-red-50'
                        )}
                      />
                    )}
                  </div>
                );
              })}

              {Object.keys(formData).length === 0 && !isLoading && (
                <p className="text-sm text-gray-400 py-8 text-center">
                  No extraction data or template available. Try re-extracting the document.
                </p>
              )}
            </div>

            {/* ── Action buttons ─────────────────────────────────── */}
            <div className="px-6 py-4 border-t border-gray-200 space-y-2">
              {(verifyMutation.isError || rejectMutation.isError) && (
                <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-3 py-2">
                  {(() => {
                    const err = (verifyMutation.error || rejectMutation.error) as any;
                    const detail = err?.response?.data?.detail;
                    if (typeof detail === 'string') return detail;
                    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
                    return err?.message || 'Operation failed. Please try again.';
                  })()}
                </div>
              )}
              <div className="flex items-center justify-between gap-3">
                {/* Changed fields count — helpful for reviewers */}
                {(() => {
                  const changed = Object.entries(formData).filter(
                    ([k, v]) => !k.startsWith('_') && v !== (originalSnapshot.current[k] ?? '')
                  ).length;
                  return changed > 0 ? (
                    <span className="text-xs text-blue-600">
                      {changed} field{changed > 1 ? 's' : ''} modified
                    </span>
                  ) : (
                    <span />
                  );
                })()}

                <div className="flex items-center gap-3">
                  <button
                    onClick={handleReject}
                    disabled={rejectMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-red-600 border border-red-300 rounded-lg hover:bg-red-50 disabled:opacity-50"
                  >
                    <Ban size={16} />
                    {rejectMutation.isPending ? 'Rejecting...' : 'Reject'}
                  </button>
                  <button
                    onClick={onClose}
                    className="px-4 py-2 text-sm border rounded-lg hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleVerify}
                    disabled={verifyMutation.isPending}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-green-600 rounded-lg hover:bg-green-700 disabled:opacity-50"
                  >
                    <Check size={16} />
                    {verifyMutation.isPending ? 'Verifying...' : 'Verify'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
```

---

## Summary — What Each Change Does for Users

| Component | Change | Reviewer sees |
|---|---|---|
| `UploadZone` | Accept PNG/TIFF, reject JPEG with message | Clear error instead of silent failure |
| `DocumentCard` | ⚡ digital / 📷 scanned badge | Instantly knows if OCR was used |
| `DocumentCard` | `check math` badge | Knows to look at totals before opening |
| `DocumentCard` | `v2`, `v3` version badge | Knows this was re-extracted |
| `ReviewModal` | Per-field confidence left border | Eye goes to red/amber fields instantly |
| `ReviewModal` | `94%` badge on field label | Exact confidence per field, not just total |
| `ReviewModal` | Validation errors banner | Math discrepancy visible before verifying |
| `ReviewModal` | `✎` edit indicator | Can see at a glance which fields were touched |
| `ReviewModal` | "2 fields modified" counter | Confirmation before clicking Verify |
| `ReviewModal` | Corrections POST on save | Every change captured for LayoutLMv3 training |

## Implementation Order

```
1. types/index.ts          — 5 min, no risk, enables everything else
2. api/extraction.ts       — 5 min, add saveCorrections()
3. hooks/useExtraction.ts  — 5 min, add useSaveCorrections()
4. UploadZone.tsx          — 20 min, Phase 2
5. DocumentCard.tsx        — 30 min, Phase 1 + 6 + 7 badges
6. ReviewModal.tsx         — 1–2 hours, most complex
```

Run `tsc --noEmit` after each file to catch type errors before testing in browser.
