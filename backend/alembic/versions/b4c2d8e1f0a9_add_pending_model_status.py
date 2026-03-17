"""add_pending_model_status

Revision ID: b4c2d8e1f0a9
Revises: a3f1c9b2e7d4
Create Date: 2026-03-16 00:00:00.000000

Adds PENDING_MODEL to the documentstatus enum.
PENDING_MODEL means the document is valid but the required AI models were not
available on the configured endpoint at the time of the extraction attempt.
These documents are held and can be re-queued via POST /admin/requeue-pending-models.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b4c2d8e1f0a9'
down_revision: Union[str, None] = 'a3f1c9b2e7d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # PostgreSQL allows adding enum values directly; IF NOT EXISTS prevents
    # errors on re-runs (e.g., if the migration is applied twice by accident).
    op.execute("ALTER TYPE documentstatus ADD VALUE IF NOT EXISTS 'PENDING_MODEL'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values without recreating the
    # type. The safest downgrade is to reclassify any PENDING_MODEL documents
    # as EXTRACTION_FAILED, then recreate the enum without the new value.
    op.execute("""
        UPDATE documents
        SET status = 'EXTRACTION_FAILED'
        WHERE status = 'PENDING_MODEL'
    """)

    # Recreate the enum type without PENDING_MODEL
    op.execute("ALTER TYPE documentstatus RENAME TO documentstatus_old")
    op.execute("""
        CREATE TYPE documentstatus AS ENUM (
            'UPLOADED',
            'EXTRACTING',
            'PENDING_REVIEW',
            'VERIFIED',
            'REJECTED',
            'EXTRACTION_FAILED'
        )
    """)
    op.execute("""
        ALTER TABLE documents
        ALTER COLUMN status TYPE documentstatus
        USING status::text::documentstatus
    """)
    op.execute("DROP TYPE documentstatus_old")
