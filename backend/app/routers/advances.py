from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.payments import Advance
from app.models.parties import Party
from datetime import date

router    = APIRouter(prefix="/advances", tags=["Advances"])
templates = Jinja2Templates(directory="app/templates")

# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def advance_list(request: Request, session: Session = Depends(get_session)):
    advances = session.exec(select(Advance).order_by(Advance.advance_date.desc())).all()

    party_ids = {a.party_id for a in advances}
    parties = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}

    total_open = round(sum(a.amount - a.adjusted_amount for a in advances if a.status == "open"), 2)

    return templates.TemplateResponse(
        request=request, name="advances/list.html",
        context={"advances": advances, "parties": parties, "total_open": total_open}
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
        advance = Advance(
            party_id     = int(data["party_id"]),
            advance_date = date.fromisoformat(data["advance_date"]),
            amount       = am,
            mode         = data.get("mode", "cash"),
            notes        = data.get("notes") or None,
        )
        session.add(advance)
        session.commit()
        session.refresh(advance)
        return {"success": True, "advance_id": advance.id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

# ── BALANCE (JSON — called by invoice.js when party selected on bill form) ────
# FIX 1: Route was entirely missing. invoice.js calls GET /advances/balance/{party_id}

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

# ── ADJUST (called when a bill uses advance amount) ───────────────────────────

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
        if remaining <= 0.0:   # FIX 3: was < 0.0
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
