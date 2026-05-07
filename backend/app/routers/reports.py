from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select
from collections import defaultdict
from datetime import date

from app.database import get_session
from app.models.invoices import Invoice, InvoiceItem
from app.models.parties import Party
from app.models.expenses import Expense

router    = APIRouter(prefix="/reports", tags=["Reports"])
templates = Jinja2Templates(directory="app/templates")


# ── HELPERS ───────────────────────────────────────────────────────────────────

def _month_label(d: date) -> str:
    """Return 'Apr 2024' style label from a date."""
    return d.strftime("%b %Y")

def _month_key(d: date) -> str:
    """Return sortable key like '2024-04' from a date."""
    return d.strftime("%Y-%m")


# ── GSTR-1 ───────────────────────────────────────────────────────────────────

@router.get("/gstr1", response_class=HTMLResponse)
def gstr1_report(
    request: Request,
    month: str = "",          # filter: "2024-04" format, empty = all
    session: Session = Depends(get_session),
):
    """
    GSTR-1: Outward supplies (sale bills only).
    B2B  = party has GSTIN
    B2C  = walk-in or party without GSTIN
    HSN  = HSN-wise summary across all items
    """

    # Base query — sale bills only, not cancelled, gst_ready or locked
    stmt = (
        select(Invoice)
        .where(Invoice.invoice_type == "sale")
        .where(Invoice.is_cancelled == False)
        .where(Invoice.gst_status.in_(["gst_ready", "locked"]))
        .order_by(Invoice.invoice_date)
    )
    if month:
        # filter by year-month prefix on invoice_date
        try:
            y, m = int(month[:4]), int(month[5:7])
            stmt = stmt.where(
                Invoice.invoice_date >= date(y, m, 1)
            )
            # last day of month
            if m == 12:
                end = date(y + 1, 1, 1)
            else:
                end = date(y, m + 1, 1)
            stmt = stmt.where(Invoice.invoice_date < end)
        except Exception:
            pass

    invoices = session.exec(stmt).all()

    # Party lookup dict
    party_ids = {inv.party_id for inv in invoices if inv.party_id}
    parties = {}
    if party_ids:
        for p in session.exec(select(Party).where(Party.id.in_(party_ids))).all():
            parties[p.id] = p

    # ── Separate B2B and B2C ──────────────────────────────────────────────
    b2b_rows = []
    b2c_rows = []

    b2b_totals = {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "grand": 0.0}
    b2c_totals = {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "grand": 0.0}

    for inv in invoices:
        party = parties.get(inv.party_id) if inv.party_id else None
        has_gstin = bool(inv.party_gstin or (party and party.gstin))
        gstin = inv.party_gstin or (party.gstin if party else None)
        party_name = party.name if party else "Walk-in"

        # taxable = subtotal + making charges (before GST)
        taxable = round(inv.subtotal + (inv.total_making_charges or 0), 2)
        cgst    = round((inv.total_cgst or 0) + (inv.making_cgst or 0), 2)
        sgst    = round((inv.total_sgst or 0) + (inv.making_sgst or 0), 2)

        row = {
            "invoice_number": inv.invoice_number,
            "invoice_date":   inv.invoice_date,
            "month_key":      _month_key(inv.invoice_date),
            "month_label":    _month_label(inv.invoice_date),
            "party_name":     party_name,
            "gstin":          gstin,
            "taxable":        taxable,
            "cgst":           cgst,
            "sgst":           sgst,
            "grand_total":    inv.grand_total,
            "invoice_id":     inv.id,
        }

        if has_gstin:
            b2b_rows.append(row)
            b2b_totals["taxable"] += taxable
            b2b_totals["cgst"]    += cgst
            b2b_totals["sgst"]    += sgst
            b2b_totals["grand"]   += inv.grand_total
        else:
            b2c_rows.append(row)
            b2c_totals["taxable"] += taxable
            b2c_totals["cgst"]    += cgst
            b2c_totals["sgst"]    += sgst
            b2c_totals["grand"]   += inv.grand_total

    # Round totals
    for t in [b2b_totals, b2c_totals]:
        for k in t:
            t[k] = round(t[k], 2)

    # ── HSN Summary ───────────────────────────────────────────────────────
    # Group items by HSN code across all filtered invoices
    invoice_ids = [inv.id for inv in invoices]
    hsn_map = defaultdict(lambda: {"taxable": 0.0, "cgst": 0.0, "sgst": 0.0, "qty": 0.0})

    if invoice_ids:
        items = session.exec(
            select(InvoiceItem).where(InvoiceItem.invoice_id.in_(invoice_ids))
        ).all()
        for item in items:
            hsn = item.hsn_code or "7113"
            hsn_map[hsn]["taxable"] += item.amount or 0
            hsn_map[hsn]["cgst"]    += (item.cgst_amount or 0) + (item.making_cgst or 0)
            hsn_map[hsn]["sgst"]    += (item.sgst_amount or 0) + (item.making_sgst or 0)
            hsn_map[hsn]["qty"]     += item.weight_grams or item.quantity or 0

    hsn_summary = [
        {
            "hsn":     hsn,
            "taxable": round(v["taxable"], 2),
            "cgst":    round(v["cgst"], 2),
            "sgst":    round(v["sgst"], 2),
            "qty":     round(v["qty"], 3),
        }
        for hsn, v in sorted(hsn_map.items())
    ]

    # ── Available months for filter dropdown ──────────────────────────────
    all_months = sorted(
        {_month_key(inv.invoice_date): _month_label(inv.invoice_date)
         for inv in session.exec(
             select(Invoice)
             .where(Invoice.invoice_type == "sale")
             .where(Invoice.is_cancelled == False)
             .where(Invoice.gst_status.in_(["gst_ready", "locked"]))
         ).all()
        }.items(),
        reverse=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="reports/gstr1.html",
        context={
            "b2b_rows":    b2b_rows,
            "b2c_rows":    b2c_rows,
            "b2b_totals":  b2b_totals,
            "b2c_totals":  b2c_totals,
            "hsn_summary": hsn_summary,
            "all_months":  all_months,   # list of (key, label)
            "selected_month": month,
            "total_bills": len(invoices),
        },
    )


# ── GSTR-3B ──────────────────────────────────────────────────────────────────

@router.get("/gstr3b", response_class=HTMLResponse)
def gstr3b_report(
    request: Request,
    month: str = "",
    session: Session = Depends(get_session),
):
    """
    GSTR-3B: Summary of output tax collected vs ITC claimable.
    Output tax = CGST + SGST from gst_ready/locked sale bills.
    ITC        = GST paid on purchase bills + itc_claimable expenses.
    Net payable = output tax - ITC.
    """

    # ── Date range filter ─────────────────────────────────────────────────
    date_start = None
    date_end   = None
    if month:
        try:
            y, m = int(month[:4]), int(month[5:7])
            date_start = date(y, m, 1)
            date_end   = date(y + 1, 1, 1) if m == 12 else date(y, m + 1, 1)
        except Exception:
            pass

    # ── Output Tax (from sale bills) ──────────────────────────────────────
    sale_stmt = (
        select(Invoice)
        .where(Invoice.invoice_type == "sale")
        .where(Invoice.is_cancelled == False)
        .where(Invoice.gst_status.in_(["gst_ready", "locked"]))
    )
    if date_start:
        sale_stmt = sale_stmt.where(Invoice.invoice_date >= date_start)
        sale_stmt = sale_stmt.where(Invoice.invoice_date < date_end)

    sale_bills = session.exec(sale_stmt).all()

    out_cgst    = round(sum((b.total_cgst or 0) + (b.making_cgst or 0) for b in sale_bills), 2)
    out_sgst    = round(sum((b.total_sgst or 0) + (b.making_sgst or 0) for b in sale_bills), 2)
    out_taxable = round(sum((b.subtotal or 0) + (b.total_making_charges or 0) for b in sale_bills), 2)
    out_total   = round(out_cgst + out_sgst, 2)

    # ── ITC from Purchase Bills ───────────────────────────────────────────
    pur_stmt = (
        select(Invoice)
        .where(Invoice.invoice_type == "purchase")
        .where(Invoice.is_cancelled == False)
        .where(Invoice.gst_status.in_(["gst_ready", "locked"]))
    )
    if date_start:
        pur_stmt = pur_stmt.where(Invoice.invoice_date >= date_start)
        pur_stmt = pur_stmt.where(Invoice.invoice_date < date_end)

    purchase_bills = session.exec(pur_stmt).all()

    itc_purchase_cgst = round(sum((b.total_cgst or 0) + (b.making_cgst or 0) for b in purchase_bills), 2)
    itc_purchase_sgst = round(sum((b.total_sgst or 0) + (b.making_sgst or 0) for b in purchase_bills), 2)
    itc_purchase      = round(itc_purchase_cgst + itc_purchase_sgst, 2)

    # ── ITC from Expenses ─────────────────────────────────────────────────
    exp_stmt = select(Expense).where(Expense.itc_claimable > 0)
    if date_start:
        exp_stmt = exp_stmt.where(Expense.expense_date >= date_start)
        exp_stmt = exp_stmt.where(Expense.expense_date < date_end)

    expenses_itc = session.exec(exp_stmt).all()
    itc_expenses = round(sum(e.itc_claimable or 0 for e in expenses_itc), 2)

    # ── Net ───────────────────────────────────────────────────────────────
    total_itc     = round(itc_purchase + itc_expenses, 2)
    net_payable   = round(max(0.0, out_total - total_itc), 2)
    # CGST and SGST net payable — split evenly (intrastate only)
    net_cgst      = round(max(0.0, out_cgst - (itc_purchase_cgst + itc_expenses / 2)), 2)
    net_sgst      = round(max(0.0, out_sgst - (itc_purchase_sgst + itc_expenses / 2)), 2)

    # ── Available months dropdown ─────────────────────────────────────────
    all_months = sorted(
        {_month_key(inv.invoice_date): _month_label(inv.invoice_date)
         for inv in session.exec(
             select(Invoice)
             .where(Invoice.is_cancelled == False)
             .where(Invoice.gst_status.in_(["gst_ready", "locked"]))
         ).all()
        }.items(),
        reverse=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="reports/gstr3b.html",
        context={
            # Output
            "out_taxable":   out_taxable,
            "out_cgst":      out_cgst,
            "out_sgst":      out_sgst,
            "out_total":     out_total,
            "sale_count":    len(sale_bills),
            # ITC
            "itc_purchase":      itc_purchase,
            "itc_purchase_cgst": itc_purchase_cgst,
            "itc_purchase_sgst": itc_purchase_sgst,
            "itc_expenses":      itc_expenses,
            "total_itc":         total_itc,
            "purchase_count":    len(purchase_bills),
            "expense_itc_count": len(expenses_itc),
            # Net
            "net_payable": net_payable,
            "net_cgst":    net_cgst,
            "net_sgst":    net_sgst,
            # Filter
            "all_months":      all_months,
            "selected_month":  month,
        },
    )