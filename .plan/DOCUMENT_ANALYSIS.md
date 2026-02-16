# 28-Document Analysis — Field Inventory & Cross-Reference Mapping

> Analysis of 28 real PDF documents from 5 customers, extracted via raw OCR (glm-ocr model).  
> All company/customer/vendor names replaced with generic identifiers.

---

## Table of Contents

1. [Document Inventory Summary](#1-document-inventory-summary)
2. [Document Type Analysis](#2-document-type-analysis)
   - 2.1 [Company DC](#21-company-dc)
   - 2.2 [Company Invoice](#22-company-invoice)
   - 2.3 [Vendor Invoice](#23-vendor-invoice)
   - 2.4 [Customer PO](#24-customer-po)
   - 2.5 [Company PO (Purchase Bill)](#25-company-po-purchase-bill)
3. [Per-Customer Chain Mapping](#3-per-customer-chain-mapping)
4. [Cross-Document Connecting Keys](#4-cross-document-connecting-keys)
5. [Root Cause Analysis](#5-root-cause-analysis)
6. [Field Coverage Matrix](#6-field-coverage-matrix)

---

## 1. Document Inventory Summary

| Customer | Customer PO | Company DC | Company Invoice | Vendor Invoice | Company PO | Total |
|---|---|---|---|---|---|---|
| Customer A | 1 (2 pages) | 1 (1 page) | 1 (1 page) | 1 (1 page) | 1 (1 page) | 5 |
| Customer B | 1 (42 pages!) | 2 (6+6 pages) | 2 (1+2 pages) | 2 (2+13 pages) | 1 (2 pages) | 8 |
| Customer C | 1 (2 pages) | 1 (1 page) | 1 (2 pages) | 1 (1 page) | 1 (2 pages) | 5 |
| Customer D | 1 (2 pages) | 1 (2 pages) | 1 (2 pages) | 1 (3 pages) | 1 (1 page) | 5 |
| Customer E | — | 1 (5 pages) | 2 (1+1 pages) | 1 (2 pages) | 1 (2 pages) | 5 |
| **Total** | **4** | **6** | **7** | **6** | **5** | **28** |

**Notes**:
- Customer B has 2 company DCs and 2 company invoices (2 different delivery locations from same PO)
- Customer B has 2 vendor invoices from 2 different vendors
- Customer E has 2 company invoices (1 for services, 1 for products) and no customer PO PDF
- Customer E's company DC is 5 pages (item details on pages 3-4, totals on page 5)
- 1 `.msg` email file found (Customer B) — excluded from analysis

---

## 2. Document Type Analysis

### 2.1 Company DC

**Title on document**: "NON RETURNABLE DELIVERY CHALLAN"  
**Issued by**: The company (seller/distributor)  
**Purpose**: Dispatching goods to customer

**Layout**: Highly consistent across all customers — same template.

#### Fields Found on Every Company DC

| Label on Document | Schema Field | Location | Notes |
|---|---|---|---|
| DC No. | `dc_number` | Top-right header | Format: `1DNTXXXXXXDCNNNN` |
| DC Date | `dc_date` | Top-right header | Format: DD/MM/YYYY |
| Customer Order No. | `po_reference` | Header block | **This is the customer's PO number** |
| Reference | *(person name)* | Header block | Attention/contact person — NOT a PO number |
| Sales Order No. | `sales_order_no` ⚠️ NEW | Header block | Format: `1OTMXXXXXXNNNNNN` — **critical for chain linking** |
| Customer Order Date | `customer_order_date` ⚠️ NEW | Header block | Date from customer's PO |
| Delivery to / Ship to | `dispatch_to` | Address block | Customer delivery address |
| Item table | `items_description` | Body | Sl.No, Description, HSN, Qty, Rate, Amount |
| Total Qty | `quantity` | Table footer | Sum of quantities |
| Estimated Amount | `est_amount` | Table footer (last page for multi-page) | **On last page only for 5+ page DCs** |

#### Company DC Examples

| Customer | DC Number | PO Reference | Sales Order No. | Pages |
|---|---|---|---|---|
| Customer A | 1DNT2526DC2995 | (customer PO number) | 1OTM2526001596 | 1 |
| Customer B | 1DNT2526DC2903, 1DNT2526DC2902 | (customer PO number) | 1OTM2526001386, 1OTM2526001387 | 6, 6 |
| Customer C | 1DNT2526DC2919 | (customer PO number) | 1OTM2526001544 | 1 |
| Customer D | 1DNT2526DC2865 | (customer PO number) | 1OTM2526001448 | 2 |
| Customer E | 1DNT2526DC2871 | (customer PO number) | 1OTM2526001428 | 5 |

#### Key Observations
- ⚠️ `sales_order_no` field is **NOT in current schema** — must be added
- ⚠️ "Reference" field (person name) must NOT be confused with `po_reference`
- ⚠️ Multi-page DCs (5-6 pages): totals/amounts only appear on the **last page**
- All DC numbers follow pattern: `1DNT` + year code + `DC` + sequence
- All sales order numbers follow pattern: `1OTM` + year code + sequence

---

### 2.2 Company Invoice

**Title on document**: "TAX INVOICE"  
**Issued by**: The company (seller/distributor)  
**Purpose**: Billing the customer for goods delivered

**Layout**: Highly consistent across all customers — same template.

#### Fields Found on Every Company Invoice

| Label on Document | Schema Field | Location | Notes |
|---|---|---|---|
| Invoice No. | `invoice_number` | Top-right header | Format: `1ITR/1ISRXXXXXXNNNNNN` |
| Invoice Date | `invoice_date` | Top-right header | Format: DD/MM/YYYY |
| Customer Order No. | `po_reference` | Header block | **Customer's PO number** |
| Customer Order Date | `customer_order_date` ⚠️ NEW | Header block | Date from customer's PO |
| SO No. | `so_number` | Header block | **Sales Order No — matches company DC** |
| Acct Manager | `acct_manager` ⚠️ NEW | Header block | Account manager name |
| IRN No. | `irn_number` | QR code area or footer | 64-char hex hash |
| Customer name | `customer_name` | "Bill to" section | Buyer's company name |
| Subtotal | `subtotal` | Amount section | Taxable value before tax |
| Tax (CGST+SGST/IGST) | `tax_amount` | Amount section | Tax amount |
| Grand Total | `total_amount` | Amount section | Final amount including tax |

#### Company Invoice Examples

| Customer | Invoice Number | PO Reference | SO Number | Total Amount | Pages |
|---|---|---|---|---|---|
| Customer A | 1ITR2526001841 | (customer PO number) | 1OTM2526001596 | ~97,500 | 1 |
| Customer B #1 | 1ITR2526001794 | (customer PO number) | 1OTM2526001386 | ~1,77,000 | 1 |
| Customer B #2 | 1ITR2526001793 | (customer PO number) | 1OTM2526001387 | ~1,56,000 | 2 |
| Customer C | 1ITR2526001789 | (customer PO number) | 1OTM2526001544 | ~8,40,000 | 2 |
| Customer D | 1ITR2526001748 | (customer PO number) | 1OTM2526001448 | ~60,87,800 | 2 |
| Customer E (services) | 1ISR2526000166 | (customer PO number) | 1OTM2526001428 | ~10,800 | 1 |
| Customer E (products) | 1ITR2526001751 | (customer PO number) | 1OTM2526001428 | ~4,78,000 | 1 |

#### Key Observations
- Invoice numbers have 2 formats: `1ITR` (trade/product invoices) and `1ISR` (service invoices)
- `so_number` on invoice matches `sales_order_no` on company DC — **critical linking field**
- Customer E has 2 invoices (1 service + 1 product) for the same PO and SO number
- ⚠️ `customer_order_date` field is **NOT in current schema** — should be added
- OCR sometimes reads `1ITR` as `11TR` (I vs 1 confusion — model limitation)

---

### 2.3 Vendor Invoice

**Title on document**: "TAX INVOICE" or "Invoice"  
**Issued by**: External vendor/supplier  
**Purpose**: Billing the company for purchased goods

**Layout**: Highly variable — each vendor has a completely different format.

#### Vendor Types Encountered

| Vendor Type | Format | Key Labels | Pages |
|---|---|---|---|
| Vendor Type 1 (IT distributor) | Clean digital format | "Invoice No.", "Invoice Date", "Buyer's Order No." | 1 page |
| Vendor Type 2 (IT distributor) | Digital format with QR | "Bill No.", "Bill Date", "Your Ref" | 2 pages |
| Vendor Type 3 (IT distributor) | Dense multi-page | "Invoice No.", "Invoice Date", "Customer Reference" | 13 pages |
| Vendor Type 4 (IT distributor) | Clean format | "Invoice No.", "Date", purchase order ref in header | 1 page |
| Vendor Type 5 (IT distributor) | Standard format | various fields | 3 pages |

#### Common Fields Across All Vendor Invoices

| Field | Schema Field | Present In |
|---|---|---|
| Invoice/Bill Number | `invoice_number` | All vendors |
| Invoice/Bill Date | `invoice_date` | All vendors |
| PO Reference | `po_reference` | Most vendors (label varies: "Buyer Order", "Your Ref", "Customer Reference") |
| Vendor Name | `vendor_name` | All vendors |
| Subtotal | `subtotal` | All vendors |
| Tax Amount | `tax_amount` | All vendors (IGST or CGST+SGST) |
| Grand Total | `total_amount` | All vendors |
| GSTIN | `gst_number` | All vendors |
| IRN | `irn_number` | Most vendors |

#### Key Observations
- PO reference label varies widely by vendor — prompt already handles this with multiple alternatives
- Some vendors put the **company's** SO/PO number as the reference, others put a different reference
- Vendor Type 3 invoices can be 13 pages — most data on page 1, item details span pages 2-12, totals on last page
- Current schema is adequate for vendor invoices — no changes needed

---

### 2.4 Customer PO

**Title on document**: "Purchase Order" or similar  
**Issued by**: The customer (buyer)  
**Purpose**: Ordering goods from the company

**Layout**: Completely different for each customer — no standard format.

#### Customer PO Formats

| Customer | Format | PO Number Label | Pages | Complexity |
|---|---|---|---|---|
| Customer A | Formal PO format | Header area | 2 | Medium |
| Customer B | Formal PO with item tables | Header area | 42(!) | Very high |
| Customer C | Simple PO format | Header area | 2 | Low |
| Customer D | Formal corporate PO | Header area | 2 | Medium |
| Customer E | No PDF available | — | — | — |

#### Common Fields Across Customer POs

| Field | Schema Field | Notes |
|---|---|---|
| PO Number | `po_number` | Always present, format varies by customer |
| PO Date | `po_date` | Always present |
| Customer Name | `customer_name` | The company issuing the PO |
| Shipping Address | `shipping_address` | Delivery destination |
| Total Amount | `total_amount` | Grand total including taxes |
| GST Number | `gst_number` | Customer's GSTIN |
| Payment Terms | `payment_terms` | Varies (Net 30, 60 days, etc.) |

#### Key Observations
- ⚠️ Customer B's 42-page PO caused Ollama 500 error on page 1 (too complex)
- PO number formats vary wildly by customer (no pattern)
- Current schema is adequate — no changes needed
- The PO Number is the **master key** linking all documents together

---

### 2.5 Company PO (Purchase Bill)

**Title on document**: "PURCHASE BILL"  
**Issued by**: The company  
**Purpose**: Company's own purchase order to vendors — records what was bought

**Layout**: Consistent format (same template as company DC/invoice).

#### Fields Found on Every Company PO

| Label on Document | Schema Field | Notes |
|---|---|---|
| PO No. | `po_no` | Company's internal PO to vendor |
| PO Date | `po_date` | Date of purchase |
| Bill No. | `bill_no` | **= Vendor Invoice Number** (critical link) |
| Bill Date | `bill_date` | = Vendor Invoice Date |
| Vendor Name | `vendor_name` | Supplier name |
| Subtotal | `subtotal` | Before tax |
| Tax | `tax_amount` | IGST or CGST+SGST |
| Grand Total | `total_amount` | After tax |

#### Key Observations
- `bill_no` field directly matches `invoice_number` on the vendor invoice — **procurement chain link**
- Currently no `SKYLARK_PO` / `COMPANY_PO` document type in the system
- **Deferred to Phase 3** — can be uploaded as supplementary vendor documentation for now
- These documents validate vendor invoice accuracy

---

## 3. Per-Customer Chain Mapping

### 3.1 Customer A

```
Customer PO (★ PO Number from customer)
  └─ Sales Order: 1OTM2526001596
       ├─ Company DC: 1DNT2526DC2995 (Customer Order No. = ★)
       └─ Company Invoice: 1ITR2526001841 (Customer Order No. = ★, SO No. = 1OTM2526001596)

Vendor Invoice: (vendor invoice number from Vendor Type 1)
  └─ Company PO: (company PO number, Bill No. = vendor invoice number)
```

| Document | Primary Ref | PO Reference (★) | Sales Order (●) |
|---|---|---|---|
| Customer PO | ★ customer PO number | — | — |
| Company DC | 1DNT2526DC2995 | ★ | 1OTM2526001596 |
| Company Invoice | 1ITR2526001841 | ★ | 1OTM2526001596 |
| Vendor Invoice | vendor invoice number | company SO number | — |
| Company PO | company PO number | Bill No = vendor inv | — |

---

### 3.2 Customer B (Most Complex — 2 delivery locations)

```
Customer PO (★ PO Number from customer — 42 pages)
  ├─ Sales Order #1: 1OTM2526001386
  │    ├─ Company DC #1: 1DNT2526DC2903 (Customer Order No. = ★)
  │    └─ Company Invoice #1: 1ITR2526001794 (Customer Order No. = ★, SO No. = 1OTM2526001386)
  │
  └─ Sales Order #2: 1OTM2526001387
       ├─ Company DC #2: 1DNT2526DC2902 (Customer Order No. = ★)
       └─ Company Invoice #2: 1ITR2526001793 (Customer Order No. = ★, SO No. = 1OTM2526001387)

Vendor Invoice #1: (from Vendor Type 2, 2 pages)
  └─ Part of company PO procurement chain

Vendor Invoice #2: (from Vendor Type 3, 13 pages)
  └─ Part of company PO procurement chain

Company PO: (Bill No. references one of the vendor invoices)
```

**Key insight**: One customer PO → multiple sales orders → multiple DCs + invoices. The PO number (★) links everything together, while SO numbers (●) pair specific DC↔Invoice pairs.

---

### 3.3 Customer C

```
Customer PO (★ PO Number from customer)
  └─ Sales Order: 1OTM2526001544
       ├─ Company DC: 1DNT2526DC2919 (Customer Order No. = ★)
       └─ Company Invoice: 1ITR2526001789 (Customer Order No. = ★, SO No. = 1OTM2526001544)

Vendor Invoice: (from Vendor Type 4)
  └─ Company PO: (Bill No. = vendor invoice number)
```

| Document | Primary Ref | PO Reference (★) | Sales Order (●) |
|---|---|---|---|
| Customer PO | ★ customer PO number | — | — |
| Company DC | 1DNT2526DC2919 | ★ | 1OTM2526001544 |
| Company Invoice | 1ITR2526001789 | ★ | 1OTM2526001544 |
| Vendor Invoice | vendor invoice number | company SO number | — |
| Company PO | company PO number | Bill No = vendor inv | — |

---

### 3.4 Customer D

```
Customer PO (★ PO Number from customer)
  └─ Sales Order: 1OTM2526001448
       ├─ Company DC: 1DNT2526DC2865 (Customer Order No. = ★)
       └─ Company Invoice: 1ITR2526001748 (Customer Order No. = ★, SO No. = 1OTM2526001448)

Vendor Invoice: (from Vendor Type 5, 3 pages)
  └─ Company PO: (Bill No. = vendor invoice number)
```

| Document | Primary Ref | PO Reference (★) | Sales Order (●) |
|---|---|---|---|
| Customer PO | ★ customer PO number | — | — |
| Company DC | 1DNT2526DC2865 | ★ | 1OTM2526001448 |
| Company Invoice | 1ITR2526001748 | ★ | 1OTM2526001448 |
| Vendor Invoice | vendor invoice number | company SO number | — |
| Company PO | company PO number | — | — |

---

### 3.5 Customer E (2 invoices — services + products)

```
Customer PO (★ PO Number from customer — no PDF available)
  └─ Sales Order: 1OTM2526001428
       ├─ Company DC: 1DNT2526DC2871 (Customer Order No. = ★, 5 pages)
       ├─ Company Invoice (services): 1ISR2526000166 (SO No. = 1OTM2526001428)
       └─ Company Invoice (products): 1ITR2526001751 (SO No. = 1OTM2526001428)

Vendor Invoice: (from Vendor Type 3, 2 pages)
  └─ Company PO: (Bill No. = vendor invoice number)
```

**Key insight**: Same SO number → 2 invoices (one for services `1ISR`, one for products `1ITR`). This demonstrates that the SO↔Invoice relationship can be one-to-many.

---

## 4. Cross-Document Connecting Keys

### 4.1 The Three Master Keys

#### ★ Customer PO Number — PRIMARY CHAIN KEY

| Appears On | Field Name | Label on Document |
|---|---|---|
| Customer PO | `po_number` | PO number (header) |
| Company DC | `po_reference` | "Customer Order No." |
| Company Invoice | `po_reference` | "Customer Order No." |

**Links**: Customer PO → Company DC → Company Invoice (all in one transaction)

#### ● Sales Order Number — DC↔INVOICE LINK

| Appears On | Field Name | Label on Document |
|---|---|---|
| Company DC | `sales_order_no` (NEW) | "Sales Order No." |
| Company Invoice | `so_number` | "SO No." |

**Links**: Specific Company DC ↔ Specific Company Invoice (1:1 or 1:many)

#### ◆ Vendor Invoice Number — PROCUREMENT CHAIN LINK

| Appears On | Field Name | Label on Document |
|---|---|---|
| Vendor Invoice | `invoice_number` | "Invoice No." / "Bill No." |
| Company PO | `bill_no` | "Bill No." |

**Links**: Vendor Invoice ↔ Company PO (what was bought from vendor)

### 4.2 Document Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    SALES CHAIN (★ PO Number)                     │
│                                                                  │
│  CUSTOMER PO ──────────► COMPANY DC ──────────► COMPANY INVOICE │
│  (po_number=★)           (po_ref=★,            (po_ref=★,       │
│                           so_no=●)              so_no=●)         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 PROCUREMENT CHAIN (◆ Vendor Inv)                 │
│                                                                  │
│  VENDOR INVOICE ──────────► COMPANY PO                           │
│  (inv_number=◆)             (bill_no=◆)                          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Connecting Points Summary

| From Document | To Document | Via Field | Direction |
|---|---|---|---|
| Customer PO | Company DC | PO Number (★) | ★ appears as `po_reference` on DC |
| Customer PO | Company Invoice | PO Number (★) | ★ appears as `po_reference` on Invoice |
| Company DC | Company Invoice | Sales Order (●) | ● appears as `so_number` on Invoice |
| Vendor Invoice | Company PO | Invoice Number (◆) | ◆ appears as `bill_no` on Company PO |
| Company DC | Company Invoice | Customer works both ways | Both have same ★ and ● |

### 4.4 Cardinality Rules

| Relationship | Cardinality | Example |
|---|---|---|
| Customer PO → Sales Orders | 1 : Many | Customer B: 1 PO → 2 SOs |
| Sales Order → Company DC | 1 : 1 | Each SO dispatches one DC |
| Sales Order → Company Invoice | 1 : Many | Customer E: 1 SO → 2 invoices (service + product) |
| Customer PO → Vendor Invoices | 1 : Many | Customer B: 1 PO → invoices from 2 vendors |
| Vendor Invoice → Company PO | 1 : 1 | Each vendor invoice has one company PO |

---

## 5. Root Cause Analysis

### RC1: Ollama 500 on Complex Pages
- **Affected**: Customer B's 42-page customer PO (page 1 crashes model)
- **Cause**: Page too complex for 1.1B parameter model — causes GGML tensor error
- **Fix**: Skip failed pages, try next page. Partial extraction > total failure.

### RC2: I vs 1 OCR Confusion
- **Affected**: All invoice numbers starting with "1ITR" → OCR reads as "11TR"
- **Cause**: Font renders `I` similar to `1` at 768px resolution
- **Fix**: Model limitation. Can add post-processing rule: if invoice number starts with "11TR" or "11SR", replace first "1" with "I". But risky if legitimate numbers exist.

### RC3: Multi-Page DCs — Last Page Data Missing
- **Affected**: Customer B (6-page DCs), Customer E (5-page DC)
- **Cause**: Totals and amounts only appear on the last page (page 5 or 6)
- **Fix**: Current `pdf_converter.py` already includes last pages for docs > max_pages. For docs ≤ 10 pages all pages are sent. Issue may be that OCR model ignores later pages if first page has enough data. Solution: ensure prompt says "if amounts not found on current page, return null" so merger picks up from last page.

### RC4: "Reference" Person Name vs "Customer Order No."
- **Affected**: Company DCs — model sometimes puts person name from "Reference" field into `po_reference`
- **Cause**: Both fields are in the header area. "Reference" field contains a contact person name.
- **Fix**: Prompt already says `po_reference` is NOT a person name. Reinforce with: "Look for the field labeled 'Customer Order No.' specifically."

### RC5: Missing `sales_order_no` in Company DC Schema
- **Affected**: All company DCs
- **Cause**: Field simply not defined in extraction schema
- **Fix**: Add `sales_order_no` to COMPANY_DC schema in prompts.py. **Phase 1.1 fix.**

### RC6: Blank/Faded Headers on Some Company POs
- **Affected**: Some company PO documents have cropped or faded header area
- **Cause**: Scan quality / physical document condition
- **Fix**: Not fixable via software. Operator may need to re-scan.

---

## 6. Field Coverage Matrix

Shows which fields are extractable from the first 2-3 pages of each document type:

### Company DC (Pages 1-2)

| Field | Page 1 | Page 2+ | Extraction Reliability |
|---|---|---|---|
| dc_number | ✅ | — | High (95%+) |
| dc_date | ✅ | — | High (95%+) |
| po_reference (Customer Order No.) | ✅ | — | Medium (80%) — RC4 confusion risk |
| sales_order_no | ✅ | — | High (95%+) if added to schema |
| customer_name | ✅ | — | High (90%+) |
| items_description | ✅ | ✅ | Medium — may be incomplete for multi-page |
| quantity | ❌ | Last page | Low for multi-page DCs |
| est_amount | ❌ | Last page | Low for multi-page DCs |
| dispatch_to | ✅ | — | High (90%+) |

### Company Invoice (Pages 1-2)

| Field | Page 1 | Page 2 | Extraction Reliability |
|---|---|---|---|
| invoice_number | ✅ | — | Medium (85%) — RC2 I/1 confusion |
| invoice_date | ✅ | — | High (95%+) |
| po_reference (Customer Order No.) | ✅ | — | High (90%+) |
| so_number | ✅ | — | High (95%+) |
| customer_name | ✅ | — | High (90%+) |
| subtotal | ✅/Page 2 | ✅ | High (90%+) |
| tax_amount | ✅/Page 2 | ✅ | High (90%+) |
| total_amount | ✅/Page 2 | ✅ | High (90%+) |
| irn_number | ✅ | — | Medium (80%) |

### Vendor Invoice (Pages 1-2)

| Field | Page 1 | Page 2 | Extraction Reliability |
|---|---|---|---|
| invoice_number | ✅ | — | High (90%+) |
| invoice_date | ✅ | — | High (90%+) |
| po_reference | ✅ | — | Medium (75%) — label varies by vendor |
| vendor_name | ✅ | — | High (95%+) |
| subtotal | ✅/Last page | ✅ | Medium (85%) |
| tax_amount | ✅/Last page | ✅ | Medium (85%) |
| total_amount | ✅/Last page | ✅ | Medium (85%) |
| gst_number | ✅ | — | High (90%+) |
| irn_number | ✅ | — | Medium (80%) |

### Customer PO (Pages 1-2)

| Field | Page 1 | Page 2 | Extraction Reliability |
|---|---|---|---|
| po_number | ✅ | — | High (90%+) |
| po_date | ✅ | — | High (90%+) |
| customer_name | ✅ | — | High (90%+) |
| shipping_address | ✅ | — | Medium (80%) |
| total_amount | ❌ | Last page | Low for multi-page POs |
| gst_number | ✅ | — | High (90%+) |
| payment_terms | ✅ | — | Medium (75%) |

---

## Summary of Required Schema Changes

| Document Type | Current Fields | Fields to Add | Fields to Fix |
|---|---|---|---|
| COMPANY_DC | 8 fields | `sales_order_no`, `customer_order_date` | `po_reference` prompt clarification |
| COMPANY_INVOICE | 9 fields | `customer_order_date`, `acct_manager` | — |
| VENDOR_INVOICE | 12 fields | — | — |
| CUSTOMER_PO | 9 fields | — | — |
| POD | 8 fields | — | — |
| COMPANY_PO (NEW) | — | Entire new type (deferred) | — |
