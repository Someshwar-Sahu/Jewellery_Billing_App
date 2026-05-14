from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import select, Session
from app.database import get_session
from app.models.payments import CashAccount
from app.models.parties import Party
from datetime import date
from calendar import monthrange
from collections import defaultdict

router = APIRouter(prefix="/ledger", tags=["Ledger"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/", response_class=HTMLResponse)
def ledger_view(request: Request, month: str = "", mode: str = "", entry_type: str = "", session: Session = Depends(get_session)):
    stmt = select(CashAccount).order_by(CashAccount.entry_date.desc(), CashAccount.id.desc())

    if month:
        try:
            year, mon = int(month.split("-")[0]), int(month.split("-")[1])
            first = date(year, mon, 1)
            last = date(year, mon, monthrange(year, mon)[1])
            stmt = stmt.where(CashAccount.entry_date >= first)
            stmt = stmt.where(CashAccount.entry_date <= last)
        except Exception :
            pass

    if mode:
        stmt = stmt.where(CashAccount.mode == mode)
    
    if entry_type:
        stmt = stmt.where(CashAccount.entry_type == entry_type)

    entries = session.exec(stmt).all()

    party_ids = {e.party_id for e in entries if e.party_id}
    parties: dict = {}
    if party_ids:
        rows = session.exec(select(Party).where(Party.id.in_(party_ids))).all()
        parties = {p.id: p for p in rows}
    
    total_receipts = round(sum(e.amount for e in entries if e.entry_type == "receipt"),2)
    total_payments = round(sum(e.amount for e in entries if e.entry_type == "payment"),2)
    net_flow = round(total_receipts - total_payments, 2)

    mode_breakdown: dict = defaultdict(float)
    for e in entries:
        if e.entry_type == "receipt":
            mode_breakdown[e.mode] += round(e.amount, 2)
        
    mode_breakdown = dict(sorted(mode_breakdown.items(), key=lambda x: -x[1]))

    all_modes_rows = session.exec(select(CashAccount.mode).distinct()).all()
    all_modes = sorted({r for r in all_modes_rows if r})

    return templates.TemplateResponse(
        request=request, name="ledger/index.html",
        context={
            "entries":         entries,
            "parties":         parties,
            "total_receipts":  total_receipts,
            "total_payments":  total_payments,
            "net_flow":        net_flow,
            "mode_breakdown":  mode_breakdown,
            "month":           month,
            "mode":            mode,
            "entry_type":      entry_type,
            "all_modes":       all_modes,
            "entry_count":     len(entries),
        },
    )