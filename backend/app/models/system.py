from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime, date

class MonthLock(SQLModel, table=True):
    __tablename__ = "month_locks"

    id: Optional[int] = Field(default=None, primary_key=True)
    year: int
    month: int
    is_locked: bool = False
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None

class AppAlert(SQLModel, table=True):
    __tablename__ = "app_alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    message: str
    show_from: datetime
    show_until: datetime
    dismissed_at: Optional[datetime] = None
    is_active: bool = True