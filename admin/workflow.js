/* Buchhaltung as a guided workflow (سير العمل المحاسبي).
   The eleven steps of a month in their working order, each with a status; the screens of the steps are the ones in accounting.js.
   Loaded after accounting.js and before admin.js. The statuses come from the server (/api/admin/accounting/workflow). */

var ACC_ORDER = ["basics", "staff", "fees", "income", "expenses", "payroll", "reconcile", "summary", "reports", "close", "archive"];
var ACC_STEP_TEXT = {
  dashboard: ["لوحة سير العمل", "ما تم وما بقي، والخطوة التالية"],
  basics: ["الإعدادات الأساسية", "العملات وسعر الصرف والصندوق والبنود"],
  staff: ["الموظفون والرواتب", "الموظفون تضيفهم الإدارة، وهنا تُنشأ رواتب الشهر المستحقة"],
  fees: ["اشتراكات الأطفال", "الاشتراك الشهري والمتبقي على كل ولي أمر (الأطفال تضيفهم الإدارة)"],
  income: ["الإيرادات", "كل ما دخل الصندوق: الدفعات وغيرها"],
  expenses: ["المصروفات والإيصالات", "كل ما خرج من الصندوق مع التاريخ والبيان والإيصال"],
  payroll: ["دفع الرواتب", "الرواتب المدفوعة فعلاً ومطابقتها بالمستحق"],
  reconcile: ["المطابقة وجرد الصندوق", "عدّ الصندوق ومقارنته بالدفاتر"],
  summary: ["الملخص المالي", "الرصيد الحالي والواردات والمصروفات"],
  reports: ["التقارير", "يومي وأسبوعي وشهري وسنوي"],
  close: ["إغلاق الشهر", "مراجعة الشهر ثم قفله نهائياً"],
  archive: ["التصدير والأرشيف", "ملف كامل للشهر المغلق وسجل التصدير"]
};
var ACC_STATUS_TEXT = {pending: "معلّقة", in_progress: "قيد التنفيذ", done: "مكتملة"};
var ACC_STEP = "dashboard";
var ACC_PERIOD = {year: new Date().getFullYear(), month: new Date().getMonth() + 1};
var ACC_FLOW = null;
var ACC_SUBSEL = {};
var ACC_GO = function(){};
var ACC_REFRESH = function(){ return Promise.resolve(); };

/* A short message at the bottom of the screen: a result must be seen even when the table is scrolled far from its top. */
function accToast(text, kind){
  var box = document.getElementById("a-toast");
  if(!box){ box = document.createElement("div"); box.id = "a-toast"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
  box.textContent = uiText(text);
  box.className = "a-toast " + (kind === "err" ? "err" : "ok") + " show";
  clearTimeout(accToast.timer);
  accToast.timer = setTimeout(function(){ box.classList.remove("show"); }, kind === "err" ? 7000 : 3000);
}
window.addEventListener("beforeunload", function(event){
  if(typeof window.accSheetDirtyCount === "function" && window.accSheetDirtyCount()){ event.preventDefault(); event.returnValue = ""; }
});
function accEnglish(){ return typeof ADMIN_LANG !== "undefined" && ADMIN_LANG === "en"; }
/* "3 expenses have no receipt": the number goes into the sentence, so the two languages are written out here. */
function accIssueText(issue){
  var n = issue.count;
  var table = {
    open_fees: ["" + n + " اشتراك لم يُسدَّد بالكامل", n + " fee(s) not fully paid"],
    review_fees: ["" + n + " اشتراك يحتاج مراجعة", n + " fee line(s) need review"],
    review_salaries: ["" + n + " راتب يحتاج مراجعة", n + " salary line(s) need review"],
    missing_receipts: ["" + n + " مصروف بلا إيصال", n + " expense(s) without a receipt"],
    cash_difference: ["فرق بين الصندوق والدفاتر", "The cash box differs from the books"],
    no_cash_count: ["لم يُجرَ جرد للصندوق هذا الشهر", "No cash count this month"],
    unpaid_salaries: ["" + n + " راتب لم يُدفع بعد", n + " salary line(s) not paid yet"],
    not_ended: ["الشهر لم ينتهِ بعد", "The month has not ended yet"]
  };
  var pair = table[issue.kind] || [issue.kind, issue.kind];
  return accEnglish() ? pair[1] : pair[0];
}
function accStepOf(key){ return ACC_FLOW ? ACC_FLOW.steps.filter(function(s){ return s.key === key; })[0] : null; }
function accPeriodQuery(){ return "year=" + ACC_PERIOD.year + "&month=" + ACC_PERIOD.month; }

/* Which steps are done / still open for the chosen month, as small marked lines with a button to the step. */
function accFlowChecks(keys, withClose){
  var card = h("div", {class:"a-card a-checks"}, [h("h3", {text:"فحص قبل المتابعة"})]);
  if(!ACC_FLOW){ card.appendChild(h("p", {class:"hint", text:"تعذّر تحميل حالة الشهر."})); return card; }
  keys.forEach(function(key){
    var step = accStepOf(key);
    if(!step) return;
    var issues = step.issues.map(function(issue){ return h("small", {class:"a-issue", text:accIssueText(issue)}); });
    card.appendChild(h("div", {class:"a-check s-" + step.status}, [
      h("span", {class:"a-check-mark", text:step.status === "done" ? "✓" : step.status === "in_progress" ? "…" : "○"}),
      h("div", {class:"a-check-body"}, [h("strong", {text:ACC_STEP_TEXT[key][0]}), h("small", {class:"hint", text:ACC_STATUS_TEXT[step.status]})].concat(issues)),
      h("button", {type:"button", class:"a-btn ghost", text:"فتح الخطوة", onclick:function(){ ACC_GO(key); }})]));
  });
  if(withClose && ACC_FLOW.close){
    ACC_FLOW.close.blockers.forEach(function(item){ card.appendChild(h("p", {class:"a-msg err", text:"⛔ " + accIssueText(item)})); });
    ACC_FLOW.close.warnings.forEach(function(item){ card.appendChild(h("p", {class:"a-msg warn", text:"⚠ " + accIssueText(item)})); });
  }
  return card;
}

/* ------------------------------------------------------------------ step 0: the dashboard */
function tabDashboard(){
  var body = h("div", {});
  function draw(){
    body.innerHTML = "";
    if(!ACC_FLOW){ body.appendChild(h("div", {class:"a-card"}, [h("p", {class:"a-msg err", text:"تعذّر تحميل حالة الشهر. تأكّد من الاتصال ثم حدّث الصفحة."})])); return; }
    var done = ACC_FLOW.steps.filter(function(s){ return s.status === "done"; }).length;
    var percent = Math.round(done * 100 / ACC_FLOW.steps.length);
    var next = ACC_FLOW.next;
    var head = [h("h3", {text:MONTHS_AR[ACC_PERIOD.month - 1] + " " + ACC_PERIOD.year}),
      h("div", {class:"a-progress", role:"progressbar", "aria-valuemin":"0", "aria-valuemax":"100", "aria-valuenow":String(percent)}, [h("span", {style:"width:" + percent + "%"})]),
      h("p", {class:"hint", text:(accEnglish() ? done + " of " + ACC_FLOW.steps.length + " steps complete" : "اكتملت " + done + " من " + ACC_FLOW.steps.length + " خطوة")})];
    if(ACC_FLOW.locked) head.push(h("p", {class:"a-msg ok", text:"🔒 هذا الشهر مغلق. يبقى التصدير والأرشفة والاطّلاع على التقارير."}));
    else if(next) head.push(h("div", {class:"a-row"}, [h("strong", {text:"الخطوة التالية"}), h("button", {type:"button", class:"a-btn sun", text:ACC_STEP_TEXT[next][0], onclick:function(){ ACC_GO(next); }})]));
    body.appendChild(h("div", {class:"a-card a-flow-head"}, head));
    var list = h("ol", {class:"a-flow"});
    ACC_FLOW.steps.forEach(function(step){
      var issues = step.issues.map(function(issue){ return h("li", {class:"a-issue", text:accIssueText(issue)}); });
      var progress = step.total ? h("small", {class:"hint", dir:"ltr", text:step.done + " / " + step.total}) : "";
      list.appendChild(h("li", {class:"a-flow-step s-" + step.status + (step.key === next ? " is-next" : "") + (step.issues.length ? " has-issue" : "")}, [
        h("span", {class:"a-flow-n", text:step.status === "done" ? "✓" : String(step.n)}),
        h("div", {class:"a-flow-body"}, [
          h("div", {class:"a-flow-title"}, [h("strong", {text:ACC_STEP_TEXT[step.key][0]}), h("span", {class:"a-badge " + (step.status === "done" ? "paid" : step.status === "in_progress" ? "partial" : "open"), text:ACC_STATUS_TEXT[step.status]}), step.key === next ? h("span", {class:"a-badge due", text:"التالية"}) : "", progress]),
          h("small", {class:"hint", text:ACC_STEP_TEXT[step.key][1]}),
          issues.length ? h("ul", {class:"a-issues"}, issues) : ""]),
        h("button", {type:"button", class:step.key === next ? "a-btn sun" : "a-btn ghost", text:"فتح", onclick:function(){ ACC_GO(step.key); }})]));
    });
    body.appendChild(h("div", {class:"a-card"}, [list]));
  }
  draw();
  fill = null;
  return h("section", {}, [body]);
}

/* ------------------------------------------------------------------ step 1: the basics */
function tabBasics(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var body = h("div", {});
  var isAdmin = typeof TEACHER_MODE !== "undefined" && !TEACHER_MODE && !ACCOUNTANT_MODE;
  var ITEMS = [["رسوم التسجيل والاشتراكات", "إيراد · يُحسب تلقائياً من دفعات الأهل"], ["المصروفات التشغيلية", "مصروف"], ["رواتب المدرسات والموظفين", "مصروف · يُحسب تلقائياً من الرواتب المدفوعة"],
    ["الأنشطة والفعاليات", "مصروف"], ["المشتريات والوسائل التعليمية", "مصروف"], ["البوفيه", "وارد أو صادر"], ["وسائل النقل (المواصلات)", "وارد أو صادر"],
    ["الإعلانات والدعاية", "وارد أو صادر"], ["مصروفات نثرية / أخرى", "مصروف"]];

  function rateCard(rates){
    var current = rates.current;
    var today = localToday();
    function readable(text){ var n = Number(text); return isFinite(n) ? n.toLocaleString("en-US", {maximumFractionDigits: 4}) : text; }
    var head;
    if(current){
      var perPound = Number(current.rate) > 0 ? 100000 / Number(current.rate) : 0;
      var source = current.stale ? (accEnglish() ? "Last known rate (the online source could not be reached)" : "آخر سعر معروف (تعذّر الوصول إلى مصدر الأسعار)") :
        current.source === "auto" ? (accEnglish() ? "Fetched automatically from the internet" : "يجلبه النظام تلقائياً من الإنترنت") : (accEnglish() ? "Entered by hand" : "مُدخل يدوياً");
      head = [h("div", {class:"a-kpis"}, [
        h("div", {class:"a-kpi good"}, [h("span", {text:"1 دولار (USD) ="}), h("strong", {dir:"ltr", text:readable(current.rate) + " SYP"})]),
        h("div", {class:"a-kpi"}, [h("span", {text:"100,000 ليرة (SYP) ≈"}), h("strong", {dir:"ltr", text:perPound.toFixed(2) + " USD"})])]),
        h("p", {class:"hint", text:source + " · " + current.date})];
    }else{
      head = [h("p", {class:"a-msg err", text:"لم يتمكّن النظام من جلب سعر الصرف من الإنترنت الآن. جرّب «تحديث الآن»، أو أدخل السعر يدوياً."})];
    }
    var rate = h("input", {type:"text", inputmode:"decimal", dir:"ltr", placeholder:"15000", "aria-label":"سعر الصرف", required:"required"});
    var date = h("input", {type:"date", value:today, max:today});
    var form = h("form", {class:"a-form-grid", hidden:current ? "hidden" : null}, [accField("كم ليرة سورية تساوي 1 دولار", rate), accField("ابتداءً من تاريخ", date), h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"حفظ سعر الصرف"})])]);
    if(!current) form.hidden = false;
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      var text = rate.value.trim().replace(/[٠-٩]/g, function(d){ return String(d.charCodeAt(0) - 1632); }).replace(",", ".");
      try{ await request("/api/admin/accounting/rates", {method:"PUT", body:JSON.stringify({effective_date:date.value, syp_per_usd:text})}); setMsg(msg, "تم حفظ سعر الصرف.", "ok"); ACC_REFRESH(); await load(); }
      catch(error){ setMsg(msg, errText(error), "err"); }
    });
    async function refresh(force){
      try{ await request("/api/admin/accounting/rates/refresh" + (force ? "?force=true" : ""), {method:"POST"}); setMsg(msg, "تم تحديث سعر الصرف من الإنترنت.", "ok"); ACC_REFRESH(); await load(); }
      catch(error){ setMsg(msg, errText(error), "err"); }
    }
    var buttons = [h("button", {type:"button", class:"a-btn sun", text:"تحديث الآن من الإنترنت", onclick:function(){ refresh(false); }})];
    if(current && current.source === "manual") buttons.push(h("button", {type:"button", class:"a-btn ghost", text:"العودة إلى السعر التلقائي", onclick:function(){ refresh(true); }}));
    buttons.push(h("button", {type:"button", class:"a-btn ghost", text:"تعديل يدوي (اختياري)", onclick:function(){ form.hidden = !form.hidden; }}));
    var rows = rates.rates.slice(0, 8).map(function(r){ return h("tr", {}, [h("td", {class:"name", dir:"ltr", text:r.date}), h("td", {class:"num", dir:"ltr", text:readable(r.rate)}), h("td", {text:r.source === "auto" ? "تلقائي" : "يدوي"})]); });
    return h("div", {class:"a-card"}, [h("h3", {text:"سعر الصرف"})].concat(head, [
      h("p", {class:"hint", text:"يعرف النظام سعر اليوم بنفسه: يجلبه من الإنترنت مرة واحدة كل يوم ويحفظه، ويحوّل به الدولار إلى ليرة والعكس. لا تحتاج إلى إدخاله. السعر اليدوي يتقدّم على التلقائي ليوم واحد فقط."}),
      h("p", {class:"hint", text:"الأسعار القديمة لا تتغير: كل عملية محوَّلة تحتفظ بسعر يومها."}), h("div", {class:"a-row"}, buttons), form,
      rows.length ? h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, ["التاريخ", "السعر", "المصدر"].map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)]))]) : ""]));
  }
  function openingCard(code, cash){
    var amount = accNumber(cash.opening, {"aria-label":"رصيد البداية", required:"required"});
    var monthSel = accSelect(accMonths(false), String(cash.start_month));
    var yearInput = h("input", {type:"number", min:"2000", max:"2100", value:String(cash.start_year)});
    var form = h("form", {class:"a-form-grid"}, [accField("المبلغ في الصندوق عند البداية (" + code + ")", amount), accField("بداية الحساب من شهر", monthSel), accField("السنة", yearInput),
      h("div", {class:"a-row"}, [h("button", {type:"submit", class:"a-btn sun", text:"حفظ رصيد البداية"})])]);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      try{ await request("/api/admin/accounting/cash", {method:"PUT", body:JSON.stringify({currency:code, opening:amount.value || "0", start_year:Number(yearInput.value), start_month:Number(monthSel.value)})}); setMsg(msg, "تم حفظ رصيد البداية.", "ok"); ACC_REFRESH(); await load(); }
      catch(error){ setMsg(msg, errText(error), "err"); }
    });
    return h("div", {class:"a-card"}, [h("h3", {text:"الصندوق بـ" + ACC_CURRENCY_NAME[code]}),
      h("span", {class:"a-badge " + (cash.configured ? "paid" : "open"), text:cash.configured ? "محدَّد" : "غير محدَّد"}),
      h("p", {class:"hint", text:cash.configured ? "رصيد البداية " + money(cash.opening) + " منذ " + cash.start_month + "/" + cash.start_year + ". تغييره يعيد حساب كل الأرصدة اللاحقة." : "بدون رصيد بداية يبدأ الحساب من صفر عند أول شهر فيه بيانات. أدخل المبلغ الموجود في الصندوق عند بدء العمل بالنظام."}), form]);
  }
  function itemsCard(){
    return h("div", {class:"a-card"}, [h("h3", {text:"البنود (فئات الإيراد والمصروف)"}),
      h("p", {class:"hint", text:"هذه هي البنود الثابتة للجداول. لأي شيء آخر أضف «بنداً مخصصاً» في الجدول اليومي باسمك."}),
      h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, ["البند", "نوعه"].map(function(t){ return h("th", {text:t}); }))]),
        h("tbody", {}, ITEMS.map(function(i){ return h("tr", {}, [h("td", {class:"name", text:i[0]}), h("td", {text:i[1]})]); }))]))])]);
  }
  function resetRow(){
    if(!isAdmin) return "";
    return h("div", {class:"a-card"}, [h("h3", {text:"تصفير البيانات المالية"}), h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn danger", text:"تصفير كل البيانات المالية", onclick:async function(){
      if(!window.confirm("سيُحذف كل ما أُدخل من اشتراكات ودفعات ورواتب وأسطر جداول، لتبدأ الأرقام من الصفر. تبقى أسماء الأطفال والموظفين والحسابات. هل تريد المتابعة؟")) return;
      var word = window.prompt("للتأكيد اكتب الكلمة RESET بالأحرف الكبيرة:");
      if(word === null) return;
      try{
        var done = await request("/api/admin/accounting/reset", {method:"POST", body:JSON.stringify({confirm:word})});
        setMsg(msg, "تم التصفير: " + done.fees + " رسم، " + done.payments + " دفعة، " + done.salaries + " سطر راتب، " + done.sheet_rows + " سطر جدول.", "ok"); ACC_REFRESH(); await load();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    }}), h("span", {class:"hint", text:"للمدير فقط. لا يمكن التراجع."})])]);
  }
  async function load(){
    body.innerHTML = "";
    try{
      var results = await Promise.all([request("/api/admin/accounting/rates"), request("/api/admin/accounting/cash")]);
      body.appendChild(rateCard(results[0]));
      ACC_CURRENCIES.forEach(function(code){ body.appendChild(openingCard(code, results[1][code])); });
      body.appendChild(itemsCard());
      body.appendChild(resetRow());
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  load();
  fill = null;
  return h("section", {}, [msg, body]);
}

/* ------------------------------------------------------------------ zero a table on purpose (administrator only) */
/* `opts.period()` gives {year, month}; `opts.scopes` the parts that can be emptied; `opts.onDone` reloads the screen. */
function accResetCard(opts){
  var card = h("div", {class:"a-card a-reset", hidden:"hidden"});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var boxes = {};
  function show(){
    var rows = opts.scopes.map(function(scope){
      var box = h("input", {type:"checkbox"});
      box.checked = !!scope[2];
      boxes[scope[0]] = box;
      return h("label", {class:"a-check-field"}, [box, h("span", {text:scope[1]})]);
    });
    card.appendChild(h("h3", {text:"تصفير الجدول"}));
    card.appendChild(h("p", {class:"hint", text:"يمسح الأجزاء المختارة من الشهر المعروض فتبدأ أرقامه من الصفر. الأطفال والموظفون والحسابات تبقى. لا يعمل على شهر مغلق ولا يمكن التراجع عنه، وكل تصفير يُسجَّل."}));
    rows.forEach(function(row){ card.appendChild(row); });
    card.appendChild(h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn danger", text:"تصفير الأجزاء المختارة", onclick:async function(){
      var when = opts.period();
      if(!when.month){ setMsg(msg, "اختر شهراً محدداً أولاً.", "err"); return; }
      var scopes = Object.keys(boxes).filter(function(key){ return boxes[key].checked; });
      if(!scopes.length){ setMsg(msg, "اختر جزءاً واحداً على الأقل.", "err"); return; }
      var names = opts.scopes.filter(function(scope){ return scopes.indexOf(scope[0]) !== -1; }).map(function(scope){ return scope[1]; }).join("، ");
      if(!window.confirm("سيُمسح من " + MONTHS_AR[when.month - 1] + " " + when.year + ": " + names + ". لا يمكن التراجع. هل تريد المتابعة؟")) return;
      var word = window.prompt("للتأكيد اكتب الكلمة RESET بالأحرف الكبيرة:");
      if(word === null) return;
      try{
        var done = await request("/api/admin/accounting/reset-part", {method:"POST", body:JSON.stringify({year:when.year, month:when.month, scopes:scopes, confirm:word})});
        var text = "تم التصفير: " + done.entries + " سطر جدول، " + done.salaries + " سطر راتب، " + done.fees + " رسم، " + done.payments + " دفعة، " + done.receipts + " إيصال.";
        setMsg(msg, text, "ok"); accToast(text, "ok");
        if(typeof ACC_REFRESH === "function") ACC_REFRESH();
        if(opts.onDone) opts.onDone();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    }})]));
    card.appendChild(msg);
    card.hidden = false;
  }
  var ready = ACC_VIEWER && ACC_VIEWER.role ? Promise.resolve(ACC_VIEWER) : request("/api/admin/fees/me").then(function(me){ ACC_VIEWER = me; return me; });
  ready.then(function(me){ if(me && me.role === "admin") show(); }, function(){});
  return card;
}

/* ------------------------------------------------------------------ the people are the work of the management */
function accManagementNote(text){
  var isAdmin = ACC_VIEWER && ACC_VIEWER.role === "admin";
  var children = [h("p", {class:"hint", text:text})];
  if(isAdmin) children.push(h("div", {class:"a-row"}, [h("a", {class:"a-btn ghost", href:"../management/", style:"text-decoration:none", text:"فتح بوابة الإدارة"})]));
  return h("div", {class:"a-card a-hintcard"}, children);
}

/* ------------------------------------------------------------------ step 2: staff (read only) and the salaries they are owed */
function staffStep(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var yearInput = h("input", {type:"number", min:"2000", max:"2100", value:String(ACC_PERIOD.year)});
  var monthSel = accSelect(accMonths(false), String(ACC_PERIOD.month));
  var card = h("div", {class:"a-card"}, [h("h3", {text:"الرواتب المستحقة للشهر"}),
    h("p", {class:"hint", text:"بعد أن تسجّل الإدارة الموظفين ورواتبهم الأساسية أنشئ سطر راتب لكل موظف لهذا الشهر دفعة واحدة. يُسجَّل الدفع الفعلي في خطوة «دفع الرواتب»."}),
    h("div", {class:"a-form-grid"}, [accField("الشهر", monthSel), accField("السنة", yearInput)]),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"إنشاء رواتب الشهر لكل الموظفين", onclick:async function(){
      try{
        var created = await accFillSavedSalaries(yearInput.value, monthSel.value, ACC_CURRENCIES, msg);
        if(!created) setMsg(msg, "لا توجد رواتب جديدة لإنشائها: كل موظف لديه سطر لهذا الشهر، أو لم تُحفظ رواتب أساسية بعد.", "ok");
        ACC_REFRESH();
      }catch(error){ setMsg(msg, errText(error), "err"); }
    }})]), msg]);
  var list = h("div", {});
  var staffCard = h("div", {class:"a-card"}, [h("h3", {text:"الموظفون المسجَّلون"}), list]);
  request("/api/admin/accounting/employees").then(function(rows){
    if(!rows.length){ list.appendChild(h("div", {class:"a-empty", text:"لا يوجد موظفون مسجَّلون بعد. تضيفهم الإدارة."})); return; }
    list.appendChild(h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [
      h("thead", {}, [h("tr", {}, ["الاسم", "المسمى الوظيفي", "الراتب المعتاد", "حساب الدخول"].map(function(t){ return h("th", {text:t}); }))]),
      h("tbody", {}, rows.map(function(e){
        return h("tr", {}, [h("td", {class:"name", dir:"auto", text:e.name}), h("td", {dir:"auto", text:e.job_title || "—"}),
          h("td", {class:"num", dir:"ltr", text:e.salary ? money(e.salary) + " " + (e.salary_currency || "") : "—"}), h("td", {text:e.account_username || "—"})]);
      }))]))]));
  }).catch(function(error){ setMsg(msg, errText(error), "err"); });
  return h("section", {}, [accManagementNote("إضافة الموظفين وتعديل بياناتهم ورواتبهم الأساسية وحذفهم من مهام الإدارة، وليست من مهام المحاسبة. هنا تختار من المسجَّلين فقط."), card, staffCard]);
}

/* ------------------------------------------------------------------ step 3: the fees of the children (the children are added by the management) */
function feesStep(){
  return h("section", {}, [accManagementNote("إضافة الأطفال وأولياء أمورهم وتعديلهم من مهام الإدارة. هنا تحدّد الاشتراكات وتسجّل الدفعات للأطفال المسجَّلين فقط."), tabFees()]);
}

/* ------------------------------------------------------------------ sub tabs inside a step */
function accSubTabs(id, defs){
  var panel = h("div", {});
  var nav = h("div", {class:"a-subnav", role:"tablist"});
  var current = ACC_SUBSEL[id] || defs[0][0];
  function draw(){
    nav.innerHTML = "";
    defs.forEach(function(def){
      nav.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(current === def[0]), text:def[1], onclick:function(){ current = ACC_SUBSEL[id] = def[0]; draw(); }}));
    });
    panel.innerHTML = "";
    var shown = defs.filter(function(def){ return def[0] === current; })[0] || defs[0];
    var content = shown[2]();
    (Array.isArray(content) ? content : [content]).forEach(function(node){ panel.appendChild(node); });
  }
  draw();
  return h("section", {}, [nav, panel]);
}

/* ------------------------------------------------------------------ step 4: income (the payments of the parents come from step 3) */
function incomeStep(){
  var note = h("div", {class:"a-card a-hintcard"}, [
    h("p", {class:"hint", text:"دفعات أولياء الأمور تُسجَّل في خطوة «اشتراكات الأطفال» وتظهر هنا تلقائياً في بند الاشتراكات. سجّل هنا الإيرادات الأخرى (بوفيه، نقل، تبرعات...)."}),
    h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn ghost", text:"تسجيل دفعة من ولي أمر", onclick:function(){ ACC_GO("fees"); }})])]);
  return h("section", {}, [note, tabSheet("day", {focus:"income"})]);
}

/* ------------------------------------------------------------------ step 9: reports (weekly check, yearly table) */
function weekCheckCard(){
  var day = h("input", {type:"date", value:localToday()});
  var body = h("div", {});
  var card = h("div", {class:"a-card"}, [h("h3", {text:"مراجعة الأسبوع"}), h("p", {class:"hint", text:"نظرة سريعة على الأسبوع دون إغلاقه: الوارد والصادر والدفعات والإيصالات الناقصة وجرد الصندوق. الإغلاق الملزم يتم شهرياً فقط."}), accField("أي يوم من الأسبوع", day), body]);
  async function load(){
    body.innerHTML = "";
    try{
      var data = await request("/api/admin/accounting/week-check?week_start=" + encodeURIComponent(day.value));
      body.appendChild(h("p", {class:"hint", dir:"ltr", text:data.week_start + " → " + data.week_end}));
      var kpis = h("div", {class:"a-kpis"});
      ACC_CURRENCIES.forEach(function(code){
        var t = data.totals[code];
        kpis.appendChild(h("div", {class:"a-kpi"}, [h("span", {text:"الوارد " + code}), h("strong", {text:money(t.income)})]));
        kpis.appendChild(h("div", {class:"a-kpi"}, [h("span", {text:"الصادر " + code}), h("strong", {text:money(t.expense)})]));
        if(data.payments[code].count) kpis.appendChild(h("div", {class:"a-kpi good"}, [h("span", {text:"دفعات الأهل " + code + " (" + data.payments[code].count + ")"}), h("strong", {text:money(data.payments[code].amount)})]));
      });
      body.appendChild(kpis);
      var LABEL = {entries: ["سُجّلت حركات هذا الأسبوع", "لم تُسجَّل أي حركة هذا الأسبوع"], missing_receipts: ["كل المصروفات لها إيصال", "مصروفات بلا إيصال"], cash_count: ["أُجري جرد للصندوق", "لم يُجرَ جرد للصندوق"], cash_difference: ["لا فرق في الجرد", "يوجد فرق في الجرد"]};
      data.checks.forEach(function(check){
        var text = LABEL[check.kind][check.ok ? 0 : 1] + (!check.ok && check.count && check.kind !== "entries" ? " (" + check.count + ")" : "");
        body.appendChild(h("p", {class:"a-msg " + (check.ok ? "ok" : "warn"), text:(check.ok ? "✓ " : "⚠ ") + text}));
      });
    }catch(error){ body.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  day.addEventListener("change", load);
  load();
  return card;
}
function tabYear(){
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(ACC_PERIOD.year)});
  var body = h("div", {});
  async function load(){
    body.innerHTML = "";
    try{
      var data = await request("/api/admin/accounting/overview?year=" + encodeURIComponent(year.value));
      ACC_CURRENCIES.forEach(function(code){
        var income = 0n, expense = 0n;
        var rows = data[code].series.map(function(s){
          income += accCents(s.income); expense += accCents(s.expense);
          var net = accCents(s.income) - accCents(s.expense);
          return h("tr", {}, [h("td", {class:"name", text:MONTHS_AR[s.month - 1]}), h("td", {class:"num", text:money(s.income)}), h("td", {class:"num", text:money(s.expense)}), h("td", {class:"num strong" + (net < 0n ? " due" : ""), text:money(String(net / 100n) + "." + String((net < 0n ? -net : net) % 100n).padStart(2, "0"))})]);
        });
        var total = income - expense;
        rows.push(h("tr", {class:"a-total"}, [h("td", {class:"name", text:"المجموع"}), h("td", {class:"num strong", text:money(String(income / 100n) + "." + String(income % 100n).padStart(2, "0"))}), h("td", {class:"num strong", text:money(String(expense / 100n) + "." + String(expense % 100n).padStart(2, "0"))}),
          h("td", {class:"num strong" + (total < 0n ? " due" : ""), text:money(String(total / 100n) + "." + String((total < 0n ? -total : total) % 100n).padStart(2, "0"))})]));
        body.appendChild(h("div", {class:"a-card"}, [h("h3", {text:"بـ" + ACC_CURRENCY_NAME[code]}),
          h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [h("thead", {}, [h("tr", {}, ["الشهر", "الوارد", "الصادر", "الصافي"].map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)]))])]));
      });
    }catch(error){ body.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  year.addEventListener("change", load);
  load();
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"التقرير السنوي"}), h("p", {class:"hint", text:"واردات ومصروفات كل شهر في السنة، لكل عملة على حدة. الأرقام من الجدول الشهري."}), accField("السنة", year)]), body]);
}

/* ------------------------------------------------------------------ step 11: export and archive */
function tabArchive(){
  var now = new Date();
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(ACC_PERIOD.year)});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var body = h("div", {});
  var logBox = h("div", {});
  function archiveName(y, m){ return "accounting-" + y + "-" + String(m).padStart(2, "0") + ".xlsx"; }
  async function load(){
    body.innerHTML = ""; logBox.innerHTML = "";
    try{
      var locks = (await request("/api/admin/accounting/periods?year=" + encodeURIComponent(year.value))).locks;
      var audit = await request("/api/admin/fees/audit?limit=500");
      var exported = {};
      audit.filter(function(row){ return row.action === "export.month"; }).forEach(function(row){ if(!exported[row.entity_id]) exported[row.entity_id] = row; });
      var byMonth = {};
      locks.forEach(function(lock){ byMonth[lock.month] = lock; });
      var rows = [];
      for(var m = 1; m <= 12; m++){
        (function(m){
          var lock = byMonth[m], ended = new Date(Number(year.value), m, 1) <= now, last = exported[m + "/" + year.value];
          var snap = lock && lock.snapshot ? ACC_CURRENCIES.map(function(code){ return lock.snapshot[code] ? code + ": +" + money(lock.snapshot[code].income) + " / −" + money(lock.snapshot[code].expense) : ""; }).filter(Boolean).join("  ·  ") : "";
          rows.push(h("tr", {}, [
            h("td", {class:"name", text:MONTHS_AR[m - 1]}),
            h("td", {}, [h("span", {class:"a-badge " + (lock ? "paid" : ended ? "partial" : "open"), text:lock ? "مغلق" : ended ? "مفتوح" : "لم ينتهِ بعد"}), lock ? h("small", {class:"hint", text:" " + lock.closed_by + " · " + String(lock.closed_at).slice(0, 10)}) : ""]),
            h("td", {dir:"ltr", text:snap || "—"}),
            h("td", {text:last ? String(last.at).slice(0, 10) + " · " + last.actor : "—"}),
            h("td", {}, [h("button", {type:"button", class:lock ? "a-btn sun" : "a-btn ghost", text:lock ? "ملف الشهر (Excel)" : "نسخة مؤقتة", onclick:function(){
              downloadFile("/api/admin/accounting/periods/" + encodeURIComponent(year.value) + "/" + m + "/export.xlsx", archiveName(year.value, m)).then(function(){ setMsg(msg, "تم تنزيل الملف وتسجيل التصدير.", "ok"); ACC_REFRESH(); load(); }).catch(function(error){ setMsg(msg, errText(error), "err"); });
            }})])]));
        })(m);
      }
      body.appendChild(h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact"}, [
        h("thead", {}, [h("tr", {}, ["الشهر", "الحالة", "الأرقام عند الإغلاق", "آخر تصدير", ""].map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)]))]));
      var recent = audit.filter(function(row){ return row.action === "export.month"; }).slice(0, 10);
      logBox.appendChild(h("h4", {text:"سجل التصدير"}));
      logBox.appendChild(recent.length ? h("ul", {class:"a-issues"}, recent.map(function(row){ return h("li", {text:row.entity_id + " — " + row.actor + " — " + String(row.at).replace("T", " ").slice(0, 16)}); })) : h("p", {class:"hint", text:"لم يُصدَّر أي شهر بعد."}));
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  year.addEventListener("change", load);

  /* quick exports of one list (fees or salaries) for any month */
  var month = accSelect([["0", "كل الأشهر"]].concat(accMonths(false)), String(now.getMonth() + 1));
  var currency = accSelect([["", "كل العملات"]].concat(ACC_CURRENCIES.map(function(c){ return [c, c]; })), "");
  function quick(label, path, name){
    return h("button", {type:"button", class:"a-btn ghost", text:label, onclick:function(){
      var query = "year=" + encodeURIComponent(year.value) + (month.value !== "0" ? "&month=" + month.value : "") + (currency.value ? "&currency=" + currency.value : "");
      downloadFile(path + "?" + query, name + "-" + year.value + (month.value !== "0" ? "-" + month.value : "") + ".xlsx").catch(function(error){ setMsg(msg, errText(error), "err"); });
    }});
  }
  var quickCard = h("div", {class:"a-card"}, [h("h3", {text:"تصدير سريع إلى Excel"}),
    h("p", {class:"hint", text:"قائمة واحدة لأي شهر أو لكل السنة: الاشتراكات أو الرواتب أو سجل العمليات."}),
    h("div", {class:"a-form-grid"}, [accField("الشهر", month), accField("العملة", currency)]),
    h("div", {class:"a-row"}, [quick("اشتراكات الأطفال", "/api/admin/fees/export.xlsx", "fees"), quick("الرواتب", "/api/admin/accounting/salaries/export.xlsx", "salaries"),
      h("button", {type:"button", class:"a-btn ghost", text:"سجل العمليات", onclick:function(){ downloadFile("/api/admin/fees/audit.xlsx", "system-log.xlsx").catch(function(error){ setMsg(msg, errText(error), "err"); }); }})])]);
  load();
  fill = null;
  return h("section", {}, [h("div", {class:"a-card"}, [h("h3", {text:"أرشيف الأشهر"}),
    h("p", {class:"hint", text:"لكل شهر ملف Excel كامل: الملخص والاشتراكات والرواتب والحركات مع عدد الإيصالات وجرد الصندوق. كل تصدير يُسجَّل باسم من أجراه وتاريخه. أفضل وقت للتصدير بعد إغلاق الشهر."}),
    accField("السنة", year), msg, body, logBox]), quickCard]);
}

/* ------------------------------------------------------------------ receipts of one row of a sheet */
function accReceiptPanel(entryId, saveNumber, receiptNo, locked, onChange){
  var panel = h("div", {class:"a-receipt-panel"});
  var list = h("div", {});
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var number = h("input", {type:"text", maxlength:"60", value:receiptNo || "", placeholder:"رقم الإيصال الورقي", dir:"ltr", "aria-label":"رقم الإيصال"});
  var file = h("input", {type:"file", accept:".pdf,.jpg,.jpeg,.png,.webp,application/pdf,image/*", "aria-label":"ملف الإيصال"});
  function size(bytes){ return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.ceil(bytes / 1024)) + " KB"; }
  async function load(){
    list.innerHTML = "";
    try{
      var items = await request("/api/admin/accounting/entries/" + encodeURIComponent(entryId) + "/receipts");
      if(!items.length) list.appendChild(h("p", {class:"hint", text:"لا توجد ملفات إيصال لهذا السطر."}));
      items.forEach(function(item){
        var actions = [h("button", {type:"button", class:"a-btn ghost", text:"تنزيل", onclick:function(){ downloadFile("/api/admin/accounting/receipts/" + encodeURIComponent(item.id) + "/download", item.name).catch(function(error){ setMsg(msg, errText(error), "err"); }); }})];
        if(!locked) actions.push(twoStep("حذف", async function(){ await request("/api/admin/accounting/receipts/" + encodeURIComponent(item.id), {method:"DELETE"}); await load(); onChange(); }));
        list.appendChild(h("div", {class:"a-receipt"}, [h("span", {dir:"auto", text:item.name + " (" + size(item.size) + ")"}), h("div", {class:"a-row"}, actions)]));
      });
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  var controls = [];
  if(!locked){
    controls.push(h("div", {class:"a-row"}, [number, h("button", {type:"button", class:"a-btn ghost", text:"حفظ الرقم", onclick:async function(){
      try{ await saveNumber(number.value.trim()); setMsg(msg, "تم حفظ رقم الإيصال.", "ok"); onChange(); }catch(error){ setMsg(msg, errText(error), "err"); }
    }})]));
    controls.push(h("div", {class:"a-row"}, [file, h("button", {type:"button", class:"a-btn sun", text:"رفع الإيصال", onclick:async function(){
      if(!file.files.length){ setMsg(msg, "اختر ملف الإيصال أولاً (PDF أو صورة حتى 3 ميغابايت).", "err"); return; }
      var data = new FormData();
      data.append("file", file.files[0]);
      try{ await request("/api/admin/accounting/entries/" + encodeURIComponent(entryId) + "/receipts", {method:"POST", body:data}); file.value = ""; setMsg(msg, "تم رفع الإيصال.", "ok"); await load(); onChange(); }
      catch(error){ setMsg(msg, errText(error), "err"); }
    }})]));
  }
  panel.appendChild(h("strong", {text:"إيصالات هذا السطر"}));
  panel.appendChild(h("small", {class:"hint", text:"يكفي رقم الإيصال أو ملف مرفوع ليُعدّ المصروف موثّقاً. الملفات: PDF أو صورة، حتى 3 ميغابايت، وبحد أقصى 5 لكل سطر."}));
  panel.appendChild(list);
  controls.forEach(function(node){ panel.appendChild(node); });
  panel.appendChild(msg);
  load();
  return panel;
}

/* ------------------------------------------------------------------ the shell */
function tabAccounting(){
  var panel = h("div", {});
  var stepper = h("div", {class:"a-steps", role:"tablist", "aria-label":"خطوات المحاسبة"});
  var year = h("input", {type:"number", min:"2000", max:"2100", value:String(ACC_PERIOD.year), "aria-label":"السنة"});
  var monthSel = accSelect(accMonths(false), String(ACC_PERIOD.month));
  monthSel.setAttribute("aria-label", "الشهر");
  var banner = h("div", {});

  function pill(key, number){
    var step = key === "dashboard" ? null : accStepOf(key);
    var status = step ? step.status : "none";
    var mark = key === "dashboard" ? "☰" : status === "done" ? "✓" : String(number);
    var b = h("button", {type:"button", role:"tab", "aria-selected":String(ACC_STEP === key), class:"a-step s-" + status + (step && step.issues.length ? " has-issue" : "") + (ACC_FLOW && ACC_FLOW.next === key ? " is-next" : ""),
      title:(ACC_STEP_TEXT[key][0]) + (step ? " — " + ACC_STATUS_TEXT[step.status] : ""), onclick:function(){ ACC_GO(key); }}, [h("span", {class:"a-step-n", text:mark}), h("span", {class:"a-step-t", text:ACC_STEP_TEXT[key][0]})]);
    if(step && step.issues.length) b.appendChild(h("span", {class:"a-step-dot", "aria-hidden":"true"}));
    return b;
  }
  function drawStepper(){
    stepper.innerHTML = "";
    stepper.appendChild(pill("dashboard", 0));
    ACC_ORDER.forEach(function(key, index){ stepper.appendChild(pill(key, index + 1)); });
    var selected = stepper.querySelector('[aria-selected="true"]');
    if(selected && selected.scrollIntoView) selected.scrollIntoView({inline:"center", block:"nearest"});
    banner.innerHTML = "";
    if(ACC_FLOW && ACC_STEP !== "dashboard" && ACC_FLOW.next && ACC_FLOW.next !== ACC_STEP){
      var next = ACC_FLOW.next, current = accStepOf(ACC_STEP);
      var open = current && current.status !== "done" ? "الخطوة الحالية: " + ACC_STEP_TEXT[ACC_STEP][0] + " (" + ACC_STATUS_TEXT[current.status] + ")" : "";
      banner.appendChild(h("div", {class:"a-nextbar"}, [h("span", {text:(open ? open + " · " : "") + "التالي في الترتيب: "}), h("button", {type:"button", class:"a-btn ghost", text:ACC_STEP_TEXT[next][0], onclick:function(){ ACC_GO(next); }})]));
    }
  }
  ACC_REFRESH = function(){
    return request("/api/admin/accounting/workflow?" + accPeriodQuery()).then(function(data){ ACC_FLOW = data; drawStepper(); return data; }, function(){ ACC_FLOW = null; drawStepper(); return null; });
  };
  function drawPanel(){
    panel.innerHTML = "";
    var content;
    switch(ACC_STEP){
      case "basics": content = tabBasics(); break;
      case "staff": content = staffStep(); break;
      case "fees": content = feesStep(); break;
      case "income": content = incomeStep(); break;
      case "expenses": content = tabSheet("day", {focus:"expense"}); break;
      case "payroll": content = tabSalaries(); break;
      case "reconcile": content = tabOverview({mode:"reconcile"}); break;
      case "summary": content = tabOverview({mode:"summary"}); break;
      case "reports": content = accSubTabs("reports", [["day", "اليومي", function(){ return tabSheet("day", {readOnly:true}); }],
        ["week", "الأسبوعي", function(){ return [weekCheckCard(), tabSheet("week", {readOnly:true})]; }], ["month", "الشهري", function(){ return tabSheet("month", {readOnly:true}); }], ["year", "السنوي", tabYear]]); break;
      case "close": content = tabOverview({mode:"close"}); break;
      case "archive": content = tabArchive(); break;
      default: content = tabDashboard();
    }
    panel.appendChild(content);
  }
  ACC_GO = function(key){
    if(typeof window.accSheetDirtyCount === "function" && window.accSheetDirtyCount()){
      if(!window.confirm(accEnglish() ? "You have changes in the sheet that are not saved. Leave and lose them?" : "لديك تعديلات في الجدول لم تُحفظ بعد. هل تريد المغادرة وفقدانها؟")) return;
      window.accSheetDirtyCount = null;
    }
    ACC_STEP = ACC_STEP_TEXT[key] ? key : "dashboard";
    drawStepper(); drawPanel();
    window.scrollTo(0, 0);
    ACC_REFRESH().then(function(){ if(ACC_STEP === "dashboard") drawPanel(); });
  };
  function period(){
    ACC_PERIOD = {year:Number(year.value) || ACC_PERIOD.year, month:Number(monthSel.value)};
    ACC_REFRESH().then(function(){ if(ACC_STEP === "dashboard") drawPanel(); });
  }
  year.addEventListener("change", period); monthSel.addEventListener("change", period);
  var refresh = h("button", {type:"button", class:"a-btn ghost", text:"تحديث الحالة", onclick:function(){ ACC_REFRESH().then(function(){ if(ACC_STEP === "dashboard") drawPanel(); }); }});
  request("/api/admin/fees/me").then(function(me){ ACC_VIEWER = me; }, function(){});
  accLoadNames();
  drawStepper(); drawPanel();
  ACC_REFRESH().then(function(){ if(ACC_STEP === "dashboard") drawPanel(); });
  fill = null;
  return h("section", {}, [
    h("div", {class:"a-card a-period"}, [h("strong", {text:"الشهر قيد العمل"}), monthSel, year, refresh]),
    stepper, banner, panel]);
}
