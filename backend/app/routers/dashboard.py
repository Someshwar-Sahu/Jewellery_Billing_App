from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from datetime import date, timedelta
from collections import defaultdict

from app.database import get_session
from app.models.invoices import Invoice
from app.models.parties import Party
from app.models.payments import Advance
from app.models.inventory import StockLedger
from app.models.products import Product
from app.models.shop import FinancialYear
from app.models.system import MonthLock, AppAlert

router    = APIRouter(prefix="/dashboard", tags=["Dashboard"])
templates = Jinja2Templates(directory="app/templates")


def _month_label(y: int, m: int) -> str:
    return date(y, m, 1).strftime("%b %Y")


@router.get("/", response_class=HTMLResponse)
def dashboard_home(request: Request, session: Session = Depends(get_session)):

    today     = date.today()
    active_fy   = session.exec(select(FinancialYear).where(FinancialYear.is_active == True)).first()
    fy_start    = active_fy.start_date if active_fy else date(today.year, 4, 1)
    fy_end      = active_fy.end_date   if active_fy else date(today.year + 1, 3, 31)
    month_start = today.replace(day=1)

    today_bills = session.exec(
        select(Invoice)
        .where(Invoice.invoice_type == "sale")
        .where(Invoice.is_cancelled == False)
        .where(Invoice.invoice_date == today)
        .where(Invoice.invoice_date >= fy_start)
    ).all()
    today_sale_count  = len(today_bills)
    today_sale_total  = round(sum(b.grand_total for b in today_bills), 2)
    today_sale_paid   = round(sum(b.amount_paid  for b in today_bills), 2)

    month_bills = session.exec(
        select(Invoice)
        .where(Invoice.invoice_type == "sale")
        .where(Invoice.is_cancelled == False)
        .where(Invoice.invoice_date >= month_start)
        .where(Invoice.invoice_date <= today)
    ).all()
    month_sale_count = len(month_bills)
    month_sale_total = round(sum(b.grand_total for b in month_bills), 2)

    mode_totals = defaultdict(float)
    for b in month_bills:
        mode = b.payment_mode or "cash"
        mode_totals[mode] += b.grand_total
    payment_modes = [
        {"mode": m.upper(), "total": round(v, 2)}
        for m, v in sorted(mode_totals.items(), key=lambda x: -x[1])
    ]

    customer_totals = defaultdict(float)
    party_ids_needed = {b.party_id for b in month_bills if b.party_id}
    parties_map = {}
    if party_ids_needed:
        for p in session.exec(select(Party).where(Party.id.in_(party_ids_needed))).all():
            parties_map[p.id] = p

    for b in month_bills:
        name = parties_map[b.party_id].name if b.party_id and b.party_id in parties_map else "Walk-in"
        customer_totals[name] += b.grand_total

    top_customers = sorted(
        [{"name": n, "total": round(v, 2)} for n, v in customer_totals.items()],
        key=lambda x: -x["total"]
    )[:5]

    pending_bills = session.exec(
        select(Invoice)
        .where(Invoice.is_cancelled == False)
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
    ).all()
    pending_count = len(pending_bills)
    pending_total = round(sum(b.amount_due for b in pending_bills), 2)

    open_advances = session.exec(
        select(Advance).where(Advance.status == "open")
    ).all()
    advance_balance = round(sum(a.amount - a.adjusted_amount for a in open_advances), 2)

    products_all = session.exec(
        select(Product).where(Product.is_active == True)
    ).all()
    low_stock_count = 0
    for product in products_all:
        if product.low_stock_alert is None:
            continue
        entries = session.exec(
            select(StockLedger).where(StockLedger.product_id == product.id)
        ).all()
        if not entries:
            continue
        balance = sum(e.quantity_in for e in entries) - sum(e.quantity_out for e in entries)
        if balance <= product.low_stock_alert:
            low_stock_count += 1

    trend = []
    for i in range(5, -1, -1):
        ref    = today.replace(day=1) - timedelta(days=i * 28)
        ref    = ref.replace(day=1)
        y, m   = ref.year, ref.month
        import calendar as _cal
        last_d = _cal.monthrange(y, m)[1]
        mn_start = date(y, m, 1)
        mn_end   = date(y, m, last_d)

        mn_bills = session.exec(
            select(Invoice)
            .where(Invoice.invoice_type == "sale")
            .where(Invoice.is_cancelled == False)
            .where(Invoice.invoice_date >= mn_start)
            .where(Invoice.invoice_date <= mn_end)
        ).all()
        trend.append({
            "label": _month_label(y, m),
            "total": round(sum(b.grand_total for b in mn_bills), 2),
            "count": len(mn_bills),
        })

    lock_status = []
    for i in range(2, -1, -1):
        ref = (today.replace(day=1) - timedelta(days=i * 28)).replace(day=1)
        y, m = ref.year, ref.month
        lock = session.exec(
            select(MonthLock)
            .where(MonthLock.year  == y)
            .where(MonthLock.month == m)
        ).first()
        lock_status.append({
            "year":      y,
            "month":     m,
            "label":     _month_label(y, m),
            "is_locked": lock.is_locked if lock else False,
            "locked_at": lock.locked_at if lock else None,
            "lock_id":   lock.id        if lock else None,
        })

    from datetime import datetime
    now = datetime.utcnow()
    alerts = session.exec(
        select(AppAlert)
        .where(AppAlert.is_active == True)
        .where(AppAlert.show_from  <= now)
        .where(AppAlert.show_until >= now)
        .where(AppAlert.dismissed_at == None)
    ).all()

    import calendar as _cal2
    last_day_this_month = _cal2.monthrange(today.year, today.month)[1]
    days_to_month_end   = last_day_this_month - today.day
    show_lock_warning   = (days_to_month_end <= 5)

    current_lock = session.exec(
        select(MonthLock)
        .where(MonthLock.year  == today.year)
        .where(MonthLock.month == today.month)
        .where(MonthLock.is_locked == True)
    ).first()
    show_lock_warning = show_lock_warning and not current_lock

    return templates.TemplateResponse(
        request=request,
        name="dashboard/index.html",
        context={
            "today":              today,
            "today_sale_count":   today_sale_count,
            "today_sale_total":   today_sale_total,
            "today_sale_paid":    today_sale_paid,
            "month_sale_count":   month_sale_count,
            "month_sale_total":   month_sale_total,
            "payment_modes":      payment_modes,
            "top_customers":      top_customers,
            "pending_count":      pending_count,
            "pending_total":      pending_total,
            "advance_balance":    advance_balance,
            "low_stock_count":    low_stock_count,
            "trend":              trend,
            "lock_status":        lock_status,
            "show_lock_warning":  show_lock_warning,
            "days_to_month_end":  days_to_month_end,
            "alerts":             alerts,
            "active_fy": active_fy,
            "fy_label":  active_fy.label if active_fy else "—",
        },
    )


# ── LOCK A MONTH ──────────────────────────────────────────────────────────────

@router.post("/lock-month")
async def lock_month(request: Request, session: Session = Depends(get_session)):
    data  = await request.json()
    year  = int(data["year"])
    month = int(data["month"])

    existing = session.exec(
        select(MonthLock)
        .where(MonthLock.year  == year)
        .where(MonthLock.month == month)
    ).first()

    from datetime import datetime
    if existing:
        existing.is_locked = True
        existing.locked_at = datetime.utcnow()
        session.add(existing)
    else:
        session.add(MonthLock(
            year      = year,
            month     = month,
            is_locked = True,
            locked_at = datetime.utcnow(),
        ))

    session.commit()
    return {"success": True, "message": f"Month {_month_label(year, month)} is now locked."}


# ── UNLOCK A MONTH ────────────────────────────────────────────────────────────

@router.post("/unlock-month")
async def unlock_month(request: Request, session: Session = Depends(get_session)):
    data  = await request.json()
    year  = int(data["year"])
    month = int(data["month"])

    lock = session.exec(
        select(MonthLock)
        .where(MonthLock.year  == year)
        .where(MonthLock.month == month)
    ).first()

    if not lock:
        raise HTTPException(status_code=404, detail="Lock not found")

    lock.is_locked = False
    lock.locked_at = None
    session.add(lock)
    session.commit()
    return {"success": True, "message": f"Month {_month_label(year, month)} unlocked."}


# ── DISMISS ALERT ─────────────────────────────────────────────────────────────

@router.post("/dismiss-alert/{alert_id}")
def dismiss_alert(alert_id: int, session: Session = Depends(get_session)):
    alert = session.get(AppAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    from datetime import datetime
    alert.dismissed_at = datetime.utcnow()
    session.add(alert)
    session.commit()
    return {"success": True}