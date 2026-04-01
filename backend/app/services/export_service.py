"""export_service.py — Build an Excel workbook from PO profile data."""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.po_service import get_po_profile

# ── Styling constants ──────────────────────────────────────────────────────────
_HEADER_FILL     = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
_HEADER_FONT     = Font(bold=True, color="00336B")
_SUBHEADER_FILL  = PatternFill(start_color="EAF2FB", end_color="EAF2FB", fill_type="solid")
_SUBHEADER_FONT  = Font(bold=True, color="1A4A70")
_SECTION_FILL    = PatternFill(start_color="1A3A5C", end_color="1A3A5C", fill_type="solid")
_SECTION_FONT    = Font(bold=True, color="FFFFFF", size=11)
_TITLE_FONT      = Font(bold=True, color="1A3A5C", size=13)

# ── Field label map ────────────────────────────────────────────────────────────
_FIELD_LABELS: dict[str, str] = {
    "po_number":            "PO Number",
    "bsif_name":            "Customer Name",
    "po_date":              "PO Date",
    "quotation_no":         "Quotation No",
    "quotation_date":       "Quotation Date",
    "grand_total":          "Grand Total",
    "delivery_details":     "Delivery Details",
    "terms_and_conditions": "Terms & Conditions",
    "invoice_number":       "Invoice Number",
    "dc_number":            "DC Number",
    "invoice_date":         "Invoice Date",
    "dc_date":              "DC Date",
    "total_amount":         "Total Amount",
    "vendor_name":          "Vendor Name",
    "company_name":         "Company Name",
    "customer_name":        "Customer Name",
}


def _label(key: str) -> str:
    return _FIELD_LABELS.get(key) or key.replace("_", " ").title()


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (list, dict)):
        return str(value)
    return str(value)


def _apply_header(ws, row: int, columns: list[str]) -> None:
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=row, column=col_idx, value=col_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.freeze_panes = ws.cell(row=row + 1, column=1)


def _primary_doc(slot):
    """Return the first (most-recent) POProfileDocument from a slot, or None."""
    return slot.documents[0] if slot.documents else None


def _autofit(ws) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                cell_len = len(str(cell.value)) if cell.value else 0
                if cell_len > max_len:
                    max_len = cell_len
            except Exception:
                pass
        adjusted = min(max_len + 4, 60)
        ws.column_dimensions[col_letter].width = max(adjusted, 12)


# ── Multi-sheet builders ───────────────────────────────────────────────────────

def _build_summary(wb: Workbook, profile) -> None:
    ws = wb.active
    ws.title = "PO Summary"

    rows = [
        ("PO Number",      profile.po_number),
        ("Customer Name",  profile.customer_name),
        ("Customer Sky ID",profile.customer_sky_id),
        ("SO Number",      profile.so_number or "—"),
        ("PO Date",        str(profile.po_date) if profile.po_date else "—"),
        ("Status",         profile.status),
        ("Chain Complete", f"{profile.chain_completeness:.1f}%"),
        ("Total Amount",   f"{profile.total_amount:,.2f}" if profile.total_amount else "—"),
        ("Created At",     profile.created_at.strftime("%Y-%m-%d %H:%M") if profile.created_at else "—"),
    ]

    ws.cell(row=1, column=1, value="Field").font = _HEADER_FONT
    ws.cell(row=1, column=1).fill = _HEADER_FILL
    ws.cell(row=1, column=2, value="Value").font = _HEADER_FONT
    ws.cell(row=1, column=2).fill = _HEADER_FILL
    ws.freeze_panes = "A2"

    for r_idx, (lbl, val) in enumerate(rows, 2):
        ws.cell(row=r_idx, column=1, value=lbl).font = Font(bold=True)
        ws.cell(row=r_idx, column=2, value=val)

    ws.column_dimensions["A"].width = 22
    ws.column_dimensions["B"].width = 40


def _build_document_chain(wb: Workbook, profile) -> None:
    ws = wb.create_sheet("Document Chain")
    columns = ["Doc Type", "Status", "Primary Ref No", "Date", "Total Amount",
               "Confidence", "Extraction Route", "Verified At", "Uploaded At"]
    _apply_header(ws, 1, columns)

    for r_idx, slot in enumerate(profile.slots, 2):
        doc = _primary_doc(slot)
        confidence = ""
        if doc and doc.confidence_score is not None:
            score = doc.confidence_score
            confidence = f"{round(score if score > 1 else score * 100)}%"

        ws.cell(row=r_idx, column=1, value=slot.document_type.replace("_", " ").title())
        ws.cell(row=r_idx, column=2, value=slot.status)
        ws.cell(row=r_idx, column=3, value=(doc.primary_ref_no if doc else None) or "—")
        ws.cell(row=r_idx, column=4, value=str(doc.doc_date) if doc and doc.doc_date else "—")
        ws.cell(row=r_idx, column=5, value=f"{doc.total_amount:,.2f}" if doc and doc.total_amount else "—")
        ws.cell(row=r_idx, column=6, value=confidence or "—")
        ws.cell(row=r_idx, column=7, value=(doc.extraction_route if doc else None) or "—")
        ws.cell(row=r_idx, column=8, value=doc.verified_at.strftime("%Y-%m-%d %H:%M") if doc and doc.verified_at else "—")
        ws.cell(row=r_idx, column=9, value=doc.uploaded_at.strftime("%Y-%m-%d %H:%M") if doc and doc.uploaded_at else "—")

    _autofit(ws)


def _build_extracted_fields(wb: Workbook, profile) -> None:
    ws = wb.create_sheet("Extracted Fields")
    _apply_header(ws, 1, ["Document Type", "Field", "Value"])

    current_row = 2
    for slot in profile.slots:
        doc = _primary_doc(slot)
        if not doc or not doc.extracted_data:
            continue

        label = slot.document_type.replace("_", " ").title()
        cell = ws.cell(row=current_row, column=1, value=label)
        cell.font = _SUBHEADER_FONT
        cell.fill = _SUBHEADER_FILL
        ws.merge_cells(start_row=current_row, start_column=1,
                       end_row=current_row, end_column=3)
        current_row += 1

        for key, value in doc.extracted_data.items():
            if key.startswith("_") or isinstance(value, (list, dict)):
                continue
            ws.cell(row=current_row, column=1, value="")
            ws.cell(row=current_row, column=2, value=_label(key))
            cell = ws.cell(row=current_row, column=3, value=_fmt(value))
            cell.alignment = Alignment(wrap_text=True)
            current_row += 1

        current_row += 1

    ws.column_dimensions["A"].width = 5
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 55


def _build_order_items(wb: Workbook, profile) -> None:
    ws = wb.create_sheet("Order Items")
    columns = ["SR No", "Description", "Qty", "Unit Price", "Total Price"]
    _apply_header(ws, 1, columns)

    items = []
    for slot in profile.slots:
        doc = _primary_doc(slot)
        if slot.document_type == "CUSTOMER_PO" and doc and doc.extracted_data:
            items = doc.extracted_data.get("order_items") or []
            break

    if not items:
        ws.cell(row=2, column=1, value="No order items found")
        _autofit(ws)
        return

    for r_idx, item in enumerate(items, 2):
        if not isinstance(item, dict):
            continue
        ws.cell(row=r_idx, column=1, value=item.get("sr_no", ""))
        ws.cell(row=r_idx, column=2, value=item.get("description", ""))
        ws.cell(row=r_idx, column=3, value=item.get("qty", ""))
        ws.cell(row=r_idx, column=4, value=item.get("unit_price", ""))
        ws.cell(row=r_idx, column=5, value=item.get("total_price", ""))

    _autofit(ws)
    ws.column_dimensions["B"].width = 60


def _build_delivery_locations(wb: Workbook, profile) -> None:
    ws = wb.create_sheet("Delivery Locations")
    columns = ["Region", "Branch", "GSTIN No", "Asset Description", "Qty",
               "Employee Name", "Contact Person", "Contact No", "Delivery Address"]
    _apply_header(ws, 1, columns)

    locations = []
    for slot in profile.slots:
        doc = _primary_doc(slot)
        if slot.document_type == "CUSTOMER_PO" and doc and doc.extracted_data:
            locations = doc.extracted_data.get("delivery_locations") or []
            break

    if not locations:
        ws.cell(row=2, column=1, value="No delivery locations found")
        _autofit(ws)
        return

    for r_idx, loc in enumerate(locations, 2):
        if not isinstance(loc, dict):
            continue
        ws.cell(row=r_idx, column=1, value=loc.get("region", ""))
        ws.cell(row=r_idx, column=2, value=loc.get("branch", ""))
        ws.cell(row=r_idx, column=3, value=loc.get("gstin_no", ""))
        ws.cell(row=r_idx, column=4, value=loc.get("asset_description", ""))
        ws.cell(row=r_idx, column=5, value=loc.get("qty", ""))
        ws.cell(row=r_idx, column=6, value=loc.get("employee_name", ""))
        ws.cell(row=r_idx, column=7, value=loc.get("contact_person", ""))
        ws.cell(row=r_idx, column=8, value=loc.get("contact_no", ""))
        cell = ws.cell(row=r_idx, column=9, value=loc.get("delivery_address", ""))
        cell.alignment = Alignment(wrap_text=True)

    _autofit(ws)


def _build_timeline(wb: Workbook, profile) -> None:
    ws = wb.create_sheet("Timeline")
    columns = ["Timestamp", "Doc Type", "Event Type", "Detail"]
    _apply_header(ws, 1, columns)

    for r_idx, event in enumerate(profile.timeline, 2):
        ws.cell(row=r_idx, column=1,
                value=event.timestamp.strftime("%Y-%m-%d %H:%M") if event.timestamp else "—")
        ws.cell(row=r_idx, column=2,
                value=event.doc_type.replace("_", " ").title() if event.doc_type else "—")
        ws.cell(row=r_idx, column=3, value=event.event_type.title())
        ws.cell(row=r_idx, column=4, value=event.detail or "")

    if len(profile.timeline) == 0:
        ws.cell(row=2, column=1, value="No events recorded yet")

    _autofit(ws)


def _build_discrepancies(wb: Workbook, profile) -> None:
    if not profile.discrepancies:
        return

    ws = wb.create_sheet("Discrepancies")
    columns = ["Severity", "Type", "Doc Type", "Message"]
    _apply_header(ws, 1, columns)

    for r_idx, d in enumerate(profile.discrepancies, 2):
        ws.cell(row=r_idx, column=1, value=d.severity.upper())
        ws.cell(row=r_idx, column=2, value=d.type)
        ws.cell(row=r_idx, column=3, value=d.doc_type.replace("_", " ").title())
        ws.cell(row=r_idx, column=4, value=d.message)

    _autofit(ws)


# ── Consolidated single-sheet builder ─────────────────────────────────────────

_CONSOLIDATED_COLS = 9  # A–I


def _section_header(ws, row: int, title: str) -> None:
    """Write a full-width dark navy section header row."""
    cell = ws.cell(row=row, column=1, value=title)
    cell.font = _SECTION_FONT
    cell.fill = _SECTION_FILL
    cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=row, start_column=1,
                   end_row=row, end_column=_CONSOLIDATED_COLS)
    ws.row_dimensions[row].height = 20


def _consolidated_header_row(ws, row: int, columns: list[str]) -> None:
    """Write a styled column-header row (blue, no freeze)."""
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=row, column=col_idx, value=col_name)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.alignment = Alignment(horizontal="left", vertical="center")


def _build_consolidated(wb: Workbook, profile) -> None:
    ws = wb.active
    ws.title = "PO Export"

    # Fixed column widths A–I
    widths = [28, 40, 20, 20, 18, 22, 22, 18, 45]
    for idx, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = w

    r = 1

    # ── Title ──────────────────────────────────────────────────────────────────
    title_cell = ws.cell(row=r, column=1,
                         value=f"Purchase Order  —  {profile.po_number}")
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.merge_cells(start_row=r, start_column=1,
                   end_row=r, end_column=_CONSOLIDATED_COLS)
    ws.row_dimensions[r].height = 28
    r += 2  # blank row after title

    # ── Section 1: PO Summary ─────────────────────────────────────────────────
    _section_header(ws, r, "PO SUMMARY")
    r += 1

    summary_rows = [
        ("PO Number",       profile.po_number),
        ("Customer Name",   profile.customer_name or "—"),
        ("Customer Sky ID", profile.customer_sky_id or "—"),
        ("SO Number",       profile.so_number or "—"),
        ("PO Date",         str(profile.po_date) if profile.po_date else "—"),
        ("Status",          profile.status),
        ("Chain Complete",  f"{profile.chain_completeness:.1f}%"),
        ("Total Amount",    f"{profile.total_amount:,.2f}" if profile.total_amount else "—"),
        ("Created At",      profile.created_at.strftime("%Y-%m-%d %H:%M") if profile.created_at else "—"),
    ]
    for lbl, val in summary_rows:
        ws.cell(row=r, column=1, value=lbl).font = Font(bold=True, color="1A3A5C")
        ws.cell(row=r, column=2, value=val)
        r += 1
    r += 1  # blank separator

    # ── Section 2: Document Chain ─────────────────────────────────────────────
    _section_header(ws, r, "DOCUMENT CHAIN")
    r += 1
    chain_cols = ["Doc Type", "Status", "Primary Ref No", "Date",
                  "Total Amount", "Confidence", "Route", "Verified At", "Uploaded At"]
    _consolidated_header_row(ws, r, chain_cols)
    r += 1

    for slot in profile.slots:
        doc = _primary_doc(slot)
        confidence = ""
        if doc and doc.confidence_score is not None:
            score = doc.confidence_score
            confidence = f"{round(score if score > 1 else score * 100)}%"

        ws.cell(row=r, column=1, value=slot.document_type.replace("_", " ").title())
        ws.cell(row=r, column=2, value=slot.status)
        ws.cell(row=r, column=3, value=(doc.primary_ref_no if doc else None) or "—")
        ws.cell(row=r, column=4, value=str(doc.doc_date) if doc and doc.doc_date else "—")
        ws.cell(row=r, column=5, value=f"{doc.total_amount:,.2f}" if doc and doc.total_amount else "—")
        ws.cell(row=r, column=6, value=confidence or "—")
        ws.cell(row=r, column=7, value=(doc.extraction_route if doc else None) or "—")
        ws.cell(row=r, column=8, value=doc.verified_at.strftime("%Y-%m-%d %H:%M") if doc and doc.verified_at else "—")
        ws.cell(row=r, column=9, value=doc.uploaded_at.strftime("%Y-%m-%d %H:%M") if doc and doc.uploaded_at else "—")
        r += 1
    r += 1

    # ── Section 3: Extracted Fields ───────────────────────────────────────────
    _section_header(ws, r, "EXTRACTED FIELDS")
    r += 1

    for slot in profile.slots:
        doc = _primary_doc(slot)
        if not doc or not doc.extracted_data:
            continue

        # Doc type sub-header
        sub_cell = ws.cell(row=r, column=1,
                           value=slot.document_type.replace("_", " ").title())
        sub_cell.font = _SUBHEADER_FONT
        sub_cell.fill = _SUBHEADER_FILL
        ws.merge_cells(start_row=r, start_column=1,
                       end_row=r, end_column=_CONSOLIDATED_COLS)
        r += 1

        for key, value in doc.extracted_data.items():
            if key.startswith("_") or isinstance(value, (list, dict)):
                continue
            ws.cell(row=r, column=1, value=_label(key)).font = Font(bold=True)
            cell = ws.cell(row=r, column=2, value=_fmt(value))
            cell.alignment = Alignment(wrap_text=True)
            ws.merge_cells(start_row=r, start_column=2,
                           end_row=r, end_column=_CONSOLIDATED_COLS)
            r += 1
        r += 1
    r += 1

    # ── Section 4: Order Items ────────────────────────────────────────────────
    _section_header(ws, r, "ORDER ITEMS")
    r += 1

    items = []
    for slot in profile.slots:
        doc = _primary_doc(slot)
        if slot.document_type == "CUSTOMER_PO" and doc and doc.extracted_data:
            items = doc.extracted_data.get("order_items") or []
            break

    if items:
        _consolidated_header_row(ws, r, ["SR No", "Description", "Qty", "Unit Price", "Total Price"])
        r += 1
        for item in items:
            if not isinstance(item, dict):
                continue
            ws.cell(row=r, column=1, value=item.get("sr_no", ""))
            ws.cell(row=r, column=2, value=item.get("description", ""))
            ws.cell(row=r, column=3, value=item.get("qty", ""))
            ws.cell(row=r, column=4, value=item.get("unit_price", ""))
            ws.cell(row=r, column=5, value=item.get("total_price", ""))
            r += 1
    else:
        ws.cell(row=r, column=1, value="No order items found")
        r += 1
    r += 1

    # ── Section 5: Delivery Locations ─────────────────────────────────────────
    _section_header(ws, r, "DELIVERY LOCATIONS")
    r += 1

    locations = []
    for slot in profile.slots:
        doc = _primary_doc(slot)
        if slot.document_type == "CUSTOMER_PO" and doc and doc.extracted_data:
            locations = doc.extracted_data.get("delivery_locations") or []
            break

    if locations:
        loc_cols = ["Region", "Branch", "GSTIN No", "Asset", "Qty",
                    "Employee Name", "Contact Person", "Contact No", "Delivery Address"]
        _consolidated_header_row(ws, r, loc_cols)
        r += 1
        for loc in locations:
            if not isinstance(loc, dict):
                continue
            ws.cell(row=r, column=1, value=loc.get("region", ""))
            ws.cell(row=r, column=2, value=loc.get("branch", ""))
            ws.cell(row=r, column=3, value=loc.get("gstin_no", ""))
            ws.cell(row=r, column=4, value=loc.get("asset_description", ""))
            ws.cell(row=r, column=5, value=loc.get("qty", ""))
            ws.cell(row=r, column=6, value=loc.get("employee_name", ""))
            ws.cell(row=r, column=7, value=loc.get("contact_person", ""))
            ws.cell(row=r, column=8, value=loc.get("contact_no", ""))
            cell = ws.cell(row=r, column=9, value=loc.get("delivery_address", ""))
            cell.alignment = Alignment(wrap_text=True)
            r += 1
    else:
        ws.cell(row=r, column=1, value="No delivery locations found")
        r += 1
    r += 1

    # ── Section 6: Timeline ───────────────────────────────────────────────────
    _section_header(ws, r, "TIMELINE")
    r += 1

    if profile.timeline:
        _consolidated_header_row(ws, r, ["Timestamp", "Doc Type", "Event", "Detail"])
        r += 1
        for event in profile.timeline:
            ws.cell(row=r, column=1,
                    value=event.timestamp.strftime("%Y-%m-%d %H:%M") if event.timestamp else "—")
            ws.cell(row=r, column=2,
                    value=event.doc_type.replace("_", " ").title() if event.doc_type else "—")
            ws.cell(row=r, column=3, value=event.event_type.title())
            ws.cell(row=r, column=4, value=event.detail or "")
            r += 1
    else:
        ws.cell(row=r, column=1, value="No events recorded yet")
        r += 1
    r += 1

    # ── Section 7: Field Comparisons ─────────────────────────────────────────
    field_comparisons = getattr(profile, "field_comparisons", [])
    if field_comparisons:
        _section_header(ws, r, "CROSS-DOCUMENT FIELD COMPARISONS")
        r += 1
        _consolidated_header_row(ws, r, ["Field", "Source Doc", "Source Value",
                                          "Compared Doc", "Compared Value", "Match", "Note"])
        r += 1
        for fc in field_comparisons:
            match_label = "✓ MATCH" if fc.match is True else ("✗ MISMATCH" if fc.match is False else "— pending")
            ws.cell(row=r, column=1, value=fc.field_label)
            ws.cell(row=r, column=2, value=fc.source_doc.replace("_", " ").title())
            ws.cell(row=r, column=3, value=fc.source_value or "—")
            ws.cell(row=r, column=4, value=fc.compared_doc.replace("_", " ").title())
            ws.cell(row=r, column=5, value=fc.compared_value or "—")
            match_cell = ws.cell(row=r, column=6, value=match_label)
            if fc.match is False:
                match_cell.font = Font(bold=True, color="C00000")
            elif fc.match is True:
                match_cell.font = Font(color="375623")
            ws.cell(row=r, column=7, value=fc.note or "")
            r += 1


def _build_field_comparisons(wb: Workbook, profile) -> None:
    """Sheet: cross-document field comparison results."""
    if not getattr(profile, "field_comparisons", None):
        return

    ws = wb.create_sheet("Field Comparisons")
    columns = ["Field", "Source Doc", "Source Value", "Compared Doc", "Compared Value", "Match", "Note"]
    _apply_header(ws, 1, columns)

    for r_idx, fc in enumerate(profile.field_comparisons, 2):
        match_label = "✓ MATCH" if fc.match is True else ("✗ MISMATCH" if fc.match is False else "— pending")
        ws.cell(row=r_idx, column=1, value=fc.field_label)
        ws.cell(row=r_idx, column=2, value=fc.source_doc.replace("_", " ").title())
        ws.cell(row=r_idx, column=3, value=fc.source_value or "—")
        ws.cell(row=r_idx, column=4, value=fc.compared_doc.replace("_", " ").title())
        ws.cell(row=r_idx, column=5, value=fc.compared_value or "—")
        match_cell = ws.cell(row=r_idx, column=6, value=match_label)
        if fc.match is False:
            match_cell.font = Font(bold=True, color="C00000")
        elif fc.match is True:
            match_cell.font = Font(color="375623")
        ws.cell(row=r_idx, column=7, value=fc.note or "")

    _autofit(ws)


def _build_vendor_groups(wb: Workbook, profile) -> None:
    """Sheet: per-vendor completeness breakdown."""
    vendor_groups = getattr(profile, "vendor_groups", None)
    if not vendor_groups:
        return

    ws = wb.create_sheet("Vendor Groups")
    columns = ["Vendor", "Vendor PO Ref", "Completeness %", "Doc Type", "Status", "Primary Ref No"]
    _apply_header(ws, 1, columns)

    r_idx = 2
    for group in vendor_groups:
        for slot in group.slots:
            doc = _primary_doc(slot)
            ws.cell(row=r_idx, column=1, value=group.vendor_name or "—")
            ws.cell(row=r_idx, column=2, value=group.vendor_po_ref)
            ws.cell(row=r_idx, column=3, value=f"{group.completeness_pct:.1f}%")
            ws.cell(row=r_idx, column=4, value=slot.document_type.replace("_", " ").title())
            ws.cell(row=r_idx, column=5, value=slot.status)
            ws.cell(row=r_idx, column=6, value=(doc.primary_ref_no if doc else None) or "—")
            r_idx += 1

    _autofit(ws)


# ── Public entry point ─────────────────────────────────────────────────────────

async def export_po_to_excel(db: AsyncSession, po_id: UUID,
                              mode: str = "separate") -> bytes:
    """Fetch PO profile and build Excel workbook. mode='single'|'separate'."""
    profile = await get_po_profile(db, po_id)

    wb = Workbook()

    if mode == "single":
        _build_consolidated(wb, profile)
    else:
        _build_summary(wb, profile)
        _build_document_chain(wb, profile)
        _build_extracted_fields(wb, profile)
        _build_order_items(wb, profile)
        _build_delivery_locations(wb, profile)
        _build_timeline(wb, profile)
        _build_discrepancies(wb, profile)
        _build_field_comparisons(wb, profile)
        _build_vendor_groups(wb, profile)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
