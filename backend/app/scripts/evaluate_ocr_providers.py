"""Evaluation-only CLI script for comparing OCR providers.

Usage:
    python -m app.scripts.evaluate_ocr_providers path/to/doc.pdf [path/to/doc2.pdf ...]
    python -m app.scripts.evaluate_ocr_providers path/to/doc.pdf --format json
    python -m app.scripts.evaluate_ocr_providers path/to/doc.pdf --document-type VENDOR_INVOICE

Options:
    --format   markdown | json   (default: markdown)
    --dpi      render DPI (default: 150)
    --timeout  OCR timeout seconds (default: 60)
    --document-type  document type for parser (default: VENDOR_INVOICE)
    --no-parser  skip structured text parser step

This script never writes to the production database.
It never changes extraction results or OCR behavior.
Reports are printed to stdout.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from pathlib import Path

from app.services.extraction.glm_ocr_client import check_ocr_provider_health
from app.services.extraction.ocr_evaluation import (
    OcrProviderResult,
    check_paddleocr_availability,
    evaluate_pdf,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Evaluate OCR providers against one or more PDFs.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("pdf_paths", nargs="+", help="PDF files to evaluate")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument("--dpi", type=int, default=150)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--document-type", default="VENDOR_INVOICE")
    p.add_argument("--no-parser", action="store_true", help="Skip structured text parser")
    return p


def _result_to_dict(r: OcrProviderResult) -> dict:
    return dataclasses.asdict(r)


def _render_markdown(pdf_path: str, results: list[OcrProviderResult]) -> str:
    lines = [
        f"## OCR Evaluation: {Path(pdf_path).name}",
        "",
    ]
    for r in results:
        lines.append(f"### Provider: `{r.provider_name}` (`{r.source_type}`)")
        lines.append(f"- **status**: {r.provider_status}")
        lines.append(f"- **success**: {r.success}")
        lines.append(f"- **provider_version**: {r.provider_version or '—'}")
        lines.append(f"- **duration_ms**: {r.duration_ms}")
        lines.append(f"- **raw_text_length**: {r.raw_text_length}")
        if r.error:
            lines.append(f"- **error**: {r.error}")
        if r.normalized_text_preview:
            preview = r.normalized_text_preview.replace("\n", " | ")[:200]
            lines.append(f"- **text_preview**: `{preview}`")
        if r.extracted_fields:
            lines.append("- **extracted_fields**:")
            for k, v in r.extracted_fields.items():
                lines.append(f"  - `{k}`: {v!r}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Entry point: evaluate OCR providers against provided PDF paths."""
    args = _build_parser().parse_args(argv)

    health = check_ocr_provider_health(timeout_seconds=3)
    paddle_status = check_paddleocr_availability()

    print(f"OCR provider health: {health}")
    print(f"PaddleOCR availability: {paddle_status}")
    print()

    if not health.get("reachable") and health.get("enabled"):
        print(
            "WARNING: OCR provider is enabled but unreachable. "
            "Full-page and header OCR evaluations will error.",
            file=sys.stderr,
        )

    all_results: dict[str, list[dict]] = {}
    for pdf_path in args.pdf_paths:
        p = Path(pdf_path)
        if not p.exists():
            print(f"ERROR: file not found: {pdf_path}", file=sys.stderr)
            continue

        results = evaluate_pdf(
            pdf_path,
            dpi=args.dpi,
            timeout_seconds=args.timeout,
            run_parser=not args.no_parser,
            document_type=args.document_type,
        )

        if args.format == "json":
            all_results[pdf_path] = [_result_to_dict(r) for r in results]
        else:
            print(_render_markdown(pdf_path, results))

    if args.format == "json":
        print(json.dumps(all_results, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
