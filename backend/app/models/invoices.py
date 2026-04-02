from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date, datetime

class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_number: str = Field(index=True)
    invoice_type: str
    bill_category: str = "cash"
    party_id: Optional[int] = Field(default=None, foreign_key="parties.id")
    financial_year_id: Optional[int] = Field(default=None, foreign_key="financial_years.id")
    invoice_date: date = Field(index=True)
    due_date: Optional[date] = None
    credit_due_date: Optional[date] = None
    place_of_supply: Optional[str] = "Uttar Pradesh"
    supply_type: str = "intrastate"
    party_gstin: Optional[str] = None

    subtotal: float = 0.0
    total_cgst: float = 0.0
    total_sgst: float = 0.0
    total_igst: float = 0.0
    total_making_charges: float = 0.0
    making_cgst: float = 0.0
    making_sgst: float = 0.0
    old_gold_value: float = 0.0
    discount: float = 0.0
    round_off: float = 0.0
    grand_total: float = 0.0
    amount_paid: float = 0.0
    amount_due: float = 0.0

    payment_mode: Optional[str] = None
    payment_status: str = "unpaid"

    gst_status: str = "pending_review"

    version_number: int = 1

    is_cancelled: bool = False
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None

    ref_invoice_id: Optional[int] = Field(default=None, foreign_key="invoices.id")

    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class InvoiceItem(SQLModel, table=True):
    __tablename__ = "invoice_items"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    product_id: Optional[int] = Field(default=None, foreign_key="products.id")

    item_name: str
    hsn_code: str = "7113"
    purity: Optional[str] = None
    huid: Optional[str] = None
    weight_grams: Optional[float] = None
    rate_per_gram: Optional[float] = None
    quantity: float = 1.0
    unit: str = "grams"
    amount: float = 0.0

    making_charges: Optional[float] = None
    making_gst_rate: float = 18.0
    making_cgst: float = 0.0
    making_sgst: float = 0.0

    gst_rate: float = 3.0
    cgst_amount: float = 0.0
    sgst_amount: float = 0.0
    igst_amount: float = 0.0

    line_total: float = 0.0
    sort_order: int = 0
    description: Optional[str] = None

class InvoiceVersion(SQLModel, table=True):
    __tablename__ = "invoice_versions"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    version_number: int
    snapshot: str
    saved_at: datetime = Field(default_factory=datetime.utcnow)
    saved_by: Optional[str] = None

class InvoiceEditLog(SQLModel, table=True):
    __tablename__ = "invoice_edit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    edited_at: datetime = Field(default_factory=datetime.utcnow)
    field_changed: str
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    edited_by: Optional[str] = None