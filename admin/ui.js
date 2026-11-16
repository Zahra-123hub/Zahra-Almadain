/* Small building blocks shared by the admin pages (control centre, accounting, system log). Loaded before the pages and admin.js;
   uses admin.js helpers (h, request, errText, uiText) only when they are called. */

function uiT(pair){ return typeof ADMIN_LANG !== "undefined" && ADMIN_LANG === "en" ? pair[1] : pair[0]; }
function uiField(label, input){ return h("label", {class:"a-field"}, [h("span", {text:label}), input]); }
function uiSelect(options, value){
  var el = h("select", {});
  options.forEach(function(o){ el.appendChild(new Option(o[1], o[0])); });
  if(value !== undefined) el.value = value;
  return el;
}
function uiBadge(text, kind){ return h("span", {class:"a-badge " + (kind || "open"), text:text}); }
function uiTable(heads, rows, empty, wide){
  if(!rows.length) return h("div", {class:"a-empty", text:empty});
  return h("div", {class:"a-table-wrap"}, [labelCells(h("table", {class:"a-table compact", style:wide ? "min-width:" + wide + "px" : ""}, [
    h("thead", {}, [h("tr", {}, heads.map(function(t){ return h("th", {text:t}); }))]), h("tbody", {}, rows)]))]);
}
/* An amount from the server (a decimal text): pounds whole, dollars with cents. Never computed with floating point here. */
function uiNum(text){
  if(text === null || text === undefined || text === "") return "—";
  var s = String(text), neg = s.charAt(0) === "-", parts = s.replace(/^[-+]/, "").split(".");
  var whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return (neg ? "-" : "") + whole + (parts[1] ? "." + parts[1] : "");
}
/* A short message at the bottom of the screen: a result must be seen even when the table is scrolled far from its top. */
function uiToast(text, kind){
  var box = document.getElementById("a-toast");
  if(!box){ box = document.createElement("div"); box.id = "a-toast"; box.setAttribute("role", "status"); box.setAttribute("aria-live", "polite"); document.body.appendChild(box); }
  box.textContent = typeof uiText === "function" ? uiText(text) : text;
  box.className = "a-toast " + (kind === "err" ? "err" : "ok") + " show";
  clearTimeout(uiToast.timer);
  uiToast.timer = setTimeout(function(){ box.classList.remove("show"); }, kind === "err" ? 7000 : 3000);
}
/* A time from the server (UTC) shown on the local clock. */
function uiWhen(iso){
  if(!iso) return "";
  var text = String(iso);
  var date = new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : text + "Z");
  if(isNaN(date.getTime())) return text.replace("T", " ").slice(0, 16);
  function two(n){ return String(n).padStart(2, "0"); }
  return date.getFullYear() + "-" + two(date.getMonth() + 1) + "-" + two(date.getDate()) + " " + two(date.getHours()) + ":" + two(date.getMinutes());
}

/* The activity log (system log tab of the administrator): every area, filter by area, user and text; Excel export. */
var UI_DOMAIN = {all: ["كل المجالات", "All areas"], finance: ["المال", "Money"], security: ["الأمان", "Security"], account: ["الحسابات والأشخاص", "Accounts and people"],
  report: ["التقارير", "Reports"], content: ["المحتوى", "Content"], system: ["النظام", "System"]};
function uiLogCard(title){
  var domain = uiSelect(Object.keys(UI_DOMAIN).map(function(k){ return [k, uiT(UI_DOMAIN[k])]; }), "all");
  var who = h("select", {}), q = h("input", {type:"search", maxlength:"60", placeholder:uiT(["بحث", "Search"])});
  var body = h("div", {});
  function query(){
    var p = ["domain=" + domain.value];
    if(who.value) p.push("actor_name=" + encodeURIComponent(who.value));
    if(q.value.trim()) p.push("q=" + encodeURIComponent(q.value.trim()));
    return p.join("&");
  }
  function load(){
    body.innerHTML = "";
    request("/api/admin/activity?limit=200&" + query()).then(function(rows){
      body.appendChild(uiTable([uiT(["الوقت", "Time"]), uiT(["المستخدم", "User"]), uiT(["المجال", "Area"]), uiT(["الإجراء", "Action"]), uiT(["السبب", "Reason"]), uiT(["تفاصيل", "Details"])],
        rows.map(function(r){
          return h("tr", {}, [h("td", {dir:"ltr", text:uiWhen(r.at)}), h("td", {text:r.actor}), h("td", {text:uiT(UI_DOMAIN[r.domain] || [r.domain, r.domain])}),
            h("td", {dir:"ltr", text:r.action}), h("td", {dir:"auto", text:r.reason || ""}), h("td", {dir:"auto", text:r.details || ""})]);
        }), uiT(["لا توجد إجراءات", "No activity"])));
    }).catch(function(e){ uiToast(errText(e), "err"); });
  }
  function actors(){
    request("/api/admin/activity/actors?domain=" + domain.value).then(function(names){
      var keep = who.value; who.innerHTML = "";
      who.appendChild(new Option(uiT(["كل المستخدمين", "Everybody"]), ""));
      names.forEach(function(n){ who.appendChild(new Option(n, n)); });
      who.value = keep;
    }).catch(function(){});
  }
  domain.addEventListener("change", function(){ actors(); load(); });
  who.addEventListener("change", load);
  q.addEventListener("change", load);
  actors(); load();
  var exportBtn = h("button", {type:"button", class:"a-btn ghost", text:uiT(["تصدير Excel", "Export Excel"]), onclick:function(){
    downloadFile("/api/admin/activity/export.xlsx?" + query(), "system-log.xlsx").catch(function(e){ uiToast(errText(e), "err"); });
  }});
  return h("div", {class:"a-card"}, [h("h3", {text:title}), h("div", {class:"a-row"}, [uiField(uiT(["المجال", "Area"]), domain), uiField(uiT(["المستخدم", "User"]), who), uiField(uiT(["بحث", "Search"]), q), exportBtn]), body]);
}

/* A month chooser with the Arabic month names (the browser's own month field shows English names). Value "2026-11". */
function uiMonthPicker(value, onChange){
  var parts = String(value).split("-"), now = new Date().getFullYear();
  var month = uiSelect(MONTHS_AR.map(function(name, i){ return [String(i + 1).padStart(2, "0"), name]; }), parts[1]);
  var years = [];
  for(var y = now + 1; y >= 2020; y--) years.push([String(y), String(y)]);
  var year = uiSelect(years, parts[0]);
  month.className = "ui-month-m"; year.className = "ui-month-y";
  var box = h("div", {class:"ui-month"}, [month, year]);
  box.value = value;
  function changed(){ box.value = year.value + "-" + month.value; if(onChange) onChange(box.value); }
  month.addEventListener("change", changed); year.addEventListener("change", changed);
  box.set = function(v){ var p = String(v).split("-"); year.value = p[0]; month.value = p[1]; box.value = v; };
  return box;
}
