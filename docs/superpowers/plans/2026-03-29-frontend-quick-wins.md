# Frontend Quick Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire up 5 missing UI elements that already have complete backend + API support — export button (2 pages), PENDING_MODEL pipeline counter, models health card, and requeue button in Admin.

**Architecture:** Pure frontend changes. Zero backend modifications needed. All API functions exist in `frontend/src/api/purchaseOrders.ts` and `frontend/src/api/client.ts`. Changes are isolated to 3 files: `POProfilePage.tsx`, `PODetailPage.tsx`, `AdminPage.tsx`.

**Tech Stack:** React 18, TypeScript, TanStack React Query, Axios, Lucide React, Tailwind CSS

---

## Pre-flight: What's Already Done (Don't Rebuild)

Before starting, note that these were originally listed as "missing" but are already fully implemented:
- ✅ SO entry modal in ReviewModal (lines 329–375)
- ✅ PENDING_MODEL card in DocumentCard (lines 160–195)
- ✅ Validation errors in ReviewModal (lines 457–506)
- ✅ POST /corrections wired in ReviewModal handleVerify + handleSave

---

## Files Modified

| File | Change |
|------|--------|
| `frontend/src/pages/POProfilePage.tsx` | Add Export button to header |
| `frontend/src/pages/PODetailPage.tsx` | Add Export button to header actions row |
| `frontend/src/pages/AdminPage.tsx` | Fix Stats type, add PENDING_MODEL counter, fix HealthResult type, add models ServiceCard, add Requeue button |

---

## Task 1: Export Button on POProfilePage

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`

**Context:** `exportPOAsExcel(poId, poNumber, mode)` already exists in `purchaseOrders.ts` and handles the full download flow (fetch blob → create anchor → auto-click → revoke URL). The Profile page header has the PO number and ID available via `profile.po_number` and `id`. The export has two modes: `'separate'` (7 sheets, default) and `'single'` (consolidated). We'll add a button that defaults to `'separate'` with a dropdown arrow for `'single'`.

- [ ] **Step 1: Add imports**

In `frontend/src/pages/POProfilePage.tsx`, change the import line:
```typescript
import { ArrowLeft, Loader2 } from 'lucide-react';
```
to:
```typescript
import { ArrowLeft, Loader2, Download } from 'lucide-react';
import { useState } from 'react';
import { exportPOAsExcel } from '@/api/purchaseOrders';
```

- [ ] **Step 2: Add export state inside the component**

Add after `const { id } = useParams<{ id: string }>();`:
```typescript
const [exporting, setExporting] = useState(false);

const handleExport = async (mode: 'separate' | 'single' = 'separate') => {
  if (!profile) return;
  setExporting(true);
  try {
    await exportPOAsExcel(id!, profile.po_number, mode);
  } finally {
    setExporting(false);
  }
};
```

- [ ] **Step 3: Add Export button to the header**

In the header `<div className="flex items-center gap-3 flex-wrap">` block (which currently contains Back link, PO number, status badge, completeness %), add the export button after the completeness span:

```tsx
<button
  onClick={() => handleExport('separate')}
  disabled={exporting}
  title="Export to Excel (7 sheets)"
  className="inline-flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50 ml-auto"
>
  <Download size={14} className={exporting ? 'animate-bounce' : ''} />
  {exporting ? 'Exporting…' : 'Export Excel'}
</button>
```

- [ ] **Step 4: Manual smoke test**

1. Start the dev server: `cd frontend && npm run dev`
2. Navigate to any PO Profile page (`/purchase-orders/{id}/profile`)
3. Click "Export Excel"
4. Verify a `.xlsx` file named `PO_{po_number}_separate_{date}.xlsx` downloads
5. Open the file — confirm it has 7 sheets (Summary, Document Chain, etc.)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx
git commit -m "feat: add Excel export button to PO Profile page"
```

---

## Task 2: Export Button on PODetailPage

**Files:**
- Modify: `frontend/src/pages/PODetailPage.tsx`

**Context:** The detail page header already has a "View Profile" button and "Delete PO" button. The export button fits naturally in that action row. The page has `po.po_number` available. `id` comes from `useParams`.

- [ ] **Step 1: Add imports**

In `frontend/src/pages/PODetailPage.tsx`, add `Download` to the existing lucide import:
```typescript
import { ArrowLeft, Loader2, Trash2, PenLine, Check, X, AlertTriangle, BarChart2, Download } from 'lucide-react';
```

Add `exportPOAsExcel` import:
```typescript
import { exportPOAsExcel } from '@/api/purchaseOrders';
```

- [ ] **Step 2: Add export state**

After the line `const [deletePOConfirm, setDeletePOConfirm] = useState(false);`, add:
```typescript
const [exporting, setExporting] = useState(false);

const handleExport = async () => {
  setExporting(true);
  try {
    await exportPOAsExcel(id!, po!.po_number, 'separate');
  } finally {
    setExporting(false);
  }
};
```

- [ ] **Step 3: Add Export button in the header action row**

In the `<div className="flex items-center gap-3 flex-wrap">` block in the JSX (where "View Profile" and "Delete PO" buttons are), add the export button between "View Profile" and "Delete PO":

```tsx
<button
  onClick={handleExport}
  disabled={exporting}
  title="Export PO data to Excel"
  className="flex items-center gap-1.5 text-sm text-gray-600 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 disabled:opacity-50"
>
  <Download size={14} className={exporting ? 'animate-bounce' : ''} />
  {exporting ? 'Exporting…' : 'Export'}
</button>
```

- [ ] **Step 4: Manual smoke test**

1. Navigate to any PO Detail page (`/purchase-orders/{id}`)
2. Click "Export"
3. Verify `.xlsx` file downloads correctly

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PODetailPage.tsx
git commit -m "feat: add Excel export button to PO Detail page"
```

---

## Task 3: AdminPage — Fix Stats Type + Add PENDING_MODEL Counter

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`

**Context:** The backend `GET /api/v1/admin/stats` already returns `pending_model` count (admin.py line 148). The frontend `Stats` interface (AdminPage.tsx line 29) doesn't include it, so it's silently ignored. The pipeline counters section also has no counter for PENDING_MODEL, meaning operators can't see or click-through to queued documents.

- [ ] **Step 1: Fix the Stats interface**

Change the Stats interface in AdminPage.tsx:
```typescript
interface Stats {
  total_customers: number;
  total_purchase_orders: number;
  total_documents: number;
  uploaded: number;
  extracting: number;
  pending_reviews: number;
  verified: number;
  extraction_failures: number;
  rejected: number;
}
```
to:
```typescript
interface Stats {
  total_customers: number;
  total_purchase_orders: number;
  total_documents: number;
  uploaded: number;
  extracting: number;
  pending_reviews: number;
  verified: number;
  extraction_failures: number;
  pending_model: number;
  rejected: number;
}
```

- [ ] **Step 2: Add PENDING_MODEL pipeline counter**

In the pipeline counters JSX, after the `<PipelineCounter label="Rejected" ...>` element, add a divider and the pending model counter. Find the section ending with:
```tsx
<PipelineCounter label="Rejected" count={stats.rejected} status="REJECTED" color="border-orange-200 bg-orange-50 text-orange-700 hover:border-orange-400" />
```
Change it to:
```tsx
<PipelineCounter label="Rejected"       count={stats.rejected}      status="REJECTED"       color="border-orange-200 bg-orange-50 text-orange-700 hover:border-orange-400" />
{stats.pending_model > 0 && (
  <>
    <div className="w-px h-10 bg-orange-200 mx-1" />
    <PipelineCounter label="Awaiting Model" count={stats.pending_model} status="PENDING_MODEL" color="border-orange-300 bg-orange-50 text-orange-700 hover:border-orange-400" />
  </>
)}
```

- [ ] **Step 3: Manual smoke test**

1. In the app, set a document to PENDING_MODEL status (or check if any exist via `GET /api/v1/admin/stats`)
2. Open Admin page — confirm "Awaiting Model" counter appears when count > 0
3. Click the counter — confirm it navigates to `/documents?status=PENDING_MODEL`

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/AdminPage.tsx
git commit -m "fix: add pending_model to Stats type and pipeline counter in AdminPage"
```

---

## Task 4: AdminPage — Fix Models Health Card + Add Requeue Button

**Files:**
- Modify: `frontend/src/pages/AdminPage.tsx`

**Context 1 — Models health card:** The backend `GET /api/v1/admin/health` returns 5 keys: `database`, `redis`, `ollama`, `models`, `storage`. The frontend `HealthResult` interface (line 18) only has 4 (missing `models`). The health grid shows 4 `ServiceCard` components — no card for model availability. This means if `glm-ocr` or `qwen2.5:3b` is missing from Ollama, the admin page shows "all green" while extraction silently fails.

**Context 2 — Requeue button:** `POST /api/v1/admin/requeue-pending-models` exists and returns `{ requeued: number, document_ids: string[] }`. No UI button calls it. Operators currently have no way to trigger requeue without using curl.

- [ ] **Step 1: Fix HealthResult interface**

Change:
```typescript
interface HealthResult {
  database: string;
  redis: string;
  ollama: string;
  storage: string;
}
```
to:
```typescript
interface HealthResult {
  database: string;
  redis: string;
  ollama: string;
  models: string;
  storage: string;
}
```

- [ ] **Step 2: Add models ServiceCard to health grid**

Find the health grid section rendering 4 ServiceCards:
```tsx
<ServiceCard name="database" value={health.database} icon={Database} />
<ServiceCard name="redis"    value={health.redis}    icon={Server} />
<ServiceCard name="model endpoint" value={health.ollama} icon={Cpu} />
<ServiceCard name="storage"  value={health.storage}  icon={HardDrive} />
```
Add `BrainCircuit` (or `Layers`) to the lucide imports at the top, then change the grid to 5 columns and add the models card:

First update the lucide import — add `Layers`:
```typescript
import {
  CheckCircle2, XCircle, RefreshCw, Database, Server, HardDrive,
  Cpu, AlertTriangle, ArrowRight, Users, Layers,
} from 'lucide-react';
```

Then change the grid from `lg:grid-cols-4` to `lg:grid-cols-5`:
```tsx
<div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
```

And add the models card after the ollama card:
```tsx
<ServiceCard name="database"       value={health.database} icon={Database} />
<ServiceCard name="redis"          value={health.redis}    icon={Server} />
<ServiceCard name="model endpoint" value={health.ollama}   icon={Cpu} />
<ServiceCard name="models loaded"  value={health.models}   icon={Layers} />
<ServiceCard name="storage"        value={health.storage}  icon={HardDrive} />
```

- [ ] **Step 3: Add requeue state**

After `const [refreshing, setRefreshing] = useState(false);`, add:
```typescript
const [requeuing, setRequeuing]   = useState(false);
const [requeueResult, setRequeueResult] = useState<{ requeued: number } | null>(null);

const handleRequeue = async () => {
  setRequeuing(true);
  setRequeueResult(null);
  try {
    const { data } = await client.post('/api/v1/admin/requeue-pending-models');
    setRequeueResult({ requeued: data.requeued });
    await refreshAll();
  } catch {
    // error toast shown by axios interceptor
  } finally {
    setRequeuing(false);
  }
};
```

- [ ] **Step 4: Add Requeue button to the header**

The header currently has only "Refresh all" button. Add the requeue button next to it:

Find the header div:
```tsx
<div className="flex items-center justify-between">
  <h2 className="text-2xl font-bold">Admin Console</h2>
  <button
    onClick={() => refreshAll()}
    disabled={refreshing}
    className="flex items-center gap-2 text-sm px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
  >
    <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
    Refresh all
  </button>
</div>
```

Change to:
```tsx
<div className="flex items-center justify-between">
  <h2 className="text-2xl font-bold">Admin Console</h2>
  <div className="flex items-center gap-2">
    {requeueResult && (
      <span className="text-xs text-green-600 font-medium">
        {requeueResult.requeued === 0
          ? 'No pending model docs'
          : `Requeued ${requeueResult.requeued} document${requeueResult.requeued > 1 ? 's' : ''}`}
      </span>
    )}
    <button
      onClick={handleRequeue}
      disabled={requeuing || refreshing}
      title="Re-queue all documents waiting for the AI model"
      className="flex items-center gap-2 text-sm px-3 py-1.5 border border-orange-300 text-orange-700 rounded-lg hover:bg-orange-50 disabled:opacity-50"
    >
      <RefreshCw size={14} className={requeuing ? 'animate-spin' : ''} />
      {requeuing ? 'Requeuing…' : 'Requeue Pending'}
    </button>
    <button
      onClick={() => refreshAll()}
      disabled={refreshing}
      className="flex items-center gap-2 text-sm px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50"
    >
      <RefreshCw size={14} className={refreshing ? 'animate-spin' : ''} />
      Refresh all
    </button>
  </div>
</div>
```

- [ ] **Step 5: Manual smoke test**

1. Open Admin page
2. Verify 5 health cards show (database, redis, model endpoint, models loaded, storage)
3. Click "Requeue Pending" — if no PENDING_MODEL docs exist, confirm "No pending model docs" message appears
4. Verify `pending_model` counter shows in pipeline section when docs exist

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/AdminPage.tsx
git commit -m "feat: add models health card, PENDING_MODEL counter, and requeue button to AdminPage"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Export button on POProfilePage — Task 1
- [x] Export button on PODetailPage — Task 2
- [x] PENDING_MODEL counter in pipeline stats — Task 3
- [x] Stats type includes `pending_model` — Task 3
- [x] Models health card in system health grid — Task 4
- [x] HealthResult type includes `models` — Task 4
- [x] Requeue button with confirmation feedback — Task 4

**No placeholders:** All code is complete. No TODOs or "add appropriate X" language.

**Type consistency:**
- `exportPOAsExcel(id!, profile.po_number, mode)` — matches signature in `purchaseOrders.ts` line 72
- `exportPOAsExcel(id!, po!.po_number, 'separate')` — `po` is non-null at render time (guarded by `if (!po)` check above)
- `stats.pending_model` — added to Stats interface in Task 3 Step 1
- `health.models` — added to HealthResult interface in Task 4 Step 1
- `client.post('/api/v1/admin/requeue-pending-models')` — matches backend route in admin.py line 196
- `PipelineCounter label="Awaiting Model" status="PENDING_MODEL"` — navigates to `/documents?status=PENDING_MODEL`; DocumentsPage filter accepts this status string

**Estimated time:** ~45–90 minutes total for all 4 tasks.
