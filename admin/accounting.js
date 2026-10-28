/* Buchhaltung (المحاسبة): overview, fees, payroll, monthly and weekly sheets.
   Loaded before admin.js; uses its helpers (h, request, setMsg, errText, twoStep, money, esc, MONTHS_AR). */

var ACC_CURRENCIES = ["SYP", "USD"];  // the Syrian pound is the main currency
var ACC_CURRENCY_NAME = {USD:"الدولار الأمريكي (USD)", SYP:"الليرة السورية (SYP)"};
var ACC_VIEWER = {name:"", role:""};

/* Names typed before are offered as suggestions (<datalist>), so nobody has to retype them. */
function accEnsureLists(){
  ["acc-persons", "acc-payers", "acc-staff"].forEach(function(id){
    if(!document.getElementById(id)){ var list = document.createElement("datalist"); list.id = id; document.body.appendChild(list); }
  });
}
function accFill(id, names){
  var list = document.getElementById(id);
  if(!list) return;
  list.innerHTML = "";
  (names || []).forEach(function(name){ var option = document.createElement("option"); option.value = name; list.appendChild(option); });
}
async function accLoadNames(){
  accEnsureLists();
  try{
    var names = await request("/api/admin/accounting/names");
    accFill("acc-persons", names.persons); accFill("acc-payers", names.payers); accFill("acc-staff", names.staff);
  }catch(e){ /* suggestions are optional */ }
}
function accField(label, input){ return h("label", {class:"a-field"}, [h("span", {text:label}), input]); }
function accSelect(options, value){
  var el = h("select", {});
  options.forEach(function(o){ el.appendChild(new Option(o[1], o[0])); });
  el.value = value;
  return el;
}
function accNumber(value, extra){ return h("input", Object.assign({type:"number", min:"0", step:"0.01", inputmode:"decimal", value:value === undefined || value === null ? "" : value}, extra || {})); }
function accMonths(withAll){ return (withAll ? [["", "كل الأشهر"]] : []).concat(MONTHS_AR.map(function(n, i){ return [String(i + 1), n]; })); }
function accCurrencyOptions(withAll){ return (withAll ? [["", "كل العملات"]] : []).concat([["SYP", "ليرة سورية (SYP)"], ["USD", "دولار أمريكي (USD)"]]); }

/* Printable A4 landscape RTL page: header with logo, even columns, tall rows to write in,
   highlighted totals and the two signature fields. `parts` = [{html, cols?, ...}]. */
function accPrint(title, subtitle, parts, msgEl){
  /* Black and white on purpose: no filled areas, no colours, thin lines, so a print uses very little ink. */
  var css = "@page{size:A4 landscape;margin:8mm}*{box-sizing:border-box}html{-webkit-print-color-adjust:economy;print-color-adjust:economy}" +
    "body{font-family:Almarai,'Segoe UI',Tahoma,sans-serif;color:#000;background:#fff;margin:0;font-size:12pt;line-height:1.35}" +
    "section{page-break-after:always;padding:0}section:last-child{page-break-after:auto}" +
    ".top{display:flex;align-items:center;gap:14px;border-bottom:1.5px solid #000;padding-bottom:5px;margin-bottom:6px}" +
    ".top img{width:50px;height:50px;object-fit:contain;filter:grayscale(1) contrast(1.2)}.top .t{flex:1;text-align:center}.top h1{margin:0;font-size:19pt;color:#000}.top h2{margin:2px 0 0;font-size:15pt}" +
    ".top .spacer{width:50px}.meta{display:flex;justify-content:center;gap:10px;flex-wrap:wrap;margin:0 0 6px}" +
    ".meta span{border:1px solid #000;border-radius:999px;padding:2px 14px;font-weight:700;font-size:11pt}" +
    "table{width:100%;border-collapse:collapse;table-layout:fixed}thead{display:table-header-group}tr{page-break-inside:avoid}" +
    "th,td{border:1px solid #000;padding:4px 7px;text-align:center;vertical-align:middle;overflow-wrap:break-word}td.n{white-space:nowrap}" +
    "th{font-weight:800;font-size:11pt;padding:6px 5px;border-bottom:2px solid #000}td{height:7mm;font-size:11.5pt}" +
    "td.l{text-align:right}td.l:first-child{font-weight:700}" +
    "tfoot{display:table-row-group}tfoot td{font-weight:800;border-top:2px solid #000;height:7mm;font-size:12pt;white-space:nowrap}" +
    ".due{font-weight:800;text-decoration:underline}" +
    ".sign{display:flex;gap:70px;margin-top:10px;page-break-inside:avoid}.sign>div{flex:1;text-align:center}.sign b{display:block;font-size:12pt;margin-bottom:12px}" +
    ".sign span{display:block;border-top:1px solid #000;padding-top:3px;min-height:20px;font-weight:700}.sign i{display:block;margin-top:6px;font-style:normal}" +
    "footer{margin-top:3px;font-size:8.5pt;color:#000;text-align:left}";
  var sign = "<div class='sign'><div><b>توقيع المحاسب</b><span>" + esc(ACC_VIEWER.role === "accountant" ? ACC_VIEWER.name : "") + "</span><i>التاريخ: ____ / ____ / ________</i></div>" +
    "<div><b>توقيع الإدارة</b><span></span><i>التاريخ: ____ / ____ / ________</i></div></div>";
  var today = new Date().toLocaleDateString("ar-SY");
  var logo = new URL("../images/logo.png?v=2", window.location.href).href;
  var html = "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><title>" + esc(title) + "</title>" +
    "<link href='https://fonts.googleapis.com/css2?family=Almarai:wght@400;700;800&display=swap' rel='stylesheet'><style>" + css + "</style></head><body>" +
    parts.map(function(part){
      var table = part.html;
      if(part.cols) table = table.replace("<table>", "<table><colgroup>" + part.cols.map(function(w){ return "<col style='width:" + w + "%'>"; }).join("") + "</colgroup>");
      return "<section><div class='top'><img src='" + esc(logo) + "' alt=''><div class='t'><h1>روضة زهرة المدائن</h1><h2>" + esc(title) + "</h2></div><div class='spacer'></div></div>" +
        "<div class='meta'>" + subtitle(part).split("|").map(function(chunk){ return "<span>" + chunk.replace(/&nbsp;/g, " ").trim() + "</span>"; }).join("") + "</div>" +
        table + sign + "<footer>طُبع بتاريخ " + esc(today) + "</footer></section>";
    }).join("") +
    "</body></html>";
  var w = window.open("", "_blank");
  if(!w){ if(msgEl) setMsg(msgEl, "اسمح بالنوافذ المنبثقة لتصدير PDF.", "err"); return; }
  w.document.write(html);
  w.document.close();
  function printWhenReady(){
    (w.document.fonts ? w.document.fonts.ready : Promise.resolve()).then(function(){ setTimeout(function(){ w.focus(); w.print(); }, 300); });
  }
  if(w.document.readyState === "complete") printWhenReady(); else w.addEventListener("load", printWhenReady);
}
/* Before a payroll or monthly sheet is exported, every employee with a saved salary gets this month's row automatically. */
async function accFillSavedSalaries(year, month, codes, msgEl){
  if(!month) return 0;
  var created = 0;
  for(var i = 0; i < codes.length; i++){
    var res = await request("/api/admin/accounting/salaries/generate", {method:"POST", body:JSON.stringify({year:Number(year), month:Number(month), currency:codes[i]})});
    created += res.created;
  }
  if(created && msgEl) setMsg(msgEl, "أُضيفت تلقائياً رواتب " + created + " موظف من الرواتب المحفوظة.", "ok");
  return created;
}
function accTh(list){ return "<tr>" + list.map(function(t){ return "<th>" + t + "</th>"; }).join("") + "</tr>"; }

/* ---------------------------------------------------------------- shell */
function tabAccounting(){
  var sub = ACC_SUB || "overview";
  var panel = h("div", {});
  var nav = h("div", {class:"a-subnav", role:"tablist"});
  var SUBS = [["overview","نظرة عامة"], ["fees","اشتراكات الأطفال"], ["salaries","الرواتب"], ["staff","الموظفون"], ["day","الجدول اليومي"], ["week","الجدول الأسبوعي"], ["month","الجدول الشهري"]];
  function draw(){
    nav.innerHTML = "";
    SUBS.forEach(function(entry){
      nav.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(sub === entry[0]), text:entry[1], onclick:function(){ sub = ACC_SUB = entry[0]; draw(); }}));
    });
    panel.innerHTML = "";
    panel.appendChild(sub === "fees" ? tabFees() : sub === "salaries" ? tabSalaries() : sub === "staff" ? tabEmployees() : sub === "month" ? tabSheet("month") : sub === "week" ? tabSheet("week") : sub === "day" ? tabSheet("day") : tabOverview());
  }
  request("/api/admin/fees/me").then(function(me){ ACC_VIEWER = me; }, function(){});
  accLoadNames();
  draw();
  fill = null;
  return h("section", {}, [nav, panel]);
}
var ACC_SUB = "";

/* ------------------------------------------------------------- overview */
function tabOverview(){
  var now = new Date();
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(now.getFullYear())});
  var currencySel = accSelect(accCurrencyOptions(false), "SYP");  // the Syrian pound first; switch to see the other currency
  var body = h("div", {});
  var msg = h("div", {class:"a-msg", role:"status"});
  year.addEventListener("change", load);
  currencySel.addEventListener("change", load);

  function chart(series){
    var max = Math.max.apply(null, series.map(function(s){ return Math.max(Number(s.income), Number(s.expense)); }).concat([1]));
    var W = 720, H = 220, base = H - 30, band = (W - 20) / 12, bar = Math.max(6, band / 2 - 4);
    var svg = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="الواردات والمصروفات الشهرية" style="width:100%;height:auto;direction:ltr">'];
    series.forEach(function(s, i){
      var x = 10 + i * band;
      var hi = Math.round((Number(s.income) / max) * (base - 14)), he = Math.round((Number(s.expense) / max) * (base - 14));
      svg.push('<rect x="' + (x + 2) + '" y="' + (base - hi) + '" width="' + bar + '" height="' + hi + '" rx="3" fill="#7DC243"><title>' + esc(MONTHS_AR[i]) + " – واردات: " + money(s.income) + '</title></rect>');
      svg.push('<rect x="' + (x + 4 + bar) + '" y="' + (base - he) + '" width="' + bar + '" height="' + he + '" rx="3" fill="#E0403D"><title>' + esc(MONTHS_AR[i]) + " – مصروفات: " + money(s.expense) + '</title></rect>');
      svg.push('<text x="' + (x + band / 2) + '" y="' + (H - 12) + '" font-size="11" text-anchor="middle" fill="currentColor">' + (i + 1) + '</text>');
    });
    svg.push('<line x1="6" y1="' + base + '" x2="' + (W - 6) + '" y2="' + base + '" stroke="currentColor" opacity=".35"/></svg>');
    var box = document.createElement("div");
    box.className = "a-chart";
    box.innerHTML = svg.join("");
    return box;
  }

  async function load(){
    body.innerHTML = "";
    try{
      var data = await request("/api/admin/accounting/overview?year=" + encodeURIComponent(year.value));
      var review = data.review || {fees:0, salaries:0};
      var cash = {};
      try{ cash = await request("/api/admin/accounting/cash"); }catch(e){ /* the rest of the overview still works */ }
      if(review.fees || review.salaries){
        body.appendChild(h("div", {class:"a-card a-review-note"}, [h("strong", {text:"يوجد " + review.fees + " سطر اشتراكات و" + review.salaries + " سطر رواتب يحتاج إلى مراجعة."}),
          h("p", {class:"hint", text:"الأسطر المميّزة بالأصفر مستوردة من الأوراق وفيها خانة غير واضحة. افتحها وصحّحها ثم اضغط «تمت المراجعة»."})]));
      }
      [currencySel.value].forEach(function(code){
        var info = data[code];
        if(cash[code]) body.appendChild(cashCard(code, cash[code]));
        var rows = [], tot = {required:0, paid:0, remaining:0};
        Object.keys(info.classes).forEach(function(cls){
          info.classes[cls].forEach(function(cell){
            tot.required += Number(cell.required); tot.paid += Number(cell.paid); tot.remaining += Number(cell.remaining);
            rows.push(h("tr", {}, [h("td", {text:cls}), h("td", {text:MONTHS_AR[cell.month - 1]}), h("td", {class:"num", text:money(cell.required)}), h("td", {class:"num", text:money(cell.paid)}),
              h("td", {class:"num" + (Number(cell.remaining) > 0 ? " due" : ""), text:money(cell.remaining)}), h("td", {class:"num", text:String(cell.children_open)})]));
          });
        });
        if(!rows.length) rows.push(h("tr", {}, [h("td", {colspan:"6", class:"a-empty", text:"لا توجد اشتراكات بهذه العملة في هذه السنة."})]));
        var yIncome = info.series.reduce(function(a, s){ return a + Number(s.income); }, 0);
        var yExpense = info.series.reduce(function(a, s){ return a + Number(s.expense); }, 0);
        body.appendChild(h("div", {class:"a-card"}, [
          h("h3", {text:"بـ" + ACC_CURRENCY_NAME[code]}),
          h("div", {class:"a-kpis"}, [
            kpi("المطلوب", money(tot.required)), kpi("المدفوع", money(tot.paid)), kpi("المتبقي", money(tot.remaining), tot.remaining > 0 ? "due" : ""),
            kpi("أطفال عليهم متبقي", String(info.children_open)), kpi("الواردات (الجدول الشهري)", money(yIncome)), kpi("المصروفات (الجدول الشهري)", money(yExpense))
          ]),
          h("h4", {text:"الاشتراكات حسب الصف والشهر"}),
          h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table"}, [
            h("thead", {}, [h("tr", {}, ["الصف","الشهر","المطلوب","المدفوع","المتبقي","أطفال عليهم متبقي"].map(function(t){ return h("th", {text:t}); }))]),
            h("tbody", {}, rows)])]),
          h("h4", {text:"الواردات والمصروفات لكل شهر"}),
          h("p", {class:"hint", text:"أخضر: واردات · أحمر: مصروفات (من الجدول الشهري، الأرقام 1–12 هي الأشهر)"}),
          chart(info.series)
        ]));
      });
    }catch(error){ body.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  /* How much money the kindergarten has: opening balance + all income - all expense, month by month. */
  function cashCard(code, cash){
    var amount = accNumber(cash.opening, {"aria-label":"رصيد البداية", required:"required"});
    var monthSel = accSelect(accMonths(false), String(cash.start_month));
    var yearInput = h("input", {type:"number", min:"2000", max:"2100", value:String(cash.start_year)});
    var cashMsg = h("div", {class:"a-msg", role:"status"});
    var form = h("form", {class:"a-form-grid", hidden:"hidden"}, [accField("المبلغ في الصندوق عند البداية (" + code + ")", amount), accField("بداية الحساب من شهر", monthSel), accField("السنة", yearInput),
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"حفظ رصيد البداية"})])]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      try{
        await request("/api/admin/accounting/cash", {method:"PUT", body:JSON.stringify({currency:code, opening:amount.value || "0", start_year:Number(yearInput.value), start_month:Number(monthSel.value)})});
        setMsg(cashMsg, "تم حفظ رصيد البداية.", "ok"); await load();
      }catch(error){ setMsg(cashMsg, errText(error), "err"); }
    });
    var recent = cash.months.slice(-24).reverse();
    var trail = h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [
      h("thead", {}, [h("tr", {}, ["الشهر", "رصيد أول الشهر", "الوارد", "الصادر", "رصيد آخر الشهر"].map(function(t){ return h("th", {text:t}); }))]),
      h("tbody", {}, recent.map(function(m){
        return h("tr", {}, [h("td", {class:"name", text:MONTHS_AR[m.month - 1] + " " + m.year}), h("td", {class:"num", text:money(m.opening)}), h("td", {class:"num", text:money(m.income)}),
          h("td", {class:"num", text:money(m.expense)}), h("td", {class:"num strong" + (Number(m.closing) < 0 ? " due" : ""), text:money(m.closing)})]);
      }))]))]);
    return h("div", {class:"a-card a-cash"}, [
      h("h3", {text:"رصيد الكيتا بـ" + ACC_CURRENCY_NAME[code]}),
      h("div", {class:"a-kpis"}, [kpi("الرصيد الحالي", money(cash.balance), Number(cash.balance) < 0 ? "due" : "good"), kpi("إجمالي الوارد", money(cash.income)), kpi("إجمالي الصادر", money(cash.expense)), kpi("رصيد البداية", money(cash.opening))]),
      cash.configured ? "" : h("p", {class:"a-review-note", text:"لم تحدّد رصيد البداية بعد، لذلك يبدأ الحساب من صفر عند أول شهر فيه بيانات. اضغط «تعديل رصيد البداية» وأدخل المبلغ الموجود في الصندوق عند بدء العمل بالنظام."}),
      h("p", {class:"hint", text:"الرصيد = رصيد البداية + كل الواردات − كل المصروفات، من شهر البداية حتى نهاية الشهر الحالي. الواردات تأتي تلقائياً من الاشتراكات المدفوعة، والمصروفات من الرواتب ومن الجداول. الراتب الذي لم يُسلَّم بعد يُخصم في شهره."}),
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"تعديل رصيد البداية", onclick:function(){ form.hidden = !form.hidden; }})]),
      form, cashMsg, h("h4", {text:"الرصيد شهراً بشهر"}), trail]);
  }
  function kpi(label, value, cls){ return h("div", {class:"a-kpi " + (cls || "")}, [h("span", {text:label}), h("strong", {text:value})]); }
  load();
  fill = null;
  var isAdmin = typeof TEACHER_MODE !== "undefined" && !TEACHER_MODE && !ACCOUNTANT_MODE;
  var resetRow = isAdmin ? h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn danger", text:"تصفير كل البيانات المالية", onclick:async function(){
    if(!window.confirm("سيُحذف كل ما أُدخل من اشتراكات ودفعات ورواتب وأسطر جداول، لتبدأ الأرقام من الصفر. تبقى أسماء الأطفال والموظفين والحسابات. هل تريد المتابعة؟")) return;
    var word = window.prompt("للتأكيد اكتب الكلمة RESET بالأحرف الكبيرة:");
    if(word === null) return;
    try{
      var done = await request("/api/admin/accounting/reset", {method:"POST", body:JSON.stringify({confirm:word})});
      setMsg(msg, "تم التصفير: " + done.fees + " رسم، " + done.payments + " دفعة، " + done.salaries + " سطر راتب، " + done.sheet_rows + " سطر جدول.", "ok");
      await load();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }}), h("span", {class:"hint", text:"للمدير فقط. لا يمكن التراجع."})]) : null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"نظرة عامة على المحاسبة"}),
    h("p", {class:"hint", text:"الأرقام هنا تتحدّث تلقائياً من الإدخالات الجديدة فقط (الاشتراكات والدفعات والرواتب وجداول المحاسبة). بدون إدخالات تكون كلها صفراً."}),
    h("div", {class:"a-form-grid"}, [accField("السنة", year), accField("العملة", currencySel)]), resetRow, msg]), body]);
}

/* -------------------------------------------------------------- payroll */
function tabSalaries(){
  var now = new Date();
  var filters = {year:String(now.getFullYear()), month:String(now.getMonth() + 1), currency:"SYP", needs_review:""};
  var data = {rows:[], totals:{}};
  var employees = [];
  var openId = "";
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var tables = h("div", {});

  var fYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var fMonth = accSelect(accMonths(true), filters.month);
  var fCurrency = accSelect(accCurrencyOptions(true), "SYP");
  var fReview = h("input", {type:"checkbox"});
  [fYear, fMonth, fCurrency, fReview].forEach(function(el){ el.addEventListener("change", function(){ filters.year = fYear.value; filters.month = fMonth.value; filters.currency = fCurrency.value; filters.needs_review = fReview.checked ? "true" : ""; load(); }); });

  var NEW = "__new__";
  var addEmp = accSelect([[NEW, "＋ موظف جديد (اكتب الاسم)"]], NEW);
  var addName = h("input", {type:"text", maxlength:"120", placeholder:"اسم الموظف / المدرسة", autocomplete:"off", list:"acc-staff"});
  var addJob = h("input", {type:"text", maxlength:"80", placeholder:"المسمى الوظيفي"});
  var addMonth = accSelect(accMonths(false), filters.month), addYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var addCurrency = accSelect(accCurrencyOptions(false), "SYP");
  var addBase = accNumber("", {required:"required"}), addBonus = accNumber("0"), addAdvance = accNumber("0"), addDeduction = accNumber("0");
  var addPaid = h("input", {type:"date"});
  var addPaidBy = h("input", {type:"text", maxlength:"120", placeholder:"من صرف الراتب؟", autocomplete:"off", list:"acc-persons"});
  var preview = h("strong", {class:"a-net", text:""});
  var nameField = accField("اسم الموظف", addName), jobField = accField("المسمى الوظيفي", addJob);
  function syncNew(){ var isNew = addEmp.value === NEW; nameField.hidden = !isNew; jobField.hidden = !isNew; }
  function netOf(b, p, a, d){ return Number(b || 0) + Number(p || 0) - Number(a || 0) - Number(d || 0); }
  function updatePreview(){ preview.textContent = "الصافي المستحق: " + money(netOf(addBase.value, addBonus.value, addAdvance.value, addDeduction.value)); }
  [addBase, addBonus, addAdvance, addDeduction].forEach(function(el){ el.addEventListener("input", updatePreview); });
  addEmp.addEventListener("change", function(){
    syncNew();
    var chosen = employees.filter(function(e){ return e.id === addEmp.value; })[0];
    if(chosen && chosen.salary !== null && chosen.salary !== undefined){ addBase.value = chosen.salary; addCurrency.value = chosen.salary_currency || "SYP"; updatePreview(); }
  });
  var addForm = h("form", {class:"a-card a-form-grid", hidden:"hidden"}, [
    h("h3", {text:"إضافة سطر راتب"}), accField("الموظف", addEmp), nameField, jobField,
    accField("الشهر", addMonth), accField("السنة", addYear), accField("العملة", addCurrency),
    accField("الراتب الأساسي", addBase), accField("المكافآت / الإضافي", addBonus), accField("السلف", addAdvance), accField("الخصومات", addDeduction),
    accField("تاريخ الاستلام", addPaid), accField("من صرف الراتب", addPaidBy), preview,
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"إضافة السطر"})])
  ]);
  addForm.addEventListener("submit", async function(event){
    event.preventDefault();
    var body = {year:Number(addYear.value), month:Number(addMonth.value), currency:addCurrency.value, base:addBase.value || "0",
      bonus:addBonus.value || "0", advance:addAdvance.value || "0", deduction:addDeduction.value || "0", paid_on:addPaid.value || null, paid_by:addPaidBy.value.trim()};
    if(addEmp.value === NEW){ body.employee_name = addName.value.trim(); body.job_title = addJob.value.trim(); if(body.employee_name.length < 2){ setMsg(msg, "اكتب اسم الموظف.", "err"); return; } }
    else body.employee_id = addEmp.value;
    try{
      await request("/api/admin/accounting/salaries", {method:"POST", body:JSON.stringify(body)});
      setMsg(msg, "تمت إضافة سطر الراتب.", "ok"); addName.value = ""; addBase.value = ""; addBonus.value = "0"; addAdvance.value = "0"; addDeduction.value = "0"; updatePreview();
      await loadEmployees(); await load();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  });

  function currencyTable(code){
    var rows = data.rows.filter(function(r){ return r.currency === code; });
    var t = data.totals[code] || {base:"0", bonus:"0", advance:"0", deduction:"0", net:"0"};
    var heads = ["الرقم","اسم الموظف / المدرسة","المسمى الوظيفي","الراتب الأساسي","المكافآت / الإضافي","السلف","الخصومات","الصافي المستحق","تاريخ الاستلام","صرفه",""];  // the signature column is only on the printed sheet
    var tbody = h("tbody", {});
    rows.forEach(function(r, i){
      var ed = r.needs_review ? salaryInline(r) : null;
      tbody.appendChild(h("tr", {class:"a-fee-row" + (r.needs_review ? " review" : "")}, [
        h("td", {class:"num", text:String(i + 1)}),
        ed ? h("td", {class:"name"}, [ed.name, h("span", {class:"a-badge review", text:"يحتاج مراجعة"})]) : h("td", {class:"name", dir:"auto", text:r.employee_name || "—"}),
        ed ? h("td", {}, [ed.job]) : h("td", {dir:"auto", text:r.job_title || "—"}),
        ed ? h("td", {class:"num"}, [ed.base]) : h("td", {class:"num", text:money(r.base)}),
        ed ? h("td", {class:"num"}, [ed.bonus]) : h("td", {class:"num", text:money(r.bonus)}),
        ed ? h("td", {class:"num"}, [ed.advance]) : h("td", {class:"num", text:money(r.advance)}),
        ed ? h("td", {class:"num"}, [ed.deduction]) : h("td", {class:"num", text:money(r.deduction)}),
        h("td", {class:"num strong", text:money(r.net)}),
        ed ? h("td", {}, [ed.date]) : h("td", {class:"num", text:r.paid_on || "—"}),
        ed ? h("td", {}, [ed.paid_by]) : h("td", {dir:"auto", title:r.recorded_by ? "سجّله: " + r.recorded_by : "", text:r.paid_by || "—"}),
        h("td", {}, [ed ? ed.save : "", h("button", {type:"button", class:"a-btn " + (openId === r.id ? "ghost" : "sun"), text:openId === r.id ? "إغلاق" : "تعديل", onclick:function(){ openId = openId === r.id ? "" : r.id; render(); }})])
      ]));
      if(openId === r.id) tbody.appendChild(editRow(r, heads.length));
    });
    if(!rows.length) tbody.appendChild(h("tr", {}, [h("td", {colspan:String(heads.length), class:"a-empty", text:"لا توجد رواتب بهذه العملة."})]));
    var foot = h("tfoot", {}, [h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"الإجمالي العام (" + code + ")"}), h("td", {class:"num", text:money(t.base)}), h("td", {class:"num", text:money(t.bonus)}),
      h("td", {class:"num", text:money(t.advance)}), h("td", {class:"num", text:money(t.deduction)}), h("td", {class:"num", text:money(t.net)}), h("td", {colspan:"3"})])]);
    return h("div", {class:"a-card"}, [h("h3", {text:"الرواتب بـ" + ACC_CURRENCY_NAME[code]}),
      h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), tbody, foot]))])]);
  }
  function salaryBody(fields){
    function num(el){ return el.value === "" ? null : el.value; }  // empty stays empty, never 0
    return JSON.stringify({employee_name:fields.name ? fields.name.value.trim() : null, job_title:fields.job.value.trim(), base:num(fields.base), bonus:num(fields.bonus),
      advance:num(fields.advance), deduction:num(fields.deduction), paid_on:fields.date.value || null, paid_by:fields.paid_by ? fields.paid_by.value.trim() : null});
  }
  function salaryInline(r){
    var f = {name:h("input", {type:"text", maxlength:"120", value:r.employee_name, placeholder:"الاسم", "aria-label":"اسم الموظف", list:"acc-staff"}),
      job:h("input", {type:"text", maxlength:"80", value:r.job_title, placeholder:"المسمى", "aria-label":"المسمى الوظيفي"}),
      base:accNumber(r.base, {"aria-label":"الراتب الأساسي"}), bonus:accNumber(r.bonus, {"aria-label":"المكافآت"}), advance:accNumber(r.advance, {"aria-label":"السلف"}),
      deduction:accNumber(r.deduction, {"aria-label":"الخصومات"}), date:h("input", {type:"date", value:r.paid_on || "", "aria-label":"تاريخ الاستلام"}),
      paid_by:h("input", {type:"text", maxlength:"120", value:r.paid_by || "", placeholder:"من صرف", "aria-label":"من صرف الراتب", list:"acc-persons"})};
    f.save = h("button", {type:"button", class:"a-btn sun", text:"حفظ", onclick:async function(){
      try{ await request("/api/admin/accounting/salaries/" + encodeURIComponent(r.id), {method:"PATCH", body:salaryBody(f)}); setMsg(msg, "تم حفظ التصحيح. اضغط «تمت المراجعة» بعد التأكد من السطر.", "ok"); await load(); }
      catch(error){ setMsg(msg, errText(error), "err"); }
    }});
    return f;
  }
  function editRow(r, cols){
    var job = h("input", {type:"text", maxlength:"80", value:r.job_title}), base = accNumber(r.base), bonus = accNumber(r.bonus), adv = accNumber(r.advance), ded = accNumber(r.deduction);
    var paid = h("input", {type:"date", value:r.paid_on || ""});
    var buttons = [h("button", {type:"submit", class:"a-btn sun", text:"حفظ"}),
      twoStep("حذف السطر", async function(){ await request("/api/admin/accounting/salaries/" + encodeURIComponent(r.id), {method:"DELETE"}); openId = ""; setMsg(msg, "تم حذف السطر.", "ok"); await load(); })];
    if(r.needs_review) buttons.unshift(h("button", {type:"button", class:"a-btn ghost", text:"تمت المراجعة", onclick:async function(){
      try{ await request("/api/admin/accounting/salaries/" + encodeURIComponent(r.id) + "/reviewed", {method:"POST"}); await load(); }catch(error){ setMsg(msg, errText(error), "err"); } }}));
    var form = h("form", {class:"a-form-grid"}, [
      r.needs_review ? h("p", {class:"a-review-note", dir:"auto", text:"النص الأصلي: " + (r.raw_text || "—") + " · المصدر: " + (r.source || "—")}) : "",
      accField("المسمى الوظيفي", job), accField("الراتب الأساسي", base), accField("المكافآت / الإضافي", bonus), accField("السلف", adv), accField("الخصومات", ded), accField("تاريخ الاستلام", paid),
      h("div", {class:"a-row"}, buttons)]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      try{
        await request("/api/admin/accounting/salaries/" + encodeURIComponent(r.id), {method:"PATCH", body:salaryBody({name:null, job:job, base:base, bonus:bonus, advance:adv, deduction:ded, date:paid})});
        setMsg(msg, "تم حفظ التعديل.", "ok"); await load();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return h("tr", {class:"a-detail-row"}, [h("td", {colspan:String(cols), class:"a-detail"}, [form])]);
  }
  function render(){ tables.innerHTML = ""; (filters.currency ? [filters.currency] : ACC_CURRENCIES).forEach(function(code){ tables.appendChild(currencyTable(code)); }); }
  async function load(){
    accLoadNames();
    var q = []; ["year","month","currency","needs_review"].forEach(function(k){ if(filters[k]) q.push(k + "=" + encodeURIComponent(filters[k])); });
    try{ data = await request("/api/admin/accounting/salaries?" + q.join("&")); render(); }
    catch(error){ tables.innerHTML = ""; tables.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  async function loadEmployees(){
    try{
      employees = await request("/api/admin/accounting/employees");
      var keep = addEmp.value; addEmp.innerHTML = ""; addEmp.appendChild(new Option("＋ موظف جديد (اكتب الاسم)", NEW));
      employees.forEach(function(e){ addEmp.appendChild(new Option(e.name + (e.job_title ? " — " + e.job_title : ""), e.id)); });
      addEmp.value = employees.some(function(e){ return e.id === keep; }) ? keep : NEW; syncNew();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  async function print(){
    var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
    try{ if(await accFillSavedSalaries(filters.year, filters.month, codes, msg)) await load(); }
    catch(error){ setMsg(msg, errText(error), "err"); return; }
    var period = (filters.month ? MONTHS_AR[Number(filters.month) - 1] + " " : "") + (filters.year || "");
    var parts = codes.map(function(code){
      var rows = data.rows.filter(function(r){ return r.currency === code; });
      var t = data.totals[code] || {base:"0", bonus:"0", advance:"0", deduction:"0", net:"0"};
      var body = rows.map(function(r, i){ return "<tr><td>" + (i + 1) + "</td><td class='l'>" + esc(r.employee_name) + "</td><td>" + esc(r.job_title || "—") + "</td><td class='n'>" + money(r.base) + "</td><td class='n'>" + money(r.bonus) +
        "</td><td class='n'>" + money(r.advance) + "</td><td class='n'>" + money(r.deduction) + "</td><td class='n'><b>" + money(r.net) + "</b></td><td class='n'>" + esc(r.paid_on || "—") + "</td><td>" + esc(r.paid_by || "") + "</td><td><span class='line'>&nbsp;</span></td></tr>"; }).join("");
      return {code:code, cols:[5,12,9,12,10,8,8,13,8,7,8], html:"<table><thead>" + accTh(["الرقم","اسم الموظف / المدرسة","المسمى الوظيفي","الراتب الأساسي","المكافآت / الإضافي","السلف","الخصومات","الصافي المستحق","تاريخ الاستلام","صرفه","توقيع المستلم"]) + "</thead><tbody>" +
        (body || "<tr><td colspan='11'>لا توجد بيانات</td></tr>") + "</tbody><tfoot><tr><td colspan='3'>الإجمالي العام (" + code + ")</td><td>" + money(t.base) + "</td><td>" + money(t.bonus) + "</td><td>" + money(t.advance) +
        "</td><td>" + money(t.deduction) + "</td><td>" + money(t.net) + "</td><td colspan='3'></td></tr></tfoot></table>"};
    });
    accPrint("كشف رواتب الموظفين والمدرسات", function(part){ return "الفترة: " + esc(period) + " &nbsp;|&nbsp; العملة: " + esc(ACC_CURRENCY_NAME[part.code]); }, parts, msg);
  }
  var filterCard = h("div", {class:"a-card"}, [h("h3", {text:"كشف رواتب الموظفين والمدرسات"}),
    h("p", {class:"hint", text:"الصافي المستحق = الراتب الأساسي + المكافآت − السلف − الخصومات. يُحسب تلقائياً."}),
    h("div", {class:"a-form-grid"}, [accField("السنة", fYear), accField("الشهر", fMonth), accField("العملة", fCurrency), h("label", {class:"a-field a-check-field"}, [fReview, h("span", {text:"فقط ما يحتاج مراجعة"})])]),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"＋ إضافة سطر راتب", onclick:function(){ addForm.hidden = !addForm.hidden; }}),
      h("button", {type:"button", class:"a-btn ghost", text:"إنشاء رواتب الشهر للجميع", onclick:async function(){
        var month = Number(fMonth.value), year = Number(fYear.value);
        if(!month || !year){ setMsg(msg, "اختر السنة والشهر أولاً.", "err"); return; }
        try{
          var created = 0, skipped = 0;
          var codes = fCurrency.value ? [fCurrency.value] : ACC_CURRENCIES;
          for(var i = 0; i < codes.length; i++){
            var res = await request("/api/admin/accounting/salaries/generate", {method:"POST", body:JSON.stringify({year:year, month:month, currency:codes[i]})});
            created += res.created; skipped += res.skipped;
          }
          setMsg(msg, "تم إنشاء " + created + " سطر راتب، وتخطّي " + skipped + " (موجود مسبقاً). الموظفون بلا راتب محفوظ لا يُنشأ لهم سطر.", "ok"); await load();
        }catch(error){ setMsg(msg, errText(error), "err"); }
      }}),
      h("button", {type:"button", class:"a-btn", text:"تصدير PDF / طباعة", onclick:print})]), msg]);
  syncNew(); updatePreview(); loadEmployees(); load();
  fill = null;
  return h("section", {}, [filterCard, addForm, tables]);
}

/* ------------------------------------------------- monthly / weekly sheet */
function tabSheet(type){
  var now = new Date();
  var isWeek = type !== "month";  // week and day sheets have separate income / expense columns
  var isDay = type === "day";
  var SHEET_TITLE = isDay ? "جدول المحاسبة اليومي" : isWeek ? "جدول المحاسبة الأسبوعي" : "جدول المحاسبة الشهري";
  var filters = {year:String(now.getFullYear()), month:String(now.getMonth() + 1), day:localToday(), currency:"SYP"};
  var sheets = {};
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var tables = h("div", {});
  var fYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var fMonth = accSelect(accMonths(false), filters.month);
  var fDay = h("input", {type:"date", value:filters.day});
  var fCurrency = accSelect(accCurrencyOptions(true), "SYP");
  [fYear, fMonth, fDay, fCurrency].forEach(function(el){ el.addEventListener("change", function(){ filters.year = fYear.value; filters.month = fMonth.value; filters.day = fDay.value; filters.currency = fCurrency.value; load(); }); });

  function sheetYear(){ return isWeek ? String(filters.day || "").slice(0, 4) || filters.year : filters.year; }  // week / day: the date decides
  function query(code){
    var q = "period_type=" + type + "&year=" + encodeURIComponent(sheetYear()) + "&currency=" + code;
    return q + (isWeek ? "&week_start=" + encodeURIComponent(filters.day) : "&month=" + encodeURIComponent(filters.month));
  }
  function entryBody(code, row, details, note, income, expense, person){
    var b = {period_type:type, year:Number(sheetYear()), currency:code, item_key:row.key, item_label:row.label, details:details, note:note, person:person || "", income:income || "0", expense:expense || "0", manual:true};
    if(isWeek) b.week_start = filters.day; else b.month = Number(filters.month);
    if(row.custom) b.id = row.id;
    return b;
  }
  function sheetCard(code){
    var sheet = sheets[code];
    var heads = isWeek ? ["البند / المادة","التفاصيل","البيان / الملاحظات","المسؤول (من صرف / استلم)","المبالغ الواردة","المبالغ الصادرة",""] : ["البند / المادة","التفاصيل","البيان / الملاحظات","المسؤول (من صرف / استلم)","المبلغ",""];
    var tbody = h("tbody", {});
    sheet.rows.forEach(function(row){
      if(row.key === "rolled"){  // a free row written on a day / week sheet, added up here: shown, not edited
        var readOnly = isWeek ? [h("td", {class:"num", text:Number(row.income) ? money(row.income) : "—"}), h("td", {class:"num", text:Number(row.expense) ? money(row.expense) : "—"})]
          : [h("td", {class:"num", text:money(Number(row.income) || Number(row.expense))})];
        var roRow = h("tr", {class:"a-rolled"}, [h("td", {class:"name"}, [row.label, h("span", {class:"a-badge partial", text:"مجمّع تلقائياً"})]), h("td", {text:"—"}), h("td", {text:"—"}), h("td", {text:"—"})].concat(readOnly).concat([h("td")]));
        Array.prototype.forEach.call(roRow.children, function(cellNode, i){ if(i > 0 && heads[i]) cellNode.setAttribute("data-label", heads[i]); });
        tbody.appendChild(roRow);
        return;
      }
      var details = h("input", {type:"text", maxlength:"500", value:row.details, "aria-label":"التفاصيل"});
      var note = h("input", {type:"text", maxlength:"500", value:row.note, "aria-label":"الملاحظات"});
      var person = h("input", {type:"text", maxlength:"120", value:row.person || "", placeholder:"الاسم", "aria-label":"المسؤول", list:"acc-persons", title:row.entered_by ? "أدخله: " + row.entered_by : ""});
      var income = accNumber(row.income, {"aria-label":"الوارد"}), expense = accNumber(row.expense, {"aria-label":"الصادر"});
      var amount = accNumber(Number(row.income) || Number(row.expense) || "", {"aria-label":"المبلغ"});
      var kindSel = (row.custom || row.choice) && !isWeek ? accSelect([["expense", "صادر"], ["income", "وارد"]], row.kind) : null;
      var amountCells = isWeek
        ? [h("td", {}, [income]), h("td", {}, [expense])]
        : [h("td", {}, [h("div", {class:"a-amount"}, [kindSel ? kindSel : h("span", {class:"a-tag kind-" + row.kind, text:row.kind === "income" ? "وارد" : "صادر"}), amount])])];
      var actions = [h("button", {type:"button", class:"a-btn sun", text:"حفظ", onclick:async function(){
        var inc = income.value, exp = expense.value;
        if(!isWeek){
          var kind = kindSel ? kindSel.value : row.kind;
          inc = kind === "income" ? amount.value : "0";
          exp = kind === "expense" ? amount.value : "0";
        }
        try{
          sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries", {method:"PUT", body:JSON.stringify(entryBody(code, row, details.value, note.value, inc, exp, person.value))}));
          setMsg(msg, "تم الحفظ.", "ok"); render();
        }catch(error){ setMsg(msg, errText(error), "err"); }
      }})];
      if(row.id && (row.custom || row.manual)) actions.push(twoStep(row.custom ? "حذف" : "إعادة للتلقائي", async function(){
        sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries/" + encodeURIComponent(row.id), {method:"DELETE"})); setMsg(msg, row.custom ? "تم حذف البند." : "عاد البند إلى القيمة التلقائية.", "ok"); render(); }));
      var label = h("td", {class:"name"}, [row.label, row.auto ? h("span", {class:"a-badge " + (row.manual ? "partial" : "paid"), text:row.manual ? "يدوي" : "تلقائي"}) : "",
        row.rolled ? h("span", {class:"a-badge partial", text:"مجمّع تلقائياً", title:"مجموع ما كُتب في الجداول الأدق (الأسبوعي واليومي)"}) : ""]);
      if(row.auto && row.manual) label.appendChild(h("small", {class:"hint", text:"القيمة التلقائية: " + money(row.key === "registration" ? row.auto_income : row.auto_expense)}));
      var sheetRow = h("tr", {}, [label, h("td", {}, [details]), h("td", {}, [note]), h("td", {}, [person])].concat(amountCells).concat([h("td", {}, [h("div", {class:"a-row", style:"margin:0"}, actions)])]));
      Array.prototype.forEach.call(sheetRow.children, function(cellNode, i){ if(i > 0 && heads[i]) cellNode.setAttribute("data-label", heads[i]); });  // shown as captions on a phone
      tbody.appendChild(sheetRow);
    });
    var t = sheet.totals;
    var balanceRows = (!isWeek && sheet.balance) ? [["رصيد أول الشهر", sheet.balance.opening], ["رصيد آخر الشهر", sheet.balance.closing]].map(function(b){
      return h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:b[0]}), h("td", {class:"num" + (Number(b[1]) < 0 ? " due" : ""), text:money(b[1])}), h("td")]);
    }) : [];
    var foot = h("tfoot", {}, isWeek ? [
      h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:"الإجمالي العام (" + code + ")"}), h("td", {class:"num", text:money(t.income)}), h("td", {class:"num", text:money(t.expense)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:"الصافي (واردات − مصروفات)"}), h("td", {colspan:"2", class:"num" + (Number(t.net) < 0 ? " due" : ""), text:money(t.net)}), h("td")])
    ] : [
      h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:"إجمالي الواردات"}), h("td", {class:"num", text:money(t.income)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:"إجمالي المصروفات"}), h("td", {class:"num", text:money(t.expense)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"4", text:"الإجمالي العام (الصافي)"}), h("td", {class:"num" + (Number(t.net) < 0 ? " due" : ""), text:money(t.net)}), h("td")])
    ].concat(balanceRows));
    var customForm = customRowForm(code);
    return h("div", {class:"a-card"}, [h("h3", {text:(isDay ? "اليوم " : isWeek ? "الأسبوع " : "الشهر ") + "بـ" + ACC_CURRENCY_NAME[code]}),
      h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table a-sheet"}, [h("colgroup", {}, (isWeek ? [19, 14, 15, 14, 13, 13, 12] : [22, 17, 18, 15, 16, 12]).map(function(w){ return h("col", {style:"width:" + w + "%"}); })),
        h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), tbody, foot])]), customForm]);
  }
  function customRowForm(code){
    var label = h("input", {type:"text", maxlength:"120", placeholder:"اسم البند"});
    var details = h("input", {type:"text", maxlength:"500"}), note = h("input", {type:"text", maxlength:"500"});
    var kind = accSelect([["expense", "صادر (مصروف)"], ["income", "وارد (إيراد)"]], "expense");
    var personNew = h("input", {type:"text", maxlength:"120", placeholder:"من صرف / من استلم؟", list:"acc-persons"});
    var amount = accNumber("", {required:"required"});
    var form = h("form", {class:"a-form-grid a-custom"}, [h("strong", {text:"＋ إضافة بند جديد"}), accField("البند", label), accField("التفاصيل", details), accField("البيان / الملاحظات", note), accField("المسؤول (من صرف / استلم)", personNew), accField("النوع", kind), accField("المبلغ", amount),
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn ghost", text:"إضافة البند"})])]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      var row = {key:"custom", label:label.value.trim(), custom:true};
      try{
        sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries", {method:"PUT", body:JSON.stringify(entryBody(code, row, details.value, note.value, kind.value === "income" ? amount.value : "0", kind.value === "expense" ? amount.value : "0", personNew.value))}));
        setMsg(msg, "تمت إضافة البند.", "ok"); render();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return form;
  }
  function render(){ tables.innerHTML = ""; (filters.currency ? [filters.currency] : ACC_CURRENCIES).forEach(function(code){ if(sheets[code]) tables.appendChild(sheetCard(code)); }); }
  async function load(){
    accLoadNames();
    try{
      var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
      var results = await Promise.all(codes.map(function(code){ return request("/api/admin/accounting/sheet?" + query(code)); }));
      codes.forEach(function(code, i){ sheets[code] = results[i]; });
      render();
    }catch(error){ tables.innerHTML = ""; tables.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  async function print(){
    var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
    if(!isWeek){  // monthly sheet: the "salaries" line comes from the payroll, so fill it from the saved salaries first
      try{ if(await accFillSavedSalaries(filters.year, filters.month, codes, msg)) await load(); }
      catch(error){ setMsg(msg, errText(error), "err"); return; }
    }
    var parts = codes.filter(function(c){ return sheets[c]; }).map(function(code){
      var sheet = sheets[code], t = sheet.totals;
      var body = sheet.rows.map(function(r){
        var kindText = Number(r.income) ? "وارد" : Number(r.expense) ? "صادر" : "";
        var amounts = isWeek ? "<td class='n'>" + (Number(r.income) ? money(r.income) : "") + "</td><td class='n'>" + (Number(r.expense) ? money(r.expense) : "") + "</td>"
          : "<td>" + kindText + "</td><td class='n'>" + ((Number(r.income) || Number(r.expense)) ? money(Number(r.income) || Number(r.expense)) : "") + "</td>";
        return "<tr><td class='l'>" + esc(r.label) + "</td><td class='l'>" + esc(r.details) + "</td><td class='l'>" + esc(r.note) + "</td><td class='l'>" + esc(r.person || "") + "</td>" + amounts + "</tr>";
      }).join("");
      var foot = isWeek ? "<tr><td colspan='4'>الإجمالي العام (" + code + ")</td><td>" + money(t.income) + "</td><td>" + money(t.expense) + "</td></tr><tr><td colspan='4'>الصافي</td><td colspan='2'>" + money(t.net) + "</td></tr>"
        : "<tr><td colspan='5'>إجمالي الواردات</td><td>" + money(t.income) + "</td></tr><tr><td colspan='5'>إجمالي المصروفات</td><td>" + money(t.expense) + "</td></tr><tr><td colspan='5'>الإجمالي العام (الصافي)</td><td>" + money(t.net) + "</td></tr>" +
          (sheet.balance ? "<tr><td colspan='5'>رصيد أول الشهر</td><td>" + money(sheet.balance.opening) + "</td></tr><tr><td colspan='5'>رصيد آخر الشهر</td><td>" + money(sheet.balance.closing) + "</td></tr>" : "");
      return {code:code, sheet:sheet, cols:isWeek ? [21, 18, 21, 16, 12, 12] : [22, 16, 18, 16, 9, 19], html:"<table><thead>" + accTh(isWeek ? ["البند / المادة","التفاصيل","البيان / الملاحظات","المسؤول (من صرف / استلم)","المبالغ الواردة","المبالغ الصادرة"] : ["البند / المادة","التفاصيل","البيان / الملاحظات","المسؤول (من صرف / استلم)","النوع","المبلغ"]) + "</thead><tbody>" + body + "</tbody><tfoot>" + foot + "</tfoot></table>"};
    });
    accPrint(SHEET_TITLE, function(part){
      return (isDay ? "التاريخ: " + esc(part.sheet.start) + " (" + esc(new Date(part.sheet.start + "T00:00:00").toLocaleDateString("ar-SY", {weekday:"long"})) + ")" : isWeek ? "من " + esc(part.sheet.start) + " إلى " + esc(part.sheet.end) : "الشهر: " + esc(MONTHS_AR[Number(filters.month) - 1]) + " " + esc(filters.year)) + " &nbsp;|&nbsp; العملة: " + esc(ACC_CURRENCY_NAME[part.code]); }, parts, msg);
  }
  var periodFields = isWeek ? [accField(isDay ? "اليوم" : "أي يوم من الأسبوع", fDay)] : [accField("السنة", fYear), accField("الشهر", fMonth)];
  var head = h("div", {class:"a-card"}, [h("h3", {text:SHEET_TITLE}),
    h("p", {class:"hint", text:"«رسوم التسجيل والاشتراكات» و«رواتب المدرسات والموظفين» تُعبَّآن تلقائياً: الاشتراكات حسب تاريخ الدفع، والرواتب حسب تاريخ الاستلام (الراتب الذي لم يُستلم بعد يُحسب في الجدول الشهري لشهره). عند تعديل المبلغ يدوياً يتوقف التحديث التلقائي لذلك البند؛ وحفظ ملاحظة فقط لا يغيّره. ما لم يُكتب في هذا الجدول يُجمع تلقائياً من الجداول الأدق (اليومي ثم الأسبوعي)، وما يُكتب هنا يغلب عليها."}),
    h("div", {class:"a-form-grid"}, periodFields.concat([accField("العملة", fCurrency)])),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn", text:"تصدير PDF / طباعة", onclick:print})]), msg]);
  load();
  fill = null;
  return h("section", {}, [head, tables]);
}

/* ----------------------------------------------------------- saved staff names */
/* Each saved person can be tied to a platform account (teacher / accountant); the name then belongs to that account. */
function tabEmployees(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var body = h("div", {});
  var accounts = [];
  var name = h("input", {type:"text", maxlength:"120", placeholder:"الاسم الكامل", autocomplete:"off", required:"required"});
  var job = h("input", {type:"text", maxlength:"80", placeholder:"المسمى الوظيفي (معلمة، مساعدة، سائق...)"});
  var accountNew = h("select", {});
  var salaryNew = accNumber("", {placeholder:"الراتب الشهري المعتاد"});
  var salaryCurNew = accSelect(accCurrencyOptions(false), "SYP");
  var form = h("form", {class:"a-form-grid", style:"margin-top:8px"}, [accField("الاسم", name), accField("المسمى الوظيفي", job), accField("الراتب الشهري (يُحفظ ويُملأ تلقائياً)", salaryNew), accField("عملة الراتب", salaryCurNew), accField("حساب الدخول (اختياري)", accountNew),
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"＋ حفظ الموظف"})])]);
  function accountOptions(select, current){
    select.innerHTML = "";
    select.appendChild(new Option("— بلا حساب دخول —", ""));
    accounts.forEach(function(a){
      var roleText = a.roles.map(function(r){ return r === "teacher" ? "معلمة" : "محاسب"; }).join(" + ");
      var takenByOther = a.linked_to && a.id !== current;
      var option = new Option(a.username + " (" + roleText + ")" + (takenByOther ? " — مرتبط بـ " + a.linked_to : ""), a.id);
      option.disabled = !!takenByOther;
      select.appendChild(option);
    });
    select.value = current || "";
  }
  form.addEventListener("submit", async function(event){
    event.preventDefault();
    try{
      await request("/api/admin/accounting/employees", {method:"POST", body:JSON.stringify({name:name.value.trim(), job_title:job.value.trim(), account_id:accountNew.value || null, salary:salaryNew.value === "" ? null : salaryNew.value, salary_currency:salaryCurNew.value})});
      name.value = ""; job.value = ""; salaryNew.value = ""; setMsg(msg, "تم حفظ الموظف، وسيظهر اسمه كاقتراح في كل الجداول.", "ok"); await load();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  });
  async function load(){
    accLoadNames();
    body.innerHTML = "";
    try{
      var results = await Promise.all([request("/api/admin/accounting/employees"), request("/api/admin/accounting/staff-accounts")]);
      var list = results[0]; accounts = results[1];
      accountOptions(accountNew, "");
      if(!list.length){ body.appendChild(h("div", {class:"a-empty", text:"لا يوجد موظفون محفوظون بعد."})); return; }
      list.forEach(function(employee){
        var nameInput = h("input", {type:"text", maxlength:"120", value:employee.name, "aria-label":"الاسم"});
        var jobInput = h("input", {type:"text", maxlength:"80", value:employee.job_title, "aria-label":"المسمى الوظيفي"});
        var salaryInput = accNumber(employee.salary, {"aria-label":"الراتب الشهري"});
        var salaryCur = accSelect(accCurrencyOptions(false), employee.salary_currency || "SYP");
        var accountSelect = h("select", {"aria-label":"حساب الدخول"});
        accountOptions(accountSelect, employee.account_id);
        body.appendChild(h("article", {class:"a-child"}, [
          h("div", {class:"a-child-head"}, [employee.account_username ? h("span", {class:"a-tag sun", text:"حساب: " + employee.account_username}) : h("span", {class:"a-tag", text:"بلا حساب دخول"})]),
          h("div", {class:"a-form-grid"}, [accField("الاسم", nameInput), accField("المسمى الوظيفي", jobInput), accField("الراتب الشهري", salaryInput), accField("عملة الراتب", salaryCur), accField("حساب الدخول", accountSelect),
            h("div", {class:"a-row"}, [
              h("button", {type:"button", class:"a-btn sun", text:"حفظ", onclick:async function(){
                try{
                  var saved = await request("/api/admin/accounting/employees/" + encodeURIComponent(employee.id), {method:"PATCH", body:JSON.stringify({name:nameInput.value.trim(), job_title:jobInput.value.trim(), account_id:accountSelect.value || null, salary:salaryInput.value === "" ? null : salaryInput.value, salary_currency:salaryCur.value})});
                  setMsg(msg, "تم الحفظ." + (saved.updated_salary_rows ? " وتحدّث راتب " + saved.updated_salary_rows + " سطر لم يُستلم بعد ليوافق الراتب الجديد." : ""), "ok"); await load(); }
                catch(error){ setMsg(msg, errText(error), "err"); }
              }}),
              twoStep("حذف من القائمة", async function(){
                await request("/api/admin/accounting/employees/" + encodeURIComponent(employee.id), {method:"DELETE"}); setMsg(msg, "أُزيل من القائمة (تبقى سجلات رواتبه القديمة).", "ok"); await load();
              })])])]));
      });
    }catch(error){ body.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  load();
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"الموظفون والأسماء المحفوظة"}),
    h("p", {class:"hint", text:"احفظ اسم كل موظف أو مدرّسة مرة واحدة واربطه بحساب دخوله إن وُجد، فيرتبط الاسم بالحساب (ويُعدَّل معه من «حسابات المنصة»). تظهر الأسماء كاقتراحات في الرواتب والجداول."}),
    form, msg]), h("div", {class:"a-card"}, [h("h3", {text:"القائمة"}), body])]);
}
