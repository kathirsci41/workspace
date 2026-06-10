from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.serializers import document_to_dict
from app import config
from app.database import get_db
from app.services.demo_seed_service import seed_panimalar_demo


router = APIRouter(prefix="/dev", tags=["dev"])


@router.post("/seed-panimalar", status_code=status.HTTP_201_CREATED)
def seed_panimalar(db: Session = Depends(get_db)):
    if not (config.settings.enable_dev_tools or config.settings.app_env == "development"):
        raise HTTPException(status_code=403, detail="Development tools are disabled.")
    result = seed_panimalar_demo(db)
    db.commit()
    db.refresh(result["bundle"])
    return {
        "bundle": {
            "id": result["bundle"].id,
            "bundle_number": result["bundle"].bundle_number,
            "customer_name": result["bundle"].customer_name,
            "status": result["bundle"].status,
            "customer_delivery_status": result["bundle"].customer_delivery_status,
            "vendor_procurement_status": result["bundle"].vendor_procurement_status,
        },
        "documents": {key: document_to_dict(value) for key, value in result["documents"].items()},
        "verification_summary": result["verification_summary"],
    }
