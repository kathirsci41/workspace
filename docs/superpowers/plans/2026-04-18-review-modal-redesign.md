# Review Modal Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the document review modal so extracted data is easy to read at a glance — read-only card view by default, wider PDF panel, fixed table truncation, edit mode on demand.

**Architecture:** All changes are confined to two frontend files: `ReviewModal.tsx` (layout, read/edit mode toggle, field display) and `OrderItemsTable.tsx` (table scroll fix). No backend changes. No new dependencies. The modal's data hooks, verify/reject mutations, and SO-entry flow are untouched — only presentation changes.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, clsx

---

## Problems being fixed (honest audit)

1. **50/50 PDF:form split** — PDF too small to read; form too cramped.
2. **Wall of inputs** — every field is an `<input>`, no visual hierarchy. Reviewer can't scan quickly.
3. **Delivery locations table truncated** — 11 columns forced into a narrow panel; `CHENNAI` shows as `CHAN`. No proper horizontal scroll.
4. **Read vs edit conflated** — reviewer is forced into edit mode even when just verifying.
5. **Confidence badges hidden** — small left-border colour is easy to miss; low-confidence fields don't stand out.

---

## Files touched

| File | Change |
|------|--------|
| `frontend/src/components/ReviewModal.tsx` | Layout: 60/40 split, full-screen, read/edit mode toggle, card-style field display |
| `frontend/src/components/OrderItemsTable.tsx` | Table: proper `min-width` per column, outer container `overflow-x-auto`, frozen first column |

No new files required.

---

## Task 1: Fix table truncation in OrderItemsTable

**Context:** The delivery locations table has 11 columns (`region`, `unit`, `branch`, `gstin_no`, `asset_description`, `qty`, `employee_code`, `employee_name`, `contact_person`, `contact_no`, `delivery_address`). Currently all columns are forced into whatever width the parent provides. `min-w-[10rem]` on description doesn't help when the table container itself is too narrow. The fix: make the table `min-w-max` so it expands to its natural width, and let the outer `overflow-x-auto` container handle scrolling. Also increase column min-widths for the delivery-specific columns.

**Files:**
- Modify: `frontend/src/components/OrderItemsTable.tsx:36-57` (COL_WIDTHS) and `:78-81` (table element)

- [ ] **Step 1: Update COL_WIDTHS and table element**

In `frontend/src/components/OrderItemsTable.tsx`, replace the COL_WIDTHS object:

```typescript
const COL_WIDTHS: Record<string, string> = {
  sr_no:            'min-w-[2.5rem]',
  part_no:          'min-w-[7rem]',
  description:      'min-w-[14rem]',
  hsn_code:         'min-w-[5rem]',
  qty:              'min-w-[3.5rem]',
  uom:              'min-w-[3.5rem]',
  unit_price:       'min-w-[6rem]',
  total_price:      'min-w-[6rem]',
  serial_numbers:   'min-w-[9rem]',
  // Delivery locations — wider to prevent truncation
  region:           'min-w-[5rem]',
  unit:             'min-w-[4rem]',
  branch:           'min-w-[7rem]',
  gstin_no:         'min-w-[10rem]',
  asset_description:'min-w-[14rem]',
  employee_code:    'min-w-[6rem]',
  employee_name:    'min-w-[12rem]',
  contact_person:   'min-w-[10rem]',
  contact_no:       'min-w-[8rem]',
  delivery_address: 'min-w-[16rem]',
};
```

Then change the `<table>` element from `w-full` to `min-w-max w-full`:

```tsx
<table className="min-w-max w-full text-xs border-collapse">
```

- [ ] **Step 2: Verify visually**

Open `http://[::1]:5174` and navigate to any PO with a CUSTOMER_PO document. Open its review modal. The delivery locations table should now scroll horizontally, and all column values should be fully readable — no truncation.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/OrderItemsTable.tsx
git commit -m "fix: expand table columns to natural width — no more truncation in delivery locations"
```

---

## Task 2: Widen modal and fix PDF:form ratio

**Context:** The modal is currently `w-[95vw] h-[90vh]`. The split is 50/50 (`w-1/2` each). This makes the PDF too small to read and the form too cramped. Fix: go full-screen (`w-screen h-screen` with no margin), and change the split to 60/40 (PDF gets more room).

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx:479` (modal container) and `:542,547` (left/right panels)

- [ ] **Step 1: Update modal container and panel widths**

In `frontend/src/components/ReviewModal.tsx`, make these three targeted replacements:

**1. Modal wrapper** — find:
```tsx
<div className="m-auto bg-white rounded-xl shadow-2xl w-[95vw] h-[90vh] max-w-7xl flex flex-col">
```
Replace with:
```tsx
<div className="m-auto bg-white w-screen h-screen flex flex-col">
```

**2. Left (PDF) panel** — find:
```tsx
<div className="w-1/2 border-r border-gray-200">
```
Replace with:
```tsx
<div className="w-[58%] border-r border-gray-200">
```

**3. Right (form) panel** — find:
```tsx
<div className="w-1/2 flex flex-col">
```
Replace with:
```tsx
<div className="w-[42%] flex flex-col">
```

- [ ] **Step 2: Verify visually**

Reload the review modal. The PDF should now occupy ~58% of the screen width. Full screen, no rounded corners, no gap around the modal.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: full-screen review modal with 58/42 PDF-to-form split"
```

---

## Task 3: Read-only card view with edit toggle

**Context:** The current right panel forces every field into an `<input>` even when the reviewer just wants to check values. This creates a visually noisy "wall of boxes". The redesign shows fields as clean `label + value` pairs (read-only cards) by default. A single "✎ Edit" button in the panel header switches to the current input-based edit mode. The verify/reject flow and all mutations are completely unchanged — only how fields are displayed changes.

The read-only view uses a 2-column grid for scalar fields (label on one line, value below in larger text). Low-confidence fields (< 60%) get an amber background card. Missing fields (empty value) get a red-tinted card.

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx` — add `isEditMode` state, conditional field rendering

- [ ] **Step 1: Add `isEditMode` state**

In `ReviewModal.tsx`, after the existing `useState` declarations (around line 68), add:

```tsx
const [isEditMode, setIsEditMode] = useState(false);
```

Also update the `isManualMode` effect — when `isManualMode` is true (no extraction data), default to edit mode:

After the line `setIsManualMode(...)` (around line 129), add:

```tsx
      setIsEditMode(
        metadata.model_version === 'manual' ||
        Object.values(metadata.extracted_data).every((v) => v === null || v === '')
      );
```

And for the template branch (line ~146), add:
```tsx
      setIsEditMode(true);
```

- [ ] **Step 2: Add edit toggle button to the panel header**

In `ReviewModal.tsx`, find the `{/* Right: Form */}` section. The form panel currently starts with `<div className="w-[42%] flex flex-col">`. The first child is `<div className="flex-1 overflow-y-auto p-6 space-y-3">`.

Add a toggle bar between those two divs:

```tsx
<div className="w-[42%] flex flex-col">
  {/* Edit mode toggle bar */}
  {!isManualMode && (
    <div className="flex items-center justify-between px-5 py-2.5 border-b border-gray-100 bg-gray-50/50">
      <span className="text-xs text-gray-400">
        {isEditMode ? 'Edit mode — modify fields then Verify' : 'Review mode — verify extracted values'}
      </span>
      <button
        onClick={() => setIsEditMode((v) => !v)}
        className={clsx(
          'inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border transition-colors',
          isEditMode
            ? 'bg-white border-gray-300 text-gray-600 hover:bg-gray-50'
            : 'bg-[--accent] border-[--accent] text-white hover:opacity-90'
        )}
      >
        <PenLine size={13} />
        {isEditMode ? 'Back to Review' : 'Edit Fields'}
      </button>
    </div>
  )}
  <div className="flex-1 overflow-y-auto p-6 space-y-3">
```

- [ ] **Step 3: Replace scalar field rendering with conditional read/edit view**

In `ReviewModal.tsx`, find the `{/* ── Form fields ──────────────────────────────────── */}` block (around line 627). It currently renders:

```tsx
{sortedFormKeys(Object.keys(formData).filter((k) => !ARRAY_FIELDS.has(k))).map((key) => {
  const value = formData[key];
  const conf  = getFieldConfidence(key);
  const isChanged = value !== (originalSnapshot.current[key] ?? '');

  return (
    <div key={key}>
      <label ...>
      <input ... />
    </div>
  );
})}
```

Replace the entire block with:

```tsx
{sortedFormKeys(Object.keys(formData).filter((k) => !ARRAY_FIELDS.has(k) && k !== 'operator_notes')).map((key) => {
  const value   = formData[key];
  const conf    = getFieldConfidence(key);
  const isEmpty = !value;
  const isLowConf = conf !== null && conf < CONF_MEDIUM;
  const isChanged = value !== (originalSnapshot.current[key] ?? '');

  if (!isEditMode) {
    // ── Read-only card ──────────────────────────────────
    return (
      <div
        key={key}
        className={clsx(
          'rounded-lg px-3 py-2.5 border',
          isEmpty       ? 'bg-red-50 border-red-200'
          : isLowConf  ? 'bg-amber-50 border-amber-200'
          :               'bg-white border-[--veil]',
        )}
      >
        <div className="flex items-center justify-between mb-0.5">
          <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-400">
            {formatLabel(key)}
          </span>
          {conf !== null && (
            <span className={clsx('text-[10px] px-1.5 py-0.5 rounded font-medium', confBadgeColour(conf))}>
              {Math.round(conf * 100)}%
            </span>
          )}
        </div>
        <p className={clsx(
          'text-sm font-medium break-words',
          isEmpty     ? 'text-red-400 italic'
          : isLowConf ? 'text-amber-900'
          :              'text-[--ink]',
        )}>
          {isEmpty ? 'Not extracted' : value}
        </p>
      </div>
    );
  }

  // ── Edit input ─────────────────────────────────────
  return (
    <div key={key}>
      <label className="flex items-center justify-between text-xs font-medium text-gray-500 mb-1">
        <span>
          {formatLabel(key)}
          {isChanged && (
            <span className="ml-1.5 text-blue-500 font-semibold" title="Modified">✎</span>
          )}
        </span>
        {conf !== null && (
          <span className={clsx('text-xs px-1.5 py-0.5 rounded font-medium', confBadgeColour(conf))}>
            {Math.round(conf * 100)}%
          </span>
        )}
      </label>
      {key === 'signature_present' ? (
        <select
          value={value}
          onChange={(e) => setFormData((f) => ({ ...f, [key]: e.target.value }))}
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
          onChange={(e) => setFormData((f) => ({ ...f, [key]: e.target.value }))}
          placeholder={`Enter ${formatLabel(key).toLowerCase()}`}
          className={clsx(
            'w-full px-3 py-2 border-l-4 border rounded-lg text-sm',
            'focus:ring-2 focus:ring-blue-500 focus:outline-none',
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
```

- [ ] **Step 4: Verify visually**

Open a document review modal. The right panel should default to the card view — clean label+value pairs in a 2-column-ish layout. Red cards for empty fields, amber for low confidence, white for good. Clicking "Edit Fields" switches to the input form. Clicking "Back to Review" returns to card view. Verify and Reject buttons work in both modes.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: read-only card view for review modal — edit mode on demand"
```

---

## Task 4: Two-column card grid for scalar fields

**Context:** The read-only cards from Task 3 render in a single column (inherited from `space-y-3`). For documents with 6–8 fields, this wastes vertical space and forces scrolling. A 2-column grid makes all fields visible at once for most document types, leaving room for the tables below.

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx` — wrap scalar field section in a grid

- [ ] **Step 1: Wrap scalar fields in a responsive grid**

In `ReviewModal.tsx`, the scalar fields block starts with `{sortedFormKeys(...).map(...)}`. Wrap the entire `.map(...)` result in a grid container. Change the parent `<div className="flex-1 overflow-y-auto p-6 space-y-3">` to `<div className="flex-1 overflow-y-auto p-5 space-y-4">`, then inside, wrap ONLY the scalar fields map in a grid:

```tsx
{/* ── Field cards grid ─────────────────────────── */}
<div className={clsx(
  isEditMode ? 'space-y-3' : 'grid grid-cols-2 gap-2.5'
)}>
  {sortedFormKeys(...).map((key) => { ... })}
</div>
```

The edit mode keeps single-column (easier to fill in). The read-only view uses 2 columns.

- [ ] **Step 2: Verify visually**

Review modal in read-only mode should show fields in a 2-column grid. Switching to edit mode should revert to single column.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: 2-column grid for read-only field cards in review modal"
```

---

## Task 5: Improve validation warnings visibility

**Context:** The warnings banner is collapsed by default (`warningsOpen = false`). For the screenshot shown, there was "1 warning" but it was hidden. Warnings should be expanded by default — they're the reason a reviewer needs to pay attention.

Also: the `operator_notes` textarea and `Custom Fields` section should be hidden in read-only mode (they're only relevant during editing).

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx` — change `warningsOpen` default, hide operator_notes/custom fields in read-only mode

- [ ] **Step 1: Expand warnings by default**

In `ReviewModal.tsx`, find:
```tsx
const [warningsOpen, setWarningsOpen]   = useState(false);
```
Change to:
```tsx
const [warningsOpen, setWarningsOpen]   = useState(true);
```

- [ ] **Step 2: Hide operator_notes and custom fields in read-only mode**

Find the `{/* ── Operator Remarks — always visible ─────────────── */}` section. Wrap it:
```tsx
{(isEditMode || formData['operator_notes']) && (
  // existing operator_notes block
)}
```

Find the `{/* ── Custom Fields ──────────────────────────────────── */}` section. Wrap it:
```tsx
{isEditMode && (
  // existing custom fields block
)}
```

- [ ] **Step 3: Verify visually**

Open review modal. Warnings banner should be expanded by default. Operator notes and custom fields should be hidden in read-only mode and visible in edit mode.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: expand warnings by default, hide edit-only sections in review mode"
```

---

## Final smoke test

1. Open any CUSTOMER_PO document review modal
2. **Read mode (default):** All scalar fields display as cards — no truncation, no input boxes. 2-column grid. Empty fields are red. Low-confidence fields are amber. 1 warning banner expanded.
3. **Delivery locations table:** Scrolls horizontally. All column values fully visible. `CHENNAI` not `CHAN`.
4. **Edit Fields button:** Switches to input form. All inputs work. Corrections save.
5. **Back to Review button:** Returns to card view.
6. **Verify button:** Works in both modes. SO entry prompt fires if no SO set.
7. **Reject button:** Works as before.
8. **PDF panel:** Occupies ~58% of full-screen width. PDF is readable.

---

*Plan saved 2026-04-18. Addresses: table truncation, PDF/form ratio, read vs edit UX, warnings visibility.*
