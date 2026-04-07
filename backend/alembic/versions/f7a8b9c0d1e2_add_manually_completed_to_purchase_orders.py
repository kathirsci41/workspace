"""add_manually_completed_to_purchase_orders

Revision ID: f7a8b9c0d1e2
Revises: e2f3a4b5c6d7
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f7a8b9c0d1e2'
down_revision: Union[str, None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'purchase_orders',
        sa.Column('manually_completed', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column(
        'purchase_orders',
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        'purchase_orders',
        sa.Column('completion_note', sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('purchase_orders', 'completion_note')
    op.drop_column('purchase_orders', 'completed_at')
    op.drop_column('purchase_orders', 'manually_completed')
