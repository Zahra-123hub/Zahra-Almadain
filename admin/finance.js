/* The cash book (دفتر الصندوق): overview, book and activity log. Loaded before admin.js; uses its helpers (h, request, setMsg, errText, money, accSelect, accField, accToast, accWhen).
   USD and SYP are always shown apart. The cash balance counts real money only; historical adjustments are marked and shown beside it. */

var CB_CURRENCIES = ["SYP", "USD"];
var CB_CATEGORIES = null;
var CB_SOURCE = {
  fee_payment: ["دفعة رسوم", "Fee payment"], salary_payment: ["صرف راتب", "Salary payout"], booking: ["حركة يدوية", "Manual booking"],
  legacy: ["تجميع تاريخي من الجداول القديمة", "Historical collective booking (old sheets)"],
  legacy_adjustment: ["تسوية تاريخية (ليست دفعاً فعلياً)", "Historical adjustment (not a real payment)"]
};
var CB_BASIS = {
  estimated_fee_month: ["تاريخ تقديري: شهر الرسم", "Estimated date: fee month"], legacy_month_end: ["تجميع: نهاية الشهر", "Collective: end of month"],
  legacy_week_mid: ["تجميع: منتصف الأسبوع", "Collective: middle of week"], derived_payment_date: ["مشتق من تاريخ الصرف", "Derived from the payment date"]
};
var CB_MODE_TEXT = {
  legacy: ["دفتر الصندوق الجديد غير مفعّل بعد. تعمل المحاسبة بالجداول القديمة.", "The new cash book is not switched on yet. Accounting still works with the old sheets."],
  shadow: ["وضع التجربة: دفتر الصندوق يحسب بجانب الجداول القديمة (للمعاينة فقط). الجداول القديمة هي المرجع حالياً.", "Trial mode: the cash book runs beside the old sheets (preview only). The old sheets are still the truth."],
  live: ["دفتر الصندوق هو المرجع. الجداول القديمة للقراءة فقط.", "The cash book is the truth. The old sheets are read-only."]
};

function cbText(pair){ return typeof ADMIN_LANG !== "undefined" && ADMIN_LANG === "en" ? pair[1] : pair[0]; }
function cbCategoryName(key){
  if(!CB_CATEGORIES) return key;
  var all = CB_CATEGORIES.income.concat(CB_CATEGORIES.expense), hit = all.filter(function(c){ return c.key === key; })[0];
  return hit ? (typeof ADMIN_LANG !== "undefined" && ADMIN_LANG === "en" ? hit.de : hit.ar) : key;
}
function cbMoney(text){ return money(text); }
function cbBadge(text, kind){ return h("span", {class:"a-badge " + (kind || "open"), text:text}); }
function cbTable(heads, rows, empty){
  if(!rows.length) return h("div", {class:"a-empty", text:empty});
  return h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact", style:"min-width:760px"}, [
    h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)])]);
}
function cbCurrencySelect(value){ return accSelect(CB_CURRENCIES.map(function(c){ return [c, ACC_CURRENCY_NAME[c]]; }), value || "SYP"); }

/* ---- overview ------------------------------------------------------------------------------------------------- */
function cbSpark(months){
  var values = months.map(function(m){ return Number(m.closing); });
  if(values.length < 2) return h("span", {});
  var min = Math.min.apply(null, values), max = Math.max.apply(null, values), span = max - min || 1, w = 260, ht = 54;
  var points = values.map(function(v, i){ return (i * (w / (values.length - 1))).toFixed(1) + "," + (ht - 4 - ((v - min) / span) * (ht - 8)).toFixed(1); }).join(" ");
  var box = document.createElement("div");
  box.innerHTML = '<svg viewBox="0 0 ' + w + " " + ht + '" width="100%" height="' + ht + '" role="img" aria-label="' + cbText(["تطور الرصيد", "Balance over time"]) + '"><polyline points="' + points + '" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/></svg>';
  box.style.color = "var(--head, #16406F)";
  return box;
}
function cbCurrencyCard(data){
  var name = ACC_CURRENCY_NAME[data.currency];
  var kids = [h("h3", {text:name})];
  if(!data.configured) kids.push(h("p", {class:"hint", text:cbText(["لم يُدخَل رأس المال بعد؛ يُحسب الرصيد من صفر.", "No opening capital entered yet; the balance counts from zero."])}));
  kids.push(h("div", {class:"a-kpis"}, [
    h("div", {class:"a-kpi good"}, [h("small", {text:cbText(["الرصيد النقدي الفعلي", "Cash balance (real money)"])}), h("strong", {text:cbMoney(data.balance)})]),
    h("div", {class:"a-kpi"}, [h("small", {text:cbText(["إجمالي الإيرادات", "Total income"])}), h("strong", {text:cbMoney(data.total_income)})]),
    h("div", {class:"a-kpi"}, [h("small", {text:cbText(["إجمالي المصروفات", "Total expenses"])}), h("strong", {text:cbMoney(data.total_expense)})])
  ]));
  if(data.this_month){
    var m = data.this_month;
    kids.push(h("p", {text:cbText(["هذا الشهر", "This month"]) + ": " + cbText(["إيرادات", "income"]) + " " + cbMoney(m.income) + " · " + cbText(["مصروفات", "expenses"]) + " " + cbMoney(m.expense) + " · " + cbText(["الفرق", "difference"]) + " " + cbMoney(m.net)}));
  }
  if(data.historical && data.historical.adjustments){
    kids.push(h("p", {class:"hint", dir:"auto", text:cbText(["الرصيد المحاسبي التاريخي (كما في النظام القديم، مع التسويات التاريخية)", "Historical accounting balance (as in the old system, with historical adjustments)"]) + ": " + cbMoney(data.historical.balance) + " · " + cbText(["الفرق عن الرصيد النقدي", "difference to the cash balance"]) + ": " + cbMoney(data.historical.difference)}));
  }
  var flags = data.flags || {};
  var notes = [];
  if(flags.estimated_dates) notes.push(flags.estimated_dates + " " + cbText(["حركة بتاريخ تقديري أو مشتق", "movements with an estimated or derived date"]));
  if(flags.legacy) notes.push(flags.legacy + " " + cbText(["تجميع تاريخي", "historical collective bookings"]));
  if(flags.missing_receipts) notes.push(flags.missing_receipts + " " + cbText(["مصروف بلا إيصال", "expenses without a receipt"]));
  if(notes.length) kids.push(h("p", {class:"hint", text:notes.join(" · ")}));
  kids.push(cbSpark(data.months));
  var rows = data.months.slice(-12).reverse().map(function(m){
    return h("tr", {}, [h("td", {class:"name", text:m.year + "-" + String(m.month).padStart(2, "0")}), h("td", {class:"num", text:cbMoney(m.opening)}), h("td", {class:"num", text:cbMoney(m.income)}), h("td", {class:"num", text:cbMoney(m.expense)}), h("td", {class:"num", text:cbMoney(m.closing)})]);
  });
  kids.push(h("h4", {text:cbText(["التطور الشهري", "Monthly development"])}));
  kids.push(cbTable([cbText(["الشهر", "Month"]), cbText(["أول الشهر", "Opening"]), cbText(["إيرادات", "Income"]), cbText(["مصروفات", "Expenses"]), cbText(["آخر الشهر", "Closing"])], rows, cbText(["لا توجد بيانات", "No data"])));
  kids.push(h("h4", {text:cbText(["آخر الحركات", "Latest movements"])}));
  kids.push(cbTable([cbText(["التاريخ", "Date"]), cbText(["البيان", "Description"]), cbText(["التصنيف", "Category"]), cbText(["المبلغ", "Amount"]), cbText(["المصدر", "Source"])], data.recent.map(cbMovementRow.bind(null, false)), cbText(["لا توجد حركات", "No movements"])));
  return h("div", {class:"a-card"}, kids);
}
function cbOverview(){
  var body = h("div", {}), msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  Promise.all([request("/api/admin/accounting/finance/status"), request("/api/admin/accounting/finance/overview"), CB_CATEGORIES ? Promise.resolve(CB_CATEGORIES) : request("/api/admin/accounting/finance/categories")]).then(function(all){
    CB_CATEGORIES = all[2];
    body.appendChild(h("div", {class:"a-card"}, [h("strong", {text:cbText(CB_MODE_TEXT[all[0].mode] || CB_MODE_TEXT.legacy)}),
      h("p", {class:"hint", text:cbText(["التوقيت المعتمد للحسابات: دمشق", "The books go by Damascus time"]) + " · " + all[0].today})]));
    if(all[0].mode === "legacy") return;
    CB_CURRENCIES.forEach(function(c){ body.appendChild(cbCurrencyCard(all[1].currencies[c])); });
  }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  return h("section", {}, [msg, body]);
}

/* ---- book ----------------------------------------------------------------------------------------------------- */
function cbMovementRow(actions, m){
  var tags = [];
  if(m.voided) tags.push(cbBadge(cbText(["ملغاة", "Cancelled"]), "open"));
  if(m.source === "legacy" || m.source === "legacy_adjustment") tags.push(cbBadge(cbText(CB_SOURCE[m.source]), m.source === "legacy_adjustment" ? "partial" : "open"));
  if(CB_BASIS[m.date_basis]) tags.push(cbBadge(cbText(CB_BASIS[m.date_basis]), "partial"));
  if(!m.counts_in_cash) tags.push(cbBadge(cbText(["لا تؤثر على النقد", "Not in cash"]), "partial"));
  if(m.needs_receipt) tags.push(cbBadge(cbText(["بلا إيصال", "No receipt"]), "review"));
  var style = m.voided ? "text-decoration:line-through;opacity:.6" : "";
  var amount = (m.kind === "income" ? "+" : "−") + cbMoney(m.amount);
  var what = [m.description || "", m.counterparty ? "(" + m.counterparty + ")" : "", m.child ? m.child : "", m.employee ? m.employee : ""].filter(Boolean).join(" ");
  var cells = [
    h("td", {dir:"ltr", style:style, text:m.day}),
    h("td", {style:style}, [h("span", {dir:"auto", text:what || cbText(CB_SOURCE[m.source] || ["", ""])}), h("div", {}, tags)]),
    h("td", {style:style, text:cbCategoryName(m.category)}),
    h("td", {class:"num", style:style + ";color:" + (m.kind === "income" ? "#1E7A45" : "#B3402F"), text:amount}),
    h("td", {style:style, text:cbText(CB_SOURCE[m.source] || [m.source, m.source])})
  ];
  if(actions) cells.push(h("td", {}, actions(m)));
  return h("tr", {}, cells);
}
function cbHistory(id){
  return request("/api/admin/accounting/finance/history/" + id).then(function(rows){
    var lines = rows.map(function(r){
      var change = r.before || r.after ? " · " + JSON.stringify(r.before || {}) + " → " + JSON.stringify(r.after || {}) : "";
      return r.at_local.replace("T", " ").slice(0, 16) + " · " + r.actor + " · " + r.action + (r.reason ? " · " + r.reason : "") + change;
    });
    window.alert(lines.length ? lines.join("\n\n") : cbText(["لا يوجد سجل.", "No history."]));
  });
}
function cbBookTab(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"}), list = h("div", {}), formBox = h("div", {});
  var currency = cbCurrencySelect("SYP");
  var from = h("input", {type:"date"}), to = h("input", {type:"date"});
  var kind = accSelect([["", cbText(["الكل", "All"])], ["income", cbText(["إيرادات", "Income"])], ["expense", cbText(["مصروفات", "Expenses"])]], "");
  var source = accSelect([["", cbText(["كل المصادر", "All sources"])]].concat(Object.keys(CB_SOURCE).map(function(k){ return [k, cbText(CB_SOURCE[k])]; })), "");
  var category = accSelect([["", cbText(["كل التصنيفات", "All categories"])]], "");
  var missing = h("input", {type:"checkbox"}), estimated = h("input", {type:"checkbox"}), voided = h("input", {type:"checkbox"});
  voided.checked = true;
  var live = false;
  function check(label, box){ return h("label", {class:"a-check"}, [box, h("span", {text:label})]); }
  function actionsFor(m){
    var out = [];
    out.push(h("button", {type:"button", class:"a-btn ghost", text:cbText(["السجل", "History"]), onclick:function(){ cbHistory(m.source_id); }}));
    if(!live || m.voided) return out;
    if(m.source === "booking") out.push(h("button", {type:"button", class:"a-btn ghost", text:cbText(["إيصال", "Receipt"]), onclick:function(){ receiptDialog(m); }}));
    var voidPath = m.source === "fee_payment" ? "/finance/payments/" : m.source === "salary_payment" ? "/finance/salaries/" : m.source === "legacy_adjustment" ? null : "/bookings/";
    if(voidPath) out.push(h("button", {type:"button", class:"a-btn danger", text:cbText(["إلغاء", "Cancel"]), onclick:function(){
      var reason = window.prompt(cbText(["سبب الإلغاء (5 أحرف على الأقل). تبقى الحركة ظاهرة ومشطوبة.", "Reason for cancelling (at least 5 characters). The line stays visible, crossed out."]), "");
      if(reason === null) return;
      request("/api/admin/accounting" + voidPath + m.source_id + "/void", {method:"POST", body:JSON.stringify({reason:reason})}).then(function(){ accToast(cbText(["تم الإلغاء.", "Cancelled."]), "ok"); load(); }).catch(function(error){ accToast(errText(error), "err"); });
    }}));
    return out;
  }
  function receiptDialog(m){
    request("/api/admin/accounting/bookings/" + m.source_id + "/receipts").then(function(items){
      var file = h("input", {type:"file", accept:"application/pdf,image/jpeg,image/png,image/webp"});
      var box = h("div", {class:"a-card", style:"border:2px solid var(--sun)"}, [
        h("h4", {text:cbText(["إيصالات الحركة", "Receipts of this booking"])}),
        h("ul", {}, items.map(function(r){ return h("li", {}, [h("span", {text:r.name + (r.removed ? " — " + cbText(["مُزال: ", "removed: "]) + r.remove_reason : "")}), " ",
          h("a", {href:"#", text:cbText(["تنزيل", "Download"]), onclick:function(e){ e.preventDefault(); cbDownload("/api/admin/accounting/booking-receipts/" + r.id + "/download", r.name); }})]); })),
        file,
        h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:cbText(["رفع", "Upload"]), onclick:function(){
          if(!file.files.length) return;
          var data = new FormData(); data.append("file", file.files[0]);
          request("/api/admin/accounting/bookings/" + m.source_id + "/receipts", {method:"POST", body:data}).then(function(){ accToast(cbText(["تم رفع الإيصال.", "Receipt uploaded."]), "ok"); box.remove(); load(); }).catch(function(error){ accToast(errText(error), "err"); });
        }}), h("button", {type:"button", class:"a-btn ghost", text:cbText(["إغلاق", "Close"]), onclick:function(){ box.remove(); }})])]);
      formBox.prepend(box);
    }).catch(function(error){ accToast(errText(error), "err"); });
  }
  function load(){
    list.innerHTML = "";
    var q = ["currency=" + currency.value];
    if(from.value) q.push("date_from=" + from.value);
    if(to.value) q.push("date_to=" + to.value);
    if(kind.value) q.push("kind=" + kind.value);
    if(source.value) q.push("source=" + source.value);
    if(category.value) q.push("category=" + category.value);
    if(missing.checked) q.push("only_missing_receipt=true");
    if(estimated.checked) q.push("only_estimated=true");
    q.push("include_voided=" + (voided.checked ? "true" : "false"));
    request("/api/admin/accounting/finance/book?" + q.join("&")).then(function(data){
      list.appendChild(h("div", {class:"a-card"}, [
        h("div", {class:"a-kpis"}, [h("div", {class:"a-kpi"}, [h("small", {text:cbText(["إيرادات", "Income"])}), h("strong", {text:cbMoney(data.income)})]),
          h("div", {class:"a-kpi"}, [h("small", {text:cbText(["مصروفات", "Expenses"])}), h("strong", {text:cbMoney(data.expense)})]),
          h("div", {class:"a-kpi good"}, [h("small", {text:cbText(["الفرق", "Difference"])}), h("strong", {text:cbMoney(data.net)})])]),
        h("p", {class:"hint", text:cbText(["المجاميع تشمل الحركات النقدية الفعلية فقط، دون الملغاة ودون التسويات التاريخية.", "Totals count real cash movements only: no cancelled lines and no historical adjustments."])}),
        cbTable([cbText(["التاريخ", "Date"]), cbText(["البيان", "Description"]), cbText(["التصنيف", "Category"]), cbText(["المبلغ", "Amount"]), cbText(["المصدر", "Source"]), ""], data.rows.map(cbMovementRow.bind(null, actionsFor)), cbText(["لا توجد حركات", "No movements"]))]));
    }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  }
  function fillCategories(){
    category.innerHTML = "";
    category.appendChild(new Option(cbText(["كل التصنيفات", "All categories"]), ""));
    CB_CATEGORIES.income.concat(CB_CATEGORIES.expense).forEach(function(c){ category.appendChild(new Option(cbCategoryName(c.key), c.key)); });
  }
  function bookingForm(){
    var cur = cbCurrencySelect("SYP"), type = accSelect([["expense", cbText(["مصروف", "Expense"])], ["income", cbText(["إيراد", "Income"])]], "expense");
    var amount = h("input", {type:"text", inputmode:"decimal", placeholder:"0.00"}), day = h("input", {type:"date", value:localToday()});
    var cat = h("select", {}), desc = h("input", {type:"text", maxlength:"500"}), who = h("input", {type:"text", maxlength:"120"}), rno = h("input", {type:"text", maxlength:"60"});
    function cats(){
      cat.innerHTML = "";
      CB_CATEGORIES[type.value].filter(function(c){ return !c.system; }).forEach(function(c){ cat.appendChild(new Option(cbCategoryName(c.key), c.key)); });
    }
    type.addEventListener("change", cats); cats();
    return h("form", {class:"a-card", onsubmit:function(event){
      event.preventDefault();
      request("/api/admin/accounting/bookings", {method:"POST", body:JSON.stringify({currency:cur.value, kind:type.value, amount:amount.value.trim().replace(/[٠-٩]/g, function(d){ return String(d.charCodeAt(0) - 1632); }), booked_on:day.value, category:cat.value, description:desc.value, counterparty:who.value, receipt_no:rno.value})})
        .then(function(){ accToast(cbText(["تم تسجيل الحركة.", "Booking saved."]), "ok"); amount.value = desc.value = who.value = rno.value = ""; load(); })
        .catch(function(error){ accToast(errText(error), "err"); });
    }}, [h("h3", {text:cbText(["حركة جديدة", "New booking"])}),
      h("div", {class:"a-row"}, [accField(cbText(["النوع", "Type"]), type), accField(cbText(["العملة", "Currency"]), cur), accField(cbText(["المبلغ", "Amount"]), amount), accField(cbText(["التاريخ", "Date"]), day)]),
      h("div", {class:"a-row"}, [accField(cbText(["التصنيف", "Category"]), cat), accField(cbText(["البيان", "Description"]), desc), accField(cbText(["الطرف", "Counterparty"]), who), accField(cbText(["رقم الإيصال", "Receipt no."]), rno)]),
      h("p", {class:"hint", text:cbText(["الرسوم والرواتب تأتي تلقائياً من أقسامها ولا تُسجَّل هنا.", "Fees and salaries come automatically from their own areas and are not booked here."])}),
      h("button", {type:"submit", class:"a-btn sun", text:cbText(["حفظ", "Save"])})]);
  }
  Promise.all([request("/api/admin/accounting/finance/status"), CB_CATEGORIES ? Promise.resolve(CB_CATEGORIES) : request("/api/admin/accounting/finance/categories")]).then(function(all){
    CB_CATEGORIES = all[1];
    live = all[0].mode === "live";
    fillCategories();
    if(all[0].mode === "legacy"){ list.appendChild(h("div", {class:"a-card"}, [h("strong", {text:cbText(CB_MODE_TEXT.legacy)})])); return; }
    if(live) formBox.appendChild(bookingForm());
    else formBox.appendChild(h("div", {class:"a-card"}, [h("strong", {text:cbText(CB_MODE_TEXT.shadow)})]));
    load();
  }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  [currency, from, to, kind, source, category, missing, estimated, voided].forEach(function(el){ el.addEventListener("change", load); });
  return h("section", {}, [msg, formBox, h("div", {class:"a-card"}, [h("div", {class:"a-row"}, [
    accField(cbText(["العملة", "Currency"]), currency), accField(cbText(["من", "From"]), from), accField(cbText(["إلى", "To"]), to), accField(cbText(["النوع", "Type"]), kind),
    accField(cbText(["المصدر", "Source"]), source), accField(cbText(["التصنيف", "Category"]), category)]),
    h("div", {class:"a-row"}, [check(cbText(["بلا إيصال فقط", "Without receipt only"]), missing), check(cbText(["بتاريخ تقديري فقط", "Estimated date only"]), estimated), check(cbText(["إظهار الملغاة", "Show cancelled"]), voided)])]), list]);
}
function cbDownload(path, name){
  var headers = new Headers();
  if(ADMIN_TOKEN) headers.set("Authorization", "Bearer " + ADMIN_TOKEN);
  fetch(API_BASE + path, {headers:headers}).then(function(r){ if(!r.ok) throw fail(cbText(["تعذّر التنزيل.", "Download failed."])); return r.blob(); }).then(function(blob){
    var a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove();
  }).catch(function(error){ accToast(errText(error), "err"); });
}

/* ---- activity log ----------------------------------------------------------------------------------------------- */
function cbActivity(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"}), body = h("div", {});
  var q = h("input", {type:"text", placeholder:cbText(["بحث (مستخدم، إجراء، بيان)", "Search (user, action, text)"])});
  function load(){
    body.innerHTML = "";
    request("/api/admin/fees/audit?limit=200&q=" + encodeURIComponent(q.value)).then(function(rows){
      body.appendChild(cbTable([cbText(["الوقت", "Time"]), cbText(["المستخدم", "User"]), cbText(["الإجراء", "Action"]), cbText(["قبل ← بعد", "Before → after"]), cbText(["السبب", "Reason"])], rows.map(function(r){
        var change = r.before || r.after ? JSON.stringify(r.before || {}) + " → " + JSON.stringify(r.after || {}) : r.details;
        return h("tr", {}, [h("td", {dir:"ltr", text:accWhen(r.at)}), h("td", {text:r.actor}), h("td", {dir:"ltr", text:r.action}), h("td", {dir:"auto", text:change}), h("td", {dir:"auto", text:r.reason || ""})]);
      }), cbText(["لا توجد إجراءات", "No activity"])));
    }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  }
  q.addEventListener("change", load); load();
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:cbText(["الأنشطة والسجل", "Activity and log"])}),
    h("p", {class:"hint", text:cbText(["من سجّل أو غيّر أو ألغى أي حركة، ومتى، وما القيمة قبل وبعد، وما السبب. يرى المحاسب إجراءاته فقط، ويرى المدير الجميع. سجل حركة بعينها: زر «السجل» في دفتر الصندوق.", "Who booked, changed or cancelled what, when, from which value to which, and why. An accountant sees their own actions, the administrator everyone's. The history of one line: the History button in the cash book."])}),
    accField("", q), msg]), body]);
}

function tabCashbook(){
  fill = null;
  var holder = h("div", {}), sub = "overview";
  var bar = h("div", {class:"a-tabs", role:"tablist"});
  var tabs = [["overview", cbText(["نظرة مالية", "Finance overview"])], ["book", cbText(["دفتر الصندوق", "Cash book"])], ["activity", cbText(["الأنشطة والسجل", "Activity and log"])]];
  function draw(){
    bar.innerHTML = "";
    tabs.forEach(function(t){ bar.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(sub === t[0]), text:t[1], onclick:function(){ sub = t[0]; draw(); }})); });
    holder.innerHTML = "";
    holder.appendChild(sub === "book" ? cbBookTab() : sub === "activity" ? cbActivity() : cbOverview());
  }
  draw();
  return h("section", {}, [bar, holder]);
}
