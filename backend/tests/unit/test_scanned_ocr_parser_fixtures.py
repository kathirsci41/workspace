"""Fixture-backed regression tests for PaddleOCR scanned-document parsing.

Each fixture is a real PaddleOCR raw-text capture (0deg) of a sample document,
paired with manually verified expected field values
(``expected_fields_scanned_samples.json``).

The test path mirrors production and the Paddle-only diagnosis runner exactly:

    normalize_ocr_text(raw)  ->  parse_structured_text(..., extraction_route="ocr")

so a passing test here means the parser would extract the same value in
production for that scanned document. Values are generic-rule driven; no sample
filename or sample value is hardcoded in the parser.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.extraction.digital_text_extractor import normalize_ocr_text
from app.services.extraction.structured_text_parser import parse_structured_text

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "scanned_ocr_parser"
EXPECTED = json.loads((FIXTURE_DIR / "expected_fields_scanned_samples.json").read_text(encoding="utf-8"))

# Original sample PDF filenames (only affects vendor filename-fallback heuristics;
# every asserted value below is independently present in the OCR text).
FILENAMES = {
    "vendor_bill_2526psi25087738": "Vendor Bill 2526PSI25087738.pdf",
    "tax_invoice_shriram_fin": "Tax Invoice Shriram fin.pdf",
    "tax_invoice_reddington": "Tax invoice reddington.pdf",
    "tax_invoice_inflow_amc": "Tax invoice inflow AMC.pdf",
    "purchase_order_shriram_fin": "Shriram finance PO.pdf",
}

# Amount fields are compared numerically (JSON stores them as strings, the parser
# returns float/int).
_AMOUNT_FIELDS = {
    "invoice_total",
    "total_amount",
    "taxable_amount",
    "tax_amount",
    "subtotal_amount",
}


def _parse_fixture(slug: str) -> dict:
    raw = (FIXTURE_DIR / f"{slug}.txt").read_text(encoding="utf-8")
    normalized = normalize_ocr_text(raw)
    result = parse_structured_text(
        EXPECTED[slug]["document_type"],
        normalized,
        extraction_route="ocr",
        filename=FILENAMES[slug],
    )
    return result["fields"]


def _iter_cases():
    for slug, spec in EXPECTED.items():
        for field, expected_value in spec["expected_fields"].items():
            yield pytest.param(slug, field, expected_value, id=f"{slug}-{field}")


def test_scanned_zero_tax_customer_invoice_keeps_zero_tax_amount():
    """A scanned (OCR-route) zero-tax (LUT/export) customer invoice must keep
    tax_amount=0, not drop it: total == taxable means tax is genuinely zero, and
    that is an arithmetic identity, not a fabricated sum."""
    raw = (
        "SUPPLIER EXPORTS PRIVATE LIMITED\n"
        "TAX INVOICE\n"
        "Invoice No\n"
        ": EXP/2026/0042\n"
        "Invoice Date\n"
        ": 14.03.2026\n"
        "Your Ref\n"
        ": 1PTR2526000999\n"
        "Bill-To:\n"
        "SKYLARK INFORMATION TECHNOLOGIES\n"
        "SUPPLY MEANT FOR EXPORT UNDER LUT WITHOUT PAYMENT OF INTEGRATED TAX\n"
        "Total before Tax\n"
        "250000.00\n"
        "Tax Total\n"
        "0.00\n"
        "Invoice Total\n"
        "250000.00\n"
    )
    result = parse_structured_text(
        "CUSTOMER_INVOICE",
        normalize_ocr_text(raw),
        extraction_route="ocr",
    )
    fields = result["fields"]
    assert fields["total_amount"] == 250000
    assert fields["taxable_amount"] == 250000
    assert fields["tax_amount"] == 0


@pytest.mark.parametrize("slug, field, expected_value", list(_iter_cases()))
def test_scanned_fixture_field(slug, field, expected_value):
    fields = _parse_fixture(slug)
    actual = fields.get(field)

    if expected_value is None:
        # A null expected value means the value is not present verbatim in the
        # OCR text and the parser must NOT fabricate it.
        assert actual is None, f"{slug}.{field} expected absent/None, got {actual!r}"
        return

    assert actual is not None, f"{slug}.{field} missing; expected {expected_value!r}"

    if field in _AMOUNT_FIELDS:
        assert float(str(actual).replace(",", "")) == pytest.approx(
            float(str(expected_value).replace(",", ""))
        ), f"{slug}.{field} expected {expected_value!r}, got {actual!r}"
    else:
        assert str(actual).strip() == str(expected_value).strip(), (
            f"{slug}.{field} expected {expected_value!r}, got {actual!r}"
        )
