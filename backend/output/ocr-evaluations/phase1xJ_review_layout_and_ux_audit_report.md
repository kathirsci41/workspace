# Phase 1xJ — Review Layout & UX Audit Report

**Date:** 2026-06-14  
**Phase:** 1xJ  
**Focus:** Extraction Review split-pane layout fix + application-wide UX audit

---

## 1. Objectives

**Part A — Extraction Review split-pane layout**  
Fix the Extraction Review page so the PDF remains visible while the fields panel scrolls independently. The whole page was previously scrolling as one unit, meaning the PDF would scroll out of view as users reviewed fields.

**Parts B+C — Application-wide UX audit**  
Audit all 9 app pages for low-risk UX issues (spacing, labels, helper text, empty states, button copy, table readability, status badges). Fix only targeted, safe issues.

**Parts D — Per-page checks**  
Verify each page renders correctly, key information is accessible, and navigation is clear.

**Part E — Playwright headed screenshots**  
10 screenshots of all pages in the running app.

**Part F — Frontend test suite**  
All vitest tests must pass.

**Part G — This report.**

---

## 2. Part A — Extraction Review Split-Pane Layout

### Problem

The Extraction Review page used a CSS grid with `align-items: start` and no height constraint. The entire page scrolled as one unit — as users scrolled to review extracted fields, the PDF preview scrolled out of view.

**Before:**
```css
.review-grid {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) minmax(380px, 420px);
  gap: 16px;
  align-items: start;   /* columns sized to content, page scrolls as one unit */
}
```

### Fix

Made the grid height-constrained to the viewport, with each column scrolling independently:

**`.review-grid`** — added `height: calc(100vh - 210px)` (accounting for sticky topbar 57px + workspace-header 76px + workflow-tabs ~53px + gaps) and `overflow: hidden`. Removed `align-items: start` to restore default `stretch` behavior so columns fill the full grid height.

**`.document-selector-panel`** — added `overflow-y: auto; min-height: 0` so the left selector panel scrolls if content exceeds height.

**`.preview-panel`** — added `display: flex; flex-direction: column; min-height: 0; overflow: hidden` to make it a flex container that the `.pdf-pane` section can fill.

**`.pdf-pane`** (new rule) — `display: flex; flex-direction: column; height: 100%; min-height: 0` so the viewport fills the available panel height after the toolbar.

**`.pdf-pane__viewport`** — changed `min-height: 800px` → `min-height: 200px`, removed `max-height: calc(100vh - 215px)`, added `flex: 1`. The flex approach allows the viewport to fill exactly the space remaining after the PDF toolbar, without hard-coded height arithmetic.

**`.fields-panel-wrap`** — added `overflow-y: auto; min-height: 0` so extracted fields scroll independently.

### Playwright confirmation

```
review-grid height: 510px, viewport: 720px
```

The grid height (510px) is less than the viewport height (720px) — the grid is correctly contained within the viewport. Both PDF pane and fields pane are visible simultaneously without any page scroll.

### Helper text added

Added a small hint above the extracted fields panel:

> "Click a field name to locate it in the PDF."

Playwright confirmed: `Helper text visible: Click a field name to locate it in the PDF.`

CSS: `.fields-hint { margin: 0 0 12px; font-size: 12px; color: #64748b; }`

---

## 3. Parts B+C — UX Audit Findings

### Pages audited

| Page | Status | Issues found | Action |
|---|---|---|---|
| Bundles | OK | — | No change |
| Bundle Overview | OK | — | No change |
| Documents | OK | — | No change |
| Extraction Review | Fixed | Split-pane not working; no hint text | Fixed (Part A) |
| Verification | OK | — | No change |
| Issues | Acceptable | Disabled "Status" always-Open dropdown | Deferred (cosmetic) |
| Audit Trail | OK | — | No change |
| Exports | Fixed | Trailing "No export history available" empty state | Removed |
| Health | OK | — | No change |

### Fix 1 — Exports page: remove useless empty state

The Exports page ended with:
```tsx
<section className="panel">
  <EmptyState title="No export history available">
    The backend does not expose an export history endpoint.
  </EmptyState>
</section>
```

This is a backend-limitation disclosure that reads as an error state — confusing to users who have just successfully exported. Removed the section and the now-unused `EmptyState` import.

Playwright confirmed: `expect(page.getByText('No export history available').count()).toBe(0)` — passes.

### Issues page — deferred

The Issues page has a `<select disabled value="Open">` Status filter. This is cosmetically odd (a disabled filter that does nothing) but accurately reflects that there is no issue-resolution workflow in this version. Changing it would require either removing the filter entirely (and updating the layout) or adding close/resolve functionality — both out of scope for this phase.

### No other low-risk changes found

All other pages are structurally sound. Status badges are consistent, table readability is good, button copy is clear, and navigation through WorkflowTabs is accessible.

---

## 4. Part D — Per-Page Check Results

| Page | PDF visible | Fields scroll | Navigation clear | Key info accessible | Result |
|---|---|---|---|---|---|
| Bundles | N/A | N/A | "Create Bundle" prominent | KPI cards, filter/sort, paginated table | OK |
| Bundle Overview | N/A | N/A | WorkflowTabs, "Next Action" CTA | Outcome card, KPIs, doc inventory | OK |
| Documents | N/A | N/A | "Upload Document" prominent | 5-slot grid, extraction status per slot | OK |
| Extraction Review | Yes (split-pane fixed) | Yes (fields panel) | WorkflowTabs, "Re-extract" | Groups A/B/C, source badges, highlight | Fixed |
| Verification | N/A | N/A | Segmented filter tabs, check detail | Check grouping, left/right values, explanation | OK |
| Issues | N/A | N/A | Severity/document/category filters | Issue cards → detail panel, severity pills | OK |
| Audit Trail | N/A | N/A | Event type/document filters | Timeline → correction detail, before/after table | OK |
| Exports | N/A | N/A | "Download Excel Report" prominent | Readiness panel, report preview table | Fixed |
| Health | N/A | N/A | Standalone page | Backend status, OCR provider info | OK |

---

## 5. Part E — Screenshots

10 screenshots captured in `backend/output/e2e-runs/phase1xJ_ux_audit/screenshots/`:

| File | Description |
|---|---|
| `01_bundles_page.png` | Bundles work queue with KPI cards, filter/sort controls, bundle table |
| `02_bundle_overview.png` | Bundle workspace with outcome card, KPI grid, document inventory |
| `03_documents_page.png` | Documents page with 5-slot upload grid and KPI cards |
| `04_extraction_review_split_pane.png` | Extraction Review with PDF left, scrollable fields right — split-pane fix confirmed |
| `05_extraction_review_field_highlight.png` | Extraction Review with amber highlight overlay over field location in PDF |
| `06_verification_page.png` | Review Results page with grouped checks and detail panel |
| `07_issues_page.png` | Open Issues page with action queue and issue detail panel |
| `08_audit_trail.png` | Manual Correction History with timeline and correction detail |
| `09_exports_page.png` | Exports page with readiness panel and download button (no stale empty state) |
| `10_health_page.png` | Health page with backend status and OCR provider details |

All 10 Playwright tests passed in 24.1 seconds.

---

## 6. Part F — Frontend Test Results

```
Test Files: 10 passed (10)
Tests:      60 passed (60)
Duration:   6.41s
```

All pre-existing tests continue to pass. No regressions introduced by the layout or UX changes.

---

## 7. Files Modified

| File | Change |
|---|---|
| `frontend/src/index.css` | `.review-grid` height + overflow constraint; `.document-selector-panel` scroll; added `.pdf-pane` flex rule; `.pdf-pane__viewport` flex:1 + removed hard min/max-height; `.preview-panel` flex column; `.fields-panel-wrap` scroll; added `.fields-hint` style |
| `frontend/src/pages/ExtractionReviewPage.tsx` | Added `.fields-hint` helper text above ExtractedFieldsPanel |
| `frontend/src/pages/ExportsPage.tsx` | Removed "No export history available" empty state section and unused import |
| `frontend/e2e/phase1xJ-ux-audit.spec.ts` | New Playwright spec: 10 UX audit screenshots covering all app pages |

---

## 8. Before / After — Extraction Review Layout

### Before
- `.review-grid { align-items: start }` → columns sized to content
- `.pdf-pane__viewport { min-height: 800px; max-height: calc(100vh - 215px) }` → viewport constrained but panel not
- Whole page scrolled as one unit
- PDF scrolled off screen when reviewing fields below the fold
- No hint text explaining field-click behavior

### After
- `.review-grid { height: calc(100vh - 210px); overflow: hidden }` → grid stays within viewport
- `.preview-panel { display: flex; flex-direction: column }` + `.pdf-pane { height: 100% }` + `.pdf-pane__viewport { flex: 1 }` → viewport fills available panel height
- `.fields-panel-wrap { overflow-y: auto }` → extracted fields scroll independently
- PDF stays fixed on left while fields scroll on right
- Helper text: "Click a field name to locate it in the PDF."

---

## 9. Feature Verification — PDF Highlight Still Works

Playwright confirmed highlight overlay after split-pane fix:
```
Highlight overlay bounds: {
  x: 393.33, y: 612.40, width: 84.40, height: 11.58
}
```

The amber highlight overlay is correctly positioned over the field location in the PDF even with the new flex-based layout. No change to `PdfPreviewPane.tsx` or highlight logic was required.

---

## 10. Final Verdict

| Criterion | Status |
|---|---|
| PDF stays visible while reviewing fields | ✅ Confirmed (review-grid height: 510px < viewport: 720px) |
| Fields panel scrolls independently | ✅ `overflow-y: auto` on `.fields-panel-wrap` |
| No whole-page scroll during field review | ✅ Grid `overflow: hidden` |
| Helper text "Click a field name..." visible | ✅ Confirmed by Playwright |
| Field highlight still works after layout change | ✅ Overlay bounds confirmed |
| All frontend tests pass | ✅ 60/60 |
| 10 Playwright screenshots captured | ✅ All 10 tests passed (24.1s) |
| No extraction/verification logic changed | ✅ Backend unmodified |
| No full app redesign | ✅ Only targeted CSS + one JSX hint + one removed section |

**Phase 1xJ complete.** The Extraction Review split-pane layout works. The PDF stays fixed and visible while the extracted fields panel scrolls. Field highlighting is unaffected. All tests pass.
