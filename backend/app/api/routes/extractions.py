from __future__ import annotations

from fastapi import APIRouter

from app.services.extraction_queue import get_ocr_extraction_activity


router = APIRouter(prefix="/extractions", tags=["extractions"])


@router.get("/activity")
def get_extraction_activity():
    return get_ocr_extraction_activity()
