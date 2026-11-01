/* Management portal: numbers, children and their assignments, groups, registration requests, report approval, notices.
   portal.js hands over its helpers (api) and the session; every call below is authorised again by the server. */
(function () {
  "use strict";

  var TXT = {
    ar: {
      kidsTitle: "إضافة طفل",
      kidsHelp: "احفظ اسم كل طفل مرة واحدة مع والده أو والدته أو كليهما. إن ربطتَ ولي الأمر بحسابه في بوابة الأهل رأى تقارير طفله ومنشوراته الخاصة. الأطفال المحفوظون هنا يراهم المحاسب في الاشتراكات.",
      oneOrBoth: "أضف الأب والأم، أو واحداً منهما فقط. اترك خانات الآخر فارغة إن لم يكن موجوداً.",
      childName: "اسم الطفل",
      className: "الصف / المجموعة",
      birthDate: "تاريخ الميلاد",
      father: "الأب",
      mother: "الأم",
      otherGuardian: "ولي أمر آخر",
      relationLabel: "الصفة",
      fullName: "الاسم الكامل",
      phoneLabel: "الهاتف",
      emailLabel: "البريد الإلكتروني (اختياري)",
      loginAccount: "حساب بوابة الأهل",
      noLogin: "بلا حساب دخول",
      saveChild: "＋ حفظ الطفل",
      childSaved: "تم حفظ الطفل وولي أمره.",
      kidsList: "الأطفال المسجَّلون",
      noKids: "لا يوجد أطفال محفوظون بعد.",
      removeFromList: "إزالة من القائمة",
      childRemoved: "أُزيل الطفل من القائمة (تبقى اشتراكاته ودفعاته القديمة).",
      needGuardian: "أضف ولي أمر واحداً على الأقل: الأب أو الأم (أو الاثنين).",
      nameFor: "اكتب اسم ",
      both: "الأب والأم",
      oneGuardian: "ولي أمر واحد",
      empTitle: "إضافة موظف",
      empHelp: "احفظ اسم كل موظف أو مدرّسة مرة واحدة، واربطه بحساب دخوله إن وُجد. يختار المحاسب منهم عند إنشاء الرواتب. الراتب الشهري المعتاد يُملأ منه سطر الراتب تلقائياً.",
      jobTitle: "المسمى الوظيفي",
      salaryLabel: "الراتب الشهري المعتاد",
      salaryCurrency: "العملة",
      empAccount: "حساب الدخول",
      saveEmp: "＋ حفظ الموظف",
      empSaved: "تم حفظ الموظف.",
      empList: "الموظفون المسجَّلون",
      noEmp: "لا يوجد موظفون محفوظون بعد.",
      empRemoved: "أُزيل الموظف من القائمة (تبقى رواتبه القديمة).",
      linkedTo: "مرتبط بـ",
      teacherRole: "معلمة",
      accountantRole: "محاسب",
      followed: "وتحدّث راتب {n} سطر لم يُدفع بعد ليوافق الراتب الجديد.",
      searchChildren: "ابحث باسم الطفل أو ولي الأمر", noChildren: "لا يوجد أطفال بعد.", noResult: "لا توجد نتيجة لهذا البحث.",
      group: "المجموعة / الصف", groupHint: "اكتب اسم المجموعة (مثال: KG1). إن لم تكن موجودة تُنشأ تلقائياً.", save: "حفظ", saved: "تم الحفظ.",
      guardians: "أولياء الأمور", noGuardians: "لم يُسجَّل ولي أمر بعد.", father: "الأب", mother: "الأم", guardian: "ولي أمر",
      withAccount: "له حساب", noAccount: "بلا حساب", teachers: "المعلمات", parents: "حسابات الأهل", none: "—",
      addTeacher: "أضف معلمة", addParent: "اربط حساب ولي أمر", add: "إضافة", remove: "إزالة", sure: "تأكيد؟",
      groupsTitle: "المجموعات", groupsHelp: "المجموعة هي صف الطفل. غيّر الاسم هنا ليتغير عند كل أطفالها، ولإنشاء مجموعة جديدة اكتب اسمها عند أحد الأطفال.",
      noGroups: "لا توجد مجموعات بعد.", childrenCount: "أطفال", rename: "إعادة تسمية",
      requestsTitle: "طلبات التسجيل", noRequests: "لا توجد طلبات.", approve: "موافقة", reject: "رفض", newCode: "رمز جديد",
      pending: "بانتظار القرار", approved: "تمت الموافقة", rejected: "مرفوض", registered: "أنشأ حسابه",
      childOf: "الطفل", phone: "الهاتف", email: "البريد", relation: "الصلة", notes: "ملاحظات",
      codeTitle: "رمز التسجيل (يُعرض مرة واحدة فقط)", codeSent: "أُرسل الرمز إلى بريد ولي الأمر.", codeNotSent: "لم يُرسل البريد. أعطِ الرمز لولي الأمر بنفسك.",
      noticesTitle: "إعلان جديد للأهل والمعلمات", noticeTitle: "العنوان", noticeBody: "النص", publish: "نشر الإعلان", published: "تم نشر الإعلان وإشعار الجميع.",
      myNotices: "الإعلانات المنشورة", noNotices: "لا توجد إعلانات.", delete: "حذف",
      home: "الرئيسية", statParents: "حسابات الأهل", statTeachers: "المعلمات", statGroups: "المجموعات", statRequests: "طلبات بانتظار القرار", statReview: "تقارير بانتظار الاعتماد"
    },
    en: {
      kidsTitle: "Add a child",
      kidsHelp: "Save every child once with the father, the mother or both. If you tie a parent to their portal account they see the reports and private posts of their child. The accountant sees the saved children in the fees.",
      oneOrBoth: "Add the father and the mother, or only one of them. Leave the other's fields empty if there is none.",
      childName: "Child's name",
      className: "Class / group",
      birthDate: "Date of birth",
      father: "Father",
      mother: "Mother",
      otherGuardian: "Another guardian",
      relationLabel: "Role",
      fullName: "Full name",
      phoneLabel: "Phone",
      emailLabel: "E-mail (optional)",
      loginAccount: "Parents' portal account",
      noLogin: "No sign-in account",
      saveChild: "＋ Save child",
      childSaved: "The child and the guardian are saved.",
      kidsList: "Saved children",
      noKids: "No children are saved yet.",
      removeFromList: "Remove from the list",
      childRemoved: "The child was removed from the list (old fees and payments stay).",
      needGuardian: "Add at least one guardian: the father or the mother (or both).",
      nameFor: "Write the name of: ",
      both: "Father and mother",
      oneGuardian: "One guardian",
      empTitle: "Add an employee",
      empHelp: "Save every employee or teacher once and tie them to their sign-in account if they have one. The accountant picks from them when creating the salaries. The usual monthly salary fills the salary line automatically.",
      jobTitle: "Job title",
      salaryLabel: "Usual monthly salary",
      salaryCurrency: "Currency",
      empAccount: "Sign-in account",
      saveEmp: "＋ Save employee",
      empSaved: "The employee is saved.",
      empList: "Saved employees",
      noEmp: "No employees are saved yet.",
      empRemoved: "The employee was removed from the list (old salaries stay).",
      linkedTo: "linked to",
      teacherRole: "Teacher",
      accountantRole: "Accountant",
      followed: "and {n} unpaid salary line(s) follow the new salary.",
      searchChildren: "Search by child or parent name", noChildren: "No children yet.", noResult: "Nothing found for this search.",
      group: "Group / class", groupHint: "Type the group name (e.g. KG1). A new name creates the group.", save: "Save", saved: "Saved.",
      guardians: "Guardians", noGuardians: "No guardian recorded yet.", father: "Father", mother: "Mother", guardian: "Guardian",
      withAccount: "Has account", noAccount: "No account", teachers: "Teachers", parents: "Parent accounts", none: "—",
      addTeacher: "Add a teacher", addParent: "Link a parent account", add: "Add", remove: "Remove", sure: "Sure?",
      groupsTitle: "Groups", groupsHelp: "A group is the class of a child. Rename it here to change it for all its children; to create a new one, type its name on a child.",
      noGroups: "No groups yet.", childrenCount: "children", rename: "Rename",
      requestsTitle: "Registration requests", noRequests: "No requests.", approve: "Approve", reject: "Reject", newCode: "New code",
      pending: "Awaiting decision", approved: "Approved", rejected: "Rejected", registered: "Account created",
      childOf: "Child", phone: "Phone", email: "E-mail", relation: "Relation", notes: "Notes",
      codeTitle: "Registration code (shown only once)", codeSent: "The code was sent to the guardian's e-mail.", codeNotSent: "The e-mail was not sent. Give the code to the guardian yourself.",
      noticesTitle: "New notice for parents and teachers", noticeTitle: "Title", noticeBody: "Text", publish: "Publish notice", published: "The notice is published and everyone is notified.",
      myNotices: "Published notices", noNotices: "No notices.", delete: "Delete",
      home: "Home", statParents: "Parent accounts", statTeachers: "Teachers", statGroups: "Groups", statRequests: "Requests awaiting a decision", statReview: "Reports awaiting approval"
    }
  };
  var API = "/api/admin/platform";

  window.ZMManagement = function (api) {
    var el = api.element, request = api.request, t = api.t;
    function m(key) { var table = TXT[api.lang()] || TXT.ar; return table[key] || key; }

    function field(label, input) {
      var wrap = el("div", "p-field");
      var caption = el("label", "", label);
      caption.appendChild(input);
      wrap.appendChild(caption);
      return wrap;
    }
    function textInput(value, max) { var input = el("input"); input.type = "text"; input.maxLength = max; input.value = value || ""; return input; }
    function note(card, text, kind) {
      var line = card.querySelector(":scope > .p-alert");
      if (!line) { line = el("p", "p-alert"); line.setAttribute("role", "status"); card.appendChild(line); }
      line.className = "p-alert " + (kind || "success");
      line.textContent = text;
    }
    /* A destructive action asks for a second click. */
    function sureButton(label, action, onError) {
      var timer = 0;
      var item = api.button(label, "outline", function () {
        if (!timer) {
          item.textContent = m("sure"); item.classList.add("danger");
          timer = setTimeout(function () { timer = 0; item.textContent = label; item.classList.remove("danger"); }, 4000);
          return;
        }
        clearTimeout(timer); timer = 0;
        item.disabled = true;
        Promise.resolve().then(action).catch(function (error) { item.disabled = false; item.textContent = label; item.classList.remove("danger"); onError(error); });
      });
      return item;
    }

    return function (shellMain) {
      var views = api.viewShell(shellMain, [
        ["home", "navHome"], ["kids", "navKids"], ["employees", "navEmployees"], ["children", "navAssign"], ["groups", "navGroups"], ["requests", "navRequests"],
        ["review", "navReview"], ["notices", "navNotices"], ["notifications", "navNotifications"], ["profile", "navProfile"]]);
      var panes = views.panes;
      var shared = {names: {}, groups: []};

      // ---- home: numbers and notices
      api.renderDashboardWelcome(panes.home);
      var stats = el("div", "p-stats");
      var tiles = {
        children: api.statTile(t("statChildren"), "kids", views.show),
        parents: api.statTile(m("statParents"), "children", views.show),
        teachers: api.statTile(m("statTeachers"), "children", views.show),
        groups: api.statTile(m("statGroups"), "groups", views.show),
        pending_requests: api.statTile(m("statRequests"), "requests", views.show),
        reports_in_review: api.statTile(m("statReview"), "review", views.show)
      };
      Object.keys(tiles).forEach(function (key) { stats.appendChild(tiles[key]); });
      panes.home.appendChild(stats);
      api.renderAnnouncements(panes.home);
      function loadStats() {
        request(API + "/stats").then(function (data) {
          Object.keys(tiles).forEach(function (key) { tiles[key].number.textContent = data[key]; });
          views.setBadge("requests", data.pending_requests);
          views.setBadge("review", data.reports_in_review);
        }).catch(function () { Object.keys(tiles).forEach(function (key) { tiles[key].number.textContent = "–"; }); });
      }
      loadStats();

      api.renderNotifications(panes.notifications, views.show, function (count) { views.setBadge("notifications", count); }).catch(function () {});
      api.renderProfile(panes.profile);

      // ---- children and their assignments
      var childCard = el("section", "p-card");
      var search = el("input"); search.type = "search"; search.placeholder = m("searchChildren"); search.setAttribute("aria-label", m("searchChildren"));
      var childList = el("div", "p-child-list");
      childCard.appendChild(el("h2", "", t("navMChildren")));
      childCard.appendChild(field(m("searchChildren"), search));
      childCard.appendChild(childList);
      panes.children.appendChild(childCard);
      var children = [], people = {teachers: [], parents: []};
      var groupsList = el("datalist"); groupsList.id = "zm-groups";
      panes.children.appendChild(groupsList);

      function relationName(value) { return m(value) || value; }
      function drawChildren() {
        childList.innerHTML = "";
        var word = search.value.trim().toLowerCase();
        var shown = children.filter(function (child) {
          if (!word) return true;
          return child.display_name.toLowerCase().indexOf(word) !== -1 || child.guardians.some(function (g) { return g.name.toLowerCase().indexOf(word) !== -1; });
        });
        if (!children.length) { childList.appendChild(el("p", "p-muted", m("noChildren"))); return; }
        if (!shown.length) { childList.appendChild(el("p", "p-muted", m("noResult"))); return; }
        shown.forEach(function (child) {
          var card = el("article", "p-card p-child");
          var head = el("div", "p-child-head");
          head.appendChild(el("span", "p-avatar sun", (child.display_name || "?").charAt(0)));
          head.appendChild(el("h3", "", child.display_name));
          if (child.class_name) head.appendChild(el("span", "p-badge", child.class_name));
          card.appendChild(head);

          var groupInput = textInput(child.class_name, 60);
          groupInput.setAttribute("list", "zm-groups");
          var groupRow = el("div", "p-row");
          groupRow.appendChild(field(m("group"), groupInput));
          groupRow.appendChild(api.button(m("save"), "sun", function () {
            request(API + "/children/" + encodeURIComponent(child.id) + "/group", {method: "PATCH", body: JSON.stringify({class_name: groupInput.value.trim()})})
              .then(function () { return reloadChildren(); }).then(function () { loadStats(); }).catch(function (error) { note(card, api.errorMessage(error), "error"); });
          }));
          card.appendChild(groupRow);

          card.appendChild(el("h4", "p-subhead", m("guardians")));
          if (!child.guardians.length) card.appendChild(el("p", "p-muted", m("noGuardians")));
          child.guardians.forEach(function (g) {
            var row = el("div", "p-content-item");
            var text = el("div");
            text.appendChild(el("strong", "", g.name));
            text.appendChild(el("small", "p-muted", relationName(g.relation)));
            row.appendChild(text);
            row.appendChild(el("span", "p-badge" + (g.has_account ? " p-status-active" : ""), g.has_account ? m("withAccount") : m("noAccount")));
            card.appendChild(row);
          });

          function assignment(title, current, options, addLabel, addPath, bodyKey, removePath) {
            card.appendChild(el("h4", "p-subhead", title));
            var chips = el("div", "p-chips");
            if (!current.length) chips.appendChild(el("span", "p-muted", m("none")));
            current.forEach(function (person) {
              var chip = el("span", "p-chip", person.username);
              chip.appendChild(sureButton("×", function () {
                return request(API + "/children/" + encodeURIComponent(child.id) + removePath + encodeURIComponent(person.id), {method: "DELETE"}).then(reloadChildren);
              }, function (error) { note(card, api.errorMessage(error), "error"); }));
              chip.lastChild.setAttribute("aria-label", m("remove") + " " + person.username);
              chips.appendChild(chip);
            });
            card.appendChild(chips);
            var free = options.filter(function (option) { return !current.some(function (person) { return person.id === option.id; }); });
            if (!free.length) return;
            var select = el("select");
            select.setAttribute("aria-label", addLabel);
            select.appendChild(new Option(addLabel, ""));
            free.forEach(function (option) { select.appendChild(new Option(option.username, option.id)); });
            var row = el("div", "p-row");
            var wrap = el("div", "p-field"); wrap.appendChild(select); row.appendChild(wrap);
            row.appendChild(api.button(m("add"), "outline", function () {
              if (!select.value) return;
              var body = {}; body[bodyKey] = select.value;
              request(API + "/children/" + encodeURIComponent(child.id) + addPath, {method: "POST", body: JSON.stringify(body)})
                .then(reloadChildren).catch(function (error) { note(card, api.errorMessage(error), "error"); });
            }));
            card.appendChild(row);
          }
          assignment(m("teachers"), child.teachers, people.teachers, m("addTeacher"), "/teachers", "teacher_id", "/teachers/");
          assignment(m("parents"), child.parent_accounts, people.parents, m("addParent"), "/parents", "parent_id", "/parents/");
          childList.appendChild(card);
        });
      }
      search.addEventListener("input", drawChildren);
      function reloadChildren() {
        return Promise.all([request(API + "/children"), request(API + "/people")]).then(function (results) {
          children = results[0]; people = results[1];
          children.forEach(function (child) { shared.names[child.id] = child.display_name; api.childNames[child.id] = child.display_name; });
          drawChildren();
          return loadGroups();
        }).catch(function (error) { childList.innerHTML = ""; api.showError(childCard, error); });
      }

      // ---- children: add, change, remove (the work of the management, not of the accounting)
      var ACCOUNTING = "/api/admin/accounting";
      var kidsCard = el("section", "p-card");
      kidsCard.appendChild(el("h2", "", m("kidsTitle")));
      kidsCard.appendChild(el("p", "p-muted", m("kidsHelp")));
      var kidForm = el("form", "p-kid-form");
      kidsCard.appendChild(kidForm);
      var kidsMsg = el("p", "p-alert");
      kidsMsg.setAttribute("role", "status");
      kidsCard.appendChild(kidsMsg);
      var kidsListCard = el("section", "p-card");
      kidsListCard.appendChild(el("h2", "", m("kidsList")));
      var kidSearch = el("input"); kidSearch.type = "search"; kidSearch.placeholder = m("searchChildren"); kidSearch.setAttribute("aria-label", m("searchChildren"));
      kidsListCard.appendChild(field(m("searchChildren"), kidSearch));
      var kidsBox = el("div", "p-child-list");
      kidsListCard.appendChild(kidsBox);
      panes.kids.appendChild(kidsCard);
      panes.kids.appendChild(kidsListCard);
      var kids = [], parentAccounts = [];
      var FIRST = function(){ return [["father", m("father")], ["guardian", m("otherGuardian")]]; };
      function kidsNote(text, kind){ kidsMsg.className = "p-alert " + (kind || "success"); kidsMsg.textContent = text; }

      /* father / other guardian, or mother: stays empty when the child has only one parent */
      function guardianBlock(title, relations, saved){
        saved = saved || {};
        var relation = null;
        if(relations.length > 1){
          relation = el("select");
          relations.forEach(function(r){ relation.appendChild(new Option(r[1], r[0])); });
          relation.value = saved.relation || relations[0][0];
        }
        var name = textInput(saved.name, 120); name.placeholder = m("fullName"); name.autocomplete = "off";
        var phone = textInput(saved.phone, 40); phone.type = "tel"; phone.dir = "ltr";
        var email = textInput(saved.email, 254); email.type = "email"; email.dir = "ltr";
        var account = el("select");
        account.appendChild(new Option("— " + m("noLogin") + " —", ""));
        parentAccounts.forEach(function(a){ account.appendChild(new Option(a.username, a.id)); });
        account.value = saved.account_id || "";
        var box = el("fieldset", "p-fieldset");
        box.appendChild(el("legend", "", title));
        if(relation) box.appendChild(field(m("relationLabel"), relation));
        box.appendChild(field(m("fullName"), name)); box.appendChild(field(m("phoneLabel"), phone));
        box.appendChild(field(m("emailLabel"), email)); box.appendChild(field(m("loginAccount"), account));
        return {
          node: box,
          get: function(){
            if(!(name.value.trim() || phone.value.trim() || email.value.trim() || account.value)) return null;
            if(!name.value.trim()) throw new Error(m("nameFor") + title);
            var out = {relation: relation ? relation.value : relations[0][0], name: name.value.trim(), phone: phone.value.trim(), email: email.value.trim(), account_id: account.value || null};
            if(saved.id) out.id = saved.id;
            return out;
          }
        };
      }
      function kidPayload(name, cls, birth, blocks){
        var guardians = blocks.map(function(b){ return b.get(); }).filter(function(g){ return g; });
        if(!guardians.length) throw new Error(m("needGuardian"));
        return {name: name.trim(), class_name: cls.trim(), birth_date: birth || null, guardians: guardians};
      }
      var newName, newClass, newBirth, newFirst, newMother;
      function drawKidForm(){
        newName = textInput("", 120); newName.required = true; newName.autocomplete = "off";
        newClass = textInput("", 60); newClass.setAttribute("list", "zm-groups");
        newBirth = el("input"); newBirth.type = "date"; newBirth.max = new Date().toISOString().slice(0, 10);
        newFirst = guardianBlock(m("father"), FIRST(), null);
        newMother = guardianBlock(m("mother"), [["mother", m("mother")]], null);
        kidForm.innerHTML = "";
        [field(m("childName"), newName), field(m("className"), newClass), field(m("birthDate"), newBirth)].forEach(function(node){ kidForm.appendChild(node); });
        kidForm.appendChild(el("p", "p-muted", m("oneOrBoth")));
        kidForm.appendChild(newFirst.node); kidForm.appendChild(newMother.node);
        var save = el("button", "p-button sun", m("saveChild")); save.type = "submit";
        kidForm.appendChild(save);
      }
      kidForm.addEventListener("submit", function(event){
        event.preventDefault();
        var body;
        try{ body = kidPayload(newName.value, newClass.value, newBirth.value, [newFirst, newMother]); }catch(error){ kidsNote(error.message, "error"); return; }
        request(ACCOUNTING + "/children", {method: "POST", body: JSON.stringify(body)}).then(function(){
          kidsNote(m("childSaved"), "success");
          return reloadKids().then(function(){ drawKidForm(); reloadChildren(); loadStats(); });
        }).catch(function(error){ kidsNote(api.errorMessage(error), "error"); });
      });
      function drawKids(){
        kidsBox.innerHTML = "";
        var word = kidSearch.value.trim().toLowerCase();
        var shown = kids.filter(function(child){
          return !word || child.name.toLowerCase().indexOf(word) !== -1 || child.guardians.some(function(g){ return (g.name + " " + g.phone).toLowerCase().indexOf(word) !== -1; });
        });
        if(!kids.length){ kidsBox.appendChild(el("p", "p-muted", m("noKids"))); return; }
        if(!shown.length){ kidsBox.appendChild(el("p", "p-muted", m("noResult"))); return; }
        shown.forEach(function(child){
          var card = el("article", "p-card p-child");
          var head = el("div", "p-child-head");
          head.appendChild(el("span", "p-avatar sun", (child.name || "?").charAt(0)));
          head.appendChild(el("h3", "", child.name));
          head.appendChild(el("span", "p-badge" + (child.guardians.length === 2 ? " p-status-active" : ""), child.guardians.length === 2 ? m("both") : m("oneGuardian")));
          card.appendChild(head);
          var nameInput = textInput(child.name, 120), clsInput = textInput(child.class_name, 60), birthInput = el("input");
          clsInput.setAttribute("list", "zm-groups");
          birthInput.type = "date"; birthInput.value = child.birth_date || ""; birthInput.max = new Date().toISOString().slice(0, 10);
          var firstSaved = child.guardians.filter(function(g){ return g.relation !== "mother"; })[0];
          var motherSaved = child.guardians.filter(function(g){ return g.relation === "mother"; })[0];
          var first = guardianBlock(m("father"), FIRST(), firstSaved), mother = guardianBlock(m("mother"), [["mother", m("mother")]], motherSaved);
          [field(m("childName"), nameInput), field(m("className"), clsInput), field(m("birthDate"), birthInput), first.node, mother.node].forEach(function(node){ card.appendChild(node); });
          var row = el("div", "p-row");
          row.appendChild(api.button(m("save"), "sun", function(){
            var body;
            try{ body = kidPayload(nameInput.value, clsInput.value, birthInput.value, [first, mother]); }catch(error){ note(card, error.message, "error"); return; }
            request(ACCOUNTING + "/children/" + encodeURIComponent(child.id), {method: "PATCH", body: JSON.stringify(body)})
              .then(function(){ kidsNote(m("saved"), "success"); return reloadKids().then(function(){ reloadChildren(); loadStats(); }); })
              .catch(function(error){ note(card, api.errorMessage(error), "error"); });
          }));
          row.appendChild(sureButton(m("removeFromList"), function(){
            return request(ACCOUNTING + "/children/" + encodeURIComponent(child.id), {method: "DELETE"}).then(function(){ kidsNote(m("childRemoved"), "success"); return reloadKids(); }).then(function(){ reloadChildren(); loadStats(); });
          }, function(error){ note(card, api.errorMessage(error), "error"); }));
          card.appendChild(row);
          kidsBox.appendChild(card);
        });
      }
      kidSearch.addEventListener("input", drawKids);
      function reloadKids(){
        return Promise.all([request(ACCOUNTING + "/children"), request(ACCOUNTING + "/parent-accounts")]).then(function(results){
          kids = results[0]; parentAccounts = results[1];
          if(!kidForm.children.length) drawKidForm();
          drawKids();
        }).catch(function(error){ kidsBox.innerHTML = ""; api.showError(kidsListCard, error); });
      }

      // ---- employees: add, change, remove (the accountant only picks from them)
      var empCard = el("section", "p-card");
      empCard.appendChild(el("h2", "", m("empTitle")));
      empCard.appendChild(el("p", "p-muted", m("empHelp")));
      var empForm = el("form", "p-kid-form");
      empCard.appendChild(empForm);
      var empMsg = el("p", "p-alert");
      empMsg.setAttribute("role", "status");
      empCard.appendChild(empMsg);
      var empListCard = el("section", "p-card");
      empListCard.appendChild(el("h2", "", m("empList")));
      var empBox = el("div", "p-child-list");
      empListCard.appendChild(empBox);
      panes.employees.appendChild(empCard);
      panes.employees.appendChild(empListCard);
      var staffAccounts = [];
      function empNote(text, kind){ empMsg.className = "p-alert " + (kind || "success"); empMsg.textContent = text; }
      function accountSelect(current){
        var select = el("select");
        select.appendChild(new Option("— " + m("noLogin") + " —", ""));
        staffAccounts.forEach(function(a){
          var roles = a.roles.map(function(r){ return r === "teacher" ? m("teacherRole") : m("accountantRole"); }).join(" + ");
          var other = a.linked_to && a.id !== current;
          var option = new Option(a.username + " (" + roles + ")" + (other ? " — " + m("linkedTo") + " " + a.linked_to : ""), a.id);
          option.disabled = !!other;
          select.appendChild(option);
        });
        select.value = current || "";
        return select;
      }
      function currencySelect(value){
        var select = el("select");
        ["SYP", "USD"].forEach(function(code){ select.appendChild(new Option(code, code)); });
        select.value = value || "SYP";
        return select;
      }
      function salaryBody(name, job, salary, currency, account){
        return {name: name.trim(), job_title: job.trim(), salary: salary === "" ? null : salary, salary_currency: currency, account_id: account || null};
      }
      var eName, eJob, eSalary, eCurrency, eAccount;
      function drawEmpForm(){
        eName = textInput("", 120); eName.required = true; eName.placeholder = m("fullName"); eName.autocomplete = "off";
        eJob = textInput("", 80);
        eSalary = el("input"); eSalary.type = "number"; eSalary.min = "0"; eSalary.step = "0.01"; eSalary.inputMode = "decimal";
        eCurrency = currencySelect("SYP"); eAccount = accountSelect("");
        empForm.innerHTML = "";
        [field(m("fullName"), eName), field(m("jobTitle"), eJob), field(m("salaryLabel"), eSalary), field(m("salaryCurrency"), eCurrency), field(m("empAccount"), eAccount)].forEach(function(node){ empForm.appendChild(node); });
        var save = el("button", "p-button sun", m("saveEmp")); save.type = "submit";
        empForm.appendChild(save);
      }
      empForm.addEventListener("submit", function(event){
        event.preventDefault();
        var body = salaryBody(eName.value, eJob.value, eSalary.value, eCurrency.value, eAccount.value);
        if(body.salary === null){ delete body.salary; }
        request(ACCOUNTING + "/employees", {method: "POST", body: JSON.stringify(body)}).then(function(){
          empNote(m("empSaved"), "success");
          return reloadEmployees().then(function(){ drawEmpForm(); });
        }).catch(function(error){ empNote(api.errorMessage(error), "error"); });
      });
      function drawEmployees(list){
        empBox.innerHTML = "";
        if(!list.length){ empBox.appendChild(el("p", "p-muted", m("noEmp"))); return; }
        list.forEach(function(person){
          var card = el("article", "p-card p-child");
          var head = el("div", "p-child-head");
          head.appendChild(el("span", "p-avatar sun", (person.name || "?").charAt(0)));
          head.appendChild(el("h3", "", person.name));
          if(person.account_username) head.appendChild(el("span", "p-badge p-status-active", person.account_username));
          card.appendChild(head);
          var nameInput = textInput(person.name, 120), jobInput = textInput(person.job_title, 80);
          var salaryInput = el("input"); salaryInput.type = "number"; salaryInput.min = "0"; salaryInput.step = "0.01"; salaryInput.inputMode = "decimal"; salaryInput.value = person.salary || "";
          var currencyInput = currencySelect(person.salary_currency), accountInput = accountSelect(person.account_id);
          [field(m("fullName"), nameInput), field(m("jobTitle"), jobInput), field(m("salaryLabel"), salaryInput), field(m("salaryCurrency"), currencyInput), field(m("empAccount"), accountInput)].forEach(function(node){ card.appendChild(node); });
          var row = el("div", "p-row");
          row.appendChild(api.button(m("save"), "sun", function(){
            request(ACCOUNTING + "/employees/" + encodeURIComponent(person.id), {method: "PATCH", body: JSON.stringify(salaryBody(nameInput.value, jobInput.value, salaryInput.value, currencyInput.value, accountInput.value))})
              .then(function(saved){ empNote(m("saved") + (saved.updated_salary_rows ? " " + m("followed").replace("{n}", saved.updated_salary_rows) : ""), "success"); return reloadEmployees(); })
              .catch(function(error){ note(card, api.errorMessage(error), "error"); });
          }));
          row.appendChild(sureButton(m("removeFromList"), function(){
            return request(ACCOUNTING + "/employees/" + encodeURIComponent(person.id), {method: "DELETE"}).then(function(){ empNote(m("empRemoved"), "success"); return reloadEmployees(); });
          }, function(error){ note(card, api.errorMessage(error), "error"); }));
          card.appendChild(row);
          empBox.appendChild(card);
        });
      }
      function reloadEmployees(){
        return Promise.all([request(ACCOUNTING + "/employees"), request(ACCOUNTING + "/staff-accounts")]).then(function(results){
          staffAccounts = results[1];
          if(!empForm.children.length) drawEmpForm();
          drawEmployees(results[0]);
        }).catch(function(error){ empBox.innerHTML = ""; api.showError(empListCard, error); });
      }

      // ---- groups
      var groupCard = el("section", "p-card");
      groupCard.appendChild(el("h2", "", m("groupsTitle")));
      groupCard.appendChild(el("p", "p-muted", m("groupsHelp")));
      var groupBox = el("div", "p-content-list");
      groupCard.appendChild(groupBox);
      panes.groups.appendChild(groupCard);
      function loadGroups() {
        return request(API + "/groups").then(function (groups) {
          shared.groups = groups;
          groupsList.innerHTML = "";
          groups.forEach(function (group) { groupsList.appendChild(new Option(group.name, group.name)); });
          groupBox.innerHTML = "";
          if (!groups.length) groupBox.appendChild(el("p", "p-muted", m("noGroups")));
          groups.forEach(function (group) {
            var row = el("div", "p-content-item");
            var name = textInput(group.name, 60);
            name.setAttribute("aria-label", m("rename"));
            row.appendChild(name);
            row.appendChild(el("span", "p-badge", group.children + " " + m("childrenCount")));
            row.appendChild(api.button(m("rename"), "outline", function () {
              var next = name.value.trim();
              if (!next || next === group.name) return;
              request(API + "/groups/rename", {method: "POST", body: JSON.stringify({old_name: group.name, new_name: next})})
                .then(reloadChildren).catch(function (error) { note(groupCard, api.errorMessage(error), "error"); });
            }));
            groupBox.appendChild(row);
          });
        }).catch(function (error) { groupBox.innerHTML = ""; api.showError(groupCard, error); });
      }

      // ---- registration requests
      var requestCard = el("section", "p-card");
      requestCard.appendChild(el("h2", "", m("requestsTitle")));
      var requestBox = el("div", "p-content-list");
      requestCard.appendChild(requestBox);
      panes.requests.appendChild(requestCard);
      function statusText(item) { return item.registered ? m("registered") : m(item.status); }
      function codeBox(result) {
        var box = el("div", "p-code");
        box.appendChild(el("strong", "", m("codeTitle")));
        box.appendChild(el("code", "", result.registration_code));
        box.appendChild(el("small", "p-muted", result.request && result.request.email_sent ? m("codeSent") : m("codeNotSent")));
        return box;
      }
      function loadRequests() {
        return request(API + "/registration-requests").then(function (items) {
          requestBox.innerHTML = "";
          items.sort(function (a, b) { return (a.status === "pending" ? 0 : 1) - (b.status === "pending" ? 0 : 1); });
          if (!items.length) requestBox.appendChild(el("p", "p-muted", m("noRequests")));
          items.forEach(function (item) {
            var card = el("article", "p-report");
            var meta = el("div", "p-report-meta");
            meta.appendChild(el("span", "p-badge" + (item.status === "approved" ? " p-status-active" : item.status === "pending" ? " p-hidden" : ""), statusText(item)));
            meta.appendChild(el("small", "p-muted", api.dateLabel(item.created_at)));
            card.appendChild(meta);
            card.appendChild(el("h3", "", item.guardian_name));
            [[m("childOf"), item.child_name + (item.child_birth_date ? " (" + item.child_birth_date + ")" : "")], [m("relation"), item.relationship_to_child],
             [m("phone"), item.phone], [m("email"), item.email], [m("notes"), item.notes]].forEach(function (pair) {
              if (!pair[1]) return;
              var line = el("p", "p-detail");
              line.appendChild(el("strong", "", pair[0] + ": "));
              line.appendChild(document.createTextNode(pair[1]));
              card.appendChild(line);
            });
            var actions = el("div", "p-row");
            function decide(decision) {
              request(API + "/registration-requests/" + encodeURIComponent(item.id) + "/decision", {method: "POST", body: JSON.stringify({decision: decision})})
                .then(function (result) { loadStats(); return loadRequests().then(function () { if (result.registration_code) requestBox.insertBefore(codeBox(result), requestBox.firstChild); }); })
                .catch(function (error) { note(card, api.errorMessage(error), "error"); });
            }
            if (item.status === "pending") {
              actions.appendChild(api.button(m("approve"), "sun", function () { decide("approve"); }));
              actions.appendChild(sureButton(m("reject"), function () { decide("reject"); }, function (error) { note(card, api.errorMessage(error), "error"); }));
            } else if (item.status === "approved" && !item.registered) {
              actions.appendChild(api.button(m("newCode"), "outline", function () {
                request(API + "/registration-requests/" + encodeURIComponent(item.id) + "/new-code", {method: "POST"}).then(function (result) {
                  if (result.registration_code) requestBox.insertBefore(codeBox(result), requestBox.firstChild);
                }).catch(function (error) { note(card, api.errorMessage(error), "error"); });
              }));
            }
            card.appendChild(actions);
            requestBox.appendChild(card);
          });
        }).catch(function (error) { requestBox.innerHTML = ""; api.showError(requestCard, error); });
      }

      // ---- notices
      var noticeCard = el("section", "p-card");
      noticeCard.appendChild(el("h2", "", m("noticesTitle")));
      var form = el("form");
      var noticeTitle = textInput("", 120); noticeTitle.required = true;
      var noticeBody = el("textarea"); noticeBody.maxLength = 2000;
      form.appendChild(field(m("noticeTitle"), noticeTitle));
      form.appendChild(field(m("noticeBody"), noticeBody));
      var publish = el("button", "p-button sun", m("publish")); publish.type = "submit";
      form.appendChild(publish);
      noticeCard.appendChild(form);
      var listCard = el("section", "p-card");
      listCard.appendChild(el("h2", "", m("myNotices")));
      var noticeBox = el("div", "p-content-list");
      listCard.appendChild(noticeBox);
      panes.notices.appendChild(noticeCard);
      panes.notices.appendChild(listCard);
      function loadNotices() {
        return request("/api/platform/announcements").then(function (items) {
          noticeBox.innerHTML = "";
          if (!items.length) noticeBox.appendChild(el("p", "p-muted", m("noNotices")));
          items.forEach(function (item) {
            var row = el("div", "p-content-item");
            var text = el("div");
            text.appendChild(el("strong", "", item.title));
            text.appendChild(el("small", "p-muted", api.dateLabel(item.created_at)));
            if (item.body) text.appendChild(el("p", "p-muted", item.body));
            row.appendChild(text);
            row.appendChild(sureButton(m("delete"), function () {
              return request(API + "/announcements/" + encodeURIComponent(item.id), {method: "DELETE"}).then(loadNotices);
            }, function (error) { note(listCard, api.errorMessage(error), "error"); }));
            noticeBox.appendChild(row);
          });
        }).catch(function (error) { noticeBox.innerHTML = ""; api.showError(listCard, error); });
      }
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        publish.disabled = true;
        request(API + "/announcements", {method: "POST", body: JSON.stringify({title: noticeTitle.value.trim(), body: noticeBody.value.trim()})}).then(function () {
          noticeTitle.value = ""; noticeBody.value = "";
          note(noticeCard, m("published"), "success");
          return loadNotices();
        }).catch(function (error) { note(noticeCard, api.errorMessage(error), "error"); }).finally(function () { publish.disabled = false; });
      });

      // ---- report approval (the names of the children come from the children list)
      reloadKids();
      reloadEmployees();
      reloadChildren().then(function () { api.loadReviewQueue(panes.review); });
      loadRequests();
      loadNotices();
    };
  };
}());
