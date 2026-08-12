from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.parties import Party, OldGoldExchange
from app.models.shop import FinancialYear
from datetime import date

router    = APIRouter(prefix="/old-gold", tags=["Old Gold"])
templates = Jinja2Templates(directory="app/templates")


# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def old_gold_list(
    request: Request,
    metal: str = "",
    tx_type: str = "",
    session: Session = Depends(get_session)
):
    stmt = select(OldGoldExchange).order_by(OldGoldExchange.exchange_date.desc())

    if metal in ["gold", "silver"]:
        stmt = stmt.where(OldGoldExchange.metal_type == metal)
    if tx_type in ["exchange", "direct_purchase"]:
        stmt = stmt.where(OldGoldExchange.transaction_type == tx_type)

    records = session.exec(stmt).all()

    party_ids = {r.party_id for r in records}
    parties   = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}

    total_gold_weight   = sum(r.weight_grams for r in records if r.metal_type == "gold")
    total_silver_weight = sum(r.weight_grams for r in records if r.metal_type == "silver")
    total_value         = sum(r.total_value  for r in records)

    return templates.TemplateResponse(
        request=request, name="old_gold/list.html",
        context={
            "records":            records,
            "parties":            parties,
            "metal_filter":       metal,
            "tx_type_filter":     tx_type,
            "total_gold_weight":  round(total_gold_weight, 3),
            "total_silver_weight":round(total_silver_weight, 3),
            "total_value":        round(total_value, 2),
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
        request=request, name="old_gold/create.html",
        context={"parties": parties, "today": date.today().isoformat()}
    )


@router.post("/create")
async def create_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        weight = float(data["weight_grams"])
        rate   = float(data["rate_per_gram"])
        if weight <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Weight must be greater than zero."})
        if rate <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Rate must be greater than zero."})
        total      = round(weight * rate, 2)
        tx_type    = data.get("transaction_type", "direct_purchase")
        party_id   = int(data["party_id"])

        party = session.get(Party, party_id)
        if not party:
            return JSONResponse(status_code=400,
                content={"success": False, "error": "Party not found"})

        ex_date = date.fromisoformat(data["exchange_date"])
        active_fy = session.exec(select(FinancialYear).where(FinancialYear.is_active == True)).first()
        if not active_fy:
            return JSONResponse(status_code=400, content={"success": False, "error": "No active financial year configured."})
        if not (active_fy.start_date <= ex_date <= active_fy.end_date):
            return JSONResponse(status_code=400, content={"success": False, "error": f"Date is outside active financial year {active_fy.label}."})

        entry = OldGoldExchange(
            party_id         = party_id,
            sale_invoice_id  = None,   
            exchange_date    = ex_date,
            transaction_type = tx_type,
            metal_type       = data.get("metal_type", "gold"),
            purity           = data.get("purity") or None,
            weight_grams     = weight,
            rate_per_gram    = rate,
            total_value      = total,
            cash_paid        = float(data["cash_paid"]) if data.get("cash_paid") else total,
            notes            = data.get("notes") or None,
        )
        session.add(entry)
        session.flush()

        cash_out = entry.cash_paid or total
        if tx_type == "direct_purchase" and cash_out > 0:
            from app.models.payments import CashAccount
            session.add(CashAccount(
                entry_date   = ex_date,
                entry_type   = "payment",
                mode         = "cash",
                amount       = cash_out,
                party_id     = party_id,
                description  = f"Direct purchase of scrap {entry.metal_type} ({entry.weight_grams}g)",
            ))

        session.commit()
        session.refresh(entry)
        return {"success": True, "id": entry.id, "total_value": total}

    except KeyError as e:
        return JSONResponse(status_code=400,
            content={"success": False, "error": f"Missing field: {e}"})
    except Exception as e:
        return JSONResponse(status_code=400,
            content={"success": False, "error": str(e)})


# ── PARTY HISTORY (JSON — used by party detail page in future) ────────────────

@router.get("/party/{party_id}")
def party_old_gold(party_id: int, session: Session = Depends(get_session)):
    records = session.exec(
        select(OldGoldExchange)
        .where(OldGoldExchange.party_id == party_id)
        .order_by(OldGoldExchange.exchange_date.desc())
    ).all()
    return [
        {
            "id":               r.id,
            "exchange_date":    r.exchange_date.isoformat(),
            "transaction_type": r.transaction_type,
            "metal_type":       r.metal_type,
            "purity":           r.purity,
            "weight_grams":     r.weight_grams,
            "rate_per_gram":    r.rate_per_gram,
            "total_value":      r.total_value,
            "cash_paid":        r.cash_paid,
            "notes":            r.notes,
        }
        for r in records
    ]