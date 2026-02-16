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
from app.config import settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
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
            prompt = build_prompt(doc_type)

            # 6. OCR each page
            ocr = OCRClient(
                base_url=settings.ocr_base_url,
                model=settings.ocr_model_name,
                timeout=settings.ocr_timeout,
                max_retries=settings.ocr_max_retries,
            )

            raw_texts = []
            total_time_ms = 0
            for i, img in enumerate(images):
                logger.info(f"OCR page {i + 1}/{len(images)} for doc {document_id}")
                # Allow Ollama to release GPU memory between pages
                if i > 0:
                    time.sleep(5)
                result = asyncio.run(ocr.extract_from_image(img, prompt))
                raw_texts.append(result["text"])
                total_time_ms += result["processing_time_ms"]

            # 7. Parse + merge
            parser = ResponseParser()
            extracted_data = parser.parse_and_merge(raw_texts, doc_type)

            # 8. Confidence
            schema_fields = list(EXTRACTION_PROMPTS[doc_type]["schema"].keys())
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
            meta.model_version = settings.ocr_model_name
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
