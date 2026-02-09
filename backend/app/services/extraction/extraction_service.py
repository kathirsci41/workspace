import asyncio
import logging
import time
from datetime import date, datetime
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.document import Document
from app.models.document_metadata import (
    DocumentMetadata, ExtractionStatus, DocumentType
)
from app.models.audit_log import AuditLog
from app.schemas.document_metadata import (
    ExtractionResponse, MetadataVerifyRequest
)
from app.services.extraction.ocr_client import OCRClient
from app.services.extraction.pdf_converter import pdf_to_images, cleanup_temp_images
from app.services.extraction.response_parser import parse_ocr_response
from app.services.extraction.prompts import get_prompt_config

logger = logging.getLogger(__name__)


class ExtractionService:
    def __init__(self, db: Session):
        self.db = db
        self.ocr_client = OCRClient()
        self._settings = get_settings()

    async def extract(
        self, document_id: int, force: bool = False
    ) -> ExtractionResponse:
        """
        Full extraction pipeline for a document.

        Steps:
        1. Load document record
        2. Check for existing metadata
        3. Convert PDF to images
        4. Call GLM-OCR with doc-type-specific prompt (with retry)
        5. Parse response
        6. Save metadata to DB
        7. Create audit log entry
        """

        # Step 1: Load document
        doc = self._get_document(document_id)
        if not doc:
            raise FileNotFoundError(f"Document not found: {document_id}")

        # Step 2: Check existing metadata
        existing = self._get_existing_metadata(document_id)
        if existing and not force:
            if existing.status == ExtractionStatus.VERIFIED:
                raise ValueError(
                    "Document already has verified metadata. "
                    "Use force_re_extract=true to override."
                )
            if existing.status == ExtractionStatus.EXTRACTED:
                return ExtractionResponse(
                    metadata_id=existing.id,
                    status=existing.status,
                    extracted_data=existing.extracted_data,
                    confidence_score=existing.confidence_score,
                    primary_ref_no=existing.primary_ref_no,
                    doc_date=str(existing.doc_date) if existing.doc_date else None,
                    message="Extraction already exists. Showing existing results."
                )

        # Step 3: Get prompt config for this doc type
        doc_type = DocumentType(doc.document_type)
        prompt_config = get_prompt_config(doc_type)

        # Step 4: Convert PDF to images
        pipeline_start = time.perf_counter()
        image_paths = []
        try:
            pdf_start = time.perf_counter()
            image_paths = pdf_to_images(
                str(doc.storage_path),
                dpi=self._settings.ocr_pdf_dpi
            )
            pdf_elapsed = time.perf_counter() - pdf_start
            logger.info(
                f"PDF→image conversion for doc {document_id}: "
                f"{pdf_elapsed:.2f}s ({len(image_paths)} pages)"
            )
            if not image_paths:
                raise ValueError("PDF conversion produced no images")

            # Step 5: Call GLM-OCR with retry (first page only for most docs)
            ocr_start = time.perf_counter()
            raw_response = await self._call_ocr_with_retry(
                image_path=image_paths[0],
                prompt=prompt_config["prompt"],
                max_retries=self._settings.ocr_max_retries
            )
            ocr_elapsed = time.perf_counter() - ocr_start
            logger.info(
                f"OCR extraction for doc {document_id}: {ocr_elapsed:.2f}s"
            )

            logger.info(
                f"OCR raw response for doc {document_id}: "
                f"{raw_response[:200]}..."
            )

            # Step 6: Parse response
            parse_start = time.perf_counter()
            extracted_data, primary_ref, doc_date, confidence = parse_ocr_response(
                raw_response=raw_response,
                expected_schema=prompt_config["schema"],
                primary_ref_field=prompt_config["primary_ref_field"],
                date_field=prompt_config["date_field"]
            )
            parse_elapsed = time.perf_counter() - parse_start

            # Total pipeline time
            total_elapsed = time.perf_counter() - pipeline_start
            logger.info(
                f"Extraction pipeline for doc {document_id} completed in {total_elapsed:.2f}s "
                f"(pdf: {pdf_elapsed:.2f}s, ocr: {ocr_elapsed:.2f}s, parse: {parse_elapsed:.2f}s)"
            )

            # Step 7: Save to DB
            metadata = self._save_metadata(
                document_id=document_id,
                document_path=doc.storage_path,
                doc_type=doc_type,
                extracted_data=extracted_data,
                primary_ref_no=primary_ref,
                doc_date=doc_date,
                confidence_score=confidence,
                raw_ocr_text=raw_response,
                status=ExtractionStatus.EXTRACTED,
                existing=existing
            )

            # Step 8: Audit log
            self._create_audit_log(
                action="METADATA_EXTRACTED",
                document_id=document_id,
                case_id=doc.case_id,
                details={
                    "metadata_id": metadata.id,
                    "confidence": confidence,
                    "fields_extracted": sum(
                        1 for v in extracted_data.values() if v
                    )
                }
            )

            return ExtractionResponse(
                metadata_id=metadata.id,
                status=metadata.status,
                extracted_data=metadata.extracted_data,
                confidence_score=metadata.confidence_score,
                primary_ref_no=metadata.primary_ref_no,
                doc_date=str(metadata.doc_date) if metadata.doc_date else None,
                message=(
                    f"Extraction successful in {total_elapsed:.2f}s "
                    f"(pdf: {pdf_elapsed:.2f}s, ocr: {ocr_elapsed:.2f}s, parse: {parse_elapsed:.2f}s). "
                    f"Please review and verify."
                )
            )

        except Exception as e:
            # Save failed status
            self._save_metadata(
                document_id=document_id,
                document_path=doc.storage_path,
                doc_type=doc_type,
                extracted_data={},
                primary_ref_no=None,
                doc_date=None,
                confidence_score=0.0,
                raw_ocr_text=str(e),
                status=ExtractionStatus.FAILED,
                existing=existing
            )
            logger.error(f"Extraction failed for document {document_id}: {e}")
            raise

        finally:
            cleanup_temp_images(image_paths)

    def get_metadata(self, document_id: int) -> Optional[DocumentMetadata]:
        """Get metadata for a document."""
        return (
            self.db.query(DocumentMetadata)
            .filter(DocumentMetadata.document_id == document_id)
            .first()
        )

    def verify(
        self, metadata_id: int, request: MetadataVerifyRequest
    ) -> DocumentMetadata:
        """Verify/edit extracted metadata."""
        metadata = (
            self.db.query(DocumentMetadata)
            .filter(DocumentMetadata.id == metadata_id)
            .first()
        )
        if not metadata:
            raise FileNotFoundError(f"Metadata not found: {metadata_id}")

        # Parse doc_date string to date object
        parsed_date: Optional[date] = None
        if request.doc_date:
            parsed_date = self._parse_date_string(request.doc_date)

        metadata.extracted_data = request.extracted_data
        metadata.primary_ref_no = request.primary_ref_no or metadata.primary_ref_no
        metadata.doc_date = parsed_date or metadata.doc_date
        metadata.status = ExtractionStatus.VERIFIED
        metadata.verified_by = request.verified_by
        metadata.verified_at = datetime.utcnow()
        metadata.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(metadata)

        # Audit log
        self._create_audit_log(
            action="METADATA_VERIFIED",
            document_id=metadata.document_id,
            case_id=metadata.document.case_id if metadata.document else None,
            details={
                "metadata_id": metadata_id,
                "verified_by": request.verified_by
            }
        )

        return metadata

    @staticmethod
    def _parse_date_string(date_str: str) -> Optional[date]:
        """Parse date string in common formats to a date object."""
        formats = [
            "%Y-%m-%d",      # ISO-8601
            "%d/%m/%Y",      # DD/MM/YYYY
            "%m/%d/%Y",      # MM/DD/YYYY
            "%d-%m-%Y",      # DD-MM-YYYY
            "%d.%m.%Y",      # DD.MM.YYYY
            "%Y/%m/%d",      # YYYY/MM/DD
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        logger.warning(f"Could not parse date string: {date_str}")
        return None

    def reject(self, metadata_id: int) -> DocumentMetadata:
        """Reject extraction and reset to PENDING."""
        metadata = (
            self.db.query(DocumentMetadata)
            .filter(DocumentMetadata.id == metadata_id)
            .first()
        )
        if not metadata:
            raise FileNotFoundError(f"Metadata not found: {metadata_id}")

        metadata.status = ExtractionStatus.PENDING
        metadata.extracted_data = {}
        metadata.primary_ref_no = None
        metadata.doc_date = None
        metadata.confidence_score = None
        metadata.verified_by = None
        metadata.verified_at = None
        metadata.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(metadata)
        return metadata

    def list_metadata(
        self,
        doc_type=None,
        status=None,
        primary_ref_no=None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[list, int]:
        """List metadata records with optional filters."""
        query = self.db.query(DocumentMetadata)
        count_query = self.db.query(func.count(DocumentMetadata.id))

        if doc_type:
            query = query.filter(DocumentMetadata.doc_type == doc_type)
            count_query = count_query.filter(DocumentMetadata.doc_type == doc_type)
        if status:
            query = query.filter(DocumentMetadata.status == status)
            count_query = count_query.filter(DocumentMetadata.status == status)
        if primary_ref_no:
            query = query.filter(
                DocumentMetadata.primary_ref_no.ilike(f"%{primary_ref_no}%")
            )
            count_query = count_query.filter(
                DocumentMetadata.primary_ref_no.ilike(f"%{primary_ref_no}%")
            )

        total = count_query.scalar()

        items = (
            query
            .order_by(DocumentMetadata.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

        return list(items), total

    def search_by_ref(
        self, query_str: str, limit: int = 20
    ) -> list[dict]:
        """
        Search documents by any extracted reference field.
        Searches primary_ref_no (indexed) and all values inside
        the extracted_data JSONB column.
        Returns rich results with parent Case/SO context.
        """
        from sqlalchemy import cast, String, or_
        from app.models.sales_order import SalesOrder
        from app.models.case import Case

        results_query = (
            self.db.query(DocumentMetadata, Document, SalesOrder, Case)
            .join(Document, DocumentMetadata.document_id == Document.id)
            .outerjoin(SalesOrder, Document.sales_order_id == SalesOrder.id)
            .outerjoin(Case, Document.case_id == Case.id)
            .filter(
                or_(
                    DocumentMetadata.primary_ref_no.ilike(f"%{query_str}%"),
                    cast(DocumentMetadata.extracted_data, String).ilike(f"%{query_str}%")
                )
            )
            .order_by(DocumentMetadata.created_at.desc())
            .limit(limit)
            .all()
        )

        results = []
        for metadata, doc, so, case in results_query:
            # Find which field(s) matched
            matched_fields = []
            if metadata.primary_ref_no and query_str.lower() in metadata.primary_ref_no.lower():
                matched_fields.append("primary_ref_no")
            if metadata.extracted_data:
                for k, v in metadata.extracted_data.items():
                    if v and isinstance(v, str) and query_str.lower() in v.lower():
                        matched_fields.append(k)

            results.append({
                "metadata_id": metadata.id,
                "document_id": doc.id,
                "doc_type": metadata.doc_type.value,
                "primary_ref_no": metadata.primary_ref_no,
                "doc_date": str(metadata.doc_date) if metadata.doc_date else None,
                "extracted_data": metadata.extracted_data,
                "confidence_score": metadata.confidence_score,
                "status": metadata.status.value,
                "filename": doc.original_filename or doc.filename,
                "matched_fields": matched_fields,
                # Parent context
                "so_number": so.so_number if so else None,
                "so_month": so.so_month if so else None,
                "case_id": case.case_id if case else None,
                "opportunity_id": case.opportunity_id if case else None,
                "customer_name": case.customer_name if case else None,
            })

        return results

    # --- Private Helpers ---

    async def _call_ocr_with_retry(
        self, image_path: str, prompt: str, max_retries: int = 3
    ) -> str:
        """Call OCR with retry logic and exponential backoff."""
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.ocr_client.extract(image_path, prompt)

                # Validate we got a parseable response
                if response and response.strip():
                    return response

                raise ValueError("Empty OCR response")

            except Exception as e:
                last_error = e
                logger.warning(
                    f"OCR attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        raise last_error or Exception("OCR extraction failed after all retries")

    def _get_document(self, document_id: int) -> Optional[Document]:
        return (
            self.db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

    def _get_existing_metadata(
        self, document_id: int
    ) -> Optional[DocumentMetadata]:
        return (
            self.db.query(DocumentMetadata)
            .filter(DocumentMetadata.document_id == document_id)
            .first()
        )

    def _save_metadata(
        self,
        document_id,
        document_path,
        doc_type,
        extracted_data,
        primary_ref_no,
        doc_date,
        confidence_score,
        raw_ocr_text,
        status,
        existing=None
    ) -> DocumentMetadata:
        """Create or update metadata record."""
        if existing:
            existing.document_path = document_path
            existing.doc_type = doc_type
            existing.extracted_data = extracted_data
            existing.primary_ref_no = primary_ref_no
            existing.doc_date = doc_date
            existing.confidence_score = confidence_score
            existing.raw_ocr_text = raw_ocr_text
            existing.status = status
            existing.extracted_at = datetime.utcnow()
            existing.updated_at = datetime.utcnow()
            # Clear verification on re-extract
            existing.verified_by = None
            existing.verified_at = None

            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            metadata = DocumentMetadata(
                document_id=document_id,
                document_path=document_path,
                doc_type=doc_type,
                extracted_data=extracted_data,
                primary_ref_no=primary_ref_no,
                doc_date=doc_date,
                confidence_score=confidence_score,
                raw_ocr_text=raw_ocr_text,
                status=status,
                extracted_at=datetime.utcnow()
            )
            self.db.add(metadata)
            self.db.commit()
            self.db.refresh(metadata)
            return metadata

    def _create_audit_log(self, action, document_id, case_id=None, details=None):
        """Create an audit log entry."""
        log = AuditLog(
            action=action,
            document_id=document_id,
            case_id=case_id,
            actor="system",
            details=details
        )
        self.db.add(log)
        self.db.commit()
