"""Celery background task for OCR extraction."""
import os
import time
import asyncio
import logging
from datetime import datetime

from sqlalchemy import func, distinct

from celery_app import celery_app
from app.database import get_sync_db
from app.models import (
    Document, DocumentMetadata, ReferenceIndex,
    DocumentStatus, MetadataStatus, PurchaseOrder, POStatus,
)
from app.services.extraction.pdf_converter import PDFConverter
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.response_parser import ResponseParser
from app.services.extraction.prompts import (
    build_prompt, get_primary_field, get_date_field,
    get_searchable_fields, EXTRACTION_PROMPTS,
)
from app.services.extraction.field_validator import validate_extracted_fields
from app.services.extraction.invoice_validator import validate_invoice_math, ValidationResult
from app.services.extraction.pipeline import build_pipeline_from_config
from app.services.extraction.scan_preprocessor import preprocess_scan
from app.services.extraction.hybrid_router import HybridRouter, ExtractionRoute
from app.services.extraction.digital_extractor import DigitalExtractor
from app.services.extraction.glm_ocr_prompts import EXTRACTION_SCHEMAS
from app.services.extraction.so_validator import validate_so_number
from app.config import settings

logger = logging.getLogger(__name__)


def _estimate_num_predict(doc_type: str, num_ctx: int, floor: int) -> int:
    """Return num_predict capped at the configured floor value.

    The old formula used (num_ctx - 2048) as a ceiling which caused two problems:
    - With large num_ctx (8192) it set num_predict=6144, making generation very slow
      and triggering Cloudflare 524 timeouts on RunPod.
    - With small num_ctx (4096) it left only 2048 tokens for input, truncating the
      document and producing near-zero extractions.

    The configured floor (OCR_EXTRACTOR_NUM_PREDICT, default 2048) is sufficient for
    the full JSON output of any supported schema (~500-1500 tokens in practice).
    num_ctx stays large (8192) to give the model plenty of input space.
    """
    schema = EXTRACTION_SCHEMAS.get(doc_type, {})
    array_fields = sum(
        1 for v in schema.values()
        if isinstance(v, str) and 'json array' in v.lower()
    )
    scalar_fields = len(schema) - array_fields
    logger.debug(
        f"[NumPredict] {doc_type}: scalar={scalar_fields} array={array_fields} → {floor}"
    )
    return floor


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def extract_document(self, document_id: str):
    """Run OCR extraction on an uploaded document."""

    with get_sync_db() as db:
        # 1. Fetch document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return {"error": "not_found"}

        # 2. Build pipeline and verify providers are reachable before starting
        # Catch config errors (bad provider name, missing API key, etc.) so the
        # document moves to PENDING_MODEL instead of being silently stuck in UPLOADED.
        pipeline = None
        try:
            pipeline = build_pipeline_from_config(settings)
            _preflight_error = asyncio.run(pipeline.health_check())
        except Exception as _build_err:
            _preflight_error = f"Pipeline config error: {_build_err}"

        if _preflight_error:
            logger.warning(
                f"[ModelCheck] Holding doc {document_id} — {_preflight_error}"
            )
            doc.status = DocumentStatus.PENDING_MODEL
            meta = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()
            if meta:
                meta.last_error = _preflight_error
                meta.extraction_attempts += 1
            else:
                meta = DocumentMetadata(
                    document_id=doc.id,
                    document_type=doc.document_type,
                    extraction_attempts=1,
                    last_error=_preflight_error,
                    status=MetadataStatus.PENDING,
                )
                db.add(meta)
            db.commit()
            return {"status": "pending_model", "reason": _preflight_error}

        assert pipeline is not None  # _preflight_error branch always returns above

        # 3. Update status to EXTRACTING
        doc.status = DocumentStatus.EXTRACTING
        db.commit()

        extracted_data = {}  # ensure always defined for error handler
        try:
            # 3. Get full file path
            storage_path = os.path.join(settings.nas_base_path, doc.file_path)

            # 4. Route document: digital fast path or OCR?
            router = HybridRouter()
            route = router.route(storage_path)
            logger.info(f"Document {document_id}: route={route.value}")

            # 5. Build prompt
            doc_type = doc.document_type.value

            # Resolve customer name for per-customer delivery schema lookup
            customer_hint = ""
            if doc_type == "CUSTOMER_PO":
                _po = db.query(PurchaseOrder).filter(
                    PurchaseOrder.id == doc.po_id
                ).first()
                if _po and _po.customer:
                    customer_hint = _po.customer.name or ""
                    logger.debug(
                        f"[CustomerHint] CUSTOMER_PO doc {document_id}: "
                        f"customer={customer_hint!r}"
                    )

            # 6. Digital fast path — skip image conversion for digital-native PDFs
            raw_texts = []
            total_time_ms = 0
            markdown_pages = []  # (markdown, elapsed_ms, page_label) for scanned path

            if route == ExtractionRoute.DIGITAL:
                digital_result = asyncio.run(pipeline.try_digital(storage_path))
                if digital_result.markdown and len(digital_result.markdown.strip()) > 50:
                    raw_texts = [digital_result.markdown]
                    logger.info(
                        f"Digital extraction: {len(digital_result.markdown)} chars, no GPU used"
                    )
                else:
                    logger.warning(
                        "Digital route returned no/sparse content — falling back to OCR"
                    )
                    route = ExtractionRoute.SCANNED

            # 7. Convert PDF → images (only if digital fast path didn't yield text)
            if not raw_texts:
                converter = PDFConverter(
                    dpi=settings.ocr_pdf_dpi,
                    max_pages=settings.ocr_max_pages,
                )
                images_list = converter.convert_to_images(storage_path)
                logger.info(f"Converted {len(images_list)} pages for doc {document_id}")

                # ── Phase 1: OCR all pages ────────────────────────────────
                for i, img in enumerate(images_list):
                    page_label = f"doc{document_id}_p{i + 1}"
                    logger.info(
                        f"OCR page {i + 1}/{len(images_list)} for doc {document_id}"
                    )
                    if route == ExtractionRoute.SCANNED:
                        img = preprocess_scan(img)
                    try:
                        ocr_result = asyncio.run(
                            pipeline.run_ocr(img, doc_type, page_label)
                        )
                        raw_texts.append(ocr_result.markdown)
                        markdown_pages.append(
                            (ocr_result.markdown, ocr_result.elapsed_ms, page_label)
                        )
                    except Exception as page_err:
                        logger.warning(f"OCR page {i + 1} failed: {page_err}")
                        _err_msg = str(page_err)
                        if "unreachable" in _err_msg or "offline" in _err_msg:
                            raise
                        raw_texts.append("")
                        markdown_pages.append(("", 0, page_label))

                # Release OCR model VRAM, wait for readiness before Layer 2
                asyncio.run(pipeline.release_vram())
                if not settings.ocr_extractor_base_url:
                    time.sleep(5)
                    asyncio.run(pipeline.wait_until_ready())

            # 8. Extract structured fields from markdown
            if pipeline.layer2 is not None:
                if markdown_pages:
                    # Scanned/image path: extract each page separately, then merge
                    page_fields = []
                    for markdown, ocr_ms, page_label in markdown_pages:
                        if not markdown or len(markdown.strip()) < 20:
                            logger.warning(
                                f"[Pipeline] Empty/short text for {page_label}, skipping"
                            )
                            page_fields.append({})
                            continue
                        try:
                            validated = asyncio.run(
                                pipeline.run_extraction(markdown, doc_type, customer_hint)
                            )
                            page_fields.append(validated)
                            total_time_ms += ocr_ms
                            filled = len([
                                v for k, v in validated.items()
                                if v is not None and not str(k).startswith("_")
                            ])
                            logger.info(
                                f"[Pipeline] {doc_type} {page_label} | "
                                f"OCR: {ocr_ms}ms | Fields: {filled}"
                            )
                        except Exception as page_err:
                            logger.warning(
                                f"Extraction {page_label} failed: {page_err}"
                            )
                            _err_msg = str(page_err)
                            if "unreachable" in _err_msg or "offline" in _err_msg:
                                raise
                            page_fields.append({})
                else:
                    # Digital path: extract from full text in one call
                    try:
                        validated = asyncio.run(
                            pipeline.run_extraction(raw_texts[0], doc_type, customer_hint)
                        )
                        page_fields = [validated]
                    except Exception as dig_err:
                        logger.warning(
                            "Digital extraction failed: %s", dig_err, exc_info=True
                        )
                        # Fallback: try to parse the raw text directly
                        _parser = ResponseParser()
                        _fallback = _parser.parse_and_merge(raw_texts, doc_type)
                        page_fields = [validate_extracted_fields(_fallback, doc_type)]

                # Merge pages (first non-null wins, same as ResponseParser)
                extracted_data = {}
                for pf in page_fields:
                    for key, value in pf.items():
                        if key.startswith("_"):
                            extracted_data[key] = value
                        elif key not in extracted_data or extracted_data[key] is None:
                            extracted_data[key] = value

                real_fields = {
                    k: v for k, v in extracted_data.items() if not k.startswith("_")
                }
                if not real_fields:
                    raise RuntimeError(
                        "Extraction service returned no data — "
                        "all pages failed or were empty"
                    )
            else:
                # Single-layer path (legacy OCRClient): ResponseParser handles merging
                _parser = ResponseParser()
                extracted_data = _parser.parse_and_merge(raw_texts, doc_type)
                extracted_data = validate_extracted_fields(extracted_data, doc_type)
                if not extracted_data:
                    raise RuntimeError(
                        "Extraction produced no data — all pages returned empty output"
                    )

            schema_fields = list(EXTRACTION_SCHEMAS.get(doc_type, {}).keys())
            model_version = pipeline.model_version

            # 9. Confidence
            parser = ResponseParser()
            confidence = parser.calculate_confidence(extracted_data, schema_fields)

            # 9. Extract key fields
            primary_field = get_primary_field(doc_type)
            date_field = get_date_field(doc_type)
            primary_ref = extracted_data.get(primary_field)
            po_ref = extracted_data.get("po_reference")
            doc_date = parser.parse_date(extracted_data.get(date_field))
            # For CUSTOMER_PO, grand_total is the primary amount field
            total_amt = extracted_data.get("total_amount") or extracted_data.get("grand_total")

            # Clean comma-formatted amounts before float conversion
            def clean_amount(val):
                if val is None:
                    return None
                if isinstance(val, (int, float)):
                    return float(val)
                s = str(val).replace(",", "").strip()
                try:
                    return float(s)
                except (ValueError, TypeError):
                    return None

            # Also sanitize amount fields in extracted_data itself
            for amt_field in ("total_amount", "subtotal", "tax_amount", "est_amount",
                              "grand_total", "unit_rate"):
                if amt_field in extracted_data and extracted_data[amt_field] is not None:
                    cleaned = clean_amount(extracted_data[amt_field])
                    if cleaned is not None:
                        extracted_data[amt_field] = cleaned

            # Phase 6: Invoice math and business rule validation
            validation_result = validate_invoice_math(extracted_data, doc_type)
            if validation_result.errors:
                logger.warning(
                    f"Validation errors for {document_id}: {validation_result.errors}"
                )
                extracted_data["_validation_errors"] = validation_result.errors
            if validation_result.warnings:
                extracted_data["_validation_warnings"] = validation_result.warnings

            # Route to PENDING_REVIEW if validation failed or has warnings
            if validation_result.route == "PENDING_REVIEW":
                doc.status = DocumentStatus.PENDING_REVIEW

            # SO number cross-document validation
            po = db.query(PurchaseOrder).filter(
                PurchaseOrder.id == doc.po_id
            ).first()
            so_errors = validate_so_number(
                extracted_data, doc_type, po.so_number if po else None
            )
            if so_errors:
                existing_errors = extracted_data.get("_validation_errors", [])
                extracted_data["_validation_errors"] = existing_errors + so_errors
                doc.status = DocumentStatus.PENDING_REVIEW
                logger.warning(
                    f"[SO Validation] {doc_type} {document_id}: {so_errors}"
                )

            # 10. Create/update metadata
            existing_meta = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()

            if existing_meta:
                meta = existing_meta
                meta.extraction_attempts += 1
            else:
                meta = DocumentMetadata(
                    document_id=doc.id,
                    document_type=doc.document_type,
                    extraction_attempts=1,
                )
                db.add(meta)

            meta.extracted_data = extracted_data
            meta.raw_ocr_text = "\n---PAGE_BREAK---\n".join(raw_texts)
            meta.primary_ref_no = str(primary_ref) if primary_ref else None
            meta.po_ref_no = str(po_ref) if po_ref else None
            meta.doc_date = doc_date
            meta.total_amount = clean_amount(total_amt)
            meta.confidence_score = confidence
            meta.status = MetadataStatus.EXTRACTED
            meta.last_error = None
            meta.extracted_at = datetime.utcnow()
            meta.model_version = model_version
            meta.processing_time_ms = total_time_ms
            meta.extraction_route = route.value  # 'digital' or 'scanned'
            meta.field_confidences = extracted_data.pop("_field_confidences", None)

            # 11. Populate ReferenceIndex
            db.query(ReferenceIndex).filter(
                ReferenceIndex.document_id == doc.id
            ).delete()

            searchable = get_searchable_fields(doc_type)
            for ref_type, field_name in searchable:
                value = extracted_data.get(field_name)
                if value and str(value).strip():
                    ref = ReferenceIndex(
                        document_id=doc.id,
                        po_id=doc.po_id,
                        ref_type=ref_type,
                        ref_value=str(value).strip(),
                        document_type=doc.document_type,
                    )
                    db.add(ref)

            # 12. Update document status
            doc.status = DocumentStatus.PENDING_REVIEW
            db.commit()

            # 13. Update PO chain completeness
            _update_chain_sync(db, doc.po_id)

            logger.info(
                f"Extraction complete: doc={document_id}, "
                f"confidence={confidence}%, time={total_time_ms}ms"
            )
            return {"status": "success", "confidence": confidence}

        except Exception as e:
            logger.error("Extraction failed for %s: %s", document_id, e, exc_info=True)
            doc.status = DocumentStatus.EXTRACTION_FAILED

            # Update metadata with error — preserve any partial results
            meta = db.query(DocumentMetadata).filter(
                DocumentMetadata.document_id == doc.id
            ).first()
            if meta:
                meta.last_error = str(e)
                meta.extraction_attempts += 1
                meta.status = MetadataStatus.FAILED
                # Save partial extracted_data + confidence if we got that far
                try:
                    if extracted_data:
                        meta.extracted_data = extracted_data
                        schema_fields = list(EXTRACTION_SCHEMAS.get(doc_type, {}).keys())
                        meta.confidence_score = parser.calculate_confidence(
                            extracted_data, schema_fields
                        )
                        meta.model_version = pipeline.model_version
                except Exception:
                    pass  # Don't let partial-save crash the error handler
            else:
                meta = DocumentMetadata(
                    document_id=doc.id,
                    document_type=doc.document_type,
                    extraction_attempts=1,
                    last_error=str(e),
                    status=MetadataStatus.FAILED,
                )
                db.add(meta)

            db.commit()

            # Don't retry if every page returned empty content — the PDF is
            # likely image-only or encrypted and a retry will produce the same result.
            _err_str = str(e)
            if "all pages failed or were empty" in _err_str:
                logger.error("Permanent OCR failure (no retry) for %s: %s", document_id, _err_str)
                return {"status": "failed", "error": _err_str}

            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                logger.error("Max retries exceeded for %s", document_id, exc_info=True)
                return {"status": "failed", "error": _err_str}


def _update_chain_sync(db, po_id):
    """Sync version of chain completeness update for Celery."""
    count = db.query(func.count(distinct(Document.document_type))).filter(
        Document.po_id == po_id,
        Document.status.notin_([
            DocumentStatus.EXTRACTION_FAILED,
            DocumentStatus.PENDING_MODEL,
            DocumentStatus.REJECTED,
        ]),
    ).scalar() or 0

    completeness = round((count / 6) * 100, 1)

    po = db.get(PurchaseOrder, po_id)
    if po:
        po.chain_completeness = completeness
        if completeness == 0:
            po.status = POStatus.INITIATED
        elif completeness < 50:
            po.status = POStatus.IN_PROGRESS
        elif completeness < 100:
            po.status = POStatus.NEAR_COMPLETE
        else:
            po.status = POStatus.COMPLETE
        db.commit()
