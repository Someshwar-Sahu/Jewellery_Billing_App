from sqlmodel import Session, select
from app.models.invoices import Invoice, InvoiceItem, InvoiceVersion, InvoiceEditLog
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate
from app.models.parties import OldGoldExchange, Party
from app.models.inventory import StockLedger
from datetime import datetime, date
from fastapi import HTTPException
import json
from app.models.system import MonthLock
from app.models.shop import FinancialYear, ShopSettings
from decimal import Decimal, ROUND_HALF_UP
from app.models.payments import Advance, CashAccount, AdvanceApplication, PaymentEvent
from sqlalchemy.exc import IntegrityError

CANCEL_GST_SNAPSHOT = "cancel_gst_snapshot"


def _d(value) -> Decimal:
    return Decimal(str(value if value is not None else 0))


def _money(value) -> float:
    return float(_d(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _active_fy(session: Session) -> FinancialYear:
    fy = session.exec(select(FinancialYear).where(FinancialYear.is_active == True)).first()
    if not fy:
        raise HTTPException(status_code=400, detail="No active financial year configured.")
    return fy


def _ensure_date_in_active_fy(session: Session, bill_date: date):
    fy = _active_fy(session)
    if not (fy.start_date <= bill_date <= fy.end_date):
        raise HTTPException(
            status_code=400,
            detail=f"Date {bill_date.isoformat()} is outside active financial year {fy.label}.",
        )


def _ensure_month_unlocked(session: Session, bill_date: date, action: str):
    lock = session.exec(
        select(MonthLock)
        .where(MonthLock.year == bill_date.year)
        .where(MonthLock.month == bill_date.month)
        .where(MonthLock.is_locked == True)
    ).first()
    if lock:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot {action}: {bill_date.strftime('%B %Y')} is locked for GST filing.",
        )

def calculate_item(item_data) -> dict:
    """Calculate all amounts for one invoice line item."""
    weight   = item_data.weight_grams  or 0
    rate     = item_data.rate_per_gram or 0
    gst_rate = item_data.gst_rate if item_data.gst_rate is not None else 3.0
    making   = item_data.making_charges or 0

    amount      = _money(_d(weight) * _d(rate)) if (weight and rate) else 0.0
    cgst_rate   = _d(gst_rate) / _d(2)
    cgst_amount = _money(_d(amount) * cgst_rate / _d(100))
    sgst_amount = cgst_amount   

    making_gst_rate = getattr(item_data, 'making_gst_rate', 18.0) or 18.0
    making_cgst = _money(_d(making) * (_d(making_gst_rate) / _d(2)) / _d(100)) if making else 0.0
    making_sgst = making_cgst

    line_total = _money(
        _d(amount) + _d(cgst_amount) + _d(sgst_amount) + _d(making) + _d(making_cgst) + _d(making_sgst)
    )

    return {
        "amount":      amount,
        "cgst_amount": cgst_amount,
        "sgst_amount": sgst_amount,
        "igst_amount": 0.0,
        "making_cgst": making_cgst,
        "making_sgst": making_sgst,
        "line_total":  line_total,
    }


def get_next_invoice_number(session: Session, invoice_type: str) -> str:
    """Generate next sequential invoice number for the active financial year."""
    fy_label = _active_fy(session).label

    prefix_map = {
        "sale":        f"S/{fy_label}/",
        "purchase":    f"P/{fy_label}/",
        "credit_note": f"CR/{fy_label}/",
        "debit_note":  f"DR/{fy_label}/",
    }
    prefix = prefix_map.get(invoice_type, f"INV/{fy_label}/")

    last = session.exec(
        select(Invoice)
        .where(Invoice.invoice_number.startswith(prefix))
        .order_by(Invoice.id.desc())
        .with_for_update()
    ).first()

    if last:
        try:
            last_num = int(last.invoice_number.split("/")[-1])
            next_num = last_num + 1
        except Exception:
            next_num = 1
    else:
        next_num = 1

    return f"{prefix}{str(next_num).zfill(4)}"


def _build_totals(calculated_items, items_to_calc, old_gold_value: float, discount: float, amount_paid: float):
    """Shared total calculation used by create and update."""
    subtotal          = Decimal("0")
    total_cgst        = Decimal("0")
    total_sgst        = Decimal("0")
    total_making      = Decimal("0")
    total_making_cgst = Decimal("0")
    total_making_sgst = Decimal("0")

    for item_data, calc in calculated_items:
        subtotal          += _d(calc["amount"])
        total_cgst        += _d(calc["cgst_amount"])
        total_sgst        += _d(calc["sgst_amount"])
        total_making      += _d(item_data.making_charges or 0)
        total_making_cgst += _d(calc["making_cgst"])
        total_making_sgst += _d(calc["making_sgst"])

    gross = subtotal + total_cgst + total_sgst + total_making + total_making_cgst + total_making_sgst
    gross = gross - _d(old_gold_value) - _d(discount)
    gross = max(Decimal("0"), gross)
    round_off = _d(round(gross) - gross)
    grand_total = gross + round_off
    amount_due = max(Decimal("0"), grand_total - _d(amount_paid))

    if _d(amount_paid) >= grand_total:
        payment_status = "paid"
    elif _d(amount_paid) > 0:
        payment_status = "partial"
    else:
        payment_status = "unpaid"

    return {
        "subtotal":          _money(subtotal),
        "total_cgst":        _money(total_cgst),
        "total_sgst":        _money(total_sgst),
        "total_making":      _money(total_making),
        "total_making_cgst": _money(total_making_cgst),
        "total_making_sgst": _money(total_making_sgst),
        "round_off":         _money(round_off),
        "grand_total":       _money(grand_total),
        "amount_due":        _money(amount_due),
        "payment_status":    payment_status,
    }


def create_invoice(session: Session, data: InvoiceCreate) -> Invoice:
    """Create a full invoice with items and calculated totals."""
    _ensure_date_in_active_fy(session, data.invoice_date)
    _ensure_month_unlocked(session, data.invoice_date, "create invoice")

    if data.party_id:
        party = session.get(Party, data.party_id)
        shop = session.exec(select(ShopSettings)).first()
        if party and shop and party.state and shop.state:
            if party.state.strip().lower() != shop.state.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail="Interstate invoices are not supported. Party state must match shop state."
                )

    calculated_items = []
    for item_data in data.items:
        calc = calculate_item(item_data)
        calculated_items.append((item_data, calc))

    effective_paid = (data.amount_paid or 0) + (data.advance_used or 0)

    totals = _build_totals(
        calculated_items,
        data.items,
        data.old_gold_value,
        data.discount,
        effective_paid,
    )

    if _d(effective_paid) > _d(totals["grand_total"]) + _d("0.01"):
        raise HTTPException(
            status_code=400,
            detail="Total settlement exceeds invoice amount."
        )

    amount_paid = _money(_d(data.amount_paid or 0))
    amount_due = max(
        0.0,
        _money(_d(totals["grand_total"]) - _d(effective_paid))
    )

    for attempt in range(3):
        try:
            invoice = Invoice(
                invoice_number       = get_next_invoice_number(session, data.invoice_type.value),
                invoice_type         = data.invoice_type.value,
                bill_category        = data.bill_category.value,
                party_id             = data.party_id,
                financial_year_id    = _active_fy(session).id,
                ref_invoice_id       = data.ref_invoice_id,
                invoice_date         = data.invoice_date,
                credit_due_date      = data.credit_due_date,
                place_of_supply      = data.place_of_supply,
                party_gstin          = data.party_gstin,
                subtotal             = totals["subtotal"],
                total_cgst           = totals["total_cgst"],
                total_sgst           = totals["total_sgst"],
                total_making_charges = totals["total_making"],
                making_cgst          = totals["total_making_cgst"],
                making_sgst          = totals["total_making_sgst"],
                old_gold_value       = data.old_gold_value,
                discount             = data.discount,
                round_off            = totals["round_off"],
                grand_total          = totals["grand_total"],
                amount_paid          = amount_paid,
                amount_due           = amount_due,
                payment_mode         = data.payment_mode.value if data.payment_mode else None,
                payment_reference    = data.payment_reference or None,
                payment_status       = totals["payment_status"],
                notes                = data.notes,
            )
            session.add(invoice)
            session.flush()

            for idx, (item_data, calc) in enumerate(calculated_items):
                item = InvoiceItem(
                    invoice_id     = invoice.id,
                    product_id     = item_data.product_id,
                    item_name      = item_data.item_name,
                    hsn_code       = item_data.hsn_code or "7113",
                    purity         = item_data.purity,
                    huid           = item_data.huid,
                    weight_grams   = item_data.weight_grams,
                    rate_per_gram  = item_data.rate_per_gram,
                    quantity       = item_data.quantity,
                    unit           = item_data.unit,
                    amount         = calc["amount"],
                    making_charges = item_data.making_charges,
                    gst_rate       = item_data.gst_rate,
                    cgst_amount    = calc["cgst_amount"],
                    sgst_amount    = calc["sgst_amount"],
                    igst_amount    = calc["igst_amount"],
                    making_cgst    = calc["making_cgst"],
                    making_sgst    = calc["making_sgst"],
                    line_total     = calc["line_total"],
                    description    = item_data.description,
                    sort_order     = item_data.sort_order if item_data.sort_order else idx,
                )
                session.add(item)

            snapshot = {
                "event":          "created",
                "invoice_number": invoice.invoice_number,
                "grand_total":    totals["grand_total"],
                "amount_paid":    amount_paid,
                "advance_used":   float(data.advance_used or 0),
                "amount_due":     amount_due,
                "payment_status": totals["payment_status"],
                "items_count":    len(calculated_items),
                "party_name":     session.get(__import__('app.models.parties', fromlist=['Party']).Party, data.party_id).name if data.party_id else None,
                "saved_at":       datetime.utcnow().isoformat(),
            }

            version = InvoiceVersion(
                invoice_id     = invoice.id,
                version_number = 1,
                snapshot       = json.dumps(snapshot),
            )
            session.add(version)
            
            if amount_paid > 0 and data.payment_mode:
                mode_val = data.payment_mode.value if hasattr(data.payment_mode, "value") else str(data.payment_mode)
                # For "mixed" mode, record under "mixed" — user can split later
                cash_entry = CashAccount(
                    entry_date   = data.invoice_date,
                    entry_type   = "receipt" if data.invoice_type.value == "sale" else "payment",
                    mode         = mode_val,
                    amount       = amount_paid,
                    reference_no = data.payment_reference or None,
                    party_id     = data.party_id or None,
                    invoice_id   = invoice.id,
                    description  = f"{'Sale' if data.invoice_type.value == 'sale' else 'Purchase'} — {invoice.invoice_number}",
                )
                session.add(cash_entry)
            
            if (
                data.old_gold_value and data.old_gold_value > 0
                and data.party_id
                and data.old_gold_weight and data.old_gold_weight > 0
            ):
                old_gold_entry = OldGoldExchange(
                    party_id         = data.party_id,
                    sale_invoice_id  = invoice.id,
                    exchange_date    = data.invoice_date,
                    transaction_type = "exchange",
                    metal_type       = (
                        data.old_gold_metal_type.value
                        if hasattr(data.old_gold_metal_type, "value")
                        else str(data.old_gold_metal_type)
                    ),
                    purity           = data.old_gold_purity,
                    weight_grams     = data.old_gold_weight,
                    rate_per_gram    = data.old_gold_rate or 0.0,
                    total_value      = data.old_gold_value,
                )
                session.add(old_gold_entry)

            is_stock_out = data.invoice_type.value in ["sale", "debit_note"]
            is_stock_in = data.invoice_type.value in ["purchase", "credit_note"]

            for item_data, calc in calculated_items:
                if not item_data.product_id:
                    continue

                stock_qty = (
                    item_data.weight_grams
                    if item_data.weight_grams
                    else (item_data.quantity or 1.0)
                )

                stock_entry = StockLedger(
                    product_id       = item_data.product_id,
                    stock_date       = data.invoice_date,
                    transaction_type = data.invoice_type.value,
                    invoice_id       = invoice.id,
                    quantity_in      = stock_qty if is_stock_in else 0.0,
                    quantity_out     = stock_qty if is_stock_out else 0.0,
                    balance          = 0.0,
                    rate             = item_data.rate_per_gram,
                    notes            = f"Auto from invoice {invoice.invoice_number}",
                )
                session.add(stock_entry)

            advance_used = float(data.advance_used or 0)

            if advance_used > 0 and data.party_id:
                open_advances = session.exec(
                    select(Advance)
                    .where(Advance.party_id == data.party_id)
                    .where(Advance.status == "open")
                    .order_by(Advance.advance_date)
                ).all()

                remaining = advance_used

                for adv in open_advances:
                    if remaining <= 0.0:
                        break

                    available = max(0.0, adv.amount - adv.adjusted_amount)
                    use = min(available, remaining)

                    adv.adjusted_amount = _money(
                        _d(adv.adjusted_amount) + _d(use)
                    )

                    if adv.adjusted_amount >= adv.amount:
                        adv.status = "used"

                    session.add(adv)

                    app_row = AdvanceApplication(
                        advance_id     = adv.id,
                        invoice_id     = invoice.id,
                        party_id       = data.party_id,
                        amount_applied = use,
                        applied_date   = data.invoice_date,
                        created_at     = datetime.utcnow(),
                    )
                    session.add(app_row)
                    session.flush()

                    session.add(PaymentEvent(
                        invoice_id              = invoice.id,
                        party_id                = data.party_id,
                        event_date              = data.invoice_date,
                        amount                  = use,
                        mode                    = "advance",
                        payment_type            = "advance",
                        advance_application_id  = app_row.id,
                        created_at              = datetime.utcnow(),
                    ))

                    remaining = _money(_d(remaining) - _d(use))

                actually_deducted = _money(_d(advance_used) - _d(remaining))

                if actually_deducted < advance_used - 0.01:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Insufficient advance balance. "
                            f"Only ₹{actually_deducted:.2f} available."
                        )
                    )

                invoice.advance_used = actually_deducted

            if amount_paid > 0 and data.payment_mode:
                session.add(PaymentEvent(
                    invoice_id   = invoice.id,
                    party_id     = data.party_id or None,
                    event_date   = data.invoice_date,
                    amount       = amount_paid,
                    mode         = data.payment_mode.value if hasattr(data.payment_mode, "value") else str(data.payment_mode),
                    payment_type = "cash",
                    created_at   = datetime.utcnow(),
                ))

            if data.old_gold_value and data.old_gold_value > 0:
                session.add(PaymentEvent(
                    invoice_id   = invoice.id,
                    party_id     = data.party_id or None,
                    event_date   = data.invoice_date,
                    amount       = data.old_gold_value,
                    mode         = "old_gold",
                    payment_type = "old_gold",
                    created_at   = datetime.utcnow(),
                ))
            session.commit()
            session.refresh(invoice)
            return invoice

        except IntegrityError as exc:
            session.rollback()

            if attempt < 2 and "uq_invoices_invoice_number" in str(exc):
                continue

            raise

        except Exception:
            session.rollback()
            raise

def update_invoice(session: Session, invoice_id: int, data: InvoiceUpdate) -> Invoice:
    """Edit an existing bill — saves version snapshot, logs changes, recalculates totals."""

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    if invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot edit a cancelled bill")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "edit invoice")

    if invoice.party_id:
        party = session.get(Party, invoice.party_id)
        shop = session.exec(select(ShopSettings)).first()
        if party and shop and party.state and shop.state:
            if party.state.strip().lower() != shop.state.strip().lower():
                raise HTTPException(
                    status_code=400,
                    detail="Interstate invoices are not supported. Party state must match shop state."
                )

    current_items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    snapshot = {
        "invoice_number": invoice.invoice_number,
        "grand_total":    invoice.grand_total,
        "items":          [i.item_name for i in current_items],
        "saved_at":       datetime.utcnow().isoformat(),
        "reason":         data.edit_reason or "manual edit",
    }
    
    version = InvoiceVersion(
        invoice_id     = invoice_id,
        version_number = invoice.version_number,   
        snapshot       = json.dumps(snapshot),
    )
    session.add(version)
    invoice.version_number += 1  

    def log_change(field: str, old_val: str, new_val: str):
        if old_val != new_val:
            session.add(InvoiceEditLog(
                invoice_id    = invoice_id,
                field_changed = field,
                old_value     = old_val,
                new_value     = new_val,
                reason        = data.edit_reason,
                edited_at     = datetime.utcnow(),
            ))

    allowed_fields = {"invoice_date", "credit_due_date", "payment_mode",
                      "old_gold_value", "discount", "notes"}
    update_data = data.model_dump(exclude_unset=True, exclude_none=True)

    for field in allowed_fields:
        if field not in update_data:
            continue
        value   = update_data[field]
        old_val = getattr(invoice, field, None)
        if hasattr(value, "value"):
            value = value.value

        if hasattr(old_val, "value"):
            old_val = old_val.value

        str_old = str(old_val) if old_val is not None else ""
        str_new = str(value) if value is not None else ""

        if str_old != str_new:
            log_change(field, str_old, str_new)
            setattr(invoice, field, value)
            
            # Close time-travel loophole: re-validate the new date
            if field == "invoice_date" and value:
                _ensure_date_in_active_fy(session, value)
                _ensure_month_unlocked(session, value, "edit invoice to new date")

    if data.items is not None and len(data.items) > 0:
        for old_item in current_items:
            session.delete(old_item)
            
        old_stock = session.exec(
            select(StockLedger).where(StockLedger.invoice_id == invoice_id)
        ).all()
        for os in old_stock:
            session.delete(os)
            
        session.flush()
        items_to_calc    = data.items
        saving_new_items = True
    else:
        items_to_calc    = current_items
        saving_new_items = False

    calculated_items = []
    for item_data in items_to_calc:
        calc = calculate_item(item_data)
        calculated_items.append((item_data, calc))

    if saving_new_items:
        for idx, (item_data, calc) in enumerate(calculated_items):
            session.add(InvoiceItem(
                invoice_id     = invoice_id,
                product_id     = item_data.product_id,
                item_name      = item_data.item_name,
                hsn_code       = item_data.hsn_code or "7113",
                purity         = item_data.purity,
                huid           = item_data.huid,       
                weight_grams   = item_data.weight_grams,
                rate_per_gram  = item_data.rate_per_gram,
                quantity       = item_data.quantity,
                unit           = item_data.unit,
                amount         = calc["amount"],
                making_charges = item_data.making_charges,
                gst_rate       = item_data.gst_rate,
                cgst_amount    = calc["cgst_amount"],
                sgst_amount    = calc["sgst_amount"],
                igst_amount    = calc["igst_amount"],
                making_cgst    = calc["making_cgst"],
                making_sgst    = calc["making_sgst"],
                line_total     = calc["line_total"],
                description    = item_data.description,
                sort_order     = item_data.sort_order if item_data.sort_order else idx,
            ))

        is_stock_out = invoice.invoice_type in ["sale", "debit_note"]
        is_stock_in = invoice.invoice_type in ["purchase", "credit_note"]

        for item_data, calc in calculated_items:
            if not item_data.product_id:
                continue

            stock_qty = (
                item_data.weight_grams
                if item_data.weight_grams
                else (item_data.quantity or 1.0)
            )

            stock_entry = StockLedger(
                product_id       = item_data.product_id,
                stock_date       = invoice.invoice_date,
                transaction_type = invoice.invoice_type,
                invoice_id       = invoice_id,
                quantity_in      = stock_qty if is_stock_in else 0.0,
                quantity_out     = stock_qty if is_stock_out else 0.0,
                balance          = 0.0,
                rate             = item_data.rate_per_gram,
                notes            = f"Auto updated from invoice {invoice.invoice_number}",
            )
            session.add(stock_entry)

    old_gold = data.old_gold_value if data.old_gold_value is not None else invoice.old_gold_value
    discount  = data.discount      if data.discount      is not None else invoice.discount

    totals = _build_totals(
        calculated_items,
        items_to_calc,
        old_gold,
        discount,
        (invoice.amount_paid or 0) + (invoice.advance_used or 0)
    )

    effective_paid = _d(invoice.amount_paid or 0) + _d(invoice.advance_used or 0)

    if effective_paid > _d(totals["grand_total"]) + _d("0.01"):
        raise HTTPException(
            status_code=400,
            detail="Existing payment exceeds updated invoice total."
        )

    new_grand_total = totals["grand_total"]
    log_change("grand_total", str(invoice.grand_total), str(new_grand_total))

    if new_grand_total < invoice.grand_total and (invoice.advance_used or 0) > 0:
        excess = _money(_d(invoice.advance_used) - max(_d(0), _d(new_grand_total) - _d(invoice.amount_paid or 0)))
        if excess > 0:
            apps = session.exec(
                select(AdvanceApplication)
                .where(AdvanceApplication.invoice_id == invoice.id)
                .order_by(AdvanceApplication.advance_id.desc())
            ).all()
            remaining_excess = excess
            for app_row in apps:
                if remaining_excess <= 0:
                    break
                release = min(app_row.amount_applied, remaining_excess)
                adv = session.get(Advance, app_row.advance_id)
                if adv:
                    adv.adjusted_amount = _money(_d(adv.adjusted_amount) - _d(release))
                    adv.status = "open"
                    session.add(adv)
                app_row.amount_applied = _money(_d(app_row.amount_applied) - _d(release))
                if app_row.amount_applied <= 0:
                    session.delete(app_row)
                else:
                    session.add(app_row)
                remaining_excess = _money(_d(remaining_excess) - _d(release))
            invoice.advance_used = _money(_d(invoice.advance_used) - _d(excess))

    invoice.subtotal             = totals["subtotal"]
    invoice.total_cgst           = totals["total_cgst"]
    invoice.total_sgst           = totals["total_sgst"]
    invoice.total_making_charges = totals["total_making"]
    invoice.making_cgst          = totals["total_making_cgst"]
    invoice.making_sgst          = totals["total_making_sgst"]
    invoice.round_off            = totals["round_off"]
    invoice.grand_total          = totals["grand_total"]
    invoice.amount_due           = totals["amount_due"]
    invoice.payment_status       = totals["payment_status"]

    if invoice.gst_status == "gst_ready":
        invoice.gst_status = "pending_review"

    invoice.updated_at = datetime.utcnow()
    session.add(invoice)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(invoice)
    return invoice


def duplicate_invoice(session: Session, invoice_id: int) -> Invoice:
    """Duplicate an existing bill — creates a fresh bill with today's date and new number."""
    original = session.get(Invoice, invoice_id)
    if not original:
        raise HTTPException(status_code=404, detail="Bill not found")

    original_items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceType, BillCategory, PaymentMode

    items = []
    for item in original_items:
        items.append(InvoiceItemCreate(
            item_name      = item.item_name,
            product_id     = item.product_id,
            hsn_code       = item.hsn_code,
            purity         = item.purity,
            huid           = None,  
            weight_grams   = item.weight_grams,
            rate_per_gram  = item.rate_per_gram,
            quantity       = item.quantity,
            unit           = item.unit,
            making_charges = item.making_charges,
            gst_rate       = item.gst_rate,
            description    = item.description,
            sort_order     = item.sort_order,
        ))

    new_data = InvoiceCreate(
        invoice_type   = InvoiceType(original.invoice_type),
        bill_category  = BillCategory(original.bill_category),
        party_id       = original.party_id,
        invoice_date   = date.today(),
        credit_due_date = date.today() if original.bill_category == 'credit' else None,
        place_of_supply = original.place_of_supply,
        party_gstin    = original.party_gstin,
        payment_mode   = PaymentMode(original.payment_mode) if original.payment_mode else None,
        amount_paid    = 0.0,
        old_gold_value = original.old_gold_value,
        old_gold_metal_type = "gold",
        discount       = original.discount,
        notes          = f"Duplicated from {original.invoice_number}",
        items          = items,
    )
    return create_invoice(session, new_data)


def cancel_invoice(session: Session, invoice_id: int, reason: str = None) -> Invoice:
    """Cancel a bill — never hard delete."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "cancel invoice")

    try:
        cash_entries = session.exec(select(CashAccount).where(CashAccount.invoice_id == invoice_id)).all()
        for ce in cash_entries:
            reversal_ce = CashAccount(
                entry_date   = date.today(),
                entry_type   = "payment" if ce.entry_type == "receipt" else "receipt",
                mode         = ce.mode,
                amount       = ce.amount,
                reference_no = ce.reference_no,
                party_id     = ce.party_id,
                invoice_id   = invoice_id,
                description  = f"Reversal for cancelled invoice {invoice.invoice_number}"
            )
            session.add(reversal_ce)

        old_gold_entries = session.exec(select(OldGoldExchange).where(OldGoldExchange.sale_invoice_id == invoice_id)).all()
        for oge in old_gold_entries:
            session.delete(oge)
            
        payment_events = session.exec(select(PaymentEvent).where(PaymentEvent.invoice_id == invoice_id)).all()
        for pe in payment_events:
            session.delete(pe)

        advance_to_restore = invoice.advance_used or 0
        if advance_to_restore > 0 and invoice.party_id:
            apps = session.exec(
                select(AdvanceApplication)
                .where(AdvanceApplication.invoice_id == invoice_id)
                .order_by(AdvanceApplication.advance_id.desc())
            ).all()
            for app_row in apps:
                adv = session.get(Advance, app_row.advance_id)
                if adv:
                    adv.adjusted_amount = _money(_d(adv.adjusted_amount) - _d(app_row.amount_applied))
                    adv.status = "open"
                    session.add(adv)
                session.delete(app_row)

        items = session.exec(
            select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
        ).all()

        is_stock_out     = invoice.invoice_type in ["sale", "debit_note"]
        is_stock_in      = invoice.invoice_type in ["purchase", "credit_note"]

        for item in items:
            if not item.product_id:
                continue
            reversal_qty = item.weight_grams if item.weight_grams else (item.quantity or 1.0)
            reversal = StockLedger(
                product_id       = item.product_id,
                stock_date       = date.today(),
                transaction_type = "adjustment",
                invoice_id       = invoice_id,
                quantity_in      = reversal_qty if is_stock_out else 0.0,
                quantity_out     = reversal_qty if is_stock_in else 0.0,
                balance          = 0.0,
                rate             = item.rate_per_gram,
                notes            = f"Reversal: bill {invoice.invoice_number} cancelled",
            )
            session.add(reversal)

        prev_gst = invoice.gst_status
        if prev_gst in ("gst_ready", "locked"):
            session.add(
                InvoiceEditLog(
                    invoice_id=invoice_id,
                    field_changed=CANCEL_GST_SNAPSHOT,
                    old_value=prev_gst,
                    new_value="pending_review",
                    reason=reason,
                )
            )
            invoice.gst_status = "pending_review"

        invoice.is_cancelled     = True
        invoice.cancelled_at     = datetime.utcnow()
        invoice.cancelled_reason = reason
        session.add(invoice)
        session.commit()
        session.refresh(invoice)
        return invoice

    except Exception:
        session.rollback()
        raise


def recover_invoice(session: Session, invoice_id: int) -> Invoice:
    """Recover a cancelled bill back to active."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    if not invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Bill is not cancelled.")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "recover invoice")

    snap = session.exec(
        select(InvoiceEditLog)
        .where(InvoiceEditLog.invoice_id == invoice_id)
        .where(InvoiceEditLog.field_changed == CANCEL_GST_SNAPSHOT)
        .order_by(InvoiceEditLog.edited_at.desc())
    ).first()
    if snap:
        session.delete(snap)
    invoice.gst_status = "pending_review"

    items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    is_sale     = invoice.invoice_type in ["sale", "debit_note"]
    is_purchase = invoice.invoice_type in ["purchase", "credit_note"]

    for item in items:
        if not item.product_id:
            continue
        re_apply_qty = item.weight_grams if item.weight_grams else (item.quantity or 1.0)
        re_entry = StockLedger(
            product_id       = item.product_id,
            stock_date       = invoice.invoice_date,   
            transaction_type = invoice.invoice_type,
            invoice_id       = invoice_id,
            quantity_in      = re_apply_qty if is_purchase else 0.0,
            quantity_out     = re_apply_qty if is_sale     else 0.0,
            balance          = 0.0,
            rate             = item.rate_per_gram,
            notes            = f"Re-applied: bill {invoice.invoice_number} recovered",
        )
        session.add(re_entry)

    if invoice.amount_paid and invoice.amount_paid > 0:
        session.add(PaymentEvent(
            invoice_id   = invoice.id,
            party_id     = invoice.party_id,
            event_date   = invoice.invoice_date,
            payment_type = "initial_payment",
            mode         = invoice.payment_mode or "cash",
            amount       = invoice.amount_paid,
            reference_no = invoice.payment_reference,
            notes        = f"Reinstated on bill recovery: {invoice.invoice_number}",
        ))
        session.add(CashAccount(
            entry_date   = date.today(),
            entry_type   = "receipt" if is_sale else "payment",
            mode         = invoice.payment_mode or "cash",
            amount       = invoice.amount_paid,
            reference_no = invoice.payment_reference,
            party_id     = invoice.party_id,
            invoice_id   = invoice.id,
            description  = f"Reinstated on recovery of {invoice.invoice_number}",
        ))

    invoice.is_cancelled     = False
    invoice.cancelled_at     = None
    invoice.cancelled_reason = None
    session.add(invoice)
    try:
        session.commit()
    except Exception:
        session.rollback()
        raise
    session.refresh(invoice)
    return invoice

def record_payment_event(
    session: Session,
    invoice_id: int,
    amount: float,
    mode: str,
    event_date: date = None,
    reference_no: str = None,
    notes: str = None,
) -> PaymentEvent:
    if event_date is None:
        event_date = date.today()

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    if invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot record payment on a cancelled bill.")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "record payment")

    amount = _money(amount)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero.")

    amount_due = _money(_d(invoice.grand_total) - _d(invoice.amount_paid) - _d(invoice.advance_used or 0))
    if amount > amount_due + 0.01:
        raise HTTPException(status_code=400, detail=f"Payment ₹{amount:.2f} exceeds amount due ₹{amount_due:.2f}.")

    if mode == "advance":
        if not invoice.party_id:
            raise HTTPException(status_code=400, detail="No party on invoice — cannot apply advance.")
        open_advances = session.exec(
            select(Advance)
            .where(Advance.party_id == invoice.party_id)
            .where(Advance.status == "open")
            .order_by(Advance.advance_date)
        ).all()
        available = _money(sum(_d(a.amount) - _d(a.adjusted_amount) for a in open_advances))
        if available < amount - 0.01:
            raise HTTPException(status_code=400, detail=f"Insufficient advance balance. Available: ₹{available:.2f}.")

        remaining = amount
        last_app_id = None
        for adv in open_advances:
            if remaining <= 0:
                break
            use = min(_money(_d(adv.amount) - _d(adv.adjusted_amount)), remaining)
            adv.adjusted_amount = _money(_d(adv.adjusted_amount) + _d(use))
            if adv.adjusted_amount >= adv.amount:
                adv.status = "used"
            session.add(adv)
            app_row = AdvanceApplication(
                advance_id     = adv.id,
                invoice_id     = invoice_id,
                party_id       = invoice.party_id,
                amount_applied = use,
                applied_date   = event_date,
                created_at     = datetime.utcnow(),
            )
            session.add(app_row)
            session.flush()
            last_app_id = app_row.id
            remaining = _money(_d(remaining) - _d(use))

        invoice.advance_used = _money(_d(invoice.advance_used or 0) + _d(amount))
        payment_type = "advance"
        pe = PaymentEvent(
            invoice_id             = invoice_id,
            party_id               = invoice.party_id,
            event_date             = event_date,
            amount                 = amount,
            mode                   = "advance",
            payment_type           = "advance",
            reference_no           = reference_no,
            advance_application_id = last_app_id,
            notes                  = notes,
            created_at             = datetime.utcnow(),
        )
    else:
        payment_type = "cash"
        session.add(CashAccount(
            entry_date   = event_date,
            entry_type   = "receipt" if invoice.invoice_type == "sale" else "payment",
            mode         = mode,
            amount       = amount,
            reference_no = reference_no or None,
            party_id     = invoice.party_id or None,
            invoice_id   = invoice_id,
            description  = f"Settlement — {invoice.invoice_number}",
        ))
        invoice.amount_paid = _money(_d(invoice.amount_paid) + _d(amount))
        pe = PaymentEvent(
            invoice_id   = invoice_id,
            party_id     = invoice.party_id or None,
            event_date   = event_date,
            amount       = amount,
            mode         = mode,
            payment_type = "cash",
            reference_no = reference_no,
            notes        = notes,
            created_at   = datetime.utcnow(),
        )

    session.add(pe)
    session.flush()

    invoice.amount_due = max(0.0, _money(
        _d(invoice.grand_total) - _d(invoice.amount_paid) - _d(invoice.advance_used or 0)
    ))
    invoice.payment_status = (
        "paid"    if invoice.amount_due <= 0 else
        "partial" if (invoice.amount_paid > 0 or (invoice.advance_used or 0) > 0) else
        "unpaid"
    )

    snapshot = {
        "event":          "payment",
        "invoice_number": invoice.invoice_number,
        "grand_total":    invoice.grand_total,
        "amount_paid":    invoice.amount_paid,
        "advance_used":   invoice.advance_used or 0,
        "amount_due":     invoice.amount_due,
        "payment_status": invoice.payment_status,
        "payment_type":   payment_type,
        "payment_mode":   mode,
        "payment_amount": amount,
        "saved_at":       datetime.utcnow().isoformat(),
    }
    session.add(InvoiceVersion(
        invoice_id     = invoice_id,
        version_number = invoice.version_number,
        snapshot       = json.dumps(snapshot),
    ))
    invoice.version_number += 1
    session.add(invoice)
    session.commit()
    session.refresh(pe)
    return pe

def get_unsettled_credit_bills(session: Session):
    """Return all credit bills not fully paid."""
    return session.exec(
        select(Invoice)
        .where(Invoice.bill_category == "credit")
        .where(Invoice.payment_status != "paid")
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.credit_due_date)
    ).all()


def get_pending_bills(session: Session) -> dict:
    """Return three separate lists for the Pending Payments page."""
    credit_sales = session.exec(
        select(Invoice)
        .where(Invoice.bill_category == "credit")
        .where(Invoice.invoice_type == "sale")
        .where(Invoice.payment_status != "paid")
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.credit_due_date)
    ).all()

    credit_purchases = session.exec(
        select(Invoice)
        .where(Invoice.bill_category == "credit")
        .where(Invoice.invoice_type == "purchase")
        .where(Invoice.payment_status != "paid")
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.credit_due_date)
    ).all()

    partial_bills = session.exec(
        select(Invoice)
        .where(Invoice.bill_category != "credit")
        .where(Invoice.payment_status.in_(["unpaid", "partial"]))
        .where(Invoice.is_cancelled == False)
        .order_by(Invoice.id.desc())
    ).all()

    return {
        "credit_sales":     credit_sales,
        "credit_purchases": credit_purchases,
        "partial_bills":    partial_bills,
    }
