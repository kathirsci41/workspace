"""Unit tests for BBoxFieldExtractor — no PDF, pure bbox list."""
from app.services.extraction.bbox_field_extractor import extract_header_fields


def _bbox(text, x, y, w=80, h=10):
    return {"page": 1, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_right_of_label():
    bboxes = [_bbox("Invoice No", 10, 100), _bbox("INV-001", 100, 100)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_invoice_no") == "INV-001"


def test_below_label():
    bboxes = [_bbox("Invoice No", 10, 100), _bbox("INV-001", 12, 115)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_invoice_no") == "INV-001"


def test_gstin_extraction():
    bboxes = [_bbox("GSTIN", 10, 50), _bbox("33AAGCS1406H1ZR", 100, 50)]
    result = extract_header_fields(bboxes)
    assert result.get("vendor_gstin") == "33AAGCS1406H1ZR"


def test_no_value_returns_empty():
    bboxes = [_bbox("Invoice No", 10, 100)]
    result = extract_header_fields(bboxes)
    assert "vendor_invoice_no" not in result
