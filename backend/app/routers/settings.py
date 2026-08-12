from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.shop import ShopSettings, FinancialYear
from datetime import date
from app.models.invoices import Invoice
from app.models.parties import Party
from decimal import Decimal

router    = APIRouter(prefix="/settings", tags=["Settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
def settings_page(request: Request, session: Session = Depends(get_session)):
    shop = session.exec(select(ShopSettings)).first()
    fy   = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    all_fy = session.exec(
        select(FinancialYear).order_by(FinancialYear.label.desc())
    ).all()
    return templates.TemplateResponse(
        request=request, name="settings/index.html",
        context={
            "shop":   shop,
            "fy":     fy,
            "all_fy": all_fy,
            "today":  date.today().isoformat(),
        }
    )


@router.post("/shop")
async def save_shop(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        shop = session.exec(select(ShopSettings)).first()

        if not shop:
            shop = ShopSettings(
                shop_name = data.get("shop_name", "My Shop"),
            )
            session.add(shop)
            session.flush()

        shop.shop_name       = data.get("shop_name")       or shop.shop_name
        shop.gstin           = data.get("gstin")           or None
        shop.address         = data.get("address")         or None
        shop.city            = data.get("city")            or None
        shop.state           = data.get("state")           or "Uttar Pradesh"
        shop.state_code      = data.get("state_code")      or "09"
        shop.phone           = data.get("phone")           or None
        shop.email           = data.get("email")           or None
        shop.bill_template   = data.get("bill_template")   or "template_dad"
        shop.bank_name       = data.get("bank_name")       or None
        shop.bank_account_no = data.get("bank_account_no") or None
        shop.bank_ifsc       = data.get("bank_ifsc")       or None
        shop.terms_line1     = data.get("terms_line1")     or None
        shop.terms_line2     = data.get("terms_line2")     or None

        session.add(shop)
        session.commit()
        return {"success": True}

    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


@router.post("/financial-year")
async def save_fy(request: Request, session: Session = Depends(get_session)):
    """Create a new financial year or switch active FY."""
    data = await request.json()
    try:
        label = (data.get("label") or "").strip()
        if not label:
            return JSONResponse(status_code=400, content={"success": False, "error": "Financial year label is required."})

        existing = session.exec(
            select(FinancialYear).where(FinancialYear.label == label)
        ).first()

        start_date = None
        end_date = None
        start_raw = data.get("start_date")
        end_raw = data.get("end_date")

        if start_raw or end_raw:
            if not start_raw or not end_raw:
                return JSONResponse(status_code=400, content={"success": False, "error": "Both start and end dates are required."})
            start_date = date.fromisoformat(start_raw)
            end_date = date.fromisoformat(end_raw)
        elif existing:
            start_date = existing.start_date
            end_date = existing.end_date
        else:
            return JSONResponse(status_code=400, content={"success": False, "error": "Start date and end date are required for a new financial year."})

        if start_date > end_date:
            return JSONResponse(status_code=400, content={"success": False, "error": "Financial year start date cannot be after end date."})

        all_fy = session.exec(select(FinancialYear)).all()
        for fy in all_fy:
            if existing and fy.id == existing.id:
                continue
            if not (end_date < fy.start_date or start_date > fy.end_date):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": f"Financial year period overlaps with existing FY '{fy.label}'.",
                    },
                )

        for fy in all_fy:
            fy.is_active = False
            session.add(fy)

        if existing:
            if existing.is_closed:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "error": f"FY '{label}' is closed and cannot be reactivated. Create a new financial year instead."}
                )
            existing.start_date = start_date
            existing.end_date   = end_date
            existing.is_active  = True
            session.add(existing)
        else:
            session.add(
                FinancialYear(
                    label=label,
                    start_date=start_date,
                    end_date=end_date,
                    is_active=True,
                )
            )

        session.commit()
        return {"success": True, "label": label}

    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})

@router.post("/close-fy")
async def close_fy(request: Request, session: Session = Depends(get_session)):
    """
    Formally close the active FY and activate a new one atomically.
    Warns about pending credit bills but does not block closing.
    """
    data = await request.json()
    new_label      = (data.get("new_label")      or "").strip()
    new_start_raw  = (data.get("new_start_date") or "").strip()
    new_end_raw    = (data.get("new_end_date")   or "").strip()
    confirmed      = data.get("confirmed", False)  

    if not new_label or not new_start_raw or not new_end_raw:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "New FY label, start date, and end date are required."}
        )

    try:
        new_start = date.fromisoformat(new_start_raw)
        new_end   = date.fromisoformat(new_end_raw)
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid date format."})

    if new_start > new_end:
        return JSONResponse(status_code=400, content={"success": False, "error": "Start date cannot be after end date."})

    active_fy = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    if not active_fy:
        return JSONResponse(status_code=400, content={"success": False, "error": "No active financial year found."})

    duplicate = session.exec(
        select(FinancialYear).where(FinancialYear.label == new_label)
    ).first()
    if duplicate:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": f"Financial year '{new_label}' already exists."}
        )

    all_fys = session.exec(select(FinancialYear)).all()
    for fy in all_fys:
        if not (new_end < fy.start_date or new_start > fy.end_date):
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": f"New FY period overlaps with existing FY '{fy.label}'."}
            )

    from app.models.invoices import Invoice
    from app.models.payments import Advance

    pending_bills = session.exec(
        select(Invoice)
        .where(Invoice.is_cancelled == False)
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
        .where(Invoice.invoice_date >= active_fy.start_date)
        .where(Invoice.invoice_date <= active_fy.end_date)
    ).all()

    open_advances = session.exec(
        select(Advance).where(Advance.status == "open")
    ).all()

    warnings = []
    if pending_bills:
        total_due = sum(b.amount_due for b in pending_bills)
        warnings.append(
            f"{len(pending_bills)} unpaid/partial credit bill(s) totalling ₹{total_due:,.2f} will remain open in the closed FY."
        )
    if open_advances:
        total_adv = sum(a.amount - a.adjusted_amount for a in open_advances)
        warnings.append(
            f"{len(open_advances)} open advance(s) totalling ₹{total_adv:,.2f} will carry forward to the new FY."
        )

    cf_preview_bills = session.exec(
        select(Invoice)
        .where(Invoice.is_cancelled == False)
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
        .where(Invoice.invoice_date >= active_fy.start_date)
        .where(Invoice.invoice_date <= active_fy.end_date)
        .where(Invoice.party_id != None)
    ).all()
    cf_parties = {b.party_id for b in cf_preview_bills}

    if not confirmed:
        return {
            "success":              False,
            "requires_confirmation": True,
            "warnings":             warnings if warnings else [],
            "carry_forward_count":  len(cf_parties),
        }

    try:
        active_fy.is_active = False
        active_fy.is_closed = True
        session.add(active_fy)

        new_fy = FinancialYear(
            label      = new_label,
            start_date = new_start,
            end_date   = new_end,
            is_active  = True,
            is_closed  = False,
        )
        session.add(new_fy)
        session.flush()   

        _carry_forward_party_balances(session, active_fy)

        session.commit()
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})

    return {
        "success":    True,
        "closed_fy":  active_fy.label,
        "new_fy":     new_label,
    }

def _carry_forward_party_balances(session: Session, closing_fy: FinancialYear) -> None:
    """
    For each party that has outstanding dues in the closing FY,
    write the net balance to Party.opening_balance.

    Rules:
    - Only bills whose invoice_date falls within closing_fy are considered.
    - Sale bills where amount_due > 0 → party owes us (debit balance).
    - Purchase bills where amount_due > 0 → we owe supplier (credit balance).
    - If a party has both, net them.
    - Only updates parties with a non-zero net balance.
    - Idempotent: overwrites previous carry-forward value (type = "carried_forward").
    """
    
    bills = session.exec(
        select(Invoice)
        .where(Invoice.is_cancelled == False)
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
        .where(Invoice.invoice_date >= closing_fy.start_date)
        .where(Invoice.invoice_date <= closing_fy.end_date)
        .where(Invoice.party_id != None)
    ).all()

    party_net: dict[int, Decimal] = {}
    for bill in bills:
        due = Decimal(str(bill.amount_due))
        if bill.invoice_type in ("sale", "debit_note"):
            party_net[bill.party_id] = party_net.get(bill.party_id, Decimal("0")) + due
        elif bill.invoice_type in ("purchase", "credit_note"):
            party_net[bill.party_id] = party_net.get(bill.party_id, Decimal("0")) - due

    for party in session.exec(select(Party)).all():
        pre_bal = Decimal(str(party.opening_balance or 0))
        pre_net = pre_bal if party.opening_balance_type == "debit" else -pre_bal
        year_net = party_net.get(party.id, Decimal("0"))
        total_net = pre_net + year_net

        if total_net != Decimal("0"):
            party.opening_balance      = float(abs(total_net))
            party.opening_balance_type = "debit" if total_net > 0 else "credit"
        else:
            party.opening_balance      = 0.0
            party.opening_balance_type = None
        session.add(party)

@router.get("/all-fy")
def all_fy_json(session: Session = Depends(get_session)):
    """JSON list of all FYs — used by exports page FY selector."""
    fys = session.exec(select(FinancialYear).order_by(FinancialYear.start_date.desc())).all()
    return [
        {"id": f.id, "label": f.label, "is_active": f.is_active, "is_closed": f.is_closed}
        for f in fys
    ]