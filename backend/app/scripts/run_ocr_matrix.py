"""CLI script for DPI x mode OCR matrix evaluation — Phase 1n.

Usage:
    python -m app.scripts.run_ocr_matrix path/to/doc.pdf
    python -m app.scripts.run_ocr_matrix path/to/doc.pdf --dpi 72 150 200 300
    python -m app.scripts.run_ocr_matrix path/to/doc.pdf --format json --output output/ocr-evaluations/result.json
    python -m app.scripts.run_ocr_matrix path/to/doc.pdf \\
        --expected vendor_invoice_no=2526PSI25087738 vendor_invoice_date=12-02-2026 po_reference=1PTR2526000467

Options:
    --dpi         Space-separated DPI values to sweep (default: 72 150 200 300)
    --providers   Space-separated providers (default: glm_full_page glm_header)
    --timeout     OCR timeout in seconds per cell (default: 60)
    --expected    key=value pairs for scoring (default: empty — no scoring)
    --format      markdown | json (default: markdown)
    --output      Write report to this file path in addition to stdout

This script never writes to the production database.
It never changes extraction results or OCR behavior.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.extraction.ocr_matrix import (
    render_matrix_report,
    run_matrix,
    summarize_matrix,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Run DPI x provider matrix OCR evaluation on a PDF.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("pdf_path", help="PDF file to evaluate")
    p.add_argument(
        "--dpi",
        nargs="+",
        type=int,
        default=[72, 150, 200, 300],
        metavar="DPI",
        help="DPI values to sweep (default: 72 150 200 300)",
    )
    p.add_argument(
        "--providers",
        nargs="+",
        default=["glm_full_page", "glm_header"],
        metavar="PROVIDER",
        help="Providers to evaluate (default: glm_full_page glm_header)",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="OCR timeout seconds per cell (default: 60)",
    )
    p.add_argument(
        "--expected",
        nargs="*",
        default=[],
        metavar="KEY=VALUE",
        help="Expected field values for scoring, e.g. vendor_invoice_no=INV001",
    )
    p.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    p.add_argument(
        "--output",
        default=None,
        help="Optional file path to write the report (in addition to stdout)",
    )
    return p


def _parse_expected(pairs: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            print(f"WARNING: ignoring malformed --expected value: {pair!r}", file=sys.stderr)
            continue
        key, _, val = pair.partition("=")
        result[key.strip()] = val.strip()
    return result


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    pdf = Path(args.pdf_path)
    if not pdf.exists():
        print(f"ERROR: file not found: {args.pdf_path}", file=sys.stderr)
        return 1

    expected = _parse_expected(args.expected)

    print(f"Matrix: {len(args.providers)} providers x {len(args.dpi)} DPI = {len(args.providers) * len(args.dpi)} cells")
    print(f"Providers: {args.providers}")
    print(f"DPI values: {args.dpi}")
    print(f"Timeout: {args.timeout}s per cell")
    if expected:
        print(f"Scoring against: {expected}")
    else:
        print("No expected values provided — scores will be 0 for all cells")
    print()

    entries = run_matrix(
        str(pdf),
        providers=args.providers,
        dpi_values=args.dpi,
        expected=expected,
        timeout_seconds=args.timeout,
    )

    report = render_matrix_report(entries, format=args.format)
    print(report)

    summary = summarize_matrix(entries)
    if args.format == "markdown":
        print()
        print(f"Matrix complete. Best: {summary['best_entry'].provider if summary['best_entry'] else 'N/A'} "
              f"@ DPI {summary['best_entry'].dpi if summary['best_entry'] else 'N/A'} "
              f"score={summary['max_score']} | Any perfect: {summary['any_perfect']}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"\nReport written to: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
