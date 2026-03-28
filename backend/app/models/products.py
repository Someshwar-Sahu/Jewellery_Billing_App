from sqlmodel import SQLModel, Field
from typing import Optional

class ProductGroup(SQLModel, table=True):
    __tablename__ = "product_groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    parent_id: Optional[int] = Field(default=None, foreign_key="product_groups.id")

class Unit(SQLModel, table=True):
    __tablename__ = "units"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    symbol: str

class Product(SQLModel, table=True):
    __tablename__ = "products"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    group_id: Optional[int] = Field(default=None, foreign_key="product_groups.id")
    unit_id: Optional[int] = Field(default=None, foreign_key="units.id")
    hsn_code: str = "7113"
    purity: Optional[str] = None
    metal_type: str = "gold"
    gst_rate: float = 3.0
    making_charge_rate: Optional[float] = None
    huid: Optional[str] = None
    current_stock: Optional[float] = None
    low_stock_alert: Optional[float] = None
    description: Optional[str] = None
    is_active: bool = True