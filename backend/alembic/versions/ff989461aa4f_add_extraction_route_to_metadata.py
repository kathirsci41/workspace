"""add_extraction_route_to_metadata

Revision ID: ff989461aa4f
Revises: phase7_versioning
Create Date: 2026-02-25 18:12:10.412923

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff989461aa4f'
down_revision: Union[str, None] = 'phase7_versioning'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('document_metadata',
        sa.Column('extraction_route', sa.String(20), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('document_metadata', 'extraction_route')
