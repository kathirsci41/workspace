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
    DocumentStatus, MetadataStatus, PurchaseOrder,
)
from app.services.extraction.pdf_converter import PDFConverter
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.response_parser import ResponseParser
from app.services.extraction.prompts import (
    build_prompt, get_primary_field, get_date_field,
    get_searchable_fields, EXTRACTION_PROMPTS,
)
from app.services.extraction.field_validator import validate_extracted_fields
from app.services.extraction.two_layer_client import TwoLayerClient
from app.services.extraction.glm_ocr_prompts import EXTRACTION_SCHEMAS
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=10)
def extract_document(self, document_id: str):
    """Run OCR extraction on an uploaded document."""

    with get_sync_db() as db:
        # 1. Fetch document
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found")
            return {"error": "not_found"}

        # 2. Update status to EXTRACTING
        doc.status = DocumentStatus.EXTRACTING
        db.commit()

        extracted_data = {}  # ensure always defined for error handler
        try:
            # 3. Get full file path
            storage_path = os.path.join(settings.nas_base_path, doc.file_path)

            # 4. Convert PDF → images
            converter = PDFConverter(
                dpi=settings.ocr_pdf_dpi,
                max_pages=settings.ocr_max_pages,
            )
            images = converter.convert_to_images(storage_path)
            logger.info(f"Converted {len(images)} pages for doc {document_id}")

            # 5. Build prompt
            doc_type = doc.document_type.value

            # 6. OCR each page — choose single-layer or two-layer pipeline
            use_two_layer = settings.ocr_two_layer_enabled
            raw_texts = []
            total_time_ms = 0

            if use_two_layer:
                # ── Two-layer pipeline ────────────────────────────────────
                logger.info(
                    f"Using TWO-LAYER pipeline for doc {document_id} "
                    f"({settings.ocr_custom_model} + {settings.ocr_extractor_model})"
                )
                two_layer = TwoLayerClient(
                    base_url=settings.ocr_base_url,
                    ocr_model=settings.ocr_custom_model,
                    extractor_model=settings.ocr_extractor_model,
                    timeout=settings.ocr_timeout,
                    max_retries=settings.ocr_max_retries,
                    extractor_num_ctx=settings.ocr_extractor_num_ctx,
                    save_debug_markdown=settings.ocr_save_debug_markdown,
                    extractor_base_url=settings.ocr_extractor_base_url,
                    extractor_api_key=settings.ocr_extractor_api_key,
                )

                markdown_pages = []  # (markdown, ocr_ms, page_label)

                # ── Phase 1: OCR all pages (GLM-OCR stays loaded) ────────
                for i, img in enumerate(images):
                    page_label = f"doc{document_id}_p{i + 1}"
                    logger.info(
                        f"Two-layer OCR {i + 1}/{len(images)} for doc {document_id}"
                    )
                    try:
                        markdown, ocr_ms = asyncio.run(
                            two_layer._run_ocr_layer(img, doc_type)
                        )
                        if two_layer.save_debug_markdown and page_label:
                            two_layer._save_markdown(markdown, page_label, doc_type)
                        raw_texts.append(markdown)
                        markdown_pages.append((markdown, ocr_ms, page_label))
                    except Exception as page_err:
                        logger.warning(
                            f"Two-layer OCR page {i + 1} failed: {page_err}"
                        )
                        raw_texts.append("")
                        markdown_pages.append(("", 0, page_label))

                # Release OCR model once (all pages done), then load extractor
                asyncio.run(two_layer.release_model(two_layer.ocr_model))
                # Only wait for local Ollama if Layer 2 is also local
                if not settings.ocr_extractor_base_url:
                    time.sleep(5)
                    asyncio.run(two_layer.wait_until_ready())

                # ── Phase 2: Extract from all pages (Qwen2.5 loads once) ─
                page_fields = []
                for markdown, ocr_ms, page_label in markdown_pages:
                    if not markdown or len(markdown.strip()) < 20:
                        logger.warning(
                            f"[TwoLayer] Empty/short text for {page_label}, skipping"
                        )
                        page_fields.append({})
                        continue
                    try:
                        fields, extract_ms = asyncio.run(
                            two_layer._run_extraction_layer(markdown, doc_type)
                        )
                        validated = validate_extracted_fields(fields, doc_type)
                        page_fields.append(validated)
                        total_time_ms += ocr_ms + extract_ms
                        filled = len([
                            v for k, v in validated.items()
                            if v is not None and not str(k).startswith("_")
                        ])
                        logger.info(
                            f"[TwoLayer] {doc_type} {page_label} | "
                            f"OCR: {ocr_ms}ms | Extract: {extract_ms}ms | "
                            f"Fields: {filled}"
                        )
                    except Exception as page_err:
                        logger.warning(
                            f"Two-layer extraction {page_label} failed: {page_err}"
                        )
                        page_fields.append({})

                # Merge page fields (first non-null wins, same as ResponseParser)
                extracted_data = {}
                for pf in page_fields:
                    for key, value in pf.items():
                        if key.startswith("_"):
                            # Preserve validation metadata from last page
                            extracted_data[key] = value
                        elif key not in extracted_data or extracted_data[key] is None:
                            extracted_data[key] = value

                # Guard: raise if no real fields extracted from any page
                real_fields = {
                    k: v for k, v in extracted_data.items()
                    if not k.startswith("_")
                }
                if not real_fields:
                    raise RuntimeError(
                        "Two-layer OCR produced no extractable fields — "
                        "all pages failed or returned empty"
                    )

                # Use two-layer schema for confidence calculation
                schema_fields = list(
                    EXTRACTION_SCHEMAS.get(doc_type, {}).keys()
                )
                model_version = (
                    f"{settings.ocr_custom_model}+{settings.ocr_extractor_model}"
                )
            else:
                # ── Single-layer pipeline (existing behavior) ─────────────
                prompt = build_prompt(doc_type)

                ocr = OCRClient(
                    base_url=settings.ocr_base_url,
                    model=settings.ocr_model_name,
                    timeout=settings.ocr_timeout,
                    max_retries=settings.ocr_max_retries,
                )

                for i, img in enumerate(images):
                    logger.info(
                        f"OCR page {i + 1}/{len(images)} for doc {document_id}"
                    )

                    if i > 0:
                        asyncio.run(ocr.release_model())
                        time.sleep(10)
                        asyncio.run(ocr.wait_until_ready())

                    try:
                        result = asyncio.run(ocr.extract_from_image(img, prompt))
                        raw_texts.append(result["text"])
                        total_time_ms += result["processing_time_ms"]
                    except Exception as page_err:
                        logger.warning(
                            f"Single-layer page {i + 1} failed, skipping: {page_err}"
                        )
                        raw_texts.append("")

                # 7. Parse + merge
                parser = ResponseParser()
                extracted_data = parser.parse_and_merge(raw_texts, doc_type)

                # Apply field validation to single-layer results too
                extracted_data = validate_extracted_fields(
                    extracted_data, doc_type
                )

                if not extracted_data:
                    raise RuntimeError(
                        "OCR produced no extractable data — "
                        "all pages returned non-JSON or empty output"
                    )

                schema_fields = list(
                    EXTRACTION_PROMPTS[doc_type]["schema"].keys()
                )
                model_version = settings.ocr_model_name

            # 8. Confidence
            parser = ResponseParser()
            confidence = parser.calculate_confidence(extracted_data, schema_fields)

            # 9. Extract key fields
            primary_field = get_primary_field(doc_type)
            date_field = get_date_field(doc_type)
            primary_ref = extracted_data.get(primary_field)
            po_ref = extracted_data.get("po_reference")
            doc_date = parser.parse_date(extracted_data.get(date_field))
            total_amt = extracted_data.get("total_amount")

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

            # If items_description is a list, join to string
            items_desc = extracted_data.get("items_description")
            if isinstance(items_desc, list):
                extracted_data["items_description"] = "; ".join(
                    str(item) for item in items_desc if item
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
            logger.error(f"Extraction failed for {document_id}: {e}")
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
                        if use_two_layer:
                            schema_fields = list(EXTRACTION_SCHEMAS.get(doc_type, {}).keys())
                        else:
                            schema_fields = list(EXTRACTION_PROMPTS[doc_type]["schema"].keys())
                        meta.confidence_score = parser.calculate_confidence(
                            extracted_data, schema_fields
                        )
                        meta.model_version = settings.ocr_model_name
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

            try:
                raise self.retry(exc=e)
            except self.MaxRetriesExceededError:
                logger.error(f"Max retries exceeded for {document_id}")
                return {"status": "failed", "error": str(e)}


def _update_chain_sync(db, po_id):
    """Sync version of chain completeness update for Celery."""
    count = db.query(func.count(distinct(Document.document_type))).filter(
        Document.po_id == po_id,
        Document.status != DocumentStatus.EXTRACTION_FAILED,
    ).scalar() or 0

    completeness = round((count / 6) * 100, 1)

    po = db.query(PurchaseOrder).get(po_id)
    if po:
        po.chain_completeness = completeness
        if completeness == 0:
            po.status = "INITIATED"
        elif completeness < 50:
            po.status = "IN_PROGRESS"
        elif completeness < 100:
            po.status = "NEAR_COMPLETE"
        else:
            po.status = "COMPLETE"
        db.commit()
