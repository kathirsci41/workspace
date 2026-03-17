"""initial schema

Revision ID: 6e44882e6975
Revises:
Create Date: 2026-02-16 15:16:18.199891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6e44882e6975'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # Drop legacy v1 tables if they exist (from old auth-based schema)
    if 'users' in existing_tables:
        with op.batch_alter_table('users', schema=None) as batch_op:
            batch_op.drop_index('ix_users_email')
            batch_op.drop_index('ix_users_username')
        op.drop_table('users')

    if 'audit_logs' in existing_tables:
        with op.batch_alter_table('audit_logs', schema=None) as batch_op:
            batch_op.drop_index('ix_audit_logs_entity_id')
            batch_op.drop_index('ix_audit_logs_entity_type')
        op.drop_table('audit_logs')

    # Create enum types (idempotent — safe to re-run)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE postatus AS ENUM (
                'INITIATED', 'IN_PROGRESS', 'NEAR_COMPLETE', 'COMPLETE', 'CANCELLED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    # documenttype starts with POD; migration a1b2c3d4e5f6 replaces it with COMPANY_PO
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE documenttype AS ENUM (
                'CUSTOMER_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
                'COMPANY_DC', 'COMPANY_INVOICE', 'POD'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    # documentstatus starts without PENDING_MODEL; migration b4c2d8e1f0a9 adds it
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE documentstatus AS ENUM (
                'UPLOADED', 'EXTRACTING', 'PENDING_REVIEW',
                'VERIFIED', 'REJECTED', 'EXTRACTION_FAILED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE metadatastatus AS ENUM (
                'PENDING', 'EXTRACTED', 'VERIFIED', 'FAILED'
            );
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # customers
    if 'customers' not in existing_tables:
        op.create_table('customers',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('customer_id', sa.String(50), nullable=False,
                comment='Business ID like SKY-AB1234, used as NAS folder name'),
            sa.Column('name', sa.String(255), nullable=False,
                comment='Display name like Acme Corp'),
            sa.Column('contact_email', sa.String(255), nullable=True),
            sa.Column('contact_phone', sa.String(50), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('gst_number', sa.String(50), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('customer_id', name='uq_customers_customer_id'),
        )
        op.create_index('ix_customers_customer_id', 'customers', ['customer_id'], unique=True)
        op.create_index('ix_customers_name', 'customers', ['name'])
        op.create_index('ix_customers_gst', 'customers', ['gst_number'])

    # purchase_orders — so_number column added later by migration a3f1c9b2e7d4
    if 'purchase_orders' not in existing_tables:
        op.create_table('purchase_orders',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('customer_id', postgresql.UUID(as_uuid=True),
                sa.ForeignKey('customers.id'), nullable=False),
            sa.Column('po_number', sa.String(100), nullable=False),
            sa.Column('po_date', sa.Date(), nullable=True),
            sa.Column('total_amount', sa.Numeric(15, 2), nullable=True),
            sa.Column('status',
                sa.Enum('INITIATED', 'IN_PROGRESS', 'NEAR_COMPLETE', 'COMPLETE', 'CANCELLED',
                        name='postatus', create_type=False),
                nullable=False, server_default='INITIATED'),
            sa.Column('chain_completeness', sa.Float(), nullable=False, server_default='0.0'),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('po_number', name='uq_po_number'),
        )
        op.create_index('ix_po_number', 'purchase_orders', ['po_number'], unique=True)
        op.create_index('ix_po_customer_id', 'purchase_orders', ['customer_id'])
        op.create_index('ix_po_status', 'purchase_orders', ['status'])
        op.create_index('ix_po_date', 'purchase_orders', ['po_date'])

    # documents
    if 'documents' not in existing_tables:
        op.create_table('documents',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('po_id', postgresql.UUID(as_uuid=True),
                sa.ForeignKey('purchase_orders.id'), nullable=False),
            sa.Column('document_type',
                sa.Enum('CUSTOMER_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
                        'COMPANY_DC', 'COMPANY_INVOICE', 'POD',
                        name='documenttype', create_type=False),
                nullable=False),
            sa.Column('filename', sa.String(255), nullable=False,
                comment='UUID-prefixed stored name'),
            sa.Column('original_filename', sa.String(255), nullable=False,
                comment="User's original filename"),
            sa.Column('file_path', sa.String(500), nullable=False,
                comment='Relative NAS path'),
            sa.Column('file_size', sa.Integer(), nullable=False,
                comment='File size in bytes'),
            sa.Column('mime_type', sa.String(100), nullable=False,
                server_default='application/pdf'),
            sa.Column('page_count', sa.Integer(), nullable=True),
            sa.Column('checksum', sa.String(64), nullable=False, comment='SHA-256 hex'),
            sa.Column('status',
                sa.Enum('UPLOADED', 'EXTRACTING', 'PENDING_REVIEW',
                        'VERIFIED', 'REJECTED', 'EXTRACTION_FAILED',
                        name='documentstatus', create_type=False),
                nullable=False, server_default='UPLOADED'),
            sa.Column('rotation', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('po_id', 'document_type', 'checksum', name='uq_doc_per_po_type'),
        )
        op.create_index('ix_doc_po_id', 'documents', ['po_id'])
        op.create_index('ix_doc_type', 'documents', ['document_type'])
        op.create_index('ix_doc_checksum', 'documents', ['checksum'])
        op.create_index('ix_doc_status', 'documents', ['status'])

    # document_metadata
    # extraction_version + field_confidences added by phase7_versioning
    # extraction_route added by ff989461aa4f
    if 'document_metadata' not in existing_tables:
        op.create_table('document_metadata',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('document_id', postgresql.UUID(as_uuid=True),
                sa.ForeignKey('documents.id'), nullable=False),
            sa.Column('document_type',
                sa.Enum('CUSTOMER_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
                        'COMPANY_DC', 'COMPANY_INVOICE', 'POD',
                        name='documenttype', create_type=False),
                nullable=False),
            sa.Column('extracted_data', postgresql.JSONB(), nullable=True),
            sa.Column('raw_ocr_text', sa.Text(), nullable=True),
            sa.Column('primary_ref_no', sa.String(100), nullable=True),
            sa.Column('po_ref_no', sa.String(100), nullable=True),
            sa.Column('doc_date', sa.Date(), nullable=True),
            sa.Column('total_amount', sa.Numeric(15, 2), nullable=True),
            sa.Column('confidence_score', sa.Float(), nullable=True),
            sa.Column('status',
                sa.Enum('PENDING', 'EXTRACTED', 'VERIFIED', 'FAILED',
                        name='metadatastatus', create_type=False),
                nullable=False, server_default='PENDING'),
            sa.Column('extraction_attempts', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('last_error', sa.Text(), nullable=True),
            sa.Column('extracted_at', sa.DateTime(), nullable=True),
            sa.Column('verified_at', sa.DateTime(), nullable=True),
            sa.Column('model_version', sa.String(50), nullable=True),
            sa.Column('processing_time_ms', sa.Integer(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.UniqueConstraint('document_id', name='uq_meta_document_id'),
        )
        op.create_index('ix_meta_document_id', 'document_metadata', ['document_id'], unique=True)
        op.create_index('ix_meta_primary_ref', 'document_metadata', ['primary_ref_no'])
        op.create_index('ix_meta_po_ref', 'document_metadata', ['po_ref_no'])
        op.create_index('ix_meta_doc_date', 'document_metadata', ['doc_date'])
        op.create_index('ix_meta_status', 'document_metadata', ['status'])
        op.create_index('ix_meta_extracted_data', 'document_metadata', ['extracted_data'],
                        postgresql_using='gin')

    # reference_index
    if 'reference_index' not in existing_tables:
        op.create_table('reference_index',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('document_id', postgresql.UUID(as_uuid=True),
                sa.ForeignKey('documents.id'), nullable=False),
            sa.Column('po_id', postgresql.UUID(as_uuid=True),
                sa.ForeignKey('purchase_orders.id'), nullable=False,
                comment='Denormalized for speed'),
            sa.Column('ref_type', sa.String(50), nullable=False,
                comment='e.g. invoice_number, dc_number, po_number'),
            sa.Column('ref_value', sa.String(255), nullable=False,
                comment='The actual reference value'),
            sa.Column('document_type',
                sa.Enum('CUSTOMER_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
                        'COMPANY_DC', 'COMPANY_INVOICE', 'POD',
                        name='documenttype', create_type=False),
                nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        )
        op.create_index('ix_ref_value', 'reference_index', ['ref_value'])
        op.create_index('ix_ref_type_value', 'reference_index', ['ref_type', 'ref_value'])
        op.create_index('ix_ref_document_id', 'reference_index', ['document_id'])
        op.create_index('ix_ref_po_id', 'reference_index', ['po_id'])


def downgrade() -> None:
    op.drop_table('reference_index')
    op.drop_table('document_metadata')
    op.drop_table('documents')
    op.drop_table('purchase_orders')
    op.drop_table('customers')

    op.execute("DROP TYPE IF EXISTS metadatastatus")
    op.execute("DROP TYPE IF EXISTS documentstatus")
    op.execute("DROP TYPE IF EXISTS documenttype")
    op.execute("DROP TYPE IF EXISTS postatus")
