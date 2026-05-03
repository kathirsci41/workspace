# Core Operational Files Report

Date: 2026-04-02

Purpose: strict list of operational files required to run/build/deploy the application. Optional and non-operational files are excluded.

Total core entries: 126

## Inclusion Rules

- Include all files listed in this report.
- Exclude tests, docs, logs, debug outputs, benchmark data, and developer-only helper scripts.
- Create a runtime .env file from .env.example with environment-specific values.

## Root And Infra Core Files

- .env.example
- docker-compose.dev.yml
- docker-compose.prod.yml

## Backend Core Files

- backend/alembic.ini
- backend/alembic/env.py
- backend/alembic/versions/6e44882e6975_initial_schema.py
- backend/alembic/versions/a1b2c3d4e5f6_add_company_po_remove_pod.py
- backend/alembic/versions/a3f1c9b2e7d4_add_so_number_to_purchase_orders.py
- backend/alembic/versions/b4c2d8e1f0a9_add_pending_model_status.py
- backend/alembic/versions/c5d3e9f2a1b8_add_performance_indexes.py
- backend/alembic/versions/d1e2f3a4b5c6_add_fulfillment_type_to_purchase_orders.py
- backend/alembic/versions/ff989461aa4f_add_extraction_route_to_metadata.py
- backend/alembic/versions/phase7_versioning.py
- backend/app/__init__.py
- backend/app/api/__init__.py
- backend/app/api/router.py
- backend/app/api/v1/__init__.py
- backend/app/api/v1/admin.py
- backend/app/api/v1/customers.py
- backend/app/api/v1/documents.py
- backend/app/api/v1/extraction.py
- backend/app/api/v1/purchase_orders.py
- backend/app/api/v1/search.py
- backend/app/config.py
- backend/app/database.py
- backend/app/logging_config.py
- backend/app/main.py
- backend/app/models/__init__.py
- backend/app/models/base.py
- backend/app/models/customer.py
- backend/app/models/document.py
- backend/app/models/document_metadata.py
- backend/app/models/extraction_correction.py
- backend/app/models/purchase_order.py
- backend/app/models/reference_index.py
- backend/app/schemas/__init__.py
- backend/app/schemas/customer.py
- backend/app/schemas/document.py
- backend/app/schemas/extraction.py
- backend/app/schemas/po_profile.py
- backend/app/schemas/purchase_order.py
- backend/app/services/__init__.py
- backend/app/services/customer_service.py
- backend/app/services/document_service.py
- backend/app/services/export_service.py
- backend/app/services/extraction/__init__.py
- backend/app/services/extraction/digital_extractor.py
- backend/app/services/extraction/field_validator.py
- backend/app/services/extraction/glm_ocr_prompts.py
- backend/app/services/extraction/hybrid_router.py
- backend/app/services/extraction/invoice_validator.py
- backend/app/services/extraction/layoutlm_extractor.py
- backend/app/services/extraction/ocr_client.py
- backend/app/services/extraction/pdf_converter.py
- backend/app/services/extraction/pipeline.py
- backend/app/services/extraction/prompts.py
- backend/app/services/extraction/providers/__init__.py
- backend/app/services/extraction/providers/base.py
- backend/app/services/extraction/providers/datalab_provider.py
- backend/app/services/extraction/providers/digital_provider.py
- backend/app/services/extraction/providers/json_utils.py
- backend/app/services/extraction/providers/ollama_provider.py
- backend/app/services/extraction/providers/openai_compat_provider.py
- backend/app/services/extraction/response_parser.py
- backend/app/services/extraction/scan_preprocessor.py
- backend/app/services/extraction/so_validator.py
- backend/app/services/extraction/tasks.py
- backend/app/services/extraction/two_layer_client.py
- backend/app/services/po_service.py
- backend/app/services/search_service.py
- backend/app/services/storage_service.py
- backend/celery_app.py
- backend/Dockerfile
- backend/pyproject.toml
- backend/requirements.txt

## Frontend Core Files

- frontend/Dockerfile
- frontend/index.html
- frontend/nginx-frontend.conf
- frontend/package.json
- frontend/package-lock.json
- frontend/postcss.config.js
- frontend/src/api/client.ts
- frontend/src/api/customers.ts
- frontend/src/api/documents.ts
- frontend/src/api/extraction.ts
- frontend/src/api/purchaseOrders.ts
- frontend/src/api/search.ts
- frontend/src/App.tsx
- frontend/src/components/ChainStatusBar.tsx
- frontend/src/components/CustomerCombobox.tsx
- frontend/src/components/DocumentCard.tsx
- frontend/src/components/layout/AppShell.tsx
- frontend/src/components/layout/InlineSearch.tsx
- frontend/src/components/OrderItemsTable.tsx
- frontend/src/components/PDFPreviewPanel.tsx
- frontend/src/components/PDFViewer.tsx
- frontend/src/components/ProfileDiscrepancyPanel.tsx
- frontend/src/components/ProfileDocumentSection.tsx
- frontend/src/components/ProfileFieldComparison.tsx
- frontend/src/components/ProfileTimeline.tsx
- frontend/src/components/ReviewModal.tsx
- frontend/src/components/UploadZone.tsx
- frontend/src/context/ToastContext.tsx
- frontend/src/hooks/useCustomers.ts
- frontend/src/hooks/useDocuments.ts
- frontend/src/hooks/useExtraction.ts
- frontend/src/hooks/usePurchaseOrders.ts
- frontend/src/hooks/useSearch.ts
- frontend/src/index.css
- frontend/src/main.tsx
- frontend/src/pages/AdminPage.tsx
- frontend/src/pages/CustomersPage.tsx
- frontend/src/pages/DashboardPage.tsx
- frontend/src/pages/DocumentsPage.tsx
- frontend/src/pages/PODetailPage.tsx
- frontend/src/pages/POListPage.tsx
- frontend/src/pages/POProfilePage.tsx
- frontend/src/pages/SearchPage.tsx
- frontend/src/types/index.ts
- frontend/src/utils/extractionErrors.ts
- frontend/tailwind.config.js
- frontend/tsconfig.json
- frontend/tsconfig.node.json
- frontend/vite.config.ts

## Nginx Core Files

- nginx/nginx.conf

## Storage Core Path

- storage/documents/

## Optional Or Non-Operational (Exclude)

- docs/
- tests/
- logs/
- benchmark/
- debug_markdown/
- backend/debug_markdown/
- backend/reports/
- backend/scripts/
- .github/
- .plan/
- start.ps1
- stop_all.ps1
- reset.ps1
- test_local_ollama.py
- CLAUDE.md
- README.md
- PDD.md
- Requirements.md
- TASK_SHEET.md
- CICD_REPORT.md
- client-mail.md

## Important Runtime Notes

- .env is required at runtime and is not part of the repository list above.
- Alembic migration files under backend/alembic/versions are required for database bootstrap and upgrades.
- frontend/package-lock.json is included to ensure reproducible dependency resolution in constrained environments.
- storage/documents/ must be writable by backend and worker containers/processes.
