(function () {
  "use strict";

  var root = document.getElementById("portal");
  var portalType = root.dataset.portal;
  var isLogin = portalType === "login";
  var isManagerPortal = portalType === "manager";
  var isTeacherPortal = portalType === "teacher" || isManagerPortal;
  var storeKey = isManagerPortal ? "zm-manager-session" : isTeacherPortal ? "zm-teacher-session" : "zm-parent-session";
  var langKey = isLogin ? "zm-login-lang" : isManagerPortal ? "zm-manager-lang" : isTeacherPortal ? "zm-teacher-lang" : "zm-parent-lang";
  var PORTAL_TARGETS = {
    admin: {key: "zm-admin-session", lang: "zm-admin-lang", url: "../admin/"},
    teacher: {key: "zm-teacher-session", lang: "zm-teacher-lang", url: "../teachers/"},
    manager: {key: "zm-manager-session", lang: "zm-manager-lang", url: "../management/"},
    parent: {key: "zm-parent-session", lang: "zm-parent-lang", url: "../parents/"},
    accountant: {key: "zm-accountant-session", lang: "zm-accountant-lang", url: "../admin/"}
  };
  var token = sessionStorage.getItem(storeKey) || "";
  var lang = localStorage.getItem(langKey) === "en" ? "en" : "ar";
  var profile = null;
  var signupMode = false;
  var requestMode = false;
  var requestForm = {guardian_name: "", email: "", phone: "", child_name: "", child_birth_date: "", relationship_to_child: "", notes: ""};
  var editingReportId = "";
  var teacherControls = null;
  var formState = {username:"", password:"", invitation_code:"", child_id:"", title:"", body:"", activities:"", meals:""};
  var loginAlert = "";
  var expiredNotice = false;
  (function readCodeFromLink() {
    var query = new URLSearchParams(window.location.search);
    if (query.get("expired")) { expiredNotice = true; history.replaceState(null, "", window.location.pathname); }
    var code = query.get("code");
    if (!code || !/^[A-Za-z0-9_-]{6,64}$/.test(code)) return;
    signupMode = true;
    formState.invitation_code = code;
    history.replaceState(null, "", window.location.pathname);
  })();
  var apiBase = (window.ZM_API_BASE || (/^(localhost|127.0.0.1)$/.test(location.hostname) ? "http://127.0.0.1:8001" : "https://zahra-123hub-almadain-api.onrender.com")).replace(/\/+$/, "");
  var copy = window.ZM_TEXT.copy, NOTIF = window.ZM_TEXT.NOTIF, ROLE_NAMES = window.ZM_TEXT.ROLE_NAMES;
  var t = function (key) { return copy[lang][key] || key; };
  /* ---- password helpers: strength meter, show/hide, Caps Lock warning ---- */
  var COMMON_PASSWORDS = ["password", "passw0rd", "qwertyuiop", "qwerty", "asdfghjkl", "zxcvbnm", "iloveyou", "welcome", "letmein", "admin", "administrator",
    "changeme", "abc123", "123456789012", "1234567890", "zahra", "zahrat", "zahratalmadain", "almadain", "kindergarten", "damascus", "syria"];
  function passwordRules(pw, user) {
    var lowered = pw.toLowerCase().replace(/\s/g, "");
    var stripped = lowered.replace(/[0-9!@#$%^&*._-]+$/, "");
    var common = COMMON_PASSWORDS.indexOf(lowered) !== -1 || COMMON_PASSWORDS.indexOf(stripped) !== -1;
    var uniq = {}; pw.split("").forEach(function (c) { uniq[c] = true; });
    return [
      {ok: pw.length >= 12, label: t("ruleLength")},
      {ok: pw.length > 0 && !common, label: t("ruleCommon")},
      {ok: pw.length > 0 && !(user && user.length >= 3 && lowered.indexOf(user) !== -1), label: t("ruleUser")},
      {ok: pw.length > 0 && !/^\d+$/.test(pw) && Object.keys(uniq).length >= 6, label: t("ruleVariety")}
    ];
  }
  function strengthMeter(input, getUser, container) {
    var box = element("div", "p-meter");
    var bar = element("div", "p-meter-bar");
    var fill = element("span");
    bar.appendChild(fill);
    var caption = element("small", "p-meter-text");
    var list = element("ul", "p-rules");
    box.appendChild(bar); box.appendChild(caption); box.appendChild(list);
    function update() {
      var pw = input.value;
      var rules = passwordRules(pw, getUser());
      var passed = rules.filter(function (r) { return r.ok; }).length;
      var classes = [/[a-z]/, /[A-Z]/, /\d/, /[^A-Za-z0-9]/].filter(function (re) { return re.test(pw); }).length;
      var score = passed === rules.length ? (pw.length >= 16 && classes >= 3 ? 3 : 2) : (passed >= 3 ? 1 : 0);
      fill.style.width = (pw ? (score + 1) * 25 : 0) + "%";
      box.className = "p-meter level-" + (pw ? score : "none");
      caption.textContent = pw ? t("strengthLabel") + ": " + t(score >= 3 ? "strengthStrong" : score === 2 ? "strengthMedium" : "strengthWeak") : "";
      list.innerHTML = "";
      rules.forEach(function (r) { var li = element("li", r.ok ? "ok" : "", (r.ok ? "✓ " : "• ") + r.label); list.appendChild(li); });
    }
    input.addEventListener("input", update);
    update();
    container.appendChild(box);
    return update;
  }
  function decoratePassword(label, input) {
    var toggle = element("button", "p-eye", t("showPassword"));
    toggle.type = "button";
    toggle.addEventListener("click", function () {
      var show = input.type === "password";
      input.type = show ? "text" : "password";
      toggle.textContent = show ? t("hidePassword") : t("showPassword");
    });
    var caps = element("small", "p-caps", t("capsOn"));
    caps.hidden = true;
    function checkCaps(event) { caps.hidden = !(event.getModifierState && event.getModifierState("CapsLock")); }
    input.addEventListener("keydown", checkCaps);
    input.addEventListener("keyup", checkCaps);
    input.addEventListener("blur", function () { caps.hidden = true; });
    label.appendChild(toggle);
    label.appendChild(caps);
  }
  function toggleChangePassword() {
    var main = root.querySelector("main");
    if (!main) return;
    var existing = main.querySelector(".p-change-password");
    if (existing) { existing.remove(); return; }
    var card = element("section", "p-card p-change-password");
    card.appendChild(element("h2", "", t("changePassword")));
    var form = element("form");
    function secret(labelText, autocomplete) {
      var wrap = element("div", "p-field");
      var label = element("label", "", labelText);
      var input = element("input");
      input.type = "password"; input.required = true; input.autocomplete = autocomplete;
      label.appendChild(input); wrap.appendChild(label); form.appendChild(wrap);
      decoratePassword(label, input);
      return input;
    }
    var current = secret(t("currentPassword"), "current-password");
    var fresh = secret(t("password"), "new-password");
    strengthMeter(fresh, function () { return (profile && profile.username || "").toLowerCase(); }, fresh.parentNode.parentNode);
    var again = secret(t("repeatPassword"), "new-password");
    var message = element("p", "p-alert");
    message.setAttribute("role", "alert");
    var save = element("button", "p-button sun", t("save"));
    save.type = "submit";
    var cancel = button(t("cancel"), "outline", function () { card.remove(); });
    form.appendChild(save); form.appendChild(cancel); form.appendChild(message);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      message.className = "p-alert error";
      if (fresh.value !== again.value) { message.textContent = t("passwordMismatch"); return; }
      save.disabled = true;
      request("/api/platform/auth/change-password", {method: "POST", body: JSON.stringify({current_password: current.value, new_password: fresh.value})}).then(function () {
        current.value = fresh.value = again.value = "";
        message.className = "p-alert success";
        message.textContent = t("passwordChanged");
      }).catch(function (error) { message.textContent = errorMessage(error); }).finally(function () { save.disabled = false; });
    });
    card.appendChild(form);
    main.insertBefore(card, main.firstChild);
    current.focus();
  }
  function portalLabel(name) {
    return name === "manager" ? t("managerTitle") : name === "teacher" ? t("teacherTitle") : name === "parent" ? t("parentTitle") : name === "accountant" ? t("accountantTitle") : name;
  }
  function otherPortals() {
    var list = [];
    try { list = JSON.parse(sessionStorage.getItem("zm-portals") || "[]"); } catch (e) {}
    var current = isManagerPortal ? "manager" : isTeacherPortal ? "teacher" : "parent";
    return list.filter(function (name) { return name !== current && PORTAL_TARGETS[name] && name !== "admin"; });
  }
  function portalTitle() { return isLogin ? t("loginTitle") : isManagerPortal ? t("managerTitle") : isTeacherPortal ? t("teacherTitle") : t("parentTitle"); }
  var element = function (tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  };
  function setLanguage(next) {
    lang = next === "en" ? "en" : "ar";
    localStorage.setItem(langKey, lang);
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    if (token) {
      request("/api/platform/auth/language", {
        method: "PATCH",
        body: JSON.stringify({language: lang})
      }).catch(function (error) { loginAlert = errorMessage(error); });
    }
    render();
  }
  function button(label, className, onClick) {
    var node = element("button", "p-button " + (className || ""), label);
    node.type = "button";
    node.addEventListener("click", onClick);
    return node;
  }
  function request(path, options) {
    options = options || {};
    var headers = new Headers(options.headers || {});
    if (token) headers.set("Authorization", "Bearer " + token);
    var isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    if (options.body && !isFormData && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    return fetch(apiBase + path, Object.assign({}, options, {headers: headers})).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (body) {
        if (!response.ok) throw new Error(body.detail || t("genericError"));
        return body;
      });
    });
  }
  function errorMessage(error) {
    var localized = API_ERROR[error.message];
    if (localized) return localized[lang];
    if (error instanceof TypeError) return t("networkError");
    return error.message || t("genericError");
  }
  function header() {
    var bar = element("header", "p-header");
    var inner = element("div", "p-header-inner");
    var brand = element("a", "p-brand");
    brand.href = "/";
    var logo = element("img");
    logo.src = "../images/logo.png?v=2";
    logo.alt = "";
    brand.appendChild(logo);
    var brandText = element("div");
    brandText.appendChild(element("h1", "", portalTitle()));
    brandText.appendChild(element("span", "", t("school")));
    brand.appendChild(brandText);
    inner.appendChild(brand);
    var actions = element("div", "p-actions");
    if (profile) {
      var identity = element("div", "p-account-identity");
      actions.appendChild(element("span", "p-avatar", (profile.username || "?").charAt(0).toUpperCase()));
      identity.appendChild(element("span", "p-account-label", t("welcomeUser")));
      identity.appendChild(element("strong", "", profile.username));
      actions.appendChild(identity);
    }
    var langGroup = element("div", "p-lang");
    langGroup.setAttribute("role", "group");
    langGroup.setAttribute("aria-label", t("language"));
    [["ar", "العربية"], ["en", "English"]].forEach(function (choice) {
      var languageButton = element("button", "", choice[1]);
      languageButton.lang = choice[0];
      languageButton.type = "button";
      languageButton.setAttribute("aria-pressed", String(lang === choice[0]));
      languageButton.addEventListener("click", function () { setLanguage(choice[0]); });
      langGroup.appendChild(languageButton);
    });
    actions.appendChild(langGroup);
    if (token && !isLogin) {
      otherPortals().forEach(function (name) {
        var other = element("a", "p-button outline", portalLabel(name));
        other.href = PORTAL_TARGETS[name].url;
        other.title = t("switchPortal");
        actions.appendChild(other);
      });
    }
    if (token && profile && !isLogin) actions.appendChild(button(t("changePassword"), "outline", toggleChangePassword));
    if (token && isTeacherPortal && !isManagerPortal) {
      var publishLink = element("a", "p-button sun", t("publishSite"));
      publishLink.href = "../admin/";
      actions.appendChild(publishLink);
    }
    if (token) actions.appendChild(button(t("logout"), "outline", logout));
    inner.appendChild(actions);
    bar.appendChild(inner);
    return bar;
  }
  function shell() {
    root.innerHTML = "";
    root.appendChild(header());
    var main = element("main", "p-main");
    root.appendChild(main);
    return main;
  }
  function showError(container, error) {
    var msg = element("p", "p-alert error", errorMessage(error));
    msg.setAttribute("role", "alert");
    container.appendChild(msg);
  }
  function loginScreen() {
    if (!isLogin) { window.location.replace("../login/"); return; }
    if (expiredNotice) { loginAlert = t("sessionExpired"); expiredNotice = false; }
    var main = shell();
    main.classList.add("p-auth-main");
    var layout = element("div", "p-auth-layout");
    var intro = element("section", "p-auth-intro");
    intro.appendChild(element("span", "p-auth-kicker", t("secureAccess")));
    intro.appendChild(element("h2", "", portalTitle()));
    intro.appendChild(element("p", "", isLogin ? t("loginIntro") : isManagerPortal ? t("managerWelcome") : isTeacherPortal ? t("teacherPortalIntro") : t("parentPortalIntro")));
    intro.appendChild(element("div", "p-auth-note", isTeacherPortal ? t("signInHint") : t("parentSignupHint")));
    layout.appendChild(intro);
    var card = element("section", "p-card p-auth-card");
    card.appendChild(element("h2", "", portalTitle()));
    card.appendChild(element("p", "p-subtitle", t("signInHint")));
    var error = element("p", "p-alert error");
    error.setAttribute("role", "alert");
    function drawForm() {
      card.querySelectorAll("form,.p-form-switch,.p-alert").forEach(function (node) { node.remove(); });
      if (requestMode) { drawRequestForm(); return; }
      var form = element("form");
      var username = field(signupMode ? t("newUsername") : t("username"), "text", "username");
      username.autocomplete = "username";
      if (signupMode) { username.pattern = "[A-Za-z0-9_.\-]{3,80}"; username.dir = "ltr"; username.autocapitalize = "none"; }
      username.required = true;
      username.minLength = 3;
      username.value = formState.username;
      username.addEventListener("input", function () { formState.username = username.value; });
      var password = field(signupMode ? t("newPassword") : t("password"), "password", signupMode ? "new-password" : "current-password");
      password.required = true;
      password.minLength = signupMode ? 12 : 1;
      password.value = formState.password;
      password.addEventListener("input", function () { formState.password = password.value; });
      form.appendChild(username.parentNode.parentNode);
      form.appendChild(password.parentNode.parentNode);
      var invite = null;
      var confirm = null;
      if (signupMode) {
        invite = field(t("invite"), "text", "off");
        invite.required = true;
        invite.minLength = 6;
        invite.maxLength = 64;
        invite.dir = "ltr";
        invite.placeholder = "XXXX-XXXX";
        invite.style.textTransform = "uppercase";
        invite.style.letterSpacing = ".12em";
        invite.value = formState.invitation_code;
        invite.addEventListener("input", function () { formState.invitation_code = invite.value; });
        form.insertBefore(invite.parentNode.parentNode, username.parentNode.parentNode);
        username.parentNode.appendChild(element("small", "p-muted", t("usernameRule")));
        password.parentNode.appendChild(element("small", "p-muted", t("passwordRule")));
        strengthMeter(password, function () { return username.value.trim().toLowerCase(); }, password.parentNode);
        confirm = field(t("confirmPassword"), "password", "new-password");
        confirm.required = true;
        confirm.minLength = 12;
        form.appendChild(confirm.parentNode.parentNode);
        var heading = element("div", "p-finish-intro");
        heading.appendChild(element("h3", "", t("finishTitle")));
        heading.appendChild(element("p", "p-muted", t("finishHint")));
        form.insertBefore(heading, form.firstChild);
      }
      var submit = element("button", "p-button sun", signupMode ? t("createAccount") : t("signIn"));
      submit.type = "submit";
      form.appendChild(submit);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        error.textContent = "";
        if (signupMode && password.value !== confirm.value) { error.className = "p-alert error"; error.textContent = t("passwordMismatch"); return; }
        submit.disabled = true;
        submit.classList.add("p-loading");
        var path = signupMode ? "/api/platform/auth/redeem-invitation" : isLogin ? "/api/auth/entry" : "/api/platform/auth/login";
        var payload = {username: username.value.trim(), password: password.value};
        if (signupMode) {
          payload.invitation_code = invite.value.trim();
          payload.preferred_language = lang;
        }
        request(path, {method: "POST", body: JSON.stringify(payload)}).then(function (result) {
          if (signupMode) {
            var chosen = {username: username.value.trim(), password: password.value};
            signupMode = false;
            formState.password = "";
            formState.invitation_code = "";
            if (result.approval_status === "active" && isLogin) {
              // The code was issued by the kindergarten, so the account is ready: sign in right away.
              return request("/api/auth/entry", {method: "POST", body: JSON.stringify(chosen)}).then(enterPortals);
            }
            loginAlert = result.approval_status === "active" ? t("accountReadyNotice") : t("approvalPendingNotice");
            drawForm();
            return;
          }
          formState.password = "";
          if (isLogin) {
            enterPortals(result);
            return;
          }
          token = result.access_token;
          sessionStorage.setItem(storeKey, token);
          return loadDashboard();
        }).catch(function (err) {
          error.textContent = errorMessage(err);
          submit.disabled = false;
          submit.classList.remove("p-loading");
        });
      });
      card.appendChild(form);
      card.appendChild(error);
      if (loginAlert) {
        error.className = "p-alert success";
        error.textContent = loginAlert;
        loginAlert = "";
      }
      if (!isTeacherPortal) {
        card.appendChild(button(signupMode ? t("switchLogin") : t("switchSignup"), "outline p-form-switch", function () {
          signupMode = !signupMode;
          error.className = "p-alert error";
          drawForm();
        }));
        card.appendChild(button(t("switchRequest"), "outline p-form-switch", function () {
          requestMode = true;
          signupMode = false;
          error.className = "p-alert error";
          drawForm();
        }));
      }
    }
    function drawRequestForm() {
      var form = element("form");
      var openedAt = Date.now();
      var trap = element("input");  // humans never see or fill this field; bots do
      trap.type = "text"; trap.name = "website"; trap.tabIndex = -1; trap.autocomplete = "off";
      trap.setAttribute("aria-hidden", "true");
      trap.style.cssText = "position:absolute;left:-9999px;width:1px;height:1px;opacity:0";
      form.appendChild(trap);
      form.appendChild(element("h3", "", t("requestTitle")));
      form.appendChild(element("p", "p-muted", t("requestHint")));
      var inputs = {};
      [
        ["guardian_name", "guardianName", "text", "name", true],
        ["email", "email", "email", "email", true],
        ["phone", "phone", "tel", "tel", true],
        ["child_name", "childName", "text", "off", true],
        ["child_birth_date", "childBirth", "date", "off", false],
        ["relationship_to_child", "relationship", "text", "off", false],
        ["notes", "notes", "textarea", "off", false]
      ].forEach(function (spec) {
        var wrap = element("div", "p-field");
        var label = element("label", "", t(spec[1]));
        var input = element(spec[2] === "textarea" ? "textarea" : "input");
        if (spec[2] === "textarea") { input.rows = 3; input.maxLength = 1000; input.style.minHeight = "90px"; }
        else { input.type = spec[2]; }
        input.autocomplete = spec[3];
        input.required = spec[4];
        if (spec[0] === "guardian_name" || spec[0] === "child_name") input.minLength = 2;
        if (spec[0] === "phone") { input.minLength = 6; input.pattern = "[0-9+()\\-\\s]{6,40}"; input.dir = "ltr"; }
        if (spec[0] === "email") input.dir = "ltr";
        input.value = requestForm[spec[0]];
        input.addEventListener("input", function () { requestForm[spec[0]] = input.value; });
        label.appendChild(input);
        wrap.appendChild(label);
        form.appendChild(wrap);
        inputs[spec[0]] = input;
      });
      var submit = element("button", "p-button sun", t("sendRequest"));
      submit.type = "submit";
      form.appendChild(submit);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        submit.disabled = true;
        error.textContent = "";
        var payload = {preferred_language: lang, website: trap.value, form_age_ms: Date.now() - openedAt};
        Object.keys(requestForm).forEach(function (key) { payload[key] = requestForm[key].trim(); });
        request("/api/platform/registration-requests", {method: "POST", body: JSON.stringify(payload)}).then(function () {
          Object.keys(requestForm).forEach(function (key) { requestForm[key] = ""; });
          requestMode = false;
          loginAlert = t("requestSent");
          drawForm();
        }).catch(function (err) {
          error.className = "p-alert error";
          error.textContent = errorMessage(err);
          submit.disabled = false;
          submit.classList.remove("p-loading");
        });
      });
      card.appendChild(form);
      card.appendChild(error);
      card.appendChild(button(t("switchLogin"), "outline p-form-switch", function () {
        requestMode = false;
        error.className = "p-alert error";
        drawForm();
      }));
    }
    /* One role: straight to its portal. Several roles: the user picks (one session works for all). */
    function enterPortals(result) {
      var portals = (result.portals && result.portals.length ? result.portals : [result.role]).filter(function (name) { return PORTAL_TARGETS[name]; });
      if (!portals.length) throw new Error(t("accessDenied"));
      try { sessionStorage.setItem("zm-portals", JSON.stringify(portals)); } catch (e) {}
      portals.forEach(function (name) {
        sessionStorage.setItem(PORTAL_TARGETS[name].key, result.access_token);
        localStorage.setItem(PORTAL_TARGETS[name].lang, lang);
      });
      if (portals.length === 1) { window.location.href = PORTAL_TARGETS[portals[0]].url; return; }
      card.innerHTML = "";
      card.appendChild(element("h2", "", t("chooseTitle")));
      card.appendChild(element("p", "p-subtitle", t("chooseHint")));
      portals.forEach(function (name) {
        var link = element("a", "p-button sun p-portal-choice", portalLabel(name));
        link.href = PORTAL_TARGETS[name].url;
        card.appendChild(link);
      });
    }
    function field(labelText, type, autocomplete) {
      var wrap = element("div", "p-field");
      var label = element("label", "", labelText);
      var input = element("input");
      input.type = type;
      if (autocomplete) input.autocomplete = autocomplete;
      label.appendChild(input);
      wrap.appendChild(label);
      if (type === "password") decoratePassword(label, input);
      return input;
    }
    drawForm();
    var back = element("a", "p-muted", t("backToWebsite"));
    back.href = "/";
    card.appendChild(back);
    layout.appendChild(card);
    main.appendChild(layout);
  }
  var activeView = "home";
  var childNames = {};
  function viewShell(main, defs) {
    var nav = element("nav", "p-nav");
    nav.setAttribute("aria-label", t("navLabel"));
    var panes = {};
    function show(key) {
      if (!panes[key]) return;
      activeView = key;
      Object.keys(panes).forEach(function (name) { panes[name].hidden = name !== key; });
      Array.prototype.forEach.call(nav.children, function (item) {
        if (item.dataset.view === key) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
      });
    }
    defs.forEach(function (def) {
      var item = element("button", "p-nav-item", t(def[1]));
      item.type = "button";
      item.dataset.view = def[0];
      item.addEventListener("click", function () { show(def[0]); window.scrollTo(0, 0); });
      nav.appendChild(item);
      panes[def[0]] = element("div", "p-view");
    });
    main.appendChild(nav);
    defs.forEach(function (def) { main.appendChild(panes[def[0]]); });
    if (!panes[activeView]) activeView = defs[0][0];
    show(activeView);
    function setBadge(key, count) {
      Array.prototype.forEach.call(nav.children, function (item) {
        if (item.dataset.view !== key) return;
        var old = item.querySelector(".p-count");
        if (old) old.remove();
        if (count > 0) item.appendChild(element("span", "p-count", count > 99 ? "99+" : String(count)));
      });
    }
    return {panes: panes, show: show, setBadge: setBadge};
  }
  function statTile(label, view, goto) {
    var tile = element("button", "p-stat");
    tile.type = "button";
    var number = element("strong", "", "…");
    tile.appendChild(number);
    tile.appendChild(element("span", "", label));
    tile.addEventListener("click", function () { goto(view); window.scrollTo(0, 0); });
    tile.number = number;
    return tile;
  }
  function dateLabel(value) { return value ? new Date(value).toLocaleDateString(lang === "ar" ? "ar" : "en") : ""; }
  function notificationText(item) {
    var map = NOTIF[lang] || NOTIF.ar;
    return (map[item.kind] || item.kind).replace("{s}", item.subject || "");
  }
  function renderNotifications(pane, goto, onCount) {
    var card = element("section", "p-card");
    var head = element("div", "p-row p-between");
    head.appendChild(element("h2", "", t("notifTitle")));
    var markAll = button(t("markAll"), "outline", function () {
      request("/api/platform/notifications/read-all", {method: "POST"}).then(load).catch(function (error) { showError(card, error); });
    });
    head.appendChild(markAll);
    card.appendChild(head);
    var list = element("div", "p-notif-list");
    card.appendChild(list);
    pane.appendChild(card);
    function load() {
      return request("/api/platform/notifications").then(function (data) {
        if (onCount) onCount(data.unread);
        list.innerHTML = "";
        markAll.hidden = !data.unread;
        if (!data.items.length) { list.appendChild(element("p", "p-muted", t("noNotifications"))); return; }
        data.items.forEach(function (item) {
          var row = element("button", "p-notif" + (item.read ? "" : " unread"));
          row.type = "button";
          row.appendChild(element("span", "p-notif-text", notificationText(item)));
          row.appendChild(element("small", "p-muted", dateLabel(item.created_at)));
          row.addEventListener("click", function () {
            var done = item.read ? Promise.resolve() : request("/api/platform/notifications/" + encodeURIComponent(item.id) + "/read", {method: "POST"});
            done.then(function () { if (item.view) goto(item.view); return load(); }).catch(function (error) { showError(card, error); });
          });
          list.appendChild(row);
        });
      }).catch(function (error) { list.innerHTML = ""; showError(card, error); });
    }
    list.appendChild(element("p", "p-muted", t("loading")));
    return load();
  }
  function renderProfile(pane) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", t("profileTitle")));
    var facts = element("dl", "p-facts");
    function fact(label, value) { facts.appendChild(element("dt", "", label)); facts.appendChild(element("dd", "", value)); }
    fact(t("username"), profile.username);
    var names = ROLE_NAMES[lang] || ROLE_NAMES.ar;
    fact(t("roleLabel"), profile.roles.map(function (role) { return names[role] || role; }).join(lang === "ar" ? "، " : ", "));
    card.appendChild(facts);
    var langRow = element("div", "p-row");
    langRow.appendChild(element("span", "p-muted", t("languageLabel")));
    [["ar", "العربية"], ["en", "English"]].forEach(function (choice) {
      var item = button(choice[1], lang === choice[0] ? "sun" : "outline", function () { if (lang !== choice[0]) setLanguage(choice[0]); });
      item.lang = choice[0];
      langRow.appendChild(item);
    });
    card.appendChild(langRow);
    var passwordRow = element("div", "p-row");
    passwordRow.appendChild(button(t("changePassword"), "outline", function () { toggleChangePassword(); window.scrollTo(0, 0); }));
    card.appendChild(passwordRow);
    pane.appendChild(card);
  }
  function renderAnnouncements(container) {
    request("/api/platform/announcements").then(function (items) {
      if (!items.length) return;
      var card = element("section", "p-card");
      card.appendChild(element("h2", "", t("announcementsTitle")));
      items.slice(0, 3).forEach(function (item) {
        var row = element("article", "p-report");
        row.appendChild(element("h3", "", item.title));
        row.appendChild(element("small", "p-muted", dateLabel(item.created_at)));
        if (item.body) row.appendChild(element("p", "", item.body));
        card.appendChild(row);
      });
      container.appendChild(card);
    }).catch(function () {});
  }
  function renderStorage(pane) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", t("storageTitle")));
    var bar = element("progress", "p-storage");
    bar.max = 100; bar.value = 0;
    var text = element("p", "p-muted", t("loading"));
    card.appendChild(bar); card.appendChild(text);
    pane.insertBefore(card, pane.firstChild);
    request("/api/platform/teacher/storage").then(function (usage) {
      bar.value = Math.min(100, Math.round(usage.used_bytes * 100 / usage.limit_bytes));
      text.textContent = fileSizeLabel(usage.used_bytes) + " / " + fileSizeLabel(usage.limit_bytes);
    }).catch(function (error) { text.remove(); showError(card, error); });
  }
  function appendReportDetails(item, report) {
    [["activities", report.activities], ["meals", report.meals]].forEach(function (pair) {
      if (!pair[1]) return;
      var line = element("p", "p-detail");
      line.appendChild(element("strong", "", t(pair[0]) + ": "));
      line.appendChild(document.createTextNode(pair[1]));
      item.appendChild(line);
    });
  }
  function renderDashboardWelcome(main) {
    var welcome = element("section", "p-dashboard-welcome");
    var copy = element("div");
    copy.appendChild(element("span", "p-auth-kicker", t("portalOverview")));
    copy.appendChild(element("h2", "", t("welcomeUser") + " " + profile.username));
    copy.appendChild(element("p", "", isManagerPortal ? t("managerWelcome") : isTeacherPortal ? t("teacherWelcome") : t("parentWelcome")));
    welcome.appendChild(copy);
    welcome.appendChild(element("span", "p-badge p-status-active", t("activeAccount")));
    main.appendChild(welcome);
  }
  function statusLabel(status) {
    return t(status === "published" ? "published" : status === "submitted" ? "submitted" : status === "rejected" ? "rejected" : status === "archived" ? "archived" : "draft");
  }
  function renderReports(container, reports) {
    if (!reports.length) {
      container.appendChild(element("p", "p-muted", isTeacherPortal ? t("notAssigned") : t("noReports")));
      return;
    }
    reports.forEach(function (report) {
      var card = element("article", "p-report");
      var meta = element("div", "p-report-meta");
      meta.appendChild(element("span", "p-badge", statusLabel(report.status)));
      if (report.created_at) meta.appendChild(element("small", "p-muted", new Date(report.created_at).toLocaleDateString(lang === "ar" ? "ar" : "en")));
      card.appendChild(meta);
      card.appendChild(element("h3", "", report.title));
      if (report.language && report.language.split("-")[0] !== lang) {
        card.appendChild(element("p", "p-muted", t("originalLanguage")));
      }
      var body = element("p", "", report.body);
      if (report.language) {
        body.lang = report.language;
        body.dir = report.language.split("-")[0] === "ar" ? "rtl" : "ltr";
      }
      card.appendChild(body);
      appendReportDetails(card, report);
      container.appendChild(card);
    });
  }
  function fileSizeLabel(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.ceil(bytes / 1024)) + " KB";
  }
  function downloadByPath(path, filename) {
    fetch(apiBase + path, {headers: {Authorization: "Bearer " + token}}).then(function (response) {
      if (!response.ok) {
        return response.json().catch(function () { return {}; }).then(function (body) { throw new Error(body.detail || t("genericError")); });
      }
      return response.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var link = element("a");
      link.href = url; link.download = filename || "download";
      document.body.appendChild(link); link.click(); link.remove();
      URL.revokeObjectURL(url);
    }).catch(function (error) { window.alert(errorMessage(error)); });
  }
  /* A post card: scope badge, title, text, attachments. fileUrl(post, file) gives the download path; onDelete adds a delete button. */
  function postCard(post, fileUrl, onDelete) {
    var card = element("article", "p-post p-post-" + (post.scope === "child" ? "private" : "general"));
    var meta = element("div", "p-report-meta");
    var badge = element("span", "p-badge " + (post.scope === "child" ? "p-scope-private" : "p-scope-general"),
      post.scope === "child" ? t("scopePrivateBadge") + (post.child_name ? " · " + post.child_name : "") : t("scopeGeneralBadge"));
    meta.appendChild(badge);
    var when = post.created_at ? post.created_at.slice(0, 10) : "";
    var who = post.author || post.author_username || "";
    var info = element("small", "p-muted p-post-info");
    if (who) { var whoNode = element("span", "", who); whoNode.setAttribute("dir", "auto"); info.appendChild(whoNode); }
    if (when) { var whenNode = element("span", "", when); whenNode.setAttribute("dir", "ltr"); info.appendChild(whenNode); }
    meta.appendChild(info);
    card.appendChild(meta);
    var postTitle = element("h3", "", post.title); postTitle.setAttribute("dir", "auto"); card.appendChild(postTitle);
    if (post.body) { var postBody = element("p", "p-post-body", post.body); postBody.setAttribute("dir", "auto"); card.appendChild(postBody); }
    if (post.files && post.files.length) {
      var files = element("div", "p-post-files");
      post.files.forEach(function (file) {
        var chip = element("button", "p-file-chip", file.filename + " · " + fileSizeLabel(file.size));
        chip.type = "button";
        chip.addEventListener("click", function () { downloadByPath(fileUrl(post, file), file.filename); });
        files.appendChild(chip);
      });
      card.appendChild(files);
    }
    if (onDelete) card.appendChild(button(t("deleteFile"), "outline p-post-delete", function () {
      if (window.confirm(t("deletePostConfirm"))) onDelete(post);
    }));
    return card;
  }
  function renderParentPosts(main) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", t("postsForYou")));
    var list = element("div", "p-post-list");
    list.appendChild(element("p", "p-muted", t("loading")));
    card.appendChild(list);
    main.appendChild(card);
    request("/api/platform/parent/posts").then(function (posts) {
      list.innerHTML = "";
      if (!posts.length) { list.appendChild(element("p", "p-muted", t("noPostsParent"))); return; }
      posts.forEach(function (post) {
        list.appendChild(postCard(post, function (p, f) { return "/api/platform/parent/posts/" + encodeURIComponent(p.id) + "/files/" + encodeURIComponent(f.id); }));
      });
    }).catch(function (error) { list.innerHTML = ""; showError(card, error); });
  }
  function renderTeacherPosts(main, adminMode) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", adminMode ? t("allPosts") : t("postsComposeTitle")));
    var list = element("div", "p-post-list");
    function loadPosts() {
      list.innerHTML = "";
      list.appendChild(element("p", "p-muted", t("loading")));
      request(adminMode ? "/api/platform/admin/posts" : "/api/platform/teacher/posts").then(function (posts) {
        list.innerHTML = "";
        if (!posts.length) { list.appendChild(element("p", "p-muted", t("noPosts"))); return; }
        posts.forEach(function (post) {
          list.appendChild(postCard(post, function (p, f) {
            return adminMode ? "/api/platform/admin/teacher-content/" + encodeURIComponent(f.id) + "/download"
              : "/api/platform/teacher/content/" + encodeURIComponent(f.id) + "/download";
          }, function (p) {
            request((adminMode ? "/api/platform/admin/posts/" : "/api/platform/teacher/posts/") + encodeURIComponent(p.id), {method: "DELETE"})
              .then(loadPosts).catch(function (error) { showError(card, error); });
          }));
        });
      }).catch(function (error) { list.innerHTML = ""; showError(card, error); });
    }
    if (!adminMode) {
      card.appendChild(element("p", "p-muted", t("postsComposeHelp")));
      var form = element("form", "p-compose");
      var scope = element("select");
      scope.appendChild(new Option(t("scopeGeneral"), "general"));
      scope.appendChild(new Option(t("scopeChild"), "child"));
      var scopeLabel = element("label", "p-field", t("scopeLabel")); scopeLabel.appendChild(scope); form.appendChild(scopeLabel);
      var childSelect = element("select");
      childSelect.appendChild(new Option(t("selectChild"), ""));
      var childLabel = element("label", "p-field", t("child")); childLabel.appendChild(childSelect); childLabel.hidden = true; form.appendChild(childLabel);
      request("/api/platform/teacher/children").then(function (children) {
        children.forEach(function (child) { childSelect.appendChild(new Option(child.display_name, child.id)); });
        if (!children.length) childLabel.appendChild(element("small", "p-muted", t("noAssignedHint")));
      }).catch(function () {});
      scope.addEventListener("change", function () { childLabel.hidden = scope.value !== "child"; childSelect.required = scope.value === "child"; });
      var title = element("input"); title.type = "text"; title.maxLength = 120; title.required = true;
      var titleLabel = element("label", "p-field", t("postTitle")); titleLabel.appendChild(title); form.appendChild(titleLabel);
      var body = element("textarea"); body.maxLength = 3000;
      var bodyLabel = element("label", "p-field", t("postBody")); bodyLabel.appendChild(body); form.appendChild(bodyLabel);
      var fileInput = element("input"); fileInput.type = "file"; fileInput.multiple = true;
      var fileLabel = element("label", "p-field", t("postFiles")); fileLabel.appendChild(fileInput); form.appendChild(fileLabel);
      var message = element("p", "p-alert"); message.setAttribute("role", "status");
      var submit = element("button", "p-button sun", t("publishPost")); submit.type = "submit";
      var previewBox = element("div", "p-preview");
      previewBox.hidden = true;
      var previewButton = button(t("preview"), "outline", function () {
        previewBox.innerHTML = "";
        previewBox.hidden = false;
        previewBox.appendChild(element("h3", "", t("previewTitle")));
        var article = element("article", "p-report");
        var kind = scope.value === "general" ? t("scopeGeneral") : (childSelect.selectedIndex > 0 ? childSelect.options[childSelect.selectedIndex].text : t("scopeChild"));
        article.appendChild(element("span", "p-badge", kind));
        article.appendChild(element("h3", "", title.value.trim() || "—"));
        article.appendChild(element("p", "", body.value));
        Array.prototype.forEach.call(fileInput.files, function (file) { article.appendChild(element("small", "p-muted", "— " + file.name + " (" + fileSizeLabel(file.size) + ")")); article.appendChild(element("br")); });
        previewBox.appendChild(article);
      });
      form.appendChild(previewButton); form.appendChild(submit); form.appendChild(previewBox); form.appendChild(message);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (fileInput.files.length > 5) { message.className = "p-alert error"; message.textContent = t("postFiles"); return; }
        var data = new FormData();
        data.append("scope", scope.value); data.append("title", title.value.trim()); data.append("body", body.value);
        if (scope.value === "child") data.append("child_id", childSelect.value);
        Array.prototype.forEach.call(fileInput.files, function (file) { data.append("files", file); });
        submit.disabled = true; message.className = "p-alert"; message.textContent = "";
        request("/api/platform/teacher/posts", {method: "POST", body: data}).then(function () {
          title.value = ""; body.value = ""; fileInput.value = "";
          message.className = "p-alert success"; message.textContent = t("postPublished");
          loadPosts();
        }).catch(function (error) {
          message.className = "p-alert error"; message.textContent = errorMessage(error);
        }).finally(function () { submit.disabled = false; });
      });
      card.appendChild(form);
      card.appendChild(element("h3", "p-subhead", t("myPosts")));
    }
    card.appendChild(list);
    main.appendChild(card);
    loadPosts();
  }
  function renderParent(shellMain) {
    var views = viewShell(shellMain, [["home", "navHome"], ["children", "navChildren"], ["reports", "navReportsAll"], ["posts", "navPosts"], ["notifications", "navNotifications"], ["guardians", "navGuardians"], ["profile", "navProfile"]]);
    var data = {children: [], reports: {}};
    var home = views.panes.home;
    renderDashboardWelcome(home);
    var stats = element("div", "p-stats");
    var tiles = {
      children: statTile(t("statChildren"), "children", views.show),
      reports: statTile(t("statReports"), "reports", views.show),
      unread: statTile(t("statUnread"), "notifications", views.show),
      posts: statTile(t("statPosts"), "posts", views.show)
    };
    Object.keys(tiles).forEach(function (key) { stats.appendChild(tiles[key]); });
    home.appendChild(stats);
    renderAnnouncements(home);
    var recentCard = element("section", "p-card");
    home.appendChild(recentCard);
    renderParentPosts(views.panes.posts);
    request("/api/platform/parent/posts").then(function (list) { tiles.posts.number.textContent = list.length; }).catch(function () { tiles.posts.number.textContent = "–"; });
    renderNotifications(views.panes.notifications, views.show, function (count) { tiles.unread.number.textContent = count; views.setBadge("notifications", count); })
      .catch(function () { tiles.unread.number.textContent = "–"; });
    renderProfile(views.panes.profile);

    var filterId = "";
    var childPane = views.panes.children, reportPane = views.panes.reports, guardPane = views.panes.guardians;
    [childPane, reportPane, guardPane, recentCard].forEach(function (pane) { pane.appendChild(element("p", "p-muted", t("loading"))); });

    function ownReports(childId) {
      var all = [];
      data.children.forEach(function (child) {
        if (childId && child.id !== childId) return;
        (data.reports[child.id] || []).forEach(function (report) { all.push({child: child, report: report}); });
      });
      all.sort(function (a, b) { return String(b.report.published_at || b.report.created_at).localeCompare(String(a.report.published_at || a.report.created_at)); });
      return all;
    }
    function reportArticle(entry, showChild) {
      var item = element("article", "p-report");
      var meta = element("div", "p-report-meta");
      if (showChild) meta.appendChild(element("span", "p-badge", entry.child.display_name));
      meta.appendChild(element("small", "p-muted", dateLabel(entry.report.published_at || entry.report.created_at)));
      item.appendChild(meta);
      item.appendChild(element("h3", "", entry.report.title));
      var body = element("p", "", entry.report.body);
      if (entry.report.language) { body.lang = entry.report.language; body.dir = entry.report.language.split("-")[0] === "ar" ? "rtl" : "ltr"; }
      item.appendChild(body);
      appendReportDetails(item, entry.report);
      return item;
    }
    function drawHome() {
      recentCard.innerHTML = "";
      recentCard.appendChild(element("h2", "", t("recentReports")));
      var latest = ownReports("").slice(0, 3);
      if (!latest.length) recentCard.appendChild(element("p", "p-muted", data.children.length ? t("noReportsYet") : t("noChildren")));
      latest.forEach(function (entry) { recentCard.appendChild(reportArticle(entry, data.children.length > 1)); });
      tiles.children.number.textContent = data.children.length;
      tiles.reports.number.textContent = ownReports("").length;
    }
    function drawChildren() {
      childPane.innerHTML = "";
      if (!data.children.length) { var empty = element("section", "p-card"); empty.appendChild(element("p", "p-muted", t("noChildren"))); childPane.appendChild(empty); return; }
      var grid = element("div", "p-grid");
      data.children.forEach(function (child) {
        var card = element("article", "p-card p-child");
        var head = element("div", "p-child-head");
        head.appendChild(element("span", "p-avatar sun", (child.display_name || "?").charAt(0)));
        head.appendChild(element("h3", "", child.display_name));
        card.appendChild(head);
        var list = data.reports[child.id] || [];
        card.appendChild(element("p", "p-muted", t("latestReport")));
        card.appendChild(element("p", "", list.length ? list[0].title + " · " + dateLabel(list[0].published_at || list[0].created_at) : t("noReportsYet")));
        card.appendChild(button(t("showReports"), "outline", function () { filterId = child.id; drawReports(); views.show("reports"); window.scrollTo(0, 0); }));
        grid.appendChild(card);
      });
      childPane.appendChild(grid);
    }
    function drawReports() {
      reportPane.innerHTML = "";
      var card = element("section", "p-card");
      card.appendChild(element("h2", "", t("navReportsAll")));
      if (data.children.length > 1) {
        var select = element("select");
        select.setAttribute("aria-label", t("child"));
        select.appendChild(new Option(t("allChildren"), ""));
        data.children.forEach(function (child) { select.appendChild(new Option(child.display_name, child.id)); });
        select.value = filterId;
        select.addEventListener("change", function () { filterId = select.value; drawReports(); });
        var wrap = element("div", "p-field"); wrap.appendChild(select); card.appendChild(wrap);
      }
      var entries = ownReports(filterId);
      if (!entries.length) card.appendChild(element("p", "p-muted", t("noReportsYet")));
      entries.forEach(function (entry) { card.appendChild(reportArticle(entry, data.children.length > 1 && !filterId)); });
      reportPane.appendChild(card);
    }
    function drawGuardians() {
      guardPane.innerHTML = "";
      if (!data.children.length) { var empty = element("section", "p-card"); empty.appendChild(element("p", "p-muted", t("noChildren"))); guardPane.appendChild(empty); return; }
      var relation = {father: t("relFather"), mother: t("relMother"), guardian: t("relGuardian")};
      data.children.forEach(function (child) {
        var card = element("section", "p-card");
        card.appendChild(element("h2", "", child.display_name));
        var list = element("div", "p-content-list");
        card.appendChild(list);
        card.appendChild(element("p", "p-muted", t("guardiansNote")));
        guardPane.appendChild(card);
        request("/api/platform/parent/children/" + encodeURIComponent(child.id) + "/guardians").then(function (people) {
          if (!people.length) list.appendChild(element("p", "p-muted", t("noGuardians")));
          people.forEach(function (person) {
            var row = element("div", "p-content-item");
            var text = element("div");
            text.appendChild(element("strong", "", person.name));
            text.appendChild(element("small", "p-muted", relation[person.relation] || person.relation));
            row.appendChild(text);
            row.appendChild(element("span", "p-badge" + (person.is_me ? " p-status-active" : ""), person.is_me ? t("you") : person.has_account ? t("hasAccount") : t("noAccount")));
            list.appendChild(row);
          });
        }).catch(function (error) { showError(card, error); });
      });
    }
    request("/api/platform/children").then(function (children) {
      data.children = children;
      return Promise.all(children.map(function (child) {
        return request("/api/platform/children/" + encodeURIComponent(child.id) + "/reports").then(function (list) { data.reports[child.id] = list; });
      }));
    }).then(function () {
      [childPane, reportPane, guardPane].forEach(function (pane) { pane.innerHTML = ""; });
      drawHome(); drawChildren(); drawReports(); drawGuardians();
    }).catch(function (error) {
      [childPane, reportPane, guardPane, recentCard].forEach(function (pane) { pane.innerHTML = ""; showError(pane, error); });
      tiles.children.number.textContent = tiles.reports.number.textContent = "–";
    });
  }
  function downloadTeacherContent(contentId, adminMode, filename) {
    var basePath = adminMode ? "/api/platform/admin/teacher-content/" : "/api/platform/teacher/content/";
    fetch(apiBase + basePath + encodeURIComponent(contentId) + "/download", {
      headers: {Authorization:"Bearer " + token}
    }).then(function (response) {
      if (!response.ok) {
        return response.json().catch(function () { return {}; }).then(function (body) {
          throw new Error(body.detail || t("genericError"));
        });
      }
      return response.blob();
    }).then(function (blob) {
      var url = URL.createObjectURL(blob);
      var link = element("a");
      link.href = url;
      link.download = filename || "download";
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }).catch(function (error) {
      window.alert(errorMessage(error));
    });
  }
  function loadTeacherContent(card, adminMode) {
    var path = adminMode ? "/api/platform/admin/teacher-content" : "/api/platform/teacher/content";
    var list = card.querySelector(".p-content-list");
    list.innerHTML = "";
    request(path).then(function (contents) {
      if (!contents.length) {
        list.appendChild(element("p", "p-muted", t("noTeacherFiles")));
        return;
      }
      contents.forEach(function (content) {
        var item = element("article", "p-content-item");
        item.appendChild(element("span", "p-file-icon p-file-" + content.category, {document:"DOC", image:"IMG", video:"VID"}[content.category] || "FILE"));
        var description = element("div", "p-content-text");
        description.appendChild(element("strong", "", content.filename));
        if (adminMode && content.owner_username) {
          description.appendChild(element("small", "p-muted", content.owner_username));
        }
        description.appendChild(element("small", "p-muted", t(content.category) + " · " + Math.max(1, Math.ceil(content.size / 1024)) + " KB"));
        item.appendChild(description);
        item.appendChild(button(t("downloadFile"), "outline", function () {
          downloadTeacherContent(content.id, adminMode, content.filename);
        }));
        if (!adminMode || profile.roles.indexOf("admin") !== -1) {
          item.appendChild(button(t("deleteFile"), "outline", function () {
            if (!window.confirm(t("deleteFile") + " · " + content.filename + "?")) return;
            var deletePath = adminMode
              ? "/api/platform/admin/teacher-content/" + encodeURIComponent(content.id)
              : "/api/platform/teacher/content/" + encodeURIComponent(content.id);
            request(deletePath, {method:"DELETE"}).then(function () {
              loadTeacherContent(card, adminMode);
            }).catch(function (error) { showError(card, error); });
          }));
        }
        list.appendChild(item);
      });
    }).catch(function (error) { list.innerHTML = ""; showError(card, error); });
  }
  function renderTeacherContent(main, adminMode) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", t("teacherFiles")));
    if (!adminMode) {
      card.appendChild(element("p", "p-muted", t("teacherFilesHelp")));
      var form = element("form", "p-card");
      var typeLabel = element("label", "p-field", t("uploadType"));
      var type = element("select");
      [["other","other"],["document","document"],["image","image"],["video","video"]].forEach(function (option) {
        type.appendChild(new Option(t(option[1]), option[0]));
      });
      typeLabel.appendChild(type);
      form.appendChild(typeLabel);
      var fileLabel = element("label", "p-field", t("chooseFile"));
      var fileInput = element("input");
      fileInput.type = "file";
      fileInput.required = true;
      fileLabel.appendChild(fileInput);
      form.appendChild(fileLabel);
      var message = element("p", "p-alert");
      var uploadButton = element("button", "p-button sun", t("uploadFile"));
      uploadButton.type = "submit";
      form.appendChild(uploadButton);
      form.appendChild(message);
      form.addEventListener("submit", function (event) {
        event.preventDefault();
        if (!fileInput.files.length) return;
        uploadButton.disabled = true;
        message.textContent = "";
        var data = new FormData();
        data.append("file", fileInput.files[0]);
        data.append("category", type.value);
        request("/api/platform/teacher/content", {method:"POST",body:data}).then(function () {
          fileInput.value = "";
          message.className = "p-alert success";
          message.textContent = t("fileUploaded");
          loadTeacherContent(card, false);
        }).catch(function (error) {
          message.className = "p-alert error";
          message.textContent = errorMessage(error);
        }).finally(function () { uploadButton.disabled = false; });
      });
      card.appendChild(form);
    }
    var list = element("div", "p-content-list");
    list.appendChild(element("p", "p-muted", t("loading")));
    card.appendChild(list);
    main.appendChild(card);
    loadTeacherContent(card, adminMode);
  }
  function renderTeacher(shellMain) {
    var canTeach = profile.roles.indexOf("teacher") !== -1;
    var canReview = profile.roles.indexOf("manager") !== -1 || profile.roles.indexOf("admin") !== -1;
    var isAdmin = profile.roles.indexOf("admin") !== -1;
    var defs = [["home", "navHome"]];
    if (canTeach) defs.push(["reports", "navReports"]);
    if (canTeach || isAdmin) defs.push(["posts", "navPosts"], ["material", "navMaterial"]);
    if (canReview) defs.push(["review", "navReview"]);
    defs.push(["notifications", "navNotifications"], ["profile", "navProfile"]);
    var views = viewShell(shellMain, defs);
    renderDashboardWelcome(views.panes.home);
    var stats = element("div", "p-stats");
    views.panes.home.appendChild(stats);
    renderAnnouncements(views.panes.home);
    renderNotifications(views.panes.notifications, views.show, function (count) { views.setBadge("notifications", count); }).catch(function () {});
    renderProfile(views.panes.profile);
    if (canTeach) {
      var tiles = {
        children: statTile(t("statChildren"), "reports", views.show),
        draft: statTile(t("statDrafts"), "reports", views.show),
        submitted: statTile(t("statSubmitted"), "reports", views.show),
        published: statTile(t("statPublished"), "reports", views.show)
      };
      Object.keys(tiles).forEach(function (key) { stats.appendChild(tiles[key]); });
      request("/api/platform/teacher/children").then(function (list) { tiles.children.number.textContent = list.length; }).catch(function () { tiles.children.number.textContent = "–"; });
      request("/api/platform/teacher/reports").then(function (list) {
        ["draft", "submitted", "published"].forEach(function (status) {
          tiles[status].number.textContent = list.filter(function (report) { return report.status === status; }).length;
        });
      }).catch(function () { ["draft", "submitted", "published"].forEach(function (status) { tiles[status].number.textContent = "–"; }); });
    } else {
      stats.remove();
    }
    if (!canTeach) {
      if (isAdmin) { renderTeacherPosts(views.panes.posts, true); renderTeacherContent(views.panes.material, true); }
      loadReviewQueue(views.panes.review);
      return;
    }
    var main = views.panes.reports;
    renderTeacherPosts(views.panes.posts, false);
    renderTeacherContent(views.panes.material, false);
    renderStorage(views.panes.material);
    var childrenCard = element("section", "p-card");
    childrenCard.appendChild(element("h2", "", t("children")));
    childrenCard.appendChild(element("p", "p-muted", t("loading")));
    main.appendChild(childrenCard);
    var reportCard = element("section", "p-card");
    reportCard.appendChild(element("h2", "", t("reports")));
    reportCard.appendChild(element("p", "p-muted", t("loading")));
    main.appendChild(reportCard);
    var childrenLoaded = request("/api/platform/teacher/children").then(function (children) {
      children.forEach(function (child) { childNames[child.id] = child.display_name; });
      childrenCard.innerHTML = "";
      childrenCard.appendChild(element("h2", "", t("children")));
      if (!children.length) childrenCard.appendChild(element("p", "p-muted", t("notAssigned")));
      else {
        var select = element("select");
        select.required = true;
        select.appendChild(new Option(t("selectChild"), ""));
        children.forEach(function (child) { select.appendChild(new Option(child.display_name, child.id)); });
        select.value = formState.child_id;
        select.addEventListener("change", function () { formState.child_id = select.value; });
        var form = element("form", "p-card");
        var selectLabel = element("label", "p-field", t("child"));
        selectLabel.appendChild(select);
        form.appendChild(selectLabel);
        var title = element("input");
        title.type = "text"; title.maxLength = 120; title.required = true;
        title.value = formState.title;
        title.addEventListener("input", function () { formState.title = title.value; });
        var titleLabel = element("label", "p-field", t("title")); titleLabel.appendChild(title); form.appendChild(titleLabel);
        var body = element("textarea");
        body.maxLength = 3000; body.required = true;
        body.value = formState.body;
        body.addEventListener("input", function () { formState.body = body.value; });
        var bodyLabel = element("label", "p-field", t("body")); bodyLabel.appendChild(body); form.appendChild(bodyLabel);
        var activities = element("textarea");
        activities.maxLength = 1000; activities.rows = 3; activities.value = formState.activities;
        activities.addEventListener("input", function () { formState.activities = activities.value; });
        var activitiesLabel = element("label", "p-field", t("activities")); activitiesLabel.appendChild(activities); form.appendChild(activitiesLabel);
        var meals = element("input");
        meals.type = "text"; meals.maxLength = 500; meals.value = formState.meals;
        meals.addEventListener("input", function () { formState.meals = meals.value; });
        var mealsLabel = element("label", "p-field", t("meals")); mealsLabel.appendChild(meals); form.appendChild(mealsLabel);
        var attachmentLabel = element("label", "p-field", t("reportAttachments"));
        var attachmentInput = element("input");
        attachmentInput.type = "file"; attachmentInput.multiple = true;
        attachmentLabel.appendChild(attachmentInput); form.appendChild(attachmentLabel);
        form.appendChild(element("p", "p-muted", t("reportAttachmentsHelp")));
        form.appendChild(element("p", "p-muted", t("privacy")));
        var message = element("p", "p-alert");
        var save = element("button", "p-button outline", t("saveDraft")); save.type = "button";
        var submit = element("button", "p-button sun", t("submit")); submit.type = "submit";
        form.appendChild(element("div", "p-row"));
        form.lastChild.appendChild(save); form.lastChild.appendChild(submit);
        var cancelEdit = element("button", "p-button outline", t("cancelEdit"));
        cancelEdit.type = "button"; cancelEdit.hidden = !editingReportId;
        form.lastChild.appendChild(cancelEdit);
        form.appendChild(message);
        teacherControls = {select:select,title:title,body:body,activities:activities,meals:meals,form:form,save:save,submit:submit,cancel:cancelEdit,message:message};
        function saveReport(submitForReview) {
          if (!select.value || !title.value.trim() || !body.value.trim()) {
            message.className = "p-alert error";
            message.textContent = t("selectChild") + " · " + t("title") + " · " + t("body");
            return Promise.resolve();
          }
          save.disabled = true; submit.disabled = true; message.textContent = "";
          var updating = !!editingReportId;
          var path = updating
            ? "/api/platform/teacher/reports/" + encodeURIComponent(editingReportId)
            : "/api/platform/teacher/reports";
          var attachmentFiles = Array.from(attachmentInput.files || []);
          if (attachmentFiles.length > 5) {
            message.className = "p-alert error";
            message.textContent = t("reportAttachmentsHelp");
            save.disabled = false; submit.disabled = false;
            return Promise.resolve();
          }
          var uploadedAttachments = [];
          var reportPayload = {
            title: title.value.trim(), body: body.value.trim(),
            activities: activities.value.trim(), meals: meals.value.trim(),
            submit_for_review: submitForReview && attachmentFiles.length === 0
          };
          if (!updating) reportPayload.child_id = select.value;
          return request(path, {method:updating ? "PATCH" : "POST",body:JSON.stringify(reportPayload)}).then(function (report) {
            var reportId = updating ? editingReportId : report.id;
            if (!updating && attachmentFiles.length) {
              editingReportId = reportId;
              select.disabled = true;
            }
            return attachmentFiles.reduce(function (chain, file) {
              return chain.then(function () {
                var data = new FormData();
                data.append("file", file);
                data.append("category", "report_attachment");
                data.append("report_id", reportId);
                return request("/api/platform/teacher/content", {method:"POST",body:data}).then(function () {
                  uploadedAttachments.push(file);
                  var remainingFiles = Array.from(attachmentInput.files || []).filter(function (selected) {
                    return uploadedAttachments.indexOf(selected) === -1;
                  });
                  var transfer = new DataTransfer();
                  remainingFiles.forEach(function (remaining) { transfer.items.add(remaining); });
                  attachmentInput.files = transfer.files;
                });
              });
            }, Promise.resolve()).then(function () {
              if (submitForReview && attachmentFiles.length) {
                return request("/api/platform/teacher/reports/" + encodeURIComponent(reportId), {
                  method:"PATCH",
                  body:JSON.stringify({title:title.value.trim(),body:body.value.trim(),activities:activities.value.trim(),meals:meals.value.trim(),submit_for_review:true})
                });
              }
            }).then(function () {
              message.className = "p-alert success";
              message.textContent = updating ? t("reportUpdated") : submitForReview ? t("reportSent") : t("reportSaved");
              title.value = ""; body.value = ""; activities.value = ""; meals.value = "";
              attachmentInput.value = "";
              formState.title = ""; formState.body = ""; formState.activities = ""; formState.meals = "";
              editingReportId = "";
              cancelEdit.hidden = true;
              select.disabled = false;
              return loadTeacherReports(reportCard);
            });
          }).catch(function (error) {
            if (uploadedAttachments.length) {
              var remainingFiles = Array.from(attachmentInput.files || []).filter(function (selected) {
                return uploadedAttachments.indexOf(selected) === -1;
              });
              var transfer = new DataTransfer();
              remainingFiles.forEach(function (remaining) { transfer.items.add(remaining); });
              attachmentInput.files = transfer.files;
            }
            message.className = "p-alert error"; message.textContent = errorMessage(error);
          }).finally(function () { save.disabled = false; submit.disabled = false; });
        }
        save.addEventListener("click", function () { saveReport(false); });
        form.addEventListener("submit", function (event) { event.preventDefault(); saveReport(true); });
        cancelEdit.addEventListener("click", function () {
          editingReportId = "";
          formState.title = ""; formState.body = ""; formState.child_id = ""; formState.activities = ""; formState.meals = "";
          title.value = ""; body.value = ""; activities.value = ""; meals.value = ""; attachmentInput.value = ""; select.value = ""; select.disabled = false;
          cancelEdit.hidden = true; message.textContent = "";
        });
        if (editingReportId) select.disabled = true;
        childrenCard.appendChild(form);
      }
    }).catch(function (error) { childrenCard.innerHTML = ""; childrenCard.appendChild(element("h2", "", t("children"))); showError(childrenCard, error); });
    childrenLoaded.then(function () { loadTeacherReports(reportCard); });
    if (canReview) loadReviewQueue(views.panes.review);
  }
  function loadTeacherReports(card) {
    request("/api/platform/teacher/reports").then(function (reports) {
      card.innerHTML = "";
      card.appendChild(element("h2", "", t("reports")));
      if (!reports.length) card.appendChild(element("p", "p-muted", t("noReports")));
      else reports.forEach(function (report) {
        var item = element("article", "p-report");
        item.appendChild(element("h3", "", report.title));
        var meta = element("div", "p-report-meta");
        meta.appendChild(element("span", "p-badge", statusLabel(report.status)));
        meta.appendChild(element("span", "p-badge " + (report.status === "published" ? "p-status-active" : "p-hidden"), report.status === "published" ? t("visibleToParents") : t("hiddenFromParents")));
        if (childNames[report.child_id]) meta.appendChild(element("small", "p-muted", childNames[report.child_id]));
        if (report.created_at) meta.appendChild(element("small", "p-muted", new Date(report.created_at).toLocaleDateString(lang === "ar" ? "ar" : "en")));
        item.appendChild(meta);
        var body = element("p", "", report.body);
        body.lang = report.language || "ar";
        body.dir = body.lang.split("-")[0] === "ar" ? "rtl" : "ltr";
        item.appendChild(body);
        appendReportDetails(item, report);
        if (report.status === "draft" || report.status === "rejected") {
          item.appendChild(button(t("edit"), "outline", function () {
            editingReportId = report.id;
            formState.child_id = report.child_id;
            formState.title = report.title;
            formState.body = report.body;
            formState.activities = report.activities || ""; formState.meals = report.meals || "";
            if (teacherControls) {
              teacherControls.activities.value = formState.activities;
              teacherControls.meals.value = formState.meals;
              teacherControls.select.value = report.child_id;
              teacherControls.select.disabled = true;
              teacherControls.title.value = report.title;
              teacherControls.body.value = report.body;
              teacherControls.cancel.hidden = false;
              teacherControls.form.scrollIntoView({behavior:"smooth", block:"start"});
            }
          }));
        }
        loadTeacherReportAttachments(report.id, item);
        card.appendChild(item);
      });
    }).catch(function (error) { card.innerHTML = ""; card.appendChild(element("h2", "", t("reports"))); showError(card, error); });
  }
  function loadTeacherReportAttachments(reportId, container) {
    request("/api/platform/teacher/reports/" + encodeURIComponent(reportId) + "/attachments").then(function (attachments) {
      if (!attachments.length) return;
      var list = element("ul", "p-attachments");
      attachments.forEach(function (attachment) {
        var row = element("li");
        row.appendChild(element("span", "", attachment.filename));
        row.appendChild(button(t("downloadFile"), "outline", function () {
          downloadTeacherContent(attachment.id, false, attachment.filename);
        }));
        list.appendChild(row);
      });
      container.appendChild(element("h4", "", t("reportAttachments")));
      container.appendChild(list);
    }).catch(function (error) { showError(container, error); });
  }
  function loadReviewQueue(main) {
    var card = element("section", "p-card");
    card.appendChild(element("h2", "", t("review")));
    card.appendChild(element("p", "p-muted", t("loading")));
    main.appendChild(card);
    request("/api/platform/review/reports").then(function (reports) {
      card.innerHTML = "";
      card.appendChild(element("h2", "", t("review")));
      if (!reports.length) card.appendChild(element("p", "p-muted", t("noReview")));
      reports.forEach(function (report) {
        var item = element("article", "p-report");
        var meta = element("div", "p-report-meta");
        if (childNames[report.child_id]) meta.appendChild(element("span", "p-badge", childNames[report.child_id]));
        if (report.created_at) meta.appendChild(element("small", "p-muted", dateLabel(report.created_at)));
        item.appendChild(meta);
        item.appendChild(element("h3", "", report.title));
        item.appendChild(element("p", "", report.body));
        appendReportDetails(item, report);
        ["published", "rejected"].forEach(function (status) {
          item.appendChild(button(t(status === "published" ? "approve" : "reject"), status === "published" ? "sun" : "outline", function () {
            request("/api/platform/review/reports/" + encodeURIComponent(report.id), {
              method: "PATCH", body: JSON.stringify({status: status})
            }).then(function () { card.remove(); loadReviewQueue(main); }).catch(function (error) { showError(item, error); });
          }));
        });
        card.appendChild(item);
      });
    }).catch(function (error) { card.innerHTML = ""; card.appendChild(element("h2", "", t("review"))); showError(card, error); });
  }
  function loadDashboard() {
    return request("/api/platform/auth/me").then(function (data) {
      profile = data;
      var allowed = isManagerPortal
        ? data.roles.indexOf("manager") !== -1 || data.roles.indexOf("admin") !== -1
        : isTeacherPortal
          ? data.roles.indexOf("teacher") !== -1 || data.roles.indexOf("manager") !== -1 || data.roles.indexOf("admin") !== -1
          : data.roles.indexOf("parent") !== -1;
      if (!allowed) {
        token = ""; sessionStorage.removeItem(storeKey);
        window.location.replace("../login/");
        return;
      }
      if (data.preferred_language === "ar" || data.preferred_language === "en") {
        lang = data.preferred_language;
        localStorage.setItem(langKey, lang);
      }
      document.documentElement.lang = lang;
      document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
      var main = shell();
      drawPortal(main);
    }).catch(function (error) {
      token = ""; sessionStorage.removeItem(storeKey);
      loginScreen();
      var alert = root.querySelector('[role="alert"]');
      if (alert) alert.textContent = errorMessage(error);
    });
  }
  function logout() {
    request("/api/platform/auth/logout", {method: "POST"}).catch(function () {}).then(function () {
      token = "";
      sessionStorage.removeItem(storeKey);
      profile = null;
      window.location.href = "../login/";
    });
  }
  function drawPortal(main) {
    if (isManagerPortal) renderManager(main);
    else if (isTeacherPortal) renderTeacher(main);
    else renderParent(main);
  }
  function renderManager(shellMain) {
    if (typeof window.ZMManagement !== "function") { shellMain.appendChild(element("p", "p-alert error", t("genericError"))); return; }
    window.ZMManagement({
      element: element, request: request, t: t, button: button, showError: showError, errorMessage: errorMessage,
      viewShell: viewShell, statTile: statTile, profile: function () { return profile; }, lang: function () { return lang; },
      renderNotifications: renderNotifications, renderProfile: renderProfile, renderAnnouncements: renderAnnouncements,
      renderDashboardWelcome: renderDashboardWelcome, loadReviewQueue: loadReviewQueue, dateLabel: dateLabel, childNames: childNames
    })(shellMain);
  }
  function render() {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    document.title = portalTitle() + " | " + t("school");
    if (token && profile) {
      var main = shell();
      drawPortal(main);
    } else if (token) {
      loadDashboard();
    } else if (!isLogin) {
      window.location.replace("../login/");
    } else {
      loginScreen();
    }
  }

  (function idleGuard() {
    if (isLogin) return;
    var limit = 30 * 60 * 1000, timer;
    function expire() {
      ["zm-teacher-session", "zm-parent-session", "zm-accountant-session", "zm-admin-session", "zm-portals"].forEach(function (key) { try { sessionStorage.removeItem(key); } catch (e) {} });
      window.location.replace("../login/?expired=1");
    }
    function reset() { clearTimeout(timer); timer = setTimeout(expire, limit); }
    ["click", "keydown", "mousemove", "touchstart", "scroll"].forEach(function (name) { window.addEventListener(name, reset, {passive: true}); });
    reset();
  }());
  render();
}());
