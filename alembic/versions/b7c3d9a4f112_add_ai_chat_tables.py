"""add_ai_chat_tables

Revision ID: b7c3d9a4f112
Revises: 21b492ac9cdf
Create Date: 2026-02-19 22:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c3d9a4f112'
down_revision = '21b492ac9cdf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ai_chat_session',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('initial_context', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_chat_session_id'), 'ai_chat_session', ['id'], unique=False)
    op.create_index(op.f('ix_ai_chat_session_user_id'), 'ai_chat_session', ['user_id'], unique=False)
    op.create_index(op.f('ix_ai_chat_session_status'), 'ai_chat_session', ['status'], unique=False)

    op.create_table(
        'ai_chat_message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('context', sa.JSON(), nullable=True),
        sa.Column('usage', sa.JSON(), nullable=True),
        sa.Column('model_version', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['ai_chat_session.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_chat_message_id'), 'ai_chat_message', ['id'], unique=False)
    op.create_index(op.f('ix_ai_chat_message_session_id'), 'ai_chat_message', ['session_id'], unique=False)
    op.create_index(op.f('ix_ai_chat_message_role'), 'ai_chat_message', ['role'], unique=False)

    op.create_table(
        'ai_chat_attachment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(), nullable=False),
        sa.Column('mime_type', sa.String(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('storage_path', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['ai_chat_session.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ai_chat_attachment_id'), 'ai_chat_attachment', ['id'], unique=False)
    op.create_index(op.f('ix_ai_chat_attachment_session_id'), 'ai_chat_attachment', ['session_id'], unique=False)
    op.create_index(op.f('ix_ai_chat_attachment_status'), 'ai_chat_attachment', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_ai_chat_attachment_status'), table_name='ai_chat_attachment')
    op.drop_index(op.f('ix_ai_chat_attachment_session_id'), table_name='ai_chat_attachment')
    op.drop_index(op.f('ix_ai_chat_attachment_id'), table_name='ai_chat_attachment')
    op.drop_table('ai_chat_attachment')

    op.drop_index(op.f('ix_ai_chat_message_role'), table_name='ai_chat_message')
    op.drop_index(op.f('ix_ai_chat_message_session_id'), table_name='ai_chat_message')
    op.drop_index(op.f('ix_ai_chat_message_id'), table_name='ai_chat_message')
    op.drop_table('ai_chat_message')

    op.drop_index(op.f('ix_ai_chat_session_status'), table_name='ai_chat_session')
    op.drop_index(op.f('ix_ai_chat_session_user_id'), table_name='ai_chat_session')
    op.drop_index(op.f('ix_ai_chat_session_id'), table_name='ai_chat_session')
    op.drop_table('ai_chat_session')
