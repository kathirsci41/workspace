# UX Quick Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement all Branch 1 changes: fix friction points across 6 pages, add 13 feature enhancements, and build the new DocumentDetailPage — all without changing the visual identity.

**Architecture:** Purely additive changes — no page is restructured, only extended. A new `Breadcrumb` component is shared across PODetailPage, POProfilePage, and DocumentDetailPage. Two backend fields are added (`days_pending` on document responses, `stats_delta` on stats) and two new frontend routes are added (`/documents/:id`). All other changes are self-contained within individual page files.

**Tech Stack:** FastAPI + SQLAlchemy (backend), React + TanStack Query + React Router + Tailwind CSS + lucide-react (frontend). No new dependencies.

---

## File Map

**Create:**
- `frontend/src/components/Breadcrumb.tsx` — reusable breadcrumb nav component
- `frontend/src/pages/DocumentDetailPage.tsx` — new two-panel document detail page
- `backend/tests/test_ux_quick_wins.py` — backend tests for new fields

**Modify:**
- `backend/app/schemas/document.py` — add `days_pending: Optional[int]`
- `backend/app/api/v1/documents.py` — compute and set `days_pending` in list response
- `backend/app/api/v1/admin.py` — add `stats_delta` to `/stats` response
- `frontend/src/types/index.ts` — add `days_pending` to Document, `stats_delta` to Stats shape, add `DOC_TYPE_LABELS` export if missing
- `frontend/src/App.tsx` — add `/documents/:id` route
- `frontend/src/components/layout/AppShell.tsx` — rename Admin→System, sidebar default open
- `frontend/src/components/DocumentCard.tsx` — dashed border + bigger empty upload target
- `frontend/src/components/ReviewModal.tsx` — keyboard shortcuts (V/R/Esc)
- `frontend/src/pages/DashboardPage.tsx` — 5th stat card, all clickable, delta display, donut, quick actions, SLA badges, deep-link
- `frontend/src/pages/POListPage.tsx` — chain bar fix, customer name fix, empty state CTA
- `frontend/src/pages/DocumentsPage.tsx` — ref no column, Review action, empty state CTA
- `frontend/src/pages/SearchPage.tsx` — tab URL state, advanced filter URL state, document → /documents/:id
- `frontend/src/pages/PODetailPage.tsx` — breadcrumbs, chain complete banner, ?review auto-open, ?highlight init
- `frontend/src/pages/CustomersPage.tsx` — toast wiring, empty state CTA
- `frontend/src/pages/POProfilePage.tsx` — breadcrumbs

---

## Task 1: Backend — `days_pending` on document list + `stats_delta` on stats

**Files:**
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/api/v1/documents.py`
- Modify: `backend/app/api/v1/admin.py`
- Create: `backend/tests/test_ux_quick_wins.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_ux_quick_wins.py
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.anyio
async def test_document_list_includes_days_pending(async_client: AsyncClient):
    """days_pending is present in document list items (None when not PENDING_REVIEW)."""
    resp = await async_client.get("/api/v1/documents?per_page=1")
    assert resp.status_code == 200
    data = resp.json()
    if data["items"]:
        assert "days_pending" in data["items"][0]


@pytest.mark.anyio
async def test_stats_includes_delta(async_client: AsyncClient):
    """stats response includes stats_delta dict with expected keys."""
    resp = await async_client.get("/api/v1/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "stats_delta" in data
    delta = data["stats_delta"]
    assert "total_purchase_orders" in delta
    assert "total_documents" in delta
    assert "verified" in delta
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd backend
python -m pytest tests/test_ux_quick_wins.py -v
```
Expected: FAIL — `days_pending` key missing from items, `stats_delta` key missing from stats.

- [ ] **Step 3: Add `days_pending` to DocumentResponse schema**

In `backend/app/schemas/document.py`, add the field to `DocumentResponse`:

```python
# Add to imports at top:
from typing import Optional

# Add to DocumentResponse class, after updated_at:
days_pending: Optional[int] = None
```

Full updated `DocumentResponse`:
```python
class DocumentResponse(BaseModel):
    id: UUID
    po_id: UUID
    document_type: str
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    page_count: Optional[int] = None
    checksum: str
    status: str
    rotation: int = 0
    created_at: datetime
    updated_at: datetime
    days_pending: Optional[int] = None
    po_number: str = ""
    customer_name: str = ""
    po_so_number: Optional[str] = None
    metadata: Optional[ExtractionResponse] = None

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 4: Compute `days_pending` in the list_documents endpoint**

In `backend/app/api/v1/documents.py`, find the loop that builds `DocumentResponse` objects (around line 85-110). After constructing each `resp` object, add:

```python
# Add import at top of file:
from datetime import datetime, timezone

# Inside the loop, after resp is constructed and before it's appended to results:
if doc.status == DocumentStatus.PENDING_REVIEW:
    delta = datetime.now(timezone.utc) - doc.updated_at.replace(tzinfo=timezone.utc)
    resp.days_pending = delta.days
```

- [ ] **Step 5: Add `stats_delta` to the get_stats endpoint**

In `backend/app/api/v1/admin.py`, add the following imports and computation inside `get_stats`:

```python
# Add to existing imports at top:
from datetime import datetime, timedelta, timezone

# Inside get_stats, after existing queries:
now = datetime.now(timezone.utc)
yesterday = now - timedelta(hours=24)
two_days_ago = now - timedelta(hours=48)

today_pos = (await db.scalar(
    select(func.count(PurchaseOrder.id)).where(PurchaseOrder.created_at >= yesterday)
)) or 0
prev_pos = (await db.scalar(
    select(func.count(PurchaseOrder.id)).where(
        PurchaseOrder.created_at >= two_days_ago,
        PurchaseOrder.created_at < yesterday,
    )
)) or 0

today_docs = (await db.scalar(
    select(func.count(Document.id)).where(Document.created_at >= yesterday)
)) or 0
prev_docs = (await db.scalar(
    select(func.count(Document.id)).where(
        Document.created_at >= two_days_ago,
        Document.created_at < yesterday,
    )
)) or 0

today_verified = (await db.scalar(
    select(func.count(Document.id)).where(
        Document.status == DocumentStatus.VERIFIED,
        Document.updated_at >= yesterday,
    )
)) or 0
prev_verified = (await db.scalar(
    select(func.count(Document.id)).where(
        Document.status == DocumentStatus.VERIFIED,
        Document.updated_at >= two_days_ago,
        Document.updated_at < yesterday,
    )
)) or 0
```

Then update the return dict to add `stats_delta`:
```python
return {
    "total_customers":       total_customers,
    "total_purchase_orders": po_count,
    "total_documents":       doc_row.total,
    "uploaded":              doc_row.uploaded,
    "extracting":            doc_row.extracting,
    "pending_reviews":       doc_row.pending_reviews,
    "verified":              doc_row.verified,
    "extraction_failures":   doc_row.extraction_failures,
    "pending_model":         doc_row.pending_model,
    "rejected":              doc_row.rejected,
    "stats_delta": {
        "total_purchase_orders": today_pos - prev_pos,
        "total_documents":       today_docs - prev_docs,
        "verified":              today_verified - prev_verified,
    },
}
```

- [ ] **Step 6: Run tests to confirm they pass**

```bash
cd backend
python -m pytest tests/test_ux_quick_wins.py -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/document.py backend/app/api/v1/documents.py backend/app/api/v1/admin.py backend/tests/test_ux_quick_wins.py
git commit -m "feat: add days_pending to document list + stats_delta to admin stats"
```

---

## Task 2: AppShell — rename Admin→System, sidebar default open

**Files:**
- Modify: `frontend/src/components/layout/AppShell.tsx`

- [ ] **Step 1: Replace Terminal icon with Settings2, rename label, fix default**

Change lines at top:
```tsx
// OLD import line — remove Terminal, add Settings2:
import {
  LayoutDashboard,
  Users,
  FileText,
  Files,
  Search,
  Settings2,   // ← new
  Menu,
  X,
  ChevronRight,
  ChevronLeft,
} from 'lucide-react';
```

Change navLinks entry:
```tsx
// OLD:
{ to: '/admin',  label: 'Admin',  icon: Terminal },
// NEW:
{ to: '/admin',  label: 'System', icon: Settings2 },
```

Change `getInitialCollapsed`:
```tsx
function getInitialCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === null ? false : stored === 'true';  // ← false (expanded) for first-time visitors
  } catch {
    return false;
  }
}
```

- [ ] **Step 2: Verify visually in browser — sidebar should start expanded on fresh localStorage**

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/layout/AppShell.tsx
git commit -m "feat: rename Admin nav to System, sidebar defaults to expanded"
```

---

## Task 3: Breadcrumb component

**Files:**
- Create: `frontend/src/components/Breadcrumb.tsx`

- [ ] **Step 1: Create the component**

```tsx
// frontend/src/components/Breadcrumb.tsx
import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

export interface BreadcrumbItem {
  label: string;
  to?: string;
}

export default function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="flex items-center gap-1.5 text-sm text-gray-500 mb-4">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-1.5">
          {i > 0 && <ChevronRight size={14} className="text-gray-400 shrink-0" />}
          {item.to ? (
            <Link to={item.to} className="hover:text-blue-600 transition-colors">
              {item.label}
            </Link>
          ) : (
            <span className="text-gray-800 font-medium">{item.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/Breadcrumb.tsx
git commit -m "feat: add Breadcrumb component"
```

---

## Task 4: Dashboard — stat cards, donut, quick actions

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add new fields to frontend types**

In `frontend/src/types/index.ts`, find the `Document` interface and add `days_pending`:
```tsx
export interface Document {
  // ... existing fields ...
  days_pending?: number | null;  // add after updated_at
}
```

There is no `Stats` interface in types — it's local to DashboardPage. No types change needed for stats.

- [ ] **Step 2: Rewrite the Stats interface and cards in DashboardPage**

Replace the `Stats` interface and `cards` array in `DashboardPage.tsx`:

```tsx
// Replace existing Stats interface:
interface Stats {
  total_customers: number;
  total_purchase_orders: number;
  total_documents: number;
  pending_reviews: number;
  verified: number;
  extracting: number;
  extraction_failures: number;
  stats_delta?: {
    total_purchase_orders: number;
    total_documents: number;
    verified: number;
  };
}
```

Replace the imports to add `Files`, `Link`, and navigation:
```tsx
import { useEffect, useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Users, FileText, Clock, CheckCircle, AlertTriangle, ArrowRight, Files, Plus, Upload, Timer } from 'lucide-react';
import client from '@/api/client';
import { usePurchaseOrders } from '@/hooks/usePurchaseOrders';
import { useDocumentsByStatus } from '@/hooks/useDocuments';
import { DOC_TYPE_LABELS } from '@/types';
import clsx from 'clsx';
```

Replace the `cards` array to add 5th card, navigation, and delta:
```tsx
const delta = stats?.stats_delta;
const cards = stats
  ? [
      {
        label: 'Total Customers',
        value: stats.total_customers,
        icon: Users,
        color: 'bg-blue-100 text-blue-600',
        to: '/customers',
        delta: undefined,
      },
      {
        label: 'Total POs',
        value: stats.total_purchase_orders,
        icon: FileText,
        color: 'bg-green-100 text-green-600',
        to: '/purchase-orders',
        delta: delta?.total_purchase_orders,
      },
      {
        label: 'Pending Reviews',
        value: stats.pending_reviews,
        icon: Clock,
        color: 'bg-amber-100 text-amber-600',
        to: undefined,
        delta: undefined,
        onClick: () => reviewQueueRef.current?.scrollIntoView({ behavior: 'smooth' }),
      },
      {
        label: 'Verified Documents',
        value: stats.verified,
        icon: CheckCircle,
        color: 'bg-emerald-100 text-emerald-600',
        to: '/documents?status=VERIFIED',
        delta: delta?.verified,
      },
      {
        label: 'Total Documents',
        value: stats.total_documents,
        icon: Files,
        color: 'bg-purple-100 text-purple-600',
        to: '/documents',
        delta: delta?.total_documents,
      },
    ]
  : [];
```

Replace the stat cards JSX:
```tsx
{/* Stat cards */}
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
  {cards.map((card) => (
    <div
      key={card.label}
      onClick={card.onClick ?? (card.to ? () => navigate(card.to!) : undefined)}
      className={clsx(
        'bg-white rounded-lg border border-gray-200 p-5 flex items-center gap-4',
        (card.onClick ?? card.to) && 'cursor-pointer hover:border-blue-300 transition-colors'
      )}
    >
      <div className={clsx('p-3 rounded-lg shrink-0', card.color)}>
        <card.icon size={24} />
      </div>
      <div>
        <p className="text-sm text-gray-500">{card.label}</p>
        <p className="text-2xl font-bold">{card.value}</p>
        {card.delta != null && card.delta !== 0 && (
          <p className={clsx('text-xs', card.delta > 0 ? 'text-green-600' : 'text-red-500')}>
            {card.delta > 0 ? `↑${card.delta}` : `↓${Math.abs(card.delta)}`} since yesterday
          </p>
        )}
      </div>
    </div>
  ))}
</div>
```

- [ ] **Step 3: Add donut chart below stat cards**

Insert the following block after the stat cards `</div>` and before the Review Queue section:

```tsx
{/* Document status donut */}
{stats && (() => {
  const total = stats.verified + stats.pending_reviews + stats.extracting + stats.extraction_failures;
  if (total === 0) return null;
  const v  = (stats.verified           / total) * 100;
  const p  = (stats.pending_reviews    / total) * 100;
  const f  = (stats.extraction_failures / total) * 100;
  // extracting fills the rest
  const gradient = `conic-gradient(#22c55e 0% ${v}%, #f59e0b ${v}% ${v + p}%, #ef4444 ${v + p}% ${v + p + f}%, #3b82f6 ${v + p + f}% 100%)`;
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-5 mb-6 flex items-center gap-6">
      <div className="relative shrink-0" style={{ width: 56, height: 56 }}>
        <div style={{ background: gradient, width: 56, height: 56, borderRadius: '50%' }} />
        <div className="absolute inset-3 bg-white rounded-full" />
      </div>
      <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-700">
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-green-500 inline-block shrink-0" />
          {stats.verified} Verified
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block shrink-0" />
          {stats.pending_reviews} Pending
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block shrink-0" />
          {stats.extraction_failures} Failed
        </span>
        <span className="flex items-center gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block shrink-0" />
          {stats.extracting} Extracting
        </span>
      </div>
    </div>
  );
})()}

{/* Quick action bar */}
<div className="flex flex-wrap items-center gap-3 mb-6">
  <button
    onClick={() => navigate('/purchase-orders')}
    className="flex items-center gap-1.5 bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 font-medium"
  >
    <Plus size={15} /> Create PO
  </button>
  <button
    onClick={() => navigate('/purchase-orders')}
    className="flex items-center gap-1.5 bg-white border border-gray-300 text-gray-700 text-sm px-4 py-2 rounded-lg hover:bg-gray-50 font-medium"
  >
    <Upload size={15} /> Upload Document
  </button>
  <button
    onClick={() => reviewQueueRef.current?.scrollIntoView({ behavior: 'smooth' })}
    className="flex items-center gap-1.5 bg-amber-50 border border-amber-300 text-amber-800 text-sm px-4 py-2 rounded-lg hover:bg-amber-100 font-medium"
  >
    <Timer size={15} /> Review Pending ({stats?.pending_reviews ?? 0})
  </button>
</div>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx frontend/src/types/index.ts
git commit -m "feat: dashboard stat cards (5th card, clickable, delta, donut, quick actions)"
```

---

## Task 5: Dashboard — SLA aging badges + review queue deep-link

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`

- [ ] **Step 1: Add SLA badges to pending review rows**

In the review queue `<tbody>`, update the row rendering to highlight SLA violations. Find the `<tr key={doc.id}>` inside `pendingData?.items?.map(...)` and:

1. Add SLA class to the row when `days_pending >= 3`:
```tsx
<tr
  key={doc.id}
  className={clsx(
    'hover:bg-amber-50',
    (doc.days_pending ?? 0) >= 3 && 'bg-red-50'
  )}
>
```

2. Add a days badge in the Note column (after the existing note span):
```tsx
<td className="px-5 py-3 max-w-[240px]">
  {(doc.days_pending ?? 0) >= 3 && (
    <span className="inline-flex items-center gap-1 text-xs text-red-700 font-medium bg-red-100 px-2 py-0.5 rounded-full mr-2">
      <AlertTriangle size={10} />
      {doc.days_pending}d overdue
    </span>
  )}
  {note && (
    <span className="flex items-center gap-1 text-xs text-amber-700">
      <AlertTriangle size={12} className="flex-shrink-0" />
      <span className="truncate" title={note}>{note}</span>
    </span>
  )}
</td>
```

- [ ] **Step 2: Change "Open PO" button to a deep-link**

Find the action `<td>` in the review queue rows and replace the button:
```tsx
<td className="px-5 py-3">
  <button
    onClick={() => navigate(`/purchase-orders/${doc.po_id}?highlight=${doc.id}&review=${doc.id}`)}
    className="text-xs font-medium text-blue-600 hover:underline"
  >
    Review →
  </button>
</td>
```

- [ ] **Step 3: Update review queue empty state to positive message**

Find the existing empty row:
```tsx
// OLD:
<td colSpan={6} className="px-5 py-8 text-center text-gray-400">
  No documents pending review.
</td>
// NEW:
<td colSpan={6} className="px-5 py-8 text-center text-green-600 font-medium">
  ✓ No documents pending review
</td>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DashboardPage.tsx
git commit -m "feat: SLA aging badges in review queue, deep-link review button, green empty state"
```

---

## Task 6: PO List — bug fixes + empty state

**Files:**
- Modify: `frontend/src/pages/POListPage.tsx`

- [ ] **Step 1: Fix chain bar max-width**

Find: `max-w-[80px]` in the chain bar cell (around line 239) and change to `max-w-[120px]`.

```tsx
// OLD:
<div className="flex-1 h-2 bg-gray-200 rounded-full max-w-[80px]">
// NEW:
<div className="flex-1 h-2 bg-gray-200 rounded-full max-w-[120px]">
```

- [ ] **Step 2: Fix customer name spacing**

Find the customer name display (around line 225):
```tsx
// OLD:
{po.customer_name
  ? `${po.customer_sky_id ?? ''} ${po.customer_name}`
  : '—'}
// NEW:
{po.customer_name
  ? `${po.customer_sky_id ? `${po.customer_sky_id} ` : ''}${po.customer_name}`
  : '—'}
```

- [ ] **Step 3: Update empty state with CTA**

Find the "No purchase orders found." empty state in the table and replace:
```tsx
// OLD:
<td colSpan={6} className="px-5 py-8 text-center text-gray-400">
  No purchase orders found.
</td>
// NEW:
<td colSpan={6} className="px-5 py-8 text-center text-gray-400">
  <p className="mb-2">No purchase orders yet.</p>
  <button
    onClick={() => setShowModal(true)}
    className="text-sm text-blue-600 hover:underline font-medium"
  >
    + Create your first PO
  </button>
</td>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/POListPage.tsx
git commit -m "fix: chain bar width, customer name spacing, PO list empty state CTA"
```

---

## Task 7: Documents Page — ref no column, Review action, empty state

**Files:**
- Modify: `frontend/src/pages/DocumentsPage.tsx`

- [ ] **Step 1: Add "Ref No" column header after Filename**

Find the `<thead>` row and insert after the Filename `<th>`:
```tsx
<th className="text-left px-5 py-3 font-medium">Filename</th>
<th className="text-left px-5 py-3 font-medium">Ref No</th>   {/* ← new */}
<th className="text-left px-5 py-3 font-medium">PO Number</th>
```

- [ ] **Step 2: Add Ref No cell in each row**

Find the Filename `<td>` in the `data.items.map(...)` loop and insert after it:
```tsx
<td className="px-5 py-3 text-gray-700 max-w-[200px] truncate" title={doc.original_filename ?? '—'}>
  {doc.original_filename ?? '—'}
</td>
<td className="px-5 py-3 font-mono text-xs text-gray-600">   {/* ← new */}
  {doc.metadata?.primary_ref_no ?? '—'}
</td>
```

- [ ] **Step 3: Add Review action for PENDING_REVIEW rows**

Find the actions `<td>` (last column, contains "Open PO" button). Replace the entire last `<td>` with:
```tsx
<td className="px-5 py-3">
  <div className="flex items-center gap-3">
    {doc.status === 'PENDING_REVIEW' && doc.po_id && (
      <button
        onClick={() => navigate(`/purchase-orders/${doc.po_id}?highlight=${doc.id}&review=${doc.id}`)}
        className="flex items-center gap-1 text-xs font-medium text-amber-700 hover:text-amber-900"
      >
        Review →
      </button>
    )}
    {doc.po_id && (
      <button
        onClick={() => navigate(`/purchase-orders/${doc.po_id}`)}
        className="flex items-center gap-1 text-xs text-blue-600 hover:underline"
      >
        <ExternalLink size={12} />
        Open PO
      </button>
    )}
  </div>
</td>
```

- [ ] **Step 4: Update empty state**

```tsx
// OLD:
<td colSpan={7} className="px-5 py-8 text-center text-gray-400">
  No documents found matching the selected filters.
</td>
// NEW (colSpan now 8 because of new column):
<td colSpan={8} className="px-5 py-8 text-center text-gray-400">
  <p className="mb-2">No documents match these filters.</p>
  <button
    onClick={resetFilters}
    className="text-sm text-blue-600 hover:underline font-medium"
  >
    Reset filters
  </button>
</td>
```

Also update the Loading and colSpan values from `7` to `8`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/DocumentsPage.tsx
git commit -m "feat: ref no column, Review action, empty state CTA in Documents page"
```

---

## Task 8: Search — URL state + document navigation

**Files:**
- Modify: `frontend/src/pages/SearchPage.tsx`

- [ ] **Step 1: Persist tab in URL**

In `SearchPage.tsx`, change the `tab` state initialization to read from URL, and write back when changed:

```tsx
// Replace this:
const [tab, setTab] = useState<'global' | 'address'>('global');

// With:
const [tab, setTab] = useState<'global' | 'address'>(
  (searchParams.get('tab') as 'global' | 'address') ?? 'global'
);

// Replace setTab calls in button handlers with a version that also updates URL:
const handleTabChange = (newTab: 'global' | 'address') => {
  setTab(newTab);
  setSearchParams((prev) => {
    const next = new URLSearchParams(prev);
    next.set('tab', newTab);
    return next;
  });
};
```

Update both tab buttons to use `handleTabChange` instead of `setTab`.

- [ ] **Step 2: Persist advanced filter state in URL when Search is clicked**

In the "Search" button handler inside the advanced filters panel, update `setSearchParams` to include active filter values:

```tsx
// Replace the existing Search button onClick:
onClick={() => {
  const active = Object.fromEntries(
    Object.entries(advFilters).filter(([, v]) => v.trim() !== '')
  );
  if (Object.keys(active).length > 0) {
    setAdvQuery(active as typeof advFilters);
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      Object.entries(active).forEach(([k, v]) => next.set(k, v));
      return next;
    });
  }
}}
```

- [ ] **Step 3: Change document result navigation to /documents/:id**

In `handleResultClick`, replace the `case 'document':` branch:

```tsx
case 'document':
  // OLD: navigate(`/purchase-orders/${result.po_id}?highlight=${result.id}`)
  navigate(`/documents/${result.id}`);
  break;
```

- [ ] **Step 4: Update empty state text**

In the global tab results, replace the empty state `<p>`:
```tsx
// OLD:
<p className="text-sm">No results found. Try a different search term.</p>
// NEW:
<p className="text-sm">No results. Try a shorter search term or use Advanced filters.</p>
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/SearchPage.tsx
git commit -m "feat: tab URL state, advanced filter URL state, document results to /documents/:id"
```

---

## Task 9: PO Detail — breadcrumbs, chain banner, ?review param, dashed empty slots

**Files:**
- Modify: `frontend/src/pages/PODetailPage.tsx`
- Modify: `frontend/src/components/DocumentCard.tsx`

- [ ] **Step 1: Add dashed border to empty DocumentCard slots**

In `DocumentCard.tsx`, update the `borderColor` for `empty` and the container class:

```tsx
// Replace:
const borderColor = {
  empty: 'border-gray-300',
  ...
}[status] ?? 'border-gray-300';

// With:
const borderStyle = status === 'empty' ? 'border-dashed' : 'border-solid';
const borderColor = {
  empty: 'border-gray-300',
  UPLOADED: 'border-blue-300',
  EXTRACTING: 'border-blue-400',
  PENDING_REVIEW: 'border-amber-400',
  PENDING_MODEL: 'border-orange-300',
  VERIFIED: 'border-green-400',
  EXTRACTION_FAILED: 'border-red-400',
  REJECTED: 'border-red-400',
}[status] ?? 'border-gray-300';
```

Update the container `className`:
```tsx
className={clsx(
  'rounded-lg border-2 p-4 transition-all',
  borderStyle,   // ← add this
  borderColor,
  isSelected && 'ring-2 ring-blue-500 shadow-md',
  highlighted && 'ring-2 ring-yellow-400 shadow-lg',
  status === 'empty' ? 'cursor-default' : 'cursor-pointer hover:shadow-sm'
)}
```

Make the empty state body larger:
```tsx
{/* Empty state */}
{status === 'empty' && (
  <div className="text-center py-5">
    <Upload size={24} className="mx-auto mb-2 text-gray-300" />
    <p className="text-sm text-gray-400 mb-3">No document uploaded yet</p>
    <button
      onClick={(e) => {
        e.stopPropagation();
        onUpload();
      }}
      className="inline-flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium border border-blue-200 hover:border-blue-400 px-3 py-1.5 rounded-lg transition-colors"
    >
      <Upload size={14} />
      Upload Document
    </button>
  </div>
)}
```

- [ ] **Step 2: Add breadcrumbs to PODetailPage**

At the top of `PODetailPage.tsx`, add the import:
```tsx
import Breadcrumb from '@/components/Breadcrumb';
```

In the JSX, add breadcrumb before the page heading. Find where the page content starts (after the loading check) and add:
```tsx
{po && (
  <Breadcrumb items={[
    { label: 'Purchase Orders', to: '/purchase-orders' },
    { label: po.po_number },
  ]} />
)}
```

- [ ] **Step 3: Auto-open ReviewModal from ?review URL param**

In `PODetailPage.tsx`, add `reviewParam` extraction and `useEffect`:

```tsx
// After existing:
const highlightDocId = searchParams.get('highlight');
// Add:
const reviewParam = searchParams.get('review');

// Add useEffect (after existing useEffects):
useEffect(() => {
  if (reviewParam && !reviewDocId) {
    setReviewDocId(reviewParam);
  }
}, [reviewParam]);  // only on mount (reviewParam is stable on first render)
```

- [ ] **Step 4: Initialize selectedDocId from ?highlight param**

Find the current `selectedDocId` state:
```tsx
// OLD:
const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
// NEW:
const [selectedDocId, setSelectedDocId] = useState<string | null>(highlightDocId);
```

- [ ] **Step 5: Add chain complete banner**

After the `<ChainStatusBar>` component and before the document cards section, add:

```tsx
{chainData?.completeness_pct === 100 && (() => {
  const bannerKey = `chain-complete-dismissed-${id}`;
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(bannerKey) === '1'; } catch { return false; }
  });
  if (dismissed) return null;
  return (
    <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
      <span className="text-sm text-green-800 font-medium">
        ✓ All documents complete —{' '}
        <Link to={`/purchase-orders/${id}/profile`} className="underline">View Profile →</Link>
      </span>
      <button
        onClick={() => {
          try { sessionStorage.setItem(bannerKey, '1'); } catch {}
          setDismissed(true);
        }}
        className="text-green-600 hover:text-green-800 ml-4"
      >
        <X size={16} />
      </button>
    </div>
  );
})()}
```

Wait — you can't call `useState` inside a callback or IIFE. Let me refactor this into a proper component:

Replace the above with a separate component defined at the bottom of the file:

```tsx
// Add at bottom of PODetailPage.tsx, before export default:
function ChainCompleteBanner({ poId, profilePath }: { poId: string; profilePath: string }) {
  const bannerKey = `chain-complete-dismissed-${poId}`;
  const [dismissed, setDismissed] = useState(() => {
    try { return sessionStorage.getItem(bannerKey) === '1'; } catch { return false; }
  });
  if (dismissed) return null;
  return (
    <div className="bg-green-50 border border-green-200 rounded-lg px-4 py-3 mb-4 flex items-center justify-between">
      <span className="text-sm text-green-800 font-medium">
        ✓ All documents complete —{' '}
        <Link to={profilePath} className="underline hover:text-green-900">View Profile →</Link>
      </span>
      <button
        onClick={() => {
          try { sessionStorage.setItem(bannerKey, '1'); } catch {}
          setDismissed(true);
        }}
        className="text-green-600 hover:text-green-800 ml-4"
      >
        <X size={16} />
      </button>
    </div>
  );
}
```

And in the JSX, after `<ChainStatusBar>`:
```tsx
{chainData?.completeness_pct === 100 && (
  <ChainCompleteBanner poId={id!} profilePath={`/purchase-orders/${id}/profile`} />
)}
```

Make sure `Link` and `X` are imported at the top of the file (Link from react-router-dom already exists, X is in lucide-react already).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/PODetailPage.tsx frontend/src/components/DocumentCard.tsx
git commit -m "feat: PO detail breadcrumbs, chain banner, auto-open review/preview from URL, dashed empty slots"
```

---

## Task 10: Review Modal — keyboard shortcuts

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx`

- [ ] **Step 1: Add keydown listener useEffect**

In `ReviewModal.tsx`, after the existing hooks and before the return statement, add a `useEffect`:

```tsx
// Add after the existing state declarations:
useEffect(() => {
  if (mode !== 'review') return;
  const handleKey = (e: KeyboardEvent) => {
    if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
    if (e.key === 'v' || e.key === 'V') {
      e.preventDefault();
      if (!verifyMutation.isPending && metadata?.status !== 'VERIFIED') {
        verifyMutation.mutate(documentId, { onSuccess: onVerified });
      }
    } else if (e.key === 'r' || e.key === 'R') {
      e.preventDefault();
      if (!rejectMutation.isPending) {
        rejectMutation.mutate(documentId, { onSuccess: onVerified });
      }
    } else if (e.key === 'Escape') {
      onClose();
    }
  };
  window.addEventListener('keydown', handleKey);
  return () => window.removeEventListener('keydown', handleKey);
}, [mode, verifyMutation, rejectMutation, documentId, onVerified, onClose, metadata]);
```

- [ ] **Step 2: Add keyboard hint in modal footer**

Find the modal footer (the section with Verify/Reject buttons). After the button row, add:

```tsx
<p className="text-xs text-gray-400 text-center mt-2">
  V verify · R reject · Esc close
</p>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: keyboard shortcuts V/R/Esc in ReviewModal"
```

---

## Task 11: Customers empty state + toast wiring

**Files:**
- Modify: `frontend/src/pages/CustomersPage.tsx`

- [ ] **Step 1: Wire toast into CustomersPage**

Add `useToast` import and hook call:
```tsx
// Add import:
import { useToast } from '@/context/ToastContext';

// Add inside the component function:
const showToast = useToast();
```

Wire the createMutation to show toasts:
```tsx
// Find the existing Add Customer button or form submit and wrap createMutation.mutate:
createMutation.mutate(body, {
  onSuccess: () => {
    setShowModal(false);
    showToast('Customer added successfully.', 'success');
  },
  onError: () => showToast('Failed to add customer.', 'error'),
});
```

- [ ] **Step 2: Update empty state**

Find the empty state in the customers table and replace:
```tsx
// Find "No customers" empty row, replace:
<td colSpan={N} className="px-5 py-8 text-center text-gray-400">
  <p className="mb-2">No customers yet.</p>
  <button
    onClick={() => setShowModal(true)}
    className="text-sm text-blue-600 hover:underline font-medium"
  >
    + Add a customer
  </button>
</td>
```

(Replace `N` with the actual colspan count — read the table headers to find it, typically 6 for Customers.)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CustomersPage.tsx
git commit -m "feat: toast wiring and empty state CTA on CustomersPage"
```

---

## Task 12: POProfilePage — breadcrumbs

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`

- [ ] **Step 1: Add breadcrumbs**

Add import:
```tsx
import Breadcrumb from '@/components/Breadcrumb';
```

Find where `id` and `profile` are available in the component and add breadcrumbs before the page header:
```tsx
{profile && (
  <Breadcrumb items={[
    { label: 'Purchase Orders', to: '/purchase-orders' },
    { label: profile.po_number, to: `/purchase-orders/${id}` },
    { label: 'Profile' },
  ]} />
)}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx
git commit -m "feat: breadcrumbs on PO Profile page"
```

---

## Task 13: New DocumentDetailPage

**Files:**
- Create: `frontend/src/pages/DocumentDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

This is the largest new addition — a two-panel page showing PDF + extracted data with cross-check alerts.

- [ ] **Step 1: Add the route in App.tsx**

```tsx
// Add import at top:
import DocumentDetailPage from './pages/DocumentDetailPage';

// Add route inside <Route element={<AppShell />}>:
<Route path="/documents/:id" element={<DocumentDetailPage />} />
```

The `/documents/:id` route must come before the `/documents` route (or use exact matching — React Router v6 handles this automatically).

- [ ] **Step 2: Create DocumentDetailPage.tsx**

```tsx
// frontend/src/pages/DocumentDetailPage.tsx
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, RotateCcw, PenLine, Download, AlertTriangle, CheckCircle, XCircle } from 'lucide-react';
import { useDocument } from '@/hooks/useDocuments';
import { usePOProfile } from '@/hooks/usePurchaseOrders';
import { getPreviewUrl, getDownloadUrl } from '@/api/documents';
import PDFPreviewPanel from '@/components/PDFPreviewPanel';
import Breadcrumb from '@/components/Breadcrumb';
import clsx from 'clsx';
import type { FieldComparison, POProfileDiscrepancy } from '@/types';

const DOC_TYPE_LABELS: Record<string, string> = {
  CUSTOMER_PO:     'Customer PO',
  COMPANY_PO:      'Company PO',
  VENDOR_DC:       'Vendor DC',
  VENDOR_INVOICE:  'Vendor Invoice',
  COMPANY_DC:      'Company DC',
  COMPANY_INVOICE: 'Company Invoice',
};

const STATUS_COLORS: Record<string, string> = {
  VERIFIED:          'bg-green-100 text-green-700',
  PENDING_REVIEW:    'bg-amber-100 text-amber-700',
  EXTRACTION_FAILED: 'bg-red-100 text-red-700',
  REJECTED:          'bg-red-100 text-red-600',
  EXTRACTING:        'bg-blue-100 text-blue-700',
  UPLOADED:          'bg-gray-100 text-gray-600',
};

export default function DocumentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: doc, isLoading: docLoading, isError } = useDocument(id!);
  const { data: profile } = usePOProfile(doc?.po_id ?? '', !!doc?.po_id);

  if (docLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading...
      </div>
    );
  }

  if (isError || !doc) {
    return (
      <div className="flex items-center justify-center h-64 text-red-500">
        Document not found.
      </div>
    );
  }

  const docTypeLabel = DOC_TYPE_LABELS[doc.document_type] ?? doc.document_type;
  const refNo = doc.metadata?.primary_ref_no ?? doc.original_filename;
  const confidence = doc.metadata?.confidence_score;
  const extractionRoute = doc.metadata?.extraction_route;

  // Filter cross-check data for this document's type
  const discrepancies: POProfileDiscrepancy[] = profile
    ? profile.discrepancies.filter((d) => d.doc_type === doc.document_type)
    : [];
  const fieldComparisons: FieldComparison[] = profile
    ? profile.field_comparisons.filter(
        (fc) => fc.source_doc === doc.document_type || fc.compared_doc === doc.document_type
      )
    : [];
  const mismatchedComparisons = fieldComparisons.filter((fc) => fc.match === false);
  const totalAlerts = discrepancies.length + mismatchedComparisons.length;

  // Extracted fields — all top-level non-private keys from extracted_data
  const extractedData = doc.metadata?.extracted_data ?? {};
  const displayFields = Object.entries(extractedData)
    .filter(([k]) => !k.startsWith('_'))
    .filter(([, v]) => v != null && v !== '' && !Array.isArray(v) && typeof v !== 'object');

  // Extraction checks from _validation_errors
  const validationErrors = (extractedData['_validation_errors'] as string[] | undefined) ?? [];

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 64px)' }}>
      {/* Breadcrumb */}
      <div className="px-6 pt-4 shrink-0">
        <Breadcrumb items={[
          { label: 'Purchase Orders', to: '/purchase-orders' },
          { label: doc.po_number || 'PO', to: doc.po_id ? `/purchase-orders/${doc.po_id}` : '/purchase-orders' },
          { label: `${docTypeLabel}${refNo ? ` — ${refNo}` : ''}` },
        ]} />
      </div>

      {/* Header bar */}
      <div className="shrink-0 px-6 pb-4 border-b border-gray-200 flex items-center gap-3 flex-wrap">
        <div>
          <div className="font-bold text-gray-900 text-base">{refNo}</div>
          <div className="text-xs text-gray-500">
            {docTypeLabel}
            {doc.customer_name && ` · ${doc.customer_name}`}
            {doc.po_number && ` · ${doc.po_number}`}
          </div>
        </div>

        <span className={clsx('text-xs font-medium px-2.5 py-1 rounded-full', STATUS_COLORS[doc.status] ?? 'bg-gray-100 text-gray-700')}>
          {doc.status.replace(/_/g, ' ')}
        </span>

        {totalAlerts > 0 && (
          <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-amber-100 text-amber-800">
            ⚠ {totalAlerts} cross-check alert{totalAlerts !== 1 ? 's' : ''}
          </span>
        )}

        {extractionRoute && confidence != null && (
          <span className="text-xs px-2.5 py-1 rounded-full bg-blue-50 text-blue-700">
            ⚡ {extractionRoute} · {Math.round(confidence * 100)}%
          </span>
        )}

        <div className="ml-auto flex items-center gap-2">
          <a
            href={getDownloadUrl(id!)}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-50 flex items-center gap-1"
          >
            <Download size={13} /> Download
          </a>
          {doc.po_id && (
            <button
              onClick={() => navigate(`/purchase-orders/${doc.po_id}?highlight=${id}`)}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 font-medium flex items-center gap-1"
            >
              Open in PO <ArrowRight size={13} />
            </button>
          )}
        </div>
      </div>

      {/* Two-panel body */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left: PDF viewer */}
        <div className="flex-1 min-w-0 border-r border-gray-200" style={{ maxWidth: '55%' }}>
          <PDFPreviewPanel
            documentId={id!}
            refNumber={refNo}
            documentType={doc.document_type}
          />
        </div>

        {/* Right: data panels */}
        <div className="w-[45%] shrink-0 overflow-y-auto bg-white flex flex-col">

          {/* Extracted Fields */}
          <div className="p-5 border-b border-gray-100">
            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">
              Extracted Fields
            </h4>
            {displayFields.length === 0 ? (
              <p className="text-sm text-gray-400">No extracted data available.</p>
            ) : (
              <div className="grid grid-cols-2 gap-2">
                {displayFields.map(([key, value]) => {
                  const hasMismatch = mismatchedComparisons.some(
                    (fc) => fc.field_label.toLowerCase().includes(key.toLowerCase())
                  );
                  return (
                    <div
                      key={key}
                      className={clsx(
                        'rounded-lg p-2.5',
                        hasMismatch
                          ? 'bg-amber-50 border border-amber-200'
                          : 'bg-gray-50'
                      )}
                    >
                      <div className="text-xs text-gray-400 mb-0.5 capitalize">
                        {key.replace(/_/g, ' ')}
                        {hasMismatch && ' ⚠'}
                      </div>
                      <div className="text-sm font-semibold text-gray-900 truncate" title={String(value)}>
                        {String(value)}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Cross-check Alerts — only if there are alerts */}
          {totalAlerts > 0 && (
            <div className="p-5 border-b border-gray-100 bg-amber-50">
              <div className="flex items-center justify-between mb-3">
                <h4 className="text-xs font-bold text-amber-900 uppercase tracking-wider">
                  ⚠ Cross-check Alerts
                </h4>
                <span className="text-xs font-semibold bg-amber-200 text-amber-900 px-2 py-0.5 rounded-full">
                  {totalAlerts} issue{totalAlerts !== 1 ? 's' : ''}
                </span>
              </div>
              <div className="space-y-2">
                {discrepancies.map((d, i) => (
                  <div key={i} className="bg-white border border-amber-200 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-1">
                      <AlertTriangle size={13} className="text-amber-600 shrink-0" />
                      <span className="text-sm font-semibold text-gray-800">{d.message}</span>
                    </div>
                    <p className="text-xs text-gray-500">{d.type.replace(/_/g, ' ')}</p>
                  </div>
                ))}
                {mismatchedComparisons.map((fc, i) => (
                  <div key={i} className="bg-white border border-amber-200 rounded-lg p-3">
                    <div className="flex items-center gap-1.5 mb-2">
                      <AlertTriangle size={13} className="text-amber-600 shrink-0" />
                      <span className="text-sm font-semibold text-gray-800">
                        {fc.field_label} mismatch
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="bg-gray-50 rounded p-2 text-center">
                        <div className="text-xs text-gray-400 mb-0.5">{fc.source_doc.replace(/_/g, ' ')}</div>
                        <div className="text-sm font-bold text-red-600">{fc.source_value ?? '—'}</div>
                      </div>
                      <div className="bg-gray-50 rounded p-2 text-center">
                        <div className="text-xs text-gray-400 mb-0.5">{fc.compared_doc.replace(/_/g, ' ')}</div>
                        <div className="text-sm font-bold text-gray-700">{fc.compared_value ?? '—'}</div>
                      </div>
                    </div>
                    {fc.note && (
                      <p className="text-xs text-amber-800 mt-2">{fc.note}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Extraction Checks */}
          <div className="p-5 border-b border-gray-100">
            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">
              Extraction Checks
            </h4>
            {validationErrors.length === 0 && displayFields.length > 0 ? (
              <div className="flex items-center gap-1.5 text-sm text-green-700">
                <CheckCircle size={14} />
                All checks passed
              </div>
            ) : validationErrors.length === 0 && displayFields.length === 0 ? (
              <p className="text-sm text-gray-400">No extraction data.</p>
            ) : (
              <div className="space-y-1.5">
                {validationErrors.map((err, i) => (
                  <div key={i} className="flex items-start gap-1.5 text-sm text-amber-700">
                    <AlertTriangle size={13} className="shrink-0 mt-0.5" />
                    {err}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Parent PO — always visible at bottom */}
          <div className="p-5 mt-auto">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 flex items-center gap-3">
              <div>
                <div className="text-xs text-gray-500">Part of</div>
                <div className="text-sm font-semibold text-blue-800">
                  {doc.po_number || 'Unknown PO'}
                  {doc.customer_name && ` — ${doc.customer_name}`}
                </div>
              </div>
              {doc.po_id && (
                <Link
                  to={`/purchase-orders/${doc.po_id}`}
                  className="ml-auto text-xs text-blue-600 hover:text-blue-800 font-medium whitespace-nowrap"
                >
                  View full PO →
                </Link>
              )}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Verify the route works — navigate to /documents/:id from the Documents page**

Open the app in browser, go to Documents page, click any document's "Open PO" to confirm the page loads. The review action should now navigate to DocumentDetailPage.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DocumentDetailPage.tsx frontend/src/App.tsx
git commit -m "feat: new DocumentDetailPage at /documents/:id with PDF viewer, extracted fields, cross-check alerts"
```

---

## Self-Review Checklist

- [x] All 19 spec changes accounted for across 13 tasks
- [x] `days_pending` added to both schema and endpoint
- [x] `stats_delta` backend + frontend delta display 
- [x] Donut uses raw `extraction_failures` (already in stats response, just not typed on frontend)
- [x] `?review=docId` auto-opens ReviewModal in PODetailPage (Task 9 Step 3)
- [x] `?highlight=docId` initializes selectedDocId (Task 9 Step 4)
- [x] Document search results navigate to `/documents/:id` (Task 8 Step 3)
- [x] DocumentDetailPage uses existing `usePOProfile` hook + filters by doc_type
- [x] ChainCompleteBanner uses sessionStorage (per-session dismissal per spec)
- [x] All colSpan values updated in Documents table (7→8 for new column)
- [x] ReviewModal keyboard shortcuts guarded against input fields
- [x] Route added in App.tsx for `/documents/:id`

**Spec gaps verified none** — all items in spec sections 1-9 are covered.
