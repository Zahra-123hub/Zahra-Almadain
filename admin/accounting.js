/* Buchhaltung (المحاسبة): overview, fees, payroll, monthly and weekly sheets.
   Loaded before admin.js; uses its helpers (h, request, setMsg, errText, twoStep, money, esc, MONTHS_AR). */

var ACC_CURRENCIES = ["SYP", "USD"];  // the Syrian pound is the main currency
var ACC_CURRENCY_NAME = {USD:"الدولار الأمريكي (USD)", SYP:"الليرة السورية (SYP)"};
var ACC_VIEWER = {name:"", role:""};

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

/* Printable A4 landscape RTL page with the two signature fields. */
function accPrint(title, subtitle, bodyHtml, msgEl){
  var css = "@page{size:A4 landscape;margin:12mm}*{box-sizing:border-box}body{font-family:Almarai,'Segoe UI',Tahoma,sans-serif;color:#111;margin:0;font-size:11pt}" +
    "section{page-break-after:always}section:last-child{page-break-after:auto}header{text-align:center;margin-bottom:8px}h1{margin:0;font-size:17pt}h2{margin:2px 0;font-size:14pt}header p{margin:4px 0}" +
    "table{width:100%;border-collapse:collapse}th,td{border:1px solid #444;padding:4px 6px;text-align:center}td.l{text-align:right}th{background:#e8eef9}tfoot td{font-weight:700;background:#f3f3f3}" +
    ".due{color:#b00020;font-weight:700}.sign{display:flex;justify-content:space-between;gap:40px;margin-top:26px}.sign div{flex:1;text-align:center}.sign b{display:block;margin-bottom:34px}" +
    ".sign span{display:block;border-top:1px solid #000;padding-top:4px;min-height:24px}.sign i{display:block;margin-top:8px;font-style:normal}footer{margin-top:10px;font-size:9pt;color:#555;text-align:left}.line{border-top:1px solid #000;min-width:90px;display:inline-block}";
  var sign = "<div class='sign'><div><b>توقيع المحاسب</b><span>" + esc(ACC_VIEWER.role === "accountant" ? ACC_VIEWER.name : "") + "</span><i>التاريخ: ____ / ____ / ________</i></div>" +
    "<div><b>توقيع الإدارة</b><span></span><i>التاريخ: ____ / ____ / ________</i></div></div>";
  var today = new Date().toLocaleDateString("ar-SY");
  var html = "<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'><title>" + esc(title) + "</title>" +
    "<link href='https://fonts.googleapis.com/css2?family=Almarai:wght@400;700&display=swap' rel='stylesheet'><style>" + css + "</style></head><body>" +
    bodyHtml.map(function(part){
      return "<section><header><h1>روضة زهرة المدائن</h1><h2>" + esc(title) + "</h2><p>" + subtitle(part) + "</p></header>" + part.html + sign + "<footer>طُبع بتاريخ " + esc(today) + "</footer></section>";
    }).join("") + "</body></html>";
  var w = window.open("", "_blank");
  if(!w){ if(msgEl) setMsg(msgEl, "اسمح بالنوافذ المنبثقة لتصدير PDF.", "err"); return; }
  w.document.write(html);
  w.document.close();
  setTimeout(function(){ w.focus(); w.print(); }, 700);
}
function accTh(list){ return "<tr>" + list.map(function(t){ return "<th>" + t + "</th>"; }).join("") + "</tr>"; }

/* ---------------------------------------------------------------- shell */
function tabAccounting(){
  var sub = ACC_SUB || "overview";
  var panel = h("div", {});
  var nav = h("div", {class:"a-subnav", role:"tablist"});
  var SUBS = [["overview","نظرة عامة"], ["fees","اشتراكات الأطفال"], ["salaries","الرواتب"], ["day","الجدول اليومي"], ["week","الجدول الأسبوعي"], ["month","الجدول الشهري"]];
  function draw(){
    nav.innerHTML = "";
    SUBS.forEach(function(entry){
      nav.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(sub === entry[0]), text:entry[1], onclick:function(){ sub = ACC_SUB = entry[0]; draw(); }}));
    });
    panel.innerHTML = "";
    panel.appendChild(sub === "fees" ? tabFees() : sub === "salaries" ? tabSalaries() : sub === "month" ? tabSheet("month") : sub === "week" ? tabSheet("week") : sub === "day" ? tabSheet("day") : tabOverview());
  }
  request("/api/admin/fees/me").then(function(me){ ACC_VIEWER = me; }, function(){});
  draw();
  fill = null;
  return h("section", {}, [nav, panel]);
}
var ACC_SUB = "";

/* ------------------------------------------------------------- overview */
function tabOverview(){
  var now = new Date();
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(now.getFullYear())});
  var body = h("div", {});
  var msg = h("div", {class:"a-msg", role:"status"});
  year.addEventListener("change", load);

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
      if(review.fees || review.salaries){
        body.appendChild(h("div", {class:"a-card a-review-note"}, [h("strong", {text:"يوجد " + review.fees + " سطر اشتراكات و" + review.salaries + " سطر رواتب يحتاج إلى مراجعة."}),
          h("p", {class:"hint", text:"الأسطر المميّزة بالأصفر مستوردة من الأوراق وفيها خانة غير واضحة. افتحها وصحّحها ثم اضغط «تمت المراجعة»."})]));
      }
      ACC_CURRENCIES.forEach(function(code){
        var info = data[code];
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
  function kpi(label, value, cls){ return h("div", {class:"a-kpi " + (cls || "")}, [h("span", {text:label}), h("strong", {text:value})]); }
  load();
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"نظرة عامة على المحاسبة"}), h("div", {class:"a-form-grid"}, [accField("السنة", year)]), msg]), body]);
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
  var addName = h("input", {type:"text", maxlength:"120", placeholder:"اسم الموظف / المدرسة", autocomplete:"off"});
  var addJob = h("input", {type:"text", maxlength:"80", placeholder:"المسمى الوظيفي"});
  var addMonth = accSelect(accMonths(false), filters.month), addYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var addCurrency = accSelect(accCurrencyOptions(false), "SYP");
  var addBase = accNumber("", {required:"required"}), addBonus = accNumber("0"), addAdvance = accNumber("0"), addDeduction = accNumber("0");
  var addPaid = h("input", {type:"date"});
  var preview = h("strong", {class:"a-net", text:""});
  var nameField = accField("اسم الموظف", addName), jobField = accField("المسمى الوظيفي", addJob);
  function syncNew(){ var isNew = addEmp.value === NEW; nameField.hidden = !isNew; jobField.hidden = !isNew; }
  function netOf(b, p, a, d){ return Number(b || 0) + Number(p || 0) - Number(a || 0) - Number(d || 0); }
  function updatePreview(){ preview.textContent = "الصافي المستحق: " + money(netOf(addBase.value, addBonus.value, addAdvance.value, addDeduction.value)); }
  [addBase, addBonus, addAdvance, addDeduction].forEach(function(el){ el.addEventListener("input", updatePreview); });
  addEmp.addEventListener("change", syncNew);
  var addForm = h("form", {class:"a-card a-form-grid", hidden:"hidden"}, [
    h("h3", {text:"إضافة سطر راتب"}), accField("الموظف", addEmp), nameField, jobField,
    accField("الشهر", addMonth), accField("السنة", addYear), accField("العملة", addCurrency),
    accField("الراتب الأساسي", addBase), accField("المكافآت / الإضافي", addBonus), accField("السلف", addAdvance), accField("الخصومات", addDeduction),
    accField("تاريخ الاستلام", addPaid), preview,
    h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"إضافة السطر"})])
  ]);
  addForm.addEventListener("submit", async function(event){
    event.preventDefault();
    var body = {year:Number(addYear.value), month:Number(addMonth.value), currency:addCurrency.value, base:addBase.value || "0",
      bonus:addBonus.value || "0", advance:addAdvance.value || "0", deduction:addDeduction.value || "0", paid_on:addPaid.value || null};
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
    var heads = ["الرقم","اسم الموظف / المدرسة","المسمى الوظيفي","الراتب الأساسي","المكافآت / الإضافي","السلف","الخصومات","الصافي المستحق","تاريخ الاستلام",""];  // the signature column is only on the printed sheet
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
        h("td", {}, [ed ? ed.save : "", h("button", {type:"button", class:"a-btn " + (openId === r.id ? "ghost" : "sun"), text:openId === r.id ? "إغلاق" : "تعديل", onclick:function(){ openId = openId === r.id ? "" : r.id; render(); }})])
      ]));
      if(openId === r.id) tbody.appendChild(editRow(r, heads.length));
    });
    if(!rows.length) tbody.appendChild(h("tr", {}, [h("td", {colspan:String(heads.length), class:"a-empty", text:"لا توجد رواتب بهذه العملة."})]));
    var foot = h("tfoot", {}, [h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"الإجمالي العام (" + code + ")"}), h("td", {class:"num", text:money(t.base)}), h("td", {class:"num", text:money(t.bonus)}),
      h("td", {class:"num", text:money(t.advance)}), h("td", {class:"num", text:money(t.deduction)}), h("td", {class:"num", text:money(t.net)}), h("td", {colspan:"2"})])]);
    return h("div", {class:"a-card"}, [h("h3", {text:"الرواتب بـ" + ACC_CURRENCY_NAME[code]}),
      h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), tbody, foot])])]);
  }
  function salaryBody(fields){
    function num(el){ return el.value === "" ? null : el.value; }  // empty stays empty, never 0
    return JSON.stringify({employee_name:fields.name ? fields.name.value.trim() : null, job_title:fields.job.value.trim(), base:num(fields.base), bonus:num(fields.bonus),
      advance:num(fields.advance), deduction:num(fields.deduction), paid_on:fields.date.value || null});
  }
  function salaryInline(r){
    var f = {name:h("input", {type:"text", maxlength:"120", value:r.employee_name, placeholder:"الاسم", "aria-label":"اسم الموظف"}),
      job:h("input", {type:"text", maxlength:"80", value:r.job_title, placeholder:"المسمى", "aria-label":"المسمى الوظيفي"}),
      base:accNumber(r.base, {"aria-label":"الراتب الأساسي"}), bonus:accNumber(r.bonus, {"aria-label":"المكافآت"}), advance:accNumber(r.advance, {"aria-label":"السلف"}),
      deduction:accNumber(r.deduction, {"aria-label":"الخصومات"}), date:h("input", {type:"date", value:r.paid_on || "", "aria-label":"تاريخ الاستلام"})};
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
  function print(){
    var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
    var period = (filters.month ? MONTHS_AR[Number(filters.month) - 1] + " " : "") + (filters.year || "");
    var parts = codes.map(function(code){
      var rows = data.rows.filter(function(r){ return r.currency === code; });
      var t = data.totals[code] || {base:"0", bonus:"0", advance:"0", deduction:"0", net:"0"};
      var body = rows.map(function(r, i){ return "<tr><td>" + (i + 1) + "</td><td class='l'>" + esc(r.employee_name) + "</td><td>" + esc(r.job_title || "—") + "</td><td>" + money(r.base) + "</td><td>" + money(r.bonus) +
        "</td><td>" + money(r.advance) + "</td><td>" + money(r.deduction) + "</td><td><b>" + money(r.net) + "</b></td><td>" + esc(r.paid_on || "—") + "</td><td><span class='line'>&nbsp;</span></td></tr>"; }).join("");
      return {code:code, html:"<table><thead>" + accTh(["الرقم","اسم الموظف / المدرسة","المسمى الوظيفي","الراتب الأساسي","المكافآت / الإضافي","السلف","الخصومات","الصافي المستحق","تاريخ الاستلام","توقيع المستلم"]) + "</thead><tbody>" +
        (body || "<tr><td colspan='10'>لا توجد بيانات</td></tr>") + "</tbody><tfoot><tr><td colspan='3'>الإجمالي العام (" + code + ")</td><td>" + money(t.base) + "</td><td>" + money(t.bonus) + "</td><td>" + money(t.advance) +
        "</td><td>" + money(t.deduction) + "</td><td>" + money(t.net) + "</td><td colspan='2'></td></tr></tfoot></table>"};
    });
    accPrint("كشف رواتب الموظفين والمدرسات", function(part){ return "الفترة: " + esc(period) + " &nbsp;|&nbsp; العملة: " + esc(ACC_CURRENCY_NAME[part.code]); }, parts, msg);
  }
  var filterCard = h("div", {class:"a-card"}, [h("h3", {text:"كشف رواتب الموظفين والمدرسات"}),
    h("p", {class:"hint", text:"الصافي المستحق = الراتب الأساسي + المكافآت − السلف − الخصومات. يُحسب تلقائياً."}),
    h("div", {class:"a-form-grid"}, [accField("السنة", fYear), accField("الشهر", fMonth), accField("العملة", fCurrency), h("label", {class:"a-field a-check-field"}, [fReview, h("span", {text:"فقط ما يحتاج مراجعة"})])]),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"＋ إضافة سطر راتب", onclick:function(){ addForm.hidden = !addForm.hidden; }}),
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
  var filters = {year:String(now.getFullYear()), month:String(now.getMonth() + 1), day:new Date().toISOString().slice(0, 10), currency:"SYP"};
  var sheets = {};
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var tables = h("div", {});
  var fYear = h("input", {type:"number", min:"2000", max:"2100", value:filters.year});
  var fMonth = accSelect(accMonths(false), filters.month);
  var fDay = h("input", {type:"date", value:filters.day});
  var fCurrency = accSelect(accCurrencyOptions(true), "SYP");
  [fYear, fMonth, fDay, fCurrency].forEach(function(el){ el.addEventListener("change", function(){ filters.year = fYear.value; filters.month = fMonth.value; filters.day = fDay.value; filters.currency = fCurrency.value; load(); }); });

  function query(code){
    var q = "period_type=" + type + "&year=" + encodeURIComponent(filters.year) + "&currency=" + code;
    return q + (isWeek ? "&week_start=" + encodeURIComponent(filters.day) : "&month=" + encodeURIComponent(filters.month));
  }
  function entryBody(code, row, details, note, income, expense){
    var b = {period_type:type, year:Number(filters.year), currency:code, item_key:row.key, item_label:row.label, details:details, note:note, income:income || "0", expense:expense || "0", manual:true};
    if(isWeek) b.week_start = filters.day; else b.month = Number(filters.month);
    if(row.custom) b.id = row.id;
    return b;
  }
  function sheetCard(code){
    var sheet = sheets[code];
    var heads = isWeek ? ["البند / المادة","التفاصيل","البيان / الملاحظات","المبالغ الواردة","المبالغ الصادرة",""] : ["البند / المادة","التفاصيل","البيان / الملاحظات","المبلغ",""];
    var tbody = h("tbody", {});
    sheet.rows.forEach(function(row){
      var details = h("input", {type:"text", maxlength:"500", value:row.details, "aria-label":"التفاصيل"});
      var note = h("input", {type:"text", maxlength:"500", value:row.note, "aria-label":"الملاحظات"});
      var income = accNumber(row.income, {"aria-label":"الوارد"}), expense = accNumber(row.expense, {"aria-label":"الصادر"});
      var amount = accNumber(Number(row.income) || Number(row.expense) || "", {"aria-label":"المبلغ"});
      var kindSel = row.custom && !isWeek ? accSelect([["expense", "صادر"], ["income", "وارد"]], row.kind) : null;
      var amountCells = isWeek
        ? [h("td", {}, [income]), h("td", {}, [expense])]
        : [h("td", {}, [h("div", {class:"a-amount"}, [kindSel ? kindSel : h("span", {class:"a-tag", text:row.kind === "income" ? "وارد" : "صادر"}), amount])])];
      var actions = [h("button", {type:"button", class:"a-btn sun", text:"حفظ", onclick:async function(){
        var inc = income.value, exp = expense.value;
        if(!isWeek){
          var kind = kindSel ? kindSel.value : row.kind;
          inc = kind === "income" ? amount.value : "0";
          exp = kind === "expense" ? amount.value : "0";
        }
        try{
          sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries", {method:"PUT", body:JSON.stringify(entryBody(code, row, details.value, note.value, inc, exp))}));
          setMsg(msg, "تم الحفظ.", "ok"); render();
        }catch(error){ setMsg(msg, errText(error), "err"); }
      }})];
      if(row.id && (row.custom || row.manual)) actions.push(twoStep(row.custom ? "حذف" : "إعادة للتلقائي", async function(){
        sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries/" + encodeURIComponent(row.id), {method:"DELETE"})); setMsg(msg, row.custom ? "تم حذف البند." : "عاد البند إلى القيمة التلقائية.", "ok"); render(); }));
      var label = h("td", {class:"name"}, [row.label, row.auto ? h("span", {class:"a-badge " + (row.manual ? "partial" : "paid"), text:row.manual ? "يدوي" : "تلقائي"}) : ""]);
      if(row.auto && row.manual) label.appendChild(h("small", {class:"hint", text:"القيمة التلقائية: " + money(row.key === "registration" ? row.auto_income : row.auto_expense)}));
      tbody.appendChild(h("tr", {}, [label, h("td", {}, [details]), h("td", {}, [note])].concat(amountCells).concat([h("td", {}, [h("div", {class:"a-row", style:"margin:0"}, actions)])])));
    });
    var t = sheet.totals;
    var foot = h("tfoot", {}, isWeek ? [
      h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"الإجمالي العام (" + code + ")"}), h("td", {class:"num", text:money(t.income)}), h("td", {class:"num", text:money(t.expense)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"الصافي (واردات − مصروفات)"}), h("td", {colspan:"2", class:"num" + (Number(t.net) < 0 ? " due" : ""), text:money(t.net)}), h("td")])
    ] : [
      h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"إجمالي الواردات"}), h("td", {class:"num", text:money(t.income)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"إجمالي المصروفات"}), h("td", {class:"num", text:money(t.expense)}), h("td")]),
      h("tr", {class:"a-total"}, [h("td", {colspan:"3", text:"الإجمالي العام (الصافي)"}), h("td", {class:"num" + (Number(t.net) < 0 ? " due" : ""), text:money(t.net)}), h("td")])
    ]);
    var customForm = customRowForm(code);
    return h("div", {class:"a-card"}, [h("h3", {text:(isDay ? "اليوم " : isWeek ? "الأسبوع " : "الشهر ") + "بـ" + ACC_CURRENCY_NAME[code]}),
      h("div", {class:"a-table-wrap"}, [h("table", {class:"a-table a-sheet"}, [h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), tbody, foot])]), customForm]);
  }
  function customRowForm(code){
    var label = h("input", {type:"text", maxlength:"120", placeholder:"اسم البند"});
    var details = h("input", {type:"text", maxlength:"500"}), note = h("input", {type:"text", maxlength:"500"});
    var kind = accSelect([["expense", "صادر (مصروف)"], ["income", "وارد (إيراد)"]], "expense");
    var amount = accNumber("", {required:"required"});
    var form = h("form", {class:"a-form-grid a-custom"}, [h("strong", {text:"＋ إضافة بند جديد"}), accField("البند", label), accField("التفاصيل", details), accField("البيان / الملاحظات", note), accField("النوع", kind), accField("المبلغ", amount),
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn ghost", text:"إضافة البند"})])]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      var row = {key:"custom", label:label.value.trim(), custom:true};
      try{
        sheets[code] = Object.assign(sheets[code], await request("/api/admin/accounting/entries", {method:"PUT", body:JSON.stringify(entryBody(code, row, details.value, note.value, kind.value === "income" ? amount.value : "0", kind.value === "expense" ? amount.value : "0"))}));
        setMsg(msg, "تمت إضافة البند.", "ok"); render();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return form;
  }
  function render(){ tables.innerHTML = ""; (filters.currency ? [filters.currency] : ACC_CURRENCIES).forEach(function(code){ if(sheets[code]) tables.appendChild(sheetCard(code)); }); }
  async function load(){
    try{
      var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
      var results = await Promise.all(codes.map(function(code){ return request("/api/admin/accounting/sheet?" + query(code)); }));
      codes.forEach(function(code, i){ sheets[code] = results[i]; });
      render();
    }catch(error){ tables.innerHTML = ""; tables.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  function print(){
    var codes = filters.currency ? [filters.currency] : ACC_CURRENCIES;
    var parts = codes.filter(function(c){ return sheets[c]; }).map(function(code){
      var sheet = sheets[code], t = sheet.totals;
      var body = sheet.rows.map(function(r){
        var amounts = isWeek ? "<td>" + (Number(r.income) ? money(r.income) : "") + "</td><td>" + (Number(r.expense) ? money(r.expense) : "") + "</td>" : "<td>" + money(Number(r.income) || Number(r.expense)) + "</td>";
        return "<tr><td class='l'>" + esc(r.label) + "</td><td class='l'>" + esc(r.details) + "</td><td class='l'>" + esc(r.note) + "</td>" + amounts + "</tr>";
      }).join("");
      var foot = isWeek ? "<tr><td colspan='3'>الإجمالي العام (" + code + ")</td><td>" + money(t.income) + "</td><td>" + money(t.expense) + "</td></tr><tr><td colspan='3'>الصافي</td><td colspan='2'>" + money(t.net) + "</td></tr>"
        : "<tr><td colspan='3'>إجمالي الواردات</td><td>" + money(t.income) + "</td></tr><tr><td colspan='3'>إجمالي المصروفات</td><td>" + money(t.expense) + "</td></tr><tr><td colspan='3'>الإجمالي العام (الصافي)</td><td>" + money(t.net) + "</td></tr>";
      return {code:code, sheet:sheet, html:"<table><thead>" + accTh(isWeek ? ["البند / المادة","التفاصيل","البيان / الملاحظات","المبالغ الواردة","المبالغ الصادرة"] : ["البند / المادة","التفاصيل","البيان / الملاحظات","المبلغ"]) + "</thead><tbody>" + body + "</tbody><tfoot>" + foot + "</tfoot></table>"};
    });
    accPrint(SHEET_TITLE, function(part){
      return (isDay ? "التاريخ: " + esc(part.sheet.start) : isWeek ? "من " + esc(part.sheet.start) + " إلى " + esc(part.sheet.end) : "الشهر: " + esc(MONTHS_AR[Number(filters.month) - 1]) + " " + esc(filters.year)) + " &nbsp;|&nbsp; العملة: " + esc(ACC_CURRENCY_NAME[part.code]); }, parts, msg);
  }
  var periodFields = isWeek ? [accField(isDay ? "اليوم" : "أي يوم من الأسبوع", fDay)] : [accField("السنة", fYear), accField("الشهر", fMonth)];
  if(isWeek) periodFields.unshift(accField("السنة", fYear));
  var head = h("div", {class:"a-card"}, [h("h3", {text:SHEET_TITLE}),
    h("p", {class:"hint", text:"«رسوم التسجيل والاشتراكات» و«رواتب المدرسات والموظفين» تُعبَّآن تلقائياً من الاشتراكات المدفوعة ومن صافي الرواتب، ويمكن تعديلهما يدوياً."}),
    h("div", {class:"a-form-grid"}, periodFields.concat([accField("العملة", fCurrency)])),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn", text:"تصدير PDF / طباعة", onclick:print})]), msg]);
  load();
  fill = null;
  return h("section", {}, [head, tables]);
}
