from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas.sales_order import SalesOrderCreate, SalesOrderResponse
from app.services.case_service import CaseService
from app.services.sales_order_service import SalesOrderService

router = APIRouter()


@router.post("/cases/{case_id}/sales-orders", response_model=SalesOrderResponse, status_code=status.HTTP_201_CREATED)
def create_sales_order(case_id: str, so_data: SalesOrderCreate, db: Session = Depends(get_db)):
    """Create a new sales order for a case."""
    # Get case by case_id string
    case_service = CaseService(db)
    case = case_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    
    so_service = SalesOrderService(db)
    try:
        sales_order = so_service.create_sales_order(case.id, so_data)
        return so_service.get_sales_order_with_checklist(sales_order)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/cases/{case_id}/sales-orders")
def get_case_sales_orders(
    case_id: str,
    month: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all sales orders for a case, optionally filtered by month."""
    # Get case by case_id string
    case_service = CaseService(db)
    case = case_service.get_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Case {case_id} not found")
    
    so_service = SalesOrderService(db)
    sales_orders = so_service.get_sales_orders_for_case(case.id, month)
    
    # Add checklist to each SO
    result = [so_service.get_sales_order_with_checklist(so) for so in sales_orders]
    return result


@router.get("/sales-orders/search")
def search_sales_orders(so_number: str, db: Session = Depends(get_db)):
    """Search for sales orders by SO number (global search)."""
    so_service = SalesOrderService(db)
    results = so_service.search_sales_orders(so_number)
    return {"results": results}


@router.get("/sales-orders/{so_id}")
def get_sales_order(so_id: int, db: Session = Depends(get_db)):
    """Get a specific sales order by ID."""
    so_service = SalesOrderService(db)
    sales_order = so_service.get_sales_order(so_id)
    if not sales_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sales Order with ID {so_id} not found")
    return so_service.get_sales_order_with_checklist(sales_order)
