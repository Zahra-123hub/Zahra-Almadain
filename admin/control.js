/* The control centre (لوحة المتابعة): what happens in the kindergarten, at a glance. Loaded after ui.js (uses its small helpers) and before admin.js.
   Read only. What the system cannot know is shown grey as "not available", never as "fine". Money is shown per currency, never added together. */

var CC_TASK_TEXT = {
  requests_pending: ["طلبات تسجيل بانتظار الموافقة", "Registration requests waiting"],
  accounts_pending: ["حسابات بانتظار الموافقة", "Accounts waiting for approval"],
  reports_in_review: ["تقارير بانتظار المراجعة", "Reports waiting for review"],
  failed_sign_ins: ["محاولات دخول فاشلة في 24 ساعة", "Failed sign-ins in 24 hours"],
  children_missing_info: ["أطفال تنقصهم معلومات", "Children with missing information"],
  invoices_unpaid: ["فواتير غير مسددة", "Unpaid invoices"]
};
var CC_PRIORITY = {high: ["مرتفعة", "High", "due"], medium: ["متوسطة", "Medium", "review"], low: ["منخفضة", "Low", "open"]};
var CC_DOMAIN = {all: ["كل المجالات", "All areas"], security: ["الأمان", "Security"], account: ["الحسابات", "Accounts"], finance: ["المال", "Money"], report: ["التقارير", "Reports"], content: ["المحتوى", "Content"], system: ["النظام", "System"]};
var CC_MISSING = {birth_date: ["تاريخ الميلاد", "birth date"], group: ["المجموعة", "group"], guardian: ["ولي الأمر", "guardian"]};

function ccKpi(label, value, note, kind){
  return h("div", {class:"a-kpi" + (kind ? " " + kind : "")}, [h("small", {text:label}), h("strong", {text:String(value)}), note ? h("small", {class:"hint", text:note}) : ""]);
}
function ccTime(iso){ return iso ? uiWhen(iso) : "—"; }

function ccOverview(box){
  return request("/api/admin/control/overview").then(function(d){
    var p = d.people;
    box.appendChild(h("div", {class:"a-card"}, [
      h("h3", {text:uiT(["نظرة عامة", "Overview"]) + " · " + d.today}),
      h("div", {class:"a-kpis"}, [
        ccKpi(uiT(["أطفال نشطون", "Active children"]), p.children_active, p.children_new_30d + " " + uiT(["جدد في 30 يوماً", "new in 30 days"]) + " · " + p.children_left_30d + " " + uiT(["غادروا", "left"])),
        ccKpi(uiT(["موظفون نشطون", "Active staff"]), p.employees_active, p.teachers + " " + uiT(["معلمات", "teachers"])),
        ccKpi(uiT(["حسابات أولياء الأمور", "Parent accounts"]), p.parents),
        ccKpi(uiT(["بانتظار الموافقة", "Waiting for approval"]), p.accounts_pending + p.requests_pending, p.requests_pending + " " + uiT(["طلبات", "requests"]) + " · " + p.accounts_pending + " " + uiT(["حسابات", "accounts"]), p.accounts_pending + p.requests_pending ? "due" : ""),
        ccKpi(uiT(["تقارير للمراجعة", "Reports to review"]), p.reports_in_review, "", p.reports_in_review ? "due" : "")
      ])
    ]));
    var tasks = d.tasks.map(function(t){
      var pr = CC_PRIORITY[t.priority] || CC_PRIORITY.low;
      return h("tr", {}, [h("td", {}, [uiBadge(uiT(pr), pr[2])]), h("td", {text:uiT(CC_TASK_TEXT[t.kind] || [t.kind, t.kind])}), h("td", {class:"num", text:String(t.count)})]);
    });
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["يحتاج انتباهك", "Needs your attention"])}),
      uiTable([uiT(["الأولوية", "Priority"]), uiT(["المهمة", "Task"]), uiT(["العدد", "Count"])], tasks, uiT(["لا توجد مهام مفتوحة", "No open tasks"]))]));
    if(d.finance) box.appendChild(ccFinance(d.finance));
    else box.appendChild(h("div", {class:"a-card"}, [h("p", {class:"hint", text:uiT(["الأرقام المالية غير مفعّلة لحسابك. يمنحها المدير لكل حساب على حدة.", "Money figures are not enabled for your account. The administrator grants them per account."])})]));
    box.appendChild(ccSystemShort(d.system));
  });
}
function ccFinance(f){
  var kids = [h("h3", {text:uiT(["المال هذا الشهر، لكل عملة على حدة", "Money this month, each currency apart"])}),
    h("p", {class:"hint", text:uiT(["المصدر: المحاسبة (المال المدفوع فعلاً بكل عملة) · بلا تحويل بين العملات", "Source: the accounting (money really paid in each currency) · no conversion between currencies"])})];
  ["USD", "SYP"].forEach(function(code){
    var c = f.currencies[code];
    kids.push(h("h4", {text:code}));
    kids.push(h("div", {class:"a-kpis"}, [
      ccKpi(uiT(["الإيرادات", "Income"]), uiNum(c.income)),
      ccKpi(uiT(["المصروفات", "Expenses"]), uiNum(c.expense)),
      h("div", {class:"a-kpi good"}, [h("small", {text:uiT(["الفائض / العجز", "Surplus / deficit"])}), h("strong", {text:uiNum(c.surplus)})]),
      ccKpi(uiT(["متبقٍّ على الفواتير", "Open on invoices"]), uiNum(c.open_invoices), "", Number(c.open_invoices) > 0 ? "due" : "")
    ]));
  });
  kids.push(h("p", {class:"hint", text:uiT(["فواتير مفتوحة / جزئية: ", "Invoices open / partly paid: "]) + f.invoices_open + " / " + f.invoices_partial + " · " +
    uiT(["إلغاءات وقيود عكسية في آخر 30 يوماً: ", "Cancellations and reversals in the last 30 days: "]) + f.cancelled_last_30_days}));
  return h("div", {class:"a-card"}, kids);
}
function ccSystemShort(s){
  return h("div", {class:"a-card"}, [h("h3", {text:uiT(["النظام", "System"])}),
    h("p", {text:uiT(["آخر فحص ناجح: ", "Last successful check: "]) + ccTime(s.last_success_at) + " · " + uiT(["دخول فاشل (24 ساعة): ", "Failed sign-ins (24 h): "]) + s.failed_sign_ins_24h}),
    h("p", {class:"hint", text:uiT(["التفاصيل في تبويب «النظام».", "Details are in the “System” tab."])})]);
}

function ccTeachers(box){
  var day = h("input", {type:"date", value:localToday()});
  var body = h("div", {});
  function load(){
    body.innerHTML = "";
    request("/api/admin/control/teachers/activity?day=" + day.value).then(function(d){
      body.appendChild(uiTable([uiT(["المعلمة", "Teacher"]), uiT(["آخر ظهور", "Last seen"]), uiT(["تقارير أُنشئت", "Reports made"]), uiT(["تقارير عُدّلت", "Reports changed"]), uiT(["مسودات", "Drafts"]), uiT(["بانتظار المراجعة", "In review"]), uiT(["أُعيدت", "Returned"]), uiT(["منشورات", "Posts"]), uiT(["ملفات", "Files"])],
        d.teachers.map(function(t){
          return h("tr", {}, [h("td", {class:"name", text:t.name}), h("td", {dir:"ltr", text:t.last_seen ? uiWhen(t.last_seen) : uiT(["لم تدخل بعد", "never"])}),
            h("td", {class:"num", text:String(t.reports_created)}), h("td", {class:"num", text:String(t.reports_changed)}), h("td", {class:"num", text:String(t.drafts_open)}),
            h("td", {class:"num", text:String(t.reports_submitted_open)}), h("td", {class:"num", text:String(t.returned_open)}), h("td", {class:"num", text:String(t.posts)}), h("td", {class:"num", text:String(t.files_uploaded)})]);
        }), uiT(["لا توجد معلمات", "No teachers"])));
      body.prepend(h("p", {class:"hint", text:uiT(["معلمات نشطات في هذا اليوم: ", "Teachers active that day: "]) + d.active}));
    }).catch(function(e){ uiToast(errText(e), "err"); });
  }
  day.addEventListener("change", load); load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["نشاط المعلمات", "Teacher activity"])}), uiField(uiT(["اليوم", "Day"]), day), body]));
}

function ccChildren(box){
  request("/api/admin/control/children").then(function(d){
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الأطفال", "Children"])}),
      h("div", {class:"a-kpis"}, [ccKpi(uiT(["نشطون", "Active"]), d.active), ccKpi(uiT(["جدد (30 يوماً)", "New (30 days)"]), d.new_last_30_days.length), ccKpi(uiT(["غادروا (30 يوماً)", "Left (30 days)"]), d.left_last_30_days.length),
        ccKpi(uiT(["بلا تقرير منشور (30 يوماً)", "No published report (30 days)"]), d.without_published_report_30d)]),
      h("h4", {text:uiT(["المجموعات", "Groups"])}),
      uiTable([uiT(["المجموعة", "Group"]), uiT(["الأطفال", "Children"])], d.groups.map(function(g){ return h("tr", {}, [h("td", {text:g.name || uiT(["بلا مجموعة", "no group"])}), h("td", {class:"num", text:String(g.children)})]); }), uiT(["لا توجد مجموعات", "No groups"])),
      h("h4", {text:uiT(["معلومات ناقصة", "Missing information"])}),
      uiTable([uiT(["الطفل", "Child"]), uiT(["ينقصه", "Missing"])], d.missing_information.map(function(c){ return h("tr", {}, [h("td", {class:"name", text:c.name}), h("td", {text:c.missing.map(function(m){ return uiT(CC_MISSING[m] || [m, m]); }).join("، ")})]); }), uiT(["كل البيانات مكتملة", "Everything is complete"])),
      h("p", {class:"hint", text:uiT(["لا يوجد ربط بين الأطفال والمعلمات: كل معلمة ترى كل الأطفال.", "There is no assignment of children to teachers: every teacher sees every child."])})]));
  }).catch(function(e){ uiToast(errText(e), "err"); });
}

function ccSystem(box){
  request("/api/admin/control/system").then(function(s){
    function line(label, ok, text){
      var colour = ok === true ? "#1E7A45" : ok === false ? "#B3402F" : "#B8C2CE";
      return h("div", {style:"display:flex;align-items:center;gap:8px;margin:6px 0"}, [h("span", {style:"width:10px;height:10px;border-radius:50%;background:" + colour, "aria-hidden":"true"}), h("span", {text:label + (text ? ": " + text : "")})]);
    }
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["حالة النظام", "System status"])}),
      line(uiT(["الخادم", "Server"]), true, uiT(["يردّ", "answering"])),
      line(uiT(["قاعدة البيانات", "Database"]), s.database.ok, s.database.ok ? s.database.milliseconds + " ms" : uiT(["لا يمكن الوصول", "not reachable"])),
      line(uiT(["إصدار قاعدة البيانات", "Database version"]), s.migrations.known ? s.migrations.ok : null, s.migrations.known ? s.migrations.current : uiT(["غير معروف", "not available"])),
      line(uiT(["آخر فحص ناجح", "Last successful check"]), s.last_success_at ? true : null, ccTime(s.last_success_at)),
      line(uiT(["النسخ الاحتياطي", "Backup"]), null, uiT(["لا توجد معلومات (لا يوجد مصدر موصول)", "no information (no source connected)"])),
      line(uiT(["دخول فاشل في 24 ساعة", "Failed sign-ins in 24 h"]), s.failed_sign_ins_24h >= 3 ? false : true, String(s.failed_sign_ins_24h)),
      h("p", {class:"hint", text:uiT(["ما لا يستطيع النظام فحصه يظهر رمادياً «غير متاح» ولا يظهر أبداً كأنه سليم.", "What the system cannot check is shown grey as “not available”, never as if it were fine."])}),
      s.recent_failures.length ? h("p", {class:"hint", text:uiT(["آخر الأعطال: ", "Latest failures: "]) + s.recent_failures.map(function(f){ return uiWhen(f.at) + " " + f.details; }).join(" · ")}) : ""]));
  }).catch(function(e){ uiToast(errText(e), "err"); });
}

function ccActivity(box){
  var domain = uiSelect(Object.keys(CC_DOMAIN).map(function(k){ return [k, uiT(CC_DOMAIN[k])]; }), "all");
  var body = h("div", {});
  function load(){
    body.innerHTML = "";
    request("/api/admin/control/activity?limit=200&domain=" + domain.value).then(function(rows){
      body.appendChild(uiTable([uiT(["الوقت", "Time"]), uiT(["المستخدم", "User"]), uiT(["المجال", "Area"]), uiT(["الإجراء", "Action"]), uiT(["السبب", "Reason"])], rows.map(function(r){
        return h("tr", {}, [h("td", {dir:"ltr", text:r.at_local ? r.at_local.replace("T", " ").slice(0, 16) : ""}), h("td", {text:r.actor}), h("td", {text:uiT(CC_DOMAIN[r.domain] || [r.domain, r.domain])}), h("td", {dir:"ltr", text:r.action}), h("td", {dir:"auto", text:r.reason || ""})]);
      }), uiT(["لا توجد إجراءات", "No activity"])));
    }).catch(function(e){ uiToast(errText(e), "err"); });
  }
  domain.addEventListener("change", load); load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["الأنشطة في كل المجالات", "Activity in every area"])}), uiField(uiT(["المجال", "Area"]), domain), body]));
}

function ccGrants(box){
  var user = h("input", {type:"text", maxlength:"80"}), kind = uiSelect([["control.view", uiT(["لوحة المتابعة", "Control centre"])], ["finance.view", uiT(["الأرقام المالية", "Money figures"])]], "control.view");
  var list = h("div", {});
  function load(){
    list.innerHTML = "";
    request("/api/admin/control/grants").then(function(rows){
      list.appendChild(uiTable([uiT(["الحساب", "Account"]), uiT(["الصلاحية", "Permission"]), uiT(["منحها", "Granted by"]), ""], rows.map(function(g){
        return h("tr", {}, [h("td", {class:"name", text:g.username}), h("td", {text:g.grant}), h("td", {text:g.granted_by}), h("td", {}, [h("button", {type:"button", class:"a-btn danger", text:uiT(["سحب", "Remove"]), onclick:function(){
          request("/api/admin/control/grants/" + g.id, {method:"DELETE"}).then(function(){ uiToast(uiT(["تم السحب.", "Removed."]), "ok"); load(); }).catch(function(e){ uiToast(errText(e), "err"); });
        }})])]);
      }), uiT(["لم تُمنح صلاحيات فردية", "No individual permissions granted"])));
    }).catch(function(e){ uiToast(errText(e), "err"); });
  }
  load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:uiT(["صلاحيات الحسابات الفردية", "Permissions of single accounts"])}),
    h("p", {class:"hint", text:uiT(["مدير (قسم الإدارة) لا يرى لوحة المتابعة إلا إذا منحته هنا. الأرقام المالية صلاحية منفصلة.", "A manager only sees the control centre when granted here. Money figures are a separate permission."])}),
    h("div", {class:"a-row"}, [uiField(uiT(["اسم المستخدم", "Username"]), user), uiField(uiT(["الصلاحية", "Permission"]), kind),
      h("button", {type:"button", class:"a-btn sun", text:uiT(["منح", "Grant"]), onclick:function(){
        request("/api/admin/control/grants", {method:"POST", body:JSON.stringify({username:user.value, grant:kind.value})}).then(function(){ uiToast(uiT(["تم المنح.", "Granted."]), "ok"); user.value = ""; load(); }).catch(function(e){ uiToast(errText(e), "err"); });
      }})]), list]));
}

function tabControl(){
  fill = null;
  var holder = h("div", {}), sub = "overview";
  var bar = h("div", {class:"a-tabs", role:"tablist"});
  var tabs = [["overview", uiT(["نظرة عامة", "Overview"])], ["teachers", uiT(["المعلمات", "Teachers"])], ["children", uiT(["الأطفال", "Children"])], ["activity", uiT(["الأنشطة", "Activity"])], ["system", uiT(["النظام", "System"])], ["grants", uiT(["الصلاحيات", "Permissions"])]];
  function draw(){
    bar.innerHTML = "";
    tabs.forEach(function(t){ bar.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(sub === t[0]), text:t[1], onclick:function(){ sub = t[0]; draw(); }})); });
    holder.innerHTML = "";
    var box = h("div", {});
    holder.appendChild(box);
    if(sub === "teachers") ccTeachers(box); else if(sub === "children") ccChildren(box); else if(sub === "activity") ccActivity(box);
    else if(sub === "system") ccSystem(box); else if(sub === "grants") ccGrants(box); else ccOverview(box).catch(function(e){ uiToast(errText(e), "err"); });
  }
  draw();
  return h("section", {}, [bar, holder]);
}
