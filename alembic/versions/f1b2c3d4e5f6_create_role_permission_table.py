"""create_role_permission_table

Revision ID: f1b2c3d4e5f6
Revises: d4a7f3c2e9b1
Create Date: 2026-03-21 12:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f1b2c3d4e5f6"
down_revision = "d4a7f3c2e9b1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "role_permission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("permission_id", sa.String(), nullable=False),
        sa.Column("module", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("allowed_roles", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("permission_id"),
    )
    op.create_index(op.f("ix_role_permission_id"), "role_permission", ["id"], unique=False)
    op.create_index(
        op.f("ix_role_permission_permission_id"),
        "role_permission",
        ["permission_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_role_permission_permission_id"), table_name="role_permission")
    op.drop_index(op.f("ix_role_permission_id"), table_name="role_permission")
    op.drop_table("role_permission")
