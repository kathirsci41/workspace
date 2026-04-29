# Architecture Docs

This directory is the current architecture set for DPP.

These documents replace the older dated architecture notes that had started to drift from the codebase.

## Reading Order

1. `system-architecture.md`
2. `backend-architecture.md`
3. `frontend-architecture.md`
4. `workflow-architecture.md`

## What Each Document Covers

- `system-architecture.md`: product purpose, runtime topology, core data model, system boundaries
- `backend-architecture.md`: FastAPI, services, models, extraction pipeline, background processing
- `frontend-architecture.md`: React app structure, page responsibilities, query/state patterns, review flow
- `workflow-architecture.md`: end-to-end business and operator workflows across PO creation, upload, extraction, review, validation, and closure

## Source Of Truth Rule

When architecture docs and code disagree:

1. trust the code
2. update these files
3. treat older non-architecture docs as secondary until aligned
