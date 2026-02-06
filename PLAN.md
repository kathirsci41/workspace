# Plan: Move Customer PO to Sales Order

## Overview

Currently, `CUSTOMER_PO` documents are stored at the Case level. The goal is to move them to be strictly associated with a Sales Order (SO), stored inside the SO folder structure (`.../{SO_MONTH}/SO-{SO_NUMBER}/CUSTOMER_PO/`), without breaking existing functionality.

## Backend Changes

### 1. Document Service (`backend/app/services/document_service.py`)

- **Validation**: Update `upload_document` to require `sales_order_id` for `CUSTOMER_PO`, similar to other SO-level documents.
- **Logic**: Remove the exception that forbids linking `CUSTOMER_PO` to a Sales Order.

### 2. Storage Service (`backend/app/services/storage_service.py`)

- **Path Generation**: Update `generate_storage_path` to remove the special case for `CUSTOMER_PO`. It will now use the standard path format: `cases/{case_id}/{so_month}/SO-{so_number}/{document_type}/{filename}`.

### 3. Sales Order Service (`backend/app/services/sales_order_service.py`)

- **Search**: Update `search_sales_orders` to include `CUSTOMER_PO` in the document checklist.

### 4. Schemas (`backend/app/schemas/sales_order.py`)

- **Response**: Update `SalesOrderResponse` default checklist to include `"CUSTOMER_PO": False`.

## Frontend Changes

### 1. Types (`frontend/src/types/index.ts`)

- **Constants**: Add `'CUSTOMER_PO'` to `SO_DOCUMENT_TYPES`.
- **Interfaces**: Add `CUSTOMER_PO: boolean` to `SalesOrderChecklist`.

### 2. Upload Modal (`frontend/src/components/documents/UploadModal.tsx`)

- **Form Logic**: Ensure `salesOrderId` is required and sent when `CUSTOMER_PO` is selected.
- **Visuals**: Update path preview logic if necessary.

### 3. Case Page (`frontend/src/components/case/CasePage.tsx`)

- **UI**: Remove the standalone `CustomerPOSection` component.
- **Cleanup**: Remove `customerPo` prop passing.

### 4. Sidebar (`frontend/src/components/layout/Sidebar.tsx`)

- **UI**: Remove the Case-level `Customer PO` indicator/link.

### 5. Sales Order Card (`frontend/src/components/case/SalesOrderCard.tsx`)

- **Verification**: Ensure `CUSTOMER_PO` renders correctly in the checklist and document table (should automatically happen via `SO_DOCUMENT_TYPES` update).

## Migration Note

- Existing `CUSTOMER_PO` documents will remain linked only to the Case in the database (`sales_order_id=NULL`) and stored in the old path.
- These legacy documents may not appear in the new SO-centric view unless a migration script is run or logic is added to display "Orphaned" POs.
- Per instructions "without affect current functionality", we will proceed with the code changes for _new_ uploads. Existing functionality for _retrieving_ files by ID/Path via API remains, but their visibility in the UI will depend on being linked to an SO.
