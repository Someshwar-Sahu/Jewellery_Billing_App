from pydantic import BaseModel, field_validator, model_validator
from typing import Optional, List
from datetime import date
from enum import Enum

class InvoiceType(str,Enum):
    sale = "sale"
    purchase = "purchase"
    credit_note = "credit_note"
    debit_note = "debit_note"

class BillCategory(str, Enum):
    cash = "cash"
    credit = "credit"

class PaymentMode(str, Enum):
    cash = "cash"
    upi = "upi"
    cheque = "cheque"
    card = "card"
    mixed = "mixed"
    neft = "neft"
    rtgs = "rtgs"

class MetalType(str, Enum):
    gold = "gold"
    silver = "silver"
    other = "other"

class InvoiceItemCreate(BaseModel):
    item_name: str
    product_id: Optional[int] = None
    hsn_code: Optional[str] = "7113"
    purity: Optional[str] = None
    huid: Optional[str] = None
    weight_grams: Optional[float] = None
    rate_per_gram: Optional[float] = None
    quantity: Optional[float] = 1.0
    unit: str = "grams"
    making_charges: Optional[float] = None
    gst_rate: float = 3.0
    description: Optional[str] = None
    sort_order: int = 0

    @field_validator('gst_rate')
    @classmethod
    def gst_rate_valid(cls, v):
        if v not in [0, 0.25, 1.5, 3.0, 5.0, 12.0, 18.0, 28.0]:
            raise ValueError('GST rate must be a valid GST slab.')
        return v
    
    @field_validator("weight_grams", "rate_per_gram", "quantity")
    @classmethod
    def mut_be_positive(cls, v):
        if v is not None and v < 0:
            raise ValueError("Value cannot be negative.")
        return v
    
    @model_validator(mode="after")
    def item_must_have_value(self):
        has_amount = (self.weight_grams or 0) > 0 and (self.rate_per_gram or 0) > 0
        has_making = (self.making_charges or 0) > 0
        if not has_amount and not has_making:
            raise ValueError("Item must have either weight+rate or making charges.")
        return self

class InvoiceItemRead(InvoiceItemCreate):
    id: int
    invoice_id: int
    amount: float
    cgst_amount: float
    sgst_amount: float
    igst_amount: float
    making_cgst: float
    making_sgst: float
    line_total: float

class InvoiceCreate(BaseModel):
    invoice_type: InvoiceType = InvoiceType.sale
    bill_category: BillCategory = BillCategory.cash
    party_id: Optional[int] = None  # None allowed — walk-in customer handled in router
    invoice_date: date
    credit_due_date: Optional[date] = None
    place_of_supply: Optional[str] = "Uttar Pradesh"
    party_gstin: Optional[str] = None
    payment_mode: Optional[PaymentMode] = None
    amount_paid: Optional[float] = 0.0
    advance_used: Optional[float] = 0.0
    old_gold_value: float = 0.0
    old_gold_metal_type: MetalType = MetalType.gold
    old_gold_purity: Optional[str] = None
    old_gold_weight: Optional[float] = None
    old_gold_rate: Optional[float] = None
    discount: float = 0.0
    notes: Optional[str] = None
    ref_invoice_id: Optional[int] = None
    items: List[InvoiceItemCreate]

    @field_validator("items")
    @classmethod
    def must_have_items(cls, v):
        if not v:
            raise ValueError("Invoice must have at least one item.")
        return v
    
    @model_validator(mode="after")
    def credit_need_due_date(self):
        if self.bill_category == BillCategory.credit and self.credit_due_date is None:
            raise ValueError("Credit invoices must have a due date.")
        if self.credit_due_date and self.invoice_date and self.credit_due_date < self.invoice_date:
            raise ValueError("Due date cannot be before invoice date.")
        return self
    
    @field_validator("amount_paid")
    @classmethod
    def amount_paid_valid(cls, v):
        if v is not None and v < 0:
            raise ValueError("Amount paid cannot be negative.")
        return v

    @field_validator("advance_used")
    @classmethod
    def advance_used_valid(cls, v):
        if v is not None and v < 0:
            raise ValueError("Advance used cannot be negative.")
        return v
    
    @field_validator("old_gold_value", "discount")
    @classmethod
    def deductions_not_negative(cls, v):
        if v is not None and v < 0:
            raise ValueError("Deductions cannot be negative.")
        return v
    
    @field_validator("invoice_date")
    @classmethod
    def date_not_too_far_future(cls, v):
        from datetime import date
        if v > date.today().replace(year=date.today().year + 1):
            raise ValueError("Invoice date cannot be more than 1 year in the future.")
        return v

class InvoiceUpdate(BaseModel):
    invoice_date: Optional[date] = None
    credit_due_date: Optional[date] = None
    payment_mode: Optional[PaymentMode] = None
    amount_paid: Optional[float] = None
    old_gold_value: Optional[float] = None
    discount: Optional[float] = None
    notes: Optional[str] = None
    items: Optional[List[InvoiceItemCreate]] = None
    edit_reason: Optional[str] = None

class InvoiceRead(BaseModel):
    id:int
    invoice_number: str
    invoice_type: str
    bill_category: str
    party_id: int
    invoice_date: date
    credit_due_date: Optional[date] = None
    subtotal: float
    total_cgst: float
    total_sgst: float
    total_making_charges: float
    making_cgst: float
    making_sgst: float
    old_gold_value: float
    discount: float
    round_off: float
    grand_total: float
    amount_paid: float
    amount_due: float
    payment_mode: Optional[str] = None
    payment_status: str
    gst_status: str
    is_cancelled: bool
    notes: Optional[str] = None
    items: List[InvoiceItemRead] = []

    class Config:
        from_attributes = True