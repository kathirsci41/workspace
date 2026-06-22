from __future__ import annotations

from app.worker import celery_app
from app.database import SessionLocal
from app.repositories.documents import DocumentRepository
from app.services.extraction_service import extract_document


@celery_app.task(
    bind=True,
    name="extraction.process_document",
    max_retries=3,
    default_retry_delay=30,
)
def process_document_task(self, document_id: str) -> dict:
    """Extract fields from a single document. Retried 3x on failure."""
    db = SessionLocal()
    try:
        document = DocumentRepository(db).get(document_id)
        if not document:
            return {"document_id": document_id, "status": "not_found"}
        result = extract_document(db, document, force=True)
        db.commit()
        return {"document_id": document_id, "status": "done"}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc)
    finally:
        db.close()
