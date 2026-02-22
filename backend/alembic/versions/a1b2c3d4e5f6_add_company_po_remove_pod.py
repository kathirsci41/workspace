"""add COMPANY_PO, remove POD from documenttype enum

Revision ID: a1b2c3d4e5f6
Revises: 6e44882e6975
Create Date: 2026-02-21 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6e44882e6975'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete any existing POD documents so the enum value can be removed
    op.execute("DELETE FROM reference_index WHERE document_type::text = 'POD'")
    op.execute("DELETE FROM document_metadata WHERE document_type::text = 'POD'")
    op.execute("DELETE FROM documents WHERE document_type::text = 'POD'")

    # Create the new enum with COMPANY_PO and without POD
    op.execute("""
        CREATE TYPE documenttype_new AS ENUM (
            'CUSTOMER_PO', 'COMPANY_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
            'COMPANY_DC', 'COMPANY_INVOICE'
        )
    """)

    # Migrate all three tables to the new enum
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN document_type TYPE documenttype_new
        USING document_type::text::documenttype_new
    """)
    op.execute("""
        ALTER TABLE document_metadata
        ALTER COLUMN document_type TYPE documenttype_new
        USING document_type::text::documenttype_new
    """)
    op.execute("""
        ALTER TABLE reference_index
        ALTER COLUMN document_type TYPE documenttype_new
        USING document_type::text::documenttype_new
    """)

    # Replace old enum
    op.execute("DROP TYPE documenttype")
    op.execute("ALTER TYPE documenttype_new RENAME TO documenttype")


def downgrade() -> None:
    # Remove any COMPANY_PO documents
    op.execute("DELETE FROM reference_index WHERE document_type::text = 'COMPANY_PO'")
    op.execute("DELETE FROM document_metadata WHERE document_type::text = 'COMPANY_PO'")
    op.execute("DELETE FROM documents WHERE document_type::text = 'COMPANY_PO'")

    op.execute("""
        CREATE TYPE documenttype_old AS ENUM (
            'CUSTOMER_PO', 'VENDOR_DC', 'VENDOR_INVOICE',
            'COMPANY_DC', 'COMPANY_INVOICE', 'POD'
        )
    """)
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN document_type TYPE documenttype_old
        USING document_type::text::documenttype_old
    """)
    op.execute("""
        ALTER TABLE document_metadata
        ALTER COLUMN document_type TYPE documenttype_old
        USING document_type::text::documenttype_old
    """)
    op.execute("""
        ALTER TABLE reference_index
        ALTER COLUMN document_type TYPE documenttype_old
        USING document_type::text::documenttype_old
    """)
    op.execute("DROP TYPE documenttype")
    op.execute("ALTER TYPE documenttype_old RENAME TO documenttype")
