"""Add missing sanction columns (profile_id, rfc) and entity_profile table

Revision ID: 9c5d3e2a1b0f
Revises: b7c3d9a4f112
Create Date: 2026-02-20 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid


# revision identifiers, used by Alembic.
revision = '9c5d3e2a1b0f'
down_revision = 'b7c3d9a4f112'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create entity_profile table if it doesn't exist
    op.create_table(
        'entity_profile',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('primary_name', sa.String(), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    )
    
    # Add profile_id column with FK to entity_profile
    op.add_column('sanction', sa.Column('profile_id', UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_sanction_profile_id', 'sanction', 'entity_profile', ['profile_id'], ['id'])
    op.create_index(op.f('ix_sanction_profile_id'), 'sanction', ['profile_id'], unique=False)
    
    # Add rfc column
    op.add_column('sanction', sa.Column('rfc', sa.String(), nullable=True))
    op.create_index(op.f('ix_sanction_rfc'), 'sanction', ['rfc'], unique=False)
    
    # Add nationality column if missing
    if not column_exists('sanction', 'nationality'):
        op.add_column('sanction', sa.Column('nationality', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_index(op.f('ix_sanction_rfc'), table_name='sanction')
    op.drop_column('sanction', 'rfc')
    op.drop_index(op.f('ix_sanction_profile_id'), table_name='sanction')
    op.drop_constraint('fk_sanction_profile_id', 'sanction', type_='foreignkey')
    op.drop_column('sanction', 'profile_id')
    if column_exists('sanction', 'nationality'):
        op.drop_column('sanction', 'nationality')
    op.drop_table('entity_profile')


def column_exists(table_name, column_name):
    """Helper function to check if column exists"""
    ctx = op.get_context()
    insp = sa.inspect(ctx.bind)
    columns = [c['name'] for c in insp.get_columns(table_name)]
    return column_name in columns

