let itemCount = 0;
let _savingBill = false;
function _escHtml(value) {
    return String(value == null ? "" : value)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function _setSaveBillLoading(loading) {
    const btn = document.getElementById("saveBillBtn");
    if (!btn) return;
    if (loading) {
        if (!btn.dataset.originalHtml) btn.dataset.originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = "Saving...";
    } else {
        btn.disabled = false;
        if (btn.dataset.originalHtml) {
            btn.innerHTML = btn.dataset.originalHtml;
            delete btn.dataset.originalHtml;
        }
    }
}

// ── BILL TYPE CHANGE ──────────────────────────────────────────────────────────

function onBillTypeChange() {
    const type            = document.getElementById("invoiceType").value;
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

// ── WALK-IN TOGGLE ────────────────────────────────────────────────────────────

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

function toggleOldGoldDetails() {
    const checked     = document.getElementById("oldGoldDetailed").checked;
    const detailBlock = document.getElementById("oldGoldDetailFields");
    detailBlock.style.display = checked ? "flex" : "none";
    if (!checked) {
        // clear detail fields when hidden so they don't get sent
        document.querySelector('[name="old_gold_metal_type"]').value = "gold";
        document.querySelector('[name="old_gold_purity"]').value     = "";
        document.querySelector('[name="old_gold_weight"]').value     = "";
        document.querySelector('[name="old_gold_rate"]').value       = "";
    }
}

// Auto-calculate old gold value from weight × rate when details filled
function calcOldGoldValue() {
    const weight = parseFloat(document.querySelector('[name="old_gold_weight"]')?.value) || 0;
    const rate   = parseFloat(document.querySelector('[name="old_gold_rate"]')?.value)   || 0;
    if (weight && rate) {
        document.getElementById("oldGoldValue").value = (weight * rate).toFixed(2);
        recalcTotals();
    }
}

// ── ITEM ROWS ─────────────────────────────────────────────────────────────────

function addItem() {
    itemCount++;
    const n     = itemCount;
    const tbody = document.getElementById("itemsBody");
    const row   = document.createElement("tr");
    row.id = `item-row-${n}`;
    row.innerHTML = `
        <td class="item-name-cell" style="position:relative">
            <input type="text" name="item_name" placeholder="Type to search..."
                 autocomplete="off" style="width:150px"
                 oninput="searchProducts(${n}, this.value)"
                 onfocus="searchProducts(${n}, this.value)">
            <div id="suggestions-${n}" class="item-suggestions"
                 style="display:none;position:absolute;top:100%;left:0;z-index:99;
                        background:#fff;border:1px solid #ccc;border-radius:6px;
                        min-width:220px;box-shadow:0 4px 12px rgba(0,0,0,0.1)">
            </div>
        </td>
        <td><input type="text" name="purity" placeholder="22K" style="width:55px"></td>
        <td><input type="number" name="weight_grams" placeholder="0.000"
             step="0.001" min="0" style="width:85px" oninput="calcRow(${n})"></td>
        <td><input type="number" name="rate_per_gram" placeholder="0.00"
             step="0.01" min="0" style="width:90px" oninput="calcRow(${n})"></td>
        <td><span id="amount-${n}">0.00</span></td>
        <td><input type="number" name="making_charges" placeholder="0.00"
             step="0.01" min="0" style="width:90px" oninput="calcRow(${n})"></td>
        <td>
            <select name="gst_rate" onchange="calcRow(${n})">
                <option value="3.0">3%</option>
                <option value="1.5">1.5%</option>
                <option value="0">0%</option>
                <option value="18.0">18%</option>
            </select>
        </td>
        <td><strong><span id="line-total-${n}">0.00</span></strong></td>
        <td><button type="button" onclick="removeItem(${n})"
            style="color:red;background:none;border:none;cursor:pointer;font-size:16px">✕</button></td>
    `;
    tbody.appendChild(row);
}

// ── PRODUCT SEARCH AUTOCOMPLETE ───────────────────────────────────────────────

let _searchTimer = null;

function searchProducts(n, query) {
    clearTimeout(_searchTimer);
    const box = document.getElementById(`suggestions-${n}`);
    if (!box) return;

    if (!query || query.length < 1) {
        box.style.display = "none";
        return;
    }

    _searchTimer = setTimeout(async () => {
        try {
            const res  = await fetch(`/products/search?q=${encodeURIComponent(query)}`);
            if (!res.ok) throw new Error("search_failed");
            const list = await res.json();

            if (!Array.isArray(list) || !list.length) { box.style.display = "none"; return; }

            box.innerHTML = list.map(p => `
                <div onclick="selectProduct(${n}, ${JSON.stringify(p).replace(/"/g, '&quot;')})"
                     style="padding:8px 12px;cursor:pointer;font-size:13px;border-bottom:1px solid #eee"
                     onmouseover="this.style.background='#f5f5f5'"
                     onmouseout="this.style.background=''">
                    <strong>${_escHtml(p.name)}</strong>
                    ${p.purity ? `<span style="color:#888;margin-left:6px">${_escHtml(p.purity)}</span>` : ""}
                    <span style="color:#aaa;font-size:11px;margin-left:6px">${_escHtml(p.metal_type)}</span>
                </div>
            `).join("");
            box.style.display = "block";
        } catch (e) {
            box.style.display = "none";
        }
    }, 200);
}

function selectProduct(n, product) {
    const row = document.getElementById(`item-row-${n}`);
    if (!row) return;

    row.querySelector('[name="item_name"]').value = product.name;

    if (product.purity) {
        row.querySelector('[name="purity"]').value = product.purity;
    }
    if(window.todayRate && window.todayRate.found){
        const rateInput = row.querySelector('[name="rate_per_gram"]');
        let rate = null;
        const purity = (product.purity || "").toUpperCase();
        const metal = (product.metal_type || "").toLowerCase();

        if (metal === "gold"){
            if (purity.includes("18"))      rate = window.todayRate.gold_18k;
            else if (purity.includes("22")) rate = window.todayRate.gold_22k;
            else                            rate = window.todayRate.gold_22k;
        }else if (metal === "silver"){
            rate = window.todayRate.silver;
        }

        if(rate){
            rateInput.value = rate;
        }
    }
    if (product.making_charge_rate) {
        row.querySelector('[name="making_charges"]').value = product.making_charge_rate;
    }

    const gstSel = row.querySelector('[name="gst_rate"]');
    for (let opt of gstSel.options) {
        if (parseFloat(opt.value) === parseFloat(product.gst_rate || 3.0)) {
            opt.selected = true; break;
        }
    }

    row.dataset.product_id = product.id;
    document.getElementById(`suggestions-${n}`).style.display = "none";
    calcRow(n);
}

document.addEventListener("click", function(e) {
    if (!e.target.closest('[id^="suggestions-"]') &&
        !e.target.closest('[name="item_name"]')) {
        document.querySelectorAll('[id^="suggestions-"]').forEach(b => b.style.display = "none");
    }
});

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

// ── ADVANCE CHECK ─────────────────────────────────────────────────────────────

async function checkAdvance() {
    const partyId = document.getElementById("partyIdSelect")?.value;
    const hint    = document.getElementById("advanceHint");
    if (!hint) return;

    if (!partyId) { hint.style.display = "none"; return; }

    try {
        const res  = await fetch(`/advances/balance/${partyId}`);
        const data = await res.json();
        if (data.available > 0) {
            document.getElementById("advanceAmount").textContent = "₹" + data.available.toFixed(2);
            hint.style.display     = "block";
            hint.dataset.available = data.available;
            hint.dataset.applied   = "0";   
        } else {
            hint.style.display = "none";
        }
    } catch (e) {
        hint.style.display = "none";
    }
}

function applyAdvance() {
    const hint       = document.getElementById("advanceHint");
    const available  = parseFloat(hint.dataset.available || 0);
    const grandTotal = window._currentGrandTotal || 0;

    const applyAmount = Math.min(available, grandTotal);
    const paidInput   = document.getElementById("amountPaid");
    if (paidInput) {
        paidInput.value = applyAmount.toFixed(2);
        onAmountPaidInput();
    }
    hint.dataset.applied   = applyAmount.toFixed(2);
    hint.dataset.wasApplied = "1";
    hint.style.display = "none";
}

// ── SUBMIT ────────────────────────────────────────────────────────────────────

async function submitBill() {
    if (_savingBill) return;
    const form     = document.getElementById("billForm");
    const billType = document.getElementById("invoiceType").value;

    let party_id     = null;
    let walkin_name  = null;
    let walkin_phone = null;

    if (billType === "purchase") {
        const supplierVal = document.getElementById("supplierIdSelect").value;
        if (!supplierVal) {
            alert("Please select a supplier for this purchase bill.");
            return;
        }
        party_id = parseInt(supplierVal);
    } else {
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
            product_id:     row.dataset.product_id                              || null,
        });
    });

    if (items.length === 0) {
        alert("Please add at least one item.");
        return;
    }

    const grandTotal = window._currentGrandTotal || 0;
    let amountPaid   = parseFloat(document.getElementById("amountPaid").value) || 0;
    if (amountPaid > grandTotal) amountPaid = grandTotal;

    const oldGoldDetailed = document.getElementById("oldGoldDetailed")?.checked || false;

    const hint        = document.getElementById("advanceHint");
    const wasApplied  = hint?.dataset?.wasApplied === "1";
    const available   = parseFloat(hint?.dataset?.available || 0);
    const advanceUsed = wasApplied ? Math.min(available, amountPaid) : 0;

    const payload = {
        party_id,
        walkin_name,
        walkin_phone,
        advance_used:    advanceUsed,   
        invoice_date:    form.querySelector('[name="invoice_date"]').value,
        invoice_type:    billType,
        bill_category:   form.querySelector('[name="bill_category"]').value,
        credit_due_date: form.querySelector('[name="credit_due_date"]')?.value || null,
        payment_mode:    form.querySelector('[name="payment_mode"]').value || null,
        amount_paid:     amountPaid,
        old_gold_value:  parseFloat(form.querySelector('[name="old_gold_value"]').value) || 0,
        old_gold_metal_type: oldGoldDetailed
            ? (form.querySelector('[name="old_gold_metal_type"]')?.value || "gold")
            : "gold",
        old_gold_purity: oldGoldDetailed
            ? (form.querySelector('[name="old_gold_purity"]')?.value || null)
            : null,
        old_gold_weight: oldGoldDetailed
            ? (form.querySelector('[name="old_gold_weight"]')?.value || null)
            : null,
        old_gold_rate:   oldGoldDetailed
            ? (form.querySelector('[name="old_gold_rate"]')?.value || null)
            : null,
        discount:        parseFloat(form.querySelector('[name="discount"]').value) || 0,
        notes:           form.querySelector('[name="notes"]').value || null,
        items,
    };

    _savingBill = true;
    _setSaveBillLoading(true);
    try {
        const res  = await fetch("/invoices/create", {
            method:  "POST",
            headers: { "Content-Type": "application/json" },
            body:    JSON.stringify(payload),
        });
        const data = await res.json();

        if (res.ok && data.success) {
            window.location.href = `/invoices/${data.invoice_id}`;
            return;
        }
        alert("Error saving bill:\n" + (data.error || "Unable to save bill."));
    } catch (e) {
        alert("Network error while saving bill. Please try again.");
    } finally {
        _savingBill = false;
        _setSaveBillLoading(false);
    }
}
