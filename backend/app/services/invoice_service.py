from sqlmodel import Session, select
from app.models.invoices import Invoice, InvoiceItem, InvoiceVersion,InvoiceEditLog
from app.schemas.invoice import InvoiceCreate,InvoiceUpdate
from app.models.parties import OldGoldExchange
from app.models.inventory import GoldRate, StockLedger
from datetime import datetime, date
from fastapi import HTTPException
import json

def calculate_item(item_data) -> dict:
    """Calculate all amounts for one invoice line item."""

    weight  = item_data.weight_grams or 0
    rate    = item_data.rate_per_gram or 0
    gst_rate = item_data.gst_rate or 3.0
    making  = item_data.making_charges or 0   # FIX: was making_charge (missing s)

    if weight and rate:
        amount = round(weight * rate, 2)
    else:
        amount = 0.0

    cgst_rate   = gst_rate / 2
    sgst_rate   = gst_rate / 2
    cgst_amount = round(amount * cgst_rate / 100, 2)
    sgst_amount = round(amount * sgst_rate / 100, 2)

    # Making charges: 18% GST split 9% CGST + 9% SGST
    making_cgst = round(making * 9 / 100, 2) if making else 0.0
    making_sgst = round(making * 9 / 100, 2) if making else 0.0

    line_total = round(
        amount + cgst_amount + sgst_amount + making + making_cgst + making_sgst, 2
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
    from app.models.shop import FinancialYear

    fy = session.exec(
        select(FinancialYear).where(FinancialYear.is_active == True)
    ).first()
    fy_label = fy.label if fy else "24-25"

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

def create_invoice(session: Session, data: InvoiceCreate) -> Invoice:
    """Create a full invoice with items and calculated totals."""

    calculated_items = []
    subtotal           = 0.0
    total_cgst         = 0.0
    total_sgst         = 0.0
    total_making       = 0.0
    total_making_cgst  = 0.0
    total_making_sgst  = 0.0

    for item_data in data.items:
        calc = calculate_item(item_data)
        calculated_items.append((item_data, calc))
        subtotal          += calc["amount"]
        total_cgst        += calc["cgst_amount"]
        total_sgst        += calc["sgst_amount"]
        total_making      += item_data.making_charges or 0   # FIX: was making_charge
        total_making_cgst += calc["making_cgst"]
        total_making_sgst += calc["making_sgst"]

    gross      = subtotal + total_cgst + total_sgst + total_making + total_making_cgst + total_making_sgst
    gross      = gross - data.old_gold_value - data.discount
    round_off  = round(round(gross) - gross, 2)
    grand_total = round(gross + round_off, 2)
    amount_due  = round(grand_total - (data.amount_paid or 0), 2)

    if (data.amount_paid or 0) >= grand_total:
        payment_status = "paid"
    elif (data.amount_paid or 0) > 0:
        payment_status = "partial"
    else:
        payment_status = "unpaid"

    invoice = Invoice(
        invoice_number    = get_next_invoice_number(session, data.invoice_type.value),
        invoice_type      = data.invoice_type.value,
        bill_category     = data.bill_category.value,
        party_id          = data.party_id,
        ref_invoice_id    =data.ref_invoice_id,
        invoice_date      = data.invoice_date,
        credit_due_date   = data.credit_due_date,
        place_of_supply   = data.place_of_supply,
        party_gstin       = data.party_gstin,
        subtotal          = round(subtotal, 2),
        total_cgst        = round(total_cgst, 2),
        total_sgst        = round(total_sgst, 2),
        total_making_charges = round(total_making, 2),
        making_cgst       = round(total_making_cgst, 2),
        making_sgst       = round(total_making_sgst, 2),
        old_gold_value    = data.old_gold_value,
        discount          = data.discount,
        round_off         = round_off,
        grand_total       = grand_total,
        amount_paid       = data.amount_paid or 0,
        amount_due        = amount_due,
        payment_mode      = data.payment_mode.value if data.payment_mode else None,
        payment_status    = payment_status,
        notes             = data.notes,
    )
    session.add(invoice)
    session.flush()  # get invoice.id without committing yet

    # FIX: session.add(item) was outside the loop — only last item was saved
    for idx, (item_data, calc) in enumerate(calculated_items):
        item = InvoiceItem(
            invoice_id    = invoice.id,
            product_id    = item_data.product_id,
            item_name     = item_data.item_name,
            hsn_code      = item_data.hsn_code or "7113",
            purity        = item_data.purity,
            huid          = item_data.huid,
            weight_grams  = item_data.weight_grams,
            rate_per_gram = item_data.rate_per_gram,
            quantity      = item_data.quantity,
            unit          = item_data.unit,
            amount        = calc["amount"],
            making_charges = item_data.making_charges,
            gst_rate      = item_data.gst_rate,
            cgst_amount   = calc["cgst_amount"],
            sgst_amount   = calc["sgst_amount"],
            igst_amount   = calc["igst_amount"],
            making_cgst   = calc["making_cgst"],
            making_sgst   = calc["making_sgst"],
            line_total    = calc["line_total"],
            description   = item_data.description,
            sort_order    = item_data.sort_order if item_data.sort_order else idx,
        )
        session.add(item)  
    # Save version 1 snapshot
    snapshot = {
        "invoice_number": invoice.invoice_number,
        "grand_total":    grand_total,
        "items":          [i.item_name for i, _ in calculated_items],
        "saved_at":       datetime.utcnow().isoformat(),
    }
    version = InvoiceVersion(
        invoice_id     = invoice.id,
        version_number = 1,
        snapshot       = json.dumps(snapshot),
    )
    session.add(version)

    # ── NEW: OldGoldExchange ──────────────────────────────────────────
    if data.old_gold_value and data.old_gold_value > 0 and data.party_id:
        old_gold_entry = OldGoldExchange(
            party_id= data.party_id,
            sale_invoice_id= invoice.id,
            exchange_date= data.invoice_date,
            transaction_type= "exchange",
            metal_type= data.old_gold_metal_type.value if hasattr(data.old_gold_metal_type, "value") else str(data.old_gold_metal_type),
            purity= data.old_gold_purity,
            weight_grams= data.old_gold_weight or 0.0,
            rate_per_gram= data.old_gold_rate or 0.0,
            total_value=data.old_gold_value,
        )
        session.add(old_gold_entry)

    is_sale = data.invoice_type.value == "sale"
    is_purchase = data.invoice_type.value == "purchase"

    for item_data, calc in calculated_items:
        if not item_data.product_id:
            continue # skip items not linked to a product catalogue entry

        stock_entry = StockLedger(
            product_id= item_data.product_id,
            stock_date=data.invoice_date,
            transaction_type= "sale" if is_sale else "purchase",
            invoice_id= invoice.id,
            quantity_in= item_data.quantity if is_purchase else 0.0,
            quantity_out= item_data.quantity if is_sale else 0.0,
            balance= 0.0,
            rate= item_data.rate_per_gram,
            notes= f"Auto from invoice{invoice.invoice_number}",
        )
        session.add(stock_entry)

    session.commit()
    session.refresh(invoice)
    return invoice

def update_invoice(session: Session, invoice_id: int, data: InvoiceUpdate) -> Invoice:
    """Edit an existing bill — saves version snapshot, logs changes, recalculates totals."""

    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")
    if invoice.is_cancelled:
        raise HTTPException(status_code=400, detail="Cannot edit a cancelled bill")

    current_items = session.exec(
        select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)
    ).all()

    # Save snapshot of current state BEFORE any changes
    snapshot = {
        "invoice_number": invoice.invoice_number,
        "grand_total":    invoice.grand_total,
        "items":          [i.item_name for i in current_items],
        "saved_at":       datetime.utcnow().isoformat(),
        "reason":         data.edit_reason or "manual edit",
    }
    # FIX: increment version number
    invoice.version_number += 1
    version = InvoiceVersion(
        invoice_id     = invoice_id,
        version_number = invoice.version_number,
        snapshot       = json.dumps(snapshot),
    )
    session.add(version)

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

    # FIX: correct field name (was "payement_mode")
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
        if str(old_val) != str(value):
            log_change(field, str(old_val), str(value))
            setattr(invoice, field, value)

    # Replace items if new ones were provided
    if data.items is not None and len(data.items) > 0:
        for old_item in current_items:
            session.delete(old_item)
        session.flush()
        items_to_calc = data.items
        saving_new_items = True
    else:
        # No new items from form — keep existing items, use them for recalc
        items_to_calc = current_items
        saving_new_items = False

    subtotal = total_cgst = total_sgst = 0.0
    total_making = total_making_cgst = total_making_sgst = 0.0
    calculated_items = []

    for item_data in items_to_calc:
        calc = calculate_item(item_data)
        calculated_items.append((item_data, calc))
        subtotal          += calc["amount"]
        total_cgst        += calc["cgst_amount"]
        total_sgst        += calc["sgst_amount"]
        total_making      += item_data.making_charges or 0
        total_making_cgst += calc["making_cgst"]
        total_making_sgst += calc["making_sgst"]

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

    # Always recalculate totals — handles item changes AND old_gold/discount changes
    old_gold = data.old_gold_value if data.old_gold_value is not None else invoice.old_gold_value
    discount  = data.discount       if data.discount       is not None else invoice.discount

    gross       = subtotal + total_cgst + total_sgst + total_making + total_making_cgst + total_making_sgst
    gross       = gross - old_gold - discount
    round_off   = round(round(gross) - gross, 2)
    grand_total = round(gross + round_off, 2)
    amount_due  = round(grand_total - (invoice.amount_paid or 0), 2)

    payment_status = (
        "paid"    if (invoice.amount_paid or 0) >= grand_total else
        "partial" if (invoice.amount_paid or 0) > 0 else
        "unpaid"
    )

    log_change("grand_total", str(invoice.grand_total), str(grand_total))

    invoice.subtotal              = round(subtotal, 2)
    invoice.total_cgst            = round(total_cgst, 2)
    invoice.total_sgst            = round(total_sgst, 2)
    invoice.total_making_charges  = round(total_making, 2)
    invoice.making_cgst           = round(total_making_cgst, 2)
    invoice.making_sgst           = round(total_making_sgst, 2)
    invoice.round_off             = round_off
    invoice.grand_total           = grand_total
    invoice.amount_due            = amount_due
    invoice.payment_status        = payment_status

    # FIX: reset GST status so edited bills don't stay "gst_ready" with wrong amounts
    if invoice.gst_status == "gst_ready":
        invoice.gst_status = "pending_review"

    invoice.updated_at = datetime.utcnow()
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

def duplicate_invoice(session: Session, invoice_id: int) -> Invoice:
    """Duplicate an existing bill — creates a fresh bill with today's date and new number."""

    original = session.get(Invoice, invoice_id)
    if not original:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    original_items = session.exec(select(InvoiceItem).where(InvoiceItem.invoice_id == invoice_id)).all()

    from app.schemas.invoice import InvoiceCreate, InvoiceItemCreate, InvoiceType, BillCategory, PaymentMode

    items = []
    for item in original_items:
        items.append(InvoiceItemCreate(
            item_name      = item.item_name,
            product_id     = item.product_id,
            hsn_code       = item.hsn_code,
            purity         = item.purity,
            huid           = item.huid,
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
        invoice_type        = InvoiceType(original.invoice_type),
        bill_category       = BillCategory(original.bill_category),
        party_id            = original.party_id,
        invoice_date        = date.today(),
        credit_due_date     = None,
        place_of_supply     = original.place_of_supply,
        party_gstin         = original.party_gstin,
        payment_mode        = PaymentMode(original.payment_mode) if original.payment_mode else None,
        amount_paid         = 0.0,
        old_gold_value      = original.old_gold_value,
        old_gold_metal_type = "gold",   # original doesn't store this on invoice — default fine
        discount            = original.discount,
        notes               = f"Duplicated from {original.invoice_number}",
        items               = items,
    )

    return create_invoice(session, new_data)

def cancel_invoice(session: Session, invoice_id: int, reason: str = None) -> Invoice:
    """Cancel a bill — never hard delete."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    invoice.is_cancelled    = True
    invoice.cancelled_at    = datetime.utcnow()
    invoice.cancelled_reason = reason
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

def recover_invoice(session: Session, invoice_id: int) -> Invoice:
    """Recover a cancelled bill back to active."""
    invoice = session.get(Invoice, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Bill not found")

    invoice.is_cancelled     = False
    invoice.cancelled_at     = None
    invoice.cancelled_reason = None
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return invoice

def get_unsettled_credit_bills(session: Session):
    """Return all credit bills that are not fully paid — for the credit tracking page."""
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

    # Cash/other bills not fully paid yet
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
