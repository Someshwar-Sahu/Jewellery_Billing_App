let itemCount = 0;

// ── BILL TYPE CHANGE ──────────────────────────────────────────────────────────
// When bill type switches between Sale and Purchase, the party section changes.
// Sale → show customer section (registered or walk-in)
// Purchase → show supplier section only (no walk-in for purchases)

function onBillTypeChange() {
    const type = document.getElementById("invoiceType").value;
    const saleSection     = document.getElementById("salePartySection");
    const purchaseSection = document.getElementById("purchasePartySection");

    if (type === "purchase") {
        saleSection.style.display     = "none";
        purchaseSection.style.display = "block";
    } else {
        saleSection.style.display     = "block";
        purchaseSection.style.display = "none";
    }
}

// ── WALK-IN TOGGLE (sale only) ────────────────────────────────────────────────

function togglePartyMode() {
    const mode        = document.getElementById("partyMode").value;
    const partySelect = document.getElementById("partySelectRow");
    const walkinRow   = document.getElementById("walkinRow");

    if (mode === "walkin") {
        partySelect.style.display = "none";
        walkinRow.style.display   = "flex";
    } else {
        partySelect.style.display = "flex";
        walkinRow.style.display   = "none";
    }
}

// ── CREDIT DATE TOGGLE ────────────────────────────────────────────────────────

function toggleCreditDate() {
    const cat       = document.getElementById("billCategory").value;
    const row       = document.getElementById("creditDateRow");
    const dateInput = document.getElementById("creditDueDate");
    row.style.display  = cat === "credit" ? "flex" : "none";
    dateInput.required = cat === "credit";
}

// ── ITEM ROWS ─────────────────────────────────────────────────────────────────

function addItem() {
    itemCount++;
    const tbody = document.getElementById("itemsBody");
    const row   = document.createElement("tr");
    row.id = `item-row-${itemCount}`;
    row.innerHTML = `
        <td><input type="text" name="item_name" placeholder="Gold Ornament" required
             style="width:140px"></td>
        <td><input type="text" name="purity" placeholder="22K"
             style="width:55px"></td>
        <td><input type="number" name="weight_grams" placeholder="0.000"
             step="0.001" min="0" style="width:85px"
             oninput="calcRow(${itemCount})"></td>
        <td><input type="number" name="rate_per_gram" placeholder="0.00"
             step="0.01" min="0" style="width:90px"
             oninput="calcRow(${itemCount})"></td>
        <td><span id="amount-${itemCount}">0.00</span></td>
        <td><input type="number" name="making_charges" placeholder="0.00"
             step="0.01" min="0" style="width:90px"
             oninput="calcRow(${itemCount})"></td>
        <td>
            <select name="gst_rate" onchange="calcRow(${itemCount})">
                <option value="3.0">3%</option>
                <option value="1.5">1.5%</option>
                <option value="0">0%</option>
                <option value="18.0">18%</option>
            </select>
        </td>
        <td><strong><span id="line-total-${itemCount}">0.00</span></strong></td>
        <td><button type="button" onclick="removeItem(${itemCount})"
            style="color:red;background:none;border:none;cursor:pointer;font-size:16px">✕</button></td>
    `;
    tbody.appendChild(row);
}

function removeItem(n) {
    const row = document.getElementById(`item-row-${n}`);
    if (row) row.remove();
    recalcTotals();
}

function calcRow(n) {
    const row = document.getElementById(`item-row-${n}`);
    if (!row) return;

    const weight  = parseFloat(row.querySelector('[name="weight_grams"]').value)  || 0;
    const rate    = parseFloat(row.querySelector('[name="rate_per_gram"]').value)  || 0;
    const making  = parseFloat(row.querySelector('[name="making_charges"]').value) || 0;
    const gstRate = parseFloat(row.querySelector('[name="gst_rate"]').value)       || 3.0;

    const amount    = weight * rate;
    const cgst      = amount * (gstRate / 2) / 100;
    const sgst      = cgst;
    const makingGst = making * 0.18;
    const lineTotal = amount + cgst + sgst + making + makingGst;

    document.getElementById(`amount-${n}`).textContent     = amount.toFixed(2);
    document.getElementById(`line-total-${n}`).textContent = lineTotal.toFixed(2);

    recalcTotals();
}

// ── TOTALS ────────────────────────────────────────────────────────────────────

window._currentGrandTotal = 0;

function recalcTotals() {
    let subtotal = 0, totalCgst = 0, totalSgst = 0, totalMaking = 0, totalMakingGst = 0;

    document.querySelectorAll("#itemsBody tr").forEach(row => {
        const weight  = parseFloat(row.querySelector('[name="weight_grams"]')?.value)  || 0;
        const rate    = parseFloat(row.querySelector('[name="rate_per_gram"]')?.value)  || 0;
        const making  = parseFloat(row.querySelector('[name="making_charges"]')?.value) || 0;
        const gstRate = parseFloat(row.querySelector('[name="gst_rate"]')?.value)       || 3.0;

        const amount = weight * rate;
        const cgst   = amount * (gstRate / 2) / 100;
        const sgst   = cgst;
        const mGst   = making * 0.18;

        subtotal       += amount;
        totalCgst      += cgst;
        totalSgst      += sgst;
        totalMaking    += making;
        totalMakingGst += mGst;
    });

    const oldGold    = parseFloat(document.getElementById("oldGoldValue")?.value) || 0;
    const discount   = parseFloat(document.getElementById("discount")?.value)     || 0;
    const gross      = subtotal + totalCgst + totalSgst + totalMaking + totalMakingGst;
    const grandTotal = Math.round((gross - oldGold - discount) * 100) / 100;

    window._currentGrandTotal = grandTotal;

    const paidInput = document.getElementById("amountPaid");
    if (paidInput) {
        paidInput.max = grandTotal.toFixed(2);
        const currentPaid = parseFloat(paidInput.value) || 0;
        if (currentPaid > grandTotal) paidInput.value = grandTotal.toFixed(2);
    }

    const paid      = parseFloat(document.getElementById("amountPaid")?.value) || 0;
    const amountDue = Math.max(0, grandTotal - paid);

    document.getElementById("tSubtotal").textContent   = "₹" + subtotal.toFixed(2);
    document.getElementById("tCgst").textContent       = "₹" + totalCgst.toFixed(2);
    document.getElementById("tSgst").textContent       = "₹" + totalSgst.toFixed(2);
    document.getElementById("tMaking").textContent     = "₹" + totalMaking.toFixed(2);
    document.getElementById("tMakingGst").textContent  = "₹" + totalMakingGst.toFixed(2);
    document.getElementById("tOldGold").textContent    = "₹" + oldGold.toFixed(2);
    document.getElementById("tDiscount").textContent   = "₹" + discount.toFixed(2);
    document.getElementById("tGrandTotal").textContent = "₹" + grandTotal.toFixed(2);
    document.getElementById("tAmountPaid").textContent = "₹" + paid.toFixed(2);
    document.getElementById("tAmountDue").textContent  = "₹" + amountDue.toFixed(2);
}

function onAmountPaidInput() {
    const paidInput  = document.getElementById("amountPaid");
    const grandTotal = window._currentGrandTotal || 0;
    let paid = parseFloat(paidInput.value) || 0;

    if (paid > grandTotal) {
        paid = grandTotal;
        paidInput.value = grandTotal.toFixed(2);
        paidInput.style.borderColor = "#dc3545";
        setTimeout(() => paidInput.style.borderColor = "", 1000);
    }
    recalcTotals();
}

// ── SUBMIT ────────────────────────────────────────────────────────────────────

async function submitBill() {
    const form     = document.getElementById("billForm");
    const billType = document.getElementById("invoiceType").value;

    // Resolve party_id based on bill type
    let party_id     = null;
    let walkin_name  = null;
    let walkin_phone = null;

    if (billType === "purchase") {
        // Purchase: must select a registered supplier
        const supplierVal = document.getElementById("supplierIdSelect").value;
        if (!supplierVal) {
            alert("Please select a supplier for this purchase bill.");
            return;
        }
        party_id = parseInt(supplierVal);
    } else {
        // Sale: registered customer or walk-in
        const mode = document.getElementById("partyMode").value;
        if (mode === "walkin") {
            walkin_name  = document.getElementById("walkinName").value.trim();
            walkin_phone = document.getElementById("walkinPhone").value.trim() || null;
            if (!walkin_name) {
                alert("Please enter the customer name.");
                return;
            }
        } else {
            const partyVal = document.getElementById("partyIdSelect").value;
            if (!partyVal) {
                alert("Please select a customer, or switch to Walk-in Customer.");
                return;
            }
            party_id = parseInt(partyVal);
        }
    }

    // Collect items
    const items = [];
    document.querySelectorAll("#itemsBody tr").forEach(row => {
        const name = row.querySelector('[name="item_name"]')?.value?.trim();
        if (!name) return;
        items.push({
            item_name:      name,
            purity:         row.querySelector('[name="purity"]')?.value         || null,
            weight_grams:   row.querySelector('[name="weight_grams"]')?.value   || null,
            rate_per_gram:  row.querySelector('[name="rate_per_gram"]')?.value  || null,
            making_charges: row.querySelector('[name="making_charges"]')?.value || null,
            gst_rate:       row.querySelector('[name="gst_rate"]')?.value       || "3.0",
        });
    });

    if (items.length === 0) {
        alert("Please add at least one item.");
        return;
    }

    const grandTotal = window._currentGrandTotal || 0;
    let amountPaid   = parseFloat(document.getElementById("amountPaid").value) || 0;
    if (amountPaid > grandTotal) amountPaid = grandTotal;

    const payload = {
        party_id,
        walkin_name,
        walkin_phone,
        invoice_date:    form.querySelector('[name="invoice_date"]').value,
        invoice_type:    billType,
        bill_category:   form.querySelector('[name="bill_category"]').value,
        credit_due_date: form.querySelector('[name="credit_due_date"]')?.value || null,
        payment_mode:    form.querySelector('[name="payment_mode"]').value || null,
        amount_paid:     amountPaid,
        old_gold_value:  parseFloat(form.querySelector('[name="old_gold_value"]').value) || 0,
        discount:        parseFloat(form.querySelector('[name="discount"]').value) || 0,
        notes:           form.querySelector('[name="notes"]').value || null,
        items,
    };

    const res  = await fetch("/invoices/create", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.success) {
        window.location.href = `/invoices/${data.invoice_id}`;
    } else {
        alert("Error saving bill:\n" + data.error);
    }
}
