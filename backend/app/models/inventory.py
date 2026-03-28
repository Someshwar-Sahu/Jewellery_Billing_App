from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, date

class GoldRate(SQLModel, table=True):
    __tablename__ = "gold_rates"

    id: Optional[int] = Field(default=None, primary_key=True)
    rate_date: date
    gold_22k_per_gram: Optional[float] = None
    gold_18k_per_gram: Optional[float] = None
    silver_per_gram: Optional[float] = None
    entered_by: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class StockLedger(SQLModel, table=True):
    __tablename__ = "stock_ledger"

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="products.id")
    stock_date: date
    transaction_type: str  
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoices.id")
    quantity_in: float = 0.0
    quantity_out: float = 0.0
    balance: float = 0.0
    rate: Optional[float] = None
    notes: Optional[str] = None