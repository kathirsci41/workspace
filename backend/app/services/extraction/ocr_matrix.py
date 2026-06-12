"""OCR DPI x mode matrix evaluation harness — Phase 1n.

Evaluation-only module. Never writes production database records.
Never changes extraction behavior. Builds on Phase 1m ocr_evaluation.py.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass

from app.services.extraction.ocr_evaluation import (
    run_glm_full_page_evaluation,
    run_glm_header_evaluation,
)


@dataclass
class MatrixEntry:
    """One cell in the DPI x provider evaluation matrix."""

    provider: str                         # "glm_full_page" | "glm_header"
    dpi: int
    duration_ms: int
    success: bool
    error: str | None
    raw_text_length: int
    extracted_fields: dict[str, str | None]   # field name -> extracted value
    match_flags: dict[str, bool]              # field name -> exact match against expected
    score: int                                 # count of exact matches (0-3)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_fields(extracted: dict, expected: dict) -> int:
    """Count how many expected fields exactly match the extracted values.

    Comparison strips surrounding whitespace. None values never match.
    """
    count = 0
    for key, exp_val in expected.items():
        got = extracted.get(key)
        if got is not None and str(got).strip() == str(exp_val).strip():
            count += 1
    return count


# ---------------------------------------------------------------------------
# Matrix runner
# ---------------------------------------------------------------------------

def _run_cell(
    pdf_path: str,
    provider: str,
    dpi: int,
    timeout_seconds: int,
    expected: dict,
) -> MatrixEntry:
    """Run one (provider, DPI) cell and return a MatrixEntry.

    All exceptions are caught so a failed cell doesn't abort the matrix.
    """
    try:
        if provider == "glm_full_page":
            result = run_glm_full_page_evaluation(
                pdf_path, dpi=dpi, timeout_seconds=timeout_seconds, run_parser=True
            )
        elif provider == "glm_header":
            result = run_glm_header_evaluation(
                pdf_path, dpi=dpi, timeout_seconds=timeout_seconds, run_parser=True
            )
        else:
            raise ValueError(f"Unknown provider: {provider!r}")

        extracted = {k: result.extracted_fields.get(k) for k in expected}
        flags = {
            k: (v is not None and str(v).strip() == str(expected[k]).strip())
            for k, v in extracted.items()
        }
        sc = sum(1 for v in flags.values() if v)
        return MatrixEntry(
            provider=provider,
            dpi=dpi,
            duration_ms=result.duration_ms,
            success=result.success,
            error=result.error,
            raw_text_length=result.raw_text_length,
            extracted_fields=extracted,
            match_flags=flags,
            score=sc,
        )
    except Exception as exc:
        return MatrixEntry(
            provider=provider,
            dpi=dpi,
            duration_ms=0,
            success=False,
            error=str(exc),
            raw_text_length=0,
            extracted_fields={k: None for k in expected},
            match_flags={k: False for k in expected},
            score=0,
        )


def run_matrix(
    pdf_path: str,
    *,
    providers: list[str],
    dpi_values: list[int],
    expected: dict[str, str],
    timeout_seconds: int = 60,
) -> list[MatrixEntry]:
    """Evaluate all (provider x DPI) combinations on pdf_path.

    Returns one MatrixEntry per cell. Provider exceptions are captured
    as failed entries rather than propagated.
    """
    entries: list[MatrixEntry] = []
    for provider in providers:
        for dpi in dpi_values:
            entry = _run_cell(pdf_path, provider, dpi, timeout_seconds, expected)
            entries.append(entry)
    return entries


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarize_matrix(entries: list[MatrixEntry]) -> dict:
    """Summarize matrix results.

    Returns:
        best_entry: entry with highest score; tiebreak by lowest duration_ms
        any_perfect: True if any entry scored 3 (all target fields matched)
        max_score: highest score observed
        total_entries: count of entries
    """
    if not entries:
        return {
            "best_entry": None,
            "any_perfect": False,
            "max_score": 0,
            "total_entries": 0,
        }

    max_score = max(e.score for e in entries)
    best = min(
        (e for e in entries if e.score == max_score),
        key=lambda e: e.duration_ms,
    )
    return {
        "best_entry": best,
        "any_perfect": any(e.score == 3 for e in entries),
        "max_score": max_score,
        "total_entries": len(entries),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_matrix_report(
    entries: list[MatrixEntry],
    *,
    format: str = "markdown",
) -> str:
    """Render the matrix as a markdown table or JSON string.

    Output is guaranteed ASCII-safe (no Unicode line-break chars) to avoid
    cp1252 encoding errors on Windows consoles.
    """
    if format == "json":
        return _render_json(entries)
    return _render_markdown(entries)


def _render_markdown(entries: list[MatrixEntry]) -> str:
    summary = summarize_matrix(entries)
    lines = [
        "## OCR Matrix Evaluation",
        "",
        f"Entries: {summary['total_entries']} | "
        f"Max score: {summary['max_score']} | "
        f"Any perfect (score=3): {'YES' if summary['any_perfect'] else 'NO'}",
        "",
    ]

    if summary["best_entry"]:
        best = summary["best_entry"]
        lines += [
            f"**Best:** `{best.provider}` @ DPI {best.dpi} "
            f"— score {best.score} — {best.duration_ms} ms",
            "",
        ]

    # Table header
    lines.append(
        "| Provider | DPI | Score | Duration ms | text_len | "
        "inv_no | inv_date | po_ref | Success | Error |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")

    for e in entries:
        inv_no = _flag(e.match_flags.get("vendor_invoice_no"))
        inv_date = _flag(e.match_flags.get("vendor_invoice_date"))
        po_ref = _flag(e.match_flags.get("po_reference"))
        err = (e.error or "")[:60].replace("|", "/") if e.error else ""
        lines.append(
            f"| {e.provider} | {e.dpi} | {e.score} | {e.duration_ms} | {e.raw_text_length} | "
            f"{inv_no} | {inv_date} | {po_ref} | {e.success} | {err} |"
        )

    lines.append("")
    lines.append("### Extracted field values")
    lines.append("")
    lines.append("| Provider | DPI | vendor_invoice_no | vendor_invoice_date | po_reference |")
    lines.append("|---|---|---|---|---|")
    for e in entries:
        inv_no = e.extracted_fields.get("vendor_invoice_no") or ""
        inv_date = e.extracted_fields.get("vendor_invoice_date") or ""
        po_ref = e.extracted_fields.get("po_reference") or ""
        lines.append(f"| {e.provider} | {e.dpi} | {inv_no} | {inv_date} | {po_ref} |")

    return "\n".join(lines)


def _render_json(entries: list[MatrixEntry]) -> str:
    data = [dataclasses.asdict(e) for e in entries]
    return json.dumps(data, indent=2, ensure_ascii=True)


def _flag(match: bool | None) -> str:
    """Return ASCII tick/cross for match flag (cp1252-safe)."""
    if match is True:
        return "OK"
    if match is False:
        return "X"
    return "?"
