# Project Definition Document (PDD)

## Business Sign-Off

### Project

Document Traceability & Order Verification Portal

### Version

Draft 3.1 (Consolidated)

### Prepared By

Amasqis.ai

### Prepared For

Skylark Information Technologies

### Date

30 March 2026

---

## 1. Business Objective

The objective of this project is to provide a single portal to track order-related documents, support faster document retrieval during customer queries and disputes, and help identify when the expected document flow is incomplete, missing, or inconsistent.

The platform is intended to reduce time, effort, and process complexity in collecting and reviewing documents. It is not intended to replace business users or remove operational ownership. Human supervision and review remain mandatory wherever validation, discrepancy handling, or business decision-making is required.

---

## 2. Current Process (As-Is)

At present, order-related documents are handled across multiple systems and storage locations. Teams rely on ERP, email, shared folders, and manual follow-up to manage the full document chain.

The current business flow operates at a high level as follows:

1. The company receives the Customer PO.
2. An SO number is generated against the Customer PO.
3. The company checks whether the required items are available in inventory.
4. If items are available in stock:
   - the company prepares the Delivery Challan (DC) and Invoice
   - the goods are delivered to the customer at the required address
5. If items are not available in stock:
   - one or more Vendor POs are raised against the SO
   - the Vendor PO is sent to the relevant vendor
   - the vendor processes the order and sends the goods along with vendor documents
   - the company receives the items and documents, verifies them, and prepares its own DC and Invoice
   - the goods are then delivered to the customer
6. When a customer raises a query or dispute, employees manually collect related documents from different sources, review them, and respond based on manual verification.

A single Customer PO may result in two or more Vendor POs when items are sourced from different vendors. In this case, each vendor covers a portion of the ordered items and together the Vendor POs must account for all items in the Customer PO.

The current process depends heavily on manual searching, manual document comparison, and employee knowledge of where records are stored.

---

## 3. Expected Future Process (To-Be)

The expected future state is a single platform where all order-related documents are managed under one order case and can be reviewed in a structured way.

In the expected future process:

- related documents are stored and viewed in one place
- users can search by key business reference numbers
- the platform helps identify missing documents in the expected flow
- the platform compares key details across documents and flags inconsistencies or mismatches for business review
- users can review the full order picture in one screen through a consolidated PO Profile view
- order-related data can be exported for sharing, reporting, or review when required
- human review remains part of the process for validation, exception handling, and final business judgment

---

## 4. Document Verification Approach

The platform checks consistency across all order documents in a structured sequence. For each order case, documents are compared step by step:

- **Step 1 — Customer PO and Vendor PO(s):** Are all items in the Customer PO covered across the Vendor POs raised? Do the order references and vendor details align? Is the delivery direction correct?
- **Step 2 — Vendor PO and Vendor Invoice:** Do the items, quantities, and vendor details in the Vendor Invoice match what was ordered in the Vendor PO? Are payment terms consistent?
- **Step 3 — Vendor Invoice and Company DC:** Do the items and quantities received and dispatched match what was invoiced by the vendor? Are serial numbers and delivery references consistent?
- **Step 4 — Company Invoice and Customer PO:** Do the items, amounts, and customer details in the Company Invoice match the original Customer PO? Is the order reference chain consistent?

Where inconsistencies are found at any step, the platform flags them for business review. Human review and judgment remain mandatory for all flagged items.

### Information Captured from Documents

The platform reads and records the following from each uploaded document where present:

| Category | Information Captured |
| -------- | -------------------- |
| Document identity | Reference number, document date |
| Issuer and recipient | Name, address, GST number, PAN number |
| Line items | Product description, product code, HSN/SAC code, quantity, unit of measure, unit price, total value |
| Tax | Tax type (IGST / CGST+SGST), rate, tax amount |
| Amounts | Subtotal, tax total, net amount |
| References | Linked PO number, SO number, invoice number, DC number, quotation reference number, quotation date |
| Payment | Payment terms, payment due date |
| Delivery | Delivery address, dispatch details |
| Traceability | Serial numbers (hardware items), e-invoice reference number, end user field |

---

## 5. Phased Delivery Approach

### Phase 1 — Standalone Platform

The platform is built and operational as a standalone tool without dependency on ERP integration. Documents are uploaded manually, the platform reads and records the relevant data, and users review and confirm the records. The four-step verification runs on the confirmed data.

This phase is fully usable as a business tool on its own.

### Phase 2 — ERP Integration

In Phase 2, Skylark's ERP team will provide specific data access points to the platform. This will allow the platform to:

- confirm SO numbers and fulfillment type linked to a Customer PO
- retrieve linked Vendor PO references for a given SO
- cross-check document data against ERP records automatically

Phase 2 removes the need for manual entry of certain reference data and improves verification confidence.

Phase 2 delivery is subject to ERP team availability and the agreed data access points being provided in the requested format. The timeline for Phase 2 cannot be confirmed until ERP readiness is known.

---

## 6. Documents in Scope

The following document types are within scope for the current phase:

- Customer PO (including Annexure where present as a separate document)
- Vendor PO (Company PO raised to vendor)
- Vendor DC
- Vendor Invoice
- Company DC
- Company Invoice

---

## 7. Project Timeline

### Estimated Duration

| Phase | Estimated Duration |
| ----- | ------------------ |
| Phase 1 — Standalone platform | 6–7 weeks from start |
| Phase 2 — ERP integration | 3–4 weeks after ERP access points are confirmed and available |
| Full project | 10–12 weeks total |

Note: Approximately 70% of Phase 1 is already built. The remaining work covers cross-document comparison, structured reading of item details from documents, and the related review screens — the most complex portion of the work.

This estimate applies to the current approved phase and assumes timely business input, availability of representative documents for testing, and no major change in scope.

### Where Delays Are Most Likely

| Area | Likelihood | Potential Delay |
| ---- | ---------- | --------------- |
| Reading and comparing item details reliably across documents with different layouts and product code formats | High | 2–4 weeks |
| Same product described under different codes by different vendors — no shared product code standard | High | 1–2 weeks |
| Document format variation beyond tested samples | Medium | 1–2 weeks |
| Customer PO accompanied by a separate Annexure document | Medium | 1 week |
| ERP data access readiness — outside the project team's control | Medium | Unknown |
| Business rules for edge cases such as partial delivery or product substitution | Medium | 1 week |

### Open Decision Required

The comparison engine matches items across documents using product codes. The same product can appear under different codes from different vendors. A business decision is needed on whether a product code reference table will be maintained by the business, or whether this data will come from ERP in Phase 2. This decision affects how much of the item-level comparison is achievable in Phase 1.

---

## 8. On-Premises Deployment

This is an on-premises application. It is installed and runs entirely within Skylark's own infrastructure. No data is sent to external services.

### Server Requirements

The following server specification is required before deployment can proceed. Procurement must be arranged by Skylark in parallel with development.

| Component | Minimum Requirement | Notes |
| --------- | ------------------- | ----- |
| RAM | 32 GB | |
| CPU | 8-core, modern processor | |
| GPU | 16 GB VRAM (NVIDIA) — advisable | Final requirement confirmed after AI model experiments. 16 GB is the recommended safe specification to procure now. |
| Storage | 500 GB SSD | |
| Operating System | Linux server (64-bit) | |
| Network | Internal LAN | Required for Phase 2 ERP access |

**Note on GPU specification:** The exact GPU memory requirement will be confirmed after AI processing experiments conclude. The platform may use more than one model. 16 GB is the advisable safe specification to procure now. A confirmed hardware specification will be issued after experiments conclude.

**If a dedicated server is not yet available:** AI processing can run via a remote service as an interim arrangement. A local server is preferred for production for performance and data privacy.

---

## 9. Expected Business Outcome

The business should be able to open one order case and clearly understand:

- what documents are available and what are missing
- whether the document flow is complete
- whether key order-related information appears consistent across documents
- where a mismatch, gap, or exception needs review
- the complete event history of the order documents

The expected benefit is reduced time spent searching, collecting, and reviewing records, along with improved visibility of the order document chain in one place.

---

## 10. Assumptions and Dependencies

- Business users will confirm the correct expected document flow for the relevant business scenarios
- Source documents will be available in usable format for upload, review, and verification
- Platform output quality depends on the quality of input documents — scan clarity, layout, page count, and content complexity affect how accurately data is read and compared
- Users will review and confirm records where the platform's reading or comparison needs validation
- Human review and supervision is mandatory for business validation, exception handling, and final decision-making
- For Phase 2: Skylark's ERP team will create and provide the agreed data access points in the requested format
- Any future integration, extended automation, or additional functionality will be considered separately based on feasibility, dependency readiness, and approval

---

## 11. Risks and Business Considerations

- Some business scenarios may not follow one fixed document chain
- Missing, low-quality, or highly complex source documents can reduce output quality and require more manual review
- Document format variation can affect how consistently data is read and compared across documents
- Users may assume future enhancements are included unless current scope boundaries are clearly understood and signed off
- The value of the platform depends on correct document upload, correct case linking, and continued business review discipline
- Phase 2 delivery timeline depends on ERP team availability to build and provide the agreed data access points
- Any future enhancement or integration depends on feasibility, business readiness, and separate approval

---

## 12. Sign-Off Statement

By approving this document, the business confirms that:

- the business objective is understood and accepted
- the As-Is process is understood and accepted as the current working process
- the To-Be process is understood and accepted as the expected future process for the current phase
- the document verification approach and the four-step comparison chain are understood and accepted
- the phased delivery approach — Phase 1 standalone, Phase 2 ERP integration — is understood and accepted
- the documents listed as in scope are understood and accepted
- the on-premises deployment requirement is understood, and hardware procurement will be initiated immediately
- the estimated timeline applies only to the current phase and is subject to the stated assumptions and dependencies
- the listed risks and business considerations are understood and accepted
- platform results depend on input document quality, page volume, and content complexity
- the platform is intended to reduce time and process complexity, not remove the need for business users
- human-in-the-loop supervision remains mandatory for review, validation, and exception handling
- any future enhancement, integration, or additional requirement is outside this sign-off unless separately reviewed and approved

---

## 13. Sign-Off Table

| Name   | Role   | Department   | Decision          | Date   | Signature   |
| ------ | ------ | ------------ | ----------------- | ------ | ----------- |
| [Name] | [Role] | [Department] | Approved / Rework | [Date] | [Signature] |
| [Name] | [Role] | [Department] | Approved / Rework | [Date] | [Signature] |
| [Name] | [Role] | [Department] | Approved / Rework | [Date] | [Signature] |
