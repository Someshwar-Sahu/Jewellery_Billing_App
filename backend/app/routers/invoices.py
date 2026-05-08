from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from app.database import get_session
from app.models.invoices import Invoice, InvoiceItem, InvoiceEditLog
from app.models.parties import Party, OldGoldExchange
from app.models.inventory import GoldRate
from app.models.system import MonthLock
from app.models.shop import FinancialYear
from app.services.invoice_service import (
    create_invoice, cancel_invoice, recover_invoice,
    get_pending_bills, update_invoice, duplicate_invoice
)
from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceUpdate
from datetime import date
from markupsafe import Markup
from num2words import num2words
from decimal import Decimal, ROUND_HALF_UP

import json as _json

router    = APIRouter(prefix="/invoices", tags=["Invoices"])
templates = Jinja2Templates(directory="app/templates")
templates.env.filters["tojson"] = lambda v: Markup(_json.dumps(v, default=str))


def _money(v) -> float:
    return float(Decimal(str(v if v is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

# ── LIST ──────────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def invoice_list(request: Request, fy_id: int = 0, session: Session = Depends(get_session)):
    # Load all FYs for the switcher dropdown
    all_fys = session.exec(select(FinancialYear).order_by(FinancialYear.start_date.desc())).all()
    active_fy = next((f for f in all_fys if f.is_active), None)

    # Determine which FY to display
    selected_fy = None
    if fy_id:
        selected_fy = session.get(FinancialYear, fy_id)
    if not selected_fy:
        selected_fy = active_fy   

    stmt = select(Invoice).where(Invoice.is_cancelled == False)
    if selected_fy:
        stmt = stmt.where(Invoice.invoice_date >= selected_fy.start_date)
        stmt = stmt.where(Invoice.invoice_date <= selected_fy.end_date)
    invoices = session.exec(stmt.order_by(Invoice.id.desc())).all()

    party_ids = {inv.party_id for inv in invoices if inv.party_id}
    parties   = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}

    return templates.TemplateResponse(
        request=request, name="invoices/list.html",
        context={
            "invoices":     invoices,
            "parties":      parties,
            "all_fys":      all_fys,
            "selected_fy":  selected_fy,
            "active_fy":    active_fy,
        }
    )

# ── CANCELLED ─────────────────────────────────────────────────────────────────

@router.get("/cancelled", response_class=HTMLResponse)
def cancelled_bills(request: Request, session: Session = Depends(get_session)):
    invoices  = session.exec(
        select(Invoice).where(Invoice.is_cancelled == True).order_by(Invoice.cancelled_at.desc())
    ).all()
    party_ids = {inv.party_id for inv in invoices if inv.party_id}
    parties   = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}
    return templates.TemplateResponse(
        request=request, name="invoices/cancelled.html",
        context={"invoices": invoices, "parties": parties}
    )


# ── PENDING PAYMENTS ──────────────────────────────────────────────────────────

@router.get("/credit/unsettled", response_class=HTMLResponse)
def unsettled_credit(request: Request, session: Session = Depends(get_session)):
    pending      = get_pending_bills(session)
    all_invoices = pending["credit_sales"] + pending["credit_purchases"] + pending["partial_bills"]
    party_ids    = {inv.party_id for inv in all_invoices if inv.party_id}
    parties      = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}
    return templates.TemplateResponse(
        request=request, name="invoices/credit_unsettled.html",
        context={
            "credit_sales":          pending["credit_sales"],
            "credit_purchases":      pending["credit_purchases"],
            "partial_bills":         pending["partial_bills"],
            "credit_sale_count":     len(pending["credit_sales"]),
            "credit_purchase_count": len(pending["credit_purchases"]),
            "partial_count":         len(pending["partial_bills"]),
            "parties":               parties,
            "today":                 date.today(),
        }
    )


# ── CREATE ────────────────────────────────────────────────────────────────────

@router.get("/create", response_class=HTMLResponse)
def create_bill_form(request: Request, session: Session = Depends(get_session)):
    parties    = session.exec(select(Party)).all()
    today_rate = session.exec(
        select(GoldRate).where(GoldRate.rate_date == date.today())
    ).first()
    return templates.TemplateResponse(
        request=request, name="invoices/create.html",
        context={
            "parties":    parties,
            "today_rate": today_rate,
            "rate_alert": today_rate is None,
            "today":      date.today().isoformat(),
        }
    )


@router.post("/create")
async def create_bill_submit(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        party_id     = data.get("party_id")
        walkin_name  = data.get("walkin_name")
        walkin_phone = data.get("walkin_phone")

        if not party_id:
            if not walkin_name:
                return JSONResponse(status_code=400, content={
                    "success": False, "error": "Customer name is required"
                })
            existing_party = None
            if walkin_phone:
                existing_party = session.exec(
                    select(Party).where(Party.phone == walkin_phone)
                ).first()

            if existing_party:
                party_id = existing_party.id
            else:
                walkin_party = Party(type="customer", name=walkin_name, phone=walkin_phone or None)
                session.add(walkin_party)
                session.flush()
                party_id = walkin_party.id
        else:
            party_id = int(party_id)

        items = []
        for item in data.get("items", []):
            items.append(InvoiceItemCreate(
                item_name      = item["item_name"],
                weight_grams   = float(item["weight_grams"])   if item.get("weight_grams")   else None,
                rate_per_gram  = float(item["rate_per_gram"])  if item.get("rate_per_gram")  else None,
                making_charges = float(item["making_charges"]) if item.get("making_charges") else None,
                gst_rate       = float(item.get("gst_rate", 3.0)),
                purity         = item.get("purity")      or None,
                huid           = item.get("huid")        or None,
                hsn_code       = item.get("hsn_code")    or "7113",
                description    = item.get("description") or None,
                product_id     = int(item["product_id"]) if item.get("product_id") else None,
            ))

        invoice_data = InvoiceCreate(
            invoice_type        = data.get("invoice_type", "sale"),
            bill_category       = data.get("bill_category", "cash"),
            party_id            = party_id,
            invoice_date        = date.fromisoformat(data["invoice_date"]),
            credit_due_date     = date.fromisoformat(data["credit_due_date"]) if data.get("credit_due_date") else None,
            payment_mode        = data.get("payment_mode") or None,
            amount_paid         = float(data.get("amount_paid", 0)),
            advance_used        = float(data.get("advance_used", 0)),
            old_gold_value      = float(data.get("old_gold_value", 0)),
            old_gold_metal_type = data.get("old_gold_metal_type") or "gold",
            old_gold_purity     = data.get("old_gold_purity")     or None,
            old_gold_weight     = float(data.get("old_gold_weight", 0)) if data.get("old_gold_weight") else None,
            old_gold_rate       = float(data.get("old_gold_rate", 0))   if data.get("old_gold_rate")   else None,
            discount            = float(data.get("discount", 0)),
            notes               = data.get("notes") or None,
            items               = items,
        )

        invoice = create_invoice(session, invoice_data)

        return {"success": True, "invoice_id": invoice.id, "invoice_number": invoice.invoice_number}

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── GST REVIEW (must be before /{invoice_id}) ─────────────────────────────────

@router.get("/gst/review", response_class=HTMLResponse)
def gst_review_page(request: Request, session: Session = Depends(get_session)):
    pending   = session.exec(
        select(Invoice)
        .where(Invoice.gst_status == "pending_review")
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.invoice_date)
    ).all()
    party_ids = {inv.party_id for inv in pending if inv.party_id}
    parties   = {p.id: p for p in session.exec(
        select(Party).where(Party.id.in_(party_ids))
    ).all()} if party_ids else {}
    return templates.TemplateResponse(
        request=request, name="invoices/gst_review.html",
        context={"invoices": pending, "parties": parties}
    )


@router.post("/gst/bulk-mark-ready")
async def bulk_gst_mark(request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    ids  = [int(i) for i in data.get("invoice_ids", [])]
    if not ids:
        return JSONResponse(status_code=400, content={"success": False, "error": "No bills selected"})
    invoices = session.exec(select(Invoice).where(Invoice.id.in_(ids))).all()
    for inv in invoices:
        inv.gst_status = "gst_ready"
        session.add(inv)
    session.commit()
    return {"success": True, "count": len(invoices)}


# ── DETAIL ────────────────────────────────────────────────────────────────────

@router.get("/{invoice_id}", response_class=HTMLResponse)
def invoice_detail(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    items = session.exec(
        select(InvoiceItem)
        .where(InvoiceItem.invoice_id == invoice_id)
        .order_by(InvoiceItem.sort_order)
    ).all()
    party     = session.get(Party, invoice.party_id) if invoice.party_id else None
    edit_logs = session.exec(
        select(InvoiceEditLog)
        .where(InvoiceEditLog.invoice_id == invoice_id)
        .order_by(InvoiceEditLog.edited_at.desc())
    ).all()
    active_fy   = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    is_historical = (
        active_fy is None or
        not (active_fy.start_date <= invoice.invoice_date <= active_fy.end_date)
    )
    return templates.TemplateResponse(
        request=request, name="invoices/detail.html",
        context={
            "invoice":      invoice,
            "items":        items,
            "party":        party,
            "edit_logs":    edit_logs,
            "today":        date.today(),
            "is_historical": is_historical,
            "active_fy":    active_fy,
        }
    )


# ── EDIT ──────────────────────────────────────────────────────────────────────

@router.get("/{invoice_id}/edit", response_class=HTMLResponse)
@router.get("/{invoice_id}/edit", response_class=HTMLResponse)
def edit_bill_form(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    if invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Bill is cancelled")
    active_fy = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    if active_fy and not (active_fy.start_date <= invoice.invoice_date <= active_fy.end_date):
        raise HTTPException(
            status_code=403,
            detail=f"Bill belongs to historical FY. Only FY {active_fy.label} is editable."
        )
    items_orm = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all()
    party     = session.get(Party, invoice.party_id) if invoice.party_id else None
    items = [
        {
            "product_id":     i.product_id,
            "item_name":      i.item_name,
            "purity":         i.purity,
            "weight_grams":   i.weight_grams,
            "rate_per_gram":  i.rate_per_gram,
            "making_charges": i.making_charges,
            "gst_rate":       i.gst_rate,
            "huid":           i.huid,
            "hsn_code":       i.hsn_code,
            "description":    i.description,
        }
        for i in items_orm
    ]
    return templates.TemplateResponse(
        request=request, name="invoices/edit.html",
        context={"invoice": invoice, "items": items, "party": party}
    )


@router.post("/{invoice_id}/edit")
async def edit_bill_submit(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        items = []
        for item in data.get("items", []):
            items.append(InvoiceItemCreate(
                item_name      = item["item_name"],
                weight_grams   = float(item["weight_grams"])   if item.get("weight_grams")   else None,
                rate_per_gram  = float(item["rate_per_gram"])  if item.get("rate_per_gram")  else None,
                making_charges = float(item["making_charges"]) if item.get("making_charges") else None,
                gst_rate       = float(item.get("gst_rate", 3.0)),
                purity         = item.get("purity")      or None,
                huid           = item.get("huid")        or None,   
                hsn_code       = item.get("hsn_code")    or "7113",
                description    = item.get("description") or None,
            ))

        update_data = InvoiceUpdate(
            invoice_date    = date.fromisoformat(data["invoice_date"]) if data.get("invoice_date") else None,
            credit_due_date = date.fromisoformat(data["credit_due_date"]) if data.get("credit_due_date") else None,
            payment_mode    = data.get("payment_mode") or None,
            old_gold_value  = float(data["old_gold_value"]) if data.get("old_gold_value") is not None else None,
            discount        = float(data["discount"])       if data.get("discount")       is not None else None,
            notes           = data.get("notes") or None,
            edit_reason     = data.get("edit_reason") or None,
            items           = items if len(items) > 0 else None,
        )
        invoice = update_invoice(session, invoice_id, update_data)
        return {"success": True, "invoice_id": invoice.id}

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── PRINT ─────────────────────────────────────────────────────────────────────

@router.get("/{invoice_id}/print", response_class=HTMLResponse)
def print_bill(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    items = session.exec(
        select(InvoiceItem)
        .where(InvoiceItem.invoice_id == invoice_id)
        .order_by(InvoiceItem.sort_order)
    ).all()
    party = session.get(Party, invoice.party_id) if invoice.party_id else None
    from app.models.shop import ShopSettings
    shop      = session.exec(select(ShopSettings)).first()
    old_gold  = session.exec(
        select(OldGoldExchange).where(OldGoldExchange.sale_invoice_id == invoice_id)
    ).first()
    
    try: 
        rupees = int(invoice.grand_total)
        paise_raw = round((invoice.grand_total - rupees) * 100)
        amount_word = num2words(rupees, lang="en_IN").title() + " Rupees"
        if paise_raw > 0:
            amount_word += " And" + num2words(paise_raw, lang= "en_IN").title() + " Paise"

        amount_word += " Only"
    except Exception:
        amount_word = ""
    template_name = "invoices/bill_print.html"
    if shop and shop.bill_template == "template_a4":
        template_name = "invoices/print_a4.html"
    else:
        template_name = "invoices/print_dad.html"

    return templates.TemplateResponse(
        request=request, name=template_name,
        context={
            "invoice": invoice,
            "items": items,
            "party": party,
            "shop": shop,   
            "old_gold": old_gold,
            "amount_word": amount_word,
        }
    )

# ── RECORD PAYMENT ────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/record-payment")
async def record_credit_payment(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    if invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot record payment on a cancelled bill.")

    active_fy = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    if not active_fy:
        raise HTTPException(status_code=400, detail="No active financial year configured.")
    if not (active_fy.start_date <= invoice.invoice_date <= active_fy.end_date):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot modify bill outside active financial year {active_fy.label}.",
        )

    lock = session.exec(
        select(MonthLock)
        .where(MonthLock.year == invoice.invoice_date.year)
        .where(MonthLock.month == invoice.invoice_date.month)
        .where(MonthLock.is_locked == True)
    ).first()
    if lock:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot record payment: {invoice.invoice_date.strftime('%B %Y')} is locked for GST filing.",
        )

    data         = await request.json()
    paid_now = _money(data.get("amount", 0))
    if paid_now <= 0:
        return JSONResponse(status_code=400, content={"success": False, "error": "Payment amount must be greater than zero."})
    mode         = data.get("mode", "cash")
    reference_no = data.get("reference_no", "")

    # FIX 15: give clear feedback when bill is already fully paid
    max_payable = _money(Decimal(str(invoice.grand_total)) - Decimal(str(invoice.amount_paid)))
    if max_payable <= 0:
        return JSONResponse(status_code=400, content={
            "success": False, "error": "Bill is already fully paid."
        })
    if paid_now > max_payable:
        paid_now = max_payable

    from app.models.payments import CreditPayment
    if invoice.party_id:
        session.add(CreditPayment(
            invoice_id   = invoice_id,
            party_id     = invoice.party_id,
            credit_date  = date.today(),
            amount       = paid_now,
            mode         = mode,
            reference_no = reference_no,
        ))

    invoice.amount_paid    = _money(Decimal(str(invoice.amount_paid)) + Decimal(str(paid_now)))
    invoice.amount_due     = max(0.0, _money(Decimal(str(invoice.grand_total)) - Decimal(str(invoice.amount_paid))))
    invoice.payment_status = (
        "paid"    if invoice.amount_paid >= invoice.grand_total else
        "partial" if invoice.amount_paid > 0 else
        "unpaid"
    )
    session.add(invoice)
    session.commit()
    return {"success": True, "payment_status": invoice.payment_status, "amount_due": invoice.amount_due}


# ── DUPLICATE ─────────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/duplicate")
def duplicate_bill(invoice_id: int, session: Session = Depends(get_session)):
    try:
        new_invoice = duplicate_invoice(session, invoice_id)
        return {"success": True, "invoice_id": new_invoice.id, "invoice_number": new_invoice.invoice_number}
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── CREDIT / DEBIT NOTE ───────────────────────────────────────────────────────

@router.get("/{invoice_id}/credit-note", response_class=HTMLResponse)
def credit_note_form(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    original = session.get(Invoice, invoice_id)
    if not original:
        raise HTTPException(status_code=404, detail="Bill not found")
    items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all()
    party = session.get(Party, original.party_id) if original.party_id else None
    return templates.TemplateResponse(
        request=request, name="invoices/credit_note.html",
        context={"original": original, "items": items, "party": party, "today": date.today().isoformat()}
    )


@router.post("/{invoice_id}/credit-note")
async def credit_note_submit(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    data = await request.json()
    try:
        original = session.get(Invoice, invoice_id)
        if not original:
            raise HTTPException(status_code=404, detail="Original bill not found")

        items = []
        for item in data.get("items", []):
            items.append(InvoiceItemCreate(
                item_name      = item["item_name"],
                weight_grams   = float(item["weight_grams"])   if item.get("weight_grams")   else None,
                rate_per_gram  = float(item["rate_per_gram"])  if item.get("rate_per_gram")  else None,
                making_charges = float(item["making_charges"]) if item.get("making_charges") else None,
                gst_rate       = float(item.get("gst_rate", 3.0)),
                purity         = item.get("purity") or None,
                huid           = item.get("huid")   or None,
                hsn_code       = item.get("hsn_code") or "7113",
            ))

        note_type    = data.get("note_type", "credit_note")
        invoice_data = InvoiceCreate(
            invoice_type   = note_type,
            bill_category  = "cash",
            party_id       = original.party_id,
            invoice_date   = date.fromisoformat(data["invoice_date"]),
            ref_invoice_id = invoice_id,
            notes          = data.get("notes") or f"Against {original.invoice_number}",
            items          = items,
        )
        invoice = create_invoice(session, invoice_data)
        return {"success": True, "invoice_id": invoice.id, "invoice_number": invoice.invoice_number}

    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"success": False, "error": e.detail})
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})


# ── MARK GST READY ────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/mark-gst-ready")
def mark_gst_ready(invoice_id: int, session: Session = Depends(get_session)):
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    invoice.gst_status = "gst_ready"
    session.add(invoice)
    session.commit()
    return {"success": True, "gst_status": invoice.gst_status}


# ── CANCEL ────────────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/cancel")
async def cancel_bill(invoice_id: int, request: Request, session: Session = Depends(get_session)):
    data   = await request.json()
    reason = data.get("reason", "")
    cancel_invoice(session, invoice_id, reason)
    return {"success": True}


# ── RECOVER ───────────────────────────────────────────────────────────────────

@router.post("/{invoice_id}/recover")
async def recover_bill(invoice_id: int, session: Session = Depends(get_session)):
    recover_invoice(session, invoice_id)
    return {"success": True}
