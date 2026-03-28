from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, date

class ExpenseCategory(SQLModel, table=True):
    __tablename__ = "expense_categories"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str              
    is_itc_eligible: bool = False

class Expense(SQLModel, table= True):
    __tablename__ = "expenses"

    id: Optional[int] = Field(default=None, primary_key=True)
    category_id: int = Field(foreign_key="expense_categories.id")
    party_id: Optional[int] = Field(default=None, foreign_key="parties.id")
    expense_date: date = Field(index=True)
    description: Optional[str] = None
    amount: float
    gst_amount: float = 0.0
    itc_claimable: float = 0.0
    payment_mode: Optional[str] = None
    reference_no: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)