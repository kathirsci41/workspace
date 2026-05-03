# DPP UI/UX Test Report
**Date:** 2026-04-20  
**Method:** Live browser inspection using Playwright against the locally running application  
**Context:** On-prem rollout readiness review

---

## 1. Scope

This review focused on the main operator and admin flows visible in the live application:

- Dashboard
- Purchase Orders list
- PO detail
- PO profile
- Documents queue
- Review flow
- Admin/System page

The goal was not visual polish review in isolation. The goal was to assess whether the UI and UX support a reliable operational rollout.

---

## 2. Summary Verdict

The UI has a strong operational structure and the overall navigation model is usable, but the current UX is not rollout-clean yet.

### High-level result

- navigation and page structure: good
- workflow coverage: good
- operational clarity: mostly good
- runtime stability of key pages: not yet good enough
- data presentation consistency: not yet good enough

### UI/UX rollout verdict

**Status:** `Usable with important defects`

The app is usable enough to understand the workflow, but some issues on key PO pages are too visible for a polished rollout.

---

## 3. What Works Well

### 3.1 Navigation model is clear

The left navigation is simple and understandable:

- Dashboard
- Customers
- Purchase Orders
- Documents
- Search
- Assistant
- System

This is a good structure for an operations application because users can move between queue views, record-level views, and admin views without guessing.

### 3.2 Dashboard supports triage

The dashboard gives useful first-glance operational signals:

- total customers
- total POs
- pending reviews
- verified documents
- total documents
- pending queue table
- recent PO list

This makes the page operationally relevant instead of decorative.

### 3.3 PO list is practical

The PO list page is one of the better screens in the product.

It provides:

- search
- customer filtering
- status filtering
- date range filtering
- sort options
- completeness filtering
- missing-document filtering

This is a strong internal-workflow page and feels appropriate for daily use.

### 3.4 Documents page is useful as a work queue

The Documents page works well conceptually as a cross-PO queue:

- type filter
- status filter
- customer filter
- uploaded-date presets
- clear “Review” and “Open PO” actions

This supports real operator work.

### 3.5 Admin page is strong

The System/Admin page is one of the strongest parts of the UI.

It shows:

- system health
- document pipeline counters
- failure state
- active work state
- queue state

This is exactly the kind of visibility an on-prem internal application needs.

### 3.6 Review flow structure is fundamentally correct

The review modal/layout is directionally good:

- source document visible
- extracted values visible
- validation errors and warnings surfaced
- line items editable
- verify/reject actions available

Even with defects, the workflow concept is strong.

### 3.7 Search page is stable and understandable

The Search page performed cleanly in the live review.

Positives:

- simple default search entry
- clear tab switch between reference search and address search
- advanced filters are discoverable without dominating the page

This page feels closer to rollout quality than the PO detail/profile surfaces.

### 3.8 Assistant page has a good initial UX

The Assistant page also loaded cleanly and communicates its purpose well.

Positives:

- clear welcome message
- optional PO context selector
- useful quick prompts
- straightforward message input layout

As a secondary feature, it feels appropriately lightweight.

---

## 4. Main Findings

### Finding 1: Key PO detail and profile pages return backend 500 errors

**Severity:** High  
**Rollout impact:** High

Observed behavior:

- PO detail triggered server-error toasts
- `chain` API calls returned `500`
- PO profile page failed to load entirely for the tested PO

Why this matters:

- PO detail and PO profile are central operational pages
- if they fail on real records, trust in the application drops quickly
- this is not cosmetic; it blocks core user workflow

UX effect:

- user sees repeated generic error toasts
- user does not get enough localized explanation
- page remains partially usable but clearly unstable

This must be resolved before a polished rollout.

---

### Finding 2: Raw structured extraction objects are leaking directly into the UI

**Severity:** High  
**Rollout impact:** High

Observed behavior:

Several pages display extracted reference values as raw object-like strings, for example:

- `{'value': '1ITR2526001785', 'confidence': 1.0}`

This appeared in:

- PO detail chain display
- Documents queue ref number column
- review-related warnings and field displays
- document title area in the review flow

Why this matters:

- users should see business values, not serialized internal payload shapes
- it makes the application feel unfinished
- it adds cognitive noise and undermines confidence in extraction quality

This is one of the most visible UX defects in the current build.

---

### Finding 3: Error messaging is too generic on critical pages

**Severity:** Medium  
**Rollout impact:** High

Observed behavior:

When key requests failed, the UI showed repeated generic toast messages:

- `Server error — please try again.`

Why this matters:

- users cannot tell whether the problem is chain computation, profile loading, model availability, or something else
- repeated generic error toasts feel noisy rather than helpful
- operators need page-local guidance when the page is still partially usable

Recommended UX direction:

- keep toast for awareness
- also show localized inline error context inside the affected panel
- identify the failed module, for example `Chain validation unavailable`

---

### Finding 4: The review flow exposes confusing validation text because values are not normalized consistently

**Severity:** Medium  
**Rollout impact:** Medium to High

Observed behavior:

Warnings in the review flow included messages like:

- date could not be parsed from an object-shaped value
- total amount warning referencing an object-shaped payload

At the same time, some displayed fields were normalized correctly while others still leaked object form.

Why this matters:

- the review screen is the trust boundary of the product
- mixed normalization makes the screen feel inconsistent
- operators may struggle to tell whether the document is wrong or the app is formatting the data badly

The review screen needs stricter presentation normalization.

---

### Finding 5: The PO detail page mixes useful workflow structure with unstable data presentation

**Severity:** Medium  
**Rollout impact:** Medium

What is good:

- header
- tabs
- order scenario area
- billing type controls
- document chain concept

What is weak right now:

- repeated server-error toasts
- raw dict-like values in chain cards
- some monetary values showing as `₹0` on a PO that clearly has active documents and invoice data
- reference-validation area showing no data on a populated order

This page is architecturally correct but currently too brittle in presentation.

---

### Finding 6: Visual consistency is acceptable but version signaling is still messy

**Severity:** Low  
**Rollout impact:** Medium

Observed behavior:

- sidebar still shows `DocPlatform v2.2.0`
- backend and current architecture positioning indicate a newer system state

Why this matters:

- customers and internal stakeholders notice visible version mismatch quickly
- it creates doubt about whether the deployment matches the documentation and build claims

This should be cleaned before rollout.

---

### Finding 7: Open review/PDF state can interfere with primary navigation

**Severity:** Medium  
**Rollout impact:** Medium

Observed behavior:

When the review/PDF view was open, a sidebar navigation click was intercepted by the PDF canvas layer instead of completing normally.

Why this matters:

- users should never feel trapped inside a modal-like document state
- navigation must remain reliable during heavy review work
- this especially matters in real operations, where users move frequently between queue and record screens

This should be fixed so overlays, canvases, or review panels do not block primary navigation interactions.

---

## 5. UX Maturity Assessment

### Navigation and layout

**Rating:** `8/10`

The app layout is clear and operationally sensible.

### Workflow clarity

**Rating:** `7/10`

The workflows make sense, but runtime defects and leaked internal data structures reduce trust.

### Data presentation quality

**Rating:** `5/10`

Core pages still expose internal extraction representations too directly.

### Error handling UX

**Rating:** `5/10`

The app notifies users, but key page failures need more targeted and less repetitive handling.

### Search UX

**Rating:** `8/10`

The Search page is clean, focused, and operationally understandable.

### Assistant UX

**Rating:** `7.5/10`

The Assistant page is simple and readable, with a good initial prompt structure.

### Admin UX

**Rating:** `8/10`

The admin page is strong and rollout-relevant.

### Overall UI/UX readiness

**Rating:** `6.5/10`

The product is operationally understandable and usable, but not yet polished enough to call the UX rollout-clean.

---

## 6. Recommended Fix Priorities

### Priority 1: Must fix before rollout

- fix backend `500` errors affecting PO detail and PO profile
- stop raw extraction-object strings from leaking into UI
- improve localized error handling on key operational pages

### Priority 2: Should fix before rollout

- normalize review warnings and displayed field values consistently
- verify monetary and summary fields on PO detail/profile
- improve reference-validation visibility for partially loaded states
- ensure review/PDF overlays do not block sidebar and page navigation

### Priority 3: Good to fix before or just after rollout

- align visible version labels
- tighten icon/text consistency
- refine some empty-state and partial-data messaging

---

## 7. Final UI/UX Verdict

The UI/UX foundation is good enough to support the intended workflow.

The application clearly understands its users:

- operators need queue views
- reviewers need source-vs-structured comparison
- managers need PO-level reconciliation
- admins need health and recovery tooling

That is a strong product signal.

However, the current build still has visible runtime and presentation defects on core PO pages. Because of that, the UX is not yet “finished rollout quality.”

### Final verdict

**UI/UX status:** `Promising and usable, but needs targeted stabilization before a polished on-prem rollout`
