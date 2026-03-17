"""Phase 7: Add version-safe persistence columns

Revision ID: phase7_versioning
Revises: a1b2c3d4e5f6
Create Date: 2026-02-25 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'phase7_versioning'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add extraction_version column to document_metadata
    op.add_column('document_metadata',
        sa.Column('extraction_version', sa.Integer(), nullable=False, server_default='1')
    )

    # Add field_confidences column to document_metadata
    op.add_column('document_metadata',
        sa.Column('field_confidences', postgresql.JSONB(), nullable=True)
    )

    # Create extraction_corrections table
    op.create_table(
        'extraction_corrections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('document_id', postgresql.UUID(as_uuid=True),
            sa.ForeignKey('documents.id'), nullable=False),
        sa.Column('field_name', sa.String(100), nullable=False),
        sa.Column('original_value', sa.Text(), nullable=True),
        sa.Column('corrected_value', sa.Text(), nullable=True),
        sa.Column('operator_id', sa.String(100), nullable=True),
        sa.Column('corrected_at', sa.DateTime(), nullable=False),
        sa.Column('extraction_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('used_for_training', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_corr_document_id', 'extraction_corrections', ['document_id'])


def downgrade() -> None:
    # Drop extraction_corrections table
    op.drop_index('ix_corr_document_id', table_name='extraction_corrections')
    op.drop_table('extraction_corrections')

    # Drop columns from document_metadata
    op.drop_column('document_metadata', 'field_confidences')
    op.drop_column('document_metadata', 'extraction_version')
