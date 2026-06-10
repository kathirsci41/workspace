# Migration Notes

## Copied And Refactored Modules

- `document_normalizer.py`
- `order_bundle_verifier.py`
- `structured_text_parser.py`
- `digital_text_extractor.py`

## Removed Legacy Coupling

The copied modules no longer import:

- `backend.app.models.*`
- `backend.app.schemas.*`
- `backend.app.services.*`
- old frontend pages/components
- old PO detail chain widgets
- old billing widgets
- `validation_agent.py`

Local replacements were added for document enums, address parsing, reference cleaning, audit creation, and reference indexing.

## Deferred To Phase 2

- Database-backed repositories
- Upload API
- Extraction job orchestration
- Document review UI
- Manual metadata patch API route
- Excel export API
- Authentication/RBAC
