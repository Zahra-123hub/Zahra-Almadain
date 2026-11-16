/* The accounting: three pages only. Income (الإيرادات), expenses (المصروفات), month overview (الملخص الشهري).
   Every amount stands in US dollars and Syrian pounds side by side. Totals are made per currency from the money really paid in it;
   the value in the other currency is shown beside an entry and never counted a second time.
   Invoices, payments, salaries, the exchange rate and the exports live inside these pages. Nothing is deleted. */

var MN = {meta:null};
var MN_STATUS = {open:["مفتوحة", "Open", "due"], partial:["مدفوعة جزئياً", "Partly paid", "review"], paid:["مدفوعة بالكامل", "Paid", "paid"], void:["ملغاة", "Cancelled", "open"]};

function mnMeta(){ return request("/api/admin/money/meta").then(function(m){ MN.meta = m; return m; }); }
function mnMonthNow(){ var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"); }
function mnShift(value, delta){
  var p = value.split("-"), d = new Date(Number(p[0]), Number(p[1]) - 1 + delta, 1);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}
function mnCells(row, cls){
  return [h("td", {class:"num " + (cls || ""), dir:"ltr", text:uiNum(row.usd)}), h("td", {class:"num " + (cls || ""), dir:"ltr", text:uiNum(row.syp)})];
}
function mnState(row){
  if(row.voided) return uiBadge(uiT(["ملغاة: ", "Cancelled: "]) + row.void_reason, "open");
  if(row.is_reversal) return uiBadge(uiT(["قيد عكسي", "Reversal"]), "review");
  if(row.reversed) return uiBadge(uiT(["صُحّحت بقيد عكسي", "Reversed"]), "review");
  return "";
}
function mnMsg(){ return h("div", {class:"a-msg", role:"status", "aria-live":"polite"}); }
function mnErr(box){ return function(e){ setMsg(box, errText(e), "err"); }; }
function mnAsk(text){ var r = window.prompt(text); return r === null ? null : r.trim(); }

/* the rate strip: shown on every page; the management sets a new rate here (no own page) */
function mnRateBar(meta, again){
  var r = meta.rate;
  var shown = r ? uiNum(r.syp_per_usd) + uiT([" ليرة للدولار الواحد", " pounds for one dollar"]) : uiT(["لا يوجد سعر صرف بعد", "No exchange rate yet"]);
  var how = !r ? uiT(["يُجلب السعر تلقائياً من الإنترنت مرة في اليوم؛ تعذّر الوصول إليه الآن.", "The rate is fetched from the internet once a day; it could not be reached right now."])
    : (r.source === "auto" ? uiT(["تلقائي من الإنترنت", "fetched automatically"]) : uiT(["أدخلته الإدارة", "set by the management"])) + " · " + uiT(["ساري من ", "valid from "]) + r.valid_from +
      (r.stale ? " · " + uiT(["لم يُحدَّث اليوم (الإنترنت غير متاح)", "not updated today (internet not reachable)"]) : "");
  var kids = [h("strong", {text:uiT(["سعر الصرف: ", "Exchange rate: "]) + shown}), h("p", {class:"hint", text:how})];
  if(meta.rights.manage){
    var day = h("input", {type:"date", value:meta.today}), rate = h("input", {type:"number", min:"0", step:"0.000001", inputMode:"decimal", placeholder:"12000", "aria-label":uiT(["ليرة لكل دولار", "Pounds per dollar"])});
    var msg = mnMsg();
    kids.push(h("details", {}, [h("summary", {text:uiT(["تصحيح السعر يدوياً (للإدارة)", "Correct the rate by hand (management)"])}),
      h("div", {class:"a-row"}, [uiField(uiT(["ساري من", "Valid from"]), day), uiField(uiT(["ليرة لكل دولار", "Pounds per dollar"]), rate),
        h("button", {type:"button", class:"a-btn sun", text:uiT(["حفظ التصحيح", "Save correction"]), onclick:function(){
          request("/api/admin/money/rates", {method:"POST", body:JSON.stringify({valid_from:day.value, syp_per_usd:rate.value})})
            .then(function(){ uiToast(uiT(["حُفظ السعر. الحركات الموجودة لا تتغير.", "Rate saved. Existing entries do not change."]), "ok"); again(); }).catch(mnErr(msg));
        }})]), msg]));
  }
  return h("div", {class:"a-card a-hintcard"}, kids);
}

/* the filters of an income / expense list: month, or a date span, a category, a search */
function mnFilters(categories, onChange){
  var month = uiMonthPicker(mnMonthNow(), function(){ onChange(); }), from = h("input", {type:"date"}), to = h("input", {type:"date"});
  var cat = uiSelect([["", uiT(["كل الفئات", "All categories"])]].concat(categories), ""), q = h("input", {type:"search", maxlength:"60"});
  [from, to, cat].forEach(function(el){ el.addEventListener("change", onChange); });
  q.addEventListener("change", onChange);
  return {
    row: h("div", {class:"a-row"}, [uiField(uiT(["الشهر", "Month"]), month), uiField(uiT(["من", "From"]), from), uiField(uiT(["إلى", "To"]), to), uiField(uiT(["الفئة", "Category"]), cat), uiField(uiT(["بحث", "Search"]), q)]),
    query: function(key){
      var p = [];
      if(from.value || to.value){ if(from.value) p.push("date_from=" + from.value); if(to.value) p.push("date_to=" + to.value); } else p.push("month=" + month.value);
      if(cat.value) p.push(key + "=" + encodeURIComponent(cat.value));
      if(q.value.trim()) p.push("q=" + encodeURIComponent(q.value.trim()));
      return p.join("&");
    },
    month: function(){ return month.value; }
  };
}
function mnExport(meta, kind, monthOf){
  if(!meta.rights.export) return "";
  var label = {income:["تنزيل الإيرادات PDF", "Download income as PDF"], expenses:["تنزيل المصروفات PDF", "Download expenses as PDF"], summary:["تقرير الشهر PDF", "Month report as PDF"]}[kind];
  var file = {income:"income", expenses:"expenses", summary:"report"}[kind];
  return h("div", {class:"a-row mn-export"}, [h("button", {type:"button", class:"a-btn sun", text:uiT(label), onclick:function(){
    downloadFile("/api/admin/money/export/" + kind + ".pdf?month=" + monthOf(), file + "-" + monthOf() + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
  }}), h("span", {class:"hint", text:uiT(["موقّع إلكترونياً، بالدولار والليرة", "signed, in dollars and pounds"])})]);
}
/* amount + currency + rate (the rate of the day is proposed; only the management may type another one) */
function mnMoneyFields(meta, row){
  var amount = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:row ? String(row.amount).replace("-", "") : ""});
  var cur = uiSelect([["USD", "USD"], ["SYP", "SYP"]], row ? row.currency : "USD");
  var rate = h("input", {type:"number", min:"0", step:"0.000001", inputMode:"decimal", value:row ? row.rate : (meta.rate ? meta.rate.syp_per_usd : "")});
  if(!meta.rights.manage) rate.readOnly = true;
  var other = h("p", {class:"hint"});
  function show(){
    var n = Number(amount.value), r = Number(rate.value);
    other.textContent = n && r ? uiT(["القيمة بالعملة الأخرى (تقريبية، يحسبها الخادم): ", "Value in the other currency (approximate, the server calculates it): "]) +
      (cur.value === "USD" ? uiNum(String(Math.round(n * r))) + " SYP" : (n / r).toFixed(2) + " USD") : "";
  }
  [amount, cur, rate].forEach(function(el){ el.addEventListener("input", show); el.addEventListener("change", show); });
  show();
  return {
    nodes: [uiField(uiT(["المبلغ", "Amount"]), amount), uiField(uiT(["العملة المدفوعة فعلاً", "Currency really paid"]), cur), uiField(uiT(["سعر الصرف (ليرة لكل دولار)", "Rate (pounds per dollar)"]), rate)],
    preview: other,
    values: function(){ var v = {amount:amount.value, currency:cur.value}; if(meta.rights.manage && rate.value) v.rate = rate.value; return v; },
    dayChanged: function(day){
      if(row) return;
      request("/api/admin/money/rates?day=" + day).then(function(r){ if(r.for_day) { rate.value = r.for_day; show(); } }).catch(function(){});
    }
  };
}

/* ======================================================================================== page 1: income (with invoices) */
function tabIncome(){
  fill = null;
  var page = h("section", {});
  mnMeta().then(function(meta){
    var cats = meta.income_categories.map(function(c){ return [c.id, c.name + (c.is_active ? "" : " (" + uiT(["معطّلة", "off"]) + ")")]; });
    var listBox = h("div", {}), formBox = h("div", {}), invoiceBox = h("div", {});
    var filters = mnFilters(cats, load);
    var children = [];
    function load(){
      listBox.innerHTML = "";
      request("/api/admin/money/income?" + filters.query("category_id")).then(function(d){
        var rows = d.rows.map(function(r){
          var acts = [];
          if(meta.rights.correct && !r.voided && !r.is_reversal && !r.reversed){
            if(!r.month_closed) acts.push(h("button", {type:"button", class:"a-btn ghost", text:uiT(["تعديل", "Change"]), onclick:function(){ showForm(r); }}));
            acts.push(h("button", {type:"button", class:"a-btn ghost", text:r.month_closed ? uiT(["قيد عكسي", "Reverse"]) : uiT(["إلغاء", "Cancel"]), onclick:function(){ cancel("income", r); }}));
          }
          acts.push(h("button", {type:"button", class:"a-btn ghost", text:uiT(["السجل", "History"]), onclick:function(){ mnHistory(r.id, listBox); }}));
          var who = [r.payer_name, r.child, r.description.indexOf(r.invoice_number) === -1 ? r.invoice_number : ""].filter(Boolean).join(" · ");
          return h("tr", {class:r.voided ? "voided" : ""}, [h("td", {dir:"ltr", text:r.booked_on}),
            h("td", {dir:"auto"}, [h("span", {text:r.description}), who ? h("small", {class:"hint", text:" — " + who}) : "", r.note ? h("small", {class:"hint", text:" (" + r.note + ")"}) : "", mnState(r)]),
            h("td", {text:r.category})].concat(mnCells(r), [h("td", {dir:"ltr", text:uiNum(r.amount) + " " + r.currency + " @ " + uiNum(r.rate)}), h("td", {}, acts)]));
        });
        listBox.appendChild(uiTable([uiT(["التاريخ", "Date"]), uiT(["الوصف", "Description"]), uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["المدفوع فعلاً", "Really paid"]), ""], rows, uiT(["لا توجد إيرادات", "No income"]), 860));
        listBox.appendChild(h("p", {class:"hint", text:uiT(["المجموع: ", "Total: "]) + "USD " + uiNum(d.totals.value.USD) + " · SYP " + uiNum(d.totals.value.SYP) + uiT([" (منها مدفوع فعلاً بالدولار ", " (of which really paid in dollars "]) + uiNum(d.totals.USD) + uiT([" وبالليرة ", " and in pounds "]) + uiNum(d.totals.SYP) + ")" + " · " + d.count + " " + uiT(["حركة", "entries"])}));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function showForm(row){
      formBox.innerHTML = "";
      var day = h("input", {type:"date", max:meta.today, value:row ? row.booked_on : meta.today});
      var desc = h("input", {type:"text", maxlength:"300", value:row ? row.description : "", placeholder:uiT(["سبب الإيراد", "Reason"])});
      var cat = uiSelect(meta.income_categories.filter(function(c){ return c.is_active || (row && c.id === row.category_id); }).map(function(c){ return [c.id, c.name]; }), row ? row.category_id : undefined);
      var child = uiSelect([["", "—"]].concat(children.map(function(c){ return [c.id, c.name]; })), row ? row.child_id : "");
      var payer = h("input", {type:"text", maxlength:"120", value:row ? row.payer_name : ""}), note = h("input", {type:"text", maxlength:"500", value:row ? row.note : ""});
      var m = mnMoneyFields(meta, row), msg = mnMsg();
      day.addEventListener("change", function(){ m.dayChanged(day.value); });
      var save = h("button", {type:"button", class:"a-btn sun", text:row ? uiT(["حفظ التعديل", "Save change"]) : uiT(["تسجيل الإيراد", "Record income"]), onclick:function(){
        var body = Object.assign({booked_on:day.value, description:desc.value.trim(), category_id:cat.value, child_id:child.value || null, payer_name:payer.value.trim(), note:note.value.trim()}, m.values());
        if(row) body.expected_version = row.version;
        request("/api/admin/money/income" + (row ? "/" + row.id : ""), {method:row ? "PATCH" : "POST", body:JSON.stringify(body)})
          .then(function(){ uiToast(uiT(["تم الحفظ.", "Saved."]), "ok"); showForm(null); load(); }).catch(mnErr(msg));
      }});
      if(!meta.rate) save.disabled = true;
      formBox.appendChild(h("div", {class:"a-card"}, [h("h3", {text:row ? uiT(["تعديل الإيراد", "Change the income"]) : uiT(["إيراد جديد", "New income"])}),
        h("div", {class:"a-row"}, [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["السبب", "Reason"]), desc), uiField(uiT(["الفئة", "Category"]), cat)]),
        h("div", {class:"a-row"}, [uiField(uiT(["الطفل (اختياري)", "Child (optional)"]), child), uiField(uiT(["الدافع (اختياري)", "Payer (optional)"]), payer)].concat(m.nodes)),
        h("div", {class:"a-row"}, [uiField(uiT(["ملاحظة", "Note"]), note)]), m.preview,
        h("div", {class:"a-row"}, [save, row ? h("button", {type:"button", class:"a-btn ghost", text:uiT(["إغلاق", "Close"]), onclick:function(){ showForm(null); }}) : ""]), msg]));
    }
    function cancel(kind, row){
      var reason = mnAsk(row.month_closed ? uiT(["الشهر مغلق: يُسجَّل قيد عكسي اليوم. السبب (5 أحرف على الأقل):", "The month is closed: a reversal is booked today. Reason (at least 5 characters):"]) : uiT(["سبب الإلغاء (5 أحرف على الأقل):", "Reason for cancelling (at least 5 characters):"]));
      if(reason === null) return;
      request("/api/admin/money/" + kind + "/" + row.id + "/void", {method:"POST", body:JSON.stringify({reason:reason})})
        .then(function(){ uiToast(uiT(["تم. السجل يبقى ظاهراً.", "Done. The record stays visible."]), "ok"); load(); loadInvoices(); }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    /* invoices: a claim, not an income; a payment is an income tied to the invoice */
    var invStatus = uiSelect([["unpaid", uiT(["غير مسددة", "Unpaid"])], ["", uiT(["كل الفواتير", "All invoices"])], ["paid", uiT(MN_STATUS.paid)], ["void", uiT(MN_STATUS.void)]], "unpaid");
    invStatus.addEventListener("change", loadInvoices);
    var invList = h("div", {}), invDetail = h("div", {});
    function loadInvoices(){
      invList.innerHTML = "";
      request("/api/admin/money/invoices?status=" + invStatus.value).then(function(d){
        invList.appendChild(uiTable(["#", uiT(["التاريخ", "Date"]), uiT(["الطفل / الدافع", "Child / payer"]), "USD " + uiT(["المجموع", "total"]), "SYP " + uiT(["المجموع", "total"]),
          "USD " + uiT(["المتبقي", "open"]), "SYP " + uiT(["المتبقي", "open"]), uiT(["الحالة", "Status"])], d.rows.map(function(r){
          var st = MN_STATUS[r.status];
          var tr = h("tr", {class:"clickable", tabindex:"0", onclick:function(){ openInvoice(r.id); }}, [h("td", {dir:"ltr", text:r.number}), h("td", {dir:"ltr", text:r.issued_on}),
            h("td", {text:r.child || r.payer_name})].concat(mnCells(r.total), mnCells(r.open, r.status === "paid" ? "" : "due"), [h("td", {}, [uiBadge(uiT(st), st[2])])]));
          tr.addEventListener("keydown", function(e){ if(e.key === "Enter") openInvoice(r.id); });
          return tr;
        }), uiT(["لا توجد فواتير", "No invoices"]), 820));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function openInvoice(id){
      invDetail.innerHTML = "";
      request("/api/admin/money/invoices/" + id).then(function(v){
        var st = MN_STATUS[v.status];
        function line(label, pair, cls){ return h("tr", {class:cls || ""}, [h("th", {text:label})].concat(mnCells(pair, cls))); }
        var table = h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, [h("th", {text:uiT(["البند", "Item"])}), h("th", {text:"USD"}), h("th", {text:"SYP"})])]),
          h("tbody", {}, v.items.map(function(i){ return h("tr", {}, [h("td", {dir:"auto", text:i.description})].concat(mnCells(i))); })
            .concat([line(uiT(["المجموع", "Total"]), v.total, "total"), line(uiT(["المدفوع", "Paid"]), v.paid), line(uiT(["المتبقي", "Open"]), v.open, v.status === "paid" ? "" : "due")]))])]);
        var pays = uiTable([uiT(["التاريخ", "Date"]), uiT(["المدفوع فعلاً", "Really paid"]), uiT(["السعر", "Rate"]), uiT(["قيمتها للفاتورة", "Credited"]), ""], v.payments.map(function(p){
          return h("tr", {class:p.voided ? "voided" : ""}, [h("td", {dir:"ltr", text:p.booked_on}), h("td", {dir:"ltr", text:uiNum(p.amount) + " " + p.currency}), h("td", {dir:"ltr", text:uiNum(p.rate)}),
            h("td", {dir:"ltr", text:uiNum(p.credited) + " " + v.currency}), h("td", {}, [p.voided ? uiBadge(uiT(["ملغاة: ", "Cancelled: "]) + p.void_reason, "open") : ""])]);
        }), uiT(["لا دفعات بعد", "No payments yet"]));
        var kids = [h("h3", {text:uiT(["فاتورة ", "Invoice "]) + v.number + " — " + (v.child || v.payer_name)}),
          h("p", {}, [uiBadge(uiT(st), st[2]), h("span", {class:"hint", text:" " + v.issued_on + " · " + uiT(["العملة ", "currency "]) + v.currency + " · 1 USD = " + uiNum(v.rate) + " SYP" + (v.description ? " · " + v.description : "")})]),
          h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:uiT(["تنزيل الفاتورة PDF (موقّعة)", "Download the invoice as PDF (signed)"]), onclick:function(){
            downloadFile("/api/admin/money/invoices/" + v.id + ".pdf", v.number + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
          }})]),
          table, h("h4", {text:uiT(["الدفعات", "Payments"])}), pays];
        if(v.status === "open" || v.status === "partial"){
          var day = h("input", {type:"date", max:meta.today, value:meta.today}), payer = h("input", {type:"text", maxlength:"120", value:v.payer_name});
          var m = mnMoneyFields(meta, null), msg = mnMsg();
          day.addEventListener("change", function(){ m.dayChanged(day.value); });
          kids.push(h("div", {class:"a-card a-hintcard"}, [h("h4", {text:uiT(["تسجيل دفعة (تُسجَّل إيراداً مرتبطاً بالفاتورة)", "Record a payment (it becomes an income tied to the invoice)"])}),
            h("div", {class:"a-row"}, [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["الدافع", "Payer"]), payer)].concat(m.nodes)), m.preview,
            h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:uiT(["تسجيل الدفعة", "Record payment"]), onclick:function(){
              request("/api/admin/money/invoices/" + v.id + "/payments", {method:"POST", body:JSON.stringify(Object.assign({booked_on:day.value, payer_name:payer.value.trim()}, m.values()))})
                .then(function(){ uiToast(uiT(["سُجّلت الدفعة.", "Payment recorded."]), "ok"); openInvoice(v.id); loadInvoices(); load(); }).catch(mnErr(msg));
            }})]), msg]));
        }
        if(meta.rights.correct && v.status === "open" && !v.voided){
          kids.push(h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:uiT(["إلغاء الفاتورة", "Cancel the invoice"]), onclick:function(){
            var reason = mnAsk(uiT(["سبب إلغاء الفاتورة (5 أحرف على الأقل):", "Reason (at least 5 characters):"]));
            if(reason === null) return;
            request("/api/admin/money/invoices/" + v.id + "/void", {method:"POST", body:JSON.stringify({reason:reason})}).then(function(){ openInvoice(v.id); loadInvoices(); }).catch(function(e){ uiToast(errText(e), "err"); });
          }})]));
        }
        invDetail.appendChild(h("div", {class:"a-card"}, kids));
        invDetail.scrollIntoView({behavior:"smooth", block:"start"});
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function invoiceForm(){
      var box = h("div", {}), items = h("div", {});
      var day = h("input", {type:"date", max:meta.today, value:meta.today});
      var child = uiSelect([["", "—"]].concat(children.map(function(c){ return [c.id, c.name]; })), "");
      var payer = h("input", {type:"text", maxlength:"120"}), desc = h("input", {type:"text", maxlength:"300"});
      var cur = uiSelect([["USD", "USD"], ["SYP", "SYP"]], "USD");
      var msg = mnMsg();
      function item(){
        var d = h("input", {type:"text", maxlength:"200", placeholder:uiT(["البند (مثل: رسوم شهرية)", "Item (e.g. monthly fee)"])}), a = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal"});
        var row = h("div", {class:"a-row"}, [uiField(uiT(["البند", "Item"]), d), uiField(uiT(["المبلغ", "Amount"]), a), h("button", {type:"button", class:"a-btn ghost", text:"✕", "aria-label":uiT(["إزالة", "Remove"]), onclick:function(){ if(items.children.length > 1) row.remove(); }})]);
        row._d = d; row._a = a; items.appendChild(row);
      }
      item();
      box.appendChild(h("details", {class:"a-card"}, [h("summary", {text:uiT(["+ فاتورة جديدة", "+ New invoice"])}),
        h("div", {class:"a-row"}, [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["الطفل", "Child"]), child), uiField(uiT(["أو الجهة الدافعة", "or the payer"]), payer), uiField(uiT(["عملة الفاتورة", "Invoice currency"]), cur)]),
        h("div", {class:"a-row"}, [uiField(uiT(["الوصف", "Description"]), desc)]), items,
        h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:uiT(["+ بند", "+ Item"]), onclick:item}),
          h("button", {type:"button", class:"a-btn sun", text:uiT(["إنشاء الفاتورة", "Create invoice"]), onclick:function(){
            var list = Array.prototype.map.call(items.children, function(r){ return {description:r._d.value.trim(), amount:r._a.value}; }).filter(function(i){ return i.amount !== ""; });
            request("/api/admin/money/invoices", {method:"POST", body:JSON.stringify({issued_on:day.value, child_id:child.value || null, payer_name:payer.value.trim(), description:desc.value.trim(), currency:cur.value, items:list})})
              .then(function(v){ uiToast(uiT(["أُنشئت الفاتورة ", "Invoice made: "]) + v.number, "ok"); loadInvoices(); openInvoice(v.id); }).catch(mnErr(msg));
          }})]),
        h("p", {class:"hint", text:uiT(["الفاتورة مطالبة وليست إيراداً. يدخل المال في الإيرادات عند تسجيل الدفعة فقط.", "An invoice is a claim, not income. Money counts as income only when a payment is recorded."])}), msg]));
      return box;
    }
    function categoryCard(){
      if(!meta.rights.manage) return "";
      var name = h("input", {type:"text", maxlength:"80"}), msg = mnMsg();
      var rows = meta.income_categories.map(function(c){
        return h("tr", {}, [h("td", {text:c.name}), h("td", {}, [c.key === "tuition" ? h("span", {class:"hint", text:uiT(["أساسية", "built in"])}) :
          h("button", {type:"button", class:"a-btn ghost", text:c.is_active ? uiT(["تعطيل", "Switch off"]) : uiT(["تفعيل", "Switch on"]), onclick:function(){
            request("/api/admin/money/categories/" + c.id, {method:"PATCH", body:JSON.stringify({is_active:!c.is_active})}).then(function(){ draw(); }).catch(mnErr(msg));
          }})])]);
      });
      return h("details", {class:"a-card"}, [h("summary", {text:uiT(["فئات الإيرادات (للإدارة)", "Income categories (management)"])}), uiTable([uiT(["الفئة", "Category"]), ""], rows, ""),
        h("div", {class:"a-row"}, [uiField(uiT(["فئة جديدة", "New category"]), name), h("button", {type:"button", class:"a-btn ghost", text:uiT(["إضافة", "Add"]), onclick:function(){
          request("/api/admin/money/categories", {method:"POST", body:JSON.stringify({name:name.value.trim()})}).then(function(){ draw(); }).catch(mnErr(msg));
        }})]), msg]);
    }
    request("/api/admin/people/children").then(function(list){ children = list; showForm(null); }).catch(function(){ showForm(null); });
    page.appendChild(mnRateBar(meta, function(){ draw(); }));
    page.appendChild(formBox);
    page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الإيرادات", "Income"])}), filters.row, mnExport(meta, "income", filters.month), listBox]));
    page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الفواتير", "Invoices"])}), h("div", {class:"a-row"}, [uiField(uiT(["الحالة", "Status"]), invStatus)]), invList]));
    page.appendChild(invDetail);
    page.appendChild(invoiceForm());
    var cc = categoryCard(); if(cc) page.appendChild(cc);
    load(); loadInvoices();
  }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  return page;
}

function mnHistory(id, near){
  request("/api/admin/money/history/" + id).then(function(rows){
    uiToast(rows.map(function(r){ return r.at.replace("T", " ").slice(0, 16) + " " + r.actor + ": " + r.action + (r.reason ? " (" + r.reason + ")" : ""); }).join(" · ") || uiT(["لا سجل", "No history"]), "ok");
  }).catch(function(e){ uiToast(errText(e), "err"); });
}

/* ======================================================================================== page 2: expenses (with salaries) */
function tabExpense(){
  fill = null;
  var page = h("section", {});
  mnMeta().then(function(meta){
    var cats = meta.expense_categories.map(function(c){ return [c.key, uiT([c.ar, c.en])]; });
    var listBox = h("div", {}), formBox = h("div", {}), salaryBox = h("div", {});
    var filters = mnFilters(cats, function(){ load(); loadSalaries(); });
    var staff = [];
    function load(){
      listBox.innerHTML = "";
      request("/api/admin/money/expenses?" + filters.query("category")).then(function(d){
        var rows = d.rows.map(function(r){
          var acts = [];
          if(meta.rights.correct && !r.voided && !r.is_reversal && !r.reversed){
            if(!r.month_closed) acts.push(h("button", {type:"button", class:"a-btn ghost", text:uiT(["تعديل", "Change"]), onclick:function(){ showForm(r); }}));
            acts.push(h("button", {type:"button", class:"a-btn ghost", text:r.month_closed ? uiT(["قيد عكسي", "Reverse"]) : uiT(["إلغاء", "Cancel"]), onclick:function(){ cancel(r); }}));
          }
          acts.push(h("button", {type:"button", class:"a-btn ghost", text:uiT(["السجل", "History"]), onclick:function(){ mnHistory(r.id); }}));
          var extra = [r.employee, r.salary_month].filter(Boolean).join(" · ");
          return h("tr", {class:r.voided ? "voided" : ""}, [h("td", {dir:"ltr", text:r.booked_on}),
            h("td", {dir:"auto"}, [h("span", {text:r.description}), extra ? h("small", {class:"hint", text:" — " + extra}) : "", r.note ? h("small", {class:"hint", text:" (" + r.note + ")"}) : "", mnState(r)]),
            h("td", {text:uiT([r.category_ar, r.category_en])})].concat(mnCells(r), [h("td", {dir:"auto", text:r.recipient || "—"}), h("td", {dir:"ltr", text:uiNum(r.amount) + " " + r.currency}), h("td", {}, acts)]));
        });
        listBox.appendChild(uiTable([uiT(["التاريخ", "Date"]), uiT(["الوصف", "Description"]), uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["المستلم", "Recipient"]), uiT(["المدفوع فعلاً", "Really paid"]), ""], rows, uiT(["لا توجد مصروفات", "No expenses"]), 900));
        listBox.appendChild(h("p", {class:"hint", text:uiT(["المجموع: ", "Total: "]) + "USD " + uiNum(d.totals.value.USD) + " · SYP " + uiNum(d.totals.value.SYP) + uiT([" (منها مدفوع فعلاً بالدولار ", " (of which really paid in dollars "]) + uiNum(d.totals.USD) + uiT([" وبالليرة ", " and in pounds "]) + uiNum(d.totals.SYP) + ")" + " · " + d.count + " " + uiT(["حركة", "entries"])}));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function cancel(row){
      var reason = mnAsk(row.month_closed ? uiT(["الشهر مغلق: يُسجَّل قيد عكسي اليوم. السبب (5 أحرف على الأقل):", "The month is closed: a reversal is booked today. Reason (at least 5 characters):"]) : uiT(["سبب الإلغاء (5 أحرف على الأقل):", "Reason for cancelling (at least 5 characters):"]));
      if(reason === null) return;
      request("/api/admin/money/expenses/" + row.id + "/void", {method:"POST", body:JSON.stringify({reason:reason})})
        .then(function(){ uiToast(uiT(["تم. السجل يبقى ظاهراً.", "Done. The record stays visible."]), "ok"); load(); loadSalaries(); }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function showForm(row, salaryFor){
      formBox.innerHTML = "";
      var day = h("input", {type:"date", max:meta.today, value:row ? row.booked_on : meta.today});
      var desc = h("input", {type:"text", maxlength:"300", value:row ? row.description : salaryFor ? uiT(["راتب ", "Salary "]) + salaryFor.name : "", placeholder:uiT(["سبب المصروف", "Reason"])});
      var cat = uiSelect(cats, row ? row.category : salaryFor ? "salaries" : "food");
      var person = uiSelect([["", "—"]].concat(staff.map(function(p){ return [p.id, p.name]; })), row ? row.employee_id : salaryFor ? salaryFor.employee_id : "");
      var month = uiMonthPicker(row && row.salary_month ? row.salary_month : filters.month());
      var recipient = h("input", {type:"text", maxlength:"120", value:row ? row.recipient : salaryFor ? salaryFor.name : ""}), note = h("input", {type:"text", maxlength:"500", value:row ? row.note : ""});
      var m = mnMoneyFields(meta, row || (salaryFor && salaryFor.salary ? {amount:salaryFor.salary, currency:salaryFor.salary_currency, rate:meta.rate ? meta.rate.syp_per_usd : ""} : null));
      var salaryRow = h("div", {class:"a-row"}, [uiField(uiT(["الموظف", "Staff member"]), person), uiField(uiT(["شهر الراتب", "Salary for month"]), month)]);
      function sync(){ salaryRow.hidden = cat.value !== "salaries"; }
      cat.addEventListener("change", sync); sync();
      day.addEventListener("change", function(){ m.dayChanged(day.value); });
      var msg = mnMsg();
      var save = h("button", {type:"button", class:"a-btn sun", text:row ? uiT(["حفظ التعديل", "Save change"]) : uiT(["تسجيل المصروف", "Record expense"]), onclick:function(){
        var salary = cat.value === "salaries";
        var body = Object.assign({booked_on:day.value, description:desc.value.trim(), category:cat.value, recipient:recipient.value.trim(), note:note.value.trim(),
          employee_id:salary && person.value ? person.value : null, salary_month:salary ? month.value : null}, m.values());
        if(row) body.expected_version = row.version;
        request("/api/admin/money/expenses" + (row ? "/" + row.id : ""), {method:row ? "PATCH" : "POST", body:JSON.stringify(body)})
          .then(function(){ uiToast(uiT(["تم الحفظ.", "Saved."]), "ok"); showForm(null); load(); loadSalaries(); }).catch(mnErr(msg));
      }});
      if(!meta.rate) save.disabled = true;
      formBox.appendChild(h("div", {class:"a-card"}, [h("h3", {text:row ? uiT(["تعديل المصروف", "Change the expense"]) : salaryFor ? uiT(["صرف الراتب", "Pay the salary"]) : uiT(["مصروف جديد", "New expense"])}),
        h("div", {class:"a-row"}, [uiField(uiT(["تاريخ الدفع", "Date paid"]), day), uiField(uiT(["السبب", "Reason"]), desc), uiField(uiT(["الفئة", "Category"]), cat)]), salaryRow,
        h("div", {class:"a-row"}, [uiField(uiT(["المستلم (اختياري)", "Recipient (optional)"]), recipient)].concat(m.nodes)),
        h("div", {class:"a-row"}, [uiField(uiT(["ملاحظة", "Note"]), note)]), m.preview,
        h("p", {class:"hint", text:uiT(["يُسجَّل المصروف بعد الدفع فعلاً فقط.", "Record an expense only once it was really paid."])}),
        h("div", {class:"a-row"}, [save, row || salaryFor ? h("button", {type:"button", class:"a-btn ghost", text:uiT(["إغلاق", "Close"]), onclick:function(){ showForm(null); }}) : ""]), msg]));
      if(row || salaryFor) formBox.scrollIntoView({behavior:"smooth", block:"start"});
    }
    function loadSalaries(){
      salaryBox.innerHTML = "";
      request("/api/admin/money/salaries?month=" + filters.month()).then(function(d){
        var rows = d.rows.map(function(r){
          return h("tr", {}, [h("td", {class:"name", text:r.name + (r.is_active ? "" : " (" + uiT(["غادر", "left"]) + ")")}), h("td", {text:r.job_title || "—"}),
            h("td", {dir:"ltr", text:r.salary ? uiNum(r.salary) + " " + r.salary_currency : "—"}),
            h("td", {}, [r.paid ? uiBadge((r.automatic ? uiT(["سُجّل تلقائياً ", "Booked automatically "]) : uiT(["صُرف ", "Paid "])) + r.paid_on + " · " + uiNum(r.paid_amount) + " " + r.paid_currency, "paid") : uiBadge(uiT(["لم يُصرف", "Not paid"]), "due")]),
            h("td", {}, [r.paid || !r.is_active ? "" : h("button", {type:"button", class:"a-btn ghost", text:uiT(["صرف الراتب", "Pay salary"]), onclick:function(){ showForm(null, r); }})])]);
        });
        salaryBox.appendChild(h("h4", {text:uiT(["رواتب ", "Salaries of "]) + d.month + ": " + d.paid + " " + uiT(["صُرفت", "paid"]) + " · " + d.unpaid + " " + uiT(["لم تُصرف", "not paid"])}));
        salaryBox.appendChild(uiTable([uiT(["الموظف", "Staff member"]), uiT(["الوظيفة", "Job"]), uiT(["الراتب المعتاد", "Usual salary"]), uiT(["الحالة", "Status"]), ""], rows, uiT(["لا يوجد موظفون", "No staff"])));
        salaryBox.appendChild(h("p", {class:"hint", text:uiT(["تُسجَّل رواتب الشهر تلقائياً كمصروف في أول الشهر التالي، بالراتب المحفوظ لكل موظف. ما صُرف يدوياً أو أُلغي لا يُسجَّل مرة ثانية؛ والراتب التلقائي يمكن تعديله أو إلغاؤه كأي مصروف.",
          "The salaries of a month are booked automatically as an expense on the 1st of the next month, with the saved salary of each person. What was paid by hand or cancelled is not booked again; an automatic salary can be changed or cancelled like any expense."])}));
        salaryBox.appendChild(h("p", {class:"hint", text:uiT(["الموظفون تديرهم الإدارة في بوابة الإدارة. المحاسبة تقرأ القائمة فقط.", "Staff are managed by the management portal. The accounting only reads the list."])}));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function staffExport(){
      if(!meta.rights.manage) return "";
      var scope = uiSelect([["all", uiT(["كل الموظفين", "All staff"])], ["active", uiT(["الفعّالون فقط", "Active only"])]], "all");
      return h("div", {class:"a-row"}, [h("span", {class:"hint", text:uiT(["قائمة الموظفين:", "Staff list:"])}), scope,
        h("button", {type:"button", class:"a-btn sun", text:uiT(["تنزيل قائمة الموظفين PDF", "Download the staff list as PDF"]), onclick:function(){
          downloadFile("/api/admin/people/employees/export.pdf?scope=" + scope.value, "staff-" + scope.value + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
        }})]);
    }
    request("/api/admin/people/employees").then(function(list){ staff = list; showForm(null); }).catch(function(){ showForm(null); });
    page.appendChild(mnRateBar(meta, function(){ draw(); }));
    page.appendChild(formBox);
    page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["المصروفات", "Expenses"])}), filters.row, mnExport(meta, "expenses", filters.month), listBox]));
    page.appendChild(h("div", {class:"a-card"}, [salaryBox, staffExport()]));
    load(); loadSalaries();
  }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  return page;
}

/* ======================================================================================== page 3: the month overview */
function tabSummary(){
  fill = null;
  var page = h("section", {}), month = mnMonthNow();
  function draw3(){
    page.innerHTML = "";
    Promise.all([mnMeta(), request("/api/admin/money/summary?month=" + month)]).then(function(res){
      var meta = res[0], d = res[1];
      var picker = uiMonthPicker(month, function(v){ month = v; draw3(); });
      function pct(c){ return c.percent === null ? "—" : (Number(c.percent) > 0 ? "+" : "") + c.percent + " %"; }
      function line(label, key, cls){
        return h("tr", {class:cls || ""}, [h("th", {text:label}), h("td", {class:"num", dir:"ltr", text:uiNum(d[key].usd)}), h("td", {class:"num", dir:"ltr", text:uiNum(d[key].syp)}),
          h("td", {class:"num", dir:"ltr", text:uiNum(d.change[key].usd.difference) + " (" + pct(d.change[key].usd) + ")"}), h("td", {class:"num", dir:"ltr", text:uiNum(d.change[key].syp.difference) + " (" + pct(d.change[key].syp) + ")"})]);
      }
      var main = h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [
        h("thead", {}, [h("tr", {}, [h("th", {text:""}), h("th", {text:"USD"}), h("th", {text:"SYP"}), h("th", {text:"USD " + uiT(["مقابل ", "vs "]) + d.previous_month}), h("th", {text:"SYP " + uiT(["مقابل ", "vs "]) + d.previous_month})])]),
        h("tbody", {}, [line(uiT(["إجمالي الإيرادات", "Total income"]), "income"), line(uiT(["إجمالي المصروفات", "Total expenses"]), "expense"), line(uiT(["الفائض / العجز", "Surplus / deficit"]), "surplus", "total")])])]);
      var closeRow = "";
      if(meta.rights.manage){
        var p = month.split("-");
        closeRow = d.closed
          ? h("button", {type:"button", class:"a-btn ghost", text:uiT(["إعادة فتح الشهر", "Reopen the month"]), onclick:function(){
              var reason = mnAsk(uiT(["سبب إعادة الفتح (5 أحرف على الأقل):", "Reason for reopening (at least 5 characters):"]));
              if(reason === null) return;
              request("/api/admin/money/closings/" + Number(p[0]) + "/" + Number(p[1]) + "/reopen", {method:"POST", body:JSON.stringify({reason:reason})}).then(draw3).catch(function(e){ uiToast(errText(e), "err"); });
            }})
          : h("button", {type:"button", class:"a-btn", text:uiT(["إغلاق الشهر", "Close the month"]), onclick:function(){
              if(!window.confirm(uiT(["بعد الإغلاق لا تُسجَّل ولا تُعدَّل حركات هذا الشهر. متابعة؟", "After closing nothing in this month can be added or changed. Continue?"]))) return;
              request("/api/admin/money/closings", {method:"POST", body:JSON.stringify({year:Number(p[0]), month:Number(p[1])})}).then(draw3).catch(function(e){ uiToast(errText(e), "err"); });
            }});
      }
      function catTable(rows, name){
        return uiTable([uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["العدد", "Entries"])], rows.map(function(r){
          return h("tr", {}, [h("td", {text:name(r)}), h("td", {class:"num", dir:"ltr", text:uiNum(r.usd)}), h("td", {class:"num", dir:"ltr", text:uiNum(r.syp)}), h("td", {class:"num", text:String(r.count)})]);
        }), uiT(["لا حركات", "No entries"]));
      }
      page.appendChild(mnRateBar(meta, draw3));
      page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الملخص الشهري", "Month overview"])}),
        h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"▶", "aria-label":uiT(["الشهر السابق", "Previous month"]), onclick:function(){ month = mnShift(month, -1); draw3(); }}), uiField(uiT(["الشهر", "Month"]), picker),
          h("button", {type:"button", class:"a-btn ghost", text:"◀", "aria-label":uiT(["الشهر التالي", "Next month"]), onclick:function(){ month = mnShift(month, 1); draw3(); }}),
          uiBadge(d.closed ? uiT(["مغلق", "Closed"]) + (d.closing ? " · " + d.closing.by : "") : uiT(["مفتوح", "Open"]), d.closed ? "paid" : "open"), closeRow]),
        main,
        h("p", {class:"hint", text:uiT(["كل عمود يجمع المال المدفوع فعلاً بعملته. لا يُجمع الدولار والليرة معاً.", "Each column adds the money really paid in its currency. Dollars and pounds are never added together."])}),
        h("p", {class:"hint", text:uiT(["للمقارنة فقط — كل الحركات محوّلة بسعرها المحفوظ: الفائض ", "For comparison only — every entry converted at its stored rate: surplus "]) + "USD " + uiNum(d.converted.surplus.usd) + " / SYP " + uiNum(d.converted.surplus.syp)}),
        h("div", {class:"a-kpis"}, [
          h("div", {class:"a-kpi"}, [h("small", {text:uiT(["حركات الإيراد", "Income entries"])}), h("strong", {text:String(d.income_count)})]),
          h("div", {class:"a-kpi"}, [h("small", {text:uiT(["حركات المصروف", "Expense entries"])}), h("strong", {text:String(d.expense_count)})]),
          h("div", {class:"a-kpi"}, [h("small", {text:uiT(["الرواتب", "Salaries"])}), h("strong", {dir:"ltr", text:"USD " + uiNum(d.salaries.usd) + " · SYP " + uiNum(d.salaries.syp)})]),
          h("div", {class:"a-kpi"}, [h("small", {text:uiT(["مصروفات أخرى", "Other expenses"])}), h("strong", {dir:"ltr", text:"USD " + uiNum(d.other_expenses.usd) + " · SYP " + uiNum(d.other_expenses.syp)})]),
          h("div", {class:"a-kpi" + (d.invoices.open + d.invoices.partial ? " due" : "")}, [h("small", {text:uiT(["فواتير مفتوحة / جزئية", "Invoices open / partly paid"])}), h("strong", {text:d.invoices.open + " / " + d.invoices.partial}),
            h("small", {class:"hint", dir:"ltr", text:"USD " + uiNum(d.invoices.open_amount.usd) + " · SYP " + uiNum(d.invoices.open_amount.syp)})])
        ]),
        mnExport(meta, "summary", function(){ return month; })]));
      page.appendChild(h("div", {class:"a-card"}, [h("h4", {text:uiT(["الإيرادات حسب الفئة", "Income by category"])}), catTable(d.income_by_category, function(r){ return r.name; }),
        h("h4", {text:uiT(["المصروفات حسب الفئة", "Expenses by category"])}), catTable(d.expense_by_category, function(r){ return uiT([r.ar, r.en]); })]));
    }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  }
  draw3();
  return page;
}

/* ======================================================================================== the one menu entry "المحاسبة" */
/* The accounting is one entry of the menu; inside it the three pages sit in their own small bar. */
var MN_PAGE = "income";
function tabMoney(){
  fill = null;
  var pages = [["income", ["الإيرادات", "Income"]], ["expense", ["المصروفات", "Expenses"]], ["summary", ["الملخص الشهري", "Month overview"]]];
  var bar = h("div", {class:"a-tabs a-subtabs", role:"tablist", "aria-label":uiT(["المحاسبة", "Accounting"])});
  var holder = h("div", {});
  function show(){
    bar.innerHTML = "";
    pages.forEach(function(p){
      bar.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(MN_PAGE === p[0]), text:uiT(p[1]), onclick:function(){ MN_PAGE = p[0]; show(); }}));
    });
    holder.innerHTML = "";
    holder.appendChild(MN_PAGE === "expense" ? tabExpense() : MN_PAGE === "summary" ? tabSummary() : tabIncome());
  }
  show();
  return h("section", {}, [h("h2", {class:"a-pagetitle", text:uiT(["المحاسبة", "Accounting"])}), bar, holder]);
}
