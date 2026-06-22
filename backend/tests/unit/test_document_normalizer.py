from app.domain.enums import DocumentType
from app.services.document_normalizer import normalize_document


class DummyDocument:
    def __init__(self, document_id: str, document_type: str):
        self.id = document_id
        self.document_type = document_type


def test_normalizes_company_invoice_to_customer_invoice_fields():
    document = DummyDocument("doc-invoice", DocumentType.COMPANY_INVOICE)
    normalized = normalize_document(
        document,
        {
            "invoice_number": "1ITR2526001878",
            "invoice_date": "13/02/2026",
            "po_reference": "PMCH&RI/024/2025-2026",
            "so_number": "1OTM2526001611",
            "customer_name": "PanimAlar Medical Hospital & Research Institute",
            "total_amount": 874439,
            "taxable_amount": 741050,
            "tax_amount": 133389,
        },
    )

    assert normalized.document_type == "CUSTOMER_INVOICE"
    assert normalized.fields["invoice_no"] == "1ITR2526001878"
    assert normalized.fields["customer_order_no"] == "PMCH&RI/024/2025-2026"
    assert normalized.fields["so_no"] == "1OTM2526001611"
    assert normalized.fields["grand_total"] == 874439


def test_customer_po_aliases_are_available_after_normalization():
    document = DummyDocument("doc-customer-po", DocumentType.CUSTOMER_PO)
    normalized = normalize_document(
        document,
        {
            "po_number": "PMCH&RI/024/2025-2026",
            "customer_name": "PANIMALAR MEDICAL HOSPITAL & RESEARCH INSTITUTE",
            "total_amount": "874439",
        },
    )

    assert normalized.fields["customer_po_no"] == "PMCH&RI/024/2025-2026"
    assert normalized.fields["customer_order_no"] == "PMCH&RI/024/2025-2026"
    assert normalized.fields["primary_ref_no"] == "PMCH&RI/024/2025-2026"
    assert normalized.fields["grand_total"] == 874439


def test_vendor_gstin_survives_vendor_invoice_normalization():
    document = DummyDocument("doc-vendor-invoice", DocumentType.VENDOR_INVOICE)
    normalized = normalize_document(
        document,
        {
            "vendor_invoice_no": "INV-1",
            "po_reference": "PO-1",
            "vendor_gstin": "33AAGCS1406H1ZR",
            "invoice_total": "1000",
        },
    )

    assert normalized.document_type == "VENDOR_INVOICE"
    assert normalized.fields["vendor_gstin"] == "33AAGCS1406H1ZR"
    assert normalized.fields["gstin"] == "33AAGCS1406H1ZR"


def test_line_items_survive_invoice_normalization():
    document = DummyDocument("doc-vendor-invoice", DocumentType.VENDOR_INVOICE)
    line_items = [{"description": "Firewall appliance", "hsn_sac": "8517", "qty": "3"}]
    normalized = normalize_document(document, {"vendor_invoice_no": "INV-1", "line_items": line_items})

    assert normalized.fields["line_items"] == line_items
