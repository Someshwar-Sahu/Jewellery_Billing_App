from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.expenses import Expense, ExpenseCategory
from app.models.parties import Party
from datetime import date

router    = APIRouter(prefix="/expenses", tags=["Expenses"])
templates = Jinja2Templates(directory="app/templates")

# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def expense_list(request: Request, month: str = "", session: Session = Depends(get_session)):
    stmt = select(Expense).order_by(Expense.expense_date.desc())

    if month:
        try:
            year, mon = month.split("-")
            stmt = stmt.where(Expense.expense_date >= date(int(year), int(mon), 1))
            import calendar
            last_day = calendar.monthrange(int(year), int(mon))[1]
            stmt = stmt.where(Expense.expense_date <= date(int(year), int(mon), last_day))
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    expenses = session.exec(stmt).all()   # FIX 2: variable renamed (was expesnses)

    cat_ids    = {e.category_id for e in expenses}
    categories = {c.id: c for c in session.exec(
        select(ExpenseCategory).where(ExpenseCategory.id.in_(cat_ids))
    ).all()} if cat_ids else {}

    party_ids = {e.party_id for e in expenses if e.party_id}
    parties   = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}

    total_amount = round(sum(e.amount        for e in expenses), 2)
    total_gst    = round(sum(e.gst_amount    for e in expenses), 2)
    total_itc    = round(sum(e.itc_claimable for e in expenses), 2)

    return templates.TemplateResponse(
        request=request, name="expenses/list.html",
        context={
            "expenses":     expenses,   # FIX 2: key was "expesnses" — template uses "expenses"
            "categories":   categories,
            "parties":      parties,
            "total_amount": total_amount,
            "total_gst":    total_gst,
            "total_itc":    total_itc,
            "month":        month,
            "today":        date.today().isoformat(),
        }
    )

# ── CREATE ────────────────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
def create_form(request: Request, session: Session = Depends(get_session)):
    categories = session.exec(select(ExpenseCategory).order_by(ExpenseCategory.name)).all()
    parties    = session.exec(
        select(Party)
        .where((Party.type == "supplier") | (Party.type == "both"))
        .order_by(Party.name)
    ).all()
    return templates.TemplateResponse(
        request=request, name="expenses/create.html",
        context={"categories": categories, "parties": parties, "today": date.today().isoformat()}
    )

@router.post("/create")
async def submit_form(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        amount     = float(data["amount"])
        gst_amount = float(data.get("gst_amount", 0.0))
        if amount <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Amount must be greater than zero."})
        if gst_amount < 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "GST amount cannot be negative."})
        if gst_amount > amount:
            return JSONResponse(status_code=400, content={"success": False, "error": "GST amount cannot exceed expense amount."})
        cat        = session.get(ExpenseCategory, int(data["category_id"]))
        if not cat:
            return JSONResponse(status_code=400, content={"success": False, "error": "Invalid expense category."})
        itc        = gst_amount if (cat and cat.is_itc_eligible) else 0.0

        expense = Expense(
            category_id   = cat.id,
            party_id      = int(data["party_id"]) if data.get("party_id") else None,
            expense_date  = date.fromisoformat(data["expense_date"]),
            description   = data.get("description") or None,
            amount        = amount,
            gst_amount    = gst_amount,
            itc_claimable = itc,
            payment_mode  = data.get("payment_mode") or None,
            reference_no  = data.get("reference_no") or None,
        )
        session.add(expense)
        session.commit()
        session.refresh(expense)
        return {"success": True, "expense_id": expense.id}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

# ── CATEGORY MANAGEMENT ───────────────────────────────────────────────────────

@router.post("/categories/create")
async def create_categories(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        cat = ExpenseCategory(
            name           = data["name"],
            is_itc_eligible = bool(data.get("is_itc_eligible", False)),
        )
        session.add(cat)
        session.commit()
        session.refresh(cat)
        return {"success": True, "category_id": cat.id, "name": cat.name}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

# ── DELETE ────────────────────────────────────────────────────────────────────

@router.post("/{expense_id}/delete")
def delete_expense(expense_id: int, session: Session = Depends(get_session)):
    expense = session.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found")
    session.delete(expense)
    session.commit()
    return {"success": True}
