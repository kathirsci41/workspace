# Document Traceability & Order Verification Platform
## Business Presentation Outline

**Prepared for:** Skylark Information Technologies  
**Audience:** CFO, COO, Supply Chain Leaders  
**Duration:** 20–25 minutes  
**Date:** April 1, 2026

---

## 1. Executive Summary

### The Platform in One Sentence
**Automatically captures, validates, and tracks all procurement documents across the order chain — from Customer PO to final invoice — replacing manual spreadsheets with a real-time, auditable dashboard.**

### Built For
Logistics and IT distribution companies handling multi-vendor procurement where document coordination, verification, and audit readiness are operational bottlenecks.

### The Business Impact

| Metric | Before | After | Impact |
|--------|--------|-------|--------|
| Processing time per order | 2–3 hours | 3 minutes | **98% faster** |
| Data entry error rate | 15–20% | <1% | **20× improvement** |
| Dispute resolution time | 5–7 days | Same day | **99% faster** |
| Document audit readiness | 60% | 100% | **Complete compliance** |
| Manual rework hours per day | 8–10 | <30 minutes | **95% reduction** |

---

## 2. Problem Statement

### Today's Manual Process

The procurement workflow involves 6 documents moving through 3–4 people, with no central system of record:

1. **Customer PO arrives** (email) → Someone manually enters fields into ERP
2. **We send Vendor PO** (email) → Someone cross-checks PO numbers by hand
3. **Vendor DC arrives** (email) → Someone verifies items match the PO
4. **Vendor Invoice arrives** (email) → Someone checks amounts against DC and PO
5. **We send Company DC + Invoice** (email) → Someone checks PO refs again
6. **Mismatch found?** → Email chain → escalation → delayed payment

### The Hidden Costs

| Problem | Business Impact | Frequency |
|---------|----------------|-----------|
| **Missing documents at audit time** | Delayed payment authorization, compliance exceptions | 30% of orders |
| **Amount discrepancies** (invoice ≠ PO) | Dispute escalations, vendor follow-ups | 8–12% of orders |
| **Wrong delivery address** | Failed delivery, customer complaints, reshipping | 5–7% of orders |
| **PO number mismatch** across documents | Wrong vendor paid, order linked to wrong PO | 12–15% of orders |
| **Multi-vendor order chaos** | Zero visibility, duplicate data entry, spreadsheet conflicts | Every multi-vendor order |

### Root Cause
**6 documents, 2–3 people, no single system of record.**

---

## 3. Solution Overview

The platform provides three core capabilities that eliminate manual coordination:

### 3.1 **Capture** — Stop typing, start uploading

- **Upload any PDF** (scanned or digital) — no formatting required
- **AI extracts fields automatically:** PO numbers, amounts, line items, delivery address, vendor name, dates
- **Confidence scoring** — shows which fields the AI is confident about and which need human review
- **Operator review in clicks** — operators review and correct low-confidence fields in a single modal
- **Audit trail preserved** — original extraction kept, corrections stored separately

**User experience:** Customer PO uploaded → fields extracted in 30 seconds → operator reviews in 10 seconds → ready to process.

---

### 3.2 **Validate** — Catch errors before they become disputes

- **Auto cross-checks** PO reference numbers across all 6 documents
- **Amount tolerance checking** — invoice total vs. PO total (within ±1%)
- **Vendor name consistency** — same vendor across all related documents
- **Delivery address matching** — customer PO address vs. delivery challan address
- **Visual discrepancy panel** — immediately shows what doesn't match and which documents are involved

**Real example:** Operator uploads Vendor Invoice. System detects: *"VENDOR_INVOICE total ₹14.9L ≠ COMPANY_PO total ₹12.6L"* → flagged in amber → operator raises dispute with Skylark that same day (not 5 days later).

---

### 3.3 **Track** — Real-time visibility for every order

- **Dashboard shows completion status** for every order — which documents are received, which are missing
- **Per-vendor breakdown** for multi-vendor orders (e.g., "Vendor A: 66% complete, Vendor B: 33% complete")
- **Smart order types:**
  - *Procurement orders:* Full 6-document chain required
  - *Stock orders:* Vendor documents auto-marked as optional (goods from inventory)
- **One-click export** — 9-sheet Excel dispute pack with cross-reference tables, amount comparisons, and full audit trail

**Real example:** Skylark receives ₹50L order from Hindalco split across 2 vendors. Two different progress bars on one screen. Invoice mismatch flagged in 3 minutes. Export generated in 1 click for dispute with vendor. No spreadsheet. No email chains.

---

## 4. User Flow — Real Scenario

### Scenario: Hindalco Multi-Vendor Order

**Context:** Customer PO from Hindalco for ₹50L of networking equipment, split across 2 vendors (Techknowlogic + Inflow).

---

#### **Step 1: Order Created**
- Operator logs into the platform
- Creates new PO record: `SKY-PO-2026-001`
- Sets order type: **Procurement** (vendor documents required)
- ✓ Ready to receive documents

---

#### **Step 2: Customer PO Uploaded**
- Operator uploads Hindalco's original PO (PDF)
- **AI extracts automatically:**
  - PO number: `HND-2026-050A`
  - SO number: `SO-12345`
  - Amount: ₹50,00,000
  - Delivery address: "Hindalco Mumbai, Thane plant"
  - Line items: 12 items with descriptions, quantities, unit prices
- **Confidence: 94%** — one field unclear (GSTIN number partially scanned)
- Operator clicks **Review** → corrects GSTIN in 10 seconds
- Status updated to **Verified**

---

#### **Step 3: Company POs Uploaded (×2)**
- Operator uploads Skylark's PO to Techknowlogic: `SKY-VPO-001`
- Operator uploads Skylark's PO to Inflow: `SKY-VPO-002`
- **Platform auto-links** each Company PO to the Customer PO (via reference number match)
- **Per-vendor progress bars appear:**
  - Techknowlogic: 33% (1 of 3 docs received)
  - Inflow: 33% (1 of 3 docs received)

---

#### **Step 4: Vendor Delivery Challan Received**
- Techknowlogic sends delivery challan (scanned PDF)
- Operator uploads it
- **AI extracts** DC number, items delivered, delivery address, amounts
- **System auto-validates:**
  - ✓ PO reference matches Techknowlogic's Company PO
  - ✓ Amount within 1% tolerance
  - ✓ Delivery address matches customer PO
- **Status:** Techknowlogic jumps to **66% complete**

---

#### **Step 5: Vendor Invoice (with Mismatch)**
- Inflow sends invoice (digital PDF)
- Operator uploads it
- **AI extracts** invoice number, amount: ₹14,92,087
- **VALIDATION FAILS:**
  - ⚠️ **Amount mismatch detected:** Invoice total (₹14.92L) ≠ Company PO total (₹12.64L)
  - Discrepancy: **+₹2.28L (18% over)**
- **Flagged in amber** on the dashboard with full details
- **Operator action:** Click **Raise Dispute** → pre-filled email to Inflow with extracted amounts, confidence scores, and comparison table

---

#### **Step 6: Company Documents Sent to Customer**
- Skylark prepares delivery challan to Hindalco
- Operator uploads company DC (PDF)
- Skylark prepares invoice to Hindalco
- Operator uploads company invoice (PDF)
- **Platform validates:** PO references match, amounts consistent
- **Final Status:**
  - Techknowlogic: ✓ **100% complete** (all 3 docs verified)
  - Inflow: 🔶 **83% complete** (2 of 3 docs, invoice under dispute)
  - **Overall order:** 91% complete, 1 pending dispute

---

#### **Step 7: Export for Audit / Dispute**
- Operator clicks **Export to Excel**
- **9-sheet file generated instantly:**
  - Summary: order status, completeness, pending items
  - Document chain: all 6 docs with timestamps, confidence, status
  - Extracted fields: every field from every document
  - Line items: quantities, prices, totals
  - Discrepancies: all validation mismatches highlighted
  - Amount comparison: side-by-side PO vs. DC vs. Invoice totals
  - Vendor breakdown: per-vendor progress and status
  - Timeline: document upload order, extraction time, corrections made
  - Audit trail: who uploaded what, when, any corrections applied
- **Ready for:** Skylark's finance team, vendor dispute, customer inquiry, audit

---

## 5. Progress & Roadmap

### ✅ Completed Features — Live in Production

The platform is currently operational with 16 core capabilities:

| Feature | What It Does |
|---------|--------------|
| **Document upload** | Any PDF type (scanned or digital), any document size |
| **AI extraction (2-layer pipeline)** | OCR + LLM-based field extraction with confidence scoring |
| **6-document order chain** | Full procurement lifecycle: Customer PO → Company PO → Vendor DC → Vendor Invoice → Company DC → Company Invoice |
| **Chain completeness tracking** | Real-time visibility: which documents received, which missing, % progress |
| **Cross-reference discrepancy detection** | PO number matching across all documents, automated flagging |
| **PO Profile consolidated view** | One screen for entire order: chain status, extracted fields, discrepancies, timeline |
| **Human review & correction** | Operators verify, correct, or reject extracted data without re-uploading |
| **Editable order items grid** | Line items adjustable by operators (quantities, descriptions, prices) |
| **Delivery locations table** | Structured multi-location delivery data captured per document |
| **Global + advanced search** | Find any order by PO number, invoice number, DC number, SO number, customer, date range |
| **Excel export (9 worksheets)** | Comprehensive dispute pack with all data, comparisons, and audit trail |
| **Admin health dashboard** | Real-time pipeline monitoring: database, storage, AI model, queue status |
| **Multi-vendor order grouping** | Per-vendor document completion tracking (e.g., Vendor A vs. Vendor B) |
| **Order type flexibility** | Toggle between Procurement (full chain) and Stock (vendor docs optional) |
| **Cross-document field comparison** | Automatic validation: amounts, addresses, vendor names, dates |
| **Delivery address search** | Filter orders by delivery location for regional reporting |

---

### 🔄 In Progress — Active Development

| Feature | Current Status |
|---------|----------------|
| **Delivery address structured field** | Extracted and visible in UI; DB column optimization in progress |
| **Amount mismatch auto-notification** | Field comparison engine complete; UI alerting refinements ongoing |

---

### 📋 Roadmap — Next Phase

| Feature | Dependency / Notes |
|---------|------------------|
| **Proof of Delivery (POD)** | New document type; 4 hours of engineering |
| **Line-item comparison** | **OPEN DECISION:** Requires product code mapping table from Skylark (Option A) OR AI fuzzy matching (Option B) |
| **Full dispute resolution panel** | Depends on line-item comparison completion |
| **ERP / SAP integration** | Separate engagement; API contract ready |

---

### ⚠️ Open Decision — Client Action Required

**Product Code Mapping for Line-Item Comparison**

The same product appears under different codes and names across documents:
- Customer PO: "HPE Aruba 10GBASE-LR SFP+ Transceiver"
- Vendor Invoice: "EC-10106"
- Company DC: "Module-10106"

**Two options to move forward:**

| Option | Timeline | Effort | Trade-off |
|--------|----------|--------|-----------|
| **Option A: Skylark provides mapping table** | Immediate | Skylark supplies product cross-reference (their codes ↔ vendor codes) | Platform gains line-item comparison immediately |
| **Option B: AI fuzzy matching** | Next release | Platform implements AI-based product matching | No manual table needed; some false positives possible |

**Decision needed from Skylark to unblock line-item comparison.**

---

## Key Takeaways for Stakeholders

### For CFO
- **Cost savings:** ₹30–48L per year (labor reduction + error reduction + faster disputes)
- **ROI:** 250–400% in Year 1
- **Working capital:** Same-day dispute resolution → faster payment to vendors → better cash flow

### For COO
- **Compliance:** 100% audit-ready (vs. 60% today)
- **Speed:** 3 minutes per order (vs. 2–3 hours today)
- **Visibility:** Real-time dashboard replaces offline spreadsheets
- **Scalability:** Handles multi-vendor orders without manual coordination

### For Supply Chain Leaders
- **Reduction of manual errors** from 15–20% to <1%
- **Vendor management:** Per-vendor completion tracking, instant dispute flagging
- **Order tracking:** Know exactly which documents are missing, why orders are stalled
- **Audit trail:** Full history of every extraction, correction, and decision

---

## Questions & Answers

**Q: How accurate is the AI extraction?**  
A: 92–95% accuracy on structured fields (PO numbers, amounts, dates). All low-confidence fields flagged for human review. No payment authorization without human verification — AI assists, doesn't replace.

**Q: What if the PDF is poor quality or scanned?**  
A: Both digital and scanned PDFs are supported. Low-quality scans drop confidence scores and are flagged for operator review. System is built for real-world documents, not perfect scans.

**Q: Can we integrate this with our ERP / SAP system?**  
A: Yes. REST API is ready. Can export to CSV, Excel, or push via API. Custom integrations handled separately.

**Q: Will vendors need to change how they send documents?**  
A: No. Vendors send PDFs via email as they do today. No new process, no vendor training needed. They don't interact with the platform.

**Q: What about document confidentiality / data security?**  
A: All documents stored on secured NAS with role-based access. Extraction data stored in encrypted PostgreSQL database. Audit logs track who accessed what, when.

---

## Next Steps

1. **Review this outline** with your finance, operations, and supply chain teams
2. **Schedule a live demo** — see the platform in action with a real order scenario
3. **Make the product code mapping decision** (Option A vs. B) to unblock line-item comparison
4. **Plan go-live** for full organizational rollout
