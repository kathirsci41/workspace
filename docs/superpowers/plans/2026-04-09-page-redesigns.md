# Page Redesigns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Branch 2 structural redesigns — Customers list new columns + Customer detail page, PO Profile sticky nav + collapsible sections + header restructure + compare drawer + print export.

**Prerequisite:** Branch 1 (`feature/ux-quick-wins`) must be merged to `development` before starting this branch. The `Breadcrumb` component and `usePOProfile` hook created in Branch 1 are used here.

**Architecture:** Two new pages (`CustomerDetailPage`, using existing customer API calls) plus significant but focused changes to the existing `POProfilePage`. No new backend endpoints needed — all data already exists. The PO Profile gets a sticky section nav built with `IntersectionObserver`, collapsible sections using `localStorage` per PO ID, and a compare drawer built as an inline controlled component (no new file needed).

**Tech Stack:** React + TanStack Query + React Router + Tailwind CSS + lucide-react. No new dependencies.

---

## File Map

**Create:**
- `frontend/src/pages/CustomerDetailPage.tsx` — customer detail page with stats + PO table + contact info

**Modify:**
- `frontend/src/App.tsx` — add `/customers/:id` route
- `frontend/src/pages/CustomersPage.tsx` — new columns (PO count, total value, chain health), chevron, row click → `/customers/:id`
- `frontend/src/pages/POProfilePage.tsx` — sticky section nav, header restructure, scenario prominence, collapsible sections, compare drawer, print export
- `frontend/src/api/customers.ts` — add `getCustomerById` and `getCustomerPOs` functions
- `frontend/src/hooks/useCustomers.ts` — add `useCustomerById` and `useCustomerPOs` hooks

---

## Task 1: Customer API — add detail + PO list functions

**Files:**
- Modify: `frontend/src/api/customers.ts`
- Modify: `frontend/src/hooks/useCustomers.ts`

- [ ] **Step 1: Read current customers.ts**

Read `frontend/src/api/customers.ts` to see existing functions before editing.

- [ ] **Step 2: Add `getCustomerById` and `getCustomerPOs` to customers.ts**

```ts
// Add to frontend/src/api/customers.ts:

export async function getCustomerById(id: string): Promise<Customer> {
  const { data } = await client.get(`/api/v1/customers/${id}`);
  return data;
}

export async function getCustomerPOs(
  customerId: string,
  page = 1,
  perPage = 100
): Promise<{ items: PurchaseOrder[]; total: number }> {
  const { data } = await client.get(`/api/v1/customers/${customerId}/purchase-orders`, {
    params: { page, per_page: perPage },
  });
  return data;
}
```

You'll need to add `import type { PurchaseOrder } from '@/types';` if not already imported.

- [ ] **Step 3: Add hooks to useCustomers.ts**

```ts
// Add to frontend/src/hooks/useCustomers.ts:
import { getCustomerById, getCustomerPOs } from '@/api/customers';
import type { Customer } from '@/types';

export function useCustomerById(id: string) {
  return useQuery({
    queryKey: ['customer', id],
    queryFn: () => getCustomerById(id),
    enabled: !!id,
  });
}

export function useCustomerPOs(customerId: string) {
  return useQuery({
    queryKey: ['customerPOs', customerId],
    queryFn: () => getCustomerPOs(customerId),
    enabled: !!customerId,
    staleTime: 30_000,
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/customers.ts frontend/src/hooks/useCustomers.ts
git commit -m "feat: add getCustomerById, getCustomerPOs API + hooks"
```

---

## Task 2: Customers list — new columns, chevron, row click to detail page

**Files:**
- Modify: `frontend/src/pages/CustomersPage.tsx`

The current Customers list shows: Customer ID, Name, GST Number, Email, Phone, Created. The redesign removes GST + Email and adds PO Count, Total Value, Chain Health %. Since these aggregates aren't in the existing customer list API, we need to either:
- Fetch them separately per customer (N+1, bad), or
- Compute on the list from per-page data

**Decision:** Display `—` for PO Count / Value / Health on the list (they're available on the detail page). These fields would need backend aggregate support. Per spec, aggregate stats are computed client-side from the PO list per customer — but that requires a PO list call per customer which is an N+1 problem for the list page. The spec's Customer Detail page does this correctly. For the list, show the columns with `—` data (a progressive enhancement).

Actually, re-reading the spec: "PO Count (integer), Total Value (₹ sum), Chain Health % (avg chain_completeness across POs)". These ARE the redesigned columns. Let me check if the existing API returns them.

Check the customer list endpoint response — it returns basic customer fields (`Customer` type: id, customer_id, name, contact_email, gst_number, address, phone, created_at, updated_at). No PO aggregates.

**Resolution:** Add the column headers, but populate from the existing `Customer` type what's available, and leave PO count/value/health as `—` with a note in the code. The detail page (Task 3) does the full computation. This is the pragmatic approach: columns are visible and the CTA to the detail page is clear.

Wait — this would make the list look broken with all `—`. Let me reconsider. The spec says these columns should show real data. The only way to do this cleanly is:

1. The backend `/api/v1/customers` endpoint needs to return aggregate stats (not in scope per spec — "already exists")
2. Or we accept placeholder data on the list

Since the spec doesn't add new backend for the customer list (it says "already exists" for the detail API), and the list can't get aggregates without N+1, I'll implement the columns with real data by calling `getCustomerPOs` per row — **limited to the current page** (20 customers max). This is acceptable for a small dataset.

**Alternative approach for the plan:** Fetch POs for each customer on the list page using the existing `useCustomerPOs` hook per row, with the data fetched lazily. This is the `CustomerRowStats` component approach.

- [ ] **Step 1: Add CustomerRowStats sub-component**

At the bottom of `CustomersPage.tsx`, add:

```tsx
function CustomerRowStats({ customerId }: { customerId: string }) {
  const { data } = useCustomerPOs(customerId);
  if (!data) return <td className="px-5 py-3 text-gray-400">—</td>;

  const pos = data.items;
  const poCount = data.total;
  const totalValue = pos.reduce((s, p) => s + (p.total_amount ?? 0), 0);
  const avgHealth = pos.length > 0
    ? Math.round(pos.reduce((s, p) => s + p.chain_completeness, 0) / pos.length)
    : 0;

  return (
    <>
      <td className="px-5 py-3 text-gray-700">{poCount}</td>
      <td className="px-5 py-3 text-gray-700">
        {totalValue > 0 ? `₹\u00A0${totalValue.toLocaleString('en-IN')}` : '—'}
      </td>
      <td className="px-5 py-3">
        <span className={clsx(
          'text-xs font-medium px-2 py-0.5 rounded-full',
          avgHealth >= 80 ? 'bg-green-100 text-green-700' :
          avgHealth >= 50 ? 'bg-amber-100 text-amber-700' :
          'bg-red-100 text-red-700'
        )}>
          {avgHealth}%
        </span>
      </td>
    </>
  );
}
```

Add the import at the top of `CustomersPage.tsx`:
```tsx
import { useCustomers, useCreateCustomer, useCustomerPOs } from '@/hooks/useCustomers';
```

- [ ] **Step 2: Replace table headers and row structure**

Replace the `<thead>` row:
```tsx
<tr>
  <th className="text-left px-5 py-3 font-medium">Customer ID</th>
  <th className="text-left px-5 py-3 font-medium">Name</th>
  <th className="text-left px-5 py-3 font-medium">PO Count</th>
  <th className="text-left px-5 py-3 font-medium">Total Value</th>
  <th className="text-left px-5 py-3 font-medium">Chain Health</th>
  <th className="text-left px-5 py-3 font-medium">Created</th>
  <th className="text-left px-5 py-3 font-medium w-6"></th>
</tr>
```

Replace each data row with:
```tsx
{data.items.map((customer) => (
  <tr
    key={customer.id}
    className="hover:bg-gray-50 cursor-pointer"
    title="Click to view customer details"
    onClick={() => navigate(`/customers/${customer.id}`)}
  >
    <td className="px-5 py-3 font-mono text-xs text-gray-600">{customer.customer_id}</td>
    <td className="px-5 py-3 font-medium text-gray-900">{customer.name}</td>
    <CustomerRowStats customerId={customer.id} />
    <td className="px-5 py-3 text-gray-400 text-xs">
      {new Date(customer.created_at).toLocaleDateString('en-IN')}
    </td>
    <td className="px-5 py-3 text-gray-400">
      <ChevronRight size={16} />
    </td>
  </tr>
))}
```

Add `ChevronRight` to lucide-react imports.

- [ ] **Step 3: Update the empty state**

The empty state colspan is now 7:
```tsx
<td colSpan={7} className="px-5 py-8 text-center text-gray-400">
  <p className="mb-2">No customers yet.</p>
  <button
    onClick={() => setShowModal(true)}
    className="text-sm text-blue-600 hover:underline font-medium"
  >
    + Add a customer
  </button>
</td>
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/CustomersPage.tsx
git commit -m "feat: customers list redesign — PO count, value, chain health columns + detail page nav"
```

---

## Task 3: CustomerDetailPage — new page

**Files:**
- Create: `frontend/src/pages/CustomerDetailPage.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add route in App.tsx**

```tsx
import CustomerDetailPage from './pages/CustomerDetailPage';

// Add inside <Route element={<AppShell />}>:
<Route path="/customers/:id" element={<CustomerDetailPage />} />
```

- [ ] **Step 2: Create CustomerDetailPage.tsx**

```tsx
// frontend/src/pages/CustomerDetailPage.tsx
import { useParams, useNavigate, Link } from 'react-router-dom';
import { ArrowRight, Users, FileText, TrendingUp } from 'lucide-react';
import { useCustomerById, useCustomerPOs } from '@/hooks/useCustomers';
import Breadcrumb from '@/components/Breadcrumb';
import clsx from 'clsx';

export default function CustomerDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: customer, isLoading, isError } = useCustomerById(id!);
  const { data: posData } = useCustomerPOs(id!);

  if (isLoading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">Loading...</div>;
  }
  if (isError || !customer) {
    return <div className="flex items-center justify-center h-64 text-red-500">Customer not found.</div>;
  }

  const pos = posData?.items ?? [];
  const totalValue = pos.reduce((s, p) => s + (p.total_amount ?? 0), 0);
  const avgHealth = pos.length > 0
    ? Math.round(pos.reduce((s, p) => s + p.chain_completeness, 0) / pos.length)
    : 0;

  // Show last 10 POs
  const recentPOs = pos.slice(0, 10);

  return (
    <div className="max-w-4xl mx-auto">
      <Breadcrumb items={[
        { label: 'Customers', to: '/customers' },
        { label: customer.name },
      ]} />

      {/* Section 1 — Summary header */}
      <div className="mb-8">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{customer.name}</h2>
            <span className="inline-block mt-1 text-xs font-mono bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
              {customer.customer_id}
            </span>
            {customer.gst_number && (
              <span className="ml-2 text-xs text-gray-500">GST: {customer.gst_number}</span>
            )}
          </div>
          <div className="flex gap-2">
            <Link
              to={`/purchase-orders?customer_id=${customer.id}`}
              className="flex items-center gap-1.5 text-sm text-blue-600 border border-blue-200 px-3 py-1.5 rounded-lg hover:bg-blue-50"
            >
              View all POs <ArrowRight size={14} />
            </Link>
          </div>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-blue-100 text-blue-600">
              <FileText size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Total POs</p>
              <p className="text-xl font-bold">{posData?.total ?? '—'}</p>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-green-100 text-green-600">
              <TrendingUp size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Total Order Value</p>
              <p className="text-xl font-bold">
                {totalValue > 0 ? `₹\u00A0${totalValue.toLocaleString('en-IN')}` : '—'}
              </p>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-100 text-emerald-600">
              <Users size={20} />
            </div>
            <div>
              <p className="text-xs text-gray-500">Avg Chain Health</p>
              <p className="text-xl font-bold">{pos.length > 0 ? `${avgHealth}%` : '—'}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Section 2 — Recent Purchase Orders */}
      <div className="bg-white rounded-lg border border-gray-200 mb-6">
        <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between">
          <h3 className="text-base font-semibold">Recent Purchase Orders</h3>
          <Link
            to={`/purchase-orders?customer_id=${customer.id}`}
            className="text-xs text-blue-600 hover:underline"
          >
            View all →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-600">
              <tr>
                <th className="text-left px-5 py-3 font-medium">PO Number</th>
                <th className="text-left px-5 py-3 font-medium">Date</th>
                <th className="text-left px-5 py-3 font-medium">Amount</th>
                <th className="text-left px-5 py-3 font-medium">Chain %</th>
                <th className="text-left px-5 py-3 font-medium">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {recentPOs.length > 0 ? recentPOs.map((po) => (
                <tr
                  key={po.id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => navigate(`/purchase-orders/${po.id}`)}
                >
                  <td className="px-5 py-3 font-medium text-blue-700">{po.po_number}</td>
                  <td className="px-5 py-3 text-gray-500">{po.po_date ?? '—'}</td>
                  <td className="px-5 py-3 text-gray-700">
                    {po.total_amount != null
                      ? `₹\u00A0${po.total_amount.toLocaleString('en-IN')}`
                      : '—'}
                  </td>
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-2">
                      <div className="w-16 h-1.5 bg-gray-200 rounded-full">
                        <div
                          className={clsx('h-full rounded-full', po.chain_completeness === 100 ? 'bg-green-500' : po.chain_completeness >= 50 ? 'bg-amber-500' : 'bg-blue-500')}
                          style={{ width: `${po.chain_completeness}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">{po.chain_completeness}%</span>
                    </div>
                  </td>
                  <td className="px-5 py-3">
                    <span className={clsx('text-xs font-medium px-2 py-0.5 rounded-full', {
                      INITIATED: 'bg-gray-100 text-gray-700',
                      IN_PROGRESS: 'bg-blue-100 text-blue-700',
                      NEAR_COMPLETE: 'bg-amber-100 text-amber-700',
                      COMPLETE: 'bg-green-100 text-green-700',
                      CANCELLED: 'bg-red-100 text-red-700',
                    }[po.status] ?? 'bg-gray-100 text-gray-700')}>
                      {po.status.replace('_', ' ')}
                    </span>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-gray-400">
                    No purchase orders yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 3 — Contact & Details */}
      <div className="bg-white rounded-lg border border-gray-200 p-5">
        <h3 className="text-base font-semibold mb-4">Contact & Details</h3>
        <div className="grid grid-cols-2 gap-4 text-sm">
          {customer.contact_email && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Email</p>
              <p className="text-gray-800">{customer.contact_email}</p>
            </div>
          )}
          {customer.gst_number && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">GST Number</p>
              <p className="font-mono text-gray-800">{customer.gst_number}</p>
            </div>
          )}
          {customer.phone && (
            <div>
              <p className="text-xs text-gray-400 mb-0.5">Phone</p>
              <p className="text-gray-800">{customer.phone}</p>
            </div>
          )}
          {customer.address && (
            <div className="col-span-2">
              <p className="text-xs text-gray-400 mb-0.5">Address</p>
              <p className="text-gray-800">{customer.address}</p>
            </div>
          )}
          {!customer.contact_email && !customer.gst_number && !customer.phone && !customer.address && (
            <p className="col-span-2 text-gray-400">No contact information on file.</p>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/CustomerDetailPage.tsx frontend/src/App.tsx
git commit -m "feat: new CustomerDetailPage at /customers/:id with stats, PO table, contact info"
```

---

## Task 4: PO Profile — sticky section nav + collapsible sections

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`

This is the largest task. Read `POProfilePage.tsx` fully before editing.

- [ ] **Step 1: Read the current POProfilePage.tsx**

Run: `cat frontend/src/pages/POProfilePage.tsx` to see the current structure before modifying.

- [ ] **Step 2: Add section refs and IntersectionObserver for active nav**

At the top of the `POProfilePage` function, add refs for each section and the observer:

```tsx
import { useRef, useState, useEffect } from 'react';

// Inside the component function:
const [activeSection, setActiveSection] = useState('overview');
const sectionRefs = {
  overview:      useRef<HTMLDivElement>(null),
  discrepancies: useRef<HTMLDivElement>(null),
  checks:        useRef<HTMLDivElement>(null),
  items:         useRef<HTMLDivElement>(null),
  vendors:       useRef<HTMLDivElement>(null),
  documents:     useRef<HTMLDivElement>(null),
  timeline:      useRef<HTMLDivElement>(null),
};

useEffect(() => {
  const observers: IntersectionObserver[] = [];
  Object.entries(sectionRefs).forEach(([key, ref]) => {
    if (!ref.current) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setActiveSection(key); },
      { threshold: 0.2 }
    );
    obs.observe(ref.current);
    observers.push(obs);
  });
  return () => observers.forEach((o) => o.disconnect());
}, [profile]);
```

- [ ] **Step 3: Add collapsible section state stored in localStorage**

```tsx
// Add after sectionRefs:
const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(() => {
  try {
    const stored = localStorage.getItem(`profile-sections-${id}`);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
});

const toggleSection = (key: string) => {
  setCollapsedSections((prev) => {
    const next = { ...prev, [key]: !prev[key] };
    try { localStorage.setItem(`profile-sections-${id}`, JSON.stringify(next)); } catch {}
    return next;
  });
};

const isCollapsed = (key: string) => collapsedSections[key] === true;
```

- [ ] **Step 4: Add the sticky left sidebar nav**

Wrap the entire profile content in a two-column grid. The left column is the sticky nav (hidden on mobile), the right column is the existing profile content:

```tsx
// Wrap the main profile content after breadcrumbs in:
<div className="flex gap-6">
  {/* Sticky sidebar nav — desktop only */}
  <aside className="hidden lg:flex w-40 shrink-0">
    <nav className="sticky top-6 space-y-1 w-full">
      {[
        { key: 'overview',      label: 'Overview' },
        { key: 'discrepancies', label: 'Discrepancies' },
        { key: 'checks',        label: 'Field Checks' },
        { key: 'items',         label: 'Items' },
        { key: 'vendors',       label: 'Vendors' },
        { key: 'documents',     label: 'Documents' },
        { key: 'timeline',      label: 'Timeline' },
      ].map(({ key, label }) => (
        <button
          key={key}
          onClick={() => sectionRefs[key as keyof typeof sectionRefs]?.current?.scrollIntoView({ behavior: 'smooth' })}
          className={clsx(
            'w-full text-left text-sm px-3 py-1.5 rounded-lg transition-colors',
            activeSection === key
              ? 'bg-blue-50 text-blue-700 font-medium'
              : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'
          )}
        >
          {label}
        </button>
      ))}
    </nav>
  </aside>

  {/* Main content */}
  <div className="flex-1 min-w-0 space-y-6">
    {/* ... existing sections ... */}
  </div>
</div>
```

- [ ] **Step 5: Attach refs and collapse toggles to each section**

For each major section in the profile, add the corresponding `ref` and a collapsible header pattern:

```tsx
// Pattern for each section:
<div ref={sectionRefs.discrepancies} id="section-discrepancies">
  <div
    className="flex items-center justify-between cursor-pointer select-none mb-3"
    onClick={() => toggleSection('discrepancies')}
  >
    <h3 className="text-base font-semibold">Discrepancies</h3>
    <div className="flex items-center gap-2">
      {isCollapsed('discrepancies') && (
        <span className="text-xs text-gray-400">
          {profile.discrepancies.length} discrepanc{profile.discrepancies.length !== 1 ? 'ies' : 'y'} — click to expand
        </span>
      )}
      <ChevronDown
        size={16}
        className={clsx('text-gray-400 transition-transform', isCollapsed('discrepancies') && 'rotate-180')}
      />
    </div>
  </div>
  {!isCollapsed('discrepancies') && (
    /* ... existing discrepancy content ... */
  )}
</div>
```

Apply this pattern to: discrepancies, checks (field comparisons), items, vendors, documents, timeline. Leave Overview always expanded.

Import `ChevronDown` from lucide-react.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx
git commit -m "feat: PO Profile sticky section nav, IntersectionObserver active tracking, collapsible sections"
```

---

## Task 5: PO Profile — header restructure + scenario prominence

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`

- [ ] **Step 1: Split header into two rows**

Find the current dense header block and restructure into two rows:

**Row 1 — Identity row** (always visible):
```tsx
<div className="flex flex-wrap items-center gap-3 mb-2">
  <h2 className="text-xl font-bold">{profile.po_number}</h2>
  <StatusBadge status={profile.status} />
  <span className="text-sm text-gray-500">{profile.chain_completeness_display ?? `${profile.chain_completeness}%`}</span>
  {profile.customer_name && <span className="text-sm text-gray-600">· {profile.customer_name}</span>}
  {profile.so_number && <span className="text-sm text-gray-500">SO: {profile.so_number}</span>}
  {profile.po_date && <span className="text-sm text-gray-500">{profile.po_date}</span>}
  {profile.total_amount != null && (
    <span className="text-sm font-medium">₹\u00A0{profile.total_amount.toLocaleString('en-IN')}</span>
  )}
  <div className="ml-auto flex gap-2">
    {/* Export + Close Order buttons (keep as-is from current implementation) */}
  </div>
</div>
```

**Row 2 — Settings row** (collapsible, default collapsed):
```tsx
{/* Settings toggle */}
<button
  onClick={() => toggleSection('header-settings')}
  className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1 mb-3"
>
  <Settings size={13} />
  Order Settings
  <ChevronDown size={12} className={clsx('transition-transform', !isCollapsed('header-settings') && 'rotate-180')} />
</button>
{!isCollapsed('header-settings') && (
  <div className="flex flex-wrap gap-4 pb-3 border-b border-gray-200 mb-4">
    {/* Scenario selector, GST type, invoice split, items verified toggle */}
    {/* Keep the existing controls from the current header */}
  </div>
)}
```

Import `Settings` from lucide-react.

Initialize `header-settings` as collapsed by default:
```tsx
const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>(() => {
  try {
    const stored = localStorage.getItem(`profile-sections-${id}`);
    return stored ? JSON.parse(stored) : { 'header-settings': true };  // ← settings collapsed by default
  } catch {
    return { 'header-settings': true };
  }
});
```

- [ ] **Step 2: Give scenario selector more visual prominence**

Find the scenario selector control (the pill buttons for `order_scenario`). Add a labeled section wrapper:

```tsx
{/* Inside the settings row, wrap scenario selector: */}
<div>
  <label className="text-xs text-gray-500 font-medium block mb-1.5">Scenario</label>
  <div className="flex flex-wrap gap-1">
    {SCENARIO_OPTIONS.map((opt) => (
      <button
        key={opt.value}
        onClick={() => handleScenarioChange(opt.value)}
        className={clsx(
          'px-3 py-1.5 text-sm rounded-full border font-medium transition-colors',
          profile.order_scenario === opt.value
            ? 'bg-blue-600 text-white border-blue-600'
            : 'bg-white text-gray-600 border-gray-300 hover:border-blue-400'
        )}
      >
        {opt.label}
      </button>
    ))}
  </div>
  {profile.order_scenario !== 'unknown' && (
    <p className="text-xs text-gray-400 mt-1">{SCENARIO_DESCRIPTIONS[profile.order_scenario]}</p>
  )}
</div>
```

Add `SCENARIO_DESCRIPTIONS`:
```tsx
const SCENARIO_DESCRIPTIONS: Record<string, string> = {
  procurement: 'All 6 document types required.',
  stock:       'Customer PO + Company DC + Company Invoice only.',
  drop_ship:   'Direct dispatch — Company DC and Vendor documents required.',
  service_amc: 'Service/AMC contract — minimal chain required.',
};
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx
git commit -m "feat: PO Profile header restructure, collapsible settings row, scenario prominence"
```

---

## Task 6: PO Profile — side-by-side document compare drawer

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`

- [ ] **Step 1: Add compare state**

```tsx
// Add inside the component:
const [showCompare, setShowCompare] = useState(false);
const [compareDocA, setCompareDocA] = useState('');
const [compareDocB, setCompareDocB] = useState('');
```

Build the available documents list from `profile.slots`:
```tsx
const availableDocuments = profile.slots.flatMap((slot) =>
  slot.documents.map((doc) => ({
    id: doc.document_id,
    label: `${slot.document_type.replace(/_/g, ' ')} — ${doc.primary_ref_no ?? doc.document_id.slice(0, 8)}`,
    extracted_data: doc.extracted_data ?? {},
  }))
);
```

- [ ] **Step 2: Add Compare button to Documents section header**

Find the Documents section header and add:
```tsx
<div className="flex items-center justify-between mb-3">
  <h3 className="text-base font-semibold">Documents</h3>
  {availableDocuments.length >= 2 && (
    <button
      onClick={() => setShowCompare(true)}
      className="text-xs text-blue-600 border border-blue-200 px-2.5 py-1 rounded-lg hover:bg-blue-50"
    >
      Compare
    </button>
  )}
</div>
```

- [ ] **Step 3: Add the compare drawer/modal**

Add at the end of the main JSX, before the closing tag:

```tsx
{showCompare && (
  <div className="fixed inset-0 z-50 bg-black/50 flex items-end sm:items-center justify-center p-4">
    <div className="bg-white rounded-xl w-full max-w-4xl max-h-[80vh] flex flex-col">
      <div className="px-5 py-4 border-b border-gray-200 flex items-center justify-between shrink-0">
        <h3 className="text-base font-semibold">Compare Documents</h3>
        <button onClick={() => setShowCompare(false)} className="text-gray-400 hover:text-gray-600">
          <X size={20} />
        </button>
      </div>
      <div className="p-5 flex gap-4 shrink-0">
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Document A</label>
          <select
            value={compareDocA}
            onChange={(e) => setCompareDocA(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Select document…</option>
            {availableDocuments.map((d) => (
              <option key={d.id} value={d.id}>{d.label}</option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-500 block mb-1">Document B</label>
          <select
            value={compareDocB}
            onChange={(e) => setCompareDocB(e.target.value)}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
          >
            <option value="">Select document…</option>
            {availableDocuments.map((d) => (
              <option key={d.id} value={d.id}>{d.label}</option>
            ))}
          </select>
        </div>
      </div>
      {compareDocA && compareDocB && compareDocA !== compareDocB && (() => {
        const docA = availableDocuments.find((d) => d.id === compareDocA);
        const docB = availableDocuments.find((d) => d.id === compareDocB);
        if (!docA || !docB) return null;
        const keysA = Object.keys(docA.extracted_data).filter((k) => !k.startsWith('_') && !Array.isArray(docA.extracted_data[k]) && typeof docA.extracted_data[k] !== 'object');
        const keysB = Object.keys(docB.extracted_data).filter((k) => !k.startsWith('_') && !Array.isArray(docB.extracted_data[k]) && typeof docB.extracted_data[k] !== 'object');
        const allKeys = [...new Set([...keysA, ...keysB])];
        return (
          <div className="flex-1 overflow-y-auto px-5 pb-5">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="text-left px-3 py-2 font-medium text-gray-500 w-1/3">Field</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">{docA.label}</th>
                  <th className="text-left px-3 py-2 font-medium text-gray-700">{docB.label}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {allKeys.map((key) => {
                  const valA = docA.extracted_data[key] != null ? String(docA.extracted_data[key]) : '—';
                  const valB = docB.extracted_data[key] != null ? String(docB.extracted_data[key]) : '—';
                  const mismatch = valA !== '—' && valB !== '—' && valA !== valB;
                  return (
                    <tr key={key} className={mismatch ? 'bg-amber-50' : ''}>
                      <td className="px-3 py-2 text-gray-400 capitalize">{key.replace(/_/g, ' ')}</td>
                      <td className={clsx('px-3 py-2', mismatch && 'text-red-600 font-medium')}>{valA}</td>
                      <td className={clsx('px-3 py-2', mismatch && 'text-red-600 font-medium')}>{valB}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        );
      })()}
    </div>
  </div>
)}
```

Import `X` from lucide-react if not already imported.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx
git commit -m "feat: PO Profile document compare drawer"
```

---

## Task 7: PO Profile — print/PDF export

**Files:**
- Modify: `frontend/src/pages/POProfilePage.tsx`
- Modify: `frontend/src/index.css` (or `tailwind.css` — whichever is the global CSS entry point)

- [ ] **Step 1: Add print button to the header**

In the header actions row, alongside the existing Export Excel button, add:
```tsx
<button
  onClick={() => window.print()}
  className="flex items-center gap-1.5 text-sm border border-gray-300 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-50"
>
  <Printer size={15} />
  Print Profile
</button>
```

Import `Printer` from lucide-react.

- [ ] **Step 2: Add print stylesheet**

Find the main CSS file — it's `frontend/src/index.css`. Add at the end:

```css
/* ─── Print styles for PO Profile ─────────────────────────── */
@media print {
  /* Hide navigation and interactive chrome */
  aside,
  header,
  nav,
  .print-hide {
    display: none !important;
  }

  /* Expand all collapsed sections */
  [data-collapsed="true"] > *:not(:first-child) {
    display: block !important;
  }

  /* Full width content */
  body, main, .flex-1 {
    width: 100% !important;
    max-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
  }

  /* Page break hints */
  .profile-section {
    break-inside: avoid;
    page-break-inside: avoid;
  }

  /* Remove shadows and interactive borders */
  * {
    box-shadow: none !important;
  }
}
```

- [ ] **Step 3: Add `print-hide` class to interactive elements**

In `POProfilePage.tsx`, add `className="print-hide"` to:
- The sidebar nav `<aside>`
- The compare drawer trigger button
- The collapse toggle buttons
- The scenario selector row
- The export Excel button (keep Print button visible)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/POProfilePage.tsx frontend/src/index.css
git commit -m "feat: PO Profile print export with @media print stylesheet"
```

---

## Self-Review Checklist

- [x] Customer list new columns — PO Count, Total Value, Chain Health via `CustomerRowStats` sub-component
- [x] Customer list row click → `/customers/:id`
- [x] CustomerDetailPage — breadcrumbs, 3 stat cards, recent PO table, contact section
- [x] CustomerDetailPage — "View all POs →" link to `/purchase-orders?customer_id=X`
- [x] `/customers/:id` route added in App.tsx
- [x] PO Profile sticky nav with IntersectionObserver
- [x] PO Profile collapsible sections with per-PO localStorage key
- [x] PO Profile header split into identity row + collapsible settings row
- [x] Scenario selector has description text below selected option
- [x] Compare drawer uses only data already loaded in profile (no extra API calls)
- [x] Print styles hide sidebar nav, interactive controls, compare button
- [x] `header-settings` defaults to collapsed (initialized in state)

**Note:** `useCustomerPOs` in `CustomerRowStats` triggers N requests per visible customer row. This is acceptable for the current dataset size (typically < 20 customers per page). If this becomes a performance issue, the backend `/api/v1/customers` endpoint should return aggregate stats — that's a Phase 2 backend enhancement.
