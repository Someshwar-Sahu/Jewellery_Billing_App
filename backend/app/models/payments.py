from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date, datetime

class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    party_id: int = Field(foreign_key="parties.id")
    payment_date: date
    amount: float
    mode: str
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CreditPayment(SQLModel,table=True):
    __tablename__ = "credit_payments"

    id: Optional[int] = Field(default=None, primary_key=True)
    invoice_id: int = Field(foreign_key="invoices.id")
    party_id: int = Field(foreign_key="parties.id")
    credit_date: date
    amount: float
    mode: str
    reference_no: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Advance(SQLModel, table=True):
    __tablename__ = "advances"

    id: Optional[int] = Field(default=None, primary_key=True)
    party_id: int = Field(foreign_key="parties.id")
    advance_date: date
    amount: float
    mode: str
    reference_no: Optional[str] = None
    adjusted_amount: float = 0.0
    status: str = "open"
    notes: Optional[str] = None

class CashAccount(SQLModel, table=True):
    __tablename__ = "cash_accounts"

    id: Optional[int] = Field(default=None, primary_key=True)
    entry_date: date = Field(index=True)
    entry_type: str                          
    mode: str                               
    amount: float
    reference_no: Optional[str] = None       
    party_id: Optional[int] = Field(default=None, foreign_key="parties.id")
    invoice_id: Optional[int] = Field(default=None, foreign_key="invoices.id")
    expense_id: Optional[int] = Field(default=None, foreign_key="expenses.id")
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)