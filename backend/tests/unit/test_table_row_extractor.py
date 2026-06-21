from app.services.extraction.table_row_extractor import (
    extract_line_items_from_bboxes,
    extract_line_items_from_table_html,
    _group_rows,
)


def _bbox(text, x, y, w=80, h=10):
    return {"page": 1, "text": text, "x": x, "y": y, "w": w, "h": h}


def test_row_grouping():
    bboxes = [
        _bbox("A", 10, 100), _bbox("B", 100, 101),  # same row (ΔY=1)
        _bbox("C", 10, 120), _bbox("D", 100, 120),  # same row
    ]
    rows = _group_rows(bboxes)
    assert len(rows) == 2


def test_extract_line_items_basic():
    bboxes = [
        # header row
        _bbox("Description", 10, 50), _bbox("Qty", 200, 50),
        _bbox("Rate", 280, 50), _bbox("Amount", 360, 50),
        # data row 1
        _bbox("HP Laptop 15s", 10, 70), _bbox("2", 200, 70),
        _bbox("45000", 280, 70), _bbox("90000", 360, 70),
        # totals row — should be skipped
        _bbox("Total", 10, 90), _bbox("90000", 360, 90),
    ]
    items = extract_line_items_from_bboxes(bboxes)
    assert len(items) == 1
    assert items[0]["description"] == "HP Laptop 15s"
    assert items[0]["qty"] == "2"
    assert items[0]["amount"] == "90000"


def test_table_html_parsing():
    html = """<table>
    <tr><th>Description</th><th>Qty</th><th>Amount</th></tr>
    <tr><td>Fortigate FG-120G</td><td>1</td><td>503200</td></tr>
    </table>"""
    items = extract_line_items_from_table_html(html)
    assert len(items) == 1
    assert items[0]["description"] == "Fortigate FG-120G"
    assert items[0]["qty"] == "1"
    assert items[0]["amount"] == "503200"
