"""add_so_number_to_purchase_orders

Revision ID: a3f1c9b2e7d4
Revises: ff989461aa4f
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9b2e7d4'
down_revision: Union[str, None] = 'ff989461aa4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('purchase_orders',
        sa.Column('so_number', sa.String(100), nullable=True)
    )
    op.create_index('ix_po_so_number', 'purchase_orders', ['so_number'])


def downgrade() -> None:
    op.drop_index('ix_po_so_number', table_name='purchase_orders')
    op.drop_column('purchase_orders', 'so_number')
