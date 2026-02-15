"""
Seed script: creates sample customers and purchase orders.
Run with: python -m app.seed
"""
import asyncio
from datetime import date
from sqlalchemy import select
from app.database import async_engine, AsyncSessionLocal
from app.models import Base, Customer, PurchaseOrder, POStatus


async def seed():
    # Create tables if they don't exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Check if data already exists
        existing = (await db.execute(
            select(Customer).where(Customer.customer_id == "SKY-AB1234")
        )).scalar_one_or_none()

        if existing:
            print("Seed data already exists. Skipping.")
            return

        # Create 3 sample customers
        c1 = Customer(
            customer_id="SKY-AB1234",
            name="Acme Corp",
            contact_email="procurement@acmecorp.com",
            contact_phone="+91-9876543210",
            address="123 Industrial Area, Bangalore, Karnataka",
            gst_number="29AABCA1234A1Z5",
            notes="Key client — high volume monthly orders",
        )
        c2 = Customer(
            customer_id="SKY-CD5678",
            name="TechVision Ltd",
            contact_email="orders@techvision.in",
            contact_phone="+91-9876543211",
            address="456 Tech Park, Delhi NCR",
            gst_number="07AABCT5678B1Z3",
            notes="Medium-volume client",
        )
        c3 = Customer(
            customer_id="SKY-EF9012",
            name="Global Traders",
            contact_email="info@globaltraders.com",
            contact_phone="+91-9876543212",
            address="789 Commerce Street, Mumbai, Maharashtra",
            gst_number="27AABCG9012C1Z1",
        )
        db.add_all([c1, c2, c3])
        await db.flush()

        # Create 2 sample POs
        po1 = PurchaseOrder(
            customer_id=c1.id,
            po_number="PO-2026-0001",
            po_date=date(2026, 1, 5),
            total_amount=450000.00,
            status=POStatus.INITIATED,
            chain_completeness=0.0,
            notes="Urgent order — Q1 delivery",
        )
        po2 = PurchaseOrder(
            customer_id=c2.id,
            po_number="PO-2026-0002",
            po_date=date(2026, 1, 12),
            total_amount=225000.00,
            status=POStatus.INITIATED,
            chain_completeness=0.0,
        )
        db.add_all([po1, po2])

        await db.commit()
        print("Seed data created successfully!")
        print(f"  Customers: {c1.customer_id}, {c2.customer_id}, {c3.customer_id}")
        print(f"  POs: {po1.po_number}, {po2.po_number}")


if __name__ == "__main__":
    asyncio.run(seed())
