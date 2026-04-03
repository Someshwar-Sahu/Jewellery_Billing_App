from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime
import re

class PartyCreate(BaseModel):
    type: str                               # customer / supplier / both
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    gstin: Optional[str] = None
    credit_limit: Optional[float] = None
    credit_days: Optional[int] = None
    opening_balance: Optional[float] = None
    opening_balance_type: Optional[str] = None  # debit / credit
    notes: Optional[str] = None

    @field_validator("type")
    @classmethod
    def type_valid(cls, v):
        if v not in ["customer", "supplier", "both"]:
            raise ValueError("Type must be customer, supplier, or both")
        return v

    @field_validator("gstin")
    @classmethod
    def gstin_format(cls, v):
        if v and v.strip():
            v = v.strip().upper()
            # GSTIN: 15 chars — 2 digit state code + 10 char PAN + 1 entity + Z + 1 checksum
            if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$", v):
                raise ValueError("Invalid GSTIN format. Example: 09ABCDE1234F1Z5")
            return v
        return None


class PartyUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    gstin: Optional[str] = None
    credit_limit: Optional[float] = None
    credit_days: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("gstin")
    @classmethod
    def gstin_format(cls, v):
        if v and v.strip():
            v = v.strip().upper()
            if not re.match(r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$", v):
                raise ValueError("Invalid GSTIN format. Example: 09ABCDE1234F1Z5")
            return v
        return None
