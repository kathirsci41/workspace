# Order Assurance — Claude Code Instructions

## 1. Active application

This is the **standalone Order Assurance application**.

Project root: `E:\PROJECTS\Experiments\Logistic\ODMP\order-assurance`

All implementation work happens inside this root only.

## 2. Implementation target

Edit only files inside this project root:

```
order-assurance/
  backend/      ← Python/FastAPI backend, SQLite, extraction service
  frontend/     ← React/Vite frontend
  migrations/   ← SQL migration files
  scripts/      ← Validation run scripts
```

## 3. Do not edit the parent ODMP backend

The directory `E:\PROJECTS\Experiments\Logistic\ODMP\backend` is a separate legacy backend.

It may be read for reference only. Never edit files inside it.

## 4. Mandatory phase test gate

Every implementation phase must complete **all five steps** and include the results in the phase report before the phase is declared done.

### Step 1 — Focused tests

Run the unit/integration tests specific to the changed area and show the result.

### Step 2 — Migration tests (if schema changed)

```
cd backend
python -m pytest tests/integration/test_migrations.py -q
```

### Step 3 — Full backend test suite

```
cd backend
python -m pytest tests -q
```

The report must include the exact pass/skip/fail count. "Tests pass" without a count is not accepted.

### Step 4 — Fresh validation run (if migrations changed)

From project root:
```
.\scripts\new-validation-run.ps1 -RunName <phase-name>-smoke
```

Verify the resulting DB contains the expected tables and applied migrations.

### Step 5 — Confirm no unrelated behavior changed

State explicitly that extraction, parser, OCR, verification, export, and frontend behavior were not changed. If any of these were changed, step 6 is required.

## 5. Real-document validations (required if extraction/parser/OCR/verification/export/frontend changes)

Run and report results for all three accepted fixtures:

| Fixture | Accepted baseline |
|---|---|
| **Panimalar** | 24/24 fields, zero failed document statuses, XLSX passed, vendor partial billing is the only open issue |
| **Trade** | Zero failed document statuses, XLSX passed |
| **AMC** | 27/28 fields, missing Delivery Challan only, vendor side PASS, XLSX passed |

Accepted validation runs for reference:
- Panimalar: `validation-runs/real-doc-001-tradefix-final8`
- Trade: `validation-runs/real-doc-002-trade-fix7`
- AMC: `validation-runs/real-doc-003-amc-fix1`

## 6. No phase is complete without test results

A phase report that omits any required test step is not complete. Do not declare a phase done or ask for approval without showing all required test output.
