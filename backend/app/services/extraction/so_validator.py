"""
SO Number Cross-Document Validator.

Validates that COMPANY_DC and COMPANY_INVOICE documents carry the same
Sales Order (SO) number that is registered on the parent PurchaseOrder.

Two blocking cases:
  1. PO has no SO number set yet → operator must set it before these docs
     can be considered valid.
  2. PO has an SO number set but the extracted value does not match →
     document likely belongs to a different PO.
"""

import logging

logger = logging.getLogger(__name__)

_SO_DOC_TYPES = {"COMPANY_DC", "COMPANY_INVOICE"}


def validate_so_number(
    extracted_data: dict,
    doc_type: str,
    po_so_number: str | None,
) -> list[str]:
    """Return a list of validation error strings for SO number issues.

    An empty list means no issues — the document can proceed normally.

    Args:
        extracted_data: The dict of fields extracted from the document.
        doc_type:       The document type string (e.g. "COMPANY_DC").
        po_so_number:   The SO number stored on the parent PurchaseOrder,
                        or None if it has not been set yet.

    Returns:
        List of human-readable error strings (empty = pass).
    """
    if doc_type not in _SO_DOC_TYPES:
        return []

    # Case 1: SO not set on PO — block until operator sets it
    if not po_so_number:
        logger.warning(
            "[SO Validator] %s blocked: SO number not set on PO", doc_type
        )
        return [
            "SO number not set for this PO. "
            "Please set the SO number on the PO first, then re-extract this document."
        ]

    # Resolve which field carries the SO number for this doc type
    extracted_so = (
        extracted_data.get("so_number")
        or extracted_data.get("sales_order_no")
    )

    if not extracted_so:
        # SO field not extracted — field validator will flag missing field;
        # we cannot compare, so skip here.
        return []

    def _normalize(s: str) -> str:
        return s.strip().upper().replace(" ", "").replace("-", "").replace("/", "")

    if _normalize(str(extracted_so)) != _normalize(str(po_so_number)):
        logger.warning(
            "[SO Validator] %s mismatch: expected '%s', found '%s'",
            doc_type,
            po_so_number,
            extracted_so,
        )
        return [
            f"SO number mismatch: expected '{po_so_number}', "
            f"found '{extracted_so}' in this document. "
            "Please verify you have uploaded the correct document."
        ]

    return []
