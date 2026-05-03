# DPP Frontend Architecture
**Last Updated:** 2026-04-19

---

## 1. Frontend Role

The frontend is an operator-facing workflow console.

Its job is not merely to visualize database rows. It needs to expose:

- document intake
- extraction progress
- PDF-assisted review
- PO-level reconciliation
- discrepancy visibility
- search and triage
- admin recovery actions
- assistant interaction

That makes it a workflow UI around backend state, not a simple CRUD dashboard.

---

## 2. Main Frontend Structure

### Entry files

- `frontend/src/main.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/layout/AppShell.tsx`

### Main folders

- `frontend/src/api/`: HTTP client wrappers
- `frontend/src/hooks/`: TanStack Query hooks
- `frontend/src/pages/`: route pages
- `frontend/src/components/`: shared UI and workflow components
- `frontend/src/context/`: app-level providers such as toasts
- `frontend/src/types/`: shared TypeScript contracts

---

## 3. State And Data Fetching Model

The frontend keeps a fairly simple state architecture.

### Server state

TanStack Query is used for:

- caching
- invalidation
- polling
- mutation status

This is the primary state model for domain data.

### Local UI state

`useState` is used for:

- modal visibility
- active tabs
- form state
- filter state
- selected documents
- temporary review inputs

### HTTP client

Axios is wrapped in a shared client with a response interceptor.

Important behavior:

- network and server failures produce toast feedback
- aborted requests stay silent
- infrastructure failures are surfaced in operator-friendly terms

---

## 4. Route Architecture

The app is route-driven and wrapped by a shared shell.

### Main routes

- `/`
- `/customers`
- `/purchase-orders`
- `/purchase-orders/:id`
- `/purchase-orders/:id/profile`
- `/documents`
- `/documents/:id`
- `/search`
- `/admin`
- `/chat`

### Shared shell behavior

`AppShell` owns:

- sidebar navigation
- collapse state
- top header
- inline search
- route outlet rendering

This keeps the layout stable while the operational pages change underneath.

---

## 5. Type Layer

The frontend mirrors a large backend contract in `frontend/src/types/index.ts`.

That file is architecturally important because it reveals the true scope of the app:

- PO and document entities
- metadata shape
- chain slot structure
- profile structures
- billing milestones
- search result types
- correction and verification payloads

This is a strongly backend-shaped frontend. Most page complexity comes from domain state richness rather than heavy client-only logic.

---

## 6. Main Page Responsibilities

### PO List Page

Primary role:

- intake queue and prioritization view

Main behaviors:

- search by PO or SO
- filter by customer and status
- date range filtering
- completeness filtering
- missing-document filtering
- sorting
- PO creation

### PO Detail Page

Primary role:

- day-to-day operations for a single PO

Main behaviors:

- fetch PO details
- poll chain state while extraction is active
- launch uploads
- open review flow
- display and highlight selected documents
- show billing and chain status
- trigger export and deletion actions

### PO Profile Page

Primary role:

- full-order reconciliation and control view

Main behaviors:

- visualize document slots
- expose scenario and GST overrides
- toggle invoice-split and item verification
- show discrepancy panels
- show field and item comparisons
- show vendor breakdowns
- show timeline
- close order manually

This is one of the most domain-heavy pages in the application.

### Documents Page

Primary role:

- cross-PO document queue

Main behaviors:

- filter by type, status, customer, and date
- jump into review for pending documents
- navigate back to the owning PO

### Document Detail Page

Primary role:

- document-centric inspection view

Main behaviors:

- PDF preview
- metadata summary
- review shortcut
- file download

### Search Page

Primary role:

- operational retrieval

Main behaviors:

- global reference search
- advanced structured filters
- address search

### Admin Page

Primary role:

- operational observability and recovery

Main behaviors:

- poll service health
- show queue state
- show pipeline counters
- show failed and active documents
- requeue held documents

### Chat Page

Primary role:

- assistant interaction with optional PO context

Main behaviors:

- stream messages over SSE
- select PO context
- render markdown-like assistant output
- support operational quick prompts

---

## 7. Query And Mutation Pattern

The common frontend pattern is:

1. page-level hook fetches domain state
2. mutation runs through a hook or API wrapper
3. success invalidates affected queries
4. UI rehydrates from server state

This keeps most business truth on the backend and avoids large local client-side stores.

That is the right fit for this product because workflow correctness matters more than optimistic client complexity.

---

## 8. Review Architecture

The review flow is one of the most important frontend subsystems.

### Central component

- `frontend/src/components/ReviewModal.tsx`

### Responsibilities

- load metadata for a document
- render editable extracted fields
- show validation errors and warnings
- show per-field confidence
- allow manual-entry mode
- preserve and edit array fields like `order_items`
- support custom fields
- handle SO-number prompting and re-verification
- verify or reject the document
- persist correction audit records

### Why it matters

This component embodies the product’s trust model:

- AI suggests
- operator verifies
- system records

Any major workflow change usually touches this component or its related hooks and APIs.

---

## 9. PDF And Document Interaction

PDF interaction is a first-class workflow concern.

Important related components include:

- `PDFViewer`
- `PDFPreviewPanel`
- document cards and profile document sections

These components are not decorative. They exist because operators need side-by-side comparison between source documents and structured extraction output.

---

## 10. Frontend Complexity Profile

The frontend framework usage is relatively conventional.

The real complexity comes from the number of operational states that must be expressed clearly:

- upload states
- extraction states
- review states
- validation errors and warnings
- chain slot states
- completeness states
- discrepancy states
- admin health states
- assistant streaming states

That means frontend changes should prioritize workflow clarity over flashy UI abstraction.

---

## 11. Design Constraints

When changing the frontend, preserve these assumptions:

- backend remains the source of truth
- review is the trust boundary
- PO pages are primary workflows
- document views should always lead back into PO context
- extraction and validation states must remain visible
- admin and search should remain operationally useful, not decorative

Those constraints are more important than incidental component structure.
