from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class AppAlert(SQLModel, table=True):
    __tablename__ = "app_alerts"

    id: Optional[int] = Field(default=None, primary_key=True)
    type: str
    message: str
    show_from: datetime
    show_until: datetime
    dismissed_at: Optional[datetime] = None
    is_active: bool = True