"""add is_closed to financial_years

Revision ID: b2e4f8a1c903
Revises: a1c7d9e8f102
Create Date: 2026-05-08 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "b2e4f8a1c903"
down_revision: Union[str, Sequence[str], None] = "a1c7d9e8f102"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("financial_years", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("financial_years", schema=None) as batch_op:
        batch_op.drop_column("is_closed")