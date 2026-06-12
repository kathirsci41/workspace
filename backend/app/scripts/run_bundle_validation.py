"""Lightweight real-document bundle validation runner — Phase 1r.

Re-extracts documents from a validation-run directory and compares against
a baseline JSON if one exists.

This script never modifies the validation-run's own DB. It creates a fresh
throwaway SQLite DB for each run (same pattern as test_panimalar_regression_phase1e.py).

Usage:
    python -m app.scripts.run_bundle_validation \\
        ../validation-runs/real-doc-003-amc-baseline \\
        --baseline-json ../validation-runs/real-doc-003-amc-baseline/artifacts/19-amc-expected-baseline.json \\
        --bundle-name AMC

Output columns per document:
    bundle_name | doc_type | filename | extraction_status | extraction_route |
    ocr_status | field | extracted | expected | classification | source
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class FieldResult:
    field: str
    extracted: Any
    expected: Any
    classification: str  # exact_match | missing | value_mismatch | no_baseline
    source: str | None


@dataclass
class DocumentResult:
    bundle_name: str
    doc_type: str
    filename: str
    extraction_status: str
    extraction_route: str | None
    ocr_status: str | None
    has_baseline: bool
    fields: dict[str, FieldResult] = dc_field(default_factory=dict)


@dataclass
class BundleResult:
    bundle_name: str
    run_dir: str
    documents: list[DocumentResult] = dc_field(default_factory=list)


# ---------------------------------------------------------------------------
# Pure comparison functions
# ---------------------------------------------------------------------------

def classify_field(extracted: Any, expected: Any) -> str:
    if expected is None:
        return "no_baseline"
    if extracted in (None, ""):
        return "missing"
    if extracted == expected:
        return "exact_match"
    return "value_mismatch"


def compare_extracted_to_baseline(
    extracted_data: dict[str, Any],
    field_metadata: dict[str, Any],
    baseline: dict[str, Any] | None,
) -> dict[str, FieldResult]:
    results: dict[str, FieldResult] = {}
    if baseline is None:
        for field_name, value in extracted_data.items():
            source = (field_metadata.get(field_name) or {}).get("source")
            results[field_name] = FieldResult(
                field=field_name,
                extracted=value,
                expected=None,
                classification="no_baseline",
                source=source,
            )
        return results

    all_fields = set(baseline.keys()) | set(extracted_data.keys())
    for field_name in all_fields:
        extracted_val = extracted_data.get(field_name)
        expected_val = baseline.get(field_name)
        source = (field_metadata.get(field_name) or {}).get("source")
        results[field_name] = FieldResult(
            field=field_name,
            extracted=extracted_val,
            expected=expected_val,
            classification=classify_field(extracted_val, expected_val),
            source=source,
        )
    return results


# ---------------------------------------------------------------------------
# Baseline JSON loader
# ---------------------------------------------------------------------------

def load_baseline_from_json(path: str) -> dict[str, dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        doc_type: {
            field: (values[0] if isinstance(values, list) and len(values) >= 1 else values)
            for field, values in fields.items()
        }
        for doc_type, fields in raw.items()
    }


# ---------------------------------------------------------------------------
# Runner — reads validation-run DB, re-extracts, compares
# ---------------------------------------------------------------------------

def _read_docs_from_valrun_db(db_path: Path) -> list[dict[str, str]]:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, document_type, filename, storage_path FROM bundle_documents"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def run_bundle_validation(
    val_run_dir: Path,
    *,
    bundle_name: str | None = None,
    baseline: dict[str, dict[str, Any]] | None = None,
    disable_ocr: bool = True,
    disable_model_layer2: bool = True,
) -> BundleResult:
    val_run_dir = Path(val_run_dir)
    name = bundle_name or val_run_dir.name

    db_path = val_run_dir / "order_assurance.db"
    if not db_path.exists():
        raise FileNotFoundError(f"No order_assurance.db found in {val_run_dir}")

    docs = _read_docs_from_valrun_db(db_path)

    from app.config import Settings, replace_settings
    from app.migrations.runner import run as run_migrations
    from app.models.document import DocumentRecord
    from app.models.order_bundle import OrderBundleRecord
    from app.services.extraction_service import extract_document
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_db = Path(tmpdir) / "validation.db"
        db_url = f"sqlite:///{tmp_db}"
        replace_settings(Settings(
            database_url=db_url,
            digital_text_enabled=True,
            structured_rules_enabled=True,
            ocr_enabled=not disable_ocr,
            model_layer2_enabled=not disable_model_layer2,
            evidence_capture_enabled=False,
        ))
        run_migrations("up")
        engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        db = Session()

        now = datetime.now(timezone.utc)
        bundle_record = OrderBundleRecord(
            id=str(uuid4()),
            bundle_number=f"VALRUN-{name}",
            customer_name=name,
            created_at=now,
            updated_at=now,
        )
        db.add(bundle_record)
        db.flush()

        doc_results: list[DocumentResult] = []
        for doc_info in docs:
            doc_type = doc_info["document_type"]
            filename = doc_info["filename"]
            storage_path = doc_info["storage_path"]

            if not Path(storage_path).exists():
                doc_results.append(DocumentResult(
                    bundle_name=name,
                    doc_type=doc_type,
                    filename=filename,
                    extraction_status="SKIPPED_NOT_FOUND",
                    extraction_route=None,
                    ocr_status=None,
                    has_baseline=baseline is not None and doc_type in (baseline or {}),
                    fields={},
                ))
                continue

            doc_record = DocumentRecord(
                id=str(uuid4()),
                order_bundle_id=bundle_record.id,
                document_type=doc_type,
                filename=filename,
                storage_path=storage_path,
                status="UPLOADED",
                created_at=now,
                updated_at=now,
            )
            db.add(doc_record)
            db.flush()

            result = extract_document(db, doc_record, force=True)
            meta = result["metadata"]
            extracted_data = dict(meta.extracted_data or {})
            diagnostics = dict(meta.diagnostics or {})
            field_metadata = diagnostics.get("field_metadata") or {}
            doc_baseline = (baseline or {}).get(doc_type)

            field_results = compare_extracted_to_baseline(
                extracted_data, field_metadata, doc_baseline
            )
            doc_results.append(DocumentResult(
                bundle_name=name,
                doc_type=doc_type,
                filename=filename,
                extraction_status=meta.status,
                extraction_route=diagnostics.get("extraction_route"),
                ocr_status=diagnostics.get("ocr_status"),
                has_baseline=doc_baseline is not None,
                fields=field_results,
            ))

            db.expire(doc_record)

        db.close()
        engine.dispose()

    return BundleResult(bundle_name=name, run_dir=str(val_run_dir), documents=doc_results)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_bundle_report(result: BundleResult) -> str:
    lines = [
        f"# Bundle Validation Report: {result.bundle_name}",
        f"Run dir: {result.run_dir}",
        f"Documents: {len(result.documents)}",
        "",
    ]
    for doc in result.documents:
        lines.append(f"## {doc.doc_type} — {doc.filename}")
        lines.append(f"Status: {doc.extraction_status} | Route: {doc.extraction_route} | OCR: {doc.ocr_status}")
        lines.append(f"Baseline: {'yes' if doc.has_baseline else 'no (smoke only)'}")
        if not doc.fields:
            lines.append("  (no fields)")
        else:
            lines.append("")
            lines.append("| Field | Extracted | Expected | Classification | Source |")
            lines.append("|-------|-----------|----------|----------------|--------|")
            for field_name, fr in sorted(doc.fields.items()):
                ext = str(fr.extracted) if fr.extracted is not None else "(missing)"
                exp = str(fr.expected) if fr.expected is not None else "(n/a)"
                lines.append(f"| {field_name} | {ext} | {exp} | {fr.classification} | {fr.source or ''} |")
        lines.append("")
    summary = _summary_line(result)
    lines.append(summary)
    return "\n".join(lines)


def _summary_line(result: BundleResult) -> str:
    total = sum(len(d.fields) for d in result.documents)
    exact = sum(
        1 for d in result.documents for fr in d.fields.values()
        if fr.classification == "exact_match"
    )
    missing = sum(
        1 for d in result.documents for fr in d.fields.values()
        if fr.classification == "missing"
    )
    mismatch = sum(
        1 for d in result.documents for fr in d.fields.values()
        if fr.classification == "value_mismatch"
    )
    no_base = sum(
        1 for d in result.documents for fr in d.fields.values()
        if fr.classification == "no_baseline"
    )
    return (
        f"Summary: total_fields={total} exact_match={exact} missing={missing} "
        f"value_mismatch={mismatch} no_baseline={no_base}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Re-extract documents from a validation run and compare to baseline."
    )
    p.add_argument("val_run_dir", help="Path to validation run directory (contains order_assurance.db)")
    p.add_argument("--bundle-name", default=None, help="Display name for the bundle")
    p.add_argument("--baseline-json", default=None, help="Path to expected baseline JSON (keyed by doc_type)")
    p.add_argument("--enable-ocr", action="store_true", help="Enable OCR during re-extraction (default: off)")
    p.add_argument("--enable-model", action="store_true", help="Enable model layer 2 (default: off)")
    args = p.parse_args(argv)

    val_run_dir = Path(args.val_run_dir)
    if not val_run_dir.exists():
        print(f"ERROR: directory not found: {val_run_dir}", file=sys.stderr)
        return 1

    baseline: dict[str, dict] | None = None
    if args.baseline_json:
        baseline = load_baseline_from_json(args.baseline_json)
        if not baseline:
            print(f"WARNING: baseline JSON empty or not found: {args.baseline_json}", file=sys.stderr)

    bundle_name = args.bundle_name or val_run_dir.name
    print(f"Bundle: {bundle_name}")
    print(f"Run dir: {val_run_dir}")
    print(f"Baseline: {'loaded' if baseline else 'none (smoke run)'}")
    print(f"OCR: {'enabled' if args.enable_ocr else 'disabled (digital PDF mode)'}")
    print()

    result = run_bundle_validation(
        val_run_dir,
        bundle_name=bundle_name,
        baseline=baseline,
        disable_ocr=not args.enable_ocr,
        disable_model_layer2=not args.enable_model,
    )
    print(render_bundle_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
