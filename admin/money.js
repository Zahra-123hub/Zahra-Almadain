/* The accounting: three pages only. Income (الإيرادات), expenses (المصروفات), month overview (الملخص الشهري).
   Every amount stands in US dollars and Syrian pounds side by side. Totals are made per currency from the money really paid in it;
   the value in the other currency is shown beside an entry and never counted a second time.
   Invoices, payments, salaries, the exchange rate and the exports live inside these pages. Nothing is deleted, except entries marked as test.

   Layout of a page: the rate strip, a row of key figures, a toolbar (month, filters, "new", PDF), the form (only when asked for),
   the table. The tables become cards on a phone (labelCells) and never make the page wider than the screen. */

var MN = {meta:null};
var MN_STATUS = {open:["مفتوحة", "Open", "due"], partial:["مدفوعة جزئياً", "Partly paid", "review"], paid:["مدفوعة بالكامل", "Paid", "paid"], void:["ملغاة", "Cancelled", "neutral"]};
var MN_ACTIONS = {
  "income.create":["سُجّل", "recorded"], "income.update":["عُدّل", "changed"], "income.void":["أُلغي", "cancelled"], "income.reverse":["صُحّح بقيد عكسي", "reversed"], "income.mark_test":["تغيّرت علامة التجريب", "test mark changed"], "expense.mark_test":["تغيّرت علامة التجريب", "test mark changed"],
  "expense.create":["سُجّل", "recorded"], "expense.update":["عُدّل", "changed"], "expense.void":["أُلغي", "cancelled"], "expense.reverse":["صُحّح بقيد عكسي", "reversed"],
  "salary.auto":["سُجّل الراتب تلقائياً", "salary booked automatically"],
  "invoice.create":["أُنشئت", "created"], "invoice.update":["عُدّلت", "changed"], "invoice.void":["أُلغيت", "cancelled"]
};

function mnMeta(){ return request("/api/admin/money/meta").then(function(m){ MN.meta = m; return m; }); }
function mnMonthNow(){ var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"); }
function mnShift(value, delta){
  var p = value.split("-"), d = new Date(Number(p[0]), Number(p[1]) - 1 + delta, 1);
  return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0");
}
function mnMonthName(value){ var p = String(value).split("-"); return MONTHS_AR[Number(p[1]) - 1] + " " + p[0]; }
function mnCells(row, cls){
  return [h("td", {class:"num " + (cls || ""), dir:"ltr", text:uiNum(row.usd)}), h("td", {class:"num " + (cls || ""), dir:"ltr", text:uiNum(row.syp)})];
}
function mnTestBadge(row){ return row.is_test ? uiBadge(uiT(["تجريبي", "Test"]), "review") : ""; }
function mnState(row){
  var test = mnTestBadge(row), state = mnStateOnly(row);
  return test ? h("span", {}, [test, " ", state]) : state;
}
/* "this is only a trial": the entry is marked and can be deleted for good later (management: "delete test data" on the overview) */
function mnTestBox(){
  var box = h("input", {type:"checkbox"});
  return {node:h("label", {class:"a-check"}, [box, uiT(["إدخال تجريبي (يمكن حذفه لاحقاً نهائياً)", "Test entry (can be deleted for good later)"])]), value:function(){ return box.checked; }};
}
function mnStateOnly(row){
  if(row.voided) return uiBadge(uiT(["ملغاة: ", "Cancelled: "]) + row.void_reason, "neutral");
  if(row.is_reversal) return uiBadge(uiT(["قيد عكسي", "Reversal"]), "review");
  if(row.reversed) return uiBadge(uiT(["صُحّحت بقيد عكسي", "Reversed"]), "review");
  return "";
}
function mnMsg(){ return h("div", {class:"a-msg", role:"status", "aria-live":"polite"}); }
function mnErr(box){ return function(e){ setMsg(box, errText(e), "err"); }; }
function mnAsk(text){ var r = window.prompt(text); return r === null ? null : r.trim(); }
function mnBtn(text, kind, onclick, title){ return h("button", {type:"button", class:"a-btn " + (kind || "ghost"), text:text, title:title || "", onclick:onclick}); }
function mnTile(label, value, sub, kind){
  return h("div", {class:"mn-tile" + (kind ? " " + kind : "")}, [h("small", {text:label}), h("strong", {dir:"ltr", text:value}), sub ? h("span", {class:"mn-tile-sub", dir:"auto", text:sub}) : ""]);
}
/* profit or loss of one currency, said in words: "ربح" / "خسارة" / "لا ربح ولا خسارة", the amount without a sign */
function mnProfitTile(code, value, income, expense, worth){
  var n = Number(value), word = n > 0 ? ["ربح", "Profit"] : n < 0 ? ["خسارة", "Loss"] : ["لا ربح ولا خسارة", "No profit, no loss"];
  var cur = code === "USD" ? [" بالدولار", " in dollars"] : [" بالليرة", " in pounds"];
  var own = uiNum(String(value).replace("-", "")), val = uiNum(String(worth).replace("-", ""));
  var tile = mnTile(uiT(word) + uiT(cur), code === "SYP" ? "SYP " + own + "   ·   USD " + val : "SYP " + val + "   ·   USD " + own,
    uiT(["إيرادات ", "income "]) + uiNum(income) + uiT([" − مصروفات ", " − expenses "]) + uiNum(expense), n < 0 ? "bad" : n > 0 ? "good" : "");
  var label = tile.querySelector("small");
  label.className = "mn-verdict"; // the word "profit" / "loss" as a filled pill
  label.textContent = (n > 0 ? "▲ " : n < 0 ? "▼ " : "") + uiT(word);
  tile.insertBefore(h("small", {text:uiT(cur).trim()}), tile.children[1]);
  return tile;
}

/* the card of a form: a title, a close button, the fields in a grid that wraps on small screens */
function mnFormCard(title, fields, footer, onClose){
  return h("div", {class:"a-card mn-form"}, [
    h("div", {class:"mn-head"}, [h("h3", {text:title}), onClose ? mnBtn("✕", "ghost mn-mini", onClose, uiT(["إغلاق", "Close"])) : ""]),
    h("div", {class:"mn-grid"}, fields)].concat(footer));
}

/* the rate strip: one line on every page; the management may correct the rate here (no own page) */
function mnRateBar(meta, again){
  var r = meta.rate;
  var value = r ? uiNum(r.syp_per_usd) + uiT([" ليرة للدولار", " pounds per dollar"]) : uiT(["لا يوجد سعر صرف بعد", "No exchange rate yet"]);
  var how = !r ? uiT(["يُجلب تلقائياً مرة في اليوم؛ الإنترنت غير متاح الآن", "fetched once a day; the internet cannot be reached now"])
    : (r.source === "auto" ? uiT(["تلقائي", "automatic"]) : uiT(["من الإدارة", "by the management"])) + " · " + uiT(["منذ ", "since "]) + r.valid_from + (r.stale ? " · " + uiT(["لم يُحدَّث اليوم", "not updated today"]) : "");
  var strip = h("div", {class:"mn-strip" + (r && !r.stale ? "" : " warn")}, [h("span", {class:"mn-strip-label", text:uiT(["سعر الصرف", "Exchange rate"])}), h("strong", {dir:"auto", text:value}), h("span", {class:"hint", text:how})]);
  if(!meta.rights.manage) return strip;
  var day = h("input", {type:"date", value:meta.today}), rate = h("input", {type:"number", min:"0", step:"1", inputMode:"decimal", placeholder:"12000"});
  var msg = mnMsg();
  var form = h("div", {class:"mn-strip-form", hidden:"hidden"}, [h("div", {class:"mn-grid"}, [uiField(uiT(["ساري من", "Valid from"]), day), uiField(uiT(["ليرة لكل دولار", "Pounds per dollar"]), rate),
    mnBtn(uiT(["حفظ السعر", "Save rate"]), "sun", function(){
      request("/api/admin/money/rates", {method:"POST", body:JSON.stringify({valid_from:day.value, syp_per_usd:rate.value})})
        .then(function(){ uiToast(uiT(["حُفظ السعر. الحركات الموجودة لا تتغير.", "Rate saved. Existing entries do not change."]), "ok"); again(); }).catch(mnErr(msg));
    })]), msg]);
  strip.appendChild(mnBtn(uiT(["تصحيح", "Correct"]), "ghost mn-mini", function(){ form.hidden = !form.hidden; }));
  return h("div", {}, [strip, form]);
}

/* the toolbar of a list: month (or a date span), category, search; the "new" button and the PDF on the other side */
function mnToolbar(meta, categories, onChange, kind, newLabel, onNew){
  var month = uiMonthPicker(mnMonthNow(), function(){ onChange(); }), from = h("input", {type:"date"}), to = h("input", {type:"date"});
  var cat = uiSelect([["", uiT(["كل الفئات", "All categories"])]].concat(categories), ""), q = h("input", {type:"search", maxlength:"60", placeholder:uiT(["بحث في الوصف والأسماء", "Search descriptions and names"])});
  [from, to, cat].forEach(function(el){ el.addEventListener("change", onChange); });
  q.addEventListener("change", onChange);
  var span = h("details", {class:"mn-span"}, [h("summary", {text:uiT(["فترة مخصّصة", "Custom dates"])}), h("div", {class:"mn-grid"}, [uiField(uiT(["من", "From"]), from), uiField(uiT(["إلى", "To"]), to)])]);
  var actions = [mnBtn(newLabel, "sun", onNew)];
  if(meta.rights.export){
    actions.push(mnBtn(uiT(["PDF", "PDF"]), "ghost", function(){
      var m = month.value;
      downloadFile("/api/admin/money/export/" + kind + ".pdf?month=" + m, kind + "-" + m + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
    }, uiT(["تنزيل الشهر PDF موقّعاً", "Download the month as a signed PDF"])));
  }
  return {
    node: h("div", {class:"mn-toolbar"}, [h("div", {class:"mn-grid mn-filters"}, [uiField(uiT(["الشهر", "Month"]), month), uiField(uiT(["الفئة", "Category"]), cat), uiField(uiT(["بحث", "Search"]), q)]),
      h("div", {class:"mn-toolbar-end"}, actions), span]),
    query: function(key){
      var p = [];
      if(from.value || to.value){ if(from.value) p.push("date_from=" + from.value); if(to.value) p.push("date_to=" + to.value); } else p.push("month=" + month.value);
      if(cat.value) p.push(key + "=" + encodeURIComponent(cat.value));
      if(q.value.trim()) p.push("q=" + encodeURIComponent(q.value.trim()));
      return p.join("&");
    },
    month: function(){ return month.value; },
    spanUsed: function(){ return !!(from.value || to.value); }
  };
}
/* the key figures above a list: the value of everything in dollars and in pounds, what was really paid, the number */
function mnTotals(d, kindWord){
  return h("div", {class:"mn-tiles"}, [
    mnTile(uiT(["المجموع بالدولار", "Total in dollars"]), "USD " + uiNum(d.totals.value.USD), uiT(["منها مدفوع بالدولار: ", "really paid in dollars: "]) + uiNum(d.totals.USD)),
    mnTile(uiT(["المجموع بالليرة", "Total in pounds"]), "SYP " + uiNum(d.totals.value.SYP), uiT(["منها مدفوع بالليرة: ", "really paid in pounds: "]) + uiNum(d.totals.SYP)),
    mnTile(kindWord, String(d.count), uiT(["حركة محسوبة", "entries counted"]))
  ]);
}
/* amount + currency + rate (the rate of the day is proposed; only the management may type another one) */
function mnMoneyFields(meta, row){
  var amount = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:row ? String(row.amount).replace("-", "") : ""});
  var cur = uiSelect([["USD", uiT(["دولار (USD)", "Dollar (USD)"])], ["SYP", uiT(["ليرة (SYP)", "Pound (SYP)"])]], row ? row.currency : "USD");
  var rate = h("input", {type:"number", min:"0", step:"any", inputMode:"decimal", value:row ? row.rate : (meta.rate ? meta.rate.syp_per_usd : "")});
  if(!meta.rights.manage){ rate.readOnly = true; rate.title = uiT(["سعر اليوم (تحدّده الإدارة)", "Today's rate (set by the management)"]); }
  var other = h("p", {class:"mn-other"});
  function show(){
    var n = Number(amount.value), r = Number(rate.value);
    other.textContent = n && r ? "≈ " + (cur.value === "USD" ? uiNum(String(Math.round(n * r))) + " SYP" : uiNum((n / r).toFixed(2)) + " USD") : "";
  }
  [amount, cur, rate].forEach(function(el){ el.addEventListener("input", show); el.addEventListener("change", show); });
  show();
  return {
    nodes: [uiField(uiT(["المبلغ", "Amount"]), amount), uiField(uiT(["عملة الدفع", "Paid in"]), cur), uiField(uiT(["سعر الصرف", "Rate"]), rate)],
    preview: other,
    values: function(){ var v = {amount:amount.value, currency:cur.value}; if(meta.rights.manage && rate.value) v.rate = rate.value; return v; },
    dayChanged: function(day){
      if(row) return;
      request("/api/admin/money/rates?day=" + day).then(function(r){ if(r.for_day) { rate.value = r.for_day; show(); } }).catch(function(){});
    }
  };
}
/* the history of an invoice, shown in its details */
function mnInvoiceLog(id, box){
  if(box.firstChild){ box.innerHTML = ""; return; }
  box.appendChild(h("span", {class:"hint", text:uiT(["جارٍ التحميل…", "Loading…"])}));
  request("/api/admin/money/history/" + id).then(function(rows){
    box.innerHTML = "";
    box.appendChild(h("ol", {class:"mn-timeline"}, rows.map(function(r){
      return h("li", {}, [h("span", {dir:"ltr", class:"hint", text:String(r.at || "").replace("T", " ").slice(0, 16)}), h("strong", {text:" " + uiT(MN_ACTIONS[r.action] || [r.action, r.action]) + " "}),
        h("span", {text:uiT(["بواسطة ", "by "]) + r.actor}), r.reason ? h("span", {class:"hint", text:" — " + r.reason}) : ""]);
    })));
  }).catch(function(e){ box.textContent = errText(e); });
}

/* the history of one entry, shown in the table under its row */
function mnHistoryRow(id, columns, after){
  var next = after.nextSibling;
  if(next && next.classList && next.classList.contains("mn-history")){ next.remove(); return; }
  var cell = h("td", {colspan:String(columns)}, [h("span", {class:"hint", text:uiT(["جارٍ التحميل…", "Loading…"])})]);
  var tr = h("tr", {class:"mn-history"}, [cell]);
  after.parentNode.insertBefore(tr, after.nextSibling);
  request("/api/admin/money/history/" + id).then(function(rows){
    cell.innerHTML = "";
    if(!rows.length){ cell.appendChild(h("span", {class:"hint", text:uiT(["لا سجل", "No history"])})); return; }
    cell.appendChild(h("ol", {class:"mn-timeline"}, rows.map(function(r){
      var who = r.actor === "auto" ? uiT(["النظام", "the system"]) : r.actor;
      return h("li", {}, [h("span", {dir:"ltr", class:"hint", text:String(r.at || "").replace("T", " ").slice(0, 16)}), h("strong", {text:" " + uiT(MN_ACTIONS[r.action] || [r.action, r.action]) + " "}),
        h("span", {text:uiT(["بواسطة ", "by "]) + who}), r.reason ? h("span", {class:"hint", text:" — " + r.reason}) : ""]);
    })));
  }).catch(function(e){ cell.textContent = errText(e); });
}
function mnCancel(kind, row, done){
  var reason = mnAsk(row.month_closed ? uiT(["الشهر مغلق: يُسجَّل قيد عكسي اليوم. السبب (5 أحرف على الأقل):", "The month is closed: a reversal is booked today. Reason (at least 5 characters):"]) : uiT(["سبب الإلغاء (5 أحرف على الأقل):", "Reason for cancelling (at least 5 characters):"]));
  if(reason === null) return;
  request("/api/admin/money/" + kind + "/" + row.id + "/void", {method:"POST", body:JSON.stringify({reason:reason})})
    .then(function(){ uiToast(uiT(["تم. السجل يبقى ظاهراً.", "Done. The record stays visible."]), "ok"); done(); }).catch(function(e){ uiToast(errText(e), "err"); });
}
/* the buttons of one row: change, cancel (or reverse in a closed month), history */
function mnRowActions(meta, kind, r, columns, onEdit, done){
  var box = h("div", {class:"mn-actions"});
  if(meta.rights.correct && !r.voided && !r.is_reversal && !r.reversed){
    if(!r.month_closed) box.appendChild(mnBtn(uiT(["تعديل", "Edit"]), "ghost mn-mini", function(){ onEdit(r); }));
    box.appendChild(mnBtn(r.month_closed ? uiT(["قيد عكسي", "Reverse"]) : uiT(["إلغاء", "Cancel"]), "ghost mn-mini", function(){ mnCancel(kind, r, done); }));
  }
  box.appendChild(mnBtn(uiT(["السجل", "Log"]), "ghost mn-mini", function(){ mnHistoryRow(r.id, columns, box.closest("tr")); }));
  if(meta.rights.manage && !r.is_reversal){
    box.appendChild(mnBtn(r.is_test ? uiT(["إزالة علامة التجريب", "Remove test mark"]) : uiT(["تعليم كتجريبي", "Mark as test"]), "ghost mn-mini", function(){
      request("/api/admin/money/" + kind + "/" + r.id + "/test", {method:"POST", body:JSON.stringify({test:!r.is_test})})
        .then(function(){ uiToast(r.is_test ? uiT(["أُزيلت علامة التجريب.", "Test mark removed."]) : uiT(["عُلّمت كتجريبية. تُحذف مع حذف البيانات التجريبية.", "Marked as test. It goes with deleting the test data."]), "ok"); done(); })
        .catch(function(e){ uiToast(errText(e), "err"); });
    }));
  }
  return box;
}
function mnPaidCell(r){
  return h("td", {class:"mn-paid", dir:"ltr"}, [h("span", {text:uiNum(r.amount) + " " + r.currency}), h("small", {text:uiT(["بسعر ", "at "]) + uiNum(r.rate)})]);
}

/* ======================================================================================== page 1: income (with invoices) */
function tabIncome(){
  fill = null;
  var page = h("section", {class:"mn-page"});
  mnMeta().then(function(meta){
    var cats = meta.income_categories.map(function(c){ return [c.id, c.name + (c.is_active ? "" : " (" + uiT(["معطّلة", "off"]) + ")")]; });
    var tiles = h("div", {}), listBox = h("div", {}), formBox = h("div", {});
    var bar = mnToolbar(meta, cats, load, "income", uiT(["+ إيراد جديد", "+ New income"]), function(){ showForm(null); });
    var children = [];
    function load(){
      listBox.innerHTML = ""; tiles.innerHTML = "";
      request("/api/admin/money/income?" + bar.query("category_id")).then(function(d){
        tiles.appendChild(mnTotals(d, uiT(["عدد الإيرادات", "Income entries"])));
        var rows = d.rows.map(function(r){
          var who = [r.payer_name, r.child, r.description.indexOf(r.invoice_number) === -1 ? r.invoice_number : ""].filter(Boolean).join(" · ");
          return h("tr", {class:r.voided ? "voided" : ""}, [h("td", {class:"mn-date", dir:"ltr", text:r.booked_on}),
            h("td", {dir:"auto"}, [h("div", {class:"mn-desc", text:r.description}), who ? h("small", {class:"hint", text:who}) : "", r.note ? h("small", {class:"hint", text:" · " + r.note}) : "", mnState(r)]),
            h("td", {text:r.category})].concat(mnCells(r), [mnPaidCell(r), h("td", {}, [mnRowActions(meta, "income", r, 7, showForm, refresh)])]));
        });
        listBox.appendChild(uiTable([uiT(["التاريخ", "Date"]), uiT(["الوصف", "Description"]), uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["المدفوع فعلاً", "Really paid"]), ""], rows,
          uiT(["لا توجد إيرادات في هذه الفترة", "No income in this period"])));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function refresh(){ load(); loadInvoices(); }
    function showForm(row){
      formBox.innerHTML = "";
      var day = h("input", {type:"date", max:meta.today, value:row ? row.booked_on : meta.today});
      var desc = h("input", {type:"text", maxlength:"300", value:row ? row.description : "", placeholder:uiT(["مثال: رسوم شهر تشرين الثاني", "e.g. November fee"])});
      var cat = uiSelect(meta.income_categories.filter(function(c){ return c.is_active || (row && c.id === row.category_id); }).map(function(c){ return [c.id, c.name]; }), row ? row.category_id : undefined);
      var child = uiSelect([["", "—"]].concat(children.map(function(c){ return [c.id, c.name]; })), row ? row.child_id : "");
      var payer = h("input", {type:"text", maxlength:"120", value:row ? row.payer_name : ""}), note = h("input", {type:"text", maxlength:"500", value:row ? row.note : ""});
      var m = mnMoneyFields(meta, row), msg = mnMsg(), tst = mnTestBox();
      day.addEventListener("change", function(){ m.dayChanged(day.value); });
      var save = mnBtn(row ? uiT(["حفظ التعديل", "Save change"]) : uiT(["تسجيل الإيراد", "Record income"]), "sun", function(){
        var body = Object.assign({booked_on:day.value, description:desc.value.trim(), category_id:cat.value, child_id:child.value || null, payer_name:payer.value.trim(), note:note.value.trim()}, m.values());
        if(!row) body.test = tst.value();
        if(row) body.expected_version = row.version;
        request("/api/admin/money/income" + (row ? "/" + row.id : ""), {method:row ? "PATCH" : "POST", body:JSON.stringify(body)})
          .then(function(){ uiToast(uiT(["تم الحفظ.", "Saved."]), "ok"); formBox.innerHTML = ""; load(); }).catch(mnErr(msg));
      });
      if(!meta.rate) save.disabled = true;
      formBox.appendChild(mnFormCard(row ? uiT(["تعديل الإيراد", "Change the income"]) : uiT(["إيراد جديد", "New income"]),
        [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["السبب", "Reason"]), desc), uiField(uiT(["الفئة", "Category"]), cat),
         uiField(uiT(["الطفل (اختياري)", "Child (optional)"]), child), uiField(uiT(["الدافع (اختياري)", "Payer (optional)"]), payer)].concat(m.nodes, [uiField(uiT(["ملاحظة", "Note"]), note)]),
        [m.preview, row ? "" : tst.node, h("div", {class:"a-row"}, [save]), msg], function(){ formBox.innerHTML = ""; }));
      formBox.scrollIntoView({behavior:"smooth", block:"start"});
    }
    /* invoices: a claim, not an income; a payment is an income tied to the invoice */
    var invStatus = uiSelect([["unpaid", uiT(["غير مسددة", "Unpaid"])], ["", uiT(["كل الفواتير", "All invoices"])], ["paid", uiT(MN_STATUS.paid)], ["void", uiT(MN_STATUS.void)]], "unpaid");
    invStatus.addEventListener("change", loadInvoices);
    var invList = h("div", {}), invDetail = h("div", {}), invForm = h("div", {});
    function loadInvoices(){
      invList.innerHTML = "";
      request("/api/admin/money/invoices?status=" + invStatus.value).then(function(d){
        invList.appendChild(uiTable(["#", uiT(["التاريخ", "Date"]), uiT(["الطفل / الدافع", "Child / payer"]), uiT(["المجموع USD", "Total USD"]), uiT(["المجموع SYP", "Total SYP"]),
          uiT(["المتبقي USD", "Open USD"]), uiT(["المتبقي SYP", "Open SYP"]), uiT(["الحالة", "Status"])], d.rows.map(function(r){
          var st = MN_STATUS[r.status];
          var tr = h("tr", {class:"clickable", tabindex:"0", onclick:function(){ openInvoice(r.id); }}, [h("td", {dir:"ltr", text:r.number}), h("td", {class:"mn-date", dir:"ltr", text:r.issued_on}),
            h("td", {text:r.child || r.payer_name})].concat(mnCells(r.total), mnCells(r.open, r.status === "paid" ? "" : "due"), [h("td", {}, [mnTestBadge(r), r.is_test ? " " : "", uiBadge(uiT(st), st[2])])]));
          tr.addEventListener("keydown", function(e){ if(e.key === "Enter") openInvoice(r.id); });
          return tr;
        }), uiT(["لا توجد فواتير", "No invoices"])));
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
        var pays = uiTable([uiT(["التاريخ", "Date"]), uiT(["المدفوع فعلاً", "Really paid"]), uiT(["قيمتها للفاتورة", "Credited"]), ""], v.payments.map(function(p){
          return h("tr", {class:p.voided ? "voided" : ""}, [h("td", {class:"mn-date", dir:"ltr", text:p.booked_on}), mnPaidCell(p),
            h("td", {dir:"ltr", text:uiNum(p.credited) + " " + v.currency}), h("td", {}, [p.voided ? uiBadge(uiT(["ملغاة: ", "Cancelled: "]) + p.void_reason, "neutral") : ""])]);
        }), uiT(["لا دفعات بعد", "No payments yet"]));
        var kids = [h("div", {class:"mn-head"}, [h("h3", {text:uiT(["فاتورة ", "Invoice "]) + v.number + " — " + (v.child || v.payer_name)}), mnBtn("✕", "ghost mn-mini", function(){ invDetail.innerHTML = ""; }, uiT(["إغلاق", "Close"]))]),
          h("div", {class:"mn-meta-line"}, [uiBadge(uiT(st), st[2]), h("span", {class:"hint", text:v.issued_on + " · " + uiT(["عملة الفاتورة ", "currency "]) + v.currency + " · " + uiT(["السعر ", "rate "]) + uiNum(v.rate) + (v.description ? " · " + v.description : "")}),
            mnBtn(uiT(["PDF موقّع", "Signed PDF"]), "ghost mn-mini", function(){ downloadFile("/api/admin/money/invoices/" + v.id + ".pdf", v.number + ".pdf").catch(function(e){ uiToast(errText(e), "err"); }); })]),
          table, h("h4", {text:uiT(["الدفعات", "Payments"])}), pays];
        if(v.status === "open" || v.status === "partial"){
          var day = h("input", {type:"date", max:meta.today, value:meta.today}), payer = h("input", {type:"text", maxlength:"120", value:v.payer_name});
          var m = mnMoneyFields(meta, null), msg = mnMsg();
          day.addEventListener("change", function(){ m.dayChanged(day.value); });
          kids.push(h("div", {class:"mn-subcard"}, [h("h4", {text:uiT(["تسجيل دفعة", "Record a payment"])}), h("p", {class:"hint", text:uiT(["تُسجَّل الدفعة إيراداً مرتبطاً بالفاتورة، ويمكن أن تكون جزئية أو بعملة أخرى.", "The payment becomes an income tied to the invoice; it may be partial or in the other currency."])}),
            h("div", {class:"mn-grid"}, [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["الدافع", "Payer"]), payer)].concat(m.nodes)), m.preview,
            h("div", {class:"a-row"}, [mnBtn(uiT(["تسجيل الدفعة", "Record payment"]), "sun", function(){
              request("/api/admin/money/invoices/" + v.id + "/payments", {method:"POST", body:JSON.stringify(Object.assign({booked_on:day.value, payer_name:payer.value.trim()}, m.values()))})
                .then(function(){ uiToast(uiT(["سُجّلت الدفعة.", "Payment recorded."]), "ok"); openInvoice(v.id); loadInvoices(); load(); }).catch(mnErr(msg));
            })]), msg]));
        }
        var logBox = h("div", {});
        if(meta.rights.correct && !v.voided){
          kids.push(h("div", {class:"a-row"}, [mnBtn(uiT(["تعديل الفاتورة", "Edit the invoice"]), "ghost", function(){ showInvoiceForm(v); }),
            mnBtn(uiT(["السجل", "Log"]), "ghost", function(){ mnInvoiceLog(v.id, logBox); })]));
        }
        if(meta.rights.manage){
          kids.push(h("div", {class:"a-row"}, [mnBtn(v.is_test ? uiT(["إزالة علامة التجريب", "Remove test mark"]) : uiT(["تعليم كتجريبية", "Mark as test"]), "ghost", function(){
            request("/api/admin/money/invoices/" + v.id + "/test", {method:"POST", body:JSON.stringify({test:!v.is_test})}).then(function(){ openInvoice(v.id); loadInvoices(); load(); }).catch(function(e){ uiToast(errText(e), "err"); });
          })]));
        }
        kids.push(logBox);
        if(meta.rights.correct && v.status === "open" && !v.voided){
          kids.push(h("div", {class:"a-row"}, [mnBtn(uiT(["إلغاء الفاتورة", "Cancel the invoice"]), "ghost", function(){
            var reason = mnAsk(uiT(["سبب إلغاء الفاتورة (5 أحرف على الأقل):", "Reason (at least 5 characters):"]));
            if(reason === null) return;
            request("/api/admin/money/invoices/" + v.id + "/void", {method:"POST", body:JSON.stringify({reason:reason})}).then(function(){ openInvoice(v.id); loadInvoices(); }).catch(function(e){ uiToast(errText(e), "err"); });
          })]));
        }
        invDetail.appendChild(h("div", {class:"a-card mn-detail"}, kids));
        invDetail.scrollIntoView({behavior:"smooth", block:"start"});
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function showInvoiceForm(old){
      invForm.innerHTML = "";
      var items = h("div", {class:"mn-items"});
      var day = h("input", {type:"date", max:meta.today, value:old ? old.issued_on : meta.today});
      var child = uiSelect([["", "—"]].concat(children.map(function(c){ return [c.id, c.name]; })), old ? old.child_id : "");
      var payer = h("input", {type:"text", maxlength:"120", value:old ? old.payer_name : ""}), desc = h("input", {type:"text", maxlength:"300", value:old ? old.description : ""});
      var cur = uiSelect([["USD", uiT(["دولار (USD)", "Dollar (USD)"])], ["SYP", uiT(["ليرة (SYP)", "Pound (SYP)"])]], old ? old.currency : "USD");
      var msg = mnMsg(), tst = mnTestBox();
      function item(text, amount){
        var d = h("input", {type:"text", maxlength:"200", value:text || "", placeholder:uiT(["مثال: رسوم شهرية", "e.g. monthly fee"])}), a = h("input", {type:"number", min:"0.01", step:"0.01", inputMode:"decimal", value:amount || ""});
        var row = h("div", {class:"mn-item"}, [uiField(uiT(["البند", "Item"]), d), uiField(uiT(["المبلغ", "Amount"]), a), mnBtn("✕", "ghost mn-mini", function(){ if(items.children.length > 1) row.remove(); }, uiT(["إزالة البند", "Remove item"]))]);
        row._d = d; row._a = a; items.appendChild(row);
      }
      if(old) old.items.forEach(function(i){ item(i.description, old.currency === "USD" ? i.usd : i.syp); }); else item();
      invForm.appendChild(mnFormCard(old ? uiT(["تعديل الفاتورة ", "Edit invoice "]) + old.number : uiT(["فاتورة جديدة لولي أمر", "New invoice to a parent"]),
        [uiField(uiT(["التاريخ", "Date"]), day), uiField(uiT(["الطفل", "Child"]), child), uiField(uiT(["أو الجهة الدافعة", "or the payer"]), payer), uiField(uiT(["عملة الفاتورة", "Invoice currency"]), cur), uiField(uiT(["الوصف", "Description"]), desc)],
        [h("h4", {text:uiT(["البنود", "Items"])}), items,
         h("div", {class:"a-row"}, [mnBtn(uiT(["+ بند", "+ Item"]), "ghost", function(){ item(); }), mnBtn(old ? uiT(["حفظ التعديل", "Save change"]) : uiT(["إنشاء الفاتورة", "Create invoice"]), "sun", function(){
           var list = Array.prototype.map.call(items.children, function(r){ return {description:r._d.value.trim(), amount:r._a.value}; }).filter(function(i){ return i.amount !== ""; });
           request("/api/admin/money/invoices" + (old ? "/" + old.id : ""), {method:old ? "PATCH" : "POST", body:JSON.stringify({issued_on:day.value, child_id:child.value || null, payer_name:payer.value.trim(), description:desc.value.trim(), currency:cur.value, items:list, test:old ? undefined : tst.value()})})
             .then(function(v){ uiToast(old ? uiT(["حُفظت الفاتورة.", "Invoice saved."]) : uiT(["أُنشئت الفاتورة ", "Invoice made: "]) + v.number, "ok"); invForm.innerHTML = ""; loadInvoices(); load(); openInvoice(v.id); }).catch(mnErr(msg));
         })]),
         old ? "" : tst.node,
         h("p", {class:"hint", text:uiT(["الفاتورة مطالبة وليست إيراداً. يدخل المال في الإيرادات عند تسجيل الدفعة فقط.", "An invoice is a claim, not income. Money counts as income only when a payment is recorded."])}), msg],
        function(){ invForm.innerHTML = ""; }));
      invForm.scrollIntoView({behavior:"smooth", block:"start"});
    }
    function categoryCard(){
      if(!meta.rights.manage) return null;
      var name = h("input", {type:"text", maxlength:"80"}), msg = mnMsg();
      var rows = meta.income_categories.map(function(c){
        return h("tr", {}, [h("td", {text:c.name}), h("td", {}, [c.is_active ? uiBadge(uiT(["مفعّلة", "on"]), "paid") : uiBadge(uiT(["معطّلة", "off"]), "neutral")]),
          h("td", {}, [mnBtn(uiT(["إعادة تسمية", "Rename"]), "ghost mn-mini", function(){
              var name = mnAsk(uiT(["الاسم الجديد للفئة:", "New name of the category:"]));
              if(!name) return;
              request("/api/admin/money/categories/" + c.id, {method:"PATCH", body:JSON.stringify({name:name})}).then(function(){ draw(); }).catch(mnErr(msg));
            }), c.key === "tuition" ? h("span", {class:"hint", text:uiT([" أساسية", " built in"])}) :
            mnBtn(c.is_active ? uiT(["تعطيل", "Switch off"]) : uiT(["تفعيل", "Switch on"]), "ghost mn-mini", function(){
              request("/api/admin/money/categories/" + c.id, {method:"PATCH", body:JSON.stringify({is_active:!c.is_active})}).then(function(){ draw(); }).catch(mnErr(msg));
            })])]);
      });
      return h("details", {class:"a-card mn-fold"}, [h("summary", {text:uiT(["فئات الإيرادات", "Income categories"])}),
        uiTable([uiT(["الفئة", "Category"]), uiT(["الحالة", "Status"]), uiT(["إجراء", "Action"])], rows, ""),
        h("div", {class:"mn-grid"}, [uiField(uiT(["فئة جديدة", "New category"]), name), mnBtn(uiT(["إضافة", "Add"]), "ghost", function(){
          request("/api/admin/money/categories", {method:"POST", body:JSON.stringify({name:name.value.trim()})}).then(function(){ draw(); }).catch(mnErr(msg));
        })]), msg]);
    }
    request("/api/admin/people/children").then(function(list){ children = list; }).catch(function(){});
    page.appendChild(mnRateBar(meta, function(){ draw(); }));
    page.appendChild(tiles);
    page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الإيرادات", "Income"])}), bar.node, listBox]));
    page.appendChild(formBox);
    page.appendChild(h("div", {class:"a-card"}, [h("div", {class:"mn-head"}, [h("h3", {text:uiT(["مستحقات الروضة على الأهالي", "What parents owe us"])}), mnBtn(uiT(["+ فاتورة جديدة للأهالي", "+ New invoice to parents"]), "sun", function(){ showInvoiceForm(null); })]),
      h("p", {class:"hint", text:uiT(["فواتير نُصدرها للأهالي، وتصبح إيراداً عند الدفع فقط.", "Invoices we send to parents. Income only once paid."])}),
      h("div", {class:"mn-grid mn-filters"}, [uiField(uiT(["الحالة", "Status"]), invStatus)]), invList]));
    page.appendChild(invForm);
    page.appendChild(invDetail);
    var cc = categoryCard(); if(cc) page.appendChild(cc);
    load(); loadInvoices();
  }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  return page;
}

/* ======================================================================================== page 2: expenses (with salaries) */
function tabExpense(){
  fill = null;
  var page = h("section", {class:"mn-page"});
  mnMeta().then(function(meta){
    var cats = meta.expense_categories.map(function(c){ return [c.key, uiT([c.ar, c.en])]; });
    var tiles = h("div", {}), listBox = h("div", {}), formBox = h("div", {}), salaryBox = h("div", {});
    var bar = mnToolbar(meta, cats, function(){ load(); loadSalaries(); }, "expenses", uiT(["+ مصروف جديد", "+ New expense"]), function(){ showForm(null); });
    var staff = [];
    function load(){
      listBox.innerHTML = ""; tiles.innerHTML = "";
      request("/api/admin/money/expenses?" + bar.query("category")).then(function(d){
        tiles.appendChild(mnTotals(d, uiT(["عدد المصروفات", "Expense entries"])));
        var rows = d.rows.map(function(r){
          var extra = [r.recipient, r.employee && r.employee !== r.recipient ? r.employee : "", r.salary_month ? uiT(["راتب ", "salary "]) + mnMonthName(r.salary_month) : ""].filter(Boolean).join(" · ");
          return h("tr", {class:r.voided ? "voided" : ""}, [h("td", {class:"mn-date", dir:"ltr", text:r.booked_on}),
            h("td", {dir:"auto"}, [h("div", {class:"mn-desc", text:r.description}), extra ? h("small", {class:"hint", text:extra}) : "", r.note ? h("small", {class:"hint", text:" · " + r.note}) : "", mnState(r)]),
            h("td", {text:uiT([r.category_ar, r.category_en])})].concat(mnCells(r), [mnPaidCell(r), h("td", {}, [mnRowActions(meta, "expenses", r, 7, showForm, refresh)])]));
        });
        listBox.appendChild(uiTable([uiT(["التاريخ", "Date"]), uiT(["الوصف", "Description"]), uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["المدفوع فعلاً", "Really paid"]), ""], rows,
          uiT(["لا توجد مصروفات في هذه الفترة", "No expenses in this period"])));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function refresh(){ load(); loadSalaries(); }
    function showForm(row, salaryFor){
      formBox.innerHTML = "";
      var day = h("input", {type:"date", max:meta.today, value:row ? row.booked_on : meta.today});
      var desc = h("input", {type:"text", maxlength:"300", value:row ? row.description : salaryFor ? uiT(["راتب ", "Salary "]) + salaryFor.name : "", placeholder:uiT(["مثال: خبز وحليب", "e.g. bread and milk"])});
      var cat = uiSelect(cats, row ? row.category : salaryFor ? "salaries" : "food");
      var person = uiSelect([["", "—"]].concat(staff.map(function(p){ return [p.id, p.name]; })), row ? row.employee_id : salaryFor ? salaryFor.employee_id : "");
      var month = uiMonthPicker(row && row.salary_month ? row.salary_month : bar.month());
      var recipient = h("input", {type:"text", maxlength:"120", value:row ? row.recipient : salaryFor ? salaryFor.name : ""}), note = h("input", {type:"text", maxlength:"500", value:row ? row.note : ""});
      var m = mnMoneyFields(meta, row || (salaryFor && salaryFor.salary ? {amount:salaryFor.salary, currency:salaryFor.salary_currency, rate:meta.rate ? meta.rate.syp_per_usd : ""} : null));
      var personField = uiField(uiT(["الموظف", "Staff member"]), person), monthField = uiField(uiT(["شهر الراتب", "Salary for month"]), month);
      function sync(){ personField.hidden = monthField.hidden = cat.value !== "salaries"; }
      cat.addEventListener("change", sync); sync();
      day.addEventListener("change", function(){ m.dayChanged(day.value); });
      var msg = mnMsg(), tst = mnTestBox();
      var save = mnBtn(row ? uiT(["حفظ التعديل", "Save change"]) : uiT(["تسجيل المصروف", "Record expense"]), "sun", function(){
        var salary = cat.value === "salaries";
        var body = Object.assign({booked_on:day.value, description:desc.value.trim(), category:cat.value, recipient:recipient.value.trim(), note:note.value.trim(),
          employee_id:salary && person.value ? person.value : null, salary_month:salary ? month.value : null}, m.values());
        if(row) body.expected_version = row.version; else body.test = tst.value();
        request("/api/admin/money/expenses" + (row ? "/" + row.id : ""), {method:row ? "PATCH" : "POST", body:JSON.stringify(body)})
          .then(function(){ uiToast(uiT(["تم الحفظ.", "Saved."]), "ok"); formBox.innerHTML = ""; refresh(); }).catch(mnErr(msg));
      });
      if(!meta.rate) save.disabled = true;
      formBox.appendChild(mnFormCard(row ? uiT(["تعديل المصروف", "Change the expense"]) : salaryFor ? uiT(["صرف راتب ", "Pay the salary of "]) + salaryFor.name : uiT(["مصروف جديد", "New expense"]),
        [uiField(uiT(["تاريخ الدفع", "Date paid"]), day), uiField(uiT(["السبب", "Reason"]), desc), uiField(uiT(["الفئة", "Category"]), cat), personField, monthField,
         uiField(uiT(["المستلم (اختياري)", "Recipient (optional)"]), recipient)].concat(m.nodes, [uiField(uiT(["ملاحظة", "Note"]), note)]),
        [m.preview, h("p", {class:"hint", text:uiT(["يُسجَّل المصروف بعد الدفع فعلاً فقط.", "Record an expense only once it was really paid."])}), row ? "" : tst.node, h("div", {class:"a-row"}, [save]), msg],
        function(){ formBox.innerHTML = ""; }));
      formBox.scrollIntoView({behavior:"smooth", block:"start"});
    }
    function loadSalaries(){
      salaryBox.innerHTML = "";
      request("/api/admin/money/salaries?month=" + bar.month()).then(function(d){
        var rows = d.rows.map(function(r){
          return h("tr", {}, [h("td", {class:"name", text:r.name + (r.is_active ? "" : " (" + uiT(["غادر", "left"]) + ")")}), h("td", {text:r.job_title || "—"}),
            h("td", {dir:"ltr", text:r.salary ? uiNum(r.salary) + " " + r.salary_currency : "—"}),
            h("td", {}, [r.paid ? uiBadge((r.automatic ? uiT(["تلقائي · ", "automatic · "]) : uiT(["صُرف · ", "paid · "])) + uiNum(r.paid_amount) + " " + r.paid_currency, "paid") : uiBadge(uiT(["لم يُصرف", "Not paid"]), "due")]),
            h("td", {}, [r.paid || !r.is_active ? "" : mnBtn(uiT(["صرف الراتب", "Pay salary"]), "ghost mn-mini", function(){ showForm(null, r); })])]);
        });
        salaryBox.appendChild(h("div", {class:"mn-head"}, [h("h3", {text:uiT(["رواتب ", "Salaries of "]) + mnMonthName(d.month)}),
          h("div", {class:"mn-meta-line"}, [uiBadge(d.paid + " " + uiT(["صُرفت", "paid"]), "paid"), uiBadge(d.unpaid + " " + uiT(["لم تُصرف", "not paid"]), d.unpaid ? "due" : "neutral")])]));
        salaryBox.appendChild(uiTable([uiT(["الموظف", "Staff member"]), uiT(["الوظيفة", "Job"]), uiT(["الراتب المعتاد", "Usual salary"]), uiT(["الحالة", "Status"]), ""], rows, uiT(["لا يوجد موظفون", "No staff"])));
        salaryBox.appendChild(h("p", {class:"hint", text:uiT(["تُسجَّل رواتب الشهر تلقائياً في أول الشهر التالي بالراتب المحفوظ. ما صُرف يدوياً أو أُلغي لا يُسجَّل مرة ثانية. الموظفون تديرهم الإدارة في بوابة الإدارة.",
          "A month's salaries are booked automatically on the 1st of the next month with the saved salary. What was paid by hand or cancelled is not booked again. Staff are managed in the management portal."])}));
      }).catch(function(e){ uiToast(errText(e), "err"); });
    }
    function staffExport(){
      if(!meta.rights.manage) return "";
      var scope = uiSelect([["all", uiT(["كل الموظفين", "All staff"])], ["active", uiT(["الفعّالون فقط", "Active only"])]], "all");
      return h("div", {class:"mn-grid mn-filters"}, [uiField(uiT(["قائمة الموظفين", "Staff list"]), scope),
        mnBtn(uiT(["تنزيل PDF", "Download PDF"]), "ghost", function(){
          downloadFile("/api/admin/people/employees/export.pdf?scope=" + scope.value, "staff-" + scope.value + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
        })]);
    }
    request("/api/admin/people/employees").then(function(list){ staff = list; }).catch(function(){});
    page.appendChild(mnRateBar(meta, function(){ draw(); }));
    page.appendChild(tiles);
    page.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["المصروفات", "Expenses"])}), bar.node, listBox]));
    page.appendChild(formBox);
    page.appendChild(h("div", {class:"a-card"}, [salaryBox, staffExport()]));
    load(); loadSalaries();
  }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  return page;
}

/* ======================================================================================== page 3: the month overview */
function tabSummary(){
  fill = null;
  var page = h("section", {class:"mn-page"}), month = mnMonthNow();
  function draw3(){
    page.innerHTML = "";
    Promise.all([mnMeta(), request("/api/admin/money/summary?month=" + month)]).then(function(res){
      var meta = res[0], d = res[1];
      var picker = uiMonthPicker(month, function(v){ month = v; draw3(); });
      function pct(c){ return c.percent === null ? "" : " (" + (Number(c.percent) > 0 ? "+" : "") + c.percent + "%)"; }
      function change(key, code){ var c = d.change[key][code]; return (Number(c.difference) > 0 ? "+" : "") + uiNum(c.difference) + pct(c); }
      function line(label, key, cls){
        return h("tr", {class:cls || ""}, [h("th", {text:label}), h("td", {class:"num", dir:"ltr", text:uiNum(d[key].usd)}), h("td", {class:"num", dir:"ltr", text:uiNum(d[key].syp)}),
          h("td", {class:"num mn-change", dir:"ltr", text:change(key, "usd")}), h("td", {class:"num mn-change", dir:"ltr", text:change(key, "syp")})]);
      }
      var main = h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [
        h("thead", {}, [h("tr", {}, [h("th", {text:""}), h("th", {text:"USD"}), h("th", {text:"SYP"}), h("th", {text:uiT(["تغيّر USD عن ", "USD vs "]) + mnMonthName(d.previous_month)}), h("th", {text:uiT(["تغيّر SYP عن ", "SYP vs "]) + mnMonthName(d.previous_month)})])]),
        h("tbody", {}, [line(uiT(["الإيرادات", "Income"]), "income"), line(uiT(["المصروفات", "Expenses"]), "expense"), line(uiT(["الربح / الخسارة", "Profit / loss"]), "surplus", "total")])])]);
      var closeBtn = "";
      if(meta.rights.manage){
        var p = month.split("-");
        closeBtn = d.closed
          ? mnBtn(uiT(["إعادة فتح الشهر", "Reopen the month"]), "ghost", function(){
              var reason = mnAsk(uiT(["سبب إعادة الفتح (5 أحرف على الأقل):", "Reason for reopening (at least 5 characters):"]));
              if(reason === null) return;
              request("/api/admin/money/closings/" + Number(p[0]) + "/" + Number(p[1]) + "/reopen", {method:"POST", body:JSON.stringify({reason:reason})}).then(draw3).catch(function(e){ uiToast(errText(e), "err"); });
            })
          : mnBtn(uiT(["إغلاق الشهر", "Close the month"]), "ghost", function(){
              if(!window.confirm(uiT(["بعد الإغلاق لا تُسجَّل ولا تُعدَّل حركات هذا الشهر. متابعة؟", "After closing nothing in this month can be added or changed. Continue?"]))) return;
              request("/api/admin/money/closings", {method:"POST", body:JSON.stringify({year:Number(p[0]), month:Number(p[1])})}).then(draw3).catch(function(e){ uiToast(errText(e), "err"); });
            });
      }
      function catTable(rows, name){
        return uiTable([uiT(["الفئة", "Category"]), "USD", "SYP", uiT(["العدد", "Entries"])], rows.map(function(r){
          return h("tr", {}, [h("td", {text:name(r)}), h("td", {class:"num", dir:"ltr", text:uiNum(r.usd)}), h("td", {class:"num", dir:"ltr", text:uiNum(r.syp)}), h("td", {class:"num", text:String(r.count)})]);
        }), uiT(["لا حركات", "No entries"]));
      }
      var pdf = meta.rights.export ? mnBtn(uiT(["تقرير الشهر PDF", "Month report PDF"]), "ghost", function(){
        downloadFile("/api/admin/money/export/summary.pdf?month=" + month, "report-" + month + ".pdf").catch(function(e){ uiToast(errText(e), "err"); });
      }) : "";
      page.appendChild(mnRateBar(meta, draw3));
      page.appendChild(h("div", {class:"a-card"}, [
        h("div", {class:"mn-monthbar"}, [mnBtn("▶", "ghost mn-mini", function(){ month = mnShift(month, -1); draw3(); }, uiT(["الشهر السابق", "Previous month"])), picker,
          mnBtn("◀", "ghost mn-mini", function(){ month = mnShift(month, 1); draw3(); }, uiT(["الشهر التالي", "Next month"])),
          uiBadge(d.closed ? uiT(["مغلق", "Closed"]) + (d.closing ? " · " + d.closing.by : "") : uiT(["مفتوح", "Open"]), d.closed ? "paid" : "neutral"),
          h("div", {class:"mn-toolbar-end"}, [closeBtn, pdf])]),
        h("div", {class:"mn-tiles"}, [
          mnProfitTile("USD", d.surplus.usd, d.income.usd, d.expense.usd, d.surplus_value.usd),
          mnProfitTile("SYP", d.surplus.syp, d.income.syp, d.expense.syp, d.surplus_value.syp),
          mnTile(uiT(["الرواتب", "Salaries"]), "SYP " + uiNum(d.salaries.syp), "USD " + uiNum(d.salaries.usd)),
          mnTile(uiT(["فواتير غير مسددة", "Unpaid invoices"]), String(d.invoices.open + d.invoices.partial), "USD " + uiNum(d.invoices.open_amount.usd) + " · SYP " + uiNum(d.invoices.open_amount.syp), d.invoices.open + d.invoices.partial ? "warn" : "")
        ]),
        main,
        h("p", {class:"hint", text:uiT(["كل عمود يجمع المال المدفوع فعلاً بعملته؛ لا يُجمع الدولار والليرة معاً. للمقارنة فقط، كل الحركات محوّلة بسعرها: ", "Each column adds the money really paid in its currency; dollars and pounds are never added. For comparison only, everything converted at its rate: "]) +
          "USD " + uiNum(d.converted.surplus.usd) + " / SYP " + uiNum(d.converted.surplus.syp) + " · " + d.income_count + uiT([" إيراد، ", " income, "]) + d.expense_count + uiT([" مصروف", " expenses"])})]));
      page.appendChild(mnBalanceCard(meta, d, draw3));
      page.appendChild(mnTestCard(meta, draw3));
      page.appendChild(h("div", {class:"mn-two"}, [
        h("div", {class:"a-card"}, [h("h3", {text:uiT(["الإيرادات حسب الفئة", "Income by category"])}), catTable(d.income_by_category, function(r){ return r.name; })]),
        h("div", {class:"a-card"}, [h("h3", {text:uiT(["المصروفات حسب الفئة", "Expenses by category"])}), catTable(d.expense_by_category, function(r){ return uiT([r.ar, r.en]); })])]));
    }).catch(function(e){ page.appendChild(h("p", {class:"a-msg err", text:errText(e)})); });
  }
  draw3();
  return page;
}

/* ======================================================================================== trial data */
/* Entries made with "test entry" ticked can be deleted for good here (management). Real entries are never touched. */
function mnTestCard(meta, again){
  var box = h("div", {class:"a-card"}), msg = mnMsg();
  request("/api/admin/money/test-data").then(function(d){
    if(!d.total) return;
    box.appendChild(h("h3", {text:uiT(["بيانات تجريبية", "Test data"])}));
    box.appendChild(h("p", {class:"hint", text:uiT(["إيرادات: ", "Income: "]) + d.income + uiT([" · مصروفات: ", " · Expenses: "]) + d.expenses + uiT([" · فواتير: ", " · Invoices: "]) + d.invoices}));
    if(meta.rights.manage){
      box.appendChild(h("div", {class:"a-row"}, [mnBtn(uiT(["حذف البيانات التجريبية نهائياً", "Delete the test data for good"]), "ghost", function(){
        if(!window.confirm(uiT(["سيُحذف نهائياً كل ما أُدخل كتجريبي (" + d.total + " حركة). الحركات الحقيقية لا تتأثر. متابعة؟", "Everything entered as a test (" + d.total + " entries) will be deleted for good. Real entries are not touched. Continue?"]))) return;
        request("/api/admin/money/test-data/purge", {method:"POST"}).then(function(){ uiToast(uiT(["حُذفت البيانات التجريبية.", "Test data deleted."]), "ok"); again(); }).catch(mnErr(msg));
      })]));
    }
    box.appendChild(msg);
    box.hidden = false;
  }).catch(function(){});
  return box;
}

/* ======================================================================================== the money the kindergarten has */
function mnBalanceCard(meta, d, again){
  var b = d.balance, known = b.start.usd !== null || b.start.syp !== null;
  var kids = [h("h3", {text:uiT(["رصيد الصندوق", "Cash of the kindergarten"])})];
  if(known){
    function line(label, pair, cls){ return h("tr", {class:cls || ""}, [h("th", {text:label}), h("td", {class:"num", dir:"ltr", text:uiNum(pair.usd)}), h("td", {class:"num", dir:"ltr", text:uiNum(pair.syp)})]); }
    kids.push(h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [
      h("thead", {}, [h("tr", {}, [h("th", {text:""}), h("th", {text:"USD"}), h("th", {text:"SYP"})])]),
      h("tbody", {}, [line(uiT(["الرصيد في أول الشهر", "Money at the start of the month"]), b.start), line(uiT(["+ الإيرادات", "+ Income"]), d.income),
        line(uiT(["− المصروفات", "− Expenses"]), d.expense), line(uiT(["= الربح / الخسارة", "= Profit / loss"]), b.profit),
        line(uiT(["الرصيد في آخر الشهر", "Money at the end of the month"]), b.end, "total")])])]));
    kids.push(h("p", {class:"hint", text:uiT(["كل عملة صندوق مستقل. الرصيد الافتتاحي من ", "Each currency is its own cash. Opening balance from "]) + ((b.opening.USD || b.opening.SYP || {}).as_of || "")}));
  } else {
    kids.push(h("p", {class:"mn-empty", text:uiT(["لم يُدخل رصيد الصندوق بعد، أو هذا الشهر قبل تاريخه. تُدخله الإدارة مرة واحدة، ثم تُحسب عليه الإيرادات والمصروفات.", "No cash balance yet, or this month is before its date. The management enters it once; income and expenses are then added to it."])}));
  }
  if(meta.rights.manage){
    var day = h("input", {type:"date", max:meta.today, value:meta.today});
    var usd = h("input", {type:"number", min:"0", step:"0.01", inputMode:"decimal", placeholder:"0"}), syp = h("input", {type:"number", min:"0", step:"1", inputMode:"decimal", placeholder:"0"});
    var note = h("input", {type:"text", maxlength:"300"}), msg = mnMsg();
    kids.push(h("details", {class:"mn-fold-inner"}, [h("summary", {text:uiT(["إدخال المال الموجود في الصندوق (للإدارة)", "Enter the money the kindergarten has (management)"])}),
      h("p", {class:"hint", text:uiT(["ما تملكه الروضة فعلاً في بداية اليوم المختار. التصحيح إدخال جديد، والقديم يبقى في السجل.", "What the kindergarten really has at the start of the chosen day. A correction is a new entry; the old one stays in the log."])}),
      h("div", {class:"mn-grid"}, [uiField(uiT(["في بداية يوم", "At the start of"]), day), uiField("USD", usd), uiField("SYP", syp), uiField(uiT(["ملاحظة", "Note"]), note),
        mnBtn(uiT(["حفظ الرصيد", "Save balance"]), "sun", function(){
          request("/api/admin/money/opening", {method:"POST", body:JSON.stringify({as_of:day.value, usd:usd.value || "0", syp:syp.value || "0", note:note.value.trim()})})
            .then(function(){ uiToast(uiT(["حُفظ رصيد الصندوق.", "Cash balance saved."]), "ok"); again(); }).catch(mnErr(msg));
        })]), msg]));
  }
  return h("div", {class:"a-card"}, kids);
}

/* ======================================================================================== the one area "المحاسبة" */
/* The accounting is one area; inside it the three pages sit in their own small bar. */
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
  return h("section", {}, [bar, holder]);
}
