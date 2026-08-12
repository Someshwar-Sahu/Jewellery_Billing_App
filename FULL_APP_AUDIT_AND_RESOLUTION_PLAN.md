# Complete Codebase Audit, Secondary Verification Trace & Resolution Plan

---

## 1. Executive Summary

This document represents the outcome of an exhaustive, 100% file-by-file audit of the **Jewellery Billing App** (`JewelBill`). Every backend service, router, database model, migration, Jinja2 template, and frontend JavaScript asset was examined without skipping or shortcutting.

All 18 identified errors, bugs, logic flaws, and UI inconsistencies—from critical 500 runtime crashes down to minor HTML syntax quirks and currency formatting—are catalogued below with exact file paths, line numbers, root causes, direct impacts, and concrete remediations, alongside the **24/7 Render & Supabase Keep-Alive Health Engine**.

---

## 2. 24/7 Keep-Alive & Health Check Engine (Render + Supabase)

To ensure the application stays live 24/7 and never goes down due to free/hobby tier sleep timeouts or database inactivity pausing:

1. **Dual Endpoint Architecture**:
   - `/health`: Public unauthenticated health check endpoint executing `SELECT 1` on Supabase PostgreSQL, returning JSON health metrics (`status: healthy`, `database: connected`, `uptime: active`).
   - `/keep-alive`: Lightweight keep-alive endpoint for external uptime monitors (UptimeRobot, Cron-Job.org, BetterUptime).

2. **Internal Background Async Keep-Alive Loop**:
   - An asynchronous task (`keep_alive_loop`) runs in the background of the FastAPI application.
   - Every 10 minutes (600 seconds):
     - Executes a lightweight `SELECT 1` query to prevent Supabase from pausing the database.
     - Self-pings its own public URL (`RENDER_EXTERNAL_URL` / `APP_URL`) to prevent Render from spinning down the web service container into sleep mode.

---

## 3. Complete Exhaustive 18-Point Bug & Flaw Inventory

### [CRITICAL] 1. `AttributeError` on Bill Update (`amount_used` vs `advance_used`)
- **Location**: `backend/app/services/invoice_service.py: Lines 610, 613`
- **Root Cause**: The `Invoice` SQLModel defines the column `advance_used: float = 0.0`. In `update_invoice()`, the code attempts to access `invoice.amount_used`:
  ```python
  totals = _build_totals(
      calculated_items,
      items_to_calc,
      old_gold,
      discount,
      (invoice.amount_paid or 0) + (invoice.amount_used or 0)  # <-- BUG
  )
  effective_paid = _d(invoice.amount_paid or 0) + _d(invoice.amount_used or 0)  # <-- BUG
  ```
- **Direct Impact**: Whenever an existing bill is edited and saved, the backend crashes with an unhandled 500 `AttributeError`, preventing any bill modifications.
- **Remediation**: Replace `invoice.amount_used` with `invoice.advance_used`.

---

### [CRITICAL] 2. Product ID Dropped on Bill Edit (Inventory Disconnection)
- **Location**: `backend/app/routers/invoices.py: Lines 351-361`
- **Root Cause**: When unpacking JSON item rows submitted from the edit screen, `product_id` is omitted from the `InvoiceItemCreate` instantiation.
- **Direct Impact**: Updating any bill sets `InvoiceItem.product_id = None`. In `update_invoice()`, `if not item_data.product_id: continue` skips stock ledger creation. Consequently, editing a bill permanently breaks stock tracking for all items on that bill.
- **Remediation**: Explicitly pass `product_id = int(item["product_id"]) if item.get("product_id") else None`.

---

### [CRITICAL] 3. Product ID Dropped on Credit Note Return Items (Inventory Not Credited)
- **Location**: `backend/app/routers/invoices.py: Lines 505-517` & `backend/app/templates/invoices/credit_note.html: Lines 53-78`
- **Root Cause**: When returning items via Credit Note, `product_id` was omitted from the form payload and the `InvoiceItemCreate` instantiation.
- **Direct Impact**: Creating a Credit Note fails to increment stock for returned catalogue products because `StockLedger` skips items without `product_id`.
- **Remediation**: Add hidden `product_id` field in `credit_note.html` and pass `product_id` to `InvoiceItemCreate`.

---

### [CRITICAL] 4. Recover Bill Fails to Reconcile Cash Ledger, Payment Events & Advances
- **Location**: `backend/app/services/invoice_service.py: Lines 734-770 & 843-876`
- **Root Cause**: 
  - On `cancel_invoice()`: Inverse `CashAccount` entries are created to reverse cash, `PaymentEvent` records are hard-deleted, and customer advances are refunded (`advance.adjusted_amount` reduced, `AdvanceApplication` deleted).
  - On `recover_invoice()`: Only stock entries are recreated. Cash ledger records and payment events are **not** restored, leaving `invoice.amount_paid > 0` with an empty payment history and missing cash balances. Furthermore, `invoice.advance_used` remains non-zero on the invoice record even though the advance was already returned to the customer's open balance during cancellation.
- **Direct Impact**: Double-counting of customer advances, empty payment audit logs, and permanent divergence between the cash drawer and invoice receipts.
- **Remediation**:
  - In `recover_invoice()`, if `invoice.amount_paid > 0`: Re-add the initial `PaymentEvent` and `CashAccount` receipt entry.
  - If `invoice.advance_used > 0`: Verify that the customer still has sufficient open advance balance before re-locking it, or prompt/reset `advance_used`.

---

### [CRITICAL] 5. Falsy `0%` GST Rate Fallback Bug
- **Locations**:
  - `backend/app/static/js/invoice.js: Lines 259, 282`
  - `backend/app/templates/invoices/edit.html: Lines 235, 251`
  - `backend/app/services/invoice_service.py: Line 59`
  - `backend/app/routers/invoices.py: Lines 177, 356, 512`
- **Root Cause**:
  - Frontend: `parseFloat("0") || 3.0` evaluates `0` as falsy, forcing `3.0%`.
  - Backend: `item_data.gst_rate or 3.0` evaluates `0.0 or 3.0` as `3.0%`.
- **Direct Impact**: Selecting `0%` (exempt / bullion / rough) in billing still calculated 3% tax.
- **Remediation**: Use explicit null/empty checks:
  - JS: `const val = row.querySelector('[name="gst_rate"]').value; const gstRate = val !== '' && !isNaN(val) ? parseFloat(val) : 3.0;`
  - Python: `gst_rate = item_data.gst_rate if item_data.gst_rate is not None else 3.0`

---

### [CRITICAL] 6. Bill Scanner `IndexError` on Non-Fenced AI Response
- **Location**: `backend/app/routers/scan.py: Lines 131-135`
- **Root Cause**: The string manipulation assumes Gemini will always wrap output in markdown code fences (`raw.split("```")[1]`).
- **Direct Impact**: 500 error when scanning bills whenever AI output lacks code fences.
- **Remediation**: Implement safe regex JSON block extraction (`re.search(r"\{.*\}", raw, re.DOTALL)`).

---

### [HIGH] 7. Historical Ledger Double-Counting on Multi-Year Rollovers
- **Location**: `backend/app/services/party_service.py: Lines 63-86` & `backend/app/routers/settings.py: Lines 280-315`
- **Root Cause**:
  - In `settings.py`, `_carry_forward_party_balances()` rolls up all outstanding dues from closing FY bills and writes them into `Party.opening_balance`.
  - In `party_service.py`, `get_party_summary()` was calculating `money_to_receive = round(sale_due + opening_receivable, 2)` where `sale_due` was summing `amount_due` across **all bills in history**.
- **Direct Impact**: In a new financial year, an unpaid ₹10,000 bill from a historical year was counted once as a historical bill and a second time as an opening balance, showing ₹20,000 outstanding (double-counting).
- **Remediation**: 
  - Ensure `_carry_forward_party_balances` compounds existing opening balances: `net = pre_existing_ob + (sale_due - purchase_due)`.
  - In `get_party_summary()`, calculate `sale_due` and `purchase_due` from bills within the active financial year, while historical dues reside in `Party.opening_balance`.

---

### [HIGH] 8. Excel Party Ledger Export Omission of Opening Balances & Settlements
- **Location**: `backend/app/routers/exports.py: Lines 288-370`
- **Root Cause**: `export_party_ledger()` only exported rows from `invoices`. Opening balances and opening balance settlements (`PaymentEvent` with `invoice_id = None`) were excluded.
- **Direct Impact**: If a customer has a carry-forward balance of ₹15,000 and settles it, the exported Excel ledger showed ₹0.00 bills and ₹0.00 dues, misrepresenting the customer's account statement.
- **Remediation**: Add an explicit Opening Balance header row in the Excel sheet and include unlinked opening balance settlement events.

---

### [HIGH] 9. Missing Cash Ledger Outflow on Direct Old Gold Purchases
- **Location**: `backend/app/routers/old_gold.py: Lines 106-121`
- **Root Cause**: When a direct purchase of old gold is created (`transaction_type="direct_purchase"` with `cash_paid > 0`), no `CashAccount(entry_type="payment")` entry was inserted.
- **Direct Impact**: Cash drawer balance in `/ledger` and KPI cards in `/dashboard` showed an inflated cash balance because scrap gold purchases never registered cash outflows.
- **Remediation**: Insert a corresponding `CashAccount` entry during direct purchase creation.

---

### [HIGH] 10. Expense Deletion Leaving Orphan Cash Outflows in Ledger
- **Location**: `backend/app/routers/expenses.py: Lines 164-188`
- **Root Cause**: Deleting an expense sets `is_deleted = True`, but leaves the associated `CashAccount(entry_type="payment", expense_id=expense.id)` row in the cash ledger.
- **Direct Impact**: Cash balance in `/ledger` remains deducted even after the expense is deleted.
- **Remediation**: Delete or reverse associated `CashAccount` rows when an expense is deleted.

---

### [HIGH] 11. GSTR-1 Turnover Overstatement (Credit Notes Ignored in Aggregates)
- **Location**: `backend/app/routers/reports.py: Lines 65-165`
- **Root Cause**: In `gstr1_report()`, credit notes are fetched for Table 9B (CDNR), but were not subtracted from the total taxable turnover, CGST, SGST, or HSN summary metrics.
- **Direct Impact**: GSTR-1 summary figures reflected gross outward supplies instead of net outward supplies.
- **Remediation**: Subtract CDNR taxable values and tax components from `b2b_totals`, `b2c_totals`, and `hsn_summary` totals.

---

### [MEDIUM] 12. Out-of-Stock Products Omitted from Dashboard & Stock Overview
- **Locations**: 
  - `backend/app/routers/dashboard.py: Lines 103-104`
  - `backend/app/routers/stocks.py: Lines 44-45`
- **Root Cause**: Both endpoints execute `if not entries: continue`.
- **Direct Impact**: Active products in the catalogue that have 0 inventory are completely hidden from the Stock Overview and excluded from the Low Stock counter on the Dashboard.
- **Remediation**: Include products with 0 entries, evaluating their balance as `0.000g` against their `low_stock_alert`.

---

### [MEDIUM] 13. Malformed `<thead>` Table Structure in `stock/list.html`
- **Location**: `backend/app/templates/stock/list.html: Lines 58-65`
- **Root Cause**: Table opening tag is immediately followed by column headers without `<thead><tr>` and missing the first two header columns (`Product` and `Purity`).
- **Direct Impact**: Table headers are shifted 2 columns to the left relative to the data.
- **Remediation**: Add `<thead><tr><th>Product</th><th>Purity / Metal</th>...`.

---

### [MEDIUM] 14. Route Function Name Collision in `auth.py`
- **Location**: `backend/app/routers/auth.py: Lines 21 & 28`
- **Root Cause**: Both `GET /setup` and `POST /setup` are named `def setup_page(...)`.
- **Remediation**: Rename the POST handler to `def setup_submit(...)`.

---

### [MEDIUM] 15. Scan Prefill Hardcoded `3.0%` GST Selection
- **Location**: `backend/app/templates/invoices/create.html: Line 428`
- **Root Cause**: `if (gs) for (let o of gs.options) if (o.value === "3.0") { o.selected = true; break; }` always selected 3% regardless of the scanned bill's tax rate.
- **Remediation**: Match against `item.gst_rate`.

---

### [LOW] 16. Print Templates & Detail View Missing Advance Used Line
- **Locations**:
  - `backend/app/templates/invoices/template_small.html: Lines 518-527`
  - `backend/app/templates/invoices/print_a4.html: Lines 374-377`
  - `backend/app/templates/invoices/bill_print.html: Lines 149-150`
  - `backend/app/templates/invoices/detail.html: Lines 134-148`
- **Root Cause**: Print receipts and detail payment summaries only check `if invoice.amount_paid > 0`. If a bill was settled using an advance (`advance_used > 0`), the adjusted advance was omitted from the printout summary box.
- **Remediation**: Add `{% if invoice.advance_used and invoice.advance_used > 0 %}<tr><td>Advance Adjusted</td>...` to small print, A4 print, bill print, and detail templates.

---

### [LOW] 17. Inconsistent Number Formatting on Invoice Detail Cards
- **Location**: `backend/app/templates/invoices/detail.html: Lines 137, 141, 146` & `bill_print.html: Line 58`
- **Root Cause**: Printed as `₹{{ invoice.grand_total }}` and filter precedence issue in `{{ invoice.payment_mode or "—" | upper }}`.
- **Remediation**: Apply `"%.2f"|format(...)` and `{{ (invoice.payment_mode or "—") | upper }}`.

---

### [LOW] 18. Stray Commas in `invoices/create.html` Input Attributes & Docstring Typo
- **Locations**:
  - `backend/app/templates/invoices/create.html: Line 143`
  - `backend/app/routers/rough_bill.py: Line 22`
- **Root Cause**: `<input class="field-input" type="text", id="walkinAddress", placeholder="e.g. Jaunpur">` contains invalid commas inside the HTML tag, and 4 quotes in docstring.
- **Remediation**: Remove commas inside the HTML tag, fix docstring quotes.

---

## 4. Comprehensive 8-Level Verification & Test Suite Design

```
┌────────────────────────────────────────────────────────────────────────┐
│                   COMPREHENSIVE VERIFICATION SUITE                     │
├────────────────────────────────────────────────────────────────────────┤
│ Level 1: Tax Slabs & Calculation Matrix (0%, 1.5%, 3%, 18%, Advances)  │
│ Level 2: Entity Validation & Injection / Boundary Testing              │
│ Level 3: Lifecycle State Machine & Workflow Invariants (Create/Cancel) │
│ Level 4: Multi-Year Financial & FY Rollover Integrity                  │
│ Level 5: Ledger Integrity & Concurrency Balancing                     │
│ Level 6: AI Bill Scanner & OCR Robustness (Malformed Inputs)          │
│ Level 7: Frontend DOM & User Interactions (Clicks, Modals, Shortcuts)  │
│ Level 8: Mobile Responsiveness, Thermal Print (13x18cm/A4) & PWA       │
└────────────────────────────────────────────────────────────────────────┘
```
