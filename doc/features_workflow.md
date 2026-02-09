# Document Platform V1.1 - Features & Workflow Documentation

## Core Purpose

A comprehensive document management platform designed to track and organize business documents for sales operations. It links Cases (defined by Opportunities) with Sales Orders (SOs) and their respective supply chain documents.

## Key Capabilities

### 1. Case Management

- **Search & Tracking**: Cases can be searched by "Opportunity ID" (using the `SKY-XXX` format) or "Sales Order Number".
- **Identification**: Each case is unique and linked to a CRM Opportunity.
- **Categorization**: Cases are classified as `HARDWARE` or `SERVICES`.

### 2. Sales Order (SO) Tracking

- **Global Uniqueness**: Sales Order numbers are globally unique across the system.
- **Monthly Buckets**: SOs are organized by their creation month (immutable once set).
- **Multiple SOs per Case**: A single case can handle multiple Sales Orders.

### 3. Document Management

The system enforces a strict hierarchy and checklist for documents. All documents are attached at the **Sales Order (SO) level**:

- **SO Level documents**:
  - `CUSTOMER_PO` (Customer Purchase Order)
  - `VENDOR_INVOICE`
  - `VENDOR_DC` (Delivery Challan)
  - `COMPANY_INVOICE`
  - `COMPANY_DC`
  - `POD` (Proof of Delivery)
- **Features**:
  - PDF Previewing
  - Checksum validation (SHA-256) to prevent duplicates
  - PDF Rotation tools
  - Metadata tracking (upload time, uploader, file size)

### 4. Audit & Compliance

- **Audit Logs**: Tracks all critical actions (`CASE_CREATED`, `DOCUMENT_UPLOADED`, etc.) with actor and timestamp.
- **Consistency**: Enforces naming conventions and storage paths.

## Business Workflow (9-Stage Process)

The application supports the complete lifecycle of a sales transaction:

1.  **Inquiry**: Customer initiates interest.
2.  **Opportunity**: Created in CRM (Synced/Input as `SKY-XXX`).
3.  **PO**: Customer sends Purchase Order → Uploaded as `CUSTOMER_PO` to the relevant SO.
4.  **Vendor Invoice**: Procurement pays vendor → Uploaded to SO.
5.  **Vendor DC**: Goods delivered from vendor → Uploaded to SO.
6.  **Company Invoice**: Bill raised to customer → Uploaded to SO.
7.  **Company DC**: Delivery Challan to customer → Uploaded to SO.
8.  **POD**: Transporter provides Proof of Delivery → Uploaded to SO.
9.  **Collection**: Payment collection (Closing the loop).
