"""add_vendor_master

Revision ID: bb3f3d3a85b0
Revises: aafc87ae6bac
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "bb3f3d3a85b0"
down_revision: Union[str, Sequence[str], None] = "aafc87ae6bac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vendor_master",
        sa.Column("gstin", sa.String(length=15), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("vendor_name", sa.String(length=256), nullable=False),
        sa.Column("trade_name", sa.String(length=256), nullable=True),
        sa.Column("state_code", sa.String(length=2), nullable=False),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("gstin"),
    )
    op.create_index(op.f("ix_vendor_master_tenant_id"), "vendor_master", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_vendor_master_tenant_id"), table_name="vendor_master")
    op.drop_table("vendor_master")
