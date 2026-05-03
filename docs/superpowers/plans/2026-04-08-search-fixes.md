# Search Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 search issues — stale index on reject, pg_trgm fuzzy matching, deep-link to document card from search results, and expose the advanced filter UI that the backend already supports.

**Architecture:** Backend fixes are independent SQLAlchemy/Alembic changes. Frontend fixes are isolated to SearchPage.tsx, PODetailPage.tsx, and DocumentCard.tsx. No new API endpoints needed — the advanced search endpoint already exists at `/api/v1/search/advanced` with full param support.

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, PostgreSQL (pg_trgm extension), React 18, TanStack Query, TypeScript

---

## File Map

| File | Change |
|------|--------|
| `backend/app/api/v1/extraction.py` | Clear ReferenceIndex in reject endpoint |
| `backend/alembic/versions/g9h0i1j2k3l4_add_pg_trgm_index.py` | New migration: enable pg_trgm + GIN index |
| `backend/app/services/search_service.py` | Add similarity OR to global_search ref query |
| `backend/tests/test_search_fixes.py` | Tests for all backend changes |
| `frontend/src/components/DocumentCard.tsx` | Add `highlighted` prop + `id` attribute |
| `frontend/src/pages/PODetailPage.tsx` | Read `?highlight=` param, scroll to card |
| `frontend/src/hooks/useSearch.ts` | Add `useAdvancedSearch` hook |
| `frontend/src/pages/SearchPage.tsx` | Deep-link navigation + advanced filter panel |

---

## Task 1: Clear ReferenceIndex on document reject

**Context:** When an operator rejects a document, its reference numbers remain in `reference_index` and keep appearing in search results as ghost entries. Document deletion already clears the index (document_service.py:177) but reject does not.

**Files:**
- Modify: `backend/app/api/v1/extraction.py` (reject_metadata function, ~line 308)
- Test: `backend/tests/test_search_fixes.py` (create)

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_search_fixes.py`:

```python
"""Tests for search index correctness fixes."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


class TestRejectClearsReferenceIndex:
    """Rejecting a document must remove its entries from reference_index."""

    @pytest.mark.asyncio
    async def test_reject_deletes_reference_index_rows(self):
        """After reject, reference_index rows for the document must be deleted."""
        from app.api.v1.extraction import reject_metadata
        from app.models import DocumentStatus, MetadataStatus

        doc_id = uuid4()
        po_id = uuid4()

        mock_meta = MagicMock()
        mock_meta.status = MetadataStatus.EXTRACTED
        mock_doc = MagicMock()
        mock_doc.id = doc_id
        mock_doc.po_id = po_id
        mock_doc.status = DocumentStatus.PENDING_REVIEW

        deleted_doc_ids = []

        async def mock_execute(stmt):
            # Capture DELETE statements by inspecting the statement
            stmt_str = str(stmt)
            if "reference_index" in stmt_str.lower() and "delete" in stmt_str.lower():
                deleted_doc_ids.append(doc_id)
            result = MagicMock()
            result.scalar_one_or_none.return_value = mock_meta if "document_metadata" in stmt_str.lower() else mock_doc
            return result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=mock_execute)
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        with patch("app.api.v1.extraction._update_chain_async", new_callable=AsyncMock):
            await reject_metadata(doc_id, db)

        assert len(deleted_doc_ids) > 0, "Expected DELETE on reference_index but none was executed"
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
cd backend
.\venv\Scripts\Activate.ps1
pytest tests/test_search_fixes.py::TestRejectClearsReferenceIndex -v
```

Expected: `FAILED — AssertionError: Expected DELETE on reference_index but none was executed`

- [ ] **Step 3: Fix reject_metadata in extraction.py**

In `backend/app/api/v1/extraction.py`, locate `reject_metadata` (~line 308). Replace the body between the doc fetch and the status-set:

```python
@router.put("/documents/{document_id}/metadata/reject", response_model=ExtractionResponse)
async def reject_metadata(
    document_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Reject extraction metadata."""
    result = await db.execute(
        select(DocumentMetadata).where(
            DocumentMetadata.document_id == document_id
        )
    )
    meta = result.scalar_one_or_none()
    if not meta:
        raise HTTPException(
            status_code=404, detail="No metadata found for this document"
        )

    doc_result = await db.execute(
        select(Document).where(Document.id == document_id)
    )
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Clear search index — rejected document should not appear in search results
    await db.execute(
        delete(ReferenceIndex).where(
            ReferenceIndex.document_id == document_id
        )
    )

    meta.status = MetadataStatus.FAILED
    doc.status = DocumentStatus.REJECTED

    await _update_chain_async(db, doc.po_id)
    await db.commit()
    await db.refresh(meta)
    return meta
```

`delete` is already imported at the top of extraction.py (`from sqlalchemy import select, delete, ...`). `ReferenceIndex` is also already imported.

- [ ] **Step 4: Run test — expect PASS**

```bash
pytest tests/test_search_fixes.py::TestRejectClearsReferenceIndex -v
```

Expected: `PASSED`

- [ ] **Step 5: Commit**

```bash
git add backend/app/api/v1/extraction.py backend/tests/test_search_fixes.py
git commit -m "fix: clear ReferenceIndex entries when document is rejected"
```

---

## Task 2: pg_trgm fuzzy index migration

**Context:** Search uses `ILIKE '%query%'` which fails on single-character OCR errors (e.g. `INV-2024-OO1` vs `INV-2024-001`). PostgreSQL's `pg_trgm` extension enables similarity-based matching. This task creates the extension and index. Task 3 uses it in queries.

**Files:**
- Create: `backend/alembic/versions/g9h0i1j2k3l4_add_pg_trgm_index.py`

- [ ] **Step 1: Create migration file**

Create `backend/alembic/versions/g9h0i1j2k3l4_add_pg_trgm_index.py`:

```python
"""add_pg_trgm_fuzzy_index

Revision ID: g9h0i1j2k3l4
Revises: f7a8b9c0d1e2
Create Date: 2026-04-08

Enables pg_trgm extension and adds GIN index on reference_index.ref_value
for similarity-based fuzzy search. Safe to apply on a live DB — read-only
addition, no data is modified.
"""
from alembic import op

revision = 'g9h0i1j2k3l4'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable trigram extension (requires superuser on first run, safe to re-run)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # GIN index for fast similarity queries on ref_value
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ref_value_trgm "
        "ON reference_index USING GIN (ref_value gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ref_value_trgm")
    # Note: do NOT drop the pg_trgm extension — other parts of the DB may depend on it
```

- [ ] **Step 2: Run migration**

```bash
cd backend
.\venv\Scripts\Activate.ps1
python -m alembic upgrade head
```

Expected output includes: `Running upgrade f7a8b9c0d1e2 -> g9h0i1j2k3l4, add_pg_trgm_fuzzy_index`

- [ ] **Step 3: Verify index exists**

```bash
python -c "
from app.database import sync_engine
from sqlalchemy import text
with sync_engine.connect() as conn:
    result = conn.execute(text(\"SELECT indexname FROM pg_indexes WHERE tablename='reference_index'\"))
    for row in result:
        print(row[0])
"
```

Expected: output includes `idx_ref_value_trgm`

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/g9h0i1j2k3l4_add_pg_trgm_index.py
git commit -m "feat: add pg_trgm GIN index on reference_index for fuzzy search"
```

---

## Task 3: Fuzzy similarity search in search_service.py

**Context:** With the GIN index from Task 2, we can add similarity-based fallback to the reference search query. The change adds an OR condition: either the existing ILIKE matches OR `similarity(ref_value, query) > 0.3`. Exact/prefix/contains results still rank higher; fuzzy-only matches rank last.

**Files:**
- Modify: `backend/app/services/search_service.py`
- Test: `backend/tests/test_search_fixes.py` (add test class)

- [ ] **Step 1: Write failing test**

Add to `backend/tests/test_search_fixes.py`:

```python
class TestFuzzySearchFallback:
    """Similarity search returns results for near-matches."""

    def test_sort_key_fuzzy_match_ranks_last(self):
        """Fuzzy-only matches (no substring) should rank below contains matches."""
        from app.services.search_service import _search_sort_key

        exact    = {"ref_number": "INV-2024-001"}
        prefix   = {"ref_number": "INV-2024-001-A"}
        contains = {"ref_number": "REF-INV-2024-001-X"}
        fuzzy    = {"ref_number": "INV-2024-OO1"}  # two letter-O OCR error

        q = "inv-2024-001"
        assert _search_sort_key(exact, q)    == 0
        assert _search_sort_key(prefix, q)   == 1
        assert _search_sort_key(contains, q) == 2
        assert _search_sort_key(fuzzy, q)    == 3
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
pytest tests/test_search_fixes.py::TestFuzzySearchFallback -v
```

Expected: `FAILED — ImportError: cannot import name '_search_sort_key'`

- [ ] **Step 3: Extract sort key and add fuzzy OR in search_service.py**

In `backend/app/services/search_service.py`, make these two changes:

**Change A** — add `func` and `or_` to the existing import at the top:
```python
from sqlalchemy import select, or_, func, cast, Text
```
(It already imports `or_` and `func` — confirm they're there. If `func` is missing, add it.)

**Change B** — extract sort key as a module-level function (add above `global_search`):
```python
def _search_sort_key(item: dict, q_lower: str) -> int:
    """Rank: 0=exact, 1=starts-with, 2=contains, 3=fuzzy-only."""
    ref = (item["ref_number"] or "").lower()
    if ref == q_lower:
        return 0
    elif ref.startswith(q_lower):
        return 1
    elif q_lower in ref:
        return 2
    return 3
```

**Change C** — in `global_search`, replace the ref_stmt `.where()` clause:

Old (single condition):
```python
.where(ReferenceIndex.ref_value.ilike(pattern))
```

New (ILIKE OR similarity):
```python
.where(
    or_(
        ReferenceIndex.ref_value.ilike(pattern),
        func.similarity(ReferenceIndex.ref_value, query) > 0.3,
    )
)
```

**Change D** — replace the inline `sort_key` function inside `global_search` with a call to the new module-level one:

Old:
```python
def sort_key(item):
    ref = (item["ref_number"] or "").lower()
    if ref == q_lower:
        return 0
    elif ref.startswith(q_lower):
        return 1
    else:
        return 2

results.sort(key=sort_key)
```

New:
```python
results.sort(key=lambda item: _search_sort_key(item, q_lower))
```

- [ ] **Step 4: Run tests — expect PASS**

```bash
pytest tests/test_search_fixes.py -v
```

Expected: both `TestRejectClearsReferenceIndex` and `TestFuzzySearchFallback` PASS

- [ ] **Step 5: Manual smoke test**

With the dev server running:
```bash
# Should return result even with O vs 0 mismatch in ref number
curl "http://localhost:8000/api/v1/search?q=INV-2024-OO1"
```

Expected: JSON response with `results` array (may be empty if no matching docs, but no 500 error).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/search_service.py backend/tests/test_search_fixes.py
git commit -m "feat: add pg_trgm similarity fallback to reference search"
```

---

## Task 4: Deep-link document card from search result

**Context:** Clicking a document in search results currently navigates to the parent PO root. The user lands at the top and must scan to find the document. This task passes `?highlight=<doc_id>` in the URL, which PODetailPage reads to scroll to and briefly highlight the correct DocumentCard.

**Files:**
- Modify: `frontend/src/pages/SearchPage.tsx`
- Modify: `frontend/src/pages/PODetailPage.tsx`
- Modify: `frontend/src/components/DocumentCard.tsx`

### Sub-task 4a: Add id + highlighted prop to DocumentCard

- [ ] **Step 1: Add `highlighted` prop and `id` attribute to DocumentCard**

In `frontend/src/components/DocumentCard.tsx`, update the `Props` interface and the root `<div>`:

```tsx
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
  onEdit?: (documentId: string) => void;
  showLabel?: boolean;
  docIndex?: number;
  highlighted?: boolean;   // ← add this
}
```

Update the destructured props to include `highlighted = false`:
```tsx
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
  onEdit,
  showLabel = true,
  docIndex,
  highlighted = false,   // ← add this
}: Props) {
```

Update the root `<div>` (line ~55) to add `id` and highlight ring:
```tsx
  return (
    <div
      id={slot?.document_id ?? undefined}
      className={clsx(
        'rounded-lg border-2 p-4 transition-all cursor-pointer',
        borderColor,
        isSelected && 'ring-2 ring-blue-500 shadow-md',
        highlighted && 'ring-2 ring-yellow-400 shadow-lg',
        status !== 'empty' && 'hover:shadow-sm'
      )}
```

### Sub-task 4b: Scroll and highlight in PODetailPage

- [ ] **Step 2: Read highlight param and scroll to card in PODetailPage**

In `frontend/src/pages/PODetailPage.tsx`, update the imports:

```tsx
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
```

Add `useSearchParams` call (after existing `useParams` line):
```tsx
const { id } = useParams<{ id: string }>();
const [searchParams] = useSearchParams();
const highlightDocId = searchParams.get('highlight');
```

Add a `useEffect` that scrolls once chainData is loaded (add after the existing `useEffect` for extraction polling):
```tsx
useEffect(() => {
  if (!highlightDocId || !chainData) return;
  const el = document.getElementById(highlightDocId);
  if (el) {
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }
}, [highlightDocId, chainData]);
```

Pass `highlighted` to each `DocumentCard` in the render (both the empty-card and the slots.map render):
```tsx
<DocumentCard
  key={slot.document_id ?? `${docType}-${idx}`}
  documentType={docType}
  slot={slot}
  isSelected={selectedDocId != null && slot.document_id === selectedDocId}
  highlighted={slot.document_id === highlightDocId}   // ← add this line
  onSelect={(docId) => setSelectedDocId(docId)}
  onUpload={() => setUploadType(docType)}
  onReview={(docId) => setReviewDocId(docId)}
  onReExtract={handleReExtract}
  onDelete={handleDelete}
  onManualEntry={handleManualEntry}
  onEdit={(docId) => setEditDocId(docId)}
  showLabel={idx === 0}
  docIndex={slots.length > 1 ? idx + 1 : undefined}
/>
```

### Sub-task 4c: Pass highlight param from SearchPage

- [ ] **Step 3: Update handleResultClick in SearchPage**

In `frontend/src/pages/SearchPage.tsx`, update the document case in `handleResultClick`:

```tsx
const handleResultClick = (result: SearchResult) => {
  switch (result.result_type) {
    case 'customer':
      navigate(`/purchase-orders?customer_id=${result.id}`);
      break;
    case 'purchase_order':
      navigate(`/purchase-orders/${result.id}`);
      break;
    case 'document':
      if (result.po_id) {
        navigate(`/purchase-orders/${result.po_id}?highlight=${result.id}`);
      }
      break;
  }
};
```

- [ ] **Step 4: Manual smoke test**

1. Start dev server
2. Upload and extract any document
3. Go to `/search`, search by the document's reference number
4. Click the result card
5. Expected: navigates to PO detail page, document card is scrolled into view with yellow ring

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/DocumentCard.tsx \
        frontend/src/pages/PODetailPage.tsx \
        frontend/src/pages/SearchPage.tsx
git commit -m "feat: deep-link from search result to highlighted document card"
```

---

## Task 5: Advanced search filter panel

**Context:** The backend `/api/v1/search/advanced` already accepts: `invoice_no`, `dc_no`, `po_no`, `so_no`, `customer_name`, `document_type`, `date_from`, `date_to`. The `advancedSearch()` API function in `search.ts` is also already implemented. Only the frontend hook and UI panel are missing.

**Files:**
- Modify: `frontend/src/hooks/useSearch.ts`
- Modify: `frontend/src/pages/SearchPage.tsx`

### Sub-task 5a: Add useAdvancedSearch hook

- [ ] **Step 1: Add useAdvancedSearch to useSearch.ts**

In `frontend/src/hooks/useSearch.ts`, add after the existing `useAddressSearch`:

```typescript
export function useAdvancedSearch(
  params: {
    invoice_no?: string;
    dc_no?: string;
    po_no?: string;
    so_no?: string;
    customer_name?: string;
    document_type?: string;
    date_from?: string;
    date_to?: string;
  },
  enabled: boolean
) {
  return useQuery({
    queryKey: ['advancedSearch', params],
    queryFn: () => advancedSearch(params),
    enabled,
  });
}
```

Add `advancedSearch` to the import at the top:
```typescript
import { globalSearch, advancedSearch } from '@/api/search';
```
(It may already be there — check before adding.)

### Sub-task 5b: Add filter panel to SearchPage

- [ ] **Step 2: Add filter state and advanced search logic to SearchPage**

In `frontend/src/pages/SearchPage.tsx`, add state for advanced filters (after existing `useState` declarations):

```tsx
const [showAdvanced, setShowAdvanced] = useState(false);
const [advFilters, setAdvFilters] = useState({
  invoice_no: '',
  dc_no: '',
  po_no: '',
  so_no: '',
  customer_name: '',
  document_type: '',
  date_from: '',
  date_to: '',
});
const [advQuery, setAdvQuery] = useState<typeof advFilters | null>(null);

const hasAdvancedFilters = advQuery !== null;

const { data: advData, isLoading: advLoading } = useAdvancedSearch(
  advQuery ?? {},
  advQuery !== null
);
```

Add the import for `useAdvancedSearch`:
```tsx
import { useSearch, useAddressSearch, useAdvancedSearch } from '@/hooks/useSearch';
```

- [ ] **Step 3: Add the advanced filter panel UI**

In `SearchPage.tsx`, inside the `tab === 'global'` block, add the collapsible filter panel directly after the main search `<form>`:

```tsx
{/* Advanced filters toggle */}
<div className="mb-4">
  <button
    type="button"
    onClick={() => setShowAdvanced((v) => !v)}
    className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
  >
    {showAdvanced ? '▲ Hide advanced filters' : '▼ Advanced filters'}
  </button>
</div>

{showAdvanced && (
  <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 mb-6 space-y-3">
    <div className="grid grid-cols-2 gap-3">
      {[
        { label: 'Invoice No', key: 'invoice_no' },
        { label: 'DC No', key: 'dc_no' },
        { label: 'PO No', key: 'po_no' },
        { label: 'SO No', key: 'so_no' },
        { label: 'Customer', key: 'customer_name' },
      ].map(({ label, key }) => (
        <div key={key}>
          <label className="block text-xs text-gray-500 mb-1">{label}</label>
          <input
            type="text"
            value={advFilters[key as keyof typeof advFilters]}
            onChange={(e) =>
              setAdvFilters((f) => ({ ...f, [key]: e.target.value }))
            }
            className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
          />
        </div>
      ))}
      <div>
        <label className="block text-xs text-gray-500 mb-1">Document Type</label>
        <select
          value={advFilters.document_type}
          onChange={(e) =>
            setAdvFilters((f) => ({ ...f, document_type: e.target.value }))
          }
          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        >
          <option value="">All types</option>
          <option value="CUSTOMER_PO">Customer PO</option>
          <option value="COMPANY_PO">Company PO</option>
          <option value="VENDOR_DC">Vendor DC</option>
          <option value="VENDOR_INVOICE">Vendor Invoice</option>
          <option value="COMPANY_DC">Company DC</option>
          <option value="COMPANY_INVOICE">Company Invoice</option>
        </select>
      </div>
    </div>
    <div className="grid grid-cols-2 gap-3">
      <div>
        <label className="block text-xs text-gray-500 mb-1">Date from</label>
        <input
          type="date"
          value={advFilters.date_from}
          onChange={(e) =>
            setAdvFilters((f) => ({ ...f, date_from: e.target.value }))
          }
          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-1">Date to</label>
        <input
          type="date"
          value={advFilters.date_to}
          onChange={(e) =>
            setAdvFilters((f) => ({ ...f, date_to: e.target.value }))
          }
          className="w-full border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </div>
    </div>
    <div className="flex gap-2 pt-1">
      <button
        type="button"
        onClick={() => {
          const active = Object.fromEntries(
            Object.entries(advFilters).filter(([, v]) => v.trim() !== '')
          );
          if (Object.keys(active).length > 0) setAdvQuery(active as typeof advFilters);
        }}
        className="bg-blue-600 text-white text-sm px-4 py-1.5 rounded-lg hover:bg-blue-700"
      >
        Search
      </button>
      <button
        type="button"
        onClick={() => {
          setAdvFilters({ invoice_no: '', dc_no: '', po_no: '', so_no: '', customer_name: '', document_type: '', date_from: '', date_to: '' });
          setAdvQuery(null);
        }}
        className="text-gray-500 text-sm px-4 py-1.5 rounded-lg border border-gray-300 hover:bg-gray-100"
      >
        Clear
      </button>
    </div>
  </div>
)}
```

- [ ] **Step 4: Show advanced search results**

In `SearchPage.tsx`, inside `tab === 'global'`, replace the results block. When `hasAdvancedFilters` is true, show `advData` instead of `data`. Add this conditional just before the results render:

```tsx
const displayData = hasAdvancedFilters ? advData : data;
const displayLoading = hasAdvancedFilters ? advLoading : isLoading;
```

Then replace `data && !isLoading` with `displayData && !displayLoading`, and `data.results` with `displayData.results`, and `data.total` / `data.query` with `displayData.total` / `displayData.query`.

- [ ] **Step 5: Manual smoke test**

1. Start frontend dev server (`npm run dev`)
2. Go to `/search`
3. Click "▼ Advanced filters" — panel expands
4. Enter a document type and click Search
5. Expected: results filtered by document type appear below
6. Click Clear — results reset

- [ ] **Step 6: Commit**

```bash
git add frontend/src/hooks/useSearch.ts frontend/src/pages/SearchPage.tsx
git commit -m "feat: expose advanced search filter panel in search page UI"
```

---

## Final Smoke Test

- [ ] **Run all backend tests**

```bash
cd backend
pytest tests/test_search_fixes.py -v
```

Expected: 2 test classes, all PASS

- [ ] **Manual end-to-end check**

1. Upload and extract a document
2. In ReviewModal, correct a reference number and verify → search for corrected value → appears in results ✅
3. Reject a different document → search for its reference number → no longer appears ✅
4. Search for a reference with 1-character OCR error (O vs 0) → still finds the document ✅
5. Click document result → scrolls to highlighted yellow card on PO detail page ✅
6. Use advanced filters (invoice_no + customer_name) → filtered results ✅
