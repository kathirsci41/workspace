"""add_customer_po_ref_to_purchase_orders

Revision ID: h0i1j2k3l4m5
Revises: g9h0i1j2k3l4
Create Date: 2026-04-29 00:00:00.000000

Adds customer_po_ref column to store the ERP/customer-side PO reference number
that appears on customer documents (e.g., PWF4251127816). This allows the
application to distinguish between the app-generated PO ID and the customer's
external reference number for accurate cross-document validation.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'h0i1j2k3l4m5'
down_revision: Union[str, None] = '42236a0b1c36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('customer_po_ref', sa.String(200), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('purchase_orders', 'customer_po_ref')
