# DPP Workflow Architecture
**Last Updated:** 2026-04-19

---

## 1. Workflow Goal

The platform exists to move a purchase order from initial registration to operational completion with a trustworthy supporting document chain.

That workflow has both machine and human stages:

- machine stages: ingestion, extraction, validation support, search indexing
- human stages: review, correction, discrepancy resolution, closure

---

## 2. Main Actors

### Operator

Primary responsibilities:

- create and maintain POs
- upload documents
- review extracted data
- correct or reject documents
- monitor missing chain pieces

### Manager

Primary responsibilities:

- override PO settings when required
- evaluate PO profile and discrepancy state
- set or confirm SO information
- close orders manually when operationally justified

### Admin

Primary responsibilities:

- monitor infrastructure and queue health
- inspect failures
- requeue held documents

---

## 3. End-To-End Workflow

### Stage 1: Customer setup

A customer record must exist before an order can be created under it.

### Stage 2: PO creation

The operator creates the PO and establishes the initial business shell:

- customer
- PO number
- date
- total amount

The PO now exists, but no document chain evidence exists yet.

### Stage 3: Document intake

The operator uploads a PDF or uses manual-entry flow for a document type under the PO.

This stage creates the input material for the rest of the workflow.

### Stage 4: Asynchronous extraction

The system attempts extraction in the background and moves the document into one of several next states:

- `PENDING_REVIEW`
- `PENDING_MODEL`
- `EXTRACTION_FAILED`

This stage is asynchronous because extraction is too expensive and failure-prone to run inside the request path.

### Stage 5: Human review

The operator checks extracted values against the document source and either:

- verifies the document
- corrects then verifies the document
- rejects the document

This is the main trust boundary for structured data.

### Stage 6: PO-level validation

Once documents accumulate, the system evaluates the order as a whole:

- required slots by scenario
- missing documents
- reference mismatches
- billing completeness
- cross-document comparison signals
- item-level integrity signals

### Stage 7: Resolution

The team resolves outstanding issues by:

- uploading missing files
- correcting bad data
- re-extracting documents
- setting or fixing SO numbers
- updating scenario or GST assumptions where necessary

### Stage 8: Closure

A manager closes the order when operations are complete, even if the document chain is not perfectly pristine.

This reflects operational reality rather than idealized workflow purity.

---

## 4. Scenario-Aware Chain Logic

Document requirements depend on the order scenario.

### Main scenarios

- stock
- procurement
- drop-ship
- service/AMC
- unknown

### Workflow implication

The system does not ask for the same documents in every case. It computes completeness against the scenario-specific required chain.

That affects:

- which slots are shown as required
- completeness percentage
- profile rendering
- discrepancy interpretation
- closure expectations

Optional documents can still appear and contribute useful evidence without blocking completion.

---

## 5. Document Status Workflow

The main document lifecycle is:

```text
UPLOADED -> EXTRACTING -> PENDING_REVIEW -> VERIFIED
                                  |-> PENDING_MODEL
                                  |-> EXTRACTION_FAILED
PENDING_REVIEW -> REJECTED
```

### Meaning of statuses

- `UPLOADED`: file stored, waiting for processing
- `EXTRACTING`: worker is processing the document
- `PENDING_REVIEW`: structured output is ready for human review
- `VERIFIED`: operator accepted the document data
- `REJECTED`: operator marked it unsuitable
- `PENDING_MODEL`: model dependency unavailable
- `EXTRACTION_FAILED`: extraction did not yield usable output

The workflow is designed so operators can distinguish system problems from document problems.

---

## 6. PO Validation Workflow

The PO workflow does not end when documents are verified individually. The system still needs to answer whether the order, as a whole, makes sense.

### Main PO-level checks

- required document presence
- SO consistency
- customer PO reference consistency
- vendor PO coverage
- billing completeness
- discrepancy summaries
- item comparisons across documents

### Why this exists

A set of individually reviewed documents can still fail as a business chain. The PO-level layer exists to catch those system-level inconsistencies.

---

## 7. Manual Intervention Points

Human intervention is intentionally supported at multiple points.

### Operator interventions

- correct extracted fields
- add manual fields
- edit item arrays
- reject incorrect documents
- trigger re-extraction

### Manager interventions

- set SO number
- override scenario
- override GST type
- toggle invoice split and related PO settings
- close order with note

### Admin interventions

- requeue held documents
- inspect infrastructure failures
- monitor queue and extraction health

This is an operational workflow system, so manual intervention is a feature, not an exception.

---

## 8. Search And Retrieval Workflow

Search is available across the lifecycle, not only after closure.

Users can retrieve information by:

- reference number
- PO number
- customer
- document type
- date range
- address-related fields

That allows the system to function as both a workflow engine and an operational retrieval tool.

---

## 9. Assistant Workflow

The assistant is an optional retrieval and summarization layer over the workflow.

It allows users to:

- ask general operational questions
- attach a PO context
- receive streamed responses

Architecturally, this is an auxiliary workflow surface, not the system’s primary control path.

---

## 10. Workflow Principles

The workflow is built around these assumptions:

- a PO is the unit of business truth
- a document is evidence, not the final truth on its own
- AI extraction accelerates work but does not bypass review
- validation happens at both document and PO level
- operational completion may require human judgment

Those principles explain most of the design choices elsewhere in the codebase.
