from __future__ import annotations

from fastapi import APIRouter

from app.services.extraction.glm_ocr_client import check_ocr_provider_health


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "order-assurance", "ocr": check_ocr_provider_health()}
