import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func

from app.database import get_db
from app.config import settings
from app.models import Document, DocumentStatus, Customer, PurchaseOrder

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

    # Ollama
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.ocr_base_url}/api/tags")
            if resp.status_code == 200:
                result["ollama"] = "ok"
            else:
                result["ollama"] = "unavailable"
    except Exception:
        result["ollama"] = "unavailable"

    # NAS Storage
    try:
        nas_path = settings.nas_base_path
        if os.path.exists(nas_path) and os.access(nas_path, os.W_OK):
            result["storage"] = "ok"
        elif os.path.exists(nas_path):
            result["storage"] = "error: not writable"
        else:
            # Try to create it
            os.makedirs(nas_path, exist_ok=True)
            result["storage"] = "ok"
    except Exception as e:
        result["storage"] = f"error: {str(e)}"

    return result


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard statistics."""
    total_customers = (await db.execute(
        func.count(Customer.id).select()
    )).scalar() or 0

    total_pos = (await db.execute(
        func.count(PurchaseOrder.id).select()
    )).scalar() or 0

    total_docs = (await db.execute(
        func.count(Document.id).select()
    )).scalar() or 0

    pending_reviews = (await db.execute(
        func.count(Document.id).select().where(
            Document.status == DocumentStatus.PENDING_REVIEW
        )
    )).scalar() or 0

    verified = (await db.execute(
        func.count(Document.id).select().where(
            Document.status == DocumentStatus.VERIFIED
        )
    )).scalar() or 0

    extraction_failures = (await db.execute(
        func.count(Document.id).select().where(
            Document.status == DocumentStatus.EXTRACTION_FAILED
        )
    )).scalar() or 0

    return {
        "total_customers": total_customers,
        "total_purchase_orders": total_pos,
        "total_documents": total_docs,
        "pending_reviews": pending_reviews,
        "verified": verified,
        "extraction_failures": extraction_failures,
    }
