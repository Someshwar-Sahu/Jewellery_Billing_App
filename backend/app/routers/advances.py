from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.payments import Advance, CashAccount, AdvanceApplication
from app.models.invoices import Invoice
from collections import defaultdict
from app.models.parties import Party
from app.models.shop import FinancialYear
from datetime import date

router    = APIRouter(prefix="/advances", tags=["Advances"])
templates = Jinja2Templates(directory="app/templates")

# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def advance_list(request: Request, status: str = "open", session: Session = Depends(get_session)):
    stmt = select(Advance).order_by(Advance.advance_date.desc())
    if status in ("open", "used"):
        stmt = stmt.where(Advance.status == status)
    advances = session.exec(stmt).all()

    party_ids = {a.party_id for a in advances}
    parties = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}

    total_open = round(sum(a.amount - a.adjusted_amount for a in advances if a.status == "open"), 2)

    advance_ids = [a.id for a in advances]
    apps_by_advance = defaultdict(list)
    invoices_map = {}
    if advance_ids:
        applications = session.exec(
            select(AdvanceApplication)
            .where(AdvanceApplication.advance_id.in_(advance_ids))
        ).all()
        for app in applications:
            apps_by_advance[app.advance_id].append(app)
        invoice_ids = {app.invoice_id for app in applications}
        if invoice_ids:
            for inv in session.exec(select(Invoice).where(Invoice.id.in_(invoice_ids))).all():
                invoices_map[inv.id] = inv

    return templates.TemplateResponse(
        request=request, name="advances/list.html",
        context={
            "advances":         advances,
            "parties":          parties,
            "total_open":       total_open,
            "status_filter":    status,
            "apps_by_advance":  dict(apps_by_advance),
            "invoices_map":     invoices_map,
        }
    )

# ── CREATE ────────────────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
def create_form(request: Request, session: Session = Depends(get_session)):
    parties = session.exec(
        select(Party)
        .where((Party.type == "customer") | (Party.type == "both"))
        .order_by(Party.name)
    ).all()
    return templates.TemplateResponse(
        request=request, name="advances/create.html",
        context={"parties": parties, "today": date.today().isoformat()}
    )

@router.post("/create")
async def create_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        am = float(data["amount"])
        if am <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Amount must be greater than zero."})
        adv_date = date.fromisoformat(data["advance_date"])
        active_fy = session.exec(select(FinancialYear).where(FinancialYear.is_active == True)).first()
        if not active_fy:
            return JSONResponse(status_code=400, content={"success": False, "error": "No active financial year configured."})
        if not (active_fy.start_date <= adv_date <= active_fy.end_date):
            return JSONResponse(status_code=400, content={"success": False, "error": f"Date is outside active financial year {active_fy.label}."})

        advance = Advance(
            party_id     = int(data["party_id"]),
            advance_date = adv_date,
            amount       = am,
            mode         = data.get("mode", "cash"),
            reference_no = data.get("reference_no") or None,
            notes        = data.get("notes") or None,
        )
        session.add(advance)
        session.flush()

        session.add(CashAccount(
            entry_date   = adv_date,
            entry_type   = "receipt",
            mode         = data.get("mode", "cash"),
            amount       = am,
            reference_no = data.get("reference_no") or None,
            party_id     = int(data["party_id"]),
            description  = f"Advance received",
        ))
        session.commit()
        session.refresh(advance)
        return {"success": True, "advance_id": advance.id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

@router.get("/balance/{party_id}")
def get_balance(party_id: int, session: Session = Depends(get_session)):
    """Return total available advance balance for a party."""
    advances = session.exec(
        select(Advance)
        .where(Advance.party_id == party_id)
        .where(Advance.status == "open")
    ).all()
    available = round(sum(a.amount - a.adjusted_amount for a in advances), 2)
    return {"available": available, "party_id": party_id}

@router.post("/adjust/{party_id}")
async def adjust_advance(party_id: int, request: Request, session: Session = Depends(get_session)):
    """Deducts amount from open advances for a party, oldest first."""
    data     = await request.json()
    amount   = float(data["amount"])
    advances = session.exec(
        select(Advance)
        .where(Advance.party_id == party_id)
        .where(Advance.status == "open")
        .order_by(Advance.advance_date)
    ).all()

    remaining = amount
    for adv in advances:
        if remaining <= 0.0:   
            break
        available = adv.amount - adv.adjusted_amount
        use       = min(available, remaining)
        adv.adjusted_amount = round(adv.adjusted_amount + use, 2)
        if adv.adjusted_amount >= adv.amount:
            adv.status = "used"
        session.add(adv)
        remaining = round(remaining - use, 2)

    session.commit()
    return {"success": True, "adjusted": round(amount - remaining, 2)}
