from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.database import get_db
from app.schemas.extraction import SearchResponse, SearchResult
from app.services.search_service import global_search, search_by_ref, advanced_search

router = APIRouter()


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query("", min_length=0),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Global search across all references, customers, and POs."""
    if len(q) < 2:
        return SearchResponse(results=[], total=0, query=q)
    result = await global_search(db, q, page, per_page)
    return SearchResponse(
        results=[SearchResult(**r) for r in result["results"]],
        total=result["total"],
        query=result["query"],
    )


@router.get("/by-ref/{ref_value}")
async def search_by_reference(
    ref_value: str,
    db: AsyncSession = Depends(get_db),
):
    """Direct exact lookup by reference value."""
    results = await search_by_ref(db, ref_value)
    return {
        "results": [SearchResult(**r) for r in results],
        "total": len(results),
        "query": ref_value,
    }


@router.get("/advanced", response_model=SearchResponse)
async def search_advanced(
    invoice_no: Optional[str] = None,
    dc_no: Optional[str] = None,
    po_no: Optional[str] = None,
    so_no: Optional[str] = None,
    customer_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    document_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Advanced multi-field search."""
    result = await advanced_search(
        db,
        invoice_no=invoice_no,
        dc_no=dc_no,
        po_no=po_no,
        so_no=so_no,
        customer_name=customer_name,
        date_from=date_from,
        date_to=date_to,
        document_type=document_type,
        page=page,
        per_page=per_page,
    )
    return SearchResponse(
        results=[SearchResult(**r) for r in result["results"]],
        total=result["total"],
        query=result["query"],
    )
