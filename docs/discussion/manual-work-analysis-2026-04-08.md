# Manual Work Analysis — DPP v2.5.0
**Date:** 2026-04-08
**Context:** Pre-production review — identifying manual bottlenecks and Phase 2 automation path

---

## Current Manual vs Automated Split

| Process Step | Current State | Manual Weight |
|---|---|---|
| Scan & upload PDF | 100% manual | Heavy |
| PO creation | 100% manual | Heavy |
| AI extraction (OCR + structured data) | Automated | Done |
| Field verification | 100% manual | Heavy |
| Field corrections | 100% manual | Heavy |
| Item comparison judgment | AI matches, human judges discrepancies | Medium |
| Discrepancy resolution | 100% manual | Heavy |
| Order closure decision | Manual by design (manager decision) | By design |
| PENDING_MODEL requeue | Manual admin click | Medium |
| Excel export / dispute pack | Manual trigger, automated generation | Light |

---

## The Three Heaviest Bottlenecks

### 1. Document Verification — every single document

Every uploaded document sits at `PENDING_REVIEW` until a human opens the ReviewModal, reads the PDF side-by-side with extracted fields, and clicks Verify.

For a STOCK order (6 required documents) that's 6 separate review sessions per PO.

**The key gap:** The confidence score is extracted but not acted on. Even a 99% confident extraction waits for human review.

```
AI extracts → confidence = 94% → still waits for human
AI extracts → confidence = 31% → still waits for human
```

**Phase 2 fix:** Auto-verify when confidence ≥ threshold (e.g., 90%). Only surface low-confidence extractions and VENDOR documents for human review.

---

### 2. PO Creation — zero automation

Every PO is created by hand:
- Customer selection
- PO number
- Order scenario (STOCK / PROCUREMENT / DROP_SHIP / SERVICE_AMC)
- GST type
- SO number
- Total amount

There is no CSV bulk import, no ERP integration, no email parsing. For companies processing 50+ POs per month, this is significant daily data entry.

**Phase 2 fix:** CSV import endpoint or email-to-PO parsing using the same extraction pipeline.

---

### 3. Field Corrections — no learning loop yet

The `ExtractionCorrection` table captures every correction operators make:
```
{ document_id, field, original_value, corrected_value, corrected_at }
```

But nothing reads that table back into the pipeline. There is no:
- Fine-tuning pipeline that uses corrections to improve qwen2.5:7b
- Pattern detection ("extraction always gets invoice totals wrong for Vendor X")
- Pre-population of likely corrections from historical patterns

**The audit trail exists. The learning loop is not wired yet.**

This is intentional — Phase 1 is data collection. Phase 2 closes the loop.

---

## Why This is Intentional (Phase 1 vs Phase 2 Design)

From the PDD (confirmed 2026-03-31):

> **Phase 1:** Manual data entry + rules-based verification + all UI.
> **Phase 2:** AI extraction + fuzzy matching (item linking, address normalization, product code matching).

The manual work in Phase 1 serves a purpose: every correction written to `ExtractionCorrection` is training data for the Phase 2 fine-tuning pipeline. Operators are unknowingly labelling the dataset.

---

## Phase 2 Automation Targets

| Manual Step | Phase 2 Automation | Prerequisite |
|---|---|---|
| Field verification (high confidence) | Auto-verify if confidence ≥ 90% | Confidence calibration |
| Item comparison judgment | Auto-flag only true mismatches, suppress noise | Item matcher tuning |
| Field corrections → model improvement | Fine-tune Layer 2 on `ExtractionCorrection` data | Enough corrections collected |
| Discrepancy resolution (common patterns) | Auto-resolve date format diffs, amount rounding | Rule engine or LLM |
| PENDING_MODEL requeue | Auto-requeue on health check recovery | Scheduler or signal |
| PO creation (bulk) | CSV import or email-to-PO parsing | Integration work |

The architecture already supports all of these — the pipeline is designed to have steps added, not rewritten.

---

## Production Implication

Moving to production with the current manual weight means:
- **Staffing requirement:** At least 1 dedicated operator per ~30 POs/day (6 document verifications each)
- **Latency:** PO chain completion depends on operator availability, not just AI speed
- **Training:** Operators need to understand document types, field meanings, and rejection criteria

The confidence auto-verify (item 1 above) is the single change that would most reduce operator workload in Phase 2 — it only requires a threshold config, not new models.

---

*Related: `docs/architecture/user-flows-2026-04-08.md` — section 3 (Operator Review flow)*
*Related: `docs/architecture/architecture-deep-analysis-2026-04-07.md` — section 9 (Known Gaps)*
