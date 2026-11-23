/* Everyday life of a child, in the portals (the same server endpoints as the app):
   - parents: the page of one child with coloured tiles (child's data, notes, things to bring, week plan, attendance, messages, fees);
   - kindergarten (teachers, management, admin): attendance, notes, things to bring, week plan, messages.
   portal.js / management.js hand over their helpers (api); every call is authorised again by the server. */
(function () {
  "use strict";

  var TXT = {
    ar: {
      openChild: "صفحة الطفل", back: "رجوع", profile: "بيانات الطفل", notes: "ملاحظات", bring: "أحضِر معك", plan: "برنامج الأسبوع",
      attendance: "الحضور", messages: "دردشة", fees: "الرسوم", fullName: "الاسم الكامل", group: "المجموعة", birth: "تاريخ الميلاد",
      status: "حالة التسجيل", registered: "مسجّل", father: "الأب", mother: "الأم", guardian: "وليّ الأمر", noNotes: "لا توجد ملاحظات بعد.",
      noBring: "لا يوجد ما يلزم إحضاره.", neededOn: "مطلوب يوم", everyGroup: "كل المجموعات", noPlan: "لم يُنشر برنامج الأسبوع بعد.",
      days: ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس"], nothing: "لا شيء مخطط", today: "اليوم",
      present: "حاضر", absent: "غائب", sick: "مريض", excused: "بعذر", reportAbsence: "الإبلاغ عن غياب", day: "اليوم", note: "ملاحظة (اختياري)",
      send: "إرسال", sent: "تم الإرسال.", noDays: "لا توجد تسجيلات في هذا الشهر.", byYou: "أبلغتم عنه", month: "الشهر",
      noMessages: "لا توجد رسائل بعد. اكتب أول رسالة.", write: "اكتب رسالة...", you: "أنت", noFees: "لا توجد فواتير.", total: "المجموع",
      paid: "المدفوع", open: "المتبقي", stPaid: "مدفوعة", stPartial: "مدفوعة جزئياً", stOpen: "غير مدفوعة", payments: "الدفعات",
      // kindergarten
      staffTitle: "الحياة اليومية", allGroups: "كل المجموعات", noGroup: "بلا مجموعة", saveMarks: "حفظ الحضور", restPresent: "الباقون حاضرون",
      parentsReported: "أبلغ الأهل", saved: "تم الحفظ.", child: "الطفل", praise: "ثناء ⭐", plainNote: "ملاحظة", textLabel: "النص",
      addNote: "إرسال للأهل", what: "ماذا يُحضَر؟", details: "تفاصيل (اختياري)", forWhom: "لمن؟", groupWord: "مجموعة", childWord: "طفل",
      sendParents: "إرسال للأهل", remove: "حذف", activity: "النشاط", addActivity: "+ نشاط", savePlan: "حفظ البرنامج", planHint: "برنامج ثابت لكل مجموعة (الأحد إلى الخميس). يراه أهل أطفال المجموعة.",
      conversations: "المحادثات", newMessage: "رسالة جديدة", chooseParent: "اختر الطفل وولي الأمر", noConversations: "لا توجد محادثات بعد.",
      noChildren: "لا يوجد أطفال.", sure: "اضغط مرة أخرى للتأكيد",
      tReports: "التقارير اليومية", tPosts: "المنشورات", tMaterial: "المواد التعليمية", tReview: "مراجعة التقارير", tEveryday: "الحياة اليومية"
    },
    en: {
      openChild: "Child's page", back: "Back", profile: "Child details", notes: "Notes", bring: "Please bring", plan: "Week plan",
      attendance: "Attendance", messages: "Messages", fees: "Fees", fullName: "Full name", group: "Group", birth: "Birth date",
      status: "Registration", registered: "registered", father: "Father", mother: "Mother", guardian: "Guardian", noNotes: "No notes yet.",
      noBring: "Nothing to bring.", neededOn: "Needed on", everyGroup: "every group", noPlan: "No week plan yet.",
      days: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"], nothing: "Nothing planned", today: "Today",
      present: "present", absent: "absent", sick: "sick", excused: "excused", reportAbsence: "Report an absence", day: "Day", note: "Note (optional)",
      send: "Send", sent: "Sent.", noDays: "No entries this month.", byYou: "reported by you", month: "Month",
      noMessages: "No messages yet. Write the first one.", write: "Write a message...", you: "You", noFees: "No invoices.", total: "Total",
      paid: "Paid", open: "Open", stPaid: "paid", stPartial: "partly paid", stOpen: "unpaid", payments: "Payments",
      staffTitle: "Everyday", allGroups: "Every group", noGroup: "no group", saveMarks: "Save attendance", restPresent: "Others present",
      parentsReported: "Parents reported", saved: "Saved.", child: "Child", praise: "Praise ⭐", plainNote: "Note", textLabel: "Text",
      addNote: "Send to the parents", what: "What to bring?", details: "Details (optional)", forWhom: "For whom?", groupWord: "Group", childWord: "Child",
      sendParents: "Send to the parents", remove: "Delete", activity: "Activity", addActivity: "+ Activity", savePlan: "Save the plan", planHint: "A fixed plan per group (Sunday to Thursday). The parents of the group see it.",
      conversations: "Conversations", newMessage: "New message", chooseParent: "Choose the child and the parent", noConversations: "No conversations yet.",
      noChildren: "No children.", sure: "Click again to confirm",
      tReports: "Daily reports", tPosts: "Posts", tMaterial: "Materials", tReview: "Review reports", tEveryday: "Everyday"
    }
  };

  var STYLE = [
    ".ev-hub-head{display:flex;align-items:center;gap:14px;padding:18px;border-radius:24px;background:linear-gradient(#dcebfb,#f4f7fb);margin-bottom:16px}",
    ".ev-avatar{width:64px;height:64px;border-radius:50%;background:#fff;display:grid;place-items:center;font-size:1.6rem;font-weight:800;color:#16406f;box-shadow:0 4px 14px #16406f22}",
    ".ev-hub-head h2{margin:0}.ev-pills{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}",
    ".ev-pill{background:#eef2f6;border-radius:999px;padding:3px 10px;font-size:.85rem;font-weight:700}",
    ".ev-tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:14px}",
    ".ev-tile{position:relative;border:0;border-radius:24px;color:#fff;padding:26px 12px;cursor:pointer;font:inherit;font-weight:800;font-size:1.05rem;display:flex;flex-direction:column;align-items:center;gap:10px;box-shadow:0 8px 18px #0002}",
    ".ev-tile .ev-ico{font-size:2.4rem;line-height:1}.ev-tile .ev-badge{position:absolute;top:10px;inset-inline-end:10px;background:#fff;color:#16406f;border-radius:999px;min-width:26px;padding:2px 7px;font-size:.85rem}",
    ".ev-card{border-radius:20px;color:#fff;padding:16px;margin-bottom:12px;box-shadow:0 6px 16px #0001}",
    ".ev-card small{opacity:.85}.ev-card .ev-x{float:inline-end;background:none;border:0;color:#fff;cursor:pointer;font-size:1.1rem}",
    ".ev-green{background:linear-gradient(135deg,#8cc47a,#5fa34c)}.ev-blue{background:linear-gradient(135deg,#8eb6f2,#5c8fe0)}",
    ".ev-orange{background:linear-gradient(135deg,#f2b65a,#e5952b)}.ev-grey{background:linear-gradient(135deg,#c9ced6,#a9b0ba)}",
    ".ev-day{border:1px solid var(--line);border-radius:16px;padding:12px 14px;margin-bottom:10px;background:var(--surface)}",
    ".ev-day.today{background:#eaf1f8}.ev-day h3{margin:0 0 6px}.ev-slot{display:flex;gap:10px;align-items:flex-start;margin:6px 0}",
    ".ev-num{background:#5c8fe0;color:#fff;border-radius:9px;min-width:26px;height:26px;display:grid;place-items:center;font-weight:800}",
    ".ev-chat{display:flex;flex-direction:column;gap:8px;max-height:60vh;overflow:auto;padding:8px}",
    ".ev-msg{max-width:78%;border:1px solid #d3deeb;border-radius:16px;padding:8px 12px;background:#fff}.ev-msg.mine{align-self:flex-start;background:#dce8f7}",
    ".ev-msg:not(.mine){align-self:flex-end}.ev-msg b{font-size:.8rem;color:#16406f}.ev-msg small{display:block;opacity:.7;font-size:.75rem;direction:ltr}",
    ".ev-row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.ev-chip{border:1px solid var(--line);border-radius:999px;padding:5px 12px;background:#fff;cursor:pointer;font:inherit}",
    ".ev-chip[aria-pressed=true]{background:var(--navy);color:#fff;border-color:var(--navy)}",
    ".ev-subnav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}"
  ].join("");

  window.ZMEveryday = function (api) {
    var el = api.element, request = api.request;
    function x(key) { var table = TXT[api.lang()] || TXT.ar; return table[key] || TXT.ar[key] || key; }
    if (!document.getElementById("ev-style")) { var st = document.createElement("style"); st.id = "ev-style"; st.textContent = STYLE; document.head.appendChild(st); }

    function card(title) { var c = el("section", "p-card"); if (title) c.appendChild(el("h2", "", title)); return c; }
    function fail(container) { return function (error) { api.showError(container, error); }; }
    function ok(container, text) { var p = el("p", "p-alert success", text); container.appendChild(p); setTimeout(function () { p.remove(); }, 3000); }
    function iso(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
    function when(value) {
      if (!value) return "";
      var d = new Date(/Z|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z");
      return iso(d) + " " + String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
    }
    function sure(label, action) {
      var armed = false, b = api.button(label, "outline", function () {
        if (!armed) { armed = true; b.textContent = x("sure"); setTimeout(function () { armed = false; b.textContent = label; }, 4000); return; }
        action();
      });
      return b;
    }
    function statusText(s) { return x(s) || s; }
    function noteCard(n, onDelete) {
      var c = el("div", "ev-card " + (n.kind === "praise" ? "ev-green" : "ev-blue"));
      if (onDelete) { var del = el("button", "ev-x", "✕"); del.type = "button"; del.title = x("remove"); del.addEventListener("click", onDelete); c.appendChild(del); }
      c.appendChild(el("strong", "", (n.kind === "praise" ? "⭐ " : "📝 ") + n.text));
      c.appendChild(el("br"));
      c.appendChild(el("small", "", (n.author || "") + " · " + when(n.created_at)));
      return c;
    }
    function bringCard(b, onDelete) {
      var past = b.due_on && b.due_on < iso(new Date());
      var c = el("div", "ev-card " + (past ? "ev-grey" : "ev-orange"));
      if (onDelete) { var del = el("button", "ev-x", "✕"); del.type = "button"; del.title = x("remove"); del.addEventListener("click", onDelete); c.appendChild(del); }
      c.appendChild(el("small", "", "📅 " + x("neededOn") + ": " + (b.due_on || "—")));
      c.appendChild(el("h3", "", "🎒 " + b.title));
      if (b.body) c.appendChild(el("p", "", b.body));
      c.appendChild(el("small", "", (b.child || (b.class_name ? b.class_name : x("everyGroup"))) + " · " + (b.author || "")));
      return c;
    }
    function planView(container, entries) {
      var todayIndex = new Date().getDay();
      x("days").forEach(function (name, d) {
        var box = el("div", "ev-day" + (d === todayIndex ? " today" : ""));
        box.appendChild(el("h3", "", name + (d === todayIndex ? " · " + x("today") : "")));
        var items = entries.filter(function (e) { return e.weekday === d; });
        if (!items.length) box.appendChild(el("p", "p-muted", x("nothing")));
        items.forEach(function (e) {
          var row = el("div", "ev-slot");
          row.appendChild(el("span", "ev-num", String(e.position)));
          var text = el("div"); text.appendChild(el("strong", "", e.title)); if (e.detail) text.appendChild(el("div", "p-muted", e.detail));
          row.appendChild(text); box.appendChild(row);
        });
        container.appendChild(box);
      });
    }
    function chat(container, listPath, sendBody, mine) {
      var box = el("div", "ev-chat"), form = el("form", "ev-row"), input = el("textarea"), send = el("button", "p-button sun", x("send"));
      input.rows = 2; input.maxLength = 2000; input.placeholder = x("write"); input.style.flex = "1"; send.type = "submit";
      form.appendChild(input); form.appendChild(send);
      container.appendChild(box); container.appendChild(form);
      function load() {
        request(listPath).then(function (list) {
          box.innerHTML = "";
          if (!list.length) box.appendChild(el("p", "p-muted", x("noMessages")));
          list.forEach(function (m) {
            var b = el("div", "ev-msg" + (mine(m) ? " mine" : ""));
            b.appendChild(el("b", "", mine(m) ? x("you") : m.sender));
            b.appendChild(el("div", "", m.body));
            b.appendChild(el("small", "", when(m.created_at) + (mine(m) ? (m.read ? " ✓✓" : " ✓") : "")));
            box.appendChild(b);
          });
          box.scrollTop = box.scrollHeight;
        }).catch(fail(container));
      }
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        var text = input.value.trim(); if (!text) return;
        send.disabled = true;
        request(sendBody.path, {method: "POST", body: JSON.stringify(sendBody.body(text))}).then(function () { input.value = ""; load(); })
          .catch(fail(container)).finally(function () { send.disabled = false; });
      });
      load();
    }

    /* ======================================================================================== parents */
    /* The parents' home: the tiles of the child at once; with several children a choice on top. */
    function parentHome(container, children) {
      var chosen = children[0];
      var chooser = el("div", "ev-subnav"), hubBox = el("div");
      container.appendChild(chooser); container.appendChild(hubBox);
      function draw() {
        chooser.innerHTML = "";
        if (children.length > 1) children.forEach(function (c) {
          var b = el("button", "ev-chip", c.display_name); b.type = "button"; b.setAttribute("aria-pressed", String(c.id === chosen.id));
          b.addEventListener("click", function () { chosen = c; draw(); });
          chooser.appendChild(b);
        });
        parentHub(hubBox, chosen, null);
      }
      draw();
    }

    /* Coloured tiles that open the views of a portal (the teachers' home). items: [key of the view, label, icon, colours]. */
    function viewTiles(container, items, show) {
      var grid = el("div", "ev-tiles");
      grid.style.marginBottom = "18px";
      items.forEach(function (item) {
        var b = el("button", "ev-tile"); b.type = "button";
        b.style.background = "linear-gradient(135deg," + item[3] + ")";
        b.appendChild(el("span", "ev-ico", item[2])); b.appendChild(el("span", "", item[1]));
        b.addEventListener("click", function () { show(item[0]); window.scrollTo(0, 0); });
        grid.appendChild(b);
      });
      container.appendChild(grid);
    }

    function parentHub(container, child, onBack) {
      var base = "/api/platform/parent/children/" + encodeURIComponent(child.id);
      function home() {
        container.innerHTML = "";
        if (onBack) container.appendChild(api.button("← " + x("back"), "outline", onBack));
        request(base + "/overview").then(function (d) {
          var head = el("div", "ev-hub-head");
          head.appendChild(el("span", "ev-avatar", (d.name || "?").charAt(0)));
          var text = el("div"); text.appendChild(el("h2", "", d.name));
          var pills = el("div", "ev-pills");
          if (d.class_name) pills.appendChild(el("span", "ev-pill", d.class_name));
          if (d.today && d.today.attendance) pills.appendChild(el("span", "ev-pill", x("today") + ": " + statusText(d.today.attendance)));
          text.appendChild(pills); head.appendChild(text); container.appendChild(head);
          var c = d.counts || {};
          var tiles = [
            ["profile", "🧒", "#7fb3f0,#4f8edc", 0], ["notes", "⭐", "#8cc47a,#5fa34c", c.notes_new], ["bring", "🎒", "#f2b65a,#e5952b", c.bring_open],
            ["plan", "🗓️", "#8eb6f2,#5c8fe0", 0], ["attendance", "✅", "#e57e6e,#cf5443", 0], ["messages", "💬", "#5fb3a6,#368f81", c.messages_unread],
            ["fees", "🧾", "#aeb4bc,#858d97", c.invoices_open]
          ];
          var grid = el("div", "ev-tiles");
          tiles.forEach(function (tile) {
            var b = el("button", "ev-tile"); b.type = "button";
            b.style.background = "linear-gradient(135deg," + tile[2] + ")";
            b.appendChild(el("span", "ev-ico", tile[1])); b.appendChild(el("span", "", x(tile[0])));
            if (tile[3] > 0) b.appendChild(el("span", "ev-badge", String(tile[3])));
            b.addEventListener("click", function () { open(tile[0], d); });
            grid.appendChild(b);
          });
          container.appendChild(grid);
        }).catch(fail(container));
      }
      function open(kind, d) {
        container.innerHTML = "";
        container.appendChild(api.button("← " + x("back"), "outline", home));
        var c = card(x(kind));
        container.appendChild(c);
        if (kind === "profile") {
          var rel = {father: x("father"), mother: x("mother")};
          [[x("fullName"), d.name], [x("group"), d.class_name || "—"], [x("birth"), d.birth_date || "—"], [x("status"), x("registered")]]
            .concat((d.guardians || []).map(function (g) { return [rel[g.relation] || x("guardian"), g.name]; }))
            .forEach(function (pair) { var p = el("p", "p-detail"); p.appendChild(el("strong", "", pair[0] + ": ")); p.appendChild(document.createTextNode(pair[1])); c.appendChild(p); });
        } else if (kind === "notes") {
          request(base + "/notes").then(function (list) { if (!list.length) c.appendChild(el("p", "p-muted", x("noNotes"))); list.forEach(function (n) { c.appendChild(noteCard(n)); }); }).catch(fail(c));
        } else if (kind === "bring") {
          request(base + "/bring").then(function (list) { if (!list.length) c.appendChild(el("p", "p-muted", x("noBring"))); list.forEach(function (b) { c.appendChild(bringCard(b)); }); }).catch(fail(c));
        } else if (kind === "plan") {
          request(base + "/plan").then(function (p) { if (!p.entries.length) c.appendChild(el("p", "p-muted", x("noPlan"))); else planView(c, p.entries); }).catch(fail(c));
        } else if (kind === "attendance") {
          attendanceParent(c);
        } else if (kind === "messages") {
          chat(c, base + "/messages", {path: base + "/messages", body: function (text) { return {body: text}; }}, function (m) { return m.from_parent; });
        } else if (kind === "fees") {
          request(base + "/fees").then(function (data) {
            if (!data.invoices.length) c.appendChild(el("p", "p-muted", x("noFees")));
            data.invoices.forEach(function (i) {
              var cur = i.currency, key = cur === "USD" ? "usd" : "syp";
              var box = el("div", "ev-day");
              box.appendChild(el("h3", "", i.number + " · " + i.issued_on + " · " + (i.status === "paid" ? x("stPaid") : i.status === "partial" ? x("stPartial") : x("stOpen"))));
              (i.items || []).forEach(function (it) { box.appendChild(el("p", "", it.description + ": " + it[key] + " " + cur)); });
              [[x("total"), i.total], [x("paid"), i.paid], [x("open"), i.open]].forEach(function (pair) { box.appendChild(el("p", "", pair[0] + ": " + pair[1][key] + " " + cur)); });
              if ((i.payments || []).length) { box.appendChild(el("strong", "", x("payments"))); i.payments.forEach(function (p) { box.appendChild(el("p", "p-muted", p.booked_on + " · " + p.amount + " " + p.currency)); }); }
              c.appendChild(box);
            });
          }).catch(fail(c));
        }
      }
      function attendanceParent(c) {
        var monthInput = el("input"); monthInput.type = "month"; monthInput.value = iso(new Date()).slice(0, 7);
        var list = el("div");
        var form = el("form", "ev-row");
        var day = el("input"); day.type = "date"; day.min = iso(new Date()); day.value = iso(new Date());
        var kind = el("select"); ["sick", "absent"].forEach(function (s) { kind.appendChild(new Option(x(s), s)); });
        var note = el("input"); note.placeholder = x("note"); note.maxLength = 300;
        var send = el("button", "p-button sun", x("reportAbsence")); send.type = "submit";
        [day, kind, note, send].forEach(function (n) { form.appendChild(n); });
        c.appendChild(el("h3", "", x("reportAbsence"))); c.appendChild(form);
        c.appendChild(el("h3", "", x("month"))); c.appendChild(monthInput); c.appendChild(list);
        function load() {
          list.innerHTML = "";
          request(base + "/attendance?month=" + monthInput.value).then(function (d) {
            var sum = el("p", "", ["present", "absent", "sick", "excused"].map(function (s) { return x(s) + ": " + (d.counts[s] || 0); }).join(" · "));
            list.appendChild(sum);
            if (!d.days.length) list.appendChild(el("p", "p-muted", x("noDays")));
            d.days.slice().reverse().forEach(function (r) { list.appendChild(el("p", "p-detail", r.day + " · " + statusText(r.status) + (r.by_parent ? " · " + x("byYou") : "") + (r.note ? " · " + r.note : ""))); });
          }).catch(fail(list));
        }
        monthInput.addEventListener("change", load);
        form.addEventListener("submit", function (event) {
          event.preventDefault();
          request(base + "/absence", {method: "POST", body: JSON.stringify({day: day.value, status: kind.value, note: note.value.trim()})})
            .then(function () { note.value = ""; ok(c, x("sent")); load(); }).catch(fail(c));
        });
        load();
      }
      home();
    }

    /* ======================================================================================== kindergarten */
    function teacherTiles(container, available, show, openEveryday) {
      var items = [
        ["reports", x("tReports"), "📄", "#6fb7a8,#3e9483"], ["everyday:attendance", x("attendance"), "✅", "#e57e6e,#cf5443"],
        ["everyday:notes", x("notes"), "⭐", "#8cc47a,#5fa34c"], ["everyday:bring", x("bring"), "🎒", "#f2b65a,#e5952b"],
        ["everyday:plan", x("plan"), "🗓️", "#8eb6f2,#5c8fe0"], ["everyday:messages", x("messages"), "💬", "#5fb3a6,#368f81"],
        ["posts", x("tPosts"), "📣", "#b07ccb,#8e52b0"], ["material", x("tMaterial"), "📁", "#aeb4bc,#858d97"], ["review", x("tReview"), "🔎", "#7fb3f0,#4f8edc"]
      ].filter(function (item) { return available.indexOf(item[0].split(":")[0]) !== -1; });
      viewTiles(container, items, function (key) {
        var parts = key.split(":");
        show(parts[0]);
        if (parts[1] && openEveryday) openEveryday(parts[1]);
      });
    }

    function staffPane(container) {
      var sections = [["attendance", attendanceStaff], ["notes", notesStaff], ["bring", bringStaff], ["plan", planStaff], ["messages", messagesStaff]];
      var nav = el("div", "ev-subnav"), body = el("div");
      container.appendChild(nav); container.appendChild(body);
      var people = null;
      function children() { return people ? Promise.resolve(people) : request("/api/platform/staff/children").then(function (d) { people = d; return d; }); }
      function show(key) {
        Array.prototype.forEach.call(nav.children, function (b) { b.setAttribute("aria-pressed", String(b.dataset.key === key)); });
        body.innerHTML = "";
        sections.filter(function (s) { return s[0] === key; })[0][1](body);
      }
      sections.forEach(function (s) {
        var b = el("button", "ev-chip", x(s[0])); b.type = "button"; b.dataset.key = s[0];
        b.addEventListener("click", function () { show(s[0]); });
        nav.appendChild(b);
      });

      function attendanceStaff(box) {
        var c = card(x("attendance")); box.appendChild(c);
        var day = el("input"); day.type = "date"; day.max = iso(new Date()); day.value = iso(new Date());
        var group = el("select"); group.appendChild(new Option(x("allGroups"), "*"));
        var list = el("div"), changes = {};
        var save = api.button(x("saveMarks"), "sun", function () {
          var entries = Object.keys(changes).map(function (id) { return {child_id: id, status: changes[id]}; });
          if (!entries.length) return;
          request("/api/platform/staff/attendance", {method: "PUT", body: JSON.stringify({day: day.value, entries: entries})}).then(function () { ok(c, x("saved")); load(); }).catch(fail(c));
        });
        var rest = api.button(x("restPresent"), "outline", function () {
          Array.prototype.forEach.call(list.querySelectorAll("[data-open]"), function (row) { changes[row.dataset.id] = "present"; row.querySelector("select").value = "present"; });
        });
        var bar = el("div", "ev-row"); [day, group, rest, save].forEach(function (n) { bar.appendChild(n); });
        c.appendChild(bar); c.appendChild(list);
        children().then(function (d) { d.groups.forEach(function (g) { group.appendChild(new Option(g || x("noGroup"), g)); }); });
        function load() {
          list.innerHTML = ""; changes = {};
          request("/api/platform/staff/attendance?day=" + day.value + "&class_name=" + encodeURIComponent(group.value)).then(function (d) {
            if (!d.rows.length) list.appendChild(el("p", "p-muted", x("noChildren")));
            d.rows.forEach(function (r) {
              var row = el("div", "p-content-item"); row.dataset.id = r.child_id; if (!r.status) row.dataset.open = "1";
              var text = el("div"); text.appendChild(el("strong", "", r.name)); text.appendChild(el("small", "p-muted", (r.class_name || "") + (r.by_parent ? " · " + x("parentsReported") + ": " + statusText(r.status) + (r.note ? " · " + r.note : "") : "")));
              var select = el("select"); select.appendChild(new Option("—", ""));
              ["present", "absent", "sick", "excused"].forEach(function (s) { select.appendChild(new Option(x(s), s)); });
              select.value = r.status || "";
              select.addEventListener("change", function () { changes[r.child_id] = select.value; });
              row.appendChild(text); row.appendChild(select); list.appendChild(row);
            });
          }).catch(fail(list));
        }
        day.addEventListener("change", load); group.addEventListener("change", load);
        load();
      }

      function notesStaff(box) {
        var c = card(x("notes")); box.appendChild(c);
        var who = el("select"), kind = el("select"), text = el("textarea"), list = el("div");
        kind.appendChild(new Option(x("praise"), "praise")); kind.appendChild(new Option(x("plainNote"), "note"));
        text.maxLength = 500; text.rows = 3; text.placeholder = x("textLabel");
        var send = api.button(x("addNote"), "sun", function () {
          if (!who.value || !text.value.trim()) return;
          request("/api/platform/staff/children/" + encodeURIComponent(who.value) + "/notes", {method: "POST", body: JSON.stringify({kind: kind.value, text: text.value.trim()})})
            .then(function () { text.value = ""; ok(c, x("sent")); load(); }).catch(fail(c));
        });
        var bar = el("div", "ev-row"); [who, kind].forEach(function (n) { bar.appendChild(n); });
        c.appendChild(bar); c.appendChild(text); c.appendChild(send); c.appendChild(list);
        function load() {
          list.innerHTML = "";
          if (!who.value) return;
          request("/api/platform/staff/children/" + encodeURIComponent(who.value) + "/notes").then(function (notes) {
            if (!notes.length) list.appendChild(el("p", "p-muted", x("noNotes")));
            notes.forEach(function (n) { list.appendChild(noteCard(n, function () { request("/api/platform/staff/notes/" + n.id, {method: "DELETE"}).then(load).catch(fail(c)); })); });
          }).catch(fail(list));
        }
        who.addEventListener("change", load);
        children().then(function (d) { d.children.forEach(function (ch) { who.appendChild(new Option(ch.name + (ch.class_name ? " · " + ch.class_name : ""), ch.id)); }); load(); }).catch(fail(c));
      }

      function bringStaff(box) {
        var c = card(x("bring")); box.appendChild(c);
        var title = el("input"), body = el("textarea"), due = el("input"), target = el("select"), list = el("div");
        title.maxLength = 160; title.placeholder = x("what"); body.maxLength = 1000; body.rows = 2; body.placeholder = x("details");
        due.type = "date"; var tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1); due.value = iso(tomorrow);
        target.appendChild(new Option(x("everyGroup"), "all"));
        var send = api.button(x("sendParents"), "sun", function () {
          if (title.value.trim().length < 2) return;
          var v = target.value;
          request("/api/platform/staff/bring", {method: "POST", body: JSON.stringify({title: title.value.trim(), body: body.value.trim(), due_on: due.value || null,
            class_name: v.indexOf("group:") === 0 ? v.slice(6) : "", child_id: v.indexOf("child:") === 0 ? v.slice(6) : null})})
            .then(function () { title.value = ""; body.value = ""; ok(c, x("sent")); load(); }).catch(fail(c));
        });
        var bar = el("div", "ev-row"); [title, due, target].forEach(function (n) { bar.appendChild(n); });
        c.appendChild(bar); c.appendChild(body); c.appendChild(send); c.appendChild(list);
        children().then(function (d) {
          d.groups.filter(Boolean).forEach(function (g) { target.appendChild(new Option(x("groupWord") + ": " + g, "group:" + g)); });
          d.children.forEach(function (ch) { target.appendChild(new Option(x("childWord") + ": " + ch.name, "child:" + ch.id)); });
        });
        function load() {
          list.innerHTML = "";
          request("/api/platform/staff/bring").then(function (items) {
            if (!items.length) list.appendChild(el("p", "p-muted", x("noBring")));
            items.forEach(function (b) { list.appendChild(bringCard(b, function () { request("/api/platform/staff/bring/" + b.id, {method: "DELETE"}).then(load).catch(fail(c)); })); });
          }).catch(fail(list));
        }
        load();
      }

      function planStaff(box) {
        var c = card(x("plan")); box.appendChild(c);
        c.appendChild(el("p", "p-muted", x("planHint")));
        var group = el("select"), grid = el("div"), entries = [];
        var save = api.button(x("savePlan"), "sun", function () {
          request("/api/platform/staff/plan", {method: "PUT", body: JSON.stringify({class_name: group.value, entries: entries})}).then(function () { ok(c, x("saved")); }).catch(fail(c));
        });
        var bar = el("div", "ev-row"); bar.appendChild(group); bar.appendChild(save);
        c.appendChild(bar); c.appendChild(grid);
        function draw() {
          grid.innerHTML = "";
          x("days").forEach(function (name, d) {
            var day = el("div", "ev-day"); day.appendChild(el("h3", "", name));
            entries.filter(function (e) { return e.weekday === d; }).forEach(function (e) {
              var row = el("div", "ev-slot");
              row.appendChild(el("span", "ev-num", String(e.position)));
              var t1 = el("input"); t1.value = e.title; t1.maxLength = 120; t1.addEventListener("input", function () { e.title = t1.value; });
              var t2 = el("input"); t2.value = e.detail || ""; t2.maxLength = 300; t2.placeholder = x("details"); t2.addEventListener("input", function () { e.detail = t2.value; });
              var del = el("button", "ev-chip", "✕"); del.type = "button";
              del.addEventListener("click", function () { entries.splice(entries.indexOf(e), 1); var i = 1; entries.filter(function (z) { return z.weekday === d; }).forEach(function (z) { z.position = i++; }); draw(); });
              [t1, t2, del].forEach(function (n) { row.appendChild(n); });
              day.appendChild(row);
            });
            day.appendChild(api.button(x("addActivity"), "outline", function () {
              entries.push({weekday: d, position: entries.filter(function (z) { return z.weekday === d; }).length + 1, title: x("activity"), detail: ""}); draw();
            }));
            grid.appendChild(day);
          });
        }
        function load() {
          request("/api/platform/staff/plan?class_name=" + encodeURIComponent(group.value)).then(function (p) { entries = p.entries; draw(); }).catch(fail(grid));
        }
        group.addEventListener("change", load);
        children().then(function (d) { d.groups.forEach(function (g) { group.appendChild(new Option(g || x("noGroup"), g)); }); load(); }).catch(fail(c));
      }

      function messagesStaff(box) {
        var c = card(x("conversations")); box.appendChild(c);
        var pick = el("select"), list = el("div"), thread = el("div");
        pick.appendChild(new Option("— " + x("chooseParent") + " —", ""));
        var start = api.button(x("newMessage"), "sun", function () { if (pick.value) { var p = pick.value.split("|"); openThread(p[0], p[1], pick.options[pick.selectedIndex].text); } });
        var bar = el("div", "ev-row"); bar.appendChild(pick); bar.appendChild(start);
        c.appendChild(bar); c.appendChild(list); box.appendChild(thread);
        children().then(function (d) { d.children.forEach(function (ch) { (ch.parents || []).forEach(function (p) { pick.appendChild(new Option(ch.name + " · " + p.username, ch.id + "|" + p.id)); }); }); });
        function openThread(childId, parentId, title) {
          thread.innerHTML = "";
          var t = card(title); thread.appendChild(t);
          chat(t, "/api/platform/staff/conversations/" + childId + "/" + parentId,
            {path: "/api/platform/staff/messages", body: function (text) { return {child_id: childId, parent_id: parentId, body: text}; }},
            function (m) { return !m.from_parent; });
          thread.scrollIntoView({behavior: "smooth", block: "start"});
          load();
        }
        function load() {
          list.innerHTML = "";
          request("/api/platform/staff/conversations").then(function (rows) {
            if (!rows.length) list.appendChild(el("p", "p-muted", x("noConversations")));
            rows.forEach(function (r) {
              var row = el("div", "p-content-item");
              var text = el("div"); text.appendChild(el("strong", "", r.child + " · " + r.parent)); text.appendChild(el("small", "p-muted", r.last.body));
              row.appendChild(text);
              if (r.unread) row.appendChild(el("span", "p-count", String(r.unread)));
              row.appendChild(api.button(x("messages"), "outline", function () { openThread(r.child_id, r.parent_id, r.child + " · " + r.parent); }));
              list.appendChild(row);
            });
          }).catch(fail(list));
        }
        load();
      }

      show("attendance");
      return {show: show};
    }

    return {parentHub: parentHub, parentHome: parentHome, staffPane: staffPane, teacherTiles: teacherTiles, viewTiles: viewTiles, text: x};
  };
}());
