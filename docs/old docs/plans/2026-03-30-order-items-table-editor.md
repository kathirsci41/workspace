# Order Items Table Editor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `order_items` (and read-only `delivery_locations`) visible and editable inside ReviewModal so operators can see, correct, and manually enter line-item table data for all 6 document types.

**Architecture:** A new reusable `OrderItemsTable` component handles the editable grid. ReviewModal gains `tableRows` state (parallel to `formData`) initialized from extracted data. On verify, `tableRows` are included in `editedData` so they persist to `extracted_data` via the existing verify endpoint. `delivery_locations` is rendered read-only with dynamic columns derived from the data itself (CUSTOMER_PO only). No backend changes required.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React — same as existing ReviewModal

---

## Files Modified / Created

| File | Action | Responsibility |
|------|--------|----------------|
| `frontend/src/components/OrderItemsTable.tsx` | **Create** | Reusable editable table grid — columns config, add/delete row, cell editing, read-only mode |
| `frontend/src/components/ReviewModal.tsx` | **Modify** | Add `tableRows` state, import + render `OrderItemsTable`, include rows in `editedData` and corrections |

---

## Task 1: Create `OrderItemsTable` Component

**Files:**
- Create: `frontend/src/components/OrderItemsTable.tsx`

`★ Insight ─────────────────────────────────────`
The component receives `columns` as a prop (not hardcoded) so it handles both the 5-column CUSTOMER_PO schema (`sr_no, description, qty, unit_price, total_price`) and the 9-column schema for all other doc types. The same component also handles `delivery_locations` in `readOnly` mode, where columns come from the actual data keys.
`─────────────────────────────────────────────────`

- [ ] **Step 1: Create the file with the full component**

Create `frontend/src/components/OrderItemsTable.tsx`:

```tsx
import { Plus, X } from 'lucide-react';

export type OrderItemRow = Record<string, string>;

interface OrderItemsTableProps {
  columns: string[];
  rows: OrderItemRow[];
  onChange: (rows: OrderItemRow[]) => void;
  readOnly?: boolean;
}

const COL_LABELS: Record<string, string> = {
  sr_no:          'Sr.No',
  part_no:        'Part No',
  description:    'Description',
  hsn_code:       'HSN',
  qty:            'Qty',
  uom:            'UOM',
  unit_price:     'Unit Price',
  total_price:    'Total',
  serial_numbers: 'Serial Nos',
};

// Tailwind classes — define width per known column; unknown columns get auto width
const COL_WIDTHS: Record<string, string> = {
  sr_no:          'w-10',
  part_no:        'w-28',
  description:    'min-w-[10rem]',
  hsn_code:       'w-20',
  qty:            'w-14',
  uom:            'w-14',
  unit_price:     'w-24',
  total_price:    'w-24',
  serial_numbers: 'w-32',
};

export function OrderItemsTable({ columns, rows, onChange, readOnly = false }: OrderItemsTableProps) {
  const addRow = () => {
    const empty: OrderItemRow = {};
    for (const col of columns) empty[col] = '';
    onChange([...rows, empty]);
  };

  const updateCell = (rowIdx: number, col: string, val: string) => {
    onChange(rows.map((r, i) => (i === rowIdx ? { ...r, [col]: val } : r)));
  };

  const deleteRow = (rowIdx: number) => {
    onChange(rows.filter((_, i) => i !== rowIdx));
  };

  if (rows.length === 0 && readOnly) {
    return <p className="text-xs text-gray-400 italic py-2">No data extracted.</p>;
  }

  return (
    <div>
      <div className="overflow-x-auto rounded border border-gray-200">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-gray-50">
              {columns.map((col) => (
                <th
                  key={col}
                  className={`px-2 py-1.5 text-left font-medium text-gray-500 border-b border-r border-gray-200 last:border-r-0 whitespace-nowrap ${COL_WIDTHS[col] ?? ''}`}
                >
                  {COL_LABELS[col] ?? col.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                </th>
              ))}
              {!readOnly && <th className="w-8 border-b border-gray-200 bg-gray-50" />}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (readOnly ? 0 : 1)}
                  className="px-3 py-4 text-center text-xs text-gray-400 italic"
                >
                  No line items — click &quot;Add Row&quot; to add one.
                </td>
              </tr>
            ) : (
              rows.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-gray-50/60 border-b border-gray-100 last:border-b-0">
                  {columns.map((col) => (
                    <td key={col} className="px-1 py-0.5 border-r border-gray-100 last:border-r-0">
                      {readOnly ? (
                        <span className="block px-1 py-1 text-gray-700">{row[col] ?? ''}</span>
                      ) : (
                        <input
                          type="text"
                          value={row[col] ?? ''}
                          onChange={(e) => updateCell(rowIdx, col, e.target.value)}
                          className="w-full px-1.5 py-1 rounded text-xs focus:ring-1 focus:ring-blue-400 focus:outline-none bg-transparent hover:bg-white focus:bg-white transition-colors"
                        />
                      )}
                    </td>
                  ))}
                  {!readOnly && (
                    <td className="px-1 py-0.5 text-center">
                      <button
                        type="button"
                        onClick={() => deleteRow(rowIdx)}
                        title="Remove row"
                        className="p-0.5 text-gray-300 hover:text-red-500 rounded transition-colors"
                      >
                        <X size={13} />
                      </button>
                    </td>
                  )}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {!readOnly && (
        <button
          type="button"
          onClick={addRow}
          className="mt-1.5 inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-700 font-medium"
        >
          <Plus size={13} /> Add Row
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify the file builds**

```bash
cd "E:\PROJECTS\Experiments\Logistic\DPP 2.2.0\frontend"
npx tsc --noEmit 2>&1 | head -30
```

Expected: no errors from `OrderItemsTable.tsx`. Other pre-existing errors are acceptable.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/OrderItemsTable.tsx
git commit -m "feat: add OrderItemsTable reusable editable grid component"
```

---

## Task 2: Integrate `OrderItemsTable` into `ReviewModal`

**Files:**
- Modify: `frontend/src/components/ReviewModal.tsx`

This task has 4 sub-parts:
1. Add imports + column definitions
2. Add `tableRows` state and initialise from `extracted_data`
3. Render the tables in the form panel
4. Include `tableRows` in `editedData` (verify) and corrections (save)

`★ Insight ─────────────────────────────────────`
The backend's `ARRAY_PRESERVE_KEYS` logic only runs when the key is **absent** from `editedData`. So once we include `order_items` in `editedData`, the backend uses our value directly — the preserve logic is a fallback, not a gate. `delivery_locations` stays absent from `editedData`, so it continues to be preserved from DB automatically.
`─────────────────────────────────────────────────`

### 2a — Add imports and column definitions

- [ ] **Step 1: Add OrderItemsTable import and column constants**

At the top of `frontend/src/components/ReviewModal.tsx`, after the existing imports, add:

```typescript
import { OrderItemsTable, type OrderItemRow } from '@/components/OrderItemsTable';
```

After the `CONF_MEDIUM` constant (line ~28), add:

```typescript
// Columns per document type for the order_items table
const ORDER_ITEMS_COLUMNS: Record<string, string[]> = {
  CUSTOMER_PO:     ['sr_no', 'description', 'qty', 'unit_price', 'total_price'],
  COMPANY_PO:      ['sr_no', 'part_no', 'description', 'hsn_code', 'qty', 'uom', 'unit_price', 'total_price', 'serial_numbers'],
  VENDOR_DC:       ['sr_no', 'part_no', 'description', 'hsn_code', 'qty', 'uom', 'unit_price', 'total_price', 'serial_numbers'],
  VENDOR_INVOICE:  ['sr_no', 'part_no', 'description', 'hsn_code', 'qty', 'uom', 'unit_price', 'total_price', 'serial_numbers'],
  COMPANY_DC:      ['sr_no', 'part_no', 'description', 'hsn_code', 'qty', 'uom', 'unit_price', 'total_price', 'serial_numbers'],
  COMPANY_INVOICE: ['sr_no', 'part_no', 'description', 'hsn_code', 'qty', 'uom', 'unit_price', 'total_price', 'serial_numbers'],
};

// Normalise an array row to Record<string, string> (handles nulls and numbers from extraction)
function normalizeRow(row: unknown): OrderItemRow {
  if (!row || typeof row !== 'object') return {};
  return Object.fromEntries(
    Object.entries(row as Record<string, unknown>).map(([k, v]) => [k, v != null ? String(v) : ''])
  );
}
```

### 2b — Add `tableRows` state and initialise

- [ ] **Step 2: Add state declaration inside the component**

Inside `ReviewModal`, after the existing `const originalSnapshot = useRef<Record<string, string>>({});` line, add:

```typescript
const [tableRows, setTableRows]         = useState<OrderItemRow[]>([]);
const originalTableRows                 = useRef<OrderItemRow[]>([]);
```

- [ ] **Step 3: Initialise `tableRows` inside the useEffect**

In the `useEffect` (the one that runs when `metadata` or `template` changes), inside the `if (metadata?.extracted_data && ...)` block, after `originalSnapshot.current = snap;`, add:

```typescript
const rawItems = metadata.extracted_data['order_items'];
const items = Array.isArray(rawItems) ? rawItems.map(normalizeRow) : [];
setTableRows(items);
originalTableRows.current = items;
```

Also inside the `else if (template?.fields)` block, after `originalSnapshot.current = { ...initial };`, add:

```typescript
setTableRows([]);
originalTableRows.current = [];
```

### 2c — Render the tables in the form panel

- [ ] **Step 4: Add order_items and delivery_locations sections**

In the JSX, find the Operator Remarks section that starts with:
```tsx
{/* ── Operator Remarks — always visible ─────────────── */}
{'operator_notes' in formData && (
```

Insert the following block **immediately before** that section (between the form fields and remarks):

```tsx
{/* ── Order Items Table ─────────────────────────────── */}
{(() => {
  const docType = metadata?.document_type ?? '';
  const columns = ORDER_ITEMS_COLUMNS[docType];
  if (!columns) return null;
  const tableChanged = JSON.stringify(tableRows) !== JSON.stringify(originalTableRows.current);
  return (
    <div className="pt-3 mt-1 border-t border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs font-medium text-gray-500">Line Items</span>
        {tableChanged && (
          <span className="text-xs text-blue-500 font-semibold" title="Modified">✎ Modified</span>
        )}
      </div>
      <OrderItemsTable
        columns={columns}
        rows={tableRows}
        onChange={setTableRows}
      />
    </div>
  );
})()}

{/* ── Delivery Locations (read-only, CUSTOMER_PO only) ── */}
{(() => {
  const raw = metadata?.extracted_data?.['delivery_locations'];
  if (!Array.isArray(raw) || raw.length === 0) return null;
  const locations = raw.map(normalizeRow);
  const cols = Object.keys(locations[0]);
  if (cols.length === 0) return null;
  return (
    <div className="pt-3 mt-1 border-t border-gray-100">
      <span className="text-xs font-medium text-gray-500 block mb-2">Delivery Locations</span>
      <OrderItemsTable
        columns={cols}
        rows={locations}
        onChange={() => {}}
        readOnly
      />
    </div>
  );
})()}
```

### 2d — Include `tableRows` in verify and save flows

- [ ] **Step 5: Include `tableRows` in `handleVerify` editedData**

In `handleVerify`, after the `for (const { label, value } of customFields)` block and before `setSoMismatchMsg(null)`, add:

```typescript
// Include edited order_items — convert empty strings to null, numeric fields to numbers
const numericCols = new Set(['qty', 'unit_price', 'total_price']);
editedData['order_items'] = tableRows.map((row) => {
  const result: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(row)) {
    if (v === '') {
      result[k] = null;
    } else if (numericCols.has(k) && !isNaN(Number(v))) {
      result[k] = Number(v);
    } else {
      result[k] = v;
    }
  }
  return result;
});
```

- [ ] **Step 6: Include `tableRows` diff in `handleSave` corrections**

In `handleSave`, after the `for (const { label, value } of customFields)` block and before `if (corrections.length === 0)`, add:

```typescript
// Include order_items change in corrections audit log
if (JSON.stringify(tableRows) !== JSON.stringify(originalTableRows.current)) {
  corrections.push({ field: 'order_items', corrected_value: tableRows });
}
```

- [ ] **Step 7: Verify TypeScript compiles**

```bash
cd "E:\PROJECTS\Experiments\Logistic\DPP 2.2.0\frontend"
npx tsc --noEmit 2>&1 | head -40
```

Expected: no new errors compared to before this task. Pre-existing errors from other files are acceptable.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/ReviewModal.tsx
git commit -m "feat: add editable order_items table and read-only delivery_locations to ReviewModal"
```

---

## Task 3: Manual Smoke Tests

- [ ] **Step 1: Start the app**

Run `start.ps1` (or `cd frontend && npm run dev` if backend already running).

- [ ] **Step 2: Test with an extracted document (review mode)**

1. Open any PENDING_REVIEW document — click "Review".
2. In the form panel, scroll past the scalar fields.
3. Verify "Line Items" section appears with the correct column headers for the doc type.
   - CUSTOMER_PO: `Sr.No | Description | Qty | Unit Price | Total`
   - Others: `Sr.No | Part No | Description | HSN | Qty | UOM | Unit Price | Total | Serial Nos`
4. Verify the AI-extracted rows are pre-populated in the table cells.
5. Edit a cell (e.g., change a Qty value) — confirm the "✎ Modified" badge appears next to "Line Items".
6. Delete a row using the X button — confirm the row disappears.
7. Click "Add Row" — confirm a new empty row appears.
8. Click "Verify" — document should verify successfully.
9. Re-open the same document in edit mode — confirm the edited rows are now shown (proving they were saved to extracted_data).

- [ ] **Step 3: Test with a CUSTOMER_PO with delivery_locations**

1. Open a CUSTOMER_PO that has delivery locations extracted.
2. Verify "Delivery Locations" section appears below "Line Items".
3. Confirm it is read-only — cells display text, no inputs or delete buttons.
4. Confirm columns match the actual column headers from the document (dynamic).

- [ ] **Step 4: Test manual entry mode**

1. Upload a new document and let extraction fail, OR find an EXTRACTION_FAILED document.
2. Open it in review mode — it should show "Manual entry mode" banner.
3. Scroll to "Line Items" section — it should be empty with "No line items — click Add Row" text.
4. Click "Add Row" and fill in the cells manually.
5. Click "Verify" — confirm the document verifies and the line items are saved.

- [ ] **Step 5: Test edit mode**

1. Find a VERIFIED document.
2. Click "Edit" (pencil icon) if available.
3. Edit a cell in the order_items table.
4. Click "Save Changes".
5. Confirm the modal closes without error.

---

## Self-Review Checklist

**Spec coverage:**
- [x] All 6 document types show order_items table — covered by `ORDER_ITEMS_COLUMNS` constant with all 6 keys
- [x] CUSTOMER_PO shows 5-column schema, others show 9-column schema — covered by `ORDER_ITEMS_COLUMNS` values
- [x] delivery_locations rendered read-only — Task 2c, second IIFE block
- [x] delivery_locations columns are dynamic — derived from `Object.keys(locations[0])`
- [x] Edits persist after verify — Task 2d Step 5 adds `editedData['order_items']`
- [x] Add row / delete row — Task 1 `OrderItemsTable` component
- [x] Modified badge shown when rows changed — Task 2c, `tableChanged` flag
- [x] Manual entry mode supports table — `tableRows` starts empty; operator clicks "Add Row"
- [x] Edit mode logs corrections — Task 2d Step 6 adds to corrections array
- [x] No backend changes required — confirmed, backend already handles order_items in editedData

**Placeholder scan:** No TBDs, no "add appropriate X" language, all code is complete.

**Type consistency:**
- `OrderItemRow = Record<string, string>` — used in both `OrderItemsTable.tsx` and `ReviewModal.tsx` (imported from component)
- `normalizeRow(row: unknown): OrderItemRow` — defined at module level in `ReviewModal.tsx`, used in useEffect and delivery_locations renderer
- `ORDER_ITEMS_COLUMNS: Record<string, string[]>` — indexed by `metadata?.document_type` (same string values used in `FIELD_ORDER` on line 258)
- `editedData['order_items']` — backend `ARRAY_PRESERVE_KEYS` only preserves when key is absent; our key is present → backend uses our value ✓
- `corrections.push({ field: 'order_items', corrected_value: tableRows })` — `corrected_value` is `Optional[Any]` on backend, array is valid ✓
