from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.inventory import GoldRate
from datetime import date

router = APIRouter(prefix="/rates", tags=["Gold Rates"])
templates = Jinja2Templates(directory="app/templates")

# ── LIST (last 30 days) ───────────────────────────────────────────────────────

@router.get("/", response_class= HTMLResponse)
def rates_list(request: Request, session: Session = Depends(get_session)):
    rates = session.exec(select(GoldRate).order_by(GoldRate.rate_date.desc()).limit(30)).all()

    today_rate = session.exec(select(GoldRate).where(GoldRate.rate_date == date.today())).first()

    return templates.TemplateResponse(
        request=request, name="rates/list.html",
        context={"rates": rates, "today_rate": today_rate, "today": date.today().isoformat()}
    )

# ── CREATE ───────────────────────────────────────────────────────

@router.get("/create",response_class= HTMLResponse)
def create_rate_form(request: Request, session: Session = Depends(get_session)):

    today_rate = session.exec(select(GoldRate).where(GoldRate.rate_date == date.today())).first()

    last_rate = session.exec(select(GoldRate).order_by(GoldRate.rate_date.desc()).limit(1)).first()

    return templates.TemplateResponse(
        request=request, name="rates/create.html",
        context={"today_rate": today_rate, "last_rate": last_rate, "today": date.today().isoformat()}
    )

@router.post("/create")
async def create_rate_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        rate_date = date.fromisoformat(data["rate_date"])

        existing = session.exec(select(GoldRate).where(GoldRate.rate_date == rate_date)).first()

        if existing:
            if data.get("gold_22k"): existing.gold_22k_per_gram = float(data["gold_22k"])
            if data.get("gold_18k"): existing.gold_18k_per_gram = float(data["gold_18k"])
            if data.get("silver"):    existing.silver_per_gram    = float(data["silver"])
            session.add(existing)
            session.commit()
            return {"success": True, "updated": True}

        else:
            gold_22k = float(data["gold_22k"]) if data.get("gold_22k") else None
            gold_18k = float(data["gold_18k"]) if data.get("gold_18k") else None
            silver   = float(data["silver"])   if data.get("silver")   else None

            # ADD:
            if gold_22k is not None and gold_22k <= 0:
                return JSONResponse(status_code=400, content={"success": False, "error": "Gold 22K rate must be greater than zero."})
            if gold_18k is not None and gold_18k <= 0:
                return JSONResponse(status_code=400, content={"success": False, "error": "Gold 18K rate must be greater than zero."})
            if silver is not None and silver <= 0:
                return JSONResponse(status_code=400, content={"success": False, "error": "Silver rate must be greater than zero."})
            rate = GoldRate(
                rate_date=rate_date,
                gold_22k_per_gram=gold_22k,
                gold_18k_per_gram=gold_18k,
                silver_per_gram=silver,
            )

            session.add(rate)
            session.commit()
            return {"success": True, "updated": False}
        
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
    
# ── TODAY'S RATE (JSON — called by invoice.js) ────────────────────────────────

@router.get("/today")
def today_rate(request: Request, session: Session = Depends(get_session)):
    """Return today's rate as JSON. Called by create bill form to auto fill rate."""
    rate = session.exec(select(GoldRate).where(GoldRate.rate_date == date.today())).first()

    if not rate:
        return {"found": False}

    return {
        "found": True,
        "gold_22k": rate.gold_22k_per_gram,
        "gold_18k": rate.gold_18k_per_gram,
        "silver": rate.silver_per_gram,
        "rate_date": rate.rate_date.isoformat(),
    }