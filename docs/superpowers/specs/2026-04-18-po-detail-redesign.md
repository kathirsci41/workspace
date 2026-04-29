# PO Detail Page — Redesign Spec
**Date:** 2026-04-18  
**Status:** Approved for implementation  
**Branch target:** development

---

## 1. Problem Statement

The current `PODetailPage` has 8 identified UX problems:

| # | Severity | Issue |
|---|---|---|
| 1 | High | Header row is overcrowded — PO#, customer, SO badge, status, amount, export, delete, profile all in one row |
| 2 | High | Dark slate-900 chain/validation/billing panels clash with the light page |
| 3 | High | Status banner duplicates the chain progress bar |
| 4 | High | 6 full-width stacked doc cards require heavy scrolling |
| 5 | Med | No visual hierarchy — every section looks equally important |
| 6 | Med | Document cards lack density; one doc per card wastes space |
| 7 | Med | Chain + validation info is buried mid-page below the fold |
| 8 | Low | 4–5 action buttons scattered on every document card |

Additionally, two features are **missing entirely**:
- Scenario selection is not surfaced to the user (only auto-derived, no override)
- Billing only handles Full billing; Staged and Recurring are not supported

---

## 2. Chosen Approach — Tabbed Layout (Approach A)

Three tabs replace the single long-scroll page:

| Tab | Purpose |
|---|---|
| **Overview** | Order metadata, scenario, chain status, reference validation, billing summary |
| **Documents** | All 6 document slots — upload, review, manage |
| **Billing** | Billing type selector, milestone tracker or invoice list, KPI cards |

A **Delete** action lives as a tab-style danger link on the right of the strip (existing pattern preserved).

---

## 3. Design Tokens (Warehouse Ledger palette)

Already applied in `index.css` and `tailwind.config.js` from the Tier 1 polish pass:

| Token | Hex | Role |
|---|---|---|
| `--ink` | `#1C1B1A` | Primary text |
| `--paper` | `#FAF7F1` | Page background |
| `--accent` | `#3B4FA3` | Primary actions, active tab underline |
| `--signal` | `#C2410C` | Destructive / stop-stream |
| `--veil` | `#E8E1D3` | Borders, shimmer base |

Fonts: `Fraunces` (display), `Inter Tight` (body), `JetBrains Mono` (ref numbers).

---

## 4. Page Structure

```
Breadcrumb  (Purchase Orders › PO-2026-SF003)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PO Header  (sticky)
  PO-ID (mono) · Customer · Status chip · Chain% chip · Amount
  [↗ Profile]  [⬇ Export]                            (right)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tab strip
  Overview | Documents (badge) | Billing | Delete (danger)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tab content (scrolls independently)
```

The sticky header always shows identity + chain% + actions regardless of active tab.

---

## 5. Overview Tab

### 5.1 Order Settings Card
A 2-column card directly below the section label, above the chain timeline.

**Left column — Order Scenario**
- Displays auto-derived scenario (STOCK / PROCUREMENT / DROP_SHIP / SERVICE_AMC) with an AUTO badge
- "Change ▾" link expands a 2×2 grid of scenario option tiles
- On manual selection, badge changes from AUTO → MANUAL; triggers chain recalculation
- API call: `PATCH /purchase-orders/{id}` with `{ order_scenario: "PROCUREMENT" }`

**Right column — Billing Type**
- Displays current billing type (FULL / STAGED / RECURRING)
- "Change ▾" opens inline selector
- Changing billing type updates the Billing tab layout and chain completion rules
- Shows a one-line summary: "3 milestones · ₹6,14,200 billed so far (66.7%)"
- API call: `PATCH /purchase-orders/{id}` with `{ billing_type: "STAGED" }`

### 5.2 Document Chain
6-node horizontal chain replacing the old dark timeline panel.

- Each node: icon (✅ / ❌ / ⚠️ / ⏳) + doc type label + ref number + status text
- Colour-coded left border: green (verified) / red (missing) / amber (pending/review)
- Arrow connectors between nodes
- Missing nodes shown with dashed empty state

### 5.3 Reference Validation
Horizontal row of status pills (replaces dark validation panel):
- `✓ SO number consistent` (green)
- `✗ Vendor DC ref mismatch` (red)
- `⚠ Company Invoice not verified` (amber)

### 5.4 Billing Summary
Compact 3-KPI card (PO Total / Billed So Far / Outstanding) + progress bar + "→ View full billing detail" link to Billing tab. Not the full billing table — just the snapshot.

---

## 6. Documents Tab

### 6.1 Document Cards
Single-column list of 6 compact cards (one per document type). Each card:
- Left accent border: green (verified) / amber (pending) / red/dashed (missing) / red (mismatch)
- Doc type label + ref number (mono) + upload date + filename
- **Primary action** (right side): context-dependent
  - Missing → `+ Upload` (accent outline)
  - Pending review → `Review →` (amber)
  - Verified → `View →` (ghost)
- **⋯ overflow menu** (three-dot): secondary actions — Edit Fields, Re-extract, View PDF, Delete

### 6.2 Overflow Menu Actions
| Action | When visible | Behaviour |
|---|---|---|
| Edit Fields | Verified or Pending | Opens ReviewModal in edit mode |
| Re-extract | Any uploaded doc | Confirm dialog → requeue → polling |
| View PDF | Any uploaded doc | Opens PDF popup modal (90vw × 90vh) |
| Delete | Any uploaded doc | Confirm modal showing doc type + filename |

### 6.3 Upload Zone
Clicking `+ Upload` on a missing card slot opens the existing `UploadZone` modal. After upload, card updates to `Extracting…` state and polls every 3s.

---

## 7. Billing Tab

### 7.1 Billing Type Selector
3-button toggle at the top of the tab: **Full | Staged | Recurring**  
Changing billing type:
- Updates PO via `PATCH /purchase-orders/{id}` with `{ billing_type: ... }`
- Switches the view below between three layouts

### 7.2 Full Billing Layout
- 3 KPI cards: PO Total / Billed So Far / Outstanding
- Simple invoice table: Document | Ref Number | Amount | Date | Status
- Rows: one per uploaded invoice document (Vendor Invoice, Company Invoice)
- Missing invoice shown as a placeholder row

### 7.3 Staged Billing Layout
- 3 KPI cards + progress bar (% filled)
- Milestone table:

| Column | Content |
|---|---|
| Milestone | Name + trigger condition (e.g. "On delivery") |
| % / Amount | Percentage + computed INR amount |
| Expected Date | Target date |
| Invoice Ref | Ref number (mono) or "— Not uploaded" |
| Status | Verified / Mismatch / Missing pill |

- Milestones are user-defined (name, %, trigger). Amounts auto-calculated from PO total.
- Each milestone links to its corresponding uploaded invoice document.
- "Edit milestones" button opens an inline editor (future: modal).

### 7.4 Recurring Billing Layout  
Placeholder for AMC/service contracts:
- Billing cycle selector (monthly / quarterly / custom)
- Invoice cadence table (future feature)
- For now: informational card with configuration prompt

---

## 8. Components to Create / Modify

### New components
| File | Purpose |
|---|---|
| `OrderSettingsCard.tsx` | Scenario selector + billing type selector in one card |
| `ScenarioSelector.tsx` | 2×2 expandable tile grid (can be inline or extracted) |
| `ChainTimeline.tsx` | Replaces existing dark ChainTimeline — horizontal 6-node light version |
| `BillingTab.tsx` | Full billing tab with type toggle + 3 layout variants |
| `StagedMilestoneTable.tsx` | Milestone rows with progress, invoice links, status |
| `DocCard.tsx` | Single compact document card with overflow menu |

### Modified components
| File | Change |
|---|---|
| `PODetailPage.tsx` | Introduce tab state, new layout, wire all sub-components |
| `ReviewModal.tsx` | Accept `mode="review" | "edit"` prop — already partially exists |
| `ChainTimeline.tsx` (existing) | Replace or refactor — current version is dark-themed |

---

## 9. API Changes Required

### New / modified fields on PO
The following fields must be patchable via `PATCH /purchase-orders/{id}`:
- `order_scenario` — already exists, but no frontend override
- `billing_type` — already exists as enum (FULL / STAGED / RECURRING)

### New: Milestone CRUD
Staged billing requires milestone definitions stored per PO. This needs:

**New table: `billing_milestones`**
```
id          UUID PK
po_id       FK → purchase_orders.id
name        VARCHAR  (e.g. "Advance Payment")
percentage  NUMERIC  (e.g. 30.0)
trigger     VARCHAR  (e.g. "On PO confirmation")
due_date    DATE nullable
order_index INTEGER
```

**New endpoints:**
- `GET  /purchase-orders/{id}/milestones` — list milestones for PO
- `POST /purchase-orders/{id}/milestones` — create milestone
- `PATCH /purchase-orders/{id}/milestones/{mid}` — update milestone
- `DELETE /purchase-orders/{id}/milestones/{mid}` — delete milestone

Invoice-to-milestone linking:
- When a Company Invoice is uploaded and verified, auto-match to the next unlinked milestone by order_index
- Manual override: user can re-link via the milestone table UI

---

## 10. State & Data Flow

```
PODetailPage
  ├── useQuery('po-detail', getPO)           — header data
  ├── useQuery('chain', getChain)            — chain + validation data
  ├── useQuery('milestones', getMilestones)  — billing milestones (new)
  ├── activeTab: 'overview' | 'documents' | 'billing'
  ├── scenarioDropdownOpen: boolean
  ├── selectedDocId: string | null           — PDF popup trigger
  └── selectedDocType: string | null
```

Tab switching is local state — no URL param needed (deep-linking is a nice-to-have, not required).

---

## 11. What Does NOT Change

- ReviewModal internals (PDF preview + field editor)
- UploadZone modal
- PDF popup modal (already built in Tier 1)
- Chain validation logic (backend unchanged)
- Extraction pipeline (backend unchanged)
- All API endpoints except the two new scenario/billing-type patches + new milestone CRUD

---

## 12. Out of Scope (future)

- Recurring billing schedule editor
- Milestone auto-detection from PO line items
- Email reminders on overdue milestones
- Bulk milestone template (e.g. "30/40/30 split" preset)
- POD (Proof of Delivery) document type
