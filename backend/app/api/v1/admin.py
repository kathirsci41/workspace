import os
import asyncio
import json
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, select, case

from app.database import get_db
from app.config import settings
from app.models import Document, DocumentStatus, DocumentMetadata, MetadataStatus, Customer, PurchaseOrder
from app.services.extraction.two_layer_client import check_models_available
from app.services.extraction.pipeline import build_pipeline_from_config
from celery_app import celery_app

router = APIRouter()

# ── Health check cache (Redis TTL = 30s) ──────────────────────────────────────

_HEALTH_CACHE_KEY = "admin:health:cache"
_HEALTH_CACHE_TTL = 30  # seconds


async def _get_redis():
    import redis.asyncio as aioredis
    return aioredis.from_url(settings.redis_url, decode_responses=True)


async def _check_database(db: AsyncSession) -> str:
    try:
        await db.execute(text("SELECT 1"))
        return "ok"
    except Exception as e:
        return f"error: {str(e)}"


async def _check_redis() -> str:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_timeout=3)
        await r.ping()
        await r.aclose()
        return "ok"
    except Exception as e:
        return f"error: {str(e)}"


async def _check_ollama() -> str:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, verify=False, follow_redirects=True) as client:
            resp = await client.get(f"{settings.ocr_base_url.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                return "ok"
            return f"error: HTTP {resp.status_code}"
    except Exception as e:
        return f"error: {str(e)}"


async def _check_models() -> str:
    try:
        if settings.layer1_provider:
            pipeline = build_pipeline_from_config(settings)
            err = await pipeline.health_check()
            return "ok" if not err else f"error: {err}"
        # Legacy path: check Ollama model list
        if settings.ocr_two_layer_enabled:
            models_to_check = [settings.ocr_custom_model, settings.ocr_extractor_model]
        else:
            models_to_check = [settings.ocr_model_name]
        ok, missing = await check_models_available(settings.ocr_base_url, models_to_check)
        return "ok" if ok else f"missing: {missing}"
    except Exception as e:
        return f"error: {str(e)}"


def _check_storage() -> str:
    try:
        nas_path = settings.nas_base_path
        if os.path.exists(nas_path) and os.access(nas_path, os.W_OK):
            return "ok"
        elif os.path.exists(nas_path):
            return "error: not writable"
        else:
            os.makedirs(nas_path, exist_ok=True)
            return "ok"
    except Exception as e:
        return f"error: {str(e)}"


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Check connectivity to all services. Result cached in Redis for 30s."""
    # Try Redis cache first
    try:
        r = await _get_redis()
        cached = await r.get(_HEALTH_CACHE_KEY)
        await r.aclose()
        if cached:
            return json.loads(cached)
    except Exception:
        pass  # Cache miss — proceed with live check

    # Run all checks in parallel
    database_res, redis_res, ollama_res, models_res = await asyncio.gather(
        _check_database(db),
        _check_redis(),
        _check_ollama(),
        _check_models(),
        return_exceptions=False,
    )
    storage_res = _check_storage()

    result = {
        "database": database_res,
        "redis":    redis_res,
        "ollama":   ollama_res,
        "models":   models_res,
        "storage":  storage_res,
    }

    # Cache result in Redis
    try:
        r = await _get_redis()
        await r.setex(_HEALTH_CACHE_KEY, _HEALTH_CACHE_TTL, json.dumps(result))
        await r.aclose()
    except Exception:
        pass

    return result


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard statistics — single combined query."""
    # All counts in one round trip using conditional aggregation
    row = (await db.execute(
        select(
            func.count(Customer.id).label("total_customers"),
        )
    )).one()
    total_customers = row.total_customers

    po_count = (await db.execute(select(func.count(PurchaseOrder.id)))).scalar() or 0

    doc_row = (await db.execute(
        select(
            func.count(Document.id).label("total"),
            func.count(case((Document.status == DocumentStatus.UPLOADED,          Document.id))).label("uploaded"),
            func.count(case((Document.status == DocumentStatus.EXTRACTING,         Document.id))).label("extracting"),
            func.count(case((Document.status == DocumentStatus.PENDING_REVIEW,     Document.id))).label("pending_reviews"),
            func.count(case((Document.status == DocumentStatus.VERIFIED,           Document.id))).label("verified"),
            func.count(case((Document.status == DocumentStatus.EXTRACTION_FAILED,  Document.id))).label("extraction_failures"),
            func.count(case((Document.status == DocumentStatus.PENDING_MODEL,      Document.id))).label("pending_model"),
            func.count(case((Document.status == DocumentStatus.REJECTED,           Document.id))).label("rejected"),
        )
    )).one()

    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(hours=24)
    two_days_ago = now - timedelta(hours=48)

    today_pos = (await db.scalar(
        select(func.count(PurchaseOrder.id)).where(PurchaseOrder.created_at >= yesterday)
    )) or 0
    prev_pos = (await db.scalar(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.created_at >= two_days_ago,
            PurchaseOrder.created_at < yesterday,
        )
    )) or 0

    today_docs = (await db.scalar(
        select(func.count(Document.id)).where(Document.created_at >= yesterday)
    )) or 0
    prev_docs = (await db.scalar(
        select(func.count(Document.id)).where(
            Document.created_at >= two_days_ago,
            Document.created_at < yesterday,
        )
    )) or 0

    today_verified = (await db.scalar(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.VERIFIED,
            Document.updated_at >= yesterday,
        )
    )) or 0
    prev_verified = (await db.scalar(
        select(func.count(Document.id)).where(
            Document.status == DocumentStatus.VERIFIED,
            Document.updated_at >= two_days_ago,
            Document.updated_at < yesterday,
        )
    )) or 0

    return {
        "total_customers":       total_customers,
        "total_purchase_orders": po_count,
        "total_documents":       doc_row.total,
        "uploaded":              doc_row.uploaded,
        "extracting":            doc_row.extracting,
        "pending_reviews":       doc_row.pending_reviews,
        "verified":              doc_row.verified,
        "extraction_failures":   doc_row.extraction_failures,
        "pending_model":         doc_row.pending_model,
        "rejected":              doc_row.rejected,
        "stats_delta": {
            "total_purchase_orders": today_pos - prev_pos,
            "total_documents":       today_docs - prev_docs,
            "verified":              today_verified - prev_verified,
        },
    }


@router.get("/queue")
async def get_queue_status():
    """Celery worker and queue depth — all inspect calls run in parallel."""
    try:
        import concurrent.futures

        def _inspect_all():
            i = celery_app.control.inspect(timeout=2)
            # Run active/reserved/stats concurrently in a thread pool
            with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
                f_active   = pool.submit(lambda: i.active()   or {})
                f_reserved = pool.submit(lambda: i.reserved() or {})
                f_stats    = pool.submit(lambda: i.stats()    or {})
                active   = f_active.result()
                reserved = f_reserved.result()
                stats_i  = f_stats.result()
            return active, reserved, stats_i

        loop = asyncio.get_event_loop()
        active, reserved, stats_i = await loop.run_in_executor(None, _inspect_all)

        return {
            "workers_online": len(stats_i),
            "active_tasks":   sum(len(v) for v in active.values()),
            "queued_tasks":   sum(len(v) for v in reserved.values()),
        }
    except Exception:
        return {"workers_online": 0, "active_tasks": 0, "queued_tasks": 0}


@router.post("/requeue-pending-models")
async def requeue_pending_models(db: AsyncSession = Depends(get_db)):
    """Re-queue all PENDING_MODEL documents for extraction."""
    from app.services.extraction.tasks import extract_document

    result = await db.execute(
        select(Document).where(Document.status == DocumentStatus.PENDING_MODEL)
    )
    docs = result.scalars().all()

    doc_ids = []
    for doc in docs:
        doc.status = DocumentStatus.UPLOADED
        meta_result = await db.execute(
            select(DocumentMetadata).where(DocumentMetadata.document_id == doc.id)
        )
        meta = meta_result.scalar_one_or_none()
        if meta:
            meta.status = MetadataStatus.PENDING
            meta.last_error = None
        doc_ids.append(str(doc.id))

    await db.commit()

    for doc_id in doc_ids:
        extract_document.delay(doc_id)

    return {"requeued": len(doc_ids), "document_ids": doc_ids}
