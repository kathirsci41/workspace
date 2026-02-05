"""Initial migration - create all tables

Revision ID: 001_initial
Revises: 
Create Date: 2026-01-24

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create cases table
    op.create_table('cases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.String(length=20), nullable=False),
        sa.Column('opportunity_id', sa.String(length=20), nullable=False),
        sa.Column('customer_name', sa.String(length=255), nullable=False),
        sa.Column('case_type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='OPEN', nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_cases_case_id', 'cases', ['case_id'], unique=True)
    op.create_index('idx_cases_opportunity_id', 'cases', ['opportunity_id'], unique=True)

    # Create sales_orders table
    op.create_table('sales_orders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('so_number', sa.String(length=50), nullable=False),
        sa.Column('so_month', sa.String(length=7), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sales_orders_case_id', 'sales_orders', ['case_id'], unique=False)
    op.create_index('idx_sales_orders_so_month', 'sales_orders', ['so_month'], unique=False)
    op.create_index('idx_sales_orders_so_number', 'sales_orders', ['so_number'], unique=True)

    # Create documents table
    op.create_table('documents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('sales_order_id', sa.Integer(), nullable=True),
        sa.Column('document_type', sa.String(length=30), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('reference_number', sa.String(length=100), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=False),
        sa.Column('checksum', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('rotation', sa.Integer(), server_default='0', nullable=True),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('uploaded_by', sa.String(length=100), server_default='Anonymous', nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_documents_case_id', 'documents', ['case_id'], unique=False)
    op.create_index('idx_documents_document_type', 'documents', ['document_type'], unique=False)
    op.create_index('idx_documents_sales_order_id', 'documents', ['sales_order_id'], unique=False)

    # Create audit_logs table
    op.create_table('audit_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('sales_order_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sales_order_id'], ['sales_orders.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_audit_logs_case_id', 'audit_logs', ['case_id'], unique=False)
    op.create_index('idx_audit_logs_created_at', 'audit_logs', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_audit_logs_created_at', table_name='audit_logs')
    op.drop_index('idx_audit_logs_case_id', table_name='audit_logs')
    op.drop_table('audit_logs')
    
    op.drop_index('idx_documents_sales_order_id', table_name='documents')
    op.drop_index('idx_documents_document_type', table_name='documents')
    op.drop_index('idx_documents_case_id', table_name='documents')
    op.drop_table('documents')
    
    op.drop_index('idx_sales_orders_so_number', table_name='sales_orders')
    op.drop_index('idx_sales_orders_so_month', table_name='sales_orders')
    op.drop_index('idx_sales_orders_case_id', table_name='sales_orders')
    op.drop_table('sales_orders')
    
    op.drop_index('idx_cases_opportunity_id', table_name='cases')
    op.drop_index('idx_cases_case_id', table_name='cases')
    op.drop_table('cases')
