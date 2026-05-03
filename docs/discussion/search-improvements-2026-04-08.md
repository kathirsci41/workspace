# Search — Pain Points, UX Improvements & Intelligence Possibilities
**Date:** 2026-04-08
**Scope:** Current search page, global_search(), ReferenceIndex, and upgrade path

---

## 1. Current Pain Points

### P1 — Stale search index (Critical)

The `ReferenceIndex` is populated **only during Celery extraction**. Three scenarios silently break it:

| Action | Index updated? | Effect |
|--------|---------------|--------|
| AI extraction completes | ✅ Yes | Searchable |
| Operator corrects a ref number in verify modal | ❌ No | Old (wrong) value still searchable; corrected value invisible |
| Manual entry (model_version = "manual") | ❌ No | Document is entirely invisible to search |
| Document rejected and re-uploaded | ❌ Old entry stays | Deleted document's refs still appear |

Practical example: AI extracts invoice number as `INV-2024-OO1` (two letter O's, should be zeros). Operator corrects it to `INV-2024-001`. Searching `INV-2024-001` returns nothing. Searching `INV-2024-OO1` still returns the document.

---

### P2 — Advanced search backend exists, frontend doesn't expose it

`/api/v1/search/advanced` supports filtering by: `invoice_no`, `dc_no`, `po_no`, `so_no`, `customer_name`, `delivery_address`, `date_from`, `date_to`, `document_type`.

The frontend only uses `delivery_address` from this endpoint (in the Address Search tab). The other 7 parameters are completely unreachable from the UI.

---

### P3 — No fuzzy / typo tolerance

Search is pure `ILIKE '%query%'`. Any character mismatch returns nothing:

```
User types: "INV-2024-OO1"  (letter O instead of zero)
Actual ref: "INV-2024-001"
Result:      No match
```

OCR errors in reference numbers are common. Operators often remember the approximate ref, not the exact string.

---

### P4 — Clicking a document result navigates to the PO, not the document

```python
case 'document':
  navigate(`/purchase-orders/${result.po_id}`)  # ← goes to PO, not the doc
```

The user searched for a specific document but lands on the PO detail page and has to visually scan for it. If the PO has 6 documents, the target card is not highlighted.

---

### P5 — No search from anywhere except /search

The PO list, dashboard, and document pages each have independent filters but no global search bar. If an operator is on the PO detail page and wants to search by invoice number, they have to navigate away to `/search`, losing their place.

---

### P6 — Search returns no status information

A result card shows: document type, PO number, customer name, confidence score. It does **not** show document status (`PENDING_REVIEW` / `VERIFIED` / `REJECTED`). You cannot tell from search results whether a found document still needs attention.

---

### P7 — No debounce — search requires form submit

```typescript
const handleSubmit = (e: React.FormEvent) => {
  e.preventDefault();
  if (input.trim()) setSearchParams({ q: input.trim() });
};
```

The query only fires on Enter / button click. No live results as you type.

---

## 2. UX Improvements (No AI Required)

### U1 — Fix stale index: update ReferenceIndex on verify

In `extraction.py`, the `verify` endpoint saves `extracted_data` to `DocumentMetadata` but never touches `ReferenceIndex`. One change fixes P1:

```
PUT /documents/{id}/metadata/verify
  → save extracted_data to DocumentMetadata  (currently done)
  → DELETE from reference_index WHERE document_id = id
  → re-insert from corrected extracted_data   (add this)
```

Same fix applies to manual entry: after the user fills fields and verifies, populate `ReferenceIndex` from the verified data.

**Impact:** Search results immediately reflect operator corrections.

---

### U2 — Deep-link document results to the document card

Instead of navigating to the PO root, navigate with a hash or query param that auto-scrolls and highlights the target document card:

```
/purchase-orders/{po_id}?highlight={document_id}
```

The PODetailPage already renders document cards by ID — adding scroll-to + highlight CSS is a small frontend change.

---

### U3 — Expose the advanced search UI

The backend is fully built. What's missing is a collapsible "Advanced Filters" panel on the search page:

```
[ Reference Search ] [ Address Search ]

▼ Advanced Filters
  Invoice No: [___________]   DC No:   [___________]
  PO No:      [___________]   SO No:   [___________]
  Customer:   [___________]   Doc Type: [▼ dropdown]
  Date from:  [__/__/____]    Date to:  [__/__/____]
```

Zero backend work needed — the API is already there.

---

### U4 — Add status badge to search results

Each result card already shows document_type, PO number, customer. Add `document.status`:

```
Vendor Invoice — INV-2024-001
VENDOR_INVOICE  |  PO: 1PTR2526000405  |  SKY-002  |  ● Pending Review
```

Operators can immediately see whether the found document needs their attention.

---

### U5 — Global search bar in the layout header

A persistent search input in the AppShell header (top bar) that navigates to `/search?q=...` on submit. Operators never have to leave their current page to start a search.

---

### U6 — Debounce with live results (300ms)

Replace form-submit with a 300ms debounced query:

```typescript
// Replace handleSubmit with:
useEffect(() => {
  const timer = setTimeout(() => {
    if (input.trim().length >= 2) setSearchParams({ q: input.trim() });
  }, 300);
  return () => clearTimeout(timer);
}, [input]);
```

Results appear as the user types, no Enter required.

---

## 3. Efficiency Improvements

### E1 — PostgreSQL trigram index (pg_trgm) for fuzzy matching

Currently: `ILIKE '%query%'` — requires exact substring match, full table scan on large datasets.

With `pg_trgm`:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX idx_ref_value_trgm ON reference_index USING GIN (ref_value gin_trgm_ops);
```

```python
# In search_service.py, replace:
ReferenceIndex.ref_value.ilike(pattern)
# With:
func.similarity(ReferenceIndex.ref_value, query) > 0.3
```

**What this fixes:** Handles OCR errors and typos. `INV-2024-OO1` would match `INV-2024-001` with ~0.85 similarity. No frontend change needed.

---

### E2 — PostgreSQL full-text search (tsvector) for natural language

For customer names and delivery addresses, ILIKE is slow and naive.

```sql
ALTER TABLE reference_index ADD COLUMN ref_tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('english', ref_value)) STORED;
CREATE INDEX idx_ref_tsv ON reference_index USING GIN (ref_tsv);
```

```python
# Search becomes:
ReferenceIndex.ref_tsv.match(query)
```

**What this fixes:** "Chennai Industrial Estate" matches "Chennai industrial" and "industrial estate Chennai". Ranking built in.

---

### E3 — Paginate at DB level, not in Python

Current `global_search()` fetches ALL matching rows from 4 tables into Python memory, deduplicates with a set, then slices:

```python
results = []          # all results in memory
...
total = len(results)  # Python count
paginated = results[start:end]  # Python slice
```

At 10,000 documents this is fine. At 100,000 it's a memory problem. Push `LIMIT/OFFSET` to the DB query level with a `UNION ALL` or a single CTE.

---

## 4. Intelligence Possibilities

### I1 — Autocomplete / typeahead from ReferenceIndex (Quick Win)

```
GET /api/v1/search/suggest?q=INV-2024
→ SELECT DISTINCT ref_value FROM reference_index
  WHERE ref_value ILIKE 'INV-2024%'
  LIMIT 10
→ ["INV-2024-001", "INV-2024-002", "INV-2024-015"]
```

Drop-down suggestions as the user types. No AI required — pure DB query. The `ix_ref_value` index already exists, so prefix queries are fast.

---

### I2 — "Did you mean?" using trigram similarity

When search returns 0 results, find the closest ref in the index:

```python
# If results == []:
SELECT ref_value, similarity(ref_value, :query) AS score
FROM reference_index
ORDER BY score DESC
LIMIT 3
```

Response includes: *"No exact match — did you mean: INV-2024-001, INV-2023-198?"*

Directly addresses OCR error mismatches where the operator searches the correct value but the index has the AI's misread version.

---

### I3 — Cross-document chain view from a single search result

When a document is found, automatically show its chain siblings:

```
Found: Vendor Invoice INV-2024-001
  └── Part of PO: 1PTR2526000405
        ├── COMPANY_PO      ✅ Verified
        ├── VENDOR_DC       ✅ Verified
        ├── VENDOR_INVOICE  ← this document
        ├── COMPANY_DC      ⏳ Pending Review
        └── COMPANY_INVOICE ❌ Missing
```

This is a single query joining `documents` on `po_id`. No AI needed. The backend already has all this data in `get_chain_status()`.

---

### I4 — Duplicate reference detection

When a new document is extracted, check if its reference number already exists in `ReferenceIndex` for a **different PO**. Flag it as a potential duplicate.

```python
# In extraction task, after populating ReferenceIndex:
existing = db.query(ReferenceIndex).filter(
    ReferenceIndex.ref_value == new_ref,
    ReferenceIndex.po_id != current_po_id
).first()
if existing:
    meta.extracted_data["_warnings"] = ["Duplicate reference found in another PO"]
```

Common real-world problem: vendor reuses invoice numbers, or same document uploaded under two different POs.

---

### I5 — Semantic search via embeddings (Phase 2)

For description-level search ("find all invoices for network switches delivered to Chennai before March"):

1. At extraction time: embed `extracted_data` summary using a small embedding model (e.g., `nomic-embed-text` via Ollama)
2. Store vector in `DocumentMetadata.embedding` (pgvector column)
3. At search time: embed the query, find nearest neighbors

```sql
-- pgvector extension
SELECT document_id, extracted_data
FROM document_metadata
ORDER BY embedding <-> query_embedding
LIMIT 10;
```

**Prerequisite:** pgvector PostgreSQL extension + embedding model. Feasible with current hardware (embedding models are tiny, < 300MB).

---

### I6 — Smart alert: missing document detection from search context

If an operator searches for `INV-2024-001` and it exists as a VENDOR_INVOICE, the system could proactively check: *"The PO this belongs to is missing a COMPANY_INVOICE — do you want to upload it now?"*

This turns the search page from passive lookup into an active workflow guide.

---

## Priority Recommendation

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | **U1 — Fix stale index on verify** | Small (1 file) | Critical — correctness |
| 2 | **U2 — Deep-link to document card** | Small (frontend only) | High — daily UX |
| 3 | **U3 — Expose advanced search UI** | Medium (frontend only) | High — backend already built |
| 4 | **E1 — pg_trgm fuzzy index** | Small (migration + 2 lines) | High — OCR error tolerance |
| 5 | **I1 — Autocomplete/typeahead** | Small (1 endpoint) | Medium — discoverability |
| 6 | **U5 — Global search bar in header** | Small (layout change) | Medium — navigation friction |
| 7 | **I3 — Chain view from result** | Medium | High — operator workflow |
| 8 | **I4 — Duplicate detection** | Medium | High — data quality |
| 9 | **E3 — DB-level pagination** | Medium | Low now, critical at scale |
| 10 | **I5 — Semantic search** | Large (Phase 2) | High for complex queries |

---

*Related: `docs/discussion/manual-work-analysis-2026-04-08.md`*
*Related: `docs/architecture/user-flows-2026-04-08.md` — section 8 (Search flows)*
