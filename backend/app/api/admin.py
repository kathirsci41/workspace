from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.case import Case
from app.models.sales_order import SalesOrder
from app.models.document import Document
from app.models.audit_log import AuditLog

router = APIRouter()


@router.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.1.0"
    }


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    """Get system statistics."""
    # Count totals
    total_cases = db.query(func.count(Case.id)).scalar()
    total_sales_orders = db.query(func.count(SalesOrder.id)).scalar()
    total_documents = db.query(func.count(Document.id)).scalar()
    
    # Count by status
    open_cases = db.query(func.count(Case.id)).filter(Case.status == "OPEN").scalar()
    in_progress_cases = db.query(func.count(Case.id)).filter(Case.status == "IN_PROGRESS").scalar()
    closed_cases = db.query(func.count(Case.id)).filter(Case.status == "CLOSED").scalar()
    
    # Count by document type
    doc_type_counts = db.query(
        Document.document_type,
        func.count(Document.id)
    ).group_by(Document.document_type).all()
    doc_by_type = {dt: count for dt, count in doc_type_counts}
    
    # Total storage size
    total_size = db.query(func.sum(Document.file_size)).scalar() or 0
    
    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_uploads = db.query(func.count(Document.id)).filter(
        Document.uploaded_at >= week_ago
    ).scalar()
    
    return {
        "cases": {
            "total": total_cases,
            "open": open_cases,
            "in_progress": in_progress_cases,
            "closed": closed_cases
        },
        "sales_orders": {
            "total": total_sales_orders
        },
        "documents": {
            "total": total_documents,
            "by_type": doc_by_type,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2) if total_size else 0,
            "recent_uploads_7d": recent_uploads
        }
    }


@router.get("/audit-logs")
def get_audit_logs(
    case_id: Optional[int] = None,
    action: Optional[str] = None,
    actor: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get audit logs with optional filters."""
    query = db.query(AuditLog)
    
    if case_id:
        query = query.filter(AuditLog.case_id == case_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if actor:
        query = query.filter(AuditLog.actor.ilike(f"%{actor}%"))
    
    total = query.count()
    logs = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
    
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": logs
    }
