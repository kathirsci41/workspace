# UX Overhaul Design Spec
**Date:** 2026-04-09  
**Status:** Approved — ready for implementation planning  
**Branches:** `feature/ux-quick-wins` (ships first) → `feature/page-redesigns` (ships after)

---

## Goals

Complete UX pass over all 8 existing pages before building the Intelligence/Chat page. Two objectives:
1. Fix all known friction points — dead clicks, missing feedback, confusing navigation
2. Add 13 selected feature enhancements — without changing the visual identity

---

## Visual Direction

**Hybrid** — keep existing white/gray/blue Tailwind palette. Improve data density: card grids instead of plain key-value lists, tighter spacing, stronger visual hierarchy between primary and secondary information. No gradients, no palette changes. Pages should feel like a natural evolution, not a redesign.

---

## Branch 1 — `feature/ux-quick-wins`

All fixes and enhancements across 6 pages + global. Ships first.

### 1. AppShell / Navigation

| Change | Detail |
|---|---|
| Rename nav item | "Admin" → "System", swap `Terminal` icon for `Settings2` |
| Sidebar default | Change localStorage default from `true` (collapsed) to `false` (expanded) for first-time visitors |
| Breadcrumbs | New `<Breadcrumb>` component, shown on `PODetailPage` and `POProfilePage`. Format: `Purchase Orders › PO-1045 › Profile` |
| Toast extension | `useToast` already exists on POProfilePage — wire it into all remaining pages: PODetailPage, POListPage, CustomersPage, DocumentsPage |

### 2. Dashboard

| Change | Detail |
|---|---|
| Add total_documents stat card | Currently in `admin/stats` response but not displayed — 5th stat card |
| Make all stat cards clickable | Currently only Pending Reviews scrolls. Total POs → `/purchase-orders`, Customers → `/customers`, Verified → `/documents?status=VERIFIED`, Total Docs → `/documents` |
| Stats with trends | Show delta vs previous day: `↑3 since yesterday`. Requires backend: add `stats_delta` to `GET /api/v1/admin/stats` (compare today vs yesterday count from DB) |
| Document status donut | Small SVG/CSS donut chart below the stat cards showing proportion of Verified / Pending / Failed / Extracting. Data from existing stats response. No chart library — pure CSS conic-gradient |
| Quick action bar | Row of 3 buttons below donut: `+ Create PO` (opens modal), `↑ Upload Document` (navigates to PO list with upload intent), `⏱ Review Pending (N)` (scrolls to queue). Replaces the current dead-space above the review queue |
| SLA aging alerts | New section above review queue: documents in PENDING_REVIEW for ≥ 3 days get a red badge. Backend: add `days_pending` field to document list response (calculated from `updated_at`). Frontend: highlight rows where `days_pending >= 3` with a red `⚠ N days` badge. Threshold hardcoded at 3 days (configurable later via admin setting) |
| Review queue deep-link | Change "Open PO" button to navigate `/purchase-orders/:po_id?highlight=:doc_id&review=:doc_id`. PODetailPage reads `?review=docId` on mount and auto-opens the ReviewModal for that document |

### 3. PO List

| Change | Detail |
|---|---|
| Fix chain bar size | Change `max-w-[80px]` to `max-w-[120px]` on the chain completeness progress bar |
| Fix customer name spacing | Change `` `${po.customer_sky_id ?? ''} ${po.customer_name}` `` to `` `${po.customer_sky_id ? `${po.customer_sky_id} ` : ''}${po.customer_name}` `` |

### 4. Documents Page

| Change | Detail |
|---|---|
| Add ref number column | New column "Ref No" showing `doc.primary_ref_no` from metadata. Position: after Filename, before PO Number |
| Direct Review action | On rows where `doc.status === 'PENDING_REVIEW'`, show a "Review →" button in the actions column that navigates to `/purchase-orders/:po_id?highlight=:doc_id&review=:doc_id` |

### 5. Search Page

| Change | Detail |
|---|---|
| Tab state in URL | Persist `tab` as a URL param: `?tab=address`. Read on mount to restore tab |
| Advanced filter URL state | Persist active `advQuery` fields as URL params when Search is clicked. Allows sharing a filtered search URL |

### 6. PO Detail Page

| Change | Detail |
|---|---|
| Chain complete banner | When `chainData.completeness === 100`, show a green banner below the chain status bar: "All documents complete — View Profile →". Banner is dismissible per-session (localStorage key) |
| Clearer upload affordance | Empty `DocumentCard` slots: add a dashed border + larger upload target area. Current "Upload Document" text link is too subtle |
| Auto-open review from URL | Read `?review=docId` on mount, set `reviewDocId` to that value so ReviewModal opens immediately (used by Dashboard deep-link and Documents page Review button). Note: `?review` opens the modal; `?highlight` scrolls + opens preview panel — two distinct params, both can be present simultaneously |
| Auto-open preview from search | Initialize `selectedDocId` state from `searchParams.get('highlight')` instead of `null`. Means arriving from search auto-opens the PDF preview panel for the matched document. Only applies when navigating to PODetailPage directly — search results for documents now go to `/documents/:id` instead |

### 7. Review Modal — Keyboard Shortcuts

Add `useEffect` with `keydown` listener when modal is open:
- `V` → trigger Verify action
- `R` → trigger Reject action  
- `Escape` → close modal

Show keyboard hint in modal footer: `V verify · R reject · Esc close`

### 8. Global — Empty States

Replace all "No results found." / "Loading..." dead ends with guided empty states:

| Page | Empty state message + CTA |
|---|---|
| PO List | "No purchase orders yet — Create your first PO +" |
| Customers | "No customers yet — Add a customer +" |
| Documents | "No documents match these filters — Reset filters" |
| Search | "No results. Try a shorter search term or use Advanced filters" |
| Dashboard review queue | "No documents pending review ✓" (green, positive) |
| Admin failures | Already has this ✓ — keep as-is |

### 9. New Page — Document Detail (`/documents/:id`)

**Route:** `/documents/:id`  
**Component:** `DocumentDetailPage.tsx`  
**Navigation:** Search result clicks for `result_type === 'document'` navigate here instead of `/purchase-orders/:po_id?highlight=:id`

**Layout:** Two-panel split (PDF left, data right), full viewport height

**Header bar** (full width):
- Breadcrumb: `Purchase Orders › [po_number] › [document_type_label]` — dynamic from loaded document data
- Document title (ref number), status badge, alert count badge (e.g. "⚠ 2 cross-check alerts"), confidence + extraction route badges
- Actions: Re-extract, Edit Fields, Download, "Open in PO →"

**Left panel — PDF Viewer:**
- Reuse existing `PDFPreviewPanel` component
- Page navigation controls (Prev / Next / page count)

**Right panel — 4 stacked sections:**

1. **Extracted Fields** — 2-column card grid. Each field in a `bg-gray-50` rounded card showing label + value. Fields sourced from `DocumentMetadata.extracted_data`. Highlight cards in amber if that field has a cross-check discrepancy.

2. **Cross-check Alerts** (amber background, shown only if discrepancies exist):
   - Data source: `GET /api/v1/purchase-orders/:po_id/profile` → filter `discrepancies` and `field_comparisons` arrays by this document's ID
   - Each alert is a card showing: alert type, the two conflicting values side-by-side, difference/explanation
   - Actionable: "Upload Vendor DC →", "Edit field →" buttons where applicable
   - If no alerts: section is hidden entirely

3. **Extraction Checks** — compact checklist of field-level validation results from `_validation_errors` in extracted_data. Green ✓ for passing, amber ⚠ for warnings.

4. **Parent PO** — `bg-blue-50` card with PO number + customer name + "View full PO →" link. Always visible at the bottom.

**API calls needed:**
- `GET /api/v1/documents/:id` — document + metadata (already exists)
- `GET /api/v1/documents/:id/preview` — PDF blob (already exists)  
- `GET /api/v1/purchase-orders/:po_id/profile` — for cross-check alerts (already exists, filter client-side)

---

## Branch 2 — `feature/page-redesigns`

Structural redesigns for Customers and PO Profile. Ships after Branch 1.

### 1. Customers List — Redesign

**Column changes:**
- Remove: GST Number, Email (almost always blank — move to detail page)
- Add: PO Count (integer), Total Value (₹ sum), Chain Health % (avg chain_completeness across POs)
- Keep: Customer ID, Name, Created date

**Row click affordance:**
- Add a `›` chevron at the end of each row
- Change destination: `/customers/:id` (new detail page) instead of `/purchase-orders?customer_id=X`
- Add `title` tooltip: "Click to view customer details"

**Customer detail page remains accessible** from the detail page itself with a "View all POs →" link.

### 2. New Page — Customer Detail (`/customers/:id`)

**Route:** `/customers/:id`  
**Component:** `CustomerDetailPage.tsx`

**Layout:** Single column, max-w-4xl

**Section 1 — Summary header:**
- Customer name (large), Customer ID badge, GST number
- 3 stat cards: Total POs, Total Order Value (₹), Avg Chain Completeness %
- Actions: Edit Customer (opens modal), "View all POs →"

**Section 2 — Recent Purchase Orders:**
- Table showing last 10 POs: PO Number, Date, Amount, Chain %, Status
- Row click → `/purchase-orders/:id`
- "View all →" link to `/purchase-orders?customer_id=X`

**Section 3 — Contact & Details panel:**
- Email, GST, address (if available)
- "Edit →" inline

**API calls:**
- `GET /api/v1/customers/:id` — already exists
- `GET /api/v1/customers/:id/purchase-orders` — already exists

### 3. PO Profile — Redesign

**Sticky section navigation:**
- Fixed left sidebar (visible on ≥ lg screens), `w-40`, lists all sections as jump-links
- Sections: Overview, Discrepancies, Field Checks, Items, Vendors, Documents, Timeline
- Active section highlighted as user scrolls (IntersectionObserver)
- On mobile: replaced by a horizontal pill row at the top

**Header restructure:**
Split the current dense 5-row header into two logical rows:

- **Row 1 — Identity:** PO number, status badge, completeness %, customer, SO number, PO date, amount, Export + Close Order buttons
- **Row 2 — Settings (collapsible):** Scenario selector, GST type, invoice split, items verified toggle. Collapsed by default, expandable with "⚙ Order Settings" toggle. Scenario selector gets a larger pill style (it drives chain logic — needs visual prominence)

**Scenario selector prominence:**
Current pill row blends in with GST/invoice controls. New design: scenario selector gets its own labeled row with slightly larger pills and a subtle description of what the selected scenario means (e.g., "Procurement: all 6 document types required").

**Side-by-side document comparison:**
- "Compare" button in the Documents section header
- Opens a drawer/modal: two dropdowns to select any two documents from the PO
- Side-by-side table of their extracted fields with match/mismatch highlighting
- Reuses field data already loaded in profile

**Print / PDF export:**
- "Print Profile" button in header (alongside existing Export Excel)
- Triggers `window.print()` with a dedicated `@media print` stylesheet
- Print layout: hides sidebar nav, actions, and interactive controls; expands all collapsed sections; formats as clean A4 document

**Collapsible sections:**
- Each section (Discrepancies, Items, Vendors, etc.) has a collapse toggle
- State persisted in `localStorage` per PO ID
- Collapsed sections show a 1-line summary (e.g., "3 discrepancies — click to expand")

---

## Search Navigation Change (Branch 1)

`handleResultClick` in `SearchPage.tsx`:

```ts
case 'document':
  // OLD: navigate(`/purchase-orders/${result.po_id}?highlight=${result.id}`)
  // NEW:
  navigate(`/documents/${result.id}`);
  break;
```

The Document Detail page handles the "Open in PO →" link back to the parent PO.

---

## Backend Changes Required

| Change | Endpoint | Work |
|---|---|---|
| Stats delta | `GET /api/v1/admin/stats` | Add yesterday comparison query |
| Days pending | `GET /api/v1/documents` list items | Add `days_pending` computed field |
| Review auto-open | No change — frontend only | — |
| Document detail | `GET /api/v1/documents/:id` | Already exists |
| Customer detail | `GET /api/v1/customers/:id` | Already exists |

---

## Component Reuse

| New need | Existing component |
|---|---|
| PDF viewer in DocDetail | `PDFPreviewPanel` — reuse as-is |
| Review actions in DocDetail | `ReviewModal` — reuse as-is |
| Chain status in CustomerDetail | `ChainStatusBar` — reuse as-is |
| Cross-check display | `ProfileDiscrepancyPanel` — filter by doc ID, render inline |

---

## Out of Scope (deferred to Intelligence page or Phase 2)

- Autocomplete in inline search
- Notification bell
- Bulk re-extract
- Saved filter presets
- Dark mode
