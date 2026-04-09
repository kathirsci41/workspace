"""add_pg_trgm_fuzzy_index

Revision ID: g9h0i1j2k3l4
Revises: f7a8b9c0d1e2
Create Date: 2026-04-08

Enables pg_trgm extension and adds GIN index on reference_index.ref_value
for similarity-based fuzzy search. Safe to apply on a live DB — read-only
addition, no data is modified.
"""
from alembic import op

revision = 'g9h0i1j2k3l4'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable trigram extension (requires superuser on first run, safe to re-run)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    # GIN index for fast similarity queries on ref_value
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_ref_value_trgm "
        "ON reference_index USING GIN (ref_value gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_ref_value_trgm")
    # Note: do NOT drop the pg_trgm extension — other parts of the DB may depend on it
