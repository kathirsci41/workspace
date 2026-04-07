"""add_order_scenario_gst_type_invoice_split_to_purchase_orders

Revision ID: e2f3a4b5c6d7
Revises: f6a7b8c9d0e1
Create Date: 2026-04-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # order_scenario enum
    op.execute("""
        CREATE TYPE orderscenario AS ENUM (
            'unknown', 'procurement', 'stock', 'drop_ship', 'service_amc'
        )
    """)
    op.add_column(
        'purchase_orders',
        sa.Column(
            'order_scenario',
            sa.Enum('unknown', 'procurement', 'stock', 'drop_ship', 'service_amc',
                    name='orderscenario'),
            nullable=False,
            server_default='unknown',
        )
    )

    # gst_type enum
    op.execute("""
        CREATE TYPE gsttype AS ENUM ('unknown', 'igst', 'cgst_sgst')
    """)
    op.add_column(
        'purchase_orders',
        sa.Column(
            'gst_type',
            sa.Enum('unknown', 'igst', 'cgst_sgst', name='gsttype'),
            nullable=False,
            server_default='unknown',
        )
    )

    # invoice_split bool
    op.add_column(
        'purchase_orders',
        sa.Column('invoice_split', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    op.drop_column('purchase_orders', 'invoice_split')
    op.drop_column('purchase_orders', 'gst_type')
    op.execute("DROP TYPE gsttype")
    op.drop_column('purchase_orders', 'order_scenario')
    op.execute("DROP TYPE orderscenario")
