from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class ShopSettings(SQLModel, table=True):
    __tablename__ = "shop_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    shop_name: str
    gstin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = "Uttar Pradesh"
    state_code: Optional[str] = "09"
    phone: Optional[str] = None
    email: Optional[str] = None
    logo_url: Optional[str] = None
    bill_prefix: Optional[str] = "BILL/"
    bill_template: str = "template_1"
    financial_year: Optional[str] = None

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = "owner"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
class FinancialYear(SQLModel, table=True):
    __tablename__ = "financial_years"

    id: Optional[int] = Field(default=None, primary_key=True)
    label: str
    start_date: str
    end_date: str
    is_active: bool = False