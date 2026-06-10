from __future__ import annotations

from pathlib import Path

import fitz

from app.services.extraction.pdf_field_locator import locate_pdf_field


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((40, 70), "Invoice No: 1ITR2526001878")
    page.insert_text((40, 100), "Customer Order No: PMCH&RI/024/2025-2026")
    document.save(path)
    document.close()


def test_locator_finds_invoice_number_on_digital_pdf(tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    _write_pdf(pdf_path)

    result = locate_pdf_field(
        str(pdf_path),
        field_name="invoice_no",
        value="1ITR2526001878",
        evidence_text="Invoice No: 1ITR2526001878",
        source="rules",
        confidence=0.9,
    )

    assert result is not None
    assert result["page"] == 1
    assert result["bbox"]
    assert result["page_width"] == 595
    assert result["page_height"] == 842
    assert result["evidence_text"] == "Invoice No: 1ITR2526001878"


def test_locator_finds_customer_order_number_using_value_fallback(tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    _write_pdf(pdf_path)

    result = locate_pdf_field(
        str(pdf_path),
        field_name="customer_order_no",
        value="PMCH&RI/024/2025-2026",
        evidence_text="digital_rules; text_length=100",
        source="rules",
        confidence=0.9,
    )

    assert result is not None
    assert result["page"] == 1
    assert result["evidence_text"] == "PMCH&RI/024/2025-2026"


def test_locator_returns_none_for_missing_value(tmp_path: Path):
    pdf_path = tmp_path / "invoice.pdf"
    _write_pdf(pdf_path)

    result = locate_pdf_field(str(pdf_path), field_name="so_no", value="NOT-FOUND")

    assert result is None
