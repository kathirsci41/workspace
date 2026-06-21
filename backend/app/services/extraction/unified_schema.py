"""
Unified invoice schema S — internal representation.
NOT exposed to frontend or verification engine in Sprint 4.

Adapter: to_flat_dict(schema) → flat dict T (existing field names).
Sprint 4 only uses the adapter output. Build 2 can expose S directly.

Schema inspired by LlamaExtract reference outputs (Panimalar, Trade, AMC fixtures).
Field names match our existing normalized field names (not LlamaExtract's variable ones).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PartyInfo:
    name: str = ""
    gstin: str = ""
    address: str = ""
    state_code: str = ""
    pan: str = ""


@dataclass
class OrderDetails:
    po_number: str = ""
    so_number: str = ""
    invoice_number: str = ""
    invoice_date: str = ""
    po_date: str = ""
    irn: str = ""
    place_of_supply: str = ""


@dataclass
class LineItem:
    description: str = ""
    product_code: str | None = None
    hsn_sac: str | None = None
    qty: str | None = None
    uom: str | None = None
    unit_rate: str | None = None
    taxable_value: str | None = None
    tax_amount: str | None = None
    amount: str | None = None
    serial_numbers: list[str] = field(default_factory=list)


@dataclass
class TaxSummary:
    gst_rate: str = ""
    igst_amount: str = ""
    cgst_amount: str = ""
    sgst_amount: str = ""
    tax_type: str = ""  # "IGST" | "CGST+SGST"


@dataclass
class FinancialSummary:
    taxable_amount: str = ""
    total_tax: str = ""
    total_amount: str = ""
    amount_in_words: str = ""


@dataclass
class InvoiceSchema:
    """Unified schema S — applies to all 5 document types."""
    doc_type: str = ""
    buyer: PartyInfo = field(default_factory=PartyInfo)
    vendor: PartyInfo = field(default_factory=PartyInfo)
    order: OrderDetails = field(default_factory=OrderDetails)
    line_items: list[LineItem] = field(default_factory=list)
    tax: TaxSummary = field(default_factory=TaxSummary)
    financial: FinancialSummary = field(default_factory=FinancialSummary)
    ship_to: str = ""
    bank_details: str = ""
    _source: str = "regex"  # "regex" | "bbox" | "bbox+regex"


def to_flat_dict(schema: InvoiceSchema) -> dict[str, Any]:
    """
    Adapter: unified schema S → flat dict T (existing field names).
    Preserves all existing field names used by verification engine and frontend.
    line_items stored as nested key (Option J — no migration).
    """
    flat: dict[str, Any] = {}

    # Buyer / Customer
    if schema.buyer.name:      flat["customer_name"]    = schema.buyer.name
    if schema.buyer.gstin:     flat["customer_gstin"]   = schema.buyer.gstin
    if schema.buyer.address:   flat["customer_address"] = schema.buyer.address

    # Vendor / Seller
    if schema.vendor.name:     flat["vendor_name"]      = schema.vendor.name
    if schema.vendor.gstin:    flat["vendor_gstin"]     = schema.vendor.gstin
    if schema.vendor.address:  flat["vendor_address"]   = schema.vendor.address

    # Order details
    if schema.order.po_number:       flat["po_reference"]      = schema.order.po_number
    if schema.order.so_number:       flat["so_no"]             = schema.order.so_number
    if schema.order.invoice_number:  flat["vendor_invoice_no"] = schema.order.invoice_number
    if schema.order.invoice_date:    flat["invoice_date"]      = schema.order.invoice_date
    if schema.order.po_date:         flat["po_date"]           = schema.order.po_date
    if schema.order.irn:             flat["irn_number"]        = schema.order.irn
    if schema.order.place_of_supply: flat["place_of_supply"]   = schema.order.place_of_supply

    # Tax
    if schema.tax.gst_rate:     flat["gst_rate"]      = schema.tax.gst_rate
    if schema.tax.igst_amount:  flat["igst_amount"]   = schema.tax.igst_amount
    if schema.tax.cgst_amount:  flat["cgst_amount"]   = schema.tax.cgst_amount
    if schema.tax.sgst_amount:  flat["sgst_amount"]   = schema.tax.sgst_amount

    # Financial
    if schema.financial.taxable_amount: flat["taxable_amount"]   = schema.financial.taxable_amount
    if schema.financial.total_tax:      flat["total_tax"]        = schema.financial.total_tax
    if schema.financial.total_amount:   flat["total_amount"]     = schema.financial.total_amount

    # Other
    if schema.ship_to:       flat["ship_to"]       = schema.ship_to
    if schema.bank_details:  flat["bank_details"]  = schema.bank_details

    # line_items — nested key in flat dict (Option J, no migration)
    if schema.line_items:
        flat["line_items"] = [
            {
                "description":   li.description,
                "product_code":  li.product_code,
                "hsn_sac":       li.hsn_sac,
                "qty":           li.qty,
                "uom":           li.uom,
                "unit_rate":     li.unit_rate,
                "taxable_value": li.taxable_value,
                "tax_amount":    li.tax_amount,
                "amount":        li.amount,
                "serial_numbers": li.serial_numbers,
            }
            for li in schema.line_items
        ]

    # Diagnostics
    flat["_extraction_source"] = schema._source

    return flat
