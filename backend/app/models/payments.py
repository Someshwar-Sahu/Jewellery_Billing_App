from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import date, datetime

class AdvanceApplication(SQLModel, table=True):
    __tablename__ = 'advance_applications'

    id: Optional[int] = Field(default=None, primary_key=True)
    advance_id: int = Field(foreign_key="advances.id", index=True)
    invoice_id: int = Field(foreign_key="invoices.id", index=True)
    party_id: int = Field(foreign_key="parties.id")
    amount_applied: float
    applied_date: date
    created_at: datetime = Field(default_factory=datetime.utcnow)

class PaymentEvent(SQLModel, table=True):
    __tablename__ = 'payment_events'

    id: Optional[int] = Field(default=None, primary_key= True)
    invoice_id: Optional[int] = Field(default=None, foreign_key='invoices.id', index=True)
    party_id: Optional[int] = Field(default=None, foreign_key='parties.id')
    event_date: date
    amount: float
    mode: str
    payment_type: str
    reference_no: Optional[str] = None
    advance_application_id: Optional[int] = Field(default=None, foreign_key="advance_applications.id")
    notes: Optional[str]
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