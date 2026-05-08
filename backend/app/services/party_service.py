from sqlmodel import Session, select, func
from app.models.parties import Party
from app.models.invoices import Invoice
from app.schemas.party import PartyCreate, PartyUpdate
from fastapi import HTTPException
from datetime import datetime


def create_party(session: Session, data: PartyCreate) -> Party:
    party = Party(
        type                 = data.type,
        name                 = data.name,
        phone                = data.phone,
        email                = data.email,
        address              = data.address,
        city                 = data.city,
        state                = data.state or "Uttar Pradesh",
        gstin                = data.gstin,
        credit_limit         = data.credit_limit,
        credit_days          = data.credit_days,
        opening_balance      = data.opening_balance,
        opening_balance_type = data.opening_balance_type,
        notes                = data.notes,
    )
    session.add(party)
    session.commit()
    session.refresh(party)
    return party


def update_party(session: Session, party_id: int, data: PartyUpdate) -> Party:
    party = session.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    update_dict = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in update_dict.items():
        setattr(party, field, value)

    session.add(party)
    session.commit()
    session.refresh(party)
    return party


def get_party_summary(session: Session, party_id: int) -> dict:
    """Return bill counts, total business, and outstanding balance for a party."""
    party = session.get(Party, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    bills = session.exec(
        select(Invoice)
        .where(Invoice.party_id == party_id)
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.invoice_date.desc())
    ).all()

    total_billed    = sum(b.grand_total  for b in bills)
    total_paid      = sum(b.amount_paid  for b in bills)
    total_due       = sum(b.amount_due   for b in bills)
    credit_bills    = [b for b in bills if b.bill_category == "credit" and b.payment_status != "paid"]
    sale_bills      = [b for b in bills if b.invoice_type == "sale"]
    purchase_bills  = [b for b in bills if b.invoice_type == "purchase"]
    opening_bal      = party.opening_balance or 0.0
    opening_bal_type = party.opening_balance_type or "debit"

    return {
        "party":           party,
        "bills":           bills,
        "total_billed":    round(total_billed, 2),
        "total_paid":      round(total_paid,   2),
        "total_due":       round(total_due,    2),
        "credit_bills":    credit_bills,
        "sale_count":      len(sale_bills),
        "purchase_count":  len(purchase_bills),
        "total_bills":     len(bills),
        "opening_bal":     round(opening_bal, 2),
        "opening_bal_type":opening_bal_type
    }


def search_parties(session: Session, query: str = "", type_filter: str = "") -> list:
    """Search parties by name or phone, optionally filtered by type."""
    stmt = select(Party)
    if query:
        stmt = stmt.where(
            (Party.name.contains(query)) | (Party.phone.contains(query))
        )
    if type_filter and type_filter in ["customer", "supplier", "both"]:
        if type_filter == "customer":
            stmt = stmt.where((Party.type == "customer") | (Party.type == "both"))
        elif type_filter == "supplier":
            stmt = stmt.where((Party.type == "supplier") | (Party.type == "both"))
        else:
            stmt = stmt.where(Party.type == "both")
    return session.exec(stmt.order_by(Party.name)).all()
