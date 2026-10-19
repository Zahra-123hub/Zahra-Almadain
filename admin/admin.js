var DATA = {settings:{}, gallery:[], news:[]}, tab = "gallery";
var API_BASE = (window.ZM_API_BASE || (/^(localhost|127.0.0.1)$/.test(location.hostname) ? "http://127.0.0.1:8001" : "https://zahra-123hub-almadain-api.onrender.com")).replace(/\/+$/, "");
var ADMIN_TOKEN = sessionStorage.getItem("zm-admin-session") || "";
// Teachers publish website content with their portal session; accounts and settings stay admin-only.
var TEACHER_MODE = false;
if(!ADMIN_TOKEN){
  ADMIN_TOKEN = sessionStorage.getItem("zm-teacher-session") || "";
  TEACHER_MODE = !!ADMIN_TOKEN;
}
function clearSessions(){
  ADMIN_TOKEN = "";
  try{ sessionStorage.removeItem("zm-admin-session"); sessionStorage.removeItem("zm-teacher-session"); }catch(e){}
}
var ADMIN_LANG = localStorage.getItem("zm-admin-lang") === "en" ? "en" : "ar";
var FILE_RE = /^[0-9a-f]{32}\.(jpg|png|webp|gif|mp4|webm)$/;
var EN_TEXT = {
  "تعذّر الاتصال بالخادم. تحقق من إعداد رابط API واتصال الإنترنت.":"Could not connect to the server. Check the API URL and your internet connection.",
  "تعذّر تنفيذ العملية. حاول مرة أخرى.":"The operation failed. Please try again.",
  "تعذّر تنفيذ العملية على الخادم.":"The server could not complete the operation.",
  "تعذّر تنفيذ العملية على GitHub.":"The operation could not be completed on GitHub.",
  "انتهت جلسة الدخول. سجّل الدخول مرة أخرى.":"Your session expired. Please sign in again.",
  "لم يتم إعداد اتصال GitHub على الخادم.":"The GitHub connection is not configured on the server.",
  "رمز GitHub المخزن على الخادم غير صالح أو منتهي.":"The GitHub token stored on the server is invalid or expired.",
  "رمز GitHub يحتاج صلاحية Contents للقراءة والكتابة.":"The GitHub token needs Contents read and write permission.",
  "تعذّر الاتصال بـ GitHub من الخادم.":"The server could not connect to GitHub.",
  "انتهت مهلة الاتصال بـ GitHub. حاول مرة أخرى.":"The connection to GitHub timed out. Please try again.",
  "لم يتم العثور على المستودع أو الملف في GitHub.":"The repository or file was not found on GitHub.",
  "ملف content.json غير صالح أو تعذّر قراءته.":"content.json is invalid or could not be read.",
  "بنية ملف المحتوى غير صالحة.":"The content file has an invalid structure.",
  "الملف غير موجود.":"File not found.",
  "نوع العنصر غير صالح.":"Invalid item type.",
  "تعارضت تعديلات متزامنة. أعد المحاولة.":"Concurrent edits conflicted. Please try again.",
  "نوع الملف غير مدعوم.":"This file type is not supported.",
  "حجم الملف يتجاوز الحد المسموح (10 ميغابايت للصورة و25 ميغابايت للفيديو).":"The file exceeds the size limit (10 MB for images, 25 MB for videos).",
  "نوع الملف لا يطابق القسم المحدد.":"The file type does not match the selected section.",
  "عنصر المعرض غير موجود.":"Gallery item not found.",
  "العنوان والنص مطلوبان.":"A title and text are required.",
  "الخبر غير موجود.":"News item not found.",
  "لم يتم إعداد جلسات المسؤول على الخادم.":"Admin sessions are not configured on the server.",
  "سجّل الدخول إلى لوحة التحكم.":"Please sign in to the admin panel.",
  "لم يتم إعداد بيانات دخول المسؤول على الخادم.":"Admin login is not configured on the server.",
  "اسم المستخدم أو كلمة المرور غير صحيحة.":"Incorrect username or password.",
  "يجب أن يبدأ الرابط بـ https://":"Links must start with https://",
  "رقم الواتساب غير صالح.":"The WhatsApp number is invalid.",
  "تعليق يظهر تحت العنصر (اختياري)":"Caption shown under the item (optional)",
  "فيديوهات الهاتف بصيغة MOV لا تعمل. صدّرها بصيغة MP4.":"MOV videos from phones are not supported. Export them as MP4.",
  "لا توجد فيديوهات مرفوعة بعد.":"No videos uploaded yet.",
  "لا توجد صور مرفوعة بعد.":"No photos uploaded yet.",
  "لا توجد أخبار مضافة.":"No news added yet.",
  "إلغاء التعديل":"Cancel edit",
  "حذف الصورة الحالية":"Remove current image",
  "صورة (اختيارية)":"Image (optional)",
  "التصنيف (كلمة قصيرة)":"Category (short label)",
  "العنوان":"Title",
  "النص":"Text",
  "شريط إعلان أعلى الموقع":"Announcement banner",
  "رقم الهاتف الظاهر":"Display phone number",
  "رقم الواتساب بالصيغة الدولية، أرقام فقط":"WhatsApp number (international digits only)",
  "أوقات الدوام":"Opening hours",
  "رابط صفحة فيسبوك":"Facebook page URL",
  "رابط صفحة إنستغرام":"Instagram page URL",
  "البريد الإلكتروني":"Email address",
  "معلومات التواصل والإعلان":"Contact information and announcements",
  "المحتوى الأصلي للموقع":"Original website content",
  "إخفاء الخبر الافتتاحي الأصلي":"Hide the original opening announcement",
  "إخفاء الصور الأصلية في المعرض":"Hide the original gallery images",
  "الصور":"Photos",
  "الفيديو":"Videos",
  "الأخبار":"News",
  "الإعدادات":"Settings",
  "حسابات المنصة":"Platform accounts",
  "طلبات أولياء الأمور والمعلمات":"Parent and teacher accounts",
  "أنشئ حساب معلمة جديداً. يكون الحساب مفعّلاً فوراً.":"Create a teacher account. It will remain pending until you activate it.",
  "كلمة المرور الأولية (12 محرفاً على الأقل)":"Initial password (at least 12 characters)",
  "إنشاء حساب المعلمة":"Create teacher account",
  "الحسابات بانتظار التفعيل":"Accounts awaiting activation",
  "نشط":"Active",
  "بانتظار التفعيل":"Pending approval",
  "موقوف":"Disabled",
  "ولي أمر":"Parent",
  "معلمة":"Teacher",
  "تفعيل الحساب":"Activate account",
  "إيقاف الحساب":"Disable account",
  "لا توجد حسابات أولياء أمور أو معلمات.":"No parent or teacher accounts yet.",
  "تم إنشاء حساب المعلمة وتفعيله. يمكنها تسجيل الدخول الآن.":"Teacher account created and active. She can sign in now.",
  "تم تحديث حالة الحساب.":"Account status updated.",
  "الاسم أو كلمة المرور غير صالحة.":"The username or password is invalid.",
  "هذا الاسم مستخدم بالفعل.":"That username is already in use.",
  "بانتظار موافقة إدارة الروضة.":"Waiting for kindergarten admin approval.",
  "تم تسجيل الحساب بنجاح. سيُفعّل بعد موافقة الإدارة.":"Account registered. It will be activated after admin approval.",
  "اسم المستخدم يحتوي على أحرف غير مدعومة.":"The username contains unsupported characters.",
  "لم يتم تهيئة أدوار المنصة. نفّذ ترحيلات قاعدة البيانات.":"Platform roles are not initialized. Run database migrations.",
  "لم يتم العثور على حساب ولي أمر أو معلمة.":"Parent or teacher account not found.",
  "تعذر إنشاء الحساب. تحقق من الاسم وكلمة المرور.":"Could not create account. Check the username and password.",
  "لوحة تحكم روضة زهرة المدائن":"Zahrat Al-Madayn Admin",
  "خروج":"Sign out",
  "عرض الموقع":"View website",
  "دخول":"Sign in",
  "دخول المسؤول":"Admin sign in",
  "اسم المستخدم":"Username",
  "كلمة المرور":"Password",
  "اختر ملف فيديو أولاً.":"Choose a video file first.",
  "اختر صورة واحدة أو أكثر أولاً.":"Choose one or more photos first.",
  "جارٍ الرفع":"Uploading",
  "تم رفع":"Uploaded",
  "صورة":"photo",
  "فيديو":"video",
  "صورة واحدة أو أكثر، تُصغَّر تلقائياً":"Photos (you can select multiple; they are resized automatically)",
  "ملف الفيديو (MP4 أو WebM، حتى 25 ميغابايت)":"Video file (MP4 or WebM, up to 25 MB)",
  "الصور (يمكن اختيار عدة صور، تُصغَّر تلقائياً)":"Photos (select multiple; they are resized automatically)",
  "تعليق":"Caption",
  "حذف":"Delete",
  "رفع الفيديو":"Upload video",
  "رفع الصور":"Upload photos",
  "رفع فيديو جديد":"Upload a new video",
  "رفع صور جديدة":"Upload new photos",
  "الفيديوهات المنشورة":"Published videos",
  "الصور المنشورة":"Published photos",
  "خبر":"News",
  "نشر الخبر":"Publish news",
  "حفظ التعديل":"Save changes",
  "خبر جديد":"New announcement",
  "تعديل الخبر":"Edit announcement",
  "اكتب العنوان والنص.":"Enter a title and text.",
  "تم نشر الخبر في الموقع.":"The announcement was published.",
  "الأخبار المنشورة":"Published news",
  "تعديل":"Edit",
  "مثال: يوم الرسم في الروضة":"Example: Art day at kindergarten",
  "مثال: التسجيل مفتوح للعام الدراسي الجديد":"Example: Enrollment is open for the new school year",
  "اتركه فارغاً لإخفاء الشريط.":"Leave blank to hide the banner.",
  "مثال: من الأحد إلى الخميس، 8:00 إلى 13:00":"Example: Sunday to Thursday, 8:00 AM to 1:00 PM",
  "مثال: 963985122704":"Example: 963985122704",
  "تم حفظ الإعدادات وطُبّقت على الموقع.":"Settings saved and applied to the website.",
  "أدخل اسم المستخدم وكلمة المرور.":"Enter your username and password.",
  "أدخل بيانات دخول لوحة التحكم التي أُعدّت على الخادم.":"Enter the admin login credentials configured on the server.",
  "اضغط مرة أخرى للتأكيد":"Click again to confirm",
  "التعليق":"Caption"
};

try{ localStorage.removeItem("zm-gh"); }catch(e){}
function up(name){ return FILE_RE.test(name || "") ? API_BASE + "/api/assets/" + name : ""; }
function sOf(v, n){ return typeof v === "string" ? v.slice(0, n) : ""; }
function byNew(a, b){ return (b.ts || 0) - (a.ts || 0); }
function uiText(value){ return ADMIN_LANG === "en" ? (EN_TEXT[value] || value) : value; }
function h(tag, a, kids){
  var e = document.createElement(tag);
  if(a) Object.keys(a).forEach(function(k){
    if(k === "class") e.className = a[k];
    else if(k === "text"){ e.dataset.arText = a[k]; e.textContent = uiText(a[k]); }
    else if(k === "placeholder" || k === "aria-label" || k === "title"){ e.dataset["ar" + k.split("-").map(function(part){ return part.charAt(0).toUpperCase() + part.slice(1); }).join("")] = a[k]; e.setAttribute(k, uiText(a[k])); }
    else if(k.slice(0,2) === "on") e.addEventListener(k.slice(2), a[k]); else e.setAttribute(k, a[k]);
  });
  (kids || []).forEach(function add(c){
    if(Array.isArray(c)) c.forEach(add);
    else if(typeof c === "string"){ var span = document.createElement("span"); span.dataset.arText = c; span.textContent = uiText(c); e.appendChild(span); }
    else if(c != null) e.append(c);
  });
  return e;
}
function fail(message){ return new Error(message); }
function errText(e){
  if(e.message && /[\u0600-\u06FF]/.test(e.message)) return uiText(e.message);
  var arabicMessage = Object.keys(EN_TEXT).find(function(key){ return EN_TEXT[key] === e.message; });
  if(arabicMessage) return uiText(arabicMessage);
  if(e instanceof TypeError) return uiText("تعذّر الاتصال بالخادم. تحقق من إعداد رابط API واتصال الإنترنت.");
  if(e.message && e.message !== "تعذّر تنفيذ العملية على الخادم.") return e.message;
  return uiText("تعذّر تنفيذ العملية. حاول مرة أخرى.");
}
function setUiText(el, text){
  delete el.dataset.enText;
  if(ADMIN_LANG === "en"){
    Object.keys(EN_TEXT).some(function(ar){ if(EN_TEXT[ar] === text){ text = ar; return true; } return false; });
  }
  el.dataset.arText = text;
  el.textContent = uiText(text);
}
function setMsg(el, text, kind){ setUiText(el, text); el.className = "a-msg" + (kind ? " " + kind : ""); }
function setMsgLanguages(el, ar, en, kind){
  el.dataset.arText = ar;
  el.dataset.enText = en;
  el.textContent = ADMIN_LANG === "en" ? en : ar;
  el.className = "a-msg" + (kind ? " " + kind : "");
}
function applyAdminLanguage(){
  document.documentElement.lang = ADMIN_LANG;
  document.documentElement.dir = ADMIN_LANG === "ar" ? "rtl" : "ltr";
  document.body.classList.toggle("lat", ADMIN_LANG === "en");
  document.title = uiText("لوحة تحكم روضة زهرة المدائن");
  document.querySelectorAll("[data-ar-text]").forEach(function(el){ el.textContent = ADMIN_LANG === "en" && el.dataset.enText ? el.dataset.enText : uiText(el.dataset.arText); });
  document.querySelectorAll("[data-ar-placeholder]").forEach(function(el){ el.setAttribute("placeholder", uiText(el.dataset.arPlaceholder)); });
  document.querySelectorAll("[data-ar-aria-label]").forEach(function(el){ el.setAttribute("aria-label", uiText(el.dataset.arAriaLabel)); });
  document.querySelectorAll("[data-ar-title]").forEach(function(el){ el.setAttribute("title", uiText(el.dataset.arTitle)); });
  document.querySelectorAll(".a-lang button").forEach(function(button){ button.setAttribute("aria-pressed", String((button.textContent === "ع" ? "ar" : "en") === ADMIN_LANG)); });
}
function languageSwitch(){
  var group = h("div", {class:"a-lang", role:"group", "aria-label":"اللغة / Language"});
  [["ar","ع"],["en","EN"]].forEach(function(choice){
    var button = h("button", {type:"button", "aria-pressed":String(ADMIN_LANG === choice[0]), text:choice[1]});
    button.addEventListener("click", function(){ setAdminLanguage(choice[0]); });
    group.appendChild(button);
  });
  return group;
}
function setAdminLanguage(lang){
  if(lang !== "ar" && lang !== "en" || lang === ADMIN_LANG) return;
  ADMIN_LANG = lang;
  try{ localStorage.setItem("zm-admin-lang", lang); }catch(e){}
  applyAdminLanguage();
}

async function request(path, options){
  options = options || {};
  var headers = new Headers(options.headers || {});
  if(ADMIN_TOKEN) headers.set("Authorization", "Bearer " + ADMIN_TOKEN);
  if(options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  var response = await fetch(API_BASE + path, Object.assign({}, options, {headers: headers}));
  var result = null;
  try{ result = await response.json(); }catch(e){}
  if(!response.ok) throw fail(result && result.detail ? result.detail : "تعذّر تنفيذ العملية على الخادم.");
  return result;
}
async function api(method, url, body){
  var resource = url.replace("/admin/api/", "");
  var path = "/api/admin/" + resource;
  return request(path, {
    method: method,
    body: body == null ? undefined : (body instanceof FormData ? body : JSON.stringify(body))
  });
}
var fill = null;
async function reload(){ DATA = await api("GET", "/admin/api/content"); if(fill) fill(); }
function twoStep(label, action){
  var b = h("button", {type:"button", class:"a-btn danger", text:label}), armed = false, t;
  b.addEventListener("click", function(){
    if(!armed){ armed = true; setUiText(b, "اضغط مرة أخرى للتأكيد"); t = setTimeout(function(){ armed = false; setUiText(b, label); }, 4000); return; }
    clearTimeout(t); b.disabled = true; action().then(null, function(e){ b.disabled = false; armed = false; setUiText(b, label); alert(errText(e)); });
  });
  return b;
}

function tabMedia(kind){
  var isVid = kind === "video", msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var file = h("input", {type:"file", id:"a-file", accept: isVid ? "video/mp4,video/webm" : "image/jpeg,image/png,image/webp,image/gif"});
  if(!isVid) file.multiple = true;
  var cap = h("input", {type:"text", id:"a-cap", maxlength:"120", placeholder:"مثال: يوم الرسم في الروضة"});
  var go = h("button", {type:"button", class:"a-btn sun", text: isVid ? "رفع الفيديو" : "رفع الصور"});
  go.addEventListener("click", async function(){
    var files = Array.prototype.slice.call(file.files || []);
    if(!files.length){ setMsg(msg, isVid ? "اختر ملف فيديو أولاً." : "اختر صورة واحدة أو أكثر أولاً.", "err"); return; }
    go.disabled = true; var done = 0;
    try{
      for(var i = 0; i < files.length; i++){
        setMsgLanguages(msg, "جارٍ الرفع " + (i + 1) + " من " + files.length + "…", "Uploading " + (i + 1) + " of " + files.length + "…");
        var fd = new FormData(); fd.append("file", files[i]); fd.append("kind", kind); fd.append("caption", cap.value);
        await api("POST", "/admin/api/gallery", fd); done++;
      }
      setMsgLanguages(msg, "تم رفع " + done + (isVid ? " فيديو" : " صورة") + " وظهر في الموقع.", done + (isVid ? " video(s) uploaded and published." : " photo(s) uploaded and published."), "ok");
      file.value = ""; cap.value = ""; await reload();
    }catch(e){ setMsg(msg, (done ? (ADMIN_LANG === "en" ? done + " uploaded. " : "تم رفع " + done + " فقط. ") : "") + errText(e), "err"); }
    go.disabled = false;
  });
  var form = h("div", {class:"a-card"}, [
    h("h3", {text: isVid ? "رفع فيديو جديد" : "رفع صور جديدة"}),
    h("label", {for:"a-file", text: isVid ? "ملف الفيديو (MP4 أو WebM، حتى 25 ميغابايت)" : "الصور (يمكن اختيار عدة صور، تُصغَّر تلقائياً)"}), file,
    h("label", {for:"a-cap", text:"تعليق يظهر تحت العنصر (اختياري)"}), cap,
    isVid ? h("p", {class:"hint", text:"فيديوهات الهاتف بصيغة MOV لا تعمل. صدّرها بصيغة MP4."}) : null,
    h("div", {class:"a-row"}, [go]), msg]);
  var list = h("div", {class:"a-grid"});
  fill = function(){
    list.innerHTML = "";
    var items = DATA.gallery.filter(function(g){ return isVid ? g.kind === "video" : g.kind !== "video"; }).sort(byNew);
    if(!items.length){ list.appendChild(h("p", {class:"hint", text: isVid ? "لا توجد فيديوهات مرفوعة بعد." : "لا توجد صور مرفوعة بعد."})); return; }
    items.forEach(function(g){
      var media = isVid ? h("video", {src:up(g.asset), controls:"", preload:"metadata"}) : h("img", {src:up(g.asset), alt:sOf(g.caption, 120), loading:"lazy"});
      var caption = h("input", {type:"text", maxlength:"120", value:sOf(g.caption, 120), placeholder:"تعليق", "aria-label":"التعليق"});
      caption.addEventListener("change", function(){ api("PATCH", "/admin/api/gallery/" + g.id, {caption:caption.value}).catch(function(e){ alert(errText(e)); }); });
      list.appendChild(h("div", {class:"a-item"}, [media, h("div", {class:"b"}, [caption, twoStep("حذف", function(){ return api("DELETE", "/admin/api/gallery/" + g.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, h("h3", {text:isVid ? "الفيديوهات المنشورة" : "الصور المنشورة"}), list]);
}

function tabNews(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"}), editing = null;
  var tag = h("input", {type:"text", id:"n-tag", maxlength:"30", value:"خبر"}), title = h("input", {type:"text", id:"n-title", maxlength:"120"});
  var text = h("textarea", {id:"n-text", maxlength:"1500"}), file = h("input", {type:"file", id:"n-file", accept:"image/jpeg,image/png,image/webp,image/gif"});
  var rm = h("input", {type:"checkbox", id:"n-rm"}), rmRow = h("label", {class:"a-check", hidden:""}, [rm, "حذف الصورة الحالية"]);
  var save = h("button", {type:"button", class:"a-btn sun", text:"نشر الخبر"}), cancel = h("button", {type:"button", class:"a-btn ghost", text:"إلغاء التعديل", hidden:""});
  var head = h("h3", {text:"خبر جديد"});
  function reset(){ editing = null; tag.value = "خبر"; title.value = ""; text.value = ""; file.value = ""; rm.checked = false; rmRow.hidden = true; cancel.hidden = true; setUiText(save, "نشر الخبر"); setUiText(head, "خبر جديد"); }
  cancel.addEventListener("click", function(){ reset(); setMsg(msg, ""); });
  save.addEventListener("click", async function(){
    if(!title.value.trim() || !text.value.trim()){ setMsg(msg, "اكتب العنوان والنص.", "err"); return; }
    save.disabled = true;
    try{
      var fd = new FormData(); fd.append("tag", tag.value); fd.append("title", title.value); fd.append("text", text.value);
      if(file.files && file.files[0]) fd.append("file", file.files[0]);
      if(rm.checked) fd.append("remove_image", "1");
      await api("POST", editing ? "/admin/api/news/" + editing.id : "/admin/api/news", fd);
      reset(); setMsg(msg, "تم نشر الخبر في الموقع.", "ok"); await reload();
    }catch(e){ setMsg(msg, errText(e), "err"); }
    save.disabled = false;
  });
  var form = h("div", {class:"a-card"}, [head,
    h("label", {for:"n-tag", text:"التصنيف (كلمة قصيرة)"}), tag, h("label", {for:"n-title", text:"العنوان"}), title,
    h("label", {for:"n-text", text:"النص"}), text, h("label", {for:"n-file", text:"صورة (اختيارية)"}), file, rmRow,
    h("div", {class:"a-row"}, [save, cancel]), msg]);
  var list = h("div", {class:"a-card"});
  fill = function(){
    list.innerHTML = ""; list.appendChild(h("h3", {text:"الأخبار المنشورة"}));
    var items = DATA.news.slice().sort(byNew);
    if(!items.length) list.appendChild(h("p", {class:"hint", text:"لا توجد أخبار مضافة."}));
    items.forEach(function(n){
      var img = up(n.asset) ? h("img", {src:up(n.asset), alt:""}) : null;
      var edit = h("button", {type:"button", class:"a-btn ghost", text:"تعديل"});
      edit.addEventListener("click", function(){
        editing = n; tag.value = sOf(n.tag, 30); title.value = sOf(n.title, 120); text.value = sOf(n.text, 1500); file.value = ""; rm.checked = false;
        rmRow.hidden = !n.asset; cancel.hidden = false; setUiText(save, "حفظ التعديل"); setUiText(head, "تعديل الخبر"); form.scrollIntoView({behavior:"smooth", block:"start"});
      });
      list.appendChild(h("div", {class:"a-news"}, [img, h("div", {class:"t"}, [h("b", {text:sOf(n.title, 120)}), h("span", {text:sOf(n.tag, 30)})]),
        h("div", {class:"a-row", style:"margin:0"}, [edit, twoStep("حذف", function(){ return api("DELETE", "/admin/api/news/" + n.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, list]);
}

function tabSettings(){
  var s = DATA.settings, msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  function fld(id, label, val, type, ph, hint){ return [h("label", {for:id, text:label}), h("input", {type:type || "text", id:id, value:sOf(val, 300), placeholder:ph || "", maxlength:"300"}), hint ? h("p", {class:"hint", text:hint}) : null]; }
  var F = {
    announce: fld("s-ann", "شريط إعلان أعلى الموقع", s.announce, "text", "مثال: التسجيل مفتوح للعام الدراسي الجديد", "اتركه فارغاً لإخفاء الشريط."),
    phone: fld("s-ph", "رقم الهاتف الظاهر", s.phone, "text", "+963 985 122 704"),
    whatsapp: fld("s-wa", "رقم الواتساب بالصيغة الدولية، أرقام فقط", s.whatsapp, "text", "963985122704", "مثال: 963985122704"),
    hours: fld("s-hr", "أوقات الدوام", s.hours, "text", "مثال: من الأحد إلى الخميس، 8:00 إلى 13:00"),
    facebook: fld("s-fb", "رابط صفحة فيسبوك", s.facebook, "url", "https://www.facebook.com/…"),
    instagram: fld("s-ig", "رابط صفحة إنستغرام", s.instagram, "url", "https://www.instagram.com/…"),
    email: fld("s-em", "البريد الإلكتروني", s.email, "email", "")
  };
  var hn = h("input", {type:"checkbox"}); hn.checked = !!s.hideDefaultNews;
  var hg = h("input", {type:"checkbox"}); hg.checked = !!s.hideDefaultGallery;
  var save = h("button", {type:"button", class:"a-btn sun", text:"حفظ الإعدادات"});
  save.addEventListener("click", async function(){
    var body = {hideDefaultNews:hn.checked, hideDefaultGallery:hg.checked};
    Object.keys(F).forEach(function(k){ body[k] = F[k][1].value.trim(); });
    save.disabled = true;
    try{ DATA.settings = await api("PUT", "/admin/api/settings", body); setMsg(msg, "تم حفظ الإعدادات وطُبّقت على الموقع.", "ok"); }
    catch(e){ setMsg(msg, errText(e), "err"); }
    save.disabled = false;
  });
  fill = null;
  return h("div", {class:"a-card"}, [h("h3", {text:"معلومات التواصل والإعلان"})].concat(Object.keys(F).map(function(k){ return F[k]; }), [
    h("h3", {text:"المحتوى الأصلي للموقع", style:"margin-top:18px"}),
    h("label", {class:"a-check"}, [hn, "إخفاء الخبر الافتتاحي الأصلي"]), h("label", {class:"a-check"}, [hg, "إخفاء الصور الأصلية في المعرض"]),
    h("div", {class:"a-row"}, [save]), msg]));
}

function tabAccounts(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var username = h("input", {type:"text", id:"a-teacher-username", autocomplete:"username", minlength:"3", maxlength:"80", pattern:"[A-Za-z0-9_.\\-]{3,80}"});
  var password = h("input", {type:"password", id:"a-teacher-password", autocomplete:"new-password", minlength:"12", maxlength:"256"});
  var create = h("button", {type:"submit", class:"a-btn sun", text:"إنشاء حساب المعلمة"});
  var form = h("form", {class:"a-card"}, [
    h("h3", {text:"أنشئ حساب معلمة جديداً. يكون الحساب مفعّلاً فوراً."}),
    h("label", {for:"a-teacher-username", text:"اسم المستخدم"}), username,
    h("label", {for:"a-teacher-password", text:"كلمة المرور الأولية (12 محرفاً على الأقل)"}), password,
    h("div", {class:"a-row"}, [create]), msg
  ]);
  var list = h("div", {class:"a-card"});
  var listBody = h("div", {});
  list.append(h("h3", {text:"طلبات أولياء الأمور والمعلمات"}), listBody);

  var reqCard = h("div", {class:"a-card"});
  var reqMsg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var reqCode = h("div", {});
  var reqBody = h("div", {});
  reqCard.append(h("h3", {text:"طلبات تسجيل أولياء الأمور"}),
    h("p", {class:"hint", text:"يرسل ولي الأمر بياناته من بوابة الأهل. عند الموافقة يُنشأ رمز تسجيل لمرة واحدة (صالح 7 أيام) يُرسل إلى بريده، ويظهر لك هنا مرة واحدة لتسلّمه يدوياً عند الحاجة."}),
    reqMsg, reqCode, reqBody);
  function showApprovalCode(result){
    var base = (window.location.origin.indexOf("http") === 0 ? window.location.origin : "https://zahra-123hub.github.io/Zahra-Almadain").replace(/\/admin.*$/, "");
    var link = base + "/login/?code=" + encodeURIComponent(result.registration_code);
    var sent = result.request.email_sent;
    reqCode.innerHTML = "";
    var codeBox = h("div", {style:"font-size:2rem;font-weight:800;letter-spacing:.18em;direction:ltr;text-align:center;padding:14px;margin:10px 0;border:2px dashed var(--sun);border-radius:14px", text:result.registration_code});
    var linkInput = h("input", {type:"text", readonly:"readonly", value:link, dir:"ltr", style:"width:100%"});
    reqCode.appendChild(h("div", {class:"a-card", style:"border:2px solid var(--sun)"}, [
      h("strong", {text:"تمت الموافقة على الطلب: " + result.request.guardian_name}),
      h("p", {class:"hint", text: sent ? "تم إنشاء رمز التسجيل تلقائياً وأُرسل إلى بريد ولي الأمر. يظهر هنا مرة واحدة فقط." : "تم إنشاء رمز التسجيل تلقائياً. لم يُرسل البريد (لم يُضبط الإرسال)، فسلّم الرمز إلى ولي الأمر يدوياً. يظهر هنا مرة واحدة فقط."}),
      codeBox,
      h("p", {class:"hint", text:"أو الرابط المباشر:"}),
      linkInput,
      h("div", {class:"a-row"}, [h("button", {type:"button", class:"a-btn sun", text:"نسخ الرمز", onclick:function(){
        try{ navigator.clipboard.writeText(result.registration_code); }catch(e){}
      }})])
    ]));
  }
  async function decideRequest(id, decision){
    try{
      var result = await request("/api/admin/platform/registration-requests/" + encodeURIComponent(id) + "/decision", {
        method:"POST", body:JSON.stringify({decision:decision})
      });
      reqCode.innerHTML = "";
      if(decision === "approve") showApprovalCode(result);
      setMsg(reqMsg, decision === "approve" ? "تمت الموافقة وإنشاء رمز التسجيل." : "تم رفض الطلب.", "ok");
      await reloadRequests();
    }catch(error){ setMsg(reqMsg, errText(error), "err"); }
  }
  async function newCode(id){
    try{
      var result = await request("/api/admin/platform/registration-requests/" + encodeURIComponent(id) + "/new-code", {method:"POST"});
      reqCode.innerHTML = "";
      showApprovalCode(result);
      setMsg(reqMsg, "تم إنشاء رمز جديد، والرمز السابق لم يعد صالحاً.", "ok");
      await reloadRequests();
    }catch(error){ setMsg(reqMsg, errText(error), "err"); }
  }
  function editRequestForm(item, close){
    var fields = [
      ["guardian_name","اسم ولي الأمر","text"], ["email","البريد الإلكتروني","email"], ["phone","رقم الهاتف","tel"],
      ["child_name","اسم الطفل","text"], ["child_birth_date","تاريخ ميلاد الطفل","date"],
      ["relationship_to_child","صلة القرابة","text"], ["notes","ملاحظات","textarea"]
    ];
    var inputs = {};
    var formMsg = h("div", {class:"a-msg", role:"status"});
    var form = h("form", {style:"flex-basis:100%;width:100%;margin-top:12px"});
    fields.forEach(function(f){
      var input = f[2] === "textarea" ? h("textarea", {rows:"3", maxlength:"1000"}) : h("input", {type:f[2]});
      input.value = item[f[0]] || "";
      if(f[0] === "email" || f[0] === "phone") input.dir = "ltr";
      inputs[f[0]] = input;
      form.append(h("label", {text:f[1]}), input);
    });
    var save = h("button", {type:"submit", class:"a-btn sun", text:"حفظ التعديلات"});
    form.append(h("div", {class:"a-row"}, [save, h("button", {type:"button", class:"a-btn ghost", text:"إلغاء", onclick:close})]), formMsg);
    form.addEventListener("submit", async function(event){
      event.preventDefault();
      save.disabled = true;
      var body = {preferred_language:"ar"};
      fields.forEach(function(f){ body[f[0]] = inputs[f[0]].value.trim(); });
      try{
        await request("/api/admin/platform/registration-requests/" + encodeURIComponent(item.id), {method:"PATCH", body:JSON.stringify(body)});
        setMsg(reqMsg, "تم حفظ التعديلات.", "ok");
        await reloadRequests();
      }catch(error){ setMsg(formMsg, errText(error), "err"); save.disabled = false; }
    });
    return form;
  }
  async function reloadRequests(){
    reqBody.innerHTML = "";
    try{
      var items = await request("/api/admin/platform/registration-requests");
      if(!items.length){ reqBody.appendChild(h("p", {class:"hint", text:"لا توجد طلبات تسجيل."})); return; }
      items.forEach(function(item){
        var statusText = item.status === "pending" ? "بانتظار القرار" : item.status === "approved" ? (item.registered ? "تم التسجيل وإنشاء الحساب" : "تمت الموافقة، بانتظار إكمال التسجيل") : "مرفوض";
        var details = [
          "الهاتف: " + item.phone,
          "البريد: " + item.email,
          "الطفل: " + item.child_name + (item.child_birth_date ? " (" + item.child_birth_date + ")" : ""),
          item.relationship_to_child ? "صلة القرابة: " + item.relationship_to_child : "",
          item.notes ? "ملاحظات: " + item.notes : ""
        ].filter(Boolean);
        var row = h("article", {class:"a-account-row"}, [
          h("div", {}, [
            h("strong", {text:item.guardian_name}),
            h("span", {class:"a-account-meta", text:statusText}),
            details.map(function(line){ return h("span", {class:"a-account-date", dir:"auto", text:line}); }),
            item.created_at ? h("time", {class:"a-account-date", text:new Date(item.created_at).toLocaleDateString(ADMIN_LANG === "ar" ? "ar" : "en")}) : null
          ])
        ]);
        var actions = h("div", {class:"a-row"});
        if(item.status === "pending"){
          actions.append(
            h("button", {type:"button", class:"a-btn sun", text:"موافقة وإنشاء الرمز", onclick:function(){ decideRequest(item.id, "approve"); }}),
            h("button", {type:"button", class:"a-btn danger", text:"رفض", onclick:function(){ decideRequest(item.id, "reject"); }})
          );
        }
        if(item.status === "approved" && !item.registered){
          actions.appendChild(h("button", {type:"button", class:"a-btn sun", text:"رمز جديد", onclick:function(){ newCode(item.id); }}));
        }
        var holder = h("div", {style:"flex-basis:100%;width:100%"});
        actions.appendChild(h("button", {type:"button", class:"a-btn ghost", text:"تعديل", onclick:function(){
          if(holder.firstChild){ holder.innerHTML = ""; return; }
          holder.appendChild(editRequestForm(item, function(){ holder.innerHTML = ""; }));
        }}));
        if(!item.registered){
          actions.appendChild(twoStep("حذف الطلب", async function(){
            await request("/api/admin/platform/registration-requests/" + encodeURIComponent(item.id), {method:"DELETE"});
            setMsg(reqMsg, "تم حذف الطلب.", "ok");
            await reloadRequests();
          }));
        }
        row.appendChild(actions);
        row.appendChild(holder);
        reqBody.appendChild(row);
      });
    }catch(error){ reqBody.appendChild(h("p", {class:"a-msg err", text:error.message || "تعذّر تنفيذ العملية على الخادم."})); }
  }
  reloadRequests();
  async function reloadAccounts(){
    listBody.innerHTML = "";
    try{
      var accounts = await request("/api/admin/platform/accounts");
      if(!accounts.length){ listBody.appendChild(h("p", {class:"hint", text:"لا توجد حسابات أولياء أمور أو معلمات."})); return; }
      accounts.forEach(function(account){
        var role = account.roles.indexOf("teacher") !== -1 ? "معلمة" : "ولي أمر";
        var status = account.approval_status === "active" ? "نشط" : account.approval_status === "pending" ? "بانتظار التفعيل" : "موقوف";
        var row = h("article", {class:"a-account-row"}, [
          h("div", {}, [
            h("strong", {text:account.username}),
            h("span", {class:"a-account-meta", text:role + " · " + status}),
            account.guardian_name ? h("span", {class:"a-account-date", dir:"auto", text:"ولي الأمر: " + account.guardian_name + " · " + account.phone}) : null,
            account.guardian_name ? h("span", {class:"a-account-date", dir:"auto", text:"البريد: " + account.email + " · الطفل: " + account.child_name}) : null,
            account.created_at ? h("time", {class:"a-account-date", text:new Date(account.created_at).toLocaleDateString(ADMIN_LANG === "ar" ? "ar" : "en")}) : null
          ])
        ]);
        if(account.approval_status !== "active"){
          row.appendChild(h("button", {type:"button", class:"a-btn sun", text:"تفعيل الحساب", onclick:function(){
            updateStatus(account.id, "active");
          }}));
        } else {
          row.appendChild(h("button", {type:"button", class:"a-btn danger", text:"إيقاف الحساب", onclick:function(){
            updateStatus(account.id, "disabled");
          }}));
        }
        listBody.appendChild(row);
      });
    }catch(error){ listBody.appendChild(h("p", {class:"a-msg err", text:error.message || "تعذّر تنفيذ العملية على الخادم."})); }
  }
  async function updateStatus(accountId, status){
    try{
      await request("/api/admin/platform/accounts/" + encodeURIComponent(accountId) + "/status", {
        method:"PATCH", body:JSON.stringify({status:status})
      });
      setMsg(msg, "تم تحديث حالة الحساب.", "ok");
      await reloadAccounts();
    }catch(error){ setMsg(msg, errText(error), "err"); }
  }
  form.addEventListener("submit", async function(event){
    event.preventDefault();
    if(!/^[A-Za-z0-9_.-]{3,80}$/.test(username.value.trim()) || password.value.length < 12){
      setMsg(msg, "الاسم أو كلمة المرور غير صالحة.", "err"); return;
    }
    create.disabled = true;
    try{
      await request("/api/admin/platform/teacher-accounts", {
        method:"POST",
        body:JSON.stringify({
          username:username.value.trim(),
          password:password.value,
          preferred_language:"ar"
        })
      });
      username.value = ""; password.value = "";
      setMsg(msg, "تم إنشاء حساب المعلمة وتفعيله. يمكنها تسجيل الدخول الآن.", "ok");
      await reloadAccounts();
    }catch(error){ setMsg(msg, errText(error), "err"); }
    create.disabled = false;
  });
  reloadAccounts();
  fill = null;
  return h("section", {}, [
    h("div", {class:"a-card"}, [
      h("h3", {text:"حسابات المنصة"}),
      h("p", {class:"hint", text:"تسجيل ولي الأمر برمز الدعوة ينشئ حساباً معلقاً. راجع الحساب ثم فعّله ليتمكن من الدخول. يمكنك أيضاً إنشاء حسابات المعلمات وإيقاف الحسابات عند الحاجة."})
    ]),
    reqCard,
    form,
    list
  ]);
}

function tabChildren(){
  var msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var reportsBody = h("div", {});
  var childrenBody = h("div", {});
  var reportsCard = h("div", {class:"a-card"}, [h("h3", {text:"تقارير بانتظار المراجعة"}),
    h("p", {class:"hint", text:"تظهر التقارير للأهل فقط بعد نشرها من هنا. لا يرى الأهل إلا تقارير طفلهم."}), reportsBody]);
  var childrenCard = h("div", {class:"a-card"}, [h("h3", {text:"الأطفال والمعلمات"}),
    h("p", {class:"hint", text:"عيّن معلمة لكل طفل. لا تستطيع المعلمة كتابة تقرير إلا للأطفال المعيّنين لها."}), childrenBody]);
  async function loadReports(){
    reportsBody.innerHTML = "";
    try{
      var reports = await request("/api/admin/platform/reports");
      if(!reports.length){ reportsBody.appendChild(h("p", {class:"hint", text:"لا توجد تقارير بانتظار المراجعة."})); return; }
      reports.forEach(function(report){
        function review(status){
          return async function(){
            try{
              await request("/api/admin/platform/reports/" + encodeURIComponent(report.id), {method:"PATCH", body:JSON.stringify({status:status})});
              setMsg(msg, status === "published" ? "تم نشر التقرير للأهل." : "تم إرجاع التقرير للمعلمة للتعديل.", "ok");
              await loadReports();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          };
        }
        reportsBody.appendChild(h("article", {class:"a-account-row"}, [
          h("div", {style:"flex:1;min-width:220px"}, [
            h("strong", {dir:"auto", text:report.title}),
            h("span", {class:"a-account-meta", dir:"auto", text:"الطفل: " + report.child_name + " · المعلمة: " + report.author}),
            h("span", {class:"a-account-date", dir:"auto", style:"white-space:pre-wrap", text:report.body})
          ]),
          h("div", {class:"a-row"}, [
            h("button", {type:"button", class:"a-btn sun", text:"نشر للأهل", onclick:review("published")}),
            h("button", {type:"button", class:"a-btn ghost", text:"إرجاع للتعديل", onclick:review("rejected")})
          ])
        ]));
      });
    }catch(error){ reportsBody.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  async function loadChildren(){
    childrenBody.innerHTML = "";
    try{
      var results = await Promise.all([request("/api/admin/platform/children"), request("/api/admin/platform/accounts")]);
      var children = results[0];
      var teachers = results[1].filter(function(a){ return a.roles.indexOf("teacher") !== -1 && a.approval_status === "active"; });
      if(!children.length){ childrenBody.appendChild(h("p", {class:"hint", text:"لا توجد ملفات أطفال بعد. تُنشأ تلقائياً عند الموافقة على طلب تسجيل."})); return; }
      children.forEach(function(child){
        var chips = h("div", {class:"a-row", style:"margin:6px 0"});
        child.teachers.forEach(function(teacher){
          chips.appendChild(h("button", {type:"button", class:"a-btn ghost", title:"إزالة التعيين", text:teacher.username + " ✕", onclick:async function(){
            try{
              await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/teachers/" + encodeURIComponent(teacher.id), {method:"DELETE"});
              await loadChildren();
            }catch(error){ setMsg(msg, errText(error), "err"); }
          }}));
        });
        var assignedIds = child.teachers.map(function(t){ return t.id; });
        var options = teachers.filter(function(t){ return assignedIds.indexOf(t.id) === -1; });
        var select = h("select", {"aria-label":"اختر معلمة"});
        options.forEach(function(t){ select.appendChild(new Option(t.username, t.id)); });
        var add = h("button", {type:"button", class:"a-btn sun", text:"تعيين معلمة", onclick:async function(){
          if(!select.value) return;
          try{
            await request("/api/admin/platform/children/" + encodeURIComponent(child.id) + "/teachers", {method:"POST", body:JSON.stringify({teacher_id:select.value})});
            setMsg(msg, "تم تعيين المعلمة.", "ok");
            await loadChildren();
          }catch(error){ setMsg(msg, errText(error), "err"); }
        }});
        childrenBody.appendChild(h("article", {class:"a-account-row"}, [
          h("div", {style:"flex:1;min-width:220px"}, [
            h("strong", {dir:"auto", text:child.display_name}),
            h("span", {class:"a-account-date", text:child.parents.length ? "ولي الأمر: " + child.parents.join("، ") : "لم يكتمل تسجيل ولي الأمر بعد"}),
            h("span", {class:"a-account-date", text:child.teachers.length ? "المعلمات:" : "لا توجد معلمة معيّنة"}),
            chips
          ]),
          options.length ? h("div", {class:"a-row"}, [select, add]) : h("span", {class:"a-account-date", text:teachers.length ? "كل المعلمات معيّنات" : "أنشئ حساب معلمة أولاً"})
        ]));
      });
    }catch(error){ childrenBody.appendChild(h("p", {class:"a-msg err", text:errText(error)})); }
  }
  loadReports(); loadChildren();
  fill = null;
  return h("section", {}, [msg, reportsCard, childrenCard]);
}

var TABS = [["gallery","الصور"],["video","الفيديو"],["news","الأخبار"],["children","الأطفال والتقارير"],["accounts","حسابات المنصة"],["settings","الإعدادات"]]
  .filter(function(t){ return !TEACHER_MODE || ["gallery","video","news"].indexOf(t[0]) !== -1; });
function draw(){
  var root = document.getElementById("app"); root.innerHTML = "";
  var out = h("button", {type:"button", class:"a-btn ghost", style:"color:#fff;border-color:#fff", text:"خروج", onclick:function(){ clearSessions(); start(); }});
  var view = h("a", {class:"a-btn sun", href:"../", target:"_blank", rel:"noopener", style:"text-decoration:none", text:"عرض الموقع"});
  var back = TEACHER_MODE ? h("a", {class:"a-btn ghost", href:"../teachers/", style:"color:#fff;border-color:#fff;text-decoration:none", text:"العودة إلى بوابتي"}) : null;
  var tabs = h("div", {class:"a-tabs", role:"tablist"});
  TABS.forEach(function(t){
    var b = h("button", {type:"button", role:"tab", "aria-selected":String(tab === t[0]), text:t[1]});
    b.addEventListener("click", function(){ tab = t[0]; draw(); }); tabs.appendChild(b);
  });
  var main = h("div", {class:"a-main"}); fill = null;
  main.appendChild(tab === "video" ? tabMedia("video") : tab === "news" ? tabNews() : tab === "settings" ? tabSettings() : tab === "accounts" ? tabAccounts() : tab === "children" ? tabChildren() : tabMedia("image"));
  root.append(h("div", {class:"a-bar"}, [h("div", {class:"a-top"}, [h("h2", {text:"لوحة تحكم روضة زهرة المدائن"}), h("div", {class:"a-row", style:"margin:0"}, [languageSwitch(), back, view, out])]), tabs]), main);
}
function loginScreen(msg){
  var root = document.getElementById("app"); root.innerHTML = "";
  var err = h("div", {class:"a-msg err", role:"alert", text:msg || ""});
  var username = h("input", {type:"text", id:"l-user", value:"admin", autocomplete:"username"});
  var password = h("input", {type:"password", id:"l-pass", autocomplete:"current-password"});
  var go = h("button", {type:"button", class:"a-btn sun", text:"دخول"});
  go.addEventListener("click", async function(){
    if(!username.value.trim() || !password.value){ setMsg(err, "أدخل اسم المستخدم وكلمة المرور.", "err"); return; }
    go.disabled = true;
    try{
      var result = await request("/api/auth/login", {method:"POST", body:JSON.stringify({username:username.value.trim(), password:password.value})});
      ADMIN_TOKEN = result.access_token; sessionStorage.setItem("zm-admin-session", ADMIN_TOKEN);
      DATA = await loadContent(); draw();
    }catch(e){ ADMIN_TOKEN = ""; sessionStorage.removeItem("zm-admin-session"); go.disabled = false; setMsg(err, errText(e), "err"); }
  });
  root.append(h("div", {class:"a-main", style:"max-width:420px"}, [h("div", {class:"a-card"}, [
    h("div", {class:"a-login-tools"}, [languageSwitch()]),
    h("h3", {text:"دخول المسؤول"}), h("p", {class:"hint", text:"أدخل بيانات دخول لوحة التحكم التي أُعدّت على الخادم."}),
    h("label", {for:"l-user", text:"اسم المستخدم"}), username,
    h("label", {for:"l-pass", text:"كلمة المرور"}), password,
    h("div", {class:"a-row"}, [go]), err])]));
}
// If only the GitHub connection is missing (e.g. local testing), still open the dashboard
// so the platform accounts tab remains usable.
async function loadContent(){
  try{ return await api("GET", "/admin/api/content"); }
  catch(e){
    if(e && e.message && /GitHub/.test(e.message)){
      tab = TEACHER_MODE ? "gallery" : "accounts";
      return {settings:{}, gallery:[], news:[]};
    }
    throw e;
  }
}
function start(){
  if(!ADMIN_TOKEN){ window.location.replace("../login/"); return; }
  loadContent().then(function(data){ DATA = data; draw(); }, function(e){
    clearSessions(); window.location.replace("../login/");
  });
}
applyAdminLanguage();
start();
