"""financial year date safety and unique constraints

Revision ID: 9f3a2d1b7c44
Revises: 321e22c937d5
Create Date: 2026-05-07 18:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f3a2d1b7c44"
down_revision: Union[str, Sequence[str], None] = "321e22c937d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    op.execute("UPDATE financial_years SET start_date = NULL WHERE start_date = ''")
    op.execute("UPDATE financial_years SET end_date = NULL WHERE end_date = ''")

    with op.batch_alter_table("financial_years", schema=None) as batch_op:
        if dialect == "postgresql":
            batch_op.alter_column(
                "start_date",
                existing_type=sa.String(),
                type_=sa.Date(),
                postgresql_using="start_date::date",
                nullable=False,
            )
            batch_op.alter_column(
                "end_date",
                existing_type=sa.String(),
                type_=sa.Date(),
                postgresql_using="end_date::date",
                nullable=False,
            )
        else:
            batch_op.alter_column("start_date", existing_type=sa.String(), type_=sa.Date(), nullable=False)
            batch_op.alter_column("end_date", existing_type=sa.String(), type_=sa.Date(), nullable=False)
        batch_op.create_unique_constraint("uq_financial_years_label", ["label"])

    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_invoices_invoice_number", ["invoice_number"])

    with op.batch_alter_table("month_locks", schema=None) as batch_op:
        batch_op.create_unique_constraint("uq_month_locks_year_month", ["year", "month"])


def downgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    with op.batch_alter_table("month_locks", schema=None) as batch_op:
        batch_op.drop_constraint("uq_month_locks_year_month", type_="unique")

    with op.batch_alter_table("invoices", schema=None) as batch_op:
        batch_op.drop_constraint("uq_invoices_invoice_number", type_="unique")

    with op.batch_alter_table("financial_years", schema=None) as batch_op:
        batch_op.drop_constraint("uq_financial_years_label", type_="unique")
        if dialect == "postgresql":
            batch_op.alter_column(
                "end_date",
                existing_type=sa.Date(),
                type_=sa.String(),
                postgresql_using="end_date::text",
                nullable=False,
            )
            batch_op.alter_column(
                "start_date",
                existing_type=sa.Date(),
                type_=sa.String(),
                postgresql_using="start_date::text",
                nullable=False,
            )
        else:
            batch_op.alter_column("end_date", existing_type=sa.Date(), type_=sa.String(), nullable=False)
            batch_op.alter_column("start_date", existing_type=sa.Date(), type_=sa.String(), nullable=False)
