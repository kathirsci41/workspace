from __future__ import annotations

import re
from typing import Any

import fitz


def locate_pdf_field(
    file_path: str,
    *,
    field_name: str,
    value: Any,
    evidence_text: str | None = None,
    source: str = "digital_text",
    confidence: float | None = None,
) -> dict[str, Any] | None:
    """Locate visible digital PDF text without making extraction dependent on highlighting."""
    if value in (None, ""):
        return None
    try:
        with fitz.open(file_path) as document:
            for candidate in _candidates(value, evidence_text):
                for page_index, page in enumerate(document):
                    matches = page.search_for(candidate)
                    if matches:
                        return _location(page, page_index, matches[0], candidate, source, confidence)
            target = _normalize(str(value))
            for page_index, page in enumerate(document):
                words = page.get_text("words")
                for word in words:
                    text = str(word[4])
                    if _normalize(text) == target:
                        return _location(page, page_index, fitz.Rect(word[:4]), text, source, confidence)
                for line in _lines(page):
                    if target and target in _normalize(line["text"]):
                        return _location(page, page_index, line["bbox"], str(value), source, confidence)
    except Exception:
        return None
    return None


def build_field_locations(
    file_path: str | None,
    fields: dict[str, Any],
    field_metadata: dict[str, dict[str, Any]],
    *,
    digital_text_used: bool,
    extraction_route: str,
) -> dict[str, dict[str, Any]]:
    locations: dict[str, dict[str, Any]] = {}
    for field, value in fields.items():
        if str(field).startswith("raw_") or value in (None, ""):
            continue
        details = field_metadata.get(field, {})
        evidence_text = _usable_evidence(details.get("evidence_text"), value)
        confidence = details.get("confidence")
        detail_source = str(details.get("source") or "rules")
        if detail_source == "model_layer2":
            source = "model_layer2"
        elif digital_text_used:
            source = "digital_text"
        elif extraction_route in {"ocr_glm", "scanned"}:
            source = "ocr"
        else:
            source = detail_source
        located = None
        if digital_text_used and file_path:
            located = locate_pdf_field(
                file_path,
                field_name=field,
                value=value,
                evidence_text=evidence_text,
                source=source,
                confidence=confidence,
            )
        locations[field] = located or {
            "page": None,
            "bbox": None,
            "evidence_text": evidence_text,
            "source": source,
            "confidence": confidence,
        }
    return locations


def _candidates(value: Any, evidence_text: str | None) -> list[str]:
    results: list[str] = []
    evidence = str(evidence_text or "").strip()
    if evidence and not evidence.endswith("text_length=0") and "text_length=" not in evidence:
        results.append(evidence)
    value_text = str(value).strip()
    if value_text and value_text not in results:
        results.append(value_text)
    return results


def _usable_evidence(evidence_text: Any, value: Any) -> str:
    evidence = str(evidence_text or "").strip()
    if not evidence or "text_length=" in evidence:
        return str(value)
    return evidence


def _location(page, page_index: int, rect: fitz.Rect, evidence_text: str, source: str, confidence: float | None) -> dict[str, Any]:
    return {
        "page": page_index + 1,
        "bbox": [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
        "page_width": round(page.rect.width, 2),
        "page_height": round(page.rect.height, 2),
        "evidence_text": evidence_text,
        "source": source,
        "confidence": confidence,
    }


def _lines(page) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    blocks = page.get_text("dict").get("blocks", [])
    for block in blocks:
        for line in block.get("lines", []):
            text = "".join(span.get("text", "") for span in line.get("spans", []))
            if text.strip():
                lines.append({"text": text, "bbox": fitz.Rect(line["bbox"])})
    return lines


def _normalize(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())
