/* Invoices (الفواتير) and the exchange rate (سعر الصرف). Loaded after finance.js (uses its helpers) and before admin.js.
   Every amount of an invoice is shown in US dollars and Syrian pounds side by side. The rate is frozen on the invoice when it is made;
   a payment keeps the money that was really handed over. Nothing is deleted: wrong payments are cancelled with a reason. */

var INV_STATUS = {paid: ["مدفوعة", "Paid", "paid"], partial: ["جزئية", "Partly paid", "partial"], open: ["مفتوحة", "Open", "open"], review: ["تحتاج مراجعة", "Needs review", "review"]};
var INV_RATE_SOURCE = {manual: ["سعر يدوي", "Manual rate"], auto: ["سعر تلقائي من الإنترنت", "Automatic rate"], reconstructed: ["سعر مُعاد بناؤه (فاتورة قديمة)", "Reconstructed rate (old invoice)"], none: ["بلا سعر", "No rate"]};

function invNum(text){ return text === null || text === undefined ? "—" : Number(text).toLocaleString("en-US", {minimumFractionDigits: text.indexOf(".") === -1 ? 0 : 2, maximumFractionDigits: 2}); }
function invPairCells(pair, kind){
  return [h("td", {class:"num " + (kind || ""), dir:"ltr", text:invNum(pair.USD)}), h("td", {class:"num " + (kind || ""), dir:"ltr", text:invNum(pair.SYP)})];
}
function invRateText(rate){
  if(!rate) return cbText(["لا يوجد سعر", "No rate"]);
  return "1 USD = " + invNum(rate.syp_per_usd) + " SYP · " + (rate.date || "") + " · " + cbText(INV_RATE_SOURCE[rate.source] || INV_RATE_SOURCE.none) + (rate.frozen ? " · " + cbText(["مثبّت على الفاتورة", "frozen on the invoice"]) : "");
}

/* ---- list ------------------------------------------------------------------------------------------------------ */
function tabInvoices(){
  fill = null;
  var holder = h("div", {}), now = new Date();
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(now.getFullYear())});
  var month = accSelect([["", cbText(["كل الأشهر", "All months"])]].concat(MONTHS_AR.map(function(n, i){ return [String(i + 1), n]; })), String(now.getMonth() + 1));
  var currency = accSelect([["", cbText(["كل العملات", "All currencies"])], ["USD", "USD"], ["SYP", "SYP"]], "");
  var status = accSelect([["", cbText(["كل الحالات", "All states"])], ["open", cbText(INV_STATUS.open)], ["partial", cbText(INV_STATUS.partial)], ["paid", cbText(INV_STATUS.paid)]], "");
  var rateBar = h("div", {class:"a-card a-hintcard"});
  var listBox = h("div", {}), detailBox = h("div", {});
  var children = [];

  function loadRate(){
    return request("/api/admin/accounting/rates").then(function(r){
      rateBar.innerHTML = "";
      rateBar.appendChild(h("p", {text:cbText(["سعر الصرف الحالي: ", "Current rate: "]) + (r.current ? "1 USD = " + invNum(r.current.rate) + " SYP (" + r.current.date + ")" : cbText(["غير مُدخل. أدخله في تبويب «سعر الصرف» قبل إنشاء فاتورة.", "not set. Enter it in the “Rate” tab before making an invoice."]))}));
    }).catch(function(){});
  }
  function load(){
    var q = ["year=" + encodeURIComponent(year.value)];
    if(month.value) q.push("month=" + month.value);
    if(currency.value) q.push("currency=" + currency.value);
    if(status.value) q.push("status=" + status.value);
    listBox.innerHTML = "";
    request("/api/admin/invoices?" + q.join("&")).then(function(data){
      var rows = data.rows.map(function(r){
        var st = INV_STATUS[r.status] || INV_STATUS.open;
        var tr = h("tr", {class:"clickable", tabindex:"0", onclick:function(){ openInvoice(r.id); }}, [
          h("td", {dir:"ltr", text:r.number || "—"}), h("td", {class:"name", dir:"auto", text:r.child.name}), h("td", {text:MONTHS_AR[r.month - 1] + " " + r.year})
        ].concat(invPairCells(r.total), invPairCells(r.paid), invPairCells(r.open, r.status === "paid" ? "" : "due"), [h("td", {}, [cbBadge(cbText(st), st[2])])]));
        tr.addEventListener("keydown", function(e){ if(e.key === "Enter") openInvoice(r.id); });
        return tr;
      });
      var heads = ["#", cbText(["الطفل", "Child"]), cbText(["الشهر", "Month"]), "USD " + cbText(["المطلوب", "due"]), "SYP " + cbText(["المطلوب", "due"]), "USD " + cbText(["المدفوع", "paid"]), "SYP " + cbText(["المدفوع", "paid"]), "USD " + cbText(["المتبقي", "open"]), "SYP " + cbText(["المتبقي", "open"]), cbText(["الحالة", "State"])];
      listBox.appendChild(cbTable(heads, rows, cbText(["لا توجد فواتير", "No invoices"])));
      var t = data.totals;
      listBox.appendChild(h("p", {class:"hint", text:cbText(["المجاميع، كل عملة وحدها (الفواتير المستحقة بها): ", "Totals, each currency on its own (invoices due in it): "]) +
        "USD " + invNum(t.USD.total) + " / " + invNum(t.USD.paid) + " / " + invNum(t.USD.open) + "  ·  SYP " + invNum(t.SYP.total) + " / " + invNum(t.SYP.paid) + " / " + invNum(t.SYP.open) + "  (" + cbText(["المطلوب / المدفوع / المتبقي", "due / paid / open"]) + ")"}));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  [year, month, currency, status].forEach(function(el){ el.addEventListener("change", load); });

  function openInvoice(id){
    detailBox.innerHTML = "";
    request("/api/admin/invoices/" + id).then(function(view){ detailBox.appendChild(invoiceCard(view, function(){ openInvoice(id); load(); })); detailBox.scrollIntoView({behavior:"smooth", block:"start"}); })
      .catch(function(e){ accToast(errText(e), "err"); });
  }

  /* new invoice */
  var child = h("select", {}), newCurrency = accSelect([["USD", ACC_CURRENCY_NAME.USD], ["SYP", ACC_CURRENCY_NAME.SYP]], "USD");
  var newYear = h("input", {type:"number", min:"2000", max:"2100", value:String(now.getFullYear())});
  var newMonth = accSelect(MONTHS_AR.map(function(n, i){ return [String(i + 1), n]; }), String(now.getMonth() + 1));
  var lineBox = h("div", {});
  function addLine(desc, amount){
    var d = h("input", {type:"text", maxlength:"200", value:desc || "", placeholder:cbText(["الوصف (مثل: رسوم شهرية)", "Description (e.g. monthly fee)"])});
    var a = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:amount || "", placeholder:"0.00"});
    var row = h("div", {class:"a-row"}, [accField(cbText(["الوصف", "Description"]), d), accField(cbText(["المبلغ", "Amount"]), a),
      h("button", {type:"button", class:"a-btn ghost", text:"✕", "aria-label":cbText(["إزالة", "Remove"]), onclick:function(){ if(lineBox.children.length > 1) row.remove(); }})]);
    row._d = d; row._a = a;
    lineBox.appendChild(row);
  }
  addLine("", "");
  var newMsg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var form = h("div", {class:"a-card"}, [h("h3", {text:cbText(["فاتورة جديدة", "New invoice"])}),
    h("div", {class:"a-row"}, [accField(cbText(["الطفل", "Child"]), child), accField(cbText(["السنة", "Year"]), newYear), accField(cbText(["الشهر", "Month"]), newMonth), accField(cbText(["عملة الفاتورة", "Invoice currency"]), newCurrency)]),
    lineBox, h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:cbText(["+ بند", "+ Position"]), onclick:function(){ addLine("", ""); }}),
      h("button", {type:"button", class:"a-btn sun", text:cbText(["إنشاء الفاتورة", "Create invoice"]), onclick:function(){
        var lines = Array.prototype.map.call(lineBox.children, function(r){ return {description:r._d.value.trim(), amount:r._a.value}; }).filter(function(l){ return l.amount !== ""; });
        request("/api/admin/invoices", {method:"POST", body:JSON.stringify({child_id:child.value, year:Number(newYear.value), month:Number(newMonth.value), currency:newCurrency.value, lines:lines})})
          .then(function(view){ setMsg(newMsg, cbText(["تم إنشاء الفاتورة ", "Invoice made: "]) + view.number, "ok"); load(); openInvoice(view.id); })
          .catch(function(e){ setMsg(newMsg, errText(e), "err"); });
      }})]), newMsg,
    h("p", {class:"hint", text:cbText(["يُثبَّت سعر اليوم على الفاتورة، ولا يغيّره أي سعر لاحق.", "Today's rate is frozen on the invoice; no later rate changes it."])})]);
  request("/api/admin/accounting/children").then(function(rows){ children = rows; rows.forEach(function(c){ child.appendChild(new Option(c.name + (c.class_name ? " — " + c.class_name : ""), c.id)); }); }).catch(function(){});

  holder.appendChild(rateBar);
  holder.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["الفواتير بالدولار والليرة معاً", "Invoices in dollars and pounds together"])}),
    h("div", {class:"a-row"}, [accField(cbText(["السنة", "Year"]), year), accField(cbText(["الشهر", "Month"]), month), accField(cbText(["العملة", "Currency"]), currency), accField(cbText(["الحالة", "State"]), status)]), listBox]));
  holder.appendChild(detailBox);
  holder.appendChild(form);
  loadRate(); load();
  return h("section", {}, [holder]);
}

/* ---- one invoice ----------------------------------------------------------------------------------------------- */
function invoiceCard(view, reload){
  var st = INV_STATUS[view.status] || INV_STATUS.open;
  var lineRows = view.lines.map(function(l){ return h("tr", {}, [h("td", {dir:"auto", text:l.description || cbText(["رسوم الشهر", "Monthly fee"])}) ].concat(invPairCells(l.amount))); });
  function sumRow(label, pair, cls){ return h("tr", {class:cls || ""}, [h("th", {text:label})].concat(invPairCells(pair, cls))); }
  var table = h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [
    h("thead", {}, [h("tr", {}, [h("th", {text:cbText(["الوصف", "Description"])}), h("th", {text:"USD"}), h("th", {text:"SYP"})])]),
    h("tbody", {}, lineRows.concat([sumRow(cbText(["المجموع", "Total"]), view.total, "total"), sumRow(cbText(["المدفوع", "Already paid"]), view.paid), sumRow(cbText(["المتبقي", "Still open"]), view.open, view.status === "paid" ? "" : "due")]))])]);
  var payRows = view.payments.map(function(p){
    var cancel = p.voided ? cbBadge(cbText(["ملغاة: ", "Cancelled: "]) + p.void_reason, "review") : h("button", {type:"button", class:"a-btn ghost", text:cbText(["إلغاء", "Cancel"]), onclick:function(){ cancelPayment(p.id, reload); }});
    return h("tr", {class:p.voided ? "voided" : ""}, [h("td", {dir:"ltr", text:p.paid_on || "—"}), h("td", {class:"num", dir:"ltr", text:invNum(p.amount) + " " + p.currency}),
      h("td", {class:"num", dir:"ltr", text:p.rate ? "1 USD = " + invNum(p.rate) + " SYP" : "—"}), h("td", {class:"num", dir:"ltr", text:invNum(p.credited) + " " + view.base_currency}),
      h("td", {dir:"auto", text:(p.payer || "") + (p.receipt_no ? " · " + p.receipt_no : "")}), h("td", {}, [cancel])]);
  });
  var pay = payForm(view, reload), edit = editForm(view, reload);
  return h("div", {class:"a-card"}, [
    h("h3", {text:cbText(["فاتورة ", "Invoice "]) + (view.number || "") + " — " + view.child.name + " — " + MONTHS_AR[view.month - 1] + " " + view.year}),
    h("p", {}, [cbBadge(cbText(st), st[2]), h("span", {class:"hint", text:" " + invRateText(view.rate)})]),
    table,
    h("h4", {text:cbText(["الدفعات (العملة الفعلية)", "Payments (the money really handed over)"])}),
    cbTable([cbText(["التاريخ", "Date"]), cbText(["المدفوع فعلياً", "Handed over"]), cbText(["سعر اليوم", "Rate of the day"]), cbText(["قيمتها للفاتورة", "Credited to invoice"]), cbText(["الدافع / الإيصال", "Payer / receipt"]), ""], payRows, cbText(["لا دفعات بعد", "No payments yet"])),
    pay, edit]);
}
function cancelPayment(id, reload){
  var reason = window.prompt(cbText(["سبب الإلغاء (5 أحرف على الأقل):", "Reason for cancelling (at least 5 characters):"]));
  if(reason === null) return;
  request("/api/admin/accounting/finance/payments/" + id + "/void", {method:"POST", body:JSON.stringify({reason:reason})}).then(function(){ accToast(cbText(["أُلغيت الدفعة وبقي سجلها ظاهراً.", "Payment cancelled; its record stays visible."]), "ok"); reload(); })
    .catch(function(e){ accToast(errText(e), "err"); });
}
function payForm(view, reload){
  var cur = accSelect([["USD", "USD"], ["SYP", "SYP"]], view.base_currency);
  var amount = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal"});
  var on = h("input", {type:"date", value:localToday()});
  var payer = h("input", {type:"text", maxlength:"120", list:"acc-payers"}), receipt = h("input", {type:"text", maxlength:"40"});
  var rate = h("input", {type:"number", min:"0", step:"0.000001", inputMode:"decimal", placeholder:cbText(["اتركه فارغاً لسعر اليوم", "leave empty for the rate of the day"])});
  var why = h("input", {type:"text", maxlength:"300", placeholder:cbText(["سبب السعر المختلف", "reason for the different rate"])});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  return h("div", {class:"a-card a-hintcard"}, [h("h4", {text:cbText(["تسجيل دفعة", "Record a payment"])}),
    h("div", {class:"a-row"}, [accField(cbText(["عملة الدفع", "Paid in"]), cur), accField(cbText(["المبلغ", "Amount"]), amount), accField(cbText(["التاريخ", "Date"]), on), accField(cbText(["الدافع", "Payer"]), payer), accField(cbText(["رقم الإيصال", "Receipt no."]), receipt)]),
    h("div", {class:"a-row"}, [accField(cbText(["سعر مختلف (اختياري)", "Different rate (optional)"]), rate), accField(cbText(["السبب", "Reason"]), why),
      h("button", {type:"button", class:"a-btn sun", text:cbText(["تسجيل", "Save payment"]), onclick:function(){
        var body = {paid_currency:cur.value, paid_amount:amount.value, paid_on:on.value, payer_name:payer.value.trim(), receipt_no:receipt.value.trim() || null};
        if(rate.value) { body.rate = rate.value; body.rate_reason = why.value.trim(); }
        request("/api/admin/invoices/" + view.id + "/payments", {method:"POST", body:JSON.stringify(body)}).then(function(){ accToast(cbText(["سُجّلت الدفعة.", "Payment saved."]), "ok"); reload(); })
          .catch(function(e){ setMsg(msg, errText(e), "err"); });
      }})]), msg]);
}
function editForm(view, reload){
  var box = h("div", {}), reason = h("input", {type:"text", maxlength:"300"});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  function line(l){
    var d = h("input", {type:"text", maxlength:"200", value:l ? l.description : ""}), a = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:l ? (l.amount[view.base_currency] || "") : ""});
    var row = h("div", {class:"a-row"}, [accField(cbText(["الوصف", "Description"]), d), accField(cbText(["المبلغ ", "Amount "]) + view.base_currency, a),
      h("button", {type:"button", class:"a-btn ghost", text:"✕", onclick:function(){ if(box.children.length > 1) row.remove(); }})]);
    row._d = d; row._a = a; box.appendChild(row);
  }
  (view.lines.length ? view.lines : [null]).forEach(line);
  var wrap = h("details", {class:"a-card a-hintcard"}, [h("summary", {text:cbText(["تعديل بنود الفاتورة (يُسجَّل السبب والقيم القديمة)", "Change the positions (reason and old values are logged)"])}), box,
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:cbText(["+ بند", "+ Position"]), onclick:function(){ line(null); }}), accField(cbText(["السبب", "Reason"]), reason),
      h("button", {type:"button", class:"a-btn sun", text:cbText(["حفظ التعديل", "Save change"]), onclick:function(){
        var lines = Array.prototype.map.call(box.children, function(r){ return {description:r._d.value.trim(), amount:r._a.value}; }).filter(function(l){ return l.amount !== ""; });
        request("/api/admin/invoices/" + view.id + "/lines", {method:"PUT", body:JSON.stringify({lines:lines, reason:reason.value.trim(), expected_version:view.version})}).then(function(){ accToast(cbText(["حُفظ التعديل. السعر المثبّت لم يتغيّر.", "Saved. The frozen rate did not change."]), "ok"); reload(); })
          .catch(function(e){ setMsg(msg, errText(e), "err"); });
      }})]), msg]);
  return wrap;
}

/* ---- the exchange rate ------------------------------------------------------------------------------------------ */
function tabRates(){
  fill = null;
  var holder = h("div", {}), canSet = !(ACC_VIEWER && ACC_VIEWER.role === "manager");
  var day = h("input", {type:"date", value:localToday()}), rate = h("input", {type:"number", min:"0", step:"0.000001", inputMode:"decimal", placeholder:"12000"});
  var why = h("input", {type:"text", maxlength:"300"}), msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  function draw(){
    holder.innerHTML = "";
    request("/api/admin/accounting/rates").then(function(state){
      var cur = state.current;
      holder.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["سعر الصرف", "Exchange rate"])}),
        h("div", {class:"a-kpis"}, [h("div", {class:"a-kpi good"}, [h("small", {text:cbText(["الدولار بالليرة", "One dollar in pounds"])}), h("strong", {dir:"ltr", text:cur ? invNum(cur.rate) : "—"}), h("small", {class:"hint", text:cur ? cur.date + " · " + cbText(cur.source === "auto" ? INV_RATE_SOURCE.auto : INV_RATE_SOURCE.manual) : cbText(["لم يُدخل بعد", "not set yet"])})])]),
        h("p", {class:"hint", text:cbText(["كل فاتورة جديدة تُثبّت سعر يوم إنشائها. تغيير السعر هنا لا يغيّر فاتورة موجودة. الدفعات بعملة غير عملة الفاتورة تُحوَّل بسعر يوم الدفع.", "Every new invoice freezes the rate of its day. Changing the rate here never changes an invoice that exists. A payment in the other currency is converted with the rate of the day of payment."])})]));
      if(canSet){
        holder.appendChild(h("div", {class:"a-card"}, [h("h4", {text:cbText(["سعر جديد (من تاريخ)", "New rate (from a date)"])}),
          h("div", {class:"a-row"}, [accField(cbText(["من تاريخ", "From"]), day), accField(cbText(["الليرة لكل دولار", "Pounds per dollar"]), rate), accField(cbText(["السبب (إلزامي عند تغيير سعر محفوظ)", "Reason (required when changing a saved rate)"]), why),
            h("button", {type:"button", class:"a-btn sun", text:cbText(["حفظ السعر", "Save rate"]), onclick:function(){
              request("/api/admin/accounting/rates", {method:"PUT", body:JSON.stringify({effective_date:day.value, syp_per_usd:rate.value, reason:why.value.trim()})}).then(function(){ rate.value = ""; why.value = ""; accToast(cbText(["حُفظ السعر.", "Rate saved."]), "ok"); draw(); })
                .catch(function(e){ setMsg(msg, errText(e), "err"); });
            }}),
            h("button", {type:"button", class:"a-btn ghost", text:cbText(["اقتراح من الإنترنت", "Suggest from the internet"]), onclick:function(){
              request("/api/admin/accounting/rates/refresh?force=true", {method:"POST"}).then(function(){ accToast(cbText(["جُلب السعر المقترح. راجعه وأكّده بحفظ سعر يدوي إن لزم.", "Suggested rate fetched. Review it and confirm with a manual rate if needed."]), "ok"); draw(); })
                .catch(function(e){ setMsg(msg, errText(e), "err"); });
            }})]), msg]));
      }
      holder.appendChild(h("div", {class:"a-card"}, [h("h4", {text:cbText(["السجل", "History"])}), cbTable([cbText(["من تاريخ", "From"]), cbText(["السعر", "Rate"]), cbText(["المصدر", "Source"]), cbText(["بواسطة", "By"]), cbText(["السبب", "Reason"])],
        state.rates.map(function(r){ return h("tr", {}, [h("td", {dir:"ltr", text:r.date}), h("td", {class:"num", dir:"ltr", text:invNum(r.rate)}), h("td", {text:cbText(r.source === "auto" ? INV_RATE_SOURCE.auto : INV_RATE_SOURCE.manual)}), h("td", {text:r.by || "—"}), h("td", {dir:"auto", text:r.reason || ""})]); }), cbText(["لا أسعار بعد", "No rates yet"]))]));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  draw();
  return h("section", {}, [holder]);
}
