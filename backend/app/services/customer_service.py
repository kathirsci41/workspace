from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from fastapi import HTTPException

from app.models.customer import Customer
from app.models.purchase_order import PurchaseOrder
from app.schemas.customer import CustomerCreate, CustomerUpdate


async def create_customer(db: AsyncSession, data: CustomerCreate) -> Customer:
    """Create a new customer. Raises 409 if customer_id already exists."""
    existing = (await db.execute(
        select(Customer).where(Customer.customer_id == data.customer_id)
    )).scalar_one_or_none()

    if existing:
        raise HTTPException(status_code=409, detail=f"Customer ID '{data.customer_id}' already exists")

    customer = Customer(**data.model_dump())
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    return customer


async def get_customer(db: AsyncSession, id: UUID) -> Customer:
    """Fetch customer by PK with purchase_orders loaded."""
    result = await db.execute(
        select(Customer)
        .options(selectinload(Customer.purchase_orders))
        .where(Customer.id == id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer


async def get_customer_by_sky_id(db: AsyncSession, customer_id: str) -> Customer:
    """Fetch customer by business ID (SKY-xxx)."""
    result = await db.execute(
        select(Customer).where(Customer.customer_id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer '{customer_id}' not found")
    return customer


async def list_customers(
    db: AsyncSession,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> tuple[list[Customer], int]:
    """List customers with optional search and pagination."""
    query = select(Customer).where(Customer.is_active == True)

    if search:
        search_filter = f"%{search}%"
        query = query.where(
            or_(
                Customer.customer_id.ilike(search_filter),
                Customer.name.ilike(search_filter),
                Customer.gst_number.ilike(search_filter),
            )
        )

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    # Fetch page
    query = query.order_by(Customer.name.asc())
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    items = list(result.scalars().all())

    return items, total


async def update_customer(db: AsyncSession, id: UUID, data: CustomerUpdate) -> Customer:
    """Update customer non-None fields."""
    customer = await get_customer(db, id)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(customer, key, value)

    await db.commit()
    await db.refresh(customer)
    return customer


async def get_customer_po_count(db: AsyncSession, customer_id: UUID) -> int:
    """Count purchase orders for a customer."""
    result = await db.execute(
        select(func.count(PurchaseOrder.id)).where(
            PurchaseOrder.customer_id == customer_id
        )
    )
    return result.scalar() or 0
