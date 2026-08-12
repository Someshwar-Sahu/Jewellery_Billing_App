"""payment_events_and_advance_applications

Revision ID: c1f3a2b8d947
Revises: b2e4f8a1c903
Create Date: 2026-06-12
"""
from typing import Union, Sequence
from alembic import op
import sqlalchemy as sa

revision: str = "c1f3a2b8d947"
down_revision: Union[str, Sequence[str], None] = "b2e4f8a1c903"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "advance_applications",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("advance_id", sa.Integer, sa.ForeignKey("advances.id"), nullable=False, index=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("amount_applied", sa.Float, nullable=False),
        sa.Column("applied_date", sa.Date, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "payment_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False, index=True),
        sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=True),
        sa.Column("event_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("payment_type", sa.String, nullable=False),
        sa.Column("reference_no", sa.String, nullable=True),
        sa.Column("advance_application_id", sa.Integer, sa.ForeignKey("advance_applications.id"), nullable=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.add_column("invoices", sa.Column("advance_used", sa.Float, nullable=False, server_default="0.0"))

    op.drop_table("credit_payments")
    op.drop_table("payments")


def downgrade():
    op.create_table(
        "payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("payment_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("reference_no", sa.String, nullable=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "credit_payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
        sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=False),
        sa.Column("credit_date", sa.Date, nullable=False),
        sa.Column("amount", sa.Float, nullable=False),
        sa.Column("mode", sa.String, nullable=False),
        sa.Column("reference_no", sa.String, nullable=True),
        sa.Column("notes", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.drop_column("invoices", "advance_used")
    op.drop_table("payment_events")
    op.drop_table("advance_applications")