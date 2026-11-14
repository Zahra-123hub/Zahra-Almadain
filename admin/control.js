/* The control centre (لوحة المتابعة): what happens in the kindergarten, at a glance. Loaded after finance.js (uses its small helpers) and before admin.js.
   Read only. What the system cannot know is shown grey as "not available", never as "fine". Money is shown per currency, never added together. */

var CC_TASK_TEXT = {
  requests_pending: ["طلبات تسجيل بانتظار الموافقة", "Registration requests waiting"],
  accounts_pending: ["حسابات بانتظار الموافقة", "Accounts waiting for approval"],
  reports_in_review: ["تقارير بانتظار المراجعة", "Reports waiting for review"],
  failed_sign_ins: ["محاولات دخول فاشلة في 24 ساعة", "Failed sign-ins in 24 hours"],
  children_missing_info: ["أطفال تنقصهم معلومات", "Children with missing information"],
  expenses_without_receipt: ["مصروفات بلا إيصال", "Expenses without a receipt"]
};
var CC_PRIORITY = {high: ["مرتفعة", "High", "due"], medium: ["متوسطة", "Medium", "review"], low: ["منخفضة", "Low", "open"]};
var CC_DOMAIN = {all: ["كل المجالات", "All areas"], security: ["الأمان", "Security"], account: ["الحسابات", "Accounts"], finance: ["المال", "Money"], report: ["التقارير", "Reports"], content: ["المحتوى", "Content"], system: ["النظام", "System"]};
var CC_MISSING = {birth_date: ["تاريخ الميلاد", "birth date"], group: ["المجموعة", "group"], guardian: ["ولي الأمر", "guardian"]};

function ccKpi(label, value, note, kind){
  return h("div", {class:"a-kpi" + (kind ? " " + kind : "")}, [h("small", {text:label}), h("strong", {text:String(value)}), note ? h("small", {class:"hint", text:note}) : ""]);
}
function ccTime(iso){ return iso ? accWhen(iso) : "—"; }

function ccOverview(box){
  return request("/api/admin/control/overview").then(function(d){
    var p = d.people;
    box.appendChild(h("div", {class:"a-card"}, [
      h("h3", {text:cbText(["نظرة عامة", "Overview"]) + " · " + d.today}),
      h("div", {class:"a-kpis"}, [
        ccKpi(cbText(["أطفال نشطون", "Active children"]), p.children_active, p.children_new_30d + " " + cbText(["جدد في 30 يوماً", "new in 30 days"]) + " · " + p.children_left_30d + " " + cbText(["غادروا", "left"])),
        ccKpi(cbText(["موظفون نشطون", "Active staff"]), p.employees_active, p.teachers + " " + cbText(["معلمات", "teachers"])),
        ccKpi(cbText(["حسابات أولياء الأمور", "Parent accounts"]), p.parents),
        ccKpi(cbText(["بانتظار الموافقة", "Waiting for approval"]), p.accounts_pending + p.requests_pending, p.requests_pending + " " + cbText(["طلبات", "requests"]) + " · " + p.accounts_pending + " " + cbText(["حسابات", "accounts"]), p.accounts_pending + p.requests_pending ? "due" : ""),
        ccKpi(cbText(["تقارير للمراجعة", "Reports to review"]), p.reports_in_review, "", p.reports_in_review ? "due" : "")
      ])
    ]));
    var tasks = d.tasks.map(function(t){
      var pr = CC_PRIORITY[t.priority] || CC_PRIORITY.low;
      return h("tr", {}, [h("td", {}, [cbBadge(cbText(pr), pr[2])]), h("td", {text:cbText(CC_TASK_TEXT[t.kind] || [t.kind, t.kind])}), h("td", {class:"num", text:String(t.count)})]);
    });
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["يحتاج انتباهك", "Needs your attention"])}),
      cbTable([cbText(["الأولوية", "Priority"]), cbText(["المهمة", "Task"]), cbText(["العدد", "Count"])], tasks, cbText(["لا توجد مهام مفتوحة", "No open tasks"]))]));
    if(d.finance) box.appendChild(ccFinance(d.finance));
    else box.appendChild(h("div", {class:"a-card"}, [h("p", {class:"hint", text:cbText(["الأرقام المالية غير مفعّلة لحسابك. يمنحها المدير لكل حساب على حدة.", "Money figures are not enabled for your account. The administrator grants them per account."])})]));
    box.appendChild(ccSystemShort(d.system));
  });
}
function ccFinance(f){
  var kids = [h("h3", {text:cbText(["المال، لكل عملة على حدة", "Money, each currency apart"])}),
    h("p", {class:"hint", text:cbText(["المصدر: ", "Source: "]) + (f.source === "cash_book" ? cbText(["دفتر الصندوق", "cash book"]) : cbText(["الجداول القديمة (دفتر الصندوق غير مفعّل بعد)", "old sheets (the cash book is not switched on yet)"])) + " · " + cbText(["بلا تحويل بين العملات", "no conversion between currencies"])})];
  CB_CURRENCIES.forEach(function(code){
    var c = f.currencies[code];
    kids.push(h("h4", {text:ACC_CURRENCY_NAME[code]}));
    kids.push(h("div", {class:"a-kpis"}, [
      h("div", {class:"a-kpi good"}, [h("small", {text:cbText(["الرصيد", "Balance"])}), h("strong", {text:cbMoney(c.balance)})]),
      ccKpi(cbText(["إجمالي الإيرادات", "Total income"]), cbMoney(c.total_income)),
      ccKpi(cbText(["إجمالي المصروفات", "Total expenses"]), cbMoney(c.total_expense)),
      ccKpi(cbText(["دفعات هذا الشهر", "Payments this month"]), cbMoney(c.payments_this_month)),
      ccKpi(cbText(["رسوم مفتوحة", "Open fees"]), cbMoney(c.open_fees.amount), c.open_fees.children + " " + cbText(["أطفال", "children"]), Number(c.open_fees.amount) > 0 ? "due" : "")
    ]));
  });
  kids.push(h("p", {class:"hint", text:cbText(["حركات ملغاة في آخر 30 يوماً: ", "Cancelled lines in the last 30 days: "]) + f.cancelled_last_30_days}));
  return h("div", {class:"a-card"}, kids);
}
function ccSystemShort(s){
  return h("div", {class:"a-card"}, [h("h3", {text:cbText(["النظام", "System"])}),
    h("p", {text:cbText(["آخر فحص ناجح: ", "Last successful check: "]) + ccTime(s.last_success_at) + " · " + cbText(["دخول فاشل (24 ساعة): ", "Failed sign-ins (24 h): "]) + s.failed_sign_ins_24h}),
    h("p", {class:"hint", text:cbText(["التفاصيل في تبويب «النظام».", "Details are in the “System” tab."])})]);
}

function ccTeachers(box){
  var day = h("input", {type:"date", value:localToday()});
  var body = h("div", {});
  function load(){
    body.innerHTML = "";
    request("/api/admin/control/teachers/activity?day=" + day.value).then(function(d){
      body.appendChild(cbTable([cbText(["المعلمة", "Teacher"]), cbText(["آخر ظهور", "Last seen"]), cbText(["تقارير أُنشئت", "Reports made"]), cbText(["تقارير عُدّلت", "Reports changed"]), cbText(["مسودات", "Drafts"]), cbText(["بانتظار المراجعة", "In review"]), cbText(["أُعيدت", "Returned"]), cbText(["منشورات", "Posts"]), cbText(["ملفات", "Files"])],
        d.teachers.map(function(t){
          return h("tr", {}, [h("td", {class:"name", text:t.name}), h("td", {dir:"ltr", text:t.last_seen ? accWhen(t.last_seen) : cbText(["لم تدخل بعد", "never"])}),
            h("td", {class:"num", text:String(t.reports_created)}), h("td", {class:"num", text:String(t.reports_changed)}), h("td", {class:"num", text:String(t.drafts_open)}),
            h("td", {class:"num", text:String(t.reports_submitted_open)}), h("td", {class:"num", text:String(t.returned_open)}), h("td", {class:"num", text:String(t.posts)}), h("td", {class:"num", text:String(t.files_uploaded)})]);
        }), cbText(["لا توجد معلمات", "No teachers"])));
      body.prepend(h("p", {class:"hint", text:cbText(["معلمات نشطات في هذا اليوم: ", "Teachers active that day: "]) + d.active}));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  day.addEventListener("change", load); load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["نشاط المعلمات", "Teacher activity"])}), accField(cbText(["اليوم", "Day"]), day), body]));
}

function ccChildren(box){
  request("/api/admin/control/children").then(function(d){
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["الأطفال", "Children"])}),
      h("div", {class:"a-kpis"}, [ccKpi(cbText(["نشطون", "Active"]), d.active), ccKpi(cbText(["جدد (30 يوماً)", "New (30 days)"]), d.new_last_30_days.length), ccKpi(cbText(["غادروا (30 يوماً)", "Left (30 days)"]), d.left_last_30_days.length),
        ccKpi(cbText(["بلا تقرير منشور (30 يوماً)", "No published report (30 days)"]), d.without_published_report_30d)]),
      h("h4", {text:cbText(["المجموعات", "Groups"])}),
      cbTable([cbText(["المجموعة", "Group"]), cbText(["الأطفال", "Children"])], d.groups.map(function(g){ return h("tr", {}, [h("td", {text:g.name || cbText(["بلا مجموعة", "no group"])}), h("td", {class:"num", text:String(g.children)})]); }), cbText(["لا توجد مجموعات", "No groups"])),
      h("h4", {text:cbText(["معلومات ناقصة", "Missing information"])}),
      cbTable([cbText(["الطفل", "Child"]), cbText(["ينقصه", "Missing"])], d.missing_information.map(function(c){ return h("tr", {}, [h("td", {class:"name", text:c.name}), h("td", {text:c.missing.map(function(m){ return cbText(CC_MISSING[m] || [m, m]); }).join("، ")})]); }), cbText(["كل البيانات مكتملة", "Everything is complete"])),
      h("p", {class:"hint", text:cbText(["لا يوجد ربط بين الأطفال والمعلمات: كل معلمة ترى كل الأطفال.", "There is no assignment of children to teachers: every teacher sees every child."])})]));
  }).catch(function(e){ accToast(errText(e), "err"); });
}

function ccSystem(box){
  request("/api/admin/control/system").then(function(s){
    function line(label, ok, text){
      var colour = ok === true ? "#1E7A45" : ok === false ? "#B3402F" : "#B8C2CE";
      return h("div", {style:"display:flex;align-items:center;gap:8px;margin:6px 0"}, [h("span", {style:"width:10px;height:10px;border-radius:50%;background:" + colour, "aria-hidden":"true"}), h("span", {text:label + (text ? ": " + text : "")})]);
    }
    box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["حالة النظام", "System status"])}),
      line(cbText(["الخادم", "Server"]), true, cbText(["يردّ", "answering"])),
      line(cbText(["قاعدة البيانات", "Database"]), s.database.ok, s.database.ok ? s.database.milliseconds + " ms" : cbText(["لا يمكن الوصول", "not reachable"])),
      line(cbText(["إصدار قاعدة البيانات", "Database version"]), s.migrations.known ? s.migrations.ok : null, s.migrations.known ? s.migrations.current : cbText(["غير معروف", "not available"])),
      line(cbText(["آخر فحص ناجح", "Last successful check"]), s.last_success_at ? true : null, ccTime(s.last_success_at)),
      line(cbText(["النسخ الاحتياطي", "Backup"]), null, cbText(["لا توجد معلومات (لا يوجد مصدر موصول)", "no information (no source connected)"])),
      line(cbText(["دخول فاشل في 24 ساعة", "Failed sign-ins in 24 h"]), s.failed_sign_ins_24h >= 3 ? false : true, String(s.failed_sign_ins_24h)),
      h("p", {class:"hint", text:cbText(["ما لا يستطيع النظام فحصه يظهر رمادياً «غير متاح» ولا يظهر أبداً كأنه سليم.", "What the system cannot check is shown grey as “not available”, never as if it were fine."])}),
      s.recent_failures.length ? h("p", {class:"hint", text:cbText(["آخر الأعطال: ", "Latest failures: "]) + s.recent_failures.map(function(f){ return accWhen(f.at) + " " + f.details; }).join(" · ")}) : ""]));
  }).catch(function(e){ accToast(errText(e), "err"); });
}

function ccActivity(box){
  var domain = accSelect(Object.keys(CC_DOMAIN).map(function(k){ return [k, cbText(CC_DOMAIN[k])]; }), "all");
  var body = h("div", {});
  function load(){
    body.innerHTML = "";
    request("/api/admin/control/activity?limit=200&domain=" + domain.value).then(function(rows){
      body.appendChild(cbTable([cbText(["الوقت", "Time"]), cbText(["المستخدم", "User"]), cbText(["المجال", "Area"]), cbText(["الإجراء", "Action"]), cbText(["السبب", "Reason"])], rows.map(function(r){
        return h("tr", {}, [h("td", {dir:"ltr", text:r.at_local ? r.at_local.replace("T", " ").slice(0, 16) : ""}), h("td", {text:r.actor}), h("td", {text:cbText(CC_DOMAIN[r.domain] || [r.domain, r.domain])}), h("td", {dir:"ltr", text:r.action}), h("td", {dir:"auto", text:r.reason || ""})]);
      }), cbText(["لا توجد إجراءات", "No activity"])));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  domain.addEventListener("change", load); load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["الأنشطة في كل المجالات", "Activity in every area"])}), accField(cbText(["المجال", "Area"]), domain), body]));
}

function ccGrants(box){
  var user = h("input", {type:"text", maxlength:"80"}), kind = accSelect([["control.view", cbText(["لوحة المتابعة", "Control centre"])], ["finance.view", cbText(["الأرقام المالية", "Money figures"])]], "control.view");
  var list = h("div", {});
  function load(){
    list.innerHTML = "";
    request("/api/admin/control/grants").then(function(rows){
      list.appendChild(cbTable([cbText(["الحساب", "Account"]), cbText(["الصلاحية", "Permission"]), cbText(["منحها", "Granted by"]), ""], rows.map(function(g){
        return h("tr", {}, [h("td", {class:"name", text:g.username}), h("td", {text:g.grant}), h("td", {text:g.granted_by}), h("td", {}, [h("button", {type:"button", class:"a-btn danger", text:cbText(["سحب", "Remove"]), onclick:function(){
          request("/api/admin/control/grants/" + g.id, {method:"DELETE"}).then(function(){ accToast(cbText(["تم السحب.", "Removed."]), "ok"); load(); }).catch(function(e){ accToast(errText(e), "err"); });
        }})])]);
      }), cbText(["لم تُمنح صلاحيات فردية", "No individual permissions granted"])));
    }).catch(function(e){ accToast(errText(e), "err"); });
  }
  load();
  box.appendChild(h("div", {class:"a-card"}, [h("h3", {text:cbText(["صلاحيات الحسابات الفردية", "Permissions of single accounts"])}),
    h("p", {class:"hint", text:cbText(["مدير (قسم الإدارة) لا يرى لوحة المتابعة إلا إذا منحته هنا. الأرقام المالية صلاحية منفصلة.", "A manager only sees the control centre when granted here. Money figures are a separate permission."])}),
    h("div", {class:"a-row"}, [accField(cbText(["اسم المستخدم", "Username"]), user), accField(cbText(["الصلاحية", "Permission"]), kind),
      h("button", {type:"button", class:"a-btn sun", text:cbText(["منح", "Grant"]), onclick:function(){
        request("/api/admin/control/grants", {method:"POST", body:JSON.stringify({username:user.value, grant:kind.value})}).then(function(){ accToast(cbText(["تم المنح.", "Granted."]), "ok"); user.value = ""; load(); }).catch(function(e){ accToast(errText(e), "err"); });
      }})]), list]));
}

function tabControl(){
  fill = null;
  var holder = h("div", {}), sub = "overview";
  var bar = h("div", {class:"a-tabs", role:"tablist"});
  var tabs = [["overview", cbText(["نظرة عامة", "Overview"])], ["teachers", cbText(["المعلمات", "Teachers"])], ["children", cbText(["الأطفال", "Children"])], ["activity", cbText(["الأنشطة", "Activity"])], ["system", cbText(["النظام", "System"])], ["grants", cbText(["الصلاحيات", "Permissions"])]];
  function draw(){
    bar.innerHTML = "";
    tabs.forEach(function(t){ bar.appendChild(h("button", {type:"button", role:"tab", "aria-selected":String(sub === t[0]), text:t[1], onclick:function(){ sub = t[0]; draw(); }})); });
    holder.innerHTML = "";
    var box = h("div", {});
    holder.appendChild(box);
    if(sub === "teachers") ccTeachers(box); else if(sub === "children") ccChildren(box); else if(sub === "activity") ccActivity(box);
    else if(sub === "system") ccSystem(box); else if(sub === "grants") ccGrants(box); else ccOverview(box).catch(function(e){ accToast(errText(e), "err"); });
  }
  draw();
  return h("section", {}, [bar, holder]);
}
