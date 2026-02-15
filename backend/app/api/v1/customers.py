from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.customer import (
    CustomerCreate, CustomerUpdate, CustomerResponse, CustomerListResponse,
)
from app.schemas.purchase_order import POListResponse, POResponse
from app.services import customer_service
from app.services import po_service

router = APIRouter()


@router.post("", response_model=CustomerResponse, status_code=201)
async def create_customer(
    data: CustomerCreate,
    db: AsyncSession = Depends(get_db),
):
    customer = await customer_service.create_customer(db, data)
    po_count = await customer_service.get_customer_po_count(db, customer.id)
    resp = CustomerResponse.model_validate(customer)
    resp.po_count = po_count
    return resp


@router.get("", response_model=CustomerListResponse)
async def list_customers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    items, total = await customer_service.list_customers(db, page, per_page, search)

    responses = []
    for c in items:
        po_count = await customer_service.get_customer_po_count(db, c.id)
        resp = CustomerResponse.model_validate(c)
        resp.po_count = po_count
        responses.append(resp)

    return CustomerListResponse(
        items=responses, total=total, page=page, per_page=per_page,
    )


@router.get("/{id}", response_model=CustomerResponse)
async def get_customer(
    id: UUID,
    db: AsyncSession = Depends(get_db),
):
    customer = await customer_service.get_customer(db, id)
    po_count = await customer_service.get_customer_po_count(db, customer.id)
    resp = CustomerResponse.model_validate(customer)
    resp.po_count = po_count
    return resp


@router.patch("/{id}", response_model=CustomerResponse)
async def update_customer(
    id: UUID,
    data: CustomerUpdate,
    db: AsyncSession = Depends(get_db),
):
    customer = await customer_service.update_customer(db, id, data)
    po_count = await customer_service.get_customer_po_count(db, customer.id)
    resp = CustomerResponse.model_validate(customer)
    resp.po_count = po_count
    return resp


@router.get("/{id}/purchase-orders", response_model=POListResponse)
async def list_customer_pos(
    id: UUID,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # Verify customer exists
    await customer_service.get_customer(db, id)

    items, total = await po_service.list_pos(
        db, page=page, per_page=per_page, customer_id=id, status=status,
    )

    responses = []
    for po in items:
        resp = POResponse.model_validate(po)
        if po.customer:
            resp.customer_name = po.customer.name
            resp.customer_sky_id = po.customer.customer_id
        responses.append(resp)

    return POListResponse(
        items=responses, total=total, page=page, per_page=per_page,
    )
