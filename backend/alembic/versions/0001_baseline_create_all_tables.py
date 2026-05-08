"""baseline: create all tables

Revision ID: 0001_baseline
Revises: 
Create Date: 2026-05-07 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0001_baseline"
down_revision: Union[str, Sequence[str], None] = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    existing = sa.inspect(bind).get_table_names()

    if "users" not in existing:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("username", sa.String, nullable=False, unique=True),
            sa.Column("password_hash", sa.String, nullable=False),
            sa.Column("role", sa.String, nullable=False, server_default="owner"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "shop_settings" not in existing:
        op.create_table(
            "shop_settings",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("shop_name", sa.String, nullable=False),
            sa.Column("gstin", sa.String),
            sa.Column("address", sa.String),
            sa.Column("city", sa.String),
            sa.Column("state", sa.String, server_default="Uttar Pradesh"),
            sa.Column("state_code", sa.String, server_default="09"),
            sa.Column("phone", sa.String),
            sa.Column("email", sa.String),
            sa.Column("logo_url", sa.String),
            sa.Column("bill_prefix", sa.String, server_default="BILL/"),
            sa.Column("bill_template", sa.String, nullable=False, server_default="template_dad"),
            sa.Column("financial_year", sa.String),
            sa.Column("bank_name", sa.String),
            sa.Column("bank_account_no", sa.String),
            sa.Column("bank_ifsc", sa.String),
            sa.Column("terms_line1", sa.String),
            sa.Column("terms_line2", sa.String),
        )

    if "financial_years" not in existing:
        op.create_table(
            "financial_years",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("label", sa.String, nullable=False),
            sa.Column("start_date", sa.Date, nullable=False),
            sa.Column("end_date", sa.Date, nullable=False),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.UniqueConstraint("label", name="uq_financial_years_label"),
        )

    if "month_locks" not in existing:
        op.create_table(
            "month_locks",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("year", sa.Integer, nullable=False),
            sa.Column("month", sa.Integer, nullable=False),
            sa.Column("is_locked", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("locked_at", sa.DateTime),
            sa.Column("locked_by", sa.String),
            sa.UniqueConstraint("year", "month", name="uq_month_locks_year_month"),
        )

    if "app_alerts" not in existing:
        op.create_table(
            "app_alerts",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("type", sa.String, nullable=False),
            sa.Column("message", sa.String, nullable=False),
            sa.Column("show_from", sa.DateTime, nullable=False),
            sa.Column("show_until", sa.DateTime, nullable=False),
            sa.Column("dismissed_at", sa.DateTime),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        )

    if "parties" not in existing:
        op.create_table(
            "parties",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("phone", sa.String),
            sa.Column("email", sa.String),
            sa.Column("address", sa.String),
            sa.Column("city", sa.String),
            sa.Column("gstin", sa.String),
            sa.Column("party_type", sa.String, nullable=False, server_default="customer"),
            sa.Column("opening_balance", sa.Float, server_default="0.0"),
            sa.Column("balance_type", sa.String, server_default="receivable"),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "products" not in existing:
        op.create_table(
            "products",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("category", sa.String),
            sa.Column("hsn_code", sa.String, server_default="7113"),
            sa.Column("default_purity", sa.String),
            sa.Column("default_gst_rate", sa.Float, server_default="3.0"),
            sa.Column("low_stock_alert", sa.Float),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "gold_rates" not in existing:
        op.create_table(
            "gold_rates",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("rate_date", sa.Date, nullable=False),
            sa.Column("gold_22k_per_gram", sa.Float),
            sa.Column("gold_18k_per_gram", sa.Float),
            sa.Column("silver_per_gram", sa.Float),
            sa.Column("entered_by", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "invoices" not in existing:
        op.create_table(
            "invoices",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_number", sa.String, nullable=False, index=True),
            sa.Column("invoice_type", sa.String, nullable=False),
            sa.Column("bill_category", sa.String, nullable=False, server_default="cash"),
            sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=True),
            sa.Column("financial_year_id", sa.Integer, sa.ForeignKey("financial_years.id")),
            sa.Column("invoice_date", sa.Date, nullable=False, index=True),
            sa.Column("due_date", sa.Date),
            sa.Column("credit_due_date", sa.Date),
            sa.Column("place_of_supply", sa.String, server_default="Uttar Pradesh"),
            sa.Column("supply_type", sa.String, nullable=False, server_default="intrastate"),
            sa.Column("party_gstin", sa.String),
            sa.Column("subtotal", sa.Float, server_default="0.0"),
            sa.Column("total_cgst", sa.Float, server_default="0.0"),
            sa.Column("total_sgst", sa.Float, server_default="0.0"),
            sa.Column("total_igst", sa.Float, server_default="0.0"),
            sa.Column("total_making_charges", sa.Float, server_default="0.0"),
            sa.Column("making_cgst", sa.Float, server_default="0.0"),
            sa.Column("making_sgst", sa.Float, server_default="0.0"),
            sa.Column("old_gold_value", sa.Float, server_default="0.0"),
            sa.Column("discount", sa.Float, server_default="0.0"),
            sa.Column("round_off", sa.Float, server_default="0.0"),
            sa.Column("grand_total", sa.Float, server_default="0.0"),
            sa.Column("amount_paid", sa.Float, server_default="0.0"),
            sa.Column("amount_due", sa.Float, server_default="0.0"),
            sa.Column("payment_mode", sa.String),
            sa.Column("payment_status", sa.String, nullable=False, server_default="unpaid"),
            sa.Column("gst_status", sa.String, nullable=False, server_default="pending_review"),
            sa.Column("version_number", sa.Integer, nullable=False, server_default="1"),
            sa.Column("is_cancelled", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("cancelled_at", sa.DateTime),
            sa.Column("cancelled_reason", sa.String),
            sa.Column("ref_invoice_id", sa.Integer, sa.ForeignKey("invoices.id")),
            sa.Column("notes", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("updated_at", sa.DateTime, nullable=False),
            sa.UniqueConstraint("invoice_number", name="uq_invoices_invoice_number"),
        )

    if "invoice_items" not in existing:
        op.create_table(
            "invoice_items",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")),
            sa.Column("item_name", sa.String, nullable=False),
            sa.Column("hsn_code", sa.String, server_default="7113"),
            sa.Column("purity", sa.String),
            sa.Column("huid", sa.String),
            sa.Column("weight_grams", sa.Float),
            sa.Column("rate_per_gram", sa.Float),
            sa.Column("quantity", sa.Float, server_default="1.0"),
            sa.Column("unit", sa.String, server_default="grams"),
            sa.Column("amount", sa.Float, server_default="0.0"),
            sa.Column("making_charges", sa.Float),
            sa.Column("making_gst_rate", sa.Float, server_default="18.0"),
            sa.Column("making_cgst", sa.Float, server_default="0.0"),
            sa.Column("making_sgst", sa.Float, server_default="0.0"),
            sa.Column("gst_rate", sa.Float, server_default="3.0"),
            sa.Column("cgst_amount", sa.Float, server_default="0.0"),
            sa.Column("sgst_amount", sa.Float, server_default="0.0"),
            sa.Column("igst_amount", sa.Float, server_default="0.0"),
            sa.Column("line_total", sa.Float, server_default="0.0"),
            sa.Column("sort_order", sa.Integer, server_default="0"),
            sa.Column("description", sa.String),
        )

    if "invoice_versions" not in existing:
        op.create_table(
            "invoice_versions",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("version_number", sa.Integer, nullable=False),
            sa.Column("snapshot", sa.String, nullable=False),
            sa.Column("saved_at", sa.DateTime, nullable=False),
            sa.Column("saved_by", sa.String),
        )

    if "invoice_edit_logs" not in existing:
        op.create_table(
            "invoice_edit_logs",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("field_changed", sa.String),
            sa.Column("old_value", sa.String),
            sa.Column("new_value", sa.String),
            sa.Column("reason", sa.String),
            sa.Column("edited_at", sa.DateTime, nullable=False),
        )

    if "stock_ledger" not in existing:
        op.create_table(
            "stock_ledger",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
            sa.Column("stock_date", sa.Date, nullable=False),
            sa.Column("transaction_type", sa.String, nullable=False),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id")),
            sa.Column("quantity_in", sa.Float, server_default="0.0"),
            sa.Column("quantity_out", sa.Float, server_default="0.0"),
            sa.Column("balance", sa.Float, server_default="0.0"),
            sa.Column("rate", sa.Float),
            sa.Column("notes", sa.String),
        )

    if "expense_categories" not in existing:
        op.create_table(
            "expense_categories",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("name", sa.String, nullable=False),
            sa.Column("is_itc_eligible", sa.Boolean, nullable=False, server_default=sa.false()),
        )

    if "expenses" not in existing:
        op.create_table(
            "expenses",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("category_id", sa.Integer, sa.ForeignKey("expense_categories.id"), nullable=False),
            sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id")),
            sa.Column("expense_date", sa.Date, nullable=False, index=True),
            sa.Column("description", sa.String),
            sa.Column("amount", sa.Float, nullable=False),
            sa.Column("gst_amount", sa.Float, server_default="0.0"),
            sa.Column("itc_claimable", sa.Float, server_default="0.0"),
            sa.Column("payment_mode", sa.String),
            sa.Column("reference_no", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
            sa.Column("is_deleted", sa.Boolean, nullable=False, server_default=sa.false()),
            sa.Column("deleted_at", sa.DateTime),
        )

    if "advances" not in existing:
        op.create_table(
            "advances",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id"), nullable=False),
            sa.Column("advance_date", sa.Date, nullable=False),
            sa.Column("amount", sa.Float, nullable=False),
            sa.Column("adjusted_amount", sa.Float, server_default="0.0"),
            sa.Column("status", sa.String, server_default="open"),
            sa.Column("notes", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "credit_payments" not in existing:
        op.create_table(
            "credit_payments",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("invoice_id", sa.Integer, sa.ForeignKey("invoices.id"), nullable=False),
            sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id")),
            sa.Column("credit_date", sa.Date, nullable=False),
            sa.Column("amount", sa.Float, nullable=False),
            sa.Column("mode", sa.String),
            sa.Column("reference_no", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )

    if "old_gold_exchanges" not in existing:
        op.create_table(
            "old_gold_exchanges",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("party_id", sa.Integer, sa.ForeignKey("parties.id")),
            sa.Column("sale_invoice_id", sa.Integer, sa.ForeignKey("invoices.id")),
            sa.Column("exchange_date", sa.Date, nullable=False),
            sa.Column("transaction_type", sa.String, nullable=False),
            sa.Column("metal_type", sa.String, nullable=False),
            sa.Column("purity", sa.String),
            sa.Column("weight_grams", sa.Float, nullable=False),
            sa.Column("rate_per_gram", sa.Float),
            sa.Column("total_value", sa.Float, nullable=False),
            sa.Column("notes", sa.String),
            sa.Column("created_at", sa.DateTime, nullable=False),
        )


def downgrade() -> None:
    # Drop in reverse FK order
    op.drop_table("old_gold_exchanges")
    op.drop_table("credit_payments")
    op.drop_table("advances")
    op.drop_table("expenses")
    op.drop_table("expense_categories")
    op.drop_table("stock_ledger")
    op.drop_table("invoice_edit_logs")
    op.drop_table("invoice_versions")
    op.drop_table("invoice_items")
    op.drop_table("invoices")
    op.drop_table("gold_rates")
    op.drop_table("products")
    op.drop_table("parties")
    op.drop_table("app_alerts")
    op.drop_table("month_locks")
    op.drop_table("financial_years")
    op.drop_table("shop_settings")
    op.drop_table("users")