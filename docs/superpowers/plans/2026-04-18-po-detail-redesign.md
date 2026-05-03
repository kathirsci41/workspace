# PO Detail Page Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the long-scroll PO Detail page with a tabbed layout (Overview / Documents / Billing) that surfaces scenario selection, reference validation, and staged billing in a light-themed, compact UI.

**Architecture:** Pure frontend work — all required backend fields (`order_scenario`, `billing_type`, `billing_milestones` JSONB) already exist and are patchable via `PATCH /purchase-orders/{id}`. Five new focused components plug into a rewritten `PODetailPage.tsx` that manages a single `activeTab` state. No new API endpoints needed.

**Tech Stack:** React 18, TypeScript, TanStack Query, Tailwind CSS (Warehouse Ledger tokens), lucide-react, clsx

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `frontend/src/types/index.ts` | Add `BillingMilestone` interface + field on `PurchaseOrder` |
| Create | `frontend/src/components/LightChainTimeline.tsx` | Horizontal 6-node light-themed chain (replaces dark one in new page) |
| Create | `frontend/src/components/DocCard.tsx` | Compact doc slot card with ⋯ overflow menu |
| Create | `frontend/src/components/OrderSettingsCard.tsx` | Scenario + billing-type selectors in one 2-col card |
| Create | `frontend/src/components/BillingTab.tsx` | Billing type toggle + Full / Staged / Recurring views |
| Modify | `frontend/src/pages/PODetailPage.tsx` | Rewrite with tab layout, wire all new components |

---

## Task 1: Add `BillingMilestone` type

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add `BillingMilestone` interface after `ChainStatus`**

Find the `export interface ChainStatus {` block (around line 148) and add after it:

```ts
export interface BillingMilestone {
  name: string;       // e.g. "Advance Payment"
  percentage: number; // e.g. 30
  trigger: string;    // e.g. "On PO confirmation"
  due_date: string | null; // ISO date or null
}
```

- [ ] **Step 2: Add `billing_milestones` field to `PurchaseOrder`**

Find the `billing_type?` line in the `PurchaseOrder` interface and add the field below it:

```ts
billing_type?: 'full' | 'staged' | 'recurring';
billing_milestones?: BillingMilestone[];
```

- [ ] **Step 3: Verify TypeScript compilation**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add BillingMilestone type and billing_milestones field on PurchaseOrder"
```

---

## Task 2: Create `LightChainTimeline` component

The existing `ChainTimeline` uses dark slate-900 backgrounds. This new component is a horizontal row of 6 nodes using the Warehouse Ledger light palette. It reads from the same `ChainStatus.chain` data.

**Files:**
- Create: `frontend/src/components/LightChainTimeline.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { CHAIN_ORDER, DOC_TYPE_LABELS } from '@/types';
import type { ChainSlot } from '@/types';
import clsx from 'clsx';

interface Props {
  chain: Record<string, ChainSlot[]>;
  missingSlots: string[];
  referenceChecks: Array<{ document_type: string; result: string }>;
}

function slotState(
  docType: string,
  slots: ChainSlot[],
  missing: string[],
  refChecks: Array<{ document_type: string; result: string }>,
): 'verified' | 'missing' | 'pending' | 'mismatch' | 'extracting' {
  if (missing.includes(docType)) return 'missing';
  const slot = slots[0];
  if (!slot || !slot.document_id) return 'missing';
  if (slot.status === 'EXTRACTING' || slot.status === 'UPLOADED') return 'extracting';
  if (refChecks.some(r => r.document_type === docType && r.result === 'mismatch')) return 'mismatch';
  if (slot.status === 'PENDING_REVIEW') return 'pending';
  return 'verified';
}

const STATE: Record<string, { icon: string; borderClass: string; labelClass: string; statusText: string }> = {
  verified:   { icon: '✓', borderClass: 'border-green-400',  labelClass: 'text-green-700',  statusText: 'Verified'    },
  missing:    { icon: '—', borderClass: 'border-[--veil] border-dashed', labelClass: 'text-gray-400', statusText: 'Missing' },
  pending:    { icon: '!', borderClass: 'border-amber-400',  labelClass: 'text-amber-700',  statusText: 'Review'      },
  mismatch:   { icon: '✗', borderClass: 'border-red-400',    labelClass: 'text-red-700',    statusText: 'Mismatch'    },
  extracting: { icon: '⟳', borderClass: 'border-blue-400',   labelClass: 'text-blue-700',   statusText: 'Extracting…' },
};

export function LightChainTimeline({ chain, missingSlots, referenceChecks }: Props) {
  return (
    <div className="grid grid-cols-6 gap-2">
      {CHAIN_ORDER.map((docType, i) => {
        const slots = chain[docType] ?? [];
        const state = slotState(docType, slots, missingSlots, referenceChecks);
        const cfg = STATE[state];
        const ref = slots[0]?.ref_no ?? null;

        return (
          <div key={docType} className="flex items-center gap-1">
            <div
              className={clsx(
                'flex-1 rounded-lg border bg-white p-2.5',
                cfg.borderClass,
                state === 'missing' && 'bg-gray-50',
              )}
            >
              <div className={clsx('text-xs font-bold', cfg.labelClass)}>{cfg.icon}</div>
              <div className="text-[10px] font-bold uppercase tracking-wide text-gray-500 mt-1 leading-tight">
                {DOC_TYPE_LABELS[docType] ?? docType}
              </div>
              {ref && (
                <div className="font-mono text-[9px] text-gray-600 mt-0.5 truncate" title={ref}>
                  {ref}
                </div>
              )}
              <div className={clsx('text-[9px] font-semibold mt-1', cfg.labelClass)}>
                {cfg.statusText}
              </div>
            </div>
            {i < CHAIN_ORDER.length - 1 && (
              <span className="text-gray-300 text-xs flex-shrink-0">→</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/LightChainTimeline.tsx
git commit -m "feat: add LightChainTimeline component (light-themed horizontal 6-node chain)"
```

---

## Task 3: Create `DocCard` component

Compact single-row card for each document slot. Primary action button changes by status; secondary actions hidden in a ⋯ menu.

**Files:**
- Create: `frontend/src/components/DocCard.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { useState, useRef, useEffect } from 'react';
import { MoreHorizontal } from 'lucide-react';
import type { ChainSlot } from '@/types';
import clsx from 'clsx';

interface Props {
  docType: string;
  label: string;
  slot: ChainSlot | null;
  onUpload: () => void;
  onReview: (docId: string) => void;
  onView: (docId: string) => void;
  onReExtract: (docId: string) => void;
  onEditFields: (docId: string) => void;
  onDelete: (docId: string) => void;
}

const STATUS_BORDER: Record<string, string> = {
  VERIFIED:       'border-l-green-400',
  PENDING_REVIEW: 'border-l-amber-400',
  EXTRACTION_FAILED: 'border-l-red-400',
  EXTRACTING:     'border-l-blue-400',
  UPLOADED:       'border-l-blue-400',
  missing:        'border-l-[--veil]',
};

const STATUS_TAG: Record<string, { label: string; cls: string }> = {
  VERIFIED:          { label: '✓ Verified',   cls: 'bg-green-100 text-green-700' },
  PENDING_REVIEW:    { label: '⚠ Review',     cls: 'bg-amber-100 text-amber-700' },
  EXTRACTION_FAILED: { label: '✗ Failed',     cls: 'bg-red-100 text-red-700' },
  EXTRACTING:        { label: '⟳ Extracting', cls: 'bg-blue-100 text-blue-700' },
  UPLOADED:          { label: '⟳ Processing', cls: 'bg-blue-100 text-blue-700' },
  missing:           { label: '— Missing',    cls: 'bg-gray-100 text-gray-500' },
};

export default function DocCard({
  docType, label, slot,
  onUpload, onReview, onView, onReExtract, onEditFields, onDelete,
}: Props) {
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  // Close menu on outside click
  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const status = slot?.status ?? 'missing';
  const docId  = slot?.document_id ?? null;
  const borderKey = STATUS_BORDER[status] ?? 'border-l-[--veil]';
  const tag = STATUS_TAG[status] ?? STATUS_TAG.missing;
  const isMissing = !slot || !docId;
  const isDashed = isMissing;

  return (
    <div
      className={clsx(
        'flex items-center gap-3 bg-white rounded-lg border border-[--veil] border-l-4 px-4 py-3',
        borderKey,
        isDashed && 'bg-gray-50 border-dashed',
      )}
    >
      {/* Icon */}
      <span className="text-lg flex-shrink-0 w-6 text-center">
        {isMissing ? '📭' : status === 'PENDING_REVIEW' ? '📋' : '📄'}
      </span>

      {/* Body */}
      <div className="flex-1 min-w-0">
        <div className={clsx('text-sm font-bold', isMissing && 'text-gray-400')}>{label}</div>
        <div className="font-mono text-[10px] text-gray-500">
          {slot?.ref_no ?? (isMissing ? 'Not uploaded' : '—')}
        </div>
      </div>

      {/* Status tag */}
      <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full flex-shrink-0', tag.cls)}>
        {tag.label}
      </span>

      {/* Primary action */}
      {isMissing && (
        <button
          onClick={onUpload}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-[--accent] text-[--accent] bg-[#eef2ff] hover:bg-[--accent] hover:text-white transition-colors flex-shrink-0"
        >
          + Upload
        </button>
      )}
      {!isMissing && status === 'PENDING_REVIEW' && (
        <button
          onClick={() => onReview(docId!)}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 transition-colors flex-shrink-0"
        >
          Review →
        </button>
      )}
      {!isMissing && status === 'VERIFIED' && (
        <button
          onClick={() => onView(docId!)}
          className="text-xs font-semibold px-3 py-1.5 rounded-md border border-[--veil] text-gray-600 bg-white hover:bg-gray-50 transition-colors flex-shrink-0"
        >
          View →
        </button>
      )}

      {/* Overflow menu */}
      {!isMissing && docId && (
        <div className="relative flex-shrink-0" ref={menuRef}>
          <button
            onClick={() => setMenuOpen(v => !v)}
            className="p-1.5 rounded-md text-gray-400 hover:bg-gray-100 transition-colors"
            aria-label="More actions"
          >
            <MoreHorizontal size={14} />
          </button>
          {menuOpen && (
            <div className="absolute right-0 top-full mt-1 w-44 bg-white border border-[--veil] rounded-lg shadow-lg z-20 overflow-hidden">
              {(status === 'VERIFIED' || status === 'PENDING_REVIEW') && (
                <button
                  className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                  onClick={() => { setMenuOpen(false); onEditFields(docId); }}
                >
                  ✏ Edit Fields
                </button>
              )}
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                onClick={() => { setMenuOpen(false); onView(docId); }}
              >
                👁 View PDF
              </button>
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-gray-50 text-gray-700"
                onClick={() => { setMenuOpen(false); onReExtract(docId); }}
              >
                ↺ Re-extract
              </button>
              <button
                className="w-full text-left px-4 py-2.5 text-xs hover:bg-red-50 text-red-600"
                onClick={() => { setMenuOpen(false); onDelete(docId); }}
              >
                🗑 Delete
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/DocCard.tsx
git commit -m "feat: add DocCard component (compact doc slot with overflow menu)"
```

---

## Task 4: Create `OrderSettingsCard` component

A 2-column card that lets the user see and override order scenario and billing type. Both call `onUpdate` which callers wire to `updatePO()`.

**Files:**
- Create: `frontend/src/components/OrderSettingsCard.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { useState } from 'react';
import type { PurchaseOrder } from '@/types';
import clsx from 'clsx';

type Scenario    = PurchaseOrder['order_scenario'];
type BillingType = NonNullable<PurchaseOrder['billing_type']>;

interface Props {
  scenario: Scenario;
  billingType: BillingType;
  billedSoFar: number;
  milestoneCount: number;
  poTotal: number | null;
  onScenarioChange: (val: Scenario) => void;
  onBillingTypeChange: (val: BillingType) => void;
}

const SCENARIOS: Array<{ value: Scenario; icon: string; label: string; desc: string }> = [
  { value: 'stock',       icon: '🏭', label: 'STOCK',      desc: 'From warehouse inventory' },
  { value: 'procurement', icon: '📦', label: 'PROCUREMENT', desc: 'Vendor order on demand' },
  { value: 'drop_ship',   icon: '🚚', label: 'DROP-SHIP',   desc: 'Vendor ships direct' },
  { value: 'service_amc', icon: '🔧', label: 'SERVICE/AMC', desc: 'Service contract' },
];

const BILLING_TYPES: Array<{ value: BillingType; label: string }> = [
  { value: 'full',      label: 'Full' },
  { value: 'staged',    label: 'Staged' },
  { value: 'recurring', label: 'Recurring' },
];

export default function OrderSettingsCard({
  scenario, billingType, billedSoFar, milestoneCount, poTotal,
  onScenarioChange, onBillingTypeChange,
}: Props) {
  const [scenarioOpen, setScenarioOpen] = useState(false);
  const isAutoScenario = scenario === 'unknown' || scenario === 'procurement'; // show AUTO badge heuristic

  const currentScenario = SCENARIOS.find(s => s.value === scenario);

  const billedPct = poTotal && poTotal > 0
    ? Math.round((billedSoFar / poTotal) * 100)
    : 0;

  return (
    <div className="bg-white border border-[--veil] rounded-xl p-4 mb-5 grid grid-cols-2 gap-6">

      {/* ── Scenario ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">
          Order Scenario
        </div>
        <div className="flex items-center gap-2">
          <div className="flex-1 flex items-center gap-2 bg-gray-50 border border-[--veil] rounded-lg px-3 py-2 text-sm font-semibold text-[--ink]">
            {currentScenario?.icon ?? '❓'} {currentScenario?.label ?? scenario.toUpperCase()}
            <span className="ml-auto text-[9px] font-bold px-1.5 py-0.5 rounded bg-blue-100 text-blue-700">
              AUTO
            </span>
          </div>
          <button
            onClick={() => setScenarioOpen(v => !v)}
            className="text-xs font-semibold text-[--accent] whitespace-nowrap hover:underline"
          >
            Change ▾
          </button>
        </div>
        {scenarioOpen && (
          <div className="grid grid-cols-2 gap-1.5 mt-2">
            {SCENARIOS.map(s => (
              <button
                key={s.value}
                onClick={() => { onScenarioChange(s.value); setScenarioOpen(false); }}
                className={clsx(
                  'text-left border rounded-lg px-3 py-2 text-xs transition-colors',
                  scenario === s.value
                    ? 'border-[--accent] bg-[#eef2ff] font-semibold text-[--accent]'
                    : 'border-[--veil] bg-white hover:border-[--accent] hover:bg-[#eef2ff]',
                )}
              >
                <div className="font-bold">{s.icon} {s.label}</div>
                <div className="text-[9px] text-gray-400 mt-0.5">{s.desc}</div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Billing Type ── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2">
          Billing Type
        </div>
        <div className="flex gap-1.5 mb-2">
          {BILLING_TYPES.map(bt => (
            <button
              key={bt.value}
              onClick={() => onBillingTypeChange(bt.value)}
              className={clsx(
                'flex-1 text-xs font-semibold py-2 rounded-lg border transition-colors',
                billingType === bt.value
                  ? 'bg-[--accent] text-white border-[--accent]'
                  : 'bg-white text-gray-600 border-[--veil] hover:border-[--accent]',
              )}
            >
              {bt.label}
            </button>
          ))}
        </div>
        <div className="text-[10px] text-gray-400">
          {billingType === 'staged' && milestoneCount > 0
            ? `${milestoneCount} milestones · ₹${billedSoFar.toLocaleString('en-IN')} billed (${billedPct}%)`
            : billingType === 'staged'
            ? 'No milestones defined — go to Billing tab to set up'
            : `₹${billedSoFar.toLocaleString('en-IN')} billed so far`}
        </div>
      </div>

    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/OrderSettingsCard.tsx
git commit -m "feat: add OrderSettingsCard (scenario selector + billing type toggle)"
```

---

## Task 5: Create `BillingTab` component

Full billing tab: type toggle at top switches between Full / Staged / Recurring views. Staged view merges `po.billing_milestones` (user-defined names/percentages) with `chainValidation.billing.stages` (invoiced amounts from backend).

**Files:**
- Create: `frontend/src/components/BillingTab.tsx`

- [ ] **Step 1: Create the file**

```tsx
import { useState } from 'react';
import type { PurchaseOrder, BillingMilestone } from '@/types';
import type { ChainStatusResponse } from '@/api/purchaseOrders';
import clsx from 'clsx';

interface Props {
  po: PurchaseOrder;
  chainValidation: ChainStatusResponse | null;
  onUpdate: (patch: Partial<PurchaseOrder>) => void;
}

const TYPE_LABELS = { full: 'Full', staged: 'Staged', recurring: 'Recurring' };

const STATUS_TAG: Record<string, string> = {
  complete: 'bg-green-100 text-green-700',
  paid:     'bg-green-100 text-green-700',
  partial:  'bg-amber-100 text-amber-700',
  pending:  'bg-gray-100 text-gray-500',
  mismatch: 'bg-red-100 text-red-700',
};

function KpiCard({ label, value, sub, variant }: {
  label: string; value: string; sub: string;
  variant: 'ok' | 'warn' | 'bad' | 'neutral';
}) {
  const cls = {
    ok:      'border-green-300 bg-green-50',
    warn:    'border-amber-300 bg-amber-50',
    bad:     'border-red-300  bg-red-50',
    neutral: 'border-[--veil] bg-white',
  }[variant];
  return (
    <div className={clsx('border rounded-xl p-3', cls)}>
      <div className="text-[9px] font-bold uppercase tracking-wide text-gray-400">{label}</div>
      <div className="text-base font-bold text-[--ink] mt-1">{value}</div>
      <div className="text-[10px] text-gray-500 mt-0.5">{sub}</div>
    </div>
  );
}

export default function BillingTab({ po, chainValidation, onUpdate }: Props) {
  const billingType = po.billing_type ?? 'full';
  const milestones: BillingMilestone[] = po.billing_milestones ?? [];
  const stages = chainValidation?.billing?.stages ?? [];
  const total = Number(po.total_amount ?? 0);

  // Compute billed so far from stages
  const billedSoFar = stages.reduce((sum, s) => sum + (s.invoiced_amount ?? 0), 0);
  const outstanding = Math.max(0, total - billedSoFar);
  const billedPct   = total > 0 ? Math.round((billedSoFar / total) * 100) : 0;

  // Milestone editor state (inline, simple)
  const [editingMilestones, setEditingMilestones] = useState(false);
  const [draftMilestones, setDraftMilestones] = useState<BillingMilestone[]>(milestones);

  function saveMilestones() {
    onUpdate({ billing_milestones: draftMilestones });
    setEditingMilestones(false);
  }

  function addMilestone() {
    setDraftMilestones(prev => [
      ...prev,
      { name: '', percentage: 0, trigger: '', due_date: null },
    ]);
  }

  function updateDraft(i: number, field: keyof BillingMilestone, value: string | number | null) {
    setDraftMilestones(prev => prev.map((m, idx) => idx === i ? { ...m, [field]: value } : m));
  }

  function removeDraft(i: number) {
    setDraftMilestones(prev => prev.filter((_, idx) => idx !== i));
  }

  return (
    <div>
      {/* ── Type selector ── */}
      <div className="bg-white border border-[--veil] rounded-xl p-4 mb-4 flex items-center gap-4">
        <span className="text-xs font-bold text-gray-500">Billing Type:</span>
        <div className="flex gap-1.5">
          {(['full', 'staged', 'recurring'] as const).map(t => (
            <button
              key={t}
              onClick={() => onUpdate({ billing_type: t })}
              className={clsx(
                'text-xs font-semibold px-4 py-2 rounded-lg border transition-colors',
                billingType === t
                  ? 'bg-[--accent] text-white border-[--accent]'
                  : 'bg-white text-gray-600 border-[--veil] hover:border-[--accent]',
              )}
            >
              {TYPE_LABELS[t]}
            </button>
          ))}
        </div>
        <span className="ml-auto text-[10px] text-gray-400">
          Billing type affects chain completion rules
        </span>
      </div>

      {/* ── KPI cards (shared across all types) ── */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <KpiCard
          label="PO Total" value={`₹${total.toLocaleString('en-IN')}`}
          sub={`${billingType === 'staged' ? `${milestones.length} milestones` : 'Single invoice expected'}`}
          variant="neutral"
        />
        <KpiCard
          label="Billed So Far" value={`₹${billedSoFar.toLocaleString('en-IN')}`}
          sub={`${billedPct}% · ${stages.length} invoice${stages.length !== 1 ? 's' : ''}`}
          variant={billedPct >= 100 ? 'ok' : billedPct > 0 ? 'warn' : 'neutral'}
        />
        <KpiCard
          label="Outstanding" value={`₹${outstanding.toLocaleString('en-IN')}`}
          sub={outstanding === 0 ? 'Fully billed ✓' : 'Remaining to bill'}
          variant={outstanding === 0 ? 'ok' : outstanding === total ? 'bad' : 'warn'}
        />
      </div>

      {/* Progress bar */}
      <div className="mb-5">
        <div className="h-2 bg-[--veil] rounded-full overflow-hidden">
          <div
            className={clsx('h-full rounded-full transition-all', billedPct >= 100 ? 'bg-green-500' : 'bg-[--accent]')}
            style={{ width: `${Math.min(100, billedPct)}%` }}
          />
        </div>
        <div className="text-[10px] text-gray-400 mt-1 text-right">
          ₹{billedSoFar.toLocaleString('en-IN')} of ₹{total.toLocaleString('en-IN')} billed
        </div>
      </div>

      {/* ── FULL view ── */}
      {billingType === 'full' && (
        <div className="bg-white border border-[--veil] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-[--veil]">
                {['Document', 'Ref Number', 'Amount', 'Stage', 'Status'].map(h => (
                  <th key={h} className="px-4 py-2.5 text-left text-[10px] font-bold uppercase tracking-wide text-gray-500">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stages.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-400">
                    No invoices uploaded yet
                  </td>
                </tr>
              )}
              {stages.map((s, i) => (
                <tr key={i} className="border-b border-gray-50 last:border-0">
                  <td className="px-4 py-3 text-gray-700">Invoice {s.stage}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-600">—</td>
                  <td className="px-4 py-3 font-semibold">₹{s.invoiced_amount.toLocaleString('en-IN')}</td>
                  <td className="px-4 py-3 text-gray-500">Stage {s.stage}</td>
                  <td className="px-4 py-3">
                    <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full', STATUS_TAG[s.status] ?? STATUS_TAG.pending)}>
                      {s.status.charAt(0).toUpperCase() + s.status.slice(1)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── STAGED view ── */}
      {billingType === 'staged' && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <span className="text-xs font-bold text-gray-500 uppercase tracking-wide">
              Milestones ({milestones.length})
            </span>
            {!editingMilestones && (
              <button
                onClick={() => { setDraftMilestones(milestones); setEditingMilestones(true); }}
                className="text-xs font-semibold text-[--accent] hover:underline"
              >
                ✏ Edit milestones
              </button>
            )}
          </div>

          {/* Edit mode */}
          {editingMilestones && (
            <div className="bg-[#eef2ff] border border-[#c7d2fe] rounded-xl p-4 mb-4">
              <div className="space-y-2 mb-3">
                {draftMilestones.map((m, i) => (
                  <div key={i} className="grid grid-cols-[2fr_1fr_2fr_auto] gap-2 items-center">
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="Milestone name"
                      value={m.name}
                      onChange={e => updateDraft(i, 'name', e.target.value)}
                    />
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="% e.g. 30"
                      type="number"
                      min={0} max={100}
                      value={m.percentage}
                      onChange={e => updateDraft(i, 'percentage', Number(e.target.value))}
                    />
                    <input
                      className="border border-[--veil] rounded-lg px-2 py-1.5 text-xs"
                      placeholder="Trigger (e.g. On delivery)"
                      value={m.trigger}
                      onChange={e => updateDraft(i, 'trigger', e.target.value)}
                    />
                    <button onClick={() => removeDraft(i)} className="text-red-400 hover:text-red-600 px-1 text-sm">✕</button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={addMilestone}
                  className="text-xs font-semibold text-[--accent] border border-[--accent] px-3 py-1.5 rounded-lg hover:bg-[--accent] hover:text-white transition-colors"
                >
                  + Add milestone
                </button>
                <button
                  onClick={saveMilestones}
                  className="text-xs font-semibold bg-[--accent] text-white px-3 py-1.5 rounded-lg hover:bg-[--accent]/90 transition-colors"
                >
                  Save
                </button>
                <button
                  onClick={() => setEditingMilestones(false)}
                  className="text-xs text-gray-500 px-3 py-1.5"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Milestone table */}
          {milestones.length === 0 && !editingMilestones && (
            <div className="bg-white border border-[--veil] rounded-xl p-6 text-center text-sm text-gray-400">
              No milestones defined yet.{' '}
              <button onClick={() => { setDraftMilestones([]); setEditingMilestones(true); }} className="text-[--accent] font-semibold hover:underline">
                Set up milestones
              </button>
            </div>
          )}

          {milestones.length > 0 && !editingMilestones && (
            <div className="bg-white border border-[--veil] rounded-xl overflow-hidden">
              <div className="grid grid-cols-[2fr_1fr_1fr_1.5fr_1fr] gap-0 bg-gray-50 border-b border-[--veil] px-4 py-2.5">
                {['Milestone', '% / Amount', 'Expected', 'Invoice Ref', 'Status'].map(h => (
                  <div key={h} className="text-[10px] font-bold uppercase tracking-wide text-gray-500">{h}</div>
                ))}
              </div>
              {milestones.map((m, i) => {
                const stage  = stages[i];
                const amt    = total * (m.percentage / 100);
                const status = stage?.status ?? 'pending';
                return (
                  <div
                    key={i}
                    className={clsx(
                      'grid grid-cols-[2fr_1fr_1fr_1.5fr_1fr] gap-0 px-4 py-3 border-b border-gray-50 last:border-0',
                      status === 'mismatch' && 'bg-red-50',
                      status === 'pending'  && 'bg-amber-50/30',
                    )}
                  >
                    <div>
                      <div className="text-sm font-semibold text-[--ink]">{m.name || `Milestone ${i + 1}`}</div>
                      <div className="text-[10px] text-gray-400">{m.trigger}</div>
                    </div>
                    <div>
                      <div className="font-mono text-xs font-semibold">₹{Math.round(amt).toLocaleString('en-IN')}</div>
                      <div className="text-[9px] text-gray-400">{m.percentage}%</div>
                    </div>
                    <div className="text-xs text-gray-500">{m.due_date ?? '—'}</div>
                    <div className="font-mono text-[10px] text-gray-600">
                      {stage ? `Stage ${stage.stage}` : '— Not uploaded'}
                    </div>
                    <div>
                      <span className={clsx('text-[9px] font-bold px-2 py-1 rounded-full', STATUS_TAG[status] ?? STATUS_TAG.pending)}>
                        {status.charAt(0).toUpperCase() + status.slice(1)}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
          <p className="text-[10px] text-gray-400 mt-2">
            💡 Milestone amounts are calculated as PO total × percentage.
          </p>
        </div>
      )}

      {/* ── RECURRING view ── */}
      {billingType === 'recurring' && (
        <div className="bg-white border border-[--veil] rounded-xl p-8 text-center text-gray-400">
          <div className="text-2xl mb-2">📅</div>
          <div className="text-sm font-semibold text-gray-500 mb-1">Recurring billing</div>
          <div className="text-xs">Monthly / quarterly invoice cadence for AMC and service contracts. Configure in a future release.</div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/BillingTab.tsx
git commit -m "feat: add BillingTab component (Full/Staged/Recurring views + milestone editor)"
```

---

## Task 6: Rewrite `PODetailPage.tsx`

Replace the long-scroll layout with tabs. Keep all existing modals (UploadZone, ReviewModal, PDF popup, delete confirms). The chain validation fetch is moved from a `useEffect` + `setState` into a direct `useQuery`.

**Files:**
- Modify: `frontend/src/pages/PODetailPage.tsx`

- [ ] **Step 1: Replace the file contents**

```tsx
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useSearchParams, Link } from 'react-router-dom';
import { Download, Loader2 } from 'lucide-react';
import { useToast } from '@/context/ToastContext';
import { useQueryClient, useQuery, useMutation } from '@tanstack/react-query';
import { usePurchaseOrder, useDeletePO } from '@/hooks/usePurchaseOrders';
import { exportPOAsExcel, getChainValidation, updatePO } from '@/api/purchaseOrders';
import { useReExtract, useCreateManualEntry } from '@/hooks/useExtraction';
import { useDeleteDocument } from '@/hooks/useDocuments';
import Breadcrumb from '@/components/Breadcrumb';
import { LightChainTimeline } from '@/components/LightChainTimeline';
import DocCard from '@/components/DocCard';
import OrderSettingsCard from '@/components/OrderSettingsCard';
import BillingTab from '@/components/BillingTab';
import PDFViewer from '@/components/PDFViewer';
import { getPreviewUrl, getDownloadUrl } from '@/api/documents';
import UploadZone from '@/components/UploadZone';
import ReviewModal from '@/components/ReviewModal';
import type { ChainSlot, ChainStatus, DocumentType, PurchaseOrder } from '@/types';
import { CHAIN_ORDER, DOC_TYPE_LABELS } from '@/types';
import clsx from 'clsx';

type Tab = 'overview' | 'documents' | 'billing';

export default function PODetailPage() {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const showToast = useToast();

  const [activeTab, setActiveTab]         = useState<Tab>('overview');
  const [uploadType, setUploadType]       = useState<DocumentType | null>(null);
  const [reviewDocId, setReviewDocId]     = useState<string | null>(null);
  const [editDocId, setEditDocId]         = useState<string | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(searchParams.get('highlight'));
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [reExtractConfirm, setReExtractConfirm] = useState<string | null>(null);
  const [deleteDocConfirm, setDeleteDocConfirm] = useState<string | null>(null);
  const [deletePOConfirm, setDeletePOConfirm]   = useState(false);
  const [exporting, setExporting] = useState(false);

  const { data: po, isLoading: poLoading } = usePurchaseOrder(id!);

  // Chain status via useQuery (replaces useEffect + setState)
  const chainQuery = useQuery({
    queryKey: ['chain-status', id],
    queryFn: () => getChainValidation(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      // Poll while any slot is extracting
      const chainStatus = query.state.data as ChainStatus | undefined;
      if (!chainStatus) return false;
      const hasExtracting = Object.values(chainStatus.chain as Record<string, ChainSlot[]>)
        .some(slots => slots.some(s => s.status === 'EXTRACTING' || s.status === 'UPLOADED'));
      return hasExtracting ? 3000 : false;
    },
  });
  const chainData       = chainQuery.data;
  const chainValidation = chainData as any; // ChainStatusResponse compat

  const reExtractMutation  = useReExtract();
  const deleteMutation     = useDeleteDocument();
  const deletePOMutation   = useDeletePO();
  const manualEntryMutation = useCreateManualEntry();

  const updatePOMutation = useMutation({
    mutationFn: (patch: Partial<PurchaseOrder>) => updatePO(id!, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['purchase-order', id] });
      queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
      showToast('Saved', 'success');
    },
    onError: () => showToast('Save failed', 'error'),
  });

  // Auto-open review tab when ?review= param is set
  useEffect(() => {
    const reviewParam = searchParams.get('review');
    if (reviewParam) setReviewDocId(reviewParam);
  }, [searchParams]);

  // Extraction toast when polling completes
  const prevExtractingRef = useRef(false);
  const hasExtracting = chainData
    ? Object.values((chainData as any).chain as Record<string, ChainSlot[]>)
        .some(slots => slots.some(s => s.status === 'EXTRACTING' || s.status === 'UPLOADED'))
    : false;
  useEffect(() => {
    if (prevExtractingRef.current && !hasExtracting && chainData) {
      const allSlots = Object.values((chainData as any).chain as Record<string, ChainSlot[]>).flat();
      if (allSlots.some(s => s.status === 'EXTRACTION_FAILED'))
        showToast('Extraction failed — open the document to enter manually.', 'error');
      else if (allSlots.some(s => s.status === 'PENDING_REVIEW'))
        showToast('Extraction complete — documents are ready to review.', 'success');
    }
    prevExtractingRef.current = hasExtracting;
  }, [hasExtracting, chainData]);

  const handleExport = async () => {
    setExporting(true);
    try { await exportPOAsExcel(id!, po!.po_number, 'separate'); }
    catch { showToast('Export failed', 'error'); }
    finally { setExporting(false); }
  };

  // Helpers
  const chain = ((chainData as any)?.chain ?? {}) as Record<string, ChainSlot[]>;
  const missingSlots = (chainData as any)?.missing_slots ?? [];
  const referenceChecks = (chainData as any)?.reference_checks ?? [];
  const billedSoFar = ((chainData as any)?.billing?.stages ?? [])
    .reduce((sum: number, s: any) => sum + (s.invoiced_amount ?? 0), 0);

  // Pending review count for badge
  const pendingCount = Object.values(chain)
    .flat()
    .filter(s => s.status === 'PENDING_REVIEW')
    .length;

  // Find docType for a docId (needed for PDF modal header)
  function findDocType(docId: string): string | null {
    for (const [dt, slots] of Object.entries(chain)) {
      if ((slots as ChainSlot[]).some(s => s.document_id === docId)) return dt;
    }
    return null;
  }

  const handleViewDoc = (docId: string) => {
    setSelectedDocId(docId);
    setSelectedDocType(findDocType(docId));
  };

  // ── Confirm helpers ──────────────────────────────────────────────
  function findDocTypeLabel(docId: string) {
    const dt = findDocType(docId);
    return dt ? (DOC_TYPE_LABELS[dt] ?? dt) : 'document';
  }
  function findDocFilename(docId: string) {
    for (const slots of Object.values(chain)) {
      const found = (slots as ChainSlot[]).find(s => s.document_id === docId);
      if (found) return (found as any).filename ?? null;
    }
    return null;
  }

  if (poLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="animate-spin text-gray-400" size={28} />
      </div>
    );
  }
  if (!po) return <div className="p-8 text-gray-500">PO not found.</div>;

  return (
    <div className="flex flex-col bg-[--paper] min-h-full">
      {/* Breadcrumb */}
      <div className="bg-white border-b border-[--veil] px-6 py-2.5">
        <Breadcrumb items={[{ label: 'Purchase Orders', to: '/purchase-orders' }, { label: po.po_number }]} />
      </div>

      {/* ── PO Header ── */}
      <div className="bg-white border-b border-[--veil] px-6 py-4 flex items-start gap-4 flex-wrap">
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-1.5 flex-wrap">
            <span className="font-mono text-base font-bold text-[--accent]">{po.po_number}</span>
            <span className={clsx(
              'text-[10px] font-bold px-2.5 py-1 rounded-full border',
              po.status === 'COMPLETE' ? 'bg-green-50 text-green-700 border-green-300'
              : po.status === 'CANCELLED' ? 'bg-red-50 text-red-700 border-red-300'
              : 'bg-amber-50 text-amber-700 border-amber-300',
            )}>
              ● {po.status.replace('_', ' ')}
            </span>
            {chainData && (
              <span className={clsx(
                'text-[10px] font-bold px-2.5 py-1 rounded-full border',
                (chainData as any).completeness_pct >= 100
                  ? 'bg-green-50 text-green-700 border-green-300'
                  : 'bg-blue-50 text-blue-700 border-blue-300',
              )}>
                ⬡ Chain {Math.round((chainData as any).completeness_pct ?? 0)}%
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 text-sm flex-wrap">
            <span className="font-medium text-[--ink]">{po.customer_name}</span>
            <span className="text-gray-300">·</span>
            <span className="font-bold text-[--ink]">₹{Number(po.total_amount ?? 0).toLocaleString('en-IN')}</span>
            {po.so_number && (
              <>
                <span className="text-gray-300">·</span>
                <span className="text-xs text-gray-500">SO: <span className="font-mono">{po.so_number}</span></span>
              </>
            )}
          </div>
        </div>
        <div className="flex gap-2 items-center">
          <Link
            to={`/purchase-orders/${id}/profile`}
            className="text-xs font-semibold px-3 py-2 rounded-lg border border-[--veil] text-gray-600 hover:bg-gray-50 transition-colors"
          >
            ↗ Profile
          </Link>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="text-xs font-semibold px-3 py-2 rounded-lg border border-[--veil] text-gray-600 hover:bg-gray-50 transition-colors flex items-center gap-1.5 disabled:opacity-50"
          >
            {exporting ? <Loader2 size={12} className="animate-spin" /> : <Download size={12} />}
            Export
          </button>
        </div>
      </div>

      {/* ── Tab strip ── */}
      <div className="bg-white border-b border-[--veil] px-6 flex gap-0">
        {([
          ['overview',  'Overview',  null],
          ['documents', 'Documents', pendingCount > 0 ? pendingCount : null],
          ['billing',   'Billing',   null],
        ] as [Tab, string, number | null][]).map(([tab, label, badge]) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              'px-5 py-3 text-xs font-semibold border-b-2 -mb-px transition-colors flex items-center gap-1.5',
              activeTab === tab
                ? 'text-[--accent] border-[--accent]'
                : 'text-gray-400 border-transparent hover:text-[--ink]',
            )}
          >
            {label}
            {badge != null && (
              <span className="bg-amber-100 text-amber-700 text-[9px] font-bold px-1.5 py-0.5 rounded-full">
                {badge}
              </span>
            )}
          </button>
        ))}
        <button
          onClick={() => setDeletePOConfirm(true)}
          className="ml-auto px-5 py-3 text-xs font-semibold text-red-400 hover:text-red-600 border-b-2 border-transparent -mb-px transition-colors"
        >
          Delete
        </button>
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 px-6 py-5 max-w-5xl">

        {/* ══ OVERVIEW ══ */}
        {activeTab === 'overview' && (
          <div>
            <OrderSettingsCard
              scenario={po.order_scenario}
              billingType={po.billing_type ?? 'full'}
              billedSoFar={billedSoFar}
              milestoneCount={(po.billing_milestones ?? []).length}
              poTotal={Number(po.total_amount ?? 0)}
              onScenarioChange={val => updatePOMutation.mutate({ order_scenario: val })}
              onBillingTypeChange={val => updatePOMutation.mutate({ billing_type: val })}
            />

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Document Chain
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="mb-5">
              <LightChainTimeline
                chain={chain}
                missingSlots={missingSlots}
                referenceChecks={referenceChecks}
              />
            </div>

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Reference Validation
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="flex flex-wrap gap-2 mb-5">
              {referenceChecks.length === 0 && (
                <span className="text-xs text-gray-400">No reference data — upload documents to validate</span>
              )}
              {referenceChecks.map((rc: any, i: number) => (
                <span
                  key={i}
                  className={clsx(
                    'text-xs font-medium px-3 py-1.5 rounded-lg border flex items-center gap-1.5',
                    rc.result === 'pass'     && 'bg-green-50 border-green-300 text-green-700',
                    rc.result === 'mismatch' && 'bg-red-50 border-red-300 text-red-700',
                    rc.result === 'skip'     && 'bg-gray-50 border-gray-200 text-gray-500',
                  )}
                >
                  {rc.result === 'pass' ? '✓' : rc.result === 'mismatch' ? '✗' : '○'}
                  {' '}{rc.check}
                </span>
              ))}
            </div>

            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-2 flex items-center gap-2">
              Billing Summary
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            <div className="bg-white border border-[--veil] rounded-xl p-4">
              <div className="grid grid-cols-3 gap-3 mb-3">
                {[
                  { label: 'PO Total',      val: `₹${Number(po.total_amount ?? 0).toLocaleString('en-IN')}`, cls: '' },
                  { label: 'Billed So Far', val: `₹${billedSoFar.toLocaleString('en-IN')}`, cls: 'text-amber-700' },
                  { label: 'Outstanding',   val: `₹${Math.max(0, Number(po.total_amount ?? 0) - billedSoFar).toLocaleString('en-IN')}`, cls: 'text-red-600' },
                ].map(k => (
                  <div key={k.label} className="border border-[--veil] rounded-lg p-3">
                    <div className="text-[9px] font-bold uppercase tracking-wide text-gray-400">{k.label}</div>
                    <div className={clsx('text-sm font-bold mt-1', k.cls || 'text-[--ink]')}>{k.val}</div>
                  </div>
                ))}
              </div>
              <button
                onClick={() => setActiveTab('billing')}
                className="text-xs font-semibold text-[--accent] hover:underline"
              >
                → View full billing detail
              </button>
            </div>
          </div>
        )}

        {/* ══ DOCUMENTS ══ */}
        {activeTab === 'documents' && (
          <div className="flex flex-col gap-2">
            <div className="text-[10px] font-bold uppercase tracking-wide text-gray-400 mb-1 flex items-center gap-2">
              {CHAIN_ORDER.length} Document Types
              <span className="flex-1 h-px bg-[--veil]" />
            </div>
            {CHAIN_ORDER.map(docType => {
              const slots = chain[docType] ?? [];
              const slot  = slots[0] ?? null;
              return (
                <DocCard
                  key={docType}
                  docType={docType}
                  label={DOC_TYPE_LABELS[docType] ?? docType}
                  slot={slot}
                  onUpload={() => setUploadType(docType as DocumentType)}
                  onReview={docId => setReviewDocId(docId)}
                  onView={docId => handleViewDoc(docId)}
                  onReExtract={docId => setReExtractConfirm(docId)}
                  onEditFields={docId => setEditDocId(docId)}
                  onDelete={docId => setDeleteDocConfirm(docId)}
                />
              );
            })}
          </div>
        )}

        {/* ══ BILLING ══ */}
        {activeTab === 'billing' && (
          <BillingTab
            po={po}
            chainValidation={chainValidation}
            onUpdate={patch => updatePOMutation.mutate(patch)}
          />
        )}
      </div>

      {/* ── PDF popup modal ── */}
      {selectedDocId && (() => {
        const previewUrl  = getPreviewUrl(selectedDocId);
        const downloadUrl = getDownloadUrl(selectedDocId);
        const label = selectedDocType
          ? (DOC_TYPE_LABELS[selectedDocType as keyof typeof DOC_TYPE_LABELS] ?? selectedDocType)
          : 'Document';
        const slot = Object.values(chain).flat().find(s => s.document_id === selectedDocId);
        return (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
            onClick={() => setSelectedDocId(null)}
          >
            <div
              className="bg-white rounded-xl shadow-2xl flex flex-col"
              style={{ width: '90vw', height: '90vh' }}
              onClick={e => e.stopPropagation()}
            >
              <div className="flex items-center justify-between px-5 py-3 border-b border-gray-200 shrink-0">
                <div>
                  <span className="font-semibold text-sm">{label}</span>
                  {slot?.ref_no && (
                    <span className="ml-2 font-mono text-xs text-gray-500">{slot.ref_no}</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <a href={downloadUrl} download className="text-xs font-semibold text-[--accent] flex items-center gap-1 hover:underline">
                    <Download size={12} /> Download
                  </a>
                  <button onClick={() => setSelectedDocId(null)} className="text-gray-400 hover:text-gray-600 text-lg leading-none">✕</button>
                </div>
              </div>
              <div className="flex-1 min-h-0">
                <PDFViewer url={previewUrl} />
              </div>
            </div>
          </div>
        );
      })()}

      {/* ── Upload modal ── */}
      {uploadType && (
        <UploadZone
          poId={id!}
          docType={uploadType}
          onClose={() => setUploadType(null)}
          onUploaded={() => {
            setUploadType(null);
            queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
          }}
        />
      )}

      {/* ── Review modal ── */}
      {reviewDocId && (
        <ReviewModal
          documentId={reviewDocId}
          mode="review"
          onClose={() => {
            setReviewDocId(null);
            queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
          }}
          onVerified={() => {
            setReviewDocId(null);
            queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
            queryClient.invalidateQueries({ queryKey: ['purchase-order', id] });
          }}
        />
      )}

      {/* ── Edit fields modal ── */}
      {editDocId && (
        <ReviewModal
          documentId={editDocId}
          mode="edit"
          onClose={() => setEditDocId(null)}
          onVerified={() => {
            setEditDocId(null);
            queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
          }}
        />
      )}

      {/* ── Re-extract confirm ── */}
      {reExtractConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-[--ink] mb-1">
              Re-extract {findDocTypeLabel(reExtractConfirm)}?
            </h3>
            {findDocFilename(reExtractConfirm) && (
              <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">
                {findDocFilename(reExtractConfirm)}
              </p>
            )}
            <p className="text-sm text-gray-500 mb-4">
              The document will be reprocessed by the AI. Existing extracted data will be replaced.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setReExtractConfirm(null)} className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => {
                  reExtractMutation.mutate(reExtractConfirm, {
                    onSuccess: () => {
                      setReExtractConfirm(null);
                      queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
                      showToast('Re-extraction queued', 'success');
                    },
                    onError: () => showToast('Re-extraction failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--accent] text-white rounded-lg hover:bg-[--accent]/90"
              >
                Re-extract
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete document confirm ── */}
      {deleteDocConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-[--ink] mb-1">
              Delete {findDocTypeLabel(deleteDocConfirm)}?
            </h3>
            {findDocFilename(deleteDocConfirm) && (
              <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">
                {findDocFilename(deleteDocConfirm)}
              </p>
            )}
            <p className="text-sm text-gray-500 mb-4">
              This will permanently delete the document. You can re-upload at any time.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeleteDocConfirm(null)} className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => {
                  deleteMutation.mutate(deleteDocConfirm, {
                    onSuccess: () => {
                      setDeleteDocConfirm(null);
                      queryClient.invalidateQueries({ queryKey: ['chain-status', id] });
                      showToast('Document deleted', 'success');
                    },
                    onError: () => showToast('Delete failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--signal] text-white rounded-lg hover:bg-[--signal]/90"
              >
                Yes, Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Delete PO confirm ── */}
      {deletePOConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-bold text-red-600 mb-2">Delete this Purchase Order?</h3>
            <p className="font-mono text-xs text-gray-500 bg-gray-50 rounded px-2 py-1 mb-3">{po.po_number}</p>
            <p className="text-sm text-gray-500 mb-4">
              This will permanently delete the PO and all associated documents. This cannot be undone.
            </p>
            <div className="flex gap-2 justify-end">
              <button onClick={() => setDeletePOConfirm(false)} className="px-4 py-2 text-sm text-gray-600 border border-[--veil] rounded-lg hover:bg-gray-50">Cancel</button>
              <button
                onClick={() => {
                  deletePOMutation.mutate(id!, {
                    onSuccess: () => navigate('/purchase-orders'),
                    onError: () => showToast('Delete failed', 'error'),
                  });
                }}
                className="px-4 py-2 text-sm font-semibold bg-[--signal] text-white rounded-lg hover:bg-[--signal]/90"
              >
                Yes, Delete PO
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Check TypeScript compilation**

```bash
cd "frontend" && npx tsc --noEmit 2>&1 | head -40
```

Fix any type errors before proceeding. Common issues:
- `useChainStatus` removed — replace with direct `useQuery` (done in the code above)
- `ChainStatusResponse` vs `ChainStatus` confusion — `chainValidation` is cast as `any` to bridge both shapes

- [ ] **Step 3: Run the dev server and manually verify all 5 flows**

```bash
cd "frontend" && npm run dev
```

Then open `http://localhost:5174/purchase-orders/<any-real-id>`.

**Checklist:**
- [ ] Overview tab: chain nodes show correct colours + ref numbers
- [ ] Overview tab: scenario "Change ▾" expands and selecting updates the chip
- [ ] Overview tab: billing type buttons update and show summary line
- [ ] Documents tab: 6 cards render; missing ones show dashed + Upload button; pending ones show Review → button
- [ ] Documents tab: ⋯ menu opens and actions fire correct handlers
- [ ] Billing tab: Full / Staged / Recurring toggle switches views
- [ ] Billing tab: "Edit milestones" on Staged view opens inline editor; Save calls updatePO
- [ ] PDF popup: clicking View → opens 90vw×90vh modal; backdrop click closes
- [ ] Delete doc modal: shows docType label + filename
- [ ] Delete PO modal: shows PO number

- [ ] **Step 4: Build check**

```bash
cd "frontend" && npm run build 2>&1 | tail -20
```

Expected: no errors, build succeeds.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/PODetailPage.tsx
git commit -m "feat: rewrite PODetailPage with tabbed layout (Overview/Documents/Billing)"
```

---

## Final Step: Cleanup

- [ ] **Remove ChainStatusBar import from PODetailPage if no longer used**

```bash
grep -n "ChainStatusBar\|useChainStatus" frontend/src/pages/PODetailPage.tsx
```

If any remain, remove the import lines.

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat: PO Detail redesign — tabbed layout, scenario selector, staged billing milestone editor"
```
