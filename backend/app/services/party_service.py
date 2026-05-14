from sqlmodel import Session, select
from app.models.parties import Party
from app.models.invoices import Invoice
from app.schemas.party import PartyCreate, PartyUpdate
from fastapi import HTTPException


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

    sale_bills      = [b for b in bills if b.invoice_type in ["sale", "debit_note"]]
    purchase_bills  = [b for b in bills if b.invoice_type in ["purchase", "credit_note"]]
    
    opening_bal      = party.opening_balance or 0.0
    opening_bal_type = party.opening_balance_type or "debit"

    net_balance = opening_bal if opening_bal_type == "debit" else -opening_bal
    
    sale_due = sum(b.amount_due for b in sale_bills)
    purchase_due = sum(b.amount_due for b in purchase_bills)
    
    from app.models.payments import Advance
    unused_advances = session.exec(
        select(Advance).where(Advance.party_id == party_id).where(Advance.status == "open")
    ).all()
    total_unused_advance = sum(a.amount - a.adjusted_amount for a in unused_advances)

    net_balance += sale_due
    net_balance -= purchase_due
    net_balance -= total_unused_advance

    net_balance_type = "debit" if net_balance >= 0 else "credit"
    net_balance = abs(round(net_balance, 2))

    total_billed    = sum(b.grand_total  for b in bills)
    total_paid      = sum(b.amount_paid  for b in bills)
    total_due       = round(sum(b.amount_due for b in bills), 2)
    credit_bills    = [b for b in bills if b.bill_category == "credit" and b.payment_status != "paid"]

    return {
        "party":           party,
        "bills":           bills,
        "total_billed":    round(total_billed, 2),
        "total_paid":      round(total_paid,   2),
        "total_due":       total_due,
        "net_balance":     net_balance,
        "net_balance_type":net_balance_type,
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
