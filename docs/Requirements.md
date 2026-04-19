# Document Processing Platform (DPP)
# Purchase Order Scenarios, Document Types, Extraction Fields & Sample Requirements

---

| | |
|---|---|
| **Prepared by** | [Your Name / Company] |
| **Prepared for** | [Client Name] |
| **Document version** | 1.0 |
| **Date** | March 2026 |
| **Status** | For Review and Approval |

---

## Table of Contents

1. Overview
2. Purchase Order Scenarios — Input Required from Your Team
3. Document Types — What Data Is Extracted
4. Document Sample Requirements — Scenarios and Count
5. AI Pipeline Testing and Experimentation — Hardware Requirements
6. Sample Submission Guidelines

---

## 1. Overview

This document is prepared as part of the Document Processing Platform (DPP) engagement. It covers three things:

- **Scenarios** — We need your team to describe the different types of Purchase Orders your business handles, so the system is built and tested to match your actual workflow
- **Extraction fields** — What data the system currently reads from each document type, and what will be added in further enhancements
- **Sample requirements** — Why we need document samples, how many, and what types of scenarios they should cover

The purpose of sharing this document is to align on what the system does and to gather the information we need to move forward effectively.

---

## 2. Purchase Order Scenarios — Input Required from Your Team

Every logistics business has its own way of handling orders. The document chain can vary significantly depending on how an order is fulfilled — whether from stock, through a vendor, in multiple batches, or with returns and replacements involved.

To ensure the system is built and tested accurately for your business, we need your team to describe the scenarios you handle. **Please answer the questions below.**

---

### 2.1 How is a typical Customer Purchase Order fulfilled?

*Describe the step-by-step process from when you receive a Customer PO to when the final invoice is raised. For example: does every customer PO require a vendor order, or do some orders get fulfilled from existing stock?*

**Your response:**
> *(Please fill in)*

---

### 2.2 Which of the 6 document types are always present, and which are sometimes not required?

For each document type, please indicate whether it is always generated, sometimes generated, or never generated in your process:

| Document Type | Always | Sometimes | Never | Notes |
| --- | --- | --- | --- | --- |
| Customer PO | | | | |
| Company PO (to Vendor) | | | | |
| Vendor Delivery Challan | | | | |
| Vendor Invoice (Vendor Bill) | | | | |
| Company Delivery Challan | | | | |
| Company Invoice (Company Bill) | | | | |

---

### 2.3 Do you handle partial fulfillment? (One Customer PO fulfilled in multiple dispatches)

*If yes, please describe how documents are managed across batches — for example, is a new vendor PO raised for each batch, or is one vendor PO split?*

**Your response:**
> *(Please fill in)*

---

### 2.4 Do you handle returns or replacements?

If yes, what documents are issued when a return happens? (Credit Note, Debit Note, replacement DC, etc.)

**Your response:**
> *(Please fill in)*

---

### 2.5 Are there any other special order types in your business?

*For example: direct vendor-to-customer dispatch, inter-branch transfers, consignment orders, service orders with no physical goods, etc.*

**Your response:**
> *(Please fill in)*

---

### 2.6 Are there any documents your business uses that are not listed in the 6 types above?

*For example: Proof of Delivery (POD), Gate Pass, Quality Inspection Report, E-Way Bill as a standalone document, etc.*

**Your response:**
> *(Please fill in)*

---

> **Note:** Your responses here will directly determine how the system is configured, tested, and validated for your workflow. There are no right or wrong answers — we simply need an accurate picture of how your team operates.

---

## 3. Document Types — Extraction Fields

For each document type, we list:
- What the document is and its business purpose
- Fields **currently extracted** by the AI system
- Fields **planned for further enhancement** in the next phase

---

### 3.1 Customer Purchase Order (Customer PO)

**What it is:**
The order placed by your customer requesting goods or services. This is the starting point of every document chain in DPP.

**Flow direction:** Customer → Your Company

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | PO Number | `po_number` | Unique PO reference prominently displayed on the document | PO/2526/00123 |
| 2 | PO Date | `po_date` | Date exactly as printed on the document | 15-Jan-2026 |
| 3 | BSIF Name | `bsif_name` | Business/company name from the PO header — the entity issuing the order | ABC Enterprises |

---

#### What Additional Data Do You Need From the Customer PO?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

### 3.2 Company Purchase Order (Company PO)

**What it is:**
The order raised by your company to a vendor to procure goods for fulfilling a customer order.

**Flow direction:** Your Company → Vendor

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | Purchase Bill Number | `purchase_bill_no` | Vendor-issued bill number (typically starts with 1PBTR) | 1PBTR2526000123 |
| 2 | PO Number | `po_number` | Our company's PO number issued to this vendor (typically starts with 1PTR) | 1PTR2526000405 |
| 3 | Bill Number | `bill_no` | Vendor's own internal bill or invoice number | VND-INV-2025-089 |

---

#### What Additional Data Do You Need From the Company PO?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

### 3.3 Vendor Delivery Challan (Vendor DC)

**What it is:**
The document the vendor sends along with the physical goods at the time of dispatch. It is proof that goods left the vendor's premises.

**Flow direction:** Vendor → Your Company

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | DC Number | `dc_number` | Delivery Challan number (e.g. 1DNT2526DC2865) | 1DNT2526DC2865 |
| 2 | DC Date | `dc_date` | DC date exactly as printed on the document | 20-Jan-2026 |
| 3 | PO Reference | `po_reference` | Purchase Order number this DC fulfils | 1PTR2526000405 |
| 4 | Vendor Name | `vendor_name` | Name of the vendor or supplier sending goods | XYZ Polymers Pvt Ltd |
| 5 | Items Description | `items_description` | All items as one string separated by semicolons, including part numbers and serial numbers | HDPE 63mm × 520 Nos; Fittings × 50 Nos |
| 6 | Quantity | `quantity` | Total quantity of items shipped | 570 |
| 7 | Vehicle Number | `vehicle_number` | Vehicle or transport number | KA-01-AB-1234 |
| 8 | Receiver Name | `receiver_name` | Name of the person who physically received the goods | Raju (with signature) |

---

#### What Additional Data Do You Need From the Vendor DC?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

### 3.4 Vendor Invoice (Vendor Bill)

**What it is:**
The bill raised by the vendor after dispatching goods. This is what your company pays to the vendor.

**Flow direction:** Vendor → Your Company

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | Invoice Number | `invoice_number` | Vendor's invoice or bill number (labeled Invoice No., Tax Invoice No., or Bill No.) | INV/XYZ/2526/0234 |
| 2 | Customer Order Number | `customer_order_no` | Customer's SO or order number as referenced by the vendor (labeled Customer Order No. or Your Order No.) | SO-2526-0098 |
| 3 | PO Reference | `po_reference` | Our company's PO number sent to this vendor (labeled Buyer Order No., Your Ref, or Customer PO) | 1PTR2526000405 |

---

#### What Additional Data Do You Need From the Vendor Invoice?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

### 3.5 Company Delivery Challan (Company DC)

**What it is:**
The document your company sends along with goods when dispatching to the customer. It is proof of dispatch from your side.

**Flow direction:** Your Company → Customer

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | DC Number | `dc_number` | Delivery Challan number (e.g. 1DNT2526DC2871) | 1DNT2526DC2871 |
| 2 | DC Date | `dc_date` | Date of dispatch exactly as printed (labeled DC Date) | 22-Jan-2026 |
| 3 | PO Reference | `po_reference` | Customer's Order or PO number (labeled Customer Order No.) | PO/2526/00123 |
| 4 | Sales Order Number | `sales_order_no` | Internal Sales Order number (labeled Sales Order No., starts with 1OTM) | 1OTM2526001448 |
| 5 | Dispatch To | `dispatch_to` | Delivery destination — customer address or name (labeled Delivery To) | Plot 45, KIADB, Tumkur |

---

#### What Additional Data Do You Need From the Company DC?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

### 3.6 Company Invoice (Company Bill)

**What it is:**
The bill your company raises to the customer for goods supplied. This is what your customer pays your company.

**Flow direction:** Your Company → Customer

---

#### Currently Extracted Fields

| # | Field | Internal Field Name | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | Invoice Number | `invoice_number` | Company's invoice number (starts with 1ITR or 1ISR) | 1ITR2526000567 |
| 2 | PO Reference | `po_reference` | Customer's Order or PO number (labeled Customer Order No.) | PO/2526/00123 |
| 3 | SO Number | `so_number` | Sales Order number (labeled SO No., starts with 1OTM) | 1OTM2526001448 |
| 4 | Customer Name | `customer_name` | Name of the customer being billed | ABC Enterprises |
| 5 | Total Amount | `total_amount` | Grand total after tax — the largest amount on the invoice | ₹70,800 |

---

#### What Additional Data Do You Need From the Company Invoice?

Beyond the fields already extracted above, please tell us what other information your team needs:

**Mandatory — we must have these fields:**
> *(Please list the field names or describe what data you need)*

**Nice to have — useful but not critical:**
> *(Please list)*

**Not needed — fields that are on the document but irrelevant to your workflow:**
> *(Please list, if any)*

---

## 4. Document Sample Requirements

### Why Samples Are Needed

The AI extraction model is trained and tested on real documents. The more varied and representative the samples are, the better the system performs across all the conditions your staff encounter daily.

Since your customers and vendors use different document formats and layouts, **format variation matters more than quantity alone.** A set of 40 diverse samples is far more useful than 40 identical documents.

The same samples will also be used in a later phase to fine-tune the AI model specifically on your document formats — this is what takes extraction accuracy from generally good to highly accurate for your specific business.

---

### Scenarios Each Sample Set Should Cover

The following 12 scenarios must be represented in the samples for each document type:

| # | Scenario | Why It Matters | Min. Samples |
|---|----------|---------------|--------------|
| 1 | Clean digital PDF — standard layout | Most common format — baseline accuracy | 5 |
| 2 | Scanned document — good scan quality | Very common — operators scan physical copies | 5 |
| 3 | Mobile phone photograph — well-lit, straight | Staff regularly photograph documents with phones | 5 |
| 4 | Mobile phone photograph — low light or slight blur | Real-world condition — ensures robustness | 3 |
| 5 | Document with many line items (5 or more products) | Multi-line table extraction is complex | 5 |
| 6 | Document with a single line item | Simpler but layout differs — must be tested | 3 |
| 7 | Different customer or vendor formats (varied templates) | Each business has its own document design | 5 |
| 8 | Documents with rubber stamps or signatures over text | Stamps obscure key fields — very common in India | 3 |
| 9 | Slightly rotated or skewed scan | Happens with flatbed scanners and phone cameras | 3 |
| 10 | Documents with mixed language content (English + regional) | Common in Indian logistics documents | 3 |
| 11 | Amended or revised document (marked as revision) | Needs to extract the latest values correctly | 3 |
| 12 | Multi-page document (2 or more pages) | Long invoices and POs span multiple pages | 3 |
| **Total per document type** | | | **46** |

---

### Total Samples Required

| Document Type | Minimum Samples |
|---------------|-----------------|
| Customer PO | 46 |
| Company PO | 46 |
| Vendor DC | 46 |
| Vendor Invoice (Vendor Bill) | 46 |
| Company DC | 46 |
| Company Invoice (Company Bill) | 46 |
| **Grand Total** | **276** |

Please prioritise the document types that your team handles most frequently so we can begin testing those first while the remaining samples are being prepared.

---

## 5. AI Pipeline Testing and Experimentation — Hardware Requirements

Before committing to a specific AI model or extraction approach, we need to test and compare multiple models against your actual document samples. This section describes the hardware and infrastructure required for that experimentation phase — this is not about hosting the application, it is about running AI model tests, measuring extraction accuracy, and eventually fine-tuning a model specifically on your document formats.

---

### What This Phase Involves

| Activity | Description |
| --- | --- |
| **Model benchmarking** | Running several AI models against the same document samples and comparing extraction accuracy, speed, and cost |
| **Pipeline testing** | Testing different pipeline configurations — single model vs two-model, different prompting strategies, pre-processing steps |
| **Accuracy measurement** | Comparing extracted values against known correct values from the sample documents |
| **Fine-tuning** | Training a model on your documents so it learns your specific formats, improving accuracy beyond what a general model achieves |

---

### Why GPU Matters for This Work

All AI models used for document extraction are neural networks that run significantly faster on a GPU than a CPU. The practical difference:

| Task | CPU Only | With GPU |
| --- | --- | --- |
| Run inference on one document | 30–120 seconds | 2–8 seconds |
| Test 276 document samples | 2–6 hours | 10–30 minutes |
| Fine-tune a 7B parameter model | Days (impractical) | 4–12 hours |
| Fine-tune a 3B parameter model | ~24 hours (borderline) | 2–5 hours |

For benchmarking alone, CPU is slow but usable. For fine-tuning, a GPU is effectively required.

---

### Option 1 — Local Machine with GPU

Running experiments on a local workstation or laptop with a dedicated GPU.

| Component | Minimum for Testing | Recommended for Fine-tuning |
| --- | --- | --- |
| GPU | NVIDIA 6 GB VRAM (e.g. RTX 3050 / 3060) | NVIDIA 16–24 GB VRAM (e.g. RTX 4070 Ti / 3090) |
| CPU | 8 cores | 12+ cores |
| RAM | 16 GB | 32 GB |
| Storage | 100 GB free | 250 GB free (model files + datasets) |
| OS | Windows with WSL2 or Ubuntu | Ubuntu preferred |

**Suitable for:** Testing 3B and 7B parameter models. Fine-tuning of 3B models is feasible. Fine-tuning 7B models requires 16+ GB VRAM.

**Limitation:** Fine-tuning requires the machine to be available for multiple hours continuously without interruption. Not practical if the machine is a daily-use workstation.

---

### Option 2 — Cloud GPU Instance (On-Demand)

Renting a GPU instance from a cloud provider for the duration of the experiment. Pay only for the hours used — no hardware investment required.

| Provider | Instance Type | GPU | VRAM | Approx. Cost |
| --- | --- | --- | --- | --- |
| RunPod | RTX 3090 Pod | RTX 3090 | 24 GB | ~$0.34–0.44 / hour |
| RunPod | A100 Pod | A100 | 80 GB | ~$1.64 / hour |
| Google Colab Pro+ | T4 or A100 | T4 / A100 | 16 / 40 GB | ~$10–50 / month flat |
| Azure | NC4as T4 v3 | NVIDIA T4 | 16 GB | ~$0.50 / hour |
| Lambda Labs | 1x A10 | A10 | 24 GB | ~$0.60 / hour |

**Suitable for:** All model sizes. Fine-tuning any model up to 13B parameters is straightforward on an A100 or RTX 3090. Cloud instances can be started for a specific experiment and shut down immediately after.

**Recommended approach for this project:** Use RunPod or Colab for fine-tuning experiments. Reserve local GPU (if available) for day-to-day inference testing.

---

### Option 3 — CPU Only (Limited Use)

Running models on CPU without any GPU. Feasible for small models only.

| Model Size | CPU Inference Speed | Fine-tuning |
| --- | --- | --- |
| 1B–3B parameters | Slow but usable (30–90 sec/doc) | Technically possible, impractical (hours per step) |
| 7B parameters | Very slow (2–5 min/doc) | Not recommended |
| 13B and above | Extremely slow | Not feasible |

**Suitable for:** Initial feasibility checks on small models. Not recommended for any serious benchmarking or fine-tuning work.

---

### Storage Requirements for AI Experimentation

| Item | Approximate Size |
| --- | --- |
| glm-ocr model (Layer 1 OCR) | ~4 GB |
| qwen2.5:7b model (Layer 2 extraction) | ~4.7 GB |
| qwen2.5:3b model (lighter alternative) | ~2 GB |
| qwen2-vl:7b (single vision model alternative) | ~5 GB |
| Document sample dataset (276 files, PDF + images) | ~2–5 GB |
| Fine-tuning dataset (LoRA format, prepared from samples) | ~500 MB |
| Fine-tuned model checkpoints | ~1–3 GB per run |

**Recommended free storage for experimentation:** 50–100 GB to allow multiple model versions and experiment checkpoints.

---

### Recommended Approach for This Project

Given the document volumes and the goal of testing the extraction pipeline before moving further:

1. **Phase 1 — Benchmarking** (no GPU required): Use RunPod remote endpoint as currently configured. Test extraction accuracy on the 276 sample documents. Measure field-level accuracy per document type.

2. **Phase 2 — Model comparison** (GPU recommended): Test 2–3 alternative models (e.g. qwen2.5:3b, qwen2-vl:7b) on the same samples. Rent a cloud GPU instance for a few hours — cost is minimal.

3. **Phase 3 — Fine-tuning** (GPU required): Once the best base model is identified, prepare a fine-tuning dataset from the verified samples and run LoRA fine-tuning on a cloud GPU instance. Expected duration: 4–12 hours depending on model size and dataset size.

---

## 6. Sample Submission Guidelines

To make the most of the samples you provide:

| # | Guideline | Detail |
|---|-----------|--------|
| 1 | **Preferred format** | PDF is preferred. Scanned images (JPG, PNG, TIFF) are also accepted |
| 2 | **Sensitive data** | Amounts, party names, and GST numbers can be masked or replaced — the layout and structure is what we analyse, not the actual values |
| 3 | **File naming** | Name files clearly — e.g. `CUSTOMER_PO_digital_clean_01.pdf`, `VENDOR_DC_phone_photo_blur_02.jpg` |
| 4 | **Variety** | Include samples from at least 3 to 4 different customers or vendors to capture format variation |
| 5 | **Priority** | If providing all 6 types is not immediately possible, start with Customer PO and Company Invoice as these are the highest-value types for the current phase |
| 6 | **Delivery** | Samples can be shared via a shared folder, email attachment, or any file transfer method that is convenient for your team |

---

*This document is prepared as part of the DPP v2.2.0 engagement — March 2026.*

*Additional fields listed under each document type will be prioritised and implemented based on your inputs.*

*For questions or clarifications on this document, please contact [Your Name] at [Your Contact].*
