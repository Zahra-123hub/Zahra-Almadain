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
      tReports: "التقارير اليومية", tPosts: "المنشورات", tMaterial: "المواد التعليمية", tReview: "مراجعة التقارير", tEveryday: "الحياة اليومية", news: "الأخبار",
      notLinked: "لم يُربط حسابك بطفل بعد. تربطه الروضة بعد الموافقة.",
      search: "بحث...", chatHint: "اكتب لمعلمة طفلك أو لإدارة الروضة. الإدارة تستطيع الاطلاع على كل المحادثات.", tapToStart: "اضغط لبدء المحادثة",
      gone: "لم تعد في الروضة", rTeacher: "معلمة", rOffice: "إدارة الروضة", rParent: "وليّ الأمر", yesterday: "أمس", allChats: "كل المحادثات",
      weekdays: ["الأحد", "الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت"],
      noticeOffice: "محادثتك مع إدارة الروضة حول {0}.", noticeTeacher: "محادثتك مع {0} حول {1}. إدارة الروضة تستطيع الاطلاع عليها.",
      noticeStaff: "محادثتك مع أهل {0}. إدارة الروضة تستطيع الاطلاع عليها.", noticeBossOffice: "محادثة إدارة الروضة مع أهل {0}.",
      noticeBossTeacher: "محادثة معلمة مع أهل {0}. ما تكتبه هنا يظهر باسمك.", fAll: "الكل", fUnread: "غير مقروءة", fOffice: "الإدارة",
      fTeachers: "المعلمات", withTeacher: "مع المعلمة", newChat: "محادثة جديدة", noResults: "لا توجد نتائج.", pickChat: "اختر محادثة من القائمة أو ابدأ محادثة جديدة."
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
      tReports: "Daily reports", tPosts: "Posts", tMaterial: "Materials", tReview: "Review reports", tEveryday: "Everyday", news: "News",
      notLinked: "Your account is not linked to a child yet. The kindergarten does that.",
      search: "Search...", chatHint: "Write to a teacher or to the management. The management can see every chat.", tapToStart: "Tap to start a chat",
      gone: "has left", rTeacher: "Teacher", rOffice: "Management", rParent: "Parent", yesterday: "Yesterday", allChats: "All chats",
      weekdays: ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"],
      noticeOffice: "Your chat with the management about {0}.", noticeTeacher: "Your chat with {0} about {1}. The management can see it.",
      noticeStaff: "Your chat with the parents of {0}. The management can see it.", noticeBossOffice: "The management's chat with the parents of {0}.",
      noticeBossTeacher: "A teacher's chat with the parents of {0}. What you write here shows your name.", fAll: "All", fUnread: "Unread", fOffice: "Management",
      fTeachers: "Teachers", withTeacher: "with teacher", newChat: "New chat", noResults: "Nothing found.", pickChat: "Choose a chat from the list or start a new one."
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
    ".ev-subnav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}",
    ".ev-wa{border-radius:16px;overflow:hidden;border:1px solid var(--line);background:#efe7de;display:flex;flex-direction:column;height:min(74vh,760px);margin-top:10px}",
    ".ev-wa-head{background:#008069;color:#fff;display:flex;align-items:center;gap:10px;padding:10px 14px}.ev-wa-head b{display:block;font-size:1.05rem}.ev-wa-head small{opacity:.8}",
    ".ev-wa-body{flex:1;overflow:auto;padding:10px 14px;display:flex;flex-direction:column;gap:2px}",
    ".ev-wa-note{align-self:center;background:#ffeecd;color:#54656f;border-radius:8px;padding:6px 12px;font-size:.8rem;margin:6px 0;text-align:center;max-width:90%}",
    ".ev-wa-day{align-self:center;background:#fff;color:#54656f;border-radius:8px;padding:4px 12px;font-size:.8rem;font-weight:600;margin:8px 0;box-shadow:0 1px 2px #0001}",
    ".ev-wa-msg{max-width:78%;background:#fff;border-radius:12px;padding:6px 10px 4px;box-shadow:0 1px 1.5px #0002;align-self:flex-start;color:#111b21}",
    ".ev-wa-msg.ours{align-self:flex-end;background:#d9fdd3}.ev-wa-msg.first{margin-top:6px}",
    ".ev-wa-msg.first:not(.ours){border-start-start-radius:2px}.ev-wa-msg.first.ours{border-start-end-radius:2px}",
    ".ev-wa-name{display:block;font-size:.8rem;font-weight:800;margin-bottom:2px}.ev-wa-body-text{white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.4}",
    ".ev-wa-meta{display:block;text-align:end;font-size:.72rem;color:#667781;margin-top:2px}",
    ".ev-wa-tick{color:#667781;letter-spacing:-3px;font-weight:700}.ev-wa-tick.read{color:#53bdeb}",
    ".ev-wa-input{display:flex;gap:8px;padding:8px;align-items:flex-end}",
    ".ev-wa-input textarea{flex:1;border:0;border-radius:22px;padding:11px 16px;resize:none;font:inherit;max-height:130px;box-shadow:0 1px 2px #0001;outline:none}",
    ".ev-wa-send{width:46px;height:46px;border-radius:50%;border:0;background:#00a884;color:#fff;font-size:1.15rem;cursor:pointer;flex:none}.ev-wa-send:disabled{background:#8fcfc0;cursor:default}",
    ".ev-wa-list{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff}",
    ".ev-wa-row{display:flex;gap:12px;align-items:center;padding:10px 14px;border:0;border-bottom:1px solid #eef0f2;background:#fff;width:100%;text-align:start;cursor:pointer;font:inherit;color:inherit}",
    ".ev-wa-row:hover{background:#f5f6f6}.ev-wa-row.active{background:#f0f2f5}",
    ".ev-wa-av{width:48px;height:48px;border-radius:50%;display:grid;place-items:center;color:#fff;font-weight:800;font-size:1.2rem;flex:none}",
    ".ev-wa-head .ev-wa-av{width:40px;height:40px;font-size:1rem}",
    ".ev-wa-main{flex:1;min-width:0;display:block}.ev-wa-top{display:flex;gap:8px;align-items:baseline}",
    ".ev-wa-top b{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ev-wa-time{font-size:.75rem;color:#667781}.ev-wa-time.new{color:#00a884;font-weight:800}",
    ".ev-wa-tag{display:block;font-size:.78rem;color:#008069;font-weight:700}",
    ".ev-wa-prev{display:flex;gap:6px;align-items:center;color:#667781;font-size:.9rem;margin-top:2px}.ev-wa-text{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}",
    ".ev-wa-badge{background:#00a884;color:#fff;border-radius:999px;min-width:22px;padding:1px 6px;font-size:.75rem;font-weight:800;text-align:center}",
    ".ev-wa-search{width:100%;box-sizing:border-box;border-radius:22px;border:0;background:#f0f2f5;padding:9px 14px;margin:8px 0;font:inherit}",
    ".ev-wa-split{display:grid;grid-template-columns:minmax(260px,380px) 1fr;gap:14px;align-items:start}.ev-wa-split>div:last-child .ev-wa{margin-top:0}",
    ".ev-wa-empty{border:1px dashed var(--line);border-radius:16px;padding:40px 16px;text-align:center;color:#667781;background:#f8f9fa}",
    "@media (max-width:820px){.ev-wa-split{grid-template-columns:1fr}}"
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
    /* ---- chats, like WhatsApp: one conversation = one child, one parent account, one teacher (or the management) ---- */
    var COLORS = ["#4f8edc", "#3e9483", "#cf5443", "#8e52b0", "#e5952b", "#5fa34c", "#368f81", "#b0527a"];
    function colorOf(name) { var s = 0; for (var i = 0; i < (name || "").length; i++) s += name.charCodeAt(i); return COLORS[s % COLORS.length]; }
    function fill(text) { var args = arguments; return text.replace(/\{(\d)\}/g, function (_, i) { return args[Number(i) + 1]; }); }
    function avatar(name, glyph) { var a = el("span", "ev-wa-av", glyph || (name || "?").charAt(0).toUpperCase()); a.style.background = glyph ? "#008069" : colorOf(name); return a; }
    function localDate(value) { return value ? new Date(/Z|[+-]\d\d:?\d\d$/.test(value) ? value : value + "Z") : null; }
    function clock(d) { return String(d.getHours()).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0"); }
    function dayLabel(d) {
      var now = new Date(), a = new Date(now.getFullYear(), now.getMonth(), now.getDate()), b = new Date(d.getFullYear(), d.getMonth(), d.getDate());
      var diff = Math.round((a - b) / 86400000);
      if (diff === 0) return x("today");
      if (diff === 1) return x("yesterday");
      if (diff > 1 && diff < 7) return x("weekdays")[d.getDay()];
      return iso(d);
    }
    function listTime(value) { var d = localDate(value); if (!d) return ""; return iso(d) === iso(new Date()) ? clock(d) : dayLabel(d); }
    function roleWord(role) { return role === "teacher" ? x("rTeacher") : (role === "manager" || role === "admin" || role === "office") ? x("rOffice") : role === "parent" ? x("rParent") : ""; }
    function tick(m) { return el("span", "ev-wa-tick" + (m.read ? " read" : ""), m.pending ? "🕓" : (m.read ? "✓✓" : "✓")); }
    /* one line of a list of chats. o: {title, tag, glyph, last, ours, unread, empty, active, onClick} */
    function chatRow(o) {
      var b = el("button", "ev-wa-row" + (o.active ? " active" : "")); b.type = "button";
      b.appendChild(avatar(o.title, o.glyph));
      var main = el("span", "ev-wa-main"), top = el("span", "ev-wa-top"), prev = el("span", "ev-wa-prev");
      top.appendChild(el("b", "", o.title));
      if (o.last) top.appendChild(el("span", "ev-wa-time" + (o.unread ? " new" : ""), listTime(o.last.created_at)));
      main.appendChild(top);
      if (o.tag) main.appendChild(el("span", "ev-wa-tag", o.tag));
      if (o.last && o.ours) prev.appendChild(tick(o.last));
      prev.appendChild(el("span", "ev-wa-text", o.last ? o.last.body.replace(/\n/g, " ") : (o.empty || "")));
      if (o.unread) prev.appendChild(el("span", "ev-wa-badge", String(o.unread)));
      main.appendChild(prev); b.appendChild(main);
      b.addEventListener("click", o.onClick);
      return b;
    }
    /* one conversation. o: {title, subtitle, glyph, notice, listPath, sendPath, sendBody(text), staffSide, onChange} */
    function chat(container, o) {
      var box = el("div", "ev-wa"), head = el("div", "ev-wa-head"), body = el("div", "ev-wa-body");
      head.appendChild(avatar(o.title, o.glyph));
      var names = el("div"); names.appendChild(el("b", "", o.title)); if (o.subtitle) names.appendChild(el("small", "", o.subtitle)); head.appendChild(names);
      var form = el("form", "ev-wa-input"), input = el("textarea"), send = el("button", "ev-wa-send", "➤");
      input.rows = 1; input.maxLength = 2000; input.placeholder = x("write"); send.type = "submit"; send.disabled = true; send.title = x("send");
      if (document.documentElement.dir === "rtl") send.style.transform = "scaleX(-1)";
      form.appendChild(input); form.appendChild(send);
      box.appendChild(head); box.appendChild(body); box.appendChild(form); container.appendChild(box);
      var messages = [], pending = [], lastKey = "";
      function ours(m) { return o.staffSide ? !m.from_parent : !!m.from_parent; }
      function draw(force) {
        var atBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 80;
        body.innerHTML = "";
        body.appendChild(el("div", "ev-wa-note", "🔒 " + o.notice));
        var all = messages.concat(pending);
        if (!all.length) body.appendChild(el("div", "ev-wa-day", x("noMessages") + " 👋"));
        var lastDay = null, prev = null;
        all.forEach(function (m) {
          var d = localDate(m.created_at) || new Date(), day = iso(d);
          if (day !== lastDay) { body.appendChild(el("div", "ev-wa-day", dayLabel(d))); lastDay = day; prev = null; }
          var first = !prev || ours(prev) !== ours(m) || prev.sender !== m.sender;
          var b = el("div", "ev-wa-msg" + (ours(m) ? " ours" : "") + (first ? " first" : ""));
          /* who wrote it: for the parents every kindergarten message; for the kindergarten a colleague's message */
          var showName = first && (o.staffSide ? (ours(m) && !m.mine && !m.pending) : !ours(m));
          if (showName && m.sender) {
            var n = el("span", "ev-wa-name", m.sender + (roleWord(m.sender_role) ? " · " + roleWord(m.sender_role) : ""));
            n.style.color = colorOf(m.sender); b.appendChild(n);
          }
          b.appendChild(el("span", "ev-wa-body-text", m.body));
          var meta = el("span", "ev-wa-meta", clock(d));
          if (ours(m)) { meta.appendChild(document.createTextNode(" ")); meta.appendChild(tick(m)); }
          b.appendChild(meta);
          body.appendChild(b); prev = m;
        });
        if (force || atBottom) body.scrollTop = body.scrollHeight;
      }
      function load(force) {
        return request(o.listPath).then(function (list) {
          var key = JSON.stringify(list.map(function (m) { return [m.id, m.read]; }));
          if (force || key !== lastKey) { messages = list; lastKey = key; draw(force); }
        }).catch(function (error) { if (!messages.length) fail(body)(error); });
      }
      function submit() {
        var text = input.value.trim(); if (!text) return;
        var draft = {body: text, from_parent: !o.staffSide, mine: true, pending: true, created_at: new Date().toISOString()};
        pending.push(draft); input.value = ""; send.disabled = true; input.style.height = "";
        draw(true);
        request(o.sendPath, {method: "POST", body: JSON.stringify(o.sendBody(text))})
          .then(function () { pending.splice(pending.indexOf(draft), 1); if (o.onChange) o.onChange(); return load(true); })
          .catch(function (error) { pending.splice(pending.indexOf(draft), 1); input.value = text; send.disabled = false; draw(true); api.showError(container, error); });
        input.focus();
      }
      input.addEventListener("input", function () {
        send.disabled = !input.value.trim();
        input.style.height = "auto"; input.style.height = Math.min(input.scrollHeight, 130) + "px";
      });
      input.addEventListener("keydown", function (event) { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); } });
      form.addEventListener("submit", function (event) { event.preventDefault(); submit(); });
      /* new messages come in by themselves while the chat is on the screen */
      var timer = setInterval(function () {
        if (!document.body.contains(box)) { clearInterval(timer); return; }
        if (!document.hidden) load(false);
      }, 6000);
      load(true).then(function () { if (o.onChange) o.onChange(); });
      input.focus();
    }
    /* the parents: whom to write to about this child (the teachers and the management) */
    function parentChats(c, base, childName) {
      c.innerHTML = "";
      c.appendChild(el("h2", "", x("messages")));
      c.appendChild(el("p", "p-muted", x("chatHint")));
      var search = el("input", "ev-wa-search"); search.type = "search"; search.placeholder = x("search");
      var list = el("div", "ev-wa-list");
      c.appendChild(search); c.appendChild(list);
      var rows = [];
      function name(r) { return r.role === "office" ? x("rOffice") : r.name; }
      function drawList() {
        list.innerHTML = "";
        var q = search.value.trim().toLowerCase();
        rows.filter(function (r) { return !q || name(r).toLowerCase().indexOf(q) !== -1 || (r.last && r.last.body.toLowerCase().indexOf(q) !== -1); })
          .forEach(function (r) {
            list.appendChild(chatRow({title: name(r), tag: r.role === "office" ? "" : x("rTeacher") + (r.gone ? " · " + x("gone") : ""), glyph: r.role === "office" ? "🏫" : "",
              last: r.last, ours: r.last && r.last.from_parent, unread: r.unread, empty: x("tapToStart"), onClick: function () { openChat(r); }}));
          });
      }
      function openChat(r) {
        var office = r.role === "office";
        c.innerHTML = "";
        c.appendChild(api.button("← " + x("allChats"), "outline", function () { parentChats(c, base, childName); }));
        chat(c, {title: name(r), subtitle: (office ? "" : x("rTeacher") + " · ") + childName, glyph: office ? "🏫" : "",
          notice: office ? fill(x("noticeOffice"), childName) : fill(x("noticeTeacher"), name(r), childName),
          listPath: base + "/messages?to=" + encodeURIComponent(r.with), sendPath: base + "/messages",
          sendBody: function (text) { return {body: text, to: r.with}; }, staffSide: false});
      }
      search.addEventListener("input", drawList);
      request(base + "/contacts").then(function (r) { rows = r; drawList(); }).catch(fail(list));
    }

    /* ======================================================================================== parents */
    /* The parents' home: the tiles of the child at once; with several children a choice on top. */
    function parentHome(container, children, goView) {
      container.innerHTML = "";
      if (!children.length) {
        var hint = el("div", "ev-hub-head");
        hint.appendChild(el("span", "ev-avatar", "i"));
        hint.appendChild(el("p", "", x("notLinked")));
        container.appendChild(hint);
        var grid = el("div", "ev-tiles");
        parentTileList({}).forEach(function (tile) {
          var b = tileButton(tile);
          b.addEventListener("click", function () {
            if (tile[0] === "news" && goView) goView("posts");
            else alert(x("notLinked"));
          });
          grid.appendChild(b);
        });
        container.appendChild(grid);
        return;
      }
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
        parentHub(hubBox, chosen, null, goView);
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

    function parentTileList(c) {
      return [
        ["profile", "🧒", "#7fb3f0,#4f8edc", 0], ["reports", "📄", "#6fb7a8,#3e9483", 0], ["notes", "⭐", "#8cc47a,#5fa34c", c.notes_new],
        ["bring", "🎒", "#f2b65a,#e5952b", c.bring_open], ["plan", "🗓️", "#8eb6f2,#5c8fe0", 0], ["attendance", "✅", "#e57e6e,#cf5443", 0],
        ["news", "📣", "#b07ccb,#8e52b0", 0], ["messages", "💬", "#5fb3a6,#368f81", c.messages_unread], ["fees", "🧾", "#aeb4bc,#858d97", c.invoices_open]
      ];
    }
    function tileButton(tile) {
      var b = el("button", "ev-tile"); b.type = "button";
      b.style.background = "linear-gradient(135deg," + tile[2] + ")";
      b.appendChild(el("span", "ev-ico", tile[1])); b.appendChild(el("span", "", x(tile[0] === "reports" ? "tReports" : tile[0])));
      if (tile[3] > 0) b.appendChild(el("span", "ev-badge", String(tile[3])));
      return b;
    }

    function parentHub(container, child, onBack, goView) {
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
          var tiles = parentTileList(d.counts || {}).filter(function (tile) { return goView || (tile[0] !== "reports" && tile[0] !== "news"); });
          var grid = el("div", "ev-tiles");
          tiles.forEach(function (tile) {
            var b = tileButton(tile);
            b.addEventListener("click", function () {
              if (tile[0] === "reports") goView("reports", child);
              else if (tile[0] === "news") goView("posts");
              else open(tile[0], d);
            });
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
          parentChats(c, base, d.name);
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

    function staffPane(container, opts) {
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

      /* the kindergarten's chats with the parents: a teacher her own, the management every one (its own and the teachers') */
      function messagesStaff(box) {
        var c = card(x("conversations")); box.appendChild(c);
        var bar = el("div", "ev-row"), pick = el("select");
        pick.appendChild(new Option("— " + x("chooseParent") + " —", ""));
        var start = api.button("💬 " + x("newChat"), "sun", function () {
          if (!pick.value) return;
          var p = pick.value.split("|"), label = pick.options[pick.selectedIndex].dataset;
          openThread({child_id: p[0], parent_id: p[1], with: "", child: label.child, parent: label.parent});
        });
        bar.appendChild(pick); bar.appendChild(start); c.appendChild(bar);
        var split = el("div", "ev-wa-split"), left = el("div"), right = el("div");
        var search = el("input", "ev-wa-search"); search.type = "search"; search.placeholder = x("search");
        var chips = el("div", "ev-subnav"), list = el("div", "ev-wa-list");
        left.appendChild(search); left.appendChild(chips); left.appendChild(list);
        right.appendChild(el("div", "ev-wa-empty", "💬 " + x("pickChat")));
        split.appendChild(left); split.appendChild(right); c.appendChild(split);
        children().then(function (d) {
          d.children.forEach(function (ch) {
            (ch.parents || []).forEach(function (p) {
              var o = new Option(p.username + " · " + ch.name, ch.id + "|" + p.id); o.dataset.child = ch.name; o.dataset.parent = p.username; pick.appendChild(o);
            });
          });
        });
        var rows = [], filter = "all", openKey = "";
        function boss() { return (opts && opts.boss) || rows.some(function (r) { return r.with === "office" || !r.mine; }); }
        function keyOf(r) { return r.child_id + "|" + r.parent_id + "|" + r.with; }
        function drawChips() {
          chips.innerHTML = "";
          [["all", "fAll"], ["unread", "fUnread"]].concat(boss() ? [["office", "fOffice"], ["teachers", "fTeachers"]] : []).forEach(function (f) {
            var b = el("button", "ev-chip", x(f[1])); b.type = "button"; b.setAttribute("aria-pressed", String(filter === f[0]));
            b.addEventListener("click", function () { filter = f[0]; drawChips(); drawList(); });
            chips.appendChild(b);
          });
        }
        function drawList() {
          list.innerHTML = "";
          var q = search.value.trim().toLowerCase(), isBoss = boss();
          var shown = rows.filter(function (r) {
            var office = r.with === "office";
            var ok = filter === "unread" ? r.unread > 0 : filter === "office" ? office : filter === "teachers" ? !office : true;
            return ok && (!q || [r.child, r.parent, r.staff, r.last && r.last.body].some(function (v) { return String(v || "").toLowerCase().indexOf(q) !== -1; }));
          });
          if (!shown.length) list.appendChild(el("p", "p-muted", rows.length ? x("noResults") : x("noConversations")));
          shown.forEach(function (r) {
            list.appendChild(chatRow({title: r.parent + " · " + r.child, tag: !isBoss ? "" : r.with === "office" ? x("rOffice") : x("withTeacher") + " " + r.staff,
              last: r.last, ours: r.last && !r.last.from_parent, unread: r.unread, active: keyOf(r) === openKey, onClick: function () { openThread(r); }}));
          });
        }
        function openThread(r) {
          var isBoss = boss(), to = r.with || "";
          openKey = to ? keyOf(r) : "";
          right.innerHTML = "";
          var notice = !isBoss ? fill(x("noticeStaff"), r.child) : (to === "office" || to === "") ? fill(x("noticeBossOffice"), r.child) : fill(x("noticeBossTeacher"), r.child);
          chat(right, {title: r.parent + " · " + r.child, subtitle: isBoss && to && to !== "office" ? x("withTeacher") + " " + (r.staff || "") : x("rParent"),
            notice: notice, listPath: "/api/platform/staff/conversations/" + r.child_id + "/" + r.parent_id + "?to=" + encodeURIComponent(to),
            sendPath: "/api/platform/staff/messages", sendBody: function (text) { return {child_id: r.child_id, parent_id: r.parent_id, body: text, to: to}; },
            staffSide: true, onChange: load});
          if (window.innerWidth <= 820) right.scrollIntoView({behavior: "smooth", block: "start"});
          drawList();
        }
        function load() {
          return request("/api/platform/staff/conversations").then(function (r) { rows = r; drawChips(); drawList(); }).catch(fail(list));
        }
        search.addEventListener("input", drawList);
        load();
      }

      show("attendance");
      return {show: show};
    }

    return {parentHub: parentHub, parentHome: parentHome, staffPane: staffPane, teacherTiles: teacherTiles, viewTiles: viewTiles, text: x};
  };
}());
