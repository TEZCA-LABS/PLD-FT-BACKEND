"""enable_pg_trgm_extension

Revision ID: 7a9d1c4e2b11
Revises: f1b2c3d4e5f6
Create Date: 2026-04-06 00:00:00.000000
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "7a9d1c4e2b11"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
