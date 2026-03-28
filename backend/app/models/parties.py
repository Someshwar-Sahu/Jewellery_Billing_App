from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date, datetime

class Party(SQLModel, table=True):
    __tablename__ = "parties"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    type: str                           # customer / supplier / both
    name: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    gstin: Optional[str] = None
    gstin_verified: bool = False
    gstin_status: Optional[str] = None  # active / cancelled / pending
    business_type: Optional[str] = None # fixed typo: bussiness -> business
    credit_limit: Optional[float] = None
    credit_days: Optional[int] = None
    opening_balance: Optional[float] = None
    opening_balance_type: Optional[str] = None  # debit / credit
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OldGoldExchange(SQLModel, table=True):
    __tablename__ = "old_gold_exchanges"

    id: Optional[int] = Field(default=None, primary_key=True)
    party_id: int = Field(foreign_key="parties.id")
    sale_invoice_id: Optional[int] = Field(default=None, foreign_key="invoices.id")
    exchange_date: date                 # renamed from date to avoid conflict with date type
    transaction_type: str = "exchange"  # exchange (part of sale) / direct_purchase (cash to customer)
    metal_type: str = "gold"            # gold / silver
    purity: Optional[str] = None        # 22K, 18K, 925, 999 etc
    weight_grams: float
    rate_per_gram: float
    total_value: float
    cash_paid: Optional[float] = None   # for direct_purchase — how much cash dad paid
    notes: Optional[str] = None