from sqlmodel import Session, select
from app.models.invoices import Invoice, InvoiceItem, InvoiceVersion, InvoiceEditLog
from app.schemas.invoice import InvoiceCreate, InvoiceUpdate
from app.models.parties import OldGoldExchange
from app.models.inventory import GoldRate, StockLedger
from datetime import datetime, date
from fastapi import HTTPException
import json
from app.models.system import MonthLock
from app.models.shop import FinancialYear
from decimal import Decimal, ROUND_HALF_UP
from app.models.payments import Advance
from sqlalchemy.exc import IntegrityError


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
    gst_rate = item_data.gst_rate      or 3.0
    making   = item_data.making_charges or 0

    amount      = _money(_d(weight) * _d(rate)) if (weight and rate) else 0.0
    cgst_rate   = _d(gst_rate) / _d(2)
    cgst_amount = _money(_d(amount) * cgst_rate / _d(100))
    sgst_amount = cgst_amount   # always equal — intrastate only

    making_cgst = _money(_d(making) * _d(9) / _d(100)) if making else 0.0
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
    # FIX 11: floor amount_due at 0 — never show negative
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

    calculated_items = []
    for item_data in data.items:
        calc = calculate_item(item_data)
        calculated_items.append((item_data, calc))

    totals = _build_totals(
        calculated_items,
        data.items,
        data.old_gold_value,
        data.discount,
        data.amount_paid or 0,
    )

    amount_paid = min(data.amount_paid or 0, totals["grand_total"])
    amount_due = max(0.0, _money(_d(totals["grand_total"]) - _d(amount_paid)))

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
                "invoice_number": invoice.invoice_number,
                "grand_total":    totals["grand_total"],
                "items":          [i.item_name for i, _ in calculated_items],
                "saved_at":       datetime.utcnow().isoformat(),
            }

            version = InvoiceVersion(
                invoice_id     = invoice.id,
                version_number = 1,
                snapshot       = json.dumps(snapshot),
            )
            session.add(version)

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

            # Keep invoice + advance adjustment atomic in one transaction.
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

                    remaining = _money(_d(remaining) - _d(use))

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

    current_items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    # Snapshot captures state BEFORE any changes
    snapshot = {
        "invoice_number": invoice.invoice_number,
        "grand_total":    invoice.grand_total,
        "items":          [i.item_name for i in current_items],
        "saved_at":       datetime.utcnow().isoformat(),
        "reason":         data.edit_reason or "manual edit",
    }
    # FIX 8: save InvoiceVersion with OLD version number BEFORE incrementing
    version = InvoiceVersion(
        invoice_id     = invoice_id,
        version_number = invoice.version_number,   # preserves the pre-edit version label
        snapshot       = json.dumps(snapshot),
    )
    session.add(version)
    invoice.version_number += 1   # now increment

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

    # Replace items if new ones provided
    if data.items is not None and len(data.items) > 0:
        for old_item in current_items:
            session.delete(old_item)
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
                huid           = item_data.huid,       # FIX 9: huid preserved through edit
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

    old_gold = data.old_gold_value if data.old_gold_value is not None else invoice.old_gold_value
    discount  = data.discount      if data.discount      is not None else invoice.discount

    totals = _build_totals(calculated_items, items_to_calc, old_gold, discount, invoice.amount_paid or 0)

    log_change("grand_total", str(invoice.grand_total), str(totals["grand_total"]))

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
            huid           = None,  # HUID should not be duplicated — forces user to re-scan item if they want HUID on new bill
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
        # Duplicate keeps old_gold_weight=None so no OldGoldExchange is re-created (Mode A)
        old_gold_metal_type = "gold",
        discount       = original.discount,
        notes          = f"Duplicated from {original.invoice_number}",
        items          = items,
    )
    return create_invoice(session, new_data)


def cancel_invoice(session: Session, invoice_id: int, reason: str = None) -> Invoice:
    """Cancel a bill — never hard delete. FIX 10: reverses stock ledger entries."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "cancel invoice")

    # FIX 10: Reverse stock for product-linked items when bill is cancelled
    items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    is_stock_out     = invoice.invoice_type in ["sale", "debit_note"]
    is_stock_in      = invoice.invoice_type in ["purchase", "credit_note"]

    for item in items:
        if not item.product_id:
            continue
        # Reverse: if original was sale (qty_out), add a qty_in reversal; vice versa
        reversal_qty = item.weight_grams if item.weight_grams else (item.quantity or 1.0)
        reversal = StockLedger(
            product_id       = item.product_id,
            stock_date       = date.today(),
            transaction_type = "adjustment",
            invoice_id       = invoice_id,
            quantity_in      = reversal_qty if is_stock_out     else 0.0,
            quantity_out     = reversal_qty if is_stock_in else 0.0,
            balance          = 0.0,
            rate             = item.rate_per_gram,
            notes            = f"Reversal: bill {invoice.invoice_number} cancelled",
        )
        session.add(reversal)

    invoice.is_cancelled     = True
    invoice.cancelled_at     = datetime.utcnow()
    invoice.cancelled_reason = reason
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice


def recover_invoice(session: Session, invoice_id: int) -> Invoice:
    """Recover a cancelled bill back to active."""
    # BUG 1 FIX: fetch invoice FIRST before passing to guards
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    # BUG 5 FIX: only allow recovery if actually cancelled
    if not invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Bill is not cancelled.")

    _ensure_date_in_active_fy(session, invoice.invoice_date)
    _ensure_month_unlocked(session, invoice.invoice_date, "recover invoice")

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
            stock_date       = invoice.invoice_date,   # BUG 5 FIX: use original date not today
            transaction_type = invoice.invoice_type,
            invoice_id       = invoice_id,
            quantity_in      = re_apply_qty if is_purchase else 0.0,
            quantity_out     = re_apply_qty if is_sale     else 0.0,
            balance          = 0.0,
            rate             = item.rate_per_gram,
            notes            = f"Re-applied: bill {invoice.invoice_number} recovered",
        )
        session.add(re_entry)

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
