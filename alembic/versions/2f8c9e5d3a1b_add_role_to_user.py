"""Add role column to user table

Revision ID: 2f8c9e5d3a1b
Revises: 9c5d3e2a1b0f
Create Date: 2026-02-20 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2f8c9e5d3a1b'
down_revision = '9c5d3e2a1b0f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add role column with default value "consultant"
    op.add_column('user', sa.Column('role', sa.String(), nullable=True, server_default='consultant'))
    op.create_index(op.f('ix_user_role'), 'user', ['role'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_role'), table_name='user')
    op.drop_column('user', 'role')
