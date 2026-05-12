from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.inventory import StockLedger
from app.models.products import Product
from app.models.invoices import Invoice
from app.models.system import MonthLock
from app.models.shop import FinancialYear

router    = APIRouter(prefix="/stock", tags=["Stock"])
templates = Jinja2Templates(directory="app/templates")


def _is_system_generated_reversal(entry: StockLedger) -> bool:
    """
    Identify stock rows auto-created by cancel/recover flows.
    Keep these rows for audit/history and balance math, but exclude from
    business summary cards (Total In / Total Out) to avoid inflation.
    """
    notes = (entry.notes or "").strip().lower()
    if not notes:
        return False
    return notes.startswith("reversal: bill ") or notes.startswith("re-applied: bill ")


def get_summary(session: Session) -> list:
    """
    For each product with stock ledger entries compute balance and low-stock flag.
    """
    products = session.exec(
        select(Product).where(Product.is_active == True).order_by(Product.name)
    ).all()

    summary = []
    for product in products:
        entries = session.exec(
            select(StockLedger)
            .where(StockLedger.product_id == product.id)
            .order_by(StockLedger.stock_date.desc())
        ).all()

        if not entries:
            continue

        effective_entries = [e for e in entries if not _is_system_generated_reversal(e)]
        total_in  = round(sum(e.quantity_in  for e in effective_entries), 3)
        total_out = round(sum(e.quantity_out for e in effective_entries), 3)
        balance   = round(sum(e.quantity_in - e.quantity_out for e in entries), 3)
        last_date = entries[0].stock_date if entries else None
        is_low    = product.low_stock_alert is not None and balance <= product.low_stock_alert

        summary.append({
            "product":   product,
            "total_in":  total_in,
            "total_out": total_out,
            "balance":   balance,
            "last_date": last_date,
            "is_low":    is_low,
            "entries":   entries,
        })

    return summary


# ── STOCK OVERVIEW ────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def stock_list(request: Request, session: Session = Depends(get_session)):
    summary   = get_summary(session)
    low_count = sum(1 for s in summary if s["is_low"])
    return templates.TemplateResponse(
        request=request, name="stock/list.html",
        context={"summary": summary, "low_count": low_count}
    )


# ── PRODUCT STOCK HISTORY ─────────────────────────────────────────────────────

@router.get("/{product_id}", response_class=HTMLResponse)
def product_stock(product_id: int, request: Request, session: Session = Depends(get_session)):
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    entries     = session.exec(
        select(StockLedger)
        .where(StockLedger.product_id == product_id)
        .order_by(StockLedger.stock_date.desc())
    ).all()
    invoice_ids = {e.invoice_id for e in entries if e.invoice_id}
    invoices    = {i.id: i for i in session.exec(
        select(Invoice).where(Invoice.id.in_(invoice_ids))
    ).all()} if invoice_ids else {}

    effective_entries = [e for e in entries if not _is_system_generated_reversal(e)]
    total_in  = round(sum(e.quantity_in  for e in effective_entries), 3)
    total_out = round(sum(e.quantity_out for e in effective_entries), 3)
    balance   = round(sum(e.quantity_in - e.quantity_out for e in entries), 3)

    return templates.TemplateResponse(
        request=request, name="stock/list.html",
        context={
            "summary":   None,
            "product":   product,
            "entries":   entries,
            "invoices":  invoices,
            "total_in":  total_in,
            "total_out": total_out,
            "balance":   balance,
            "low_count": 0,
        }
    )


# ── MANUAL ADJUSTMENT ─────────────────────────────────────────────────────────

@router.post("/{product_id}/adjust")
async def adjust_stock(product_id: int, request: Request, session: Session = Depends(get_session)):
    """Manual stock adjustment — for opening stock or corrections."""
    data    = await request.json()
    product = session.get(Product, product_id)

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")   

    try:
        from datetime import date as date_type
        adj_type = data.get("type", "in")
        stock_date = date_type.fromisoformat(data.get("date", date_type.today().isoformat()))
        active_fy = session.exec(select(FinancialYear).where(FinancialYear.is_active == True)).first()
        if not active_fy:
            return JSONResponse(status_code=400, content={"success": False, "error": "No active financial year configured."})
        if not (active_fy.start_date <= stock_date <= active_fy.end_date):
            return JSONResponse(status_code=400, content={"success": False, "error": f"Date is outside active financial year {active_fy.label}."})

        quantity = float(data["quantity"])
        if quantity <= 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Quantity must be greater than zero."})
        rate = float(data["rate"]) if data.get("rate") else None
        if rate is not None and rate < 0:
            return JSONResponse(status_code=400, content={"success": False, "error": "Rate cannot be negative."})

        lock = session.exec(
            select(MonthLock)
            .where(MonthLock.year == stock_date.year)
            .where(MonthLock.month == stock_date.month)
            .where(MonthLock.is_locked == True)
        ).first()
        if lock:
            return JSONResponse(status_code=400, content={"success": False, "error": f"{stock_date.strftime('%B %Y')} is locked for GST filing."})
        entry = StockLedger(
            product_id       = product_id,
            stock_date       = stock_date,
            transaction_type = "adjustment",
            invoice_id       = None,
            quantity_in      = quantity if adj_type == "in"  else 0.0,
            quantity_out     = quantity if adj_type == "out" else 0.0,
            balance          = 0.0,
            rate             = rate,
            notes            = data.get("notes"),
        )
        session.add(entry)
        session.commit()
        return {"success": True}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)}) 
