"""Phase 1r: Focused unit tests for the bundle validation runner.

Tests cover:
- Field comparison classification (exact_match / missing / value_mismatch / no_baseline)
- compare_extracted_to_baseline: field result shape, missing vs mismatch, provenance
- Data class shapes: FieldResult, DocumentResult, BundleResult
- Baseline JSON loader (from file, missing file)
- No production mutation (baseline loader is decoupled — caller supplies the baseline dict)
- No document-specific hardcoding (classification logic is generic, baselines loaded from files)

TDD: all tests written before implementation.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.scripts.run_bundle_validation import (
    BundleResult,
    DocumentResult,
    FieldResult,
    classify_field,
    compare_extracted_to_baseline,
    load_baseline_from_json,
)


# ---------------------------------------------------------------------------
# classify_field — pure classification logic
# ---------------------------------------------------------------------------

class TestClassifyField:
    def test_exact_match_string(self):
        assert classify_field("CHIPL/2025-26/682", "CHIPL/2025-26/682") == "exact_match"

    def test_exact_match_integer(self):
        assert classify_field(496000, 496000) == "exact_match"

    def test_missing_when_extracted_none(self):
        assert classify_field(None, "CHIPL/2025-26/682") == "missing"

    def test_missing_when_extracted_empty_string(self):
        assert classify_field("", "CHIPL/2025-26/682") == "missing"

    def test_value_mismatch_string(self):
        assert classify_field("WRONG/001", "CHIPL/2025-26/682") == "value_mismatch"

    def test_value_mismatch_integer(self):
        assert classify_field(100000, 496000) == "value_mismatch"

    def test_no_baseline_when_expected_none(self):
        assert classify_field("CHIPL/2025-26/682", None) == "no_baseline"

    def test_no_baseline_when_both_none(self):
        assert classify_field(None, None) == "no_baseline"

    def test_numeric_string_mismatch(self):
        # "496000" != 496000 — not coerced
        assert classify_field("496000", 496000) == "value_mismatch"


# ---------------------------------------------------------------------------
# compare_extracted_to_baseline
# ---------------------------------------------------------------------------

class TestCompareExtractedToBaseline:
    def test_returns_exact_match_for_matching_fields(self):
        extracted = {"customer_po_no": "CHIPL/2025-26/682", "grand_total": 496000}
        metadata = {"customer_po_no": {"source": "rules"}, "grand_total": {"source": "rules"}}
        baseline = {"customer_po_no": "CHIPL/2025-26/682", "grand_total": 496000}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["customer_po_no"].classification == "exact_match"
        assert results["grand_total"].classification == "exact_match"

    def test_missing_field_classified_as_missing(self):
        extracted = {"customer_po_no": "CHIPL/2025-26/682"}
        metadata = {}
        baseline = {"customer_po_no": "CHIPL/2025-26/682", "grand_total": 496000}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["grand_total"].classification == "missing"
        assert results["grand_total"].extracted is None

    def test_mismatched_field_classified_as_value_mismatch(self):
        extracted = {"grand_total": 100000}
        metadata = {}
        baseline = {"grand_total": 496000}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["grand_total"].classification == "value_mismatch"
        assert results["grand_total"].extracted == 100000
        assert results["grand_total"].expected == 496000

    def test_no_baseline_all_fields_classified_no_baseline(self):
        extracted = {"customer_po_no": "CHIPL/2025-26/682", "grand_total": 496000}
        metadata = {}
        results = compare_extracted_to_baseline(extracted, metadata, None)
        assert all(r.classification == "no_baseline" for r in results.values())

    def test_no_baseline_includes_all_extracted_fields(self):
        extracted = {"customer_po_no": "X", "grand_total": 1}
        metadata = {}
        results = compare_extracted_to_baseline(extracted, metadata, None)
        assert set(results.keys()) == {"customer_po_no", "grand_total"}

    def test_source_provenance_captured_from_metadata(self):
        extracted = {"customer_po_no": "CHIPL/2025-26/682"}
        metadata = {"customer_po_no": {"source": "rules", "confidence": 0.95}}
        baseline = {"customer_po_no": "CHIPL/2025-26/682"}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["customer_po_no"].source == "rules"

    def test_source_is_none_when_not_in_metadata(self):
        extracted = {"customer_po_no": "CHIPL/2025-26/682"}
        metadata = {}
        baseline = {"customer_po_no": "CHIPL/2025-26/682"}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["customer_po_no"].source is None

    def test_result_contains_expected_and_extracted_values(self):
        extracted = {"invoice_no": "1IAM2526000527"}
        metadata = {}
        baseline = {"invoice_no": "1IAM2526000527"}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        fr = results["invoice_no"]
        assert fr.extracted == "1IAM2526000527"
        assert fr.expected == "1IAM2526000527"

    def test_baseline_fields_not_in_extracted_have_none_extracted(self):
        extracted = {}
        metadata = {}
        baseline = {"customer_po_no": "CHIPL/2025-26/682"}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert results["customer_po_no"].extracted is None

    def test_result_keys_are_field_names(self):
        extracted = {"vendor_invoice_no": "333335674"}
        metadata = {}
        baseline = {"vendor_invoice_no": "333335674", "po_reference": "1POC2526000408"}
        results = compare_extracted_to_baseline(extracted, metadata, baseline)
        assert "vendor_invoice_no" in results
        assert "po_reference" in results


# ---------------------------------------------------------------------------
# Data class shape tests
# ---------------------------------------------------------------------------

class TestDataClasses:
    def test_field_result_has_required_attributes(self):
        fr = FieldResult(
            field="customer_po_no",
            extracted="CHIPL/2025-26/682",
            expected="CHIPL/2025-26/682",
            classification="exact_match",
            source="rules",
        )
        assert fr.field == "customer_po_no"
        assert fr.extracted == "CHIPL/2025-26/682"
        assert fr.expected == "CHIPL/2025-26/682"
        assert fr.classification == "exact_match"
        assert fr.source == "rules"

    def test_document_result_has_required_attributes(self):
        doc = DocumentResult(
            bundle_name="AMC",
            doc_type="CUSTOMER_PO",
            filename="AMC - CUSTOMER PO.pdf",
            extraction_status="EXTRACTED",
            extraction_route="digital_rules",
            ocr_status="skipped_digital_text",
            has_baseline=True,
            fields={},
        )
        assert doc.bundle_name == "AMC"
        assert doc.doc_type == "CUSTOMER_PO"
        assert doc.filename == "AMC - CUSTOMER PO.pdf"
        assert doc.extraction_status == "EXTRACTED"
        assert doc.extraction_route == "digital_rules"
        assert doc.ocr_status == "skipped_digital_text"
        assert doc.has_baseline is True
        assert doc.fields == {}

    def test_bundle_result_has_required_attributes(self):
        br = BundleResult(bundle_name="AMC", run_dir="/some/path", documents=[])
        assert br.bundle_name == "AMC"
        assert br.run_dir == "/some/path"
        assert br.documents == []

    def test_bundle_result_accepts_document_list(self):
        doc = DocumentResult(
            bundle_name="AMC", doc_type="CUSTOMER_PO", filename="f.pdf",
            extraction_status="EXTRACTED", extraction_route="digital_rules",
            ocr_status="skipped_digital_text", has_baseline=False, fields={},
        )
        br = BundleResult(bundle_name="AMC", run_dir="/p", documents=[doc])
        assert len(br.documents) == 1
        assert br.documents[0].doc_type == "CUSTOMER_PO"


# ---------------------------------------------------------------------------
# Baseline JSON loader
# ---------------------------------------------------------------------------

class TestLoadBaselineFromJson:
    def test_returns_nested_dict(self, tmp_path: Path):
        data = {
            "CUSTOMER_PO": {"customer_po_no": "TEST/123", "grand_total": 100000},
            "VENDOR_INVOICE": {"vendor_invoice_no": "INV001"},
        }
        f = tmp_path / "baseline.json"
        f.write_text(json.dumps(data))
        result = load_baseline_from_json(str(f))
        assert result["CUSTOMER_PO"]["customer_po_no"] == "TEST/123"
        assert "VENDOR_INVOICE" in result

    def test_returns_empty_dict_when_file_not_found(self, tmp_path: Path):
        result = load_baseline_from_json(str(tmp_path / "nonexistent.json"))
        assert result == {}

    def test_returns_empty_dict_for_empty_json_object(self, tmp_path: Path):
        f = tmp_path / "empty.json"
        f.write_text("{}")
        result = load_baseline_from_json(str(f))
        assert result == {}

    def test_baseline_fields_accessible_by_doc_type(self, tmp_path: Path):
        data = {"COMPANY_INVOICE": {"invoice_no": "1IAM2526000527", "tax_amount": 0}}
        f = tmp_path / "b.json"
        f.write_text(json.dumps(data))
        result = load_baseline_from_json(str(f))
        assert result["COMPANY_INVOICE"]["invoice_no"] == "1IAM2526000527"
        assert result["COMPANY_INVOICE"]["tax_amount"] == 0

    def test_normalizes_list_values_to_first_element(self, tmp_path: Path):
        data = {
            "CUSTOMER_PO": {
                "customer_po_no": ["CHIPL/2025-26/682", "Order No. on customer PO"],
                "grand_total": [496000, "Total 4,96,000.00"],
            }
        }
        f = tmp_path / "baseline.json"
        f.write_text(json.dumps(data))
        result = load_baseline_from_json(str(f))
        assert result["CUSTOMER_PO"]["customer_po_no"] == "CHIPL/2025-26/682"
        assert result["CUSTOMER_PO"]["grand_total"] == 496000

    def test_flat_values_preserved_as_is(self, tmp_path: Path):
        data = {"CUSTOMER_PO": {"grand_total": 496000, "po_no": "ABC/123"}}
        f = tmp_path / "baseline.json"
        f.write_text(json.dumps(data))
        result = load_baseline_from_json(str(f))
        assert result["CUSTOMER_PO"]["grand_total"] == 496000
        assert result["CUSTOMER_PO"]["po_no"] == "ABC/123"
