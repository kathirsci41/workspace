"""add_performance_indexes

Revision ID: c5d3e9f2a1b8
Revises: b4c2d8e1f0a9
Create Date: 2026-03-20 00:00:00.000000

Adds index on documents.status — the most-filtered column in all list/count queries.
Note: ix_doc_po_id on documents.po_id already exists from the initial schema.

Read-only addition. No data is modified. Safe to apply on a live DB.
"""
from alembic import op

revision = 'c5d3e9f2a1b8'
down_revision = 'b4c2d8e1f0a9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index('idx_document_status', 'documents', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_document_status', table_name='documents')
