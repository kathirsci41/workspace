"""add document_metadata table

Revision ID: 002_add_document_metadata
Revises: 001_initial
Create Date: 2026-02-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_add_document_metadata'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create PostgreSQL ENUM types first
    extraction_status = postgresql.ENUM(
        'PENDING', 'EXTRACTED', 'VERIFIED', 'FAILED',
        name='extraction_status',
        create_type=False
    )
    extraction_status.create(op.get_bind(), checkfirst=True)

    metadata_doc_type = postgresql.ENUM(
        'CUSTOMER_PO', 'VENDOR_INVOICE', 'VENDOR_DC',
        'COMPANY_INVOICE', 'COMPANY_DC', 'POD', 'PURCHASE_BILL',
        name='metadata_doc_type',
        create_type=False
    )
    metadata_doc_type.create(op.get_bind(), checkfirst=True)

    # Create document_metadata table
    op.create_table(
        'document_metadata',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('document_path', sa.String(length=1024), nullable=False),
        sa.Column('doc_type', metadata_doc_type, nullable=False),
        sa.Column('primary_ref_no', sa.String(length=255), nullable=True),
        sa.Column('doc_date', sa.Date(), nullable=True),
        sa.Column('extracted_data', postgresql.JSONB(astext_type=sa.Text()),
                  server_default='{}', nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('status', extraction_status, server_default='PENDING', nullable=False),
        sa.Column('raw_ocr_text', sa.Text(), nullable=True),
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_by', sa.String(length=255), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(
            ['document_id'], ['documents.id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', name='uq_document_metadata_document_id'),
    )

    # Indexes
    op.create_index('ix_document_metadata_id', 'document_metadata', ['id'])
    op.create_index('idx_metadata_doc_type', 'document_metadata', ['doc_type'])
    op.create_index('idx_metadata_status', 'document_metadata', ['status'])
    op.create_index('idx_metadata_primary_ref', 'document_metadata', ['primary_ref_no'])
    op.create_index('idx_metadata_doc_date', 'document_metadata', ['doc_date'])

    # GIN index on JSONB column for efficient JSON queries
    op.create_index(
        'idx_metadata_extracted_data',
        'document_metadata',
        ['extracted_data'],
        postgresql_using='gin'
    )


def downgrade() -> None:
    op.drop_index('idx_metadata_extracted_data', table_name='document_metadata')
    op.drop_index('idx_metadata_doc_date', table_name='document_metadata')
    op.drop_index('idx_metadata_primary_ref', table_name='document_metadata')
    op.drop_index('idx_metadata_status', table_name='document_metadata')
    op.drop_index('idx_metadata_doc_type', table_name='document_metadata')
    op.drop_index('ix_document_metadata_id', table_name='document_metadata')
    op.drop_table('document_metadata')

    # Drop ENUM types
    sa.Enum(name='extraction_status').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='metadata_doc_type').drop(op.get_bind(), checkfirst=True)
