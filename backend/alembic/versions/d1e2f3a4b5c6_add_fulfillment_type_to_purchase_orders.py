"""add_fulfillment_type_to_purchase_orders

Revision ID: d1e2f3a4b5c6
Revises: c5d3e9f2a1b8
Create Date: 2026-03-30 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c5d3e9f2a1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum type idempotently (safe to re-run if type already exists)
    op.execute("""
    DO $$ BEGIN
        CREATE TYPE fulfillmenttype AS ENUM ('procurement', 'stock');
    EXCEPTION WHEN duplicate_object THEN null;
    END $$;
""")
    op.add_column(
        'purchase_orders',
        sa.Column(
            'fulfillment_type',
            sa.Enum('procurement', 'stock', name='fulfillmenttype'),
            nullable=False,
            server_default='procurement',
        )
    )


def downgrade() -> None:
    op.drop_column('purchase_orders', 'fulfillment_type')
    op.execute("""
    DO $$ BEGIN
        DROP TYPE fulfillmenttype;
    EXCEPTION WHEN undefined_object THEN null;
    END $$;
""")
