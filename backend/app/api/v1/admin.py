import os
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select

from app.database import get_db
from app.config import settings
from app.models import Document, DocumentStatus, DocumentMetadata, MetadataStatus, Customer, PurchaseOrder
from app.services.extraction.two_layer_client import check_models_available

router = APIRouter()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check connectivity to all services."""
    result = {}

    # Database
    try:
        await db.execute(text("SELECT 1"))
        result["database"] = "ok"
    except Exception as e:
        result["database"] = f"error: {str(e)}"

    # Redis
    try:
        import redis as redis_lib
        r: redis_lib.Redis = redis_lib.Redis.from_url(settings.redis_url, socket_timeout=3)  # type: ignore[assignment]
        r.ping()
        result["redis"] = "ok"
    except Exception as e:
        result["redis"] = f"error: {str(e)}"

    # Ollama / OCR endpoint reachability + model availability
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=True) as client:
            resp = await client.get(f"{settings.ocr_base_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                result["ollama"] = "ok"
            else:
                result["ollama"] = f"error: HTTP {resp.status_code} from {settings.ocr_base_url}"
    except Exception as e:
        result["ollama"] = f"error: {str(e)}"

    # Required model availability
    try:
        if settings.ocr_two_layer_enabled:
            models_to_check = [settings.ocr_custom_model, settings.ocr_extractor_model]
        else:
            models_to_check = [settings.ocr_model_name]

        ok, missing = await check_models_available(settings.ocr_base_url, models_to_check)
        if ok:
            result["models"] = "ok"
        else:
            result["models"] = f"missing: {missing}"
    except Exception as e:
        result["models"] = f"error: {str(e)}"

    # NAS Storage
    try:
        nas_path = settings.nas_base_path
        if os.path.exists(nas_path) and os.access(nas_path, os.W_OK):
            result["storage"] = "ok"
        elif os.path.exists(nas_path):
            result["storage"] = "error: not writable"
        else:
            os.makedirs(nas_path, exist_ok=True)
            result["storage"] = "ok"
    except Exception as e:
        result["storage"] = f"error: {str(e)}"

    return result


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard and admin statistics."""
    total_customers = (await db.execute(
        select(func.count(Customer.id))
    )).scalar() or 0

    total_pos = (await db.execute(
        select(func.count(PurchaseOrder.id))
    )).scalar() or 0

    total_docs = (await db.execute(
        select(func.count(Document.id))
    )).scalar() or 0

    uploaded = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.UPLOADED
        )
    )).scalar() or 0

    extracting = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.EXTRACTING
        )
    )).scalar() or 0

    pending_reviews = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.PENDING_REVIEW
        )
    )).scalar() or 0

    verified = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.VERIFIED
        )
    )).scalar() or 0

    extraction_failures = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.EXTRACTION_FAILED
        )
    )).scalar() or 0

    pending_model = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.PENDING_MODEL
        )
    )).scalar() or 0

    rejected = (await db.execute(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.REJECTED
        )
    )).scalar() or 0

    return {
        "total_customers": total_customers,
        "total_purchase_orders": total_pos,
        "total_documents": total_docs,
        "uploaded": uploaded,
        "extracting": extracting,
        "pending_reviews": pending_reviews,
        "verified": verified,
        "extraction_failures": extraction_failures,
        "pending_model": pending_model,
        "rejected": rejected,
    }


@router.get("/queue")
async def get_queue_status():
    """Celery worker and queue depth status."""
    try:
        from celery_app import celery_app
        i = celery_app.control.inspect(timeout=2)
        active = i.active() or {}
        reserved = i.reserved() or {}
        stats_i = i.stats() or {}
        return {
            "workers_online": len(stats_i),
            "active_tasks": sum(len(v) for v in active.values()),
            "queued_tasks": sum(len(v) for v in reserved.values()),
        }
    except Exception:
        return {
            "workers_online": 0,
            "active_tasks": 0,
            "queued_tasks": 0,
        }


@router.post("/requeue-pending-models")
async def requeue_pending_models(db: AsyncSession = Depends(get_db)):
    """Re-queue all PENDING_MODEL documents for extraction.

    Use this after fixing the model endpoint (e.g., after pulling a missing
    model or switching the OCR_BASE_URL). All held documents are reset to
    UPLOADED so the extraction task will run again with a fresh model check.
    """
    from app.services.extraction.tasks import extract_document

    result = await db.execute(
        select(Document).where(Document.status == DocumentStatus.PENDING_MODEL)
    )
    docs = result.scalars().all()

    doc_ids = []
    for doc in docs:
        doc.status = DocumentStatus.UPLOADED
        # Reset metadata so it's ready for a fresh extraction attempt
        meta_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id)
        )
        meta = meta_result.scalar_one_or_none()
        if meta:
            meta.status = MetadataStatus.PENDING
            meta.last_error = None
        doc_ids.append(str(doc.id))

    await db.commit()

    # Queue extraction tasks after the DB commit
    for doc_id in doc_ids:
        extract_document.delay(doc_id)

    return {"requeued": len(doc_ids), "document_ids": doc_ids}
