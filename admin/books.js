/* The accounting: three pages only. Income (الإيرادات), expenses (المصروفات) and the month overview (الملخص الشهري).
   Every amount is shown in US dollars and Syrian pounds side by side. The two columns are added each on its own, never into one number.
   Loaded after invoices.js (uses its number helper) and before admin.js. Nothing is deleted: a wrong entry is cancelled with a reason. */

var BK_STATE = {status:null};
var BK_SOURCE = {from_fees: ["من الرسوم (النظام القديم)", "From fees (old system)"], from_salary: ["من الرواتب (النظام القديم)", "From salaries (old system)"], historical: ["نقل تاريخي", "Historical"]};

function bkCat(row){ return typeof ADMIN_LANG !== "undefined" && ADMIN_LANG === "en" ? (row.category_de || row.category) : (row.category_ar || row.category); }
function bkMonth(delta, value){
  var parts = value.split("-"), d = new Date(Number(parts[0]), Number(parts[1]) - 1 + delta, 1);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}
function bkLoadStatus(){
  return request("/api/admin/books/status").then(function(s){ BK_STATE.status = s; return s; });
}
function bkBanner(st){
  var items = [];
  if(!st.live) items.push(h("p", {class:"a-msg err", role:"status", text:cbText(["دفتر الصندوق الجديد غير مفعّل بعد: الصفحات للعرض فقط حتى تتم الترقية (نسخة احتياطية أولاً ثم موافقة المدير).", "The new cash book is not switched on yet: these pages are read-only until the upgrade (backup first, then the owner's approval)."])}));
  if(!st.rate) items.push(h("p", {class:"a-msg err", role:"status", text:cbText(["لا يوجد سعر صرف. تحدّد الإدارة السعر في «الملخص الشهري» قبل تسجيل أي حركة.", "There is no exchange rate. The management sets it in “Month overview” before any entry can be made."])}));
  return items;
}
function bkTwoCells(row, cls){
  return [h("td", {class:"num " + (cls || ""), dir:"ltr", text:row.usd === null ? "—" : invNum(row.usd)}), h("td", {class:"num " + (cls || ""), dir:"ltr", text:row.syp === null ? "—" : invNum(row.syp)})];
}

/* ---- the entry form (new and change) ------------------------------------------------------------------------------ */
function bkForm(kind, st, row, done){
  var editing = !!row;
  var day = h("input", {type:"date", max:st.today, value:row ? row.day : st.today});
  var desc = h("input", {type:"text", maxlength:"500", value:row ? row.description : "", placeholder:kind === "income" ? cbText(["سبب الإيراد", "Reason of the income"]) : cbText(["سبب المصروف", "Reason of the expense"])});
  var cat = accSelect(st.categories[kind].map(function(c){ return [c.key, cbText([c.ar, c.de])]; }), row ? row.category : st.categories[kind][0].key);
  var amount = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:row ? row.paid_amount : ""});
  var cur = accSelect([["USD", "USD"], ["SYP", "SYP"]], row ? row.paid_currency : "USD");
  var who = h("input", {type:"text", maxlength:"120", list:kind === "income" ? "acc-payers" : "acc-persons", value:row ? row.counterparty : ""});
  var link = h("select", {});
  link.appendChild(new Option("—", ""));
  var linkLabel = kind === "income" ? cbText(["الطفل (اختياري)", "Child (optional)"]) : cbText(["الموظف (للرواتب)", "Staff member (for salaries)"]);
  var receipt = h("input", {type:"text", maxlength:"60", value:row ? row.receipt_no : ""});
  var note = h("input", {type:"text", maxlength:"500", value:row ? row.note : ""});
  var reason = h("input", {type:"text", maxlength:"300", placeholder:cbText(["سبب التعديل (إلزامي)", "Reason for the change (required)"])});
  var refresh = h("input", {type:"checkbox"});
  var preview = h("p", {class:"hint"});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var rate = st.rate ? Number(st.rate.syp_per_usd) : null;
  function show(){
    var n = Number(amount.value);
    if(!rate || !n){ preview.textContent = ""; return; }
    var other = cur.value === "USD" ? Math.round(n * rate).toLocaleString("en-US") + " SYP" : (n / rate).toFixed(2) + " USD";
    preview.textContent = cbText(["القيمة بالعملة الأخرى (تقريبية، يحسبها الخادم بسعر يوم الحركة): ", "Value in the other currency (approximate, the server calculates it with the rate of the day): "]) + other;
  }
  [amount, cur].forEach(function(el){ el.addEventListener("input", show); el.addEventListener("change", show); });
  show();
  var source = kind === "income" ? "/api/admin/accounting/children" : "/api/admin/accounting/employees";
  request(source).then(function(list){
    list.forEach(function(p){ link.appendChild(new Option(p.name, p.id)); });
    if(row && (row.child_id || row.employee_id)) link.value = row.child_id || row.employee_id;
  }).catch(function(){});
  function body(){
    var b = {booked_on:day.value, description:desc.value.trim(), category:cat.value, amount:amount.value, currency:cur.value, counterparty:who.value.trim(), receipt_no:receipt.value.trim(), note:note.value.trim()};
    if(kind === "income") b.child_id = link.value || null; else b.employee_id = cat.value === "salaries" && link.value ? link.value : null;
    return b;
  }
  var save = h("button", {type:"button", class:"a-btn sun", text:editing ? cbText(["حفظ التعديل", "Save change"]) : cbText(["إضافة", "Add"]), onclick:function(){
    var b = body(), url = "/api/admin/books/entries" + (editing ? "/" + row.id : ""), method = editing ? "PATCH" : "POST";
    if(editing){ b.reason = reason.value.trim(); b.expected_version = row.version; b.refresh_rate = refresh.checked; if(kind === "income") b.child_id = link.value || null; }
    request(url, {method:method, body:JSON.stringify(b)}).then(function(){ accToast(editing ? cbText(["حُفظ التعديل.", "Saved."]) : cbText(["أُضيفت الحركة.", "Entry added."]), "ok"); done(); })
      .catch(function(e){ setMsg(msg, errText(e), "err"); });
  }});
  var cancel = editing ? h("button", {type:"button", class:"a-btn ghost", text:cbText(["إلغاء", "Close"]), onclick:done}) : "";
  var enabled = st.live && !!st.rate;
  if(!enabled) save.disabled = true;
  return h("div", {class:"a-card"}, [h("h3", {text:editing ? cbText(["تعديل الحركة", "Change the entry"]) : (kind === "income" ? cbText(["إضافة إيراد", "Add income"]) : cbText(["إضافة مصروف", "Add expense"]))}),
    h("div", {class:"a-row"}, [accField(cbText(["التاريخ", "Date"]), day), accField(cbText(["الوصف", "Description"]), desc), accField(cbText(["الفئة", "Category"]), cat)]),
    h("div", {class:"a-row"}, [accField(cbText(["المبلغ", "Amount"]), amount), accField(cbText(["عملة الدفع الفعلية", "Currency really used"]), cur),
      accField(kind === "income" ? cbText(["الدافع", "Payer"]) : cbText(["المستلم", "Recipient"]), who), accField(linkLabel, link)]),
    h("div", {class:"a-row"}, [accField(cbText(["رقم الإيصال", "Receipt no."]), receipt), accField(cbText(["ملاحظة", "Note"]), note)]),
    editing ? h("div", {class:"a-row"}, [accField(cbText(["السبب", "Reason"]), reason), h("label", {class:"a-field"}, [refresh, h("span", {text:" " + cbText(["احسب السعر من جديد (سعر يوم الحركة)", "Take the rate again (rate of the booking day)"])})])]) : "",
    preview, h("div", {class:"a-row"}, [save, cancel]), msg]);
}

/* ---- an income or an expense page --------------------------------------------------------------------------------- */
function bkEntries(kind){
  fill = null;
  var holder = h("div", {});
  var now = new Date();
  var month = h("input", {type:"month", value:now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0")});
  var from = h("input", {type:"date"}), to = h("input", {type:"date"}), cat = h("select", {});
  var tableBox = h("div", {}), formBox = h("div", {}), st = null;

  function exportCard(){
    if(!st || (st.role !== "manager" && st.role !== "admin") || kind !== "expense") return "";
    var scope = accSelect([["all", cbText(["كل الموظفين", "All staff"])], ["active", cbText(["الفعّالون فقط", "Active only"])]], "all");
    function go(fmt){ downloadFile("/api/admin/accounting/employees/export." + fmt + "?scope=" + scope.value, "staff-" + scope.value + "." + fmt).catch(function(e){ accToast(errText(e), "err"); }); }
    return h("div", {class:"a-card a-hintcard"}, [h("h4", {text:cbText(["تصدير قائمة الموظفين (للإدارة)", "Export the staff list (management)"])}),
      h("div", {class:"a-row"}, [accField(cbText(["النطاق", "Scope"]), scope), h("button", {type:"button", class:"a-btn ghost", text:"XLSX", onclick:function(){ go("xlsx"); }}), h("button", {type:"button", class:"a-btn ghost", text:"CSV", onclick:function(){ go("csv"); }})]),
      h("p", {class:"hint", text:cbText(["الموظفون يُدارون في بوابة الإدارة، وليس هنا.", "Staff are managed in the management portal, not here."])})]);
  }
  function showForm(row){
    formBox.innerHTML = "";
    if(st.can_write === false) return;
    formBox.appendChild(bkForm(kind, st, row || null, function(){ showForm(null); load(); }));
  }
  function load(){
    var q = ["kind=" + kind];
    if(from.value || to.value){ if(from.value) q.push("date_from=" + from.value); if(to.value) q.push("date_to=" + to.value); } else q.push("month=" + month.value);
    if(cat.value) q.push("category=" + cat.value);
    tableBox.innerHTML = "";
    request("/api/admin/books/entries?" + q.join("&")).then(function(data){
      var rows = data.rows.map(function(r){
        var tags = [];
        ["from_fees", "from_salary", "historical"].forEach(function(k){ if(r[k]) tags.push(cbBadge(cbText(BK_SOURCE[k]), "review")); });
        var who = [r.counterparty, r.child, r.employee].filter(Boolean).join(" · ");
        var actions = [];
        if(r.editable) actions.push(h("button", {type:"button", class:"a-btn ghost", text:cbText(["تعديل", "Change"]), onclick:function(){ showForm(r); formBox.scrollIntoView({behavior:"smooth"}); }}));
        if(r.voidable) actions.push(h("button", {type:"button", class:"a-btn ghost", text:cbText(["إلغاء", "Cancel"]), onclick:function(){ bkVoid(r, load); }}));
        if(r.voided) actions.push(cbBadge(cbText(["ملغاة: ", "Cancelled: "]) + r.void_reason, "review"));
        return h("tr", {class:r.voided ? "voided" : ""}, [h("td", {dir:"ltr", text:r.day}),
          h("td", {dir:"auto"}, [h("span", {text:r.description}), who ? h("small", {class:"hint", text:" — " + who}) : "", r.note ? h("small", {class:"hint", text:" (" + r.note + ")"}) : ""].concat(tags)),
          h("td", {text:bkCat(r)})].concat(bkTwoCells(r), [h("td", {dir:"ltr", text:invNum(r.paid_amount) + " " + r.paid_currency}), h("td", {}, actions)]));
      });
      tableBox.appendChild(cbTable([cbText(["التاريخ", "Date"]), cbText(["الوصف", "Description"]), cbText(["الفئة", "Category"]), "USD", "SYP", cbText(["المدفوع فعلياً", "Really paid"]), ""], rows, cbText(["لا توجد حركات", "No entries"])));
      tableBox.appendChild(h("p", {class:"hint", text:cbText(["المجموع: ", "Total: "]) + "USD " + invNum(data.total.usd) + "  ·  SYP " + invNum(data.total.syp) + "  ·  " + data.count + " " + cbText(["حركة", "entries"]) +
        (data.missing_rate ? " · " + data.missing_rate + " " + cbText(["حركة بلا سعر صرف خارج المجموع", "without a rate, not in the total"]) : "")}));
      tableBox.appendChild(h("p", {class:"hint", text:cbText(["الأعمدة تُجمع كل واحد على حدة. المبلغ الفعلي بعملة الدفع محفوظ دائماً.", "The columns are added each on its own. The amount really paid is always kept."])}));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  [month, from, to, cat].forEach(function(el){ el.addEventListener("change", load); });
  bkLoadStatus().then(function(status){
    st = status;
    cat.appendChild(new Option(cbText(["كل الفئات", "All categories"]), ""));
    status.categories[kind].forEach(function(c){ cat.appendChild(new Option(cbText([c.ar, c.de]), c.key)); });
    bkBanner(status).forEach(function(n){ holder.insertBefore(n, holder.firstChild); });
    holder.appendChild(h("div", {class:"a-card"}, [h("h3", {text:kind === "income" ? cbText(["الإيرادات", "Income"]) : cbText(["المصروفات", "Expenses"])}),
      h("div", {class:"a-row"}, [accField(cbText(["الشهر", "Month"]), month), accField(cbText(["من تاريخ", "From"]), from), accField(cbText(["إلى تاريخ", "To"]), to), accField(cbText(["الفئة", "Category"]), cat)]), tableBox]));
    holder.appendChild(formBox);
    var ex = exportCard();
    if(ex) holder.appendChild(ex);
    showForm(null);
    load();
  }).catch(function(e){ accToast(errText(e), "err"); });
  return h("section", {}, [holder]);
}
function bkVoid(row, reload){
  var reason = window.prompt(cbText(["سبب الإلغاء (5 أحرف على الأقل):", "Reason for cancelling (at least 5 characters):"]));
  if(reason === null) return;
  request("/api/admin/books/entries/" + row.id + "/void", {method:"POST", body:JSON.stringify({reason:reason.trim()})})
    .then(function(){ accToast(cbText(["أُلغيت الحركة وبقي سجلها ظاهراً.", "Cancelled; the record stays visible."]), "ok"); reload(); }).catch(function(e){ accToast(errText(e), "err"); });
}
function tabIncome(){ return bkEntries("income"); }
function tabExpense(){ return bkEntries("expense"); }

/* ---- the month overview ------------------------------------------------------------------------------------------- */
function tabSummary(){
  fill = null;
  var holder = h("div", {}), now = new Date();
  var month = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0");
  function draw(){
    holder.innerHTML = "";
    Promise.all([bkLoadStatus(), request("/api/admin/books/summary?month=" + month)]).then(function(res){
      var st = res[0], d = res[1];
      bkBanner(st).forEach(function(n){ holder.appendChild(n); });
      var picker = h("input", {type:"month", value:month}); picker.addEventListener("change", function(){ if(picker.value){ month = picker.value; draw(); } });
      holder.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["الملخص الشهري", "Month overview"])}),
        h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"◀", "aria-label":cbText(["الشهر السابق", "Previous month"]), onclick:function(){ month = bkMonth(-1, month); draw(); }}), accField(cbText(["الشهر", "Month"]), picker),
          h("button", {type:"button", class:"a-btn ghost", text:"▶", "aria-label":cbText(["الشهر التالي", "Next month"]), onclick:function(){ month = bkMonth(1, month); draw(); }})]),
        summaryTable(d),
        h("p", {class:"hint", text:cbText(["الأعمدة تُجمع كل واحد على حدة ولا تُدمج في رقم واحد. ", "The columns are added each on its own and never merged into one number. "]) + (d.missing_rate ? d.missing_rate + " " + cbText(["حركة بلا سعر صرف خارج الحساب.", "entries without a rate are not counted."]) : "")}),
        realCash(d), h("p", {class:"hint", text:cbText(["عدد الحركات: ", "Entries: "]) + d.counts.income + " " + cbText(["إيراد", "income"]) + " · " + d.counts.expense + " " + cbText(["مصروف", "expense"])})]));
      holder.appendChild(h("div", {class:"a-card"}, [h("h4", {text:cbText(["الإيرادات حسب الفئة", "Income by category"])}), catTable(d.income_by_category), h("h4", {text:cbText(["المصروفات حسب الفئة", "Expenses by category"])}), catTable(d.expense_by_category)]));
      holder.appendChild(rateCard(st, draw));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  function pct(c){ return c.percent === null ? "—" : (Number(c.percent) > 0 ? "+" : "") + c.percent + " %"; }
  function summaryTable(d){
    function line(label, key, cls){
      return h("tr", {class:cls || ""}, [h("th", {text:label}), h("td", {class:"num", dir:"ltr", text:invNum(d[key].usd)}), h("td", {class:"num", dir:"ltr", text:invNum(d[key].syp)}),
        h("td", {class:"num", dir:"ltr", text:(Number(d.change[key].usd.difference) > 0 ? "+" : "") + invNum(d.change[key].usd.difference) + " (" + pct(d.change[key].usd) + ")"}),
        h("td", {class:"num", dir:"ltr", text:(Number(d.change[key].syp.difference) > 0 ? "+" : "") + invNum(d.change[key].syp.difference) + " (" + pct(d.change[key].syp) + ")"})]);
    }
    return h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [
      h("thead", {}, [h("tr", {}, [h("th", {text:""}), h("th", {text:"USD"}), h("th", {text:"SYP"}), h("th", {text:"USD " + cbText(["مقابل ", "vs "]) + d.previous_month}), h("th", {text:"SYP " + cbText(["مقابل ", "vs "]) + d.previous_month})])]),
      h("tbody", {}, [line(cbText(["إجمالي الإيرادات", "Total income"]), "income"), line(cbText(["إجمالي المصروفات", "Total expenses"]), "expense"), line(cbText(["الفائض / العجز الشهري", "Monthly surplus / deficit"]), "surplus", "total")])])]);
  }
  function realCash(d){
    return h("p", {class:"hint", text:cbText(["المدفوع فعلياً — إيرادات: ", "Really paid — income: "]) + "USD " + invNum(d.real_cash.USD.income) + " / SYP " + invNum(d.real_cash.SYP.income) +
      cbText(["، مصروفات: ", ", expenses: "]) + "USD " + invNum(d.real_cash.USD.expense) + " / SYP " + invNum(d.real_cash.SYP.expense)});
  }
  function catTable(rows){
    return cbTable([cbText(["الفئة", "Category"]), "USD", "SYP", cbText(["العدد", "Entries"])], rows.map(function(r){
      return h("tr", {}, [h("td", {text:bkCat(r)}), h("td", {class:"num", dir:"ltr", text:invNum(r.usd)}), h("td", {class:"num", dir:"ltr", text:invNum(r.syp)}), h("td", {class:"num", text:String(r.count)})]);
    }), cbText(["لا توجد حركات", "No entries"]));
  }
  draw();
  return h("section", {}, [holder]);
}

/* the exchange rate: a strip on the overview (set by the management, only looked at by the others) */
function rateCard(st, again){
  var box = h("div", {class:"a-card"}, [h("h4", {text:cbText(["سعر الصرف", "Exchange rate"])}),
    h("p", {text:st.rate ? "1 USD = " + invNum(st.rate.syp_per_usd) + " SYP (" + st.rate.date + ")" : cbText(["غير مُدخل", "not set"])}),
    h("p", {class:"hint", text:cbText(["يُحفظ سعر يوم الحركة مع كل حركة، ولا يغيّره أي سعر لاحق.", "Every entry keeps the rate of its day; no later rate changes it."])})]);
  var history = h("div", {});
  request("/api/admin/accounting/rates").then(function(s){
    history.appendChild(h("details", {}, [h("summary", {text:cbText(["سجل الأسعار", "Rate history"])}), cbTable([cbText(["من تاريخ", "From"]), cbText(["السعر", "Rate"]), cbText(["بواسطة", "By"]), cbText(["السبب", "Reason"])],
      s.rates.slice(0, 12).map(function(r){ return h("tr", {}, [h("td", {dir:"ltr", text:r.date}), h("td", {class:"num", dir:"ltr", text:invNum(r.rate)}), h("td", {text:r.by || (r.source === "auto" ? cbText(["تلقائي", "automatic"]) : "—")}), h("td", {dir:"auto", text:r.reason || ""})]); }), cbText(["لا أسعار بعد", "No rates yet"]))]));
  }).catch(function(){});
  box.appendChild(history);
  if(st.can_set_rate){
    var day = h("input", {type:"date", value:st.today}), rate = h("input", {type:"number", min:"0", step:"0.000001", inputMode:"decimal", placeholder:"12000"}), why = h("input", {type:"text", maxlength:"300"});
    var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
    box.appendChild(h("div", {class:"a-row"}, [accField(cbText(["من تاريخ", "From"]), day), accField(cbText(["الليرة لكل دولار", "Pounds per dollar"]), rate), accField(cbText(["السبب (عند تغيير سعر محفوظ)", "Reason (when changing a saved rate)"]), why),
      h("button", {type:"button", class:"a-btn sun", text:cbText(["حفظ السعر", "Save rate"]), onclick:function(){
        request("/api/admin/accounting/rates", {method:"PUT", body:JSON.stringify({effective_date:day.value, syp_per_usd:rate.value, reason:why.value.trim()})})
          .then(function(){ accToast(cbText(["حُفظ السعر. الحركات القديمة لم تتغير.", "Rate saved. Old entries did not change."]), "ok"); again(); }).catch(function(e){ setMsg(msg, errText(e), "err"); });
      }})]));
    box.appendChild(msg);
  } else {
    box.appendChild(h("p", {class:"hint", text:cbText(["تحدّد الإدارة سعر الصرف.", "The management sets the exchange rate."])}));
  }
  return box;
}
