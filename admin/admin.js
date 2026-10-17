var DATA = {settings:{}, gallery:[], news:[]}, tab = "gallery";
var API_BASE = (window.ZM_API_BASE || "https://zahra-123hub-almadain-api.onrender.com").replace(/\/+$/, "");
var ADMIN_TOKEN = sessionStorage.getItem("zm-admin-session") || "";
var FILE_RE = /^[0-9a-f]{32}\.(jpg|png|webp|gif|mp4|webm)$/;

try{ localStorage.removeItem("zm-gh"); }catch(e){}
function up(name){ return FILE_RE.test(name || "") ? API_BASE + "/api/assets/" + name : ""; }
function sOf(v, n){ return typeof v === "string" ? v.slice(0, n) : ""; }
function byNew(a, b){ return (b.ts || 0) - (a.ts || 0); }
function h(tag, a, kids){
  var e = document.createElement(tag);
  if(a) Object.keys(a).forEach(function(k){
    if(k === "class") e.className = a[k]; else if(k === "text") e.textContent = a[k];
    else if(k.slice(0,2) === "on") e.addEventListener(k.slice(2), a[k]); else e.setAttribute(k, a[k]);
  });
  (kids || []).forEach(function add(c){ if(Array.isArray(c)) c.forEach(add); else if(c != null) e.append(c); });
  return e;
}
function fail(message){ return new Error(message); }
function errText(e){
  if(e.message && /[\u0600-\u06FF]/.test(e.message)) return e.message;
  if(e instanceof TypeError) return "تعذّر الاتصال بالخادم. تحقق من إعداد رابط API واتصال الإنترنت.";
  return "تعذّر تنفيذ العملية. حاول مرة أخرى.";
}
function setMsg(el, text, kind){ el.textContent = text; el.className = "a-msg" + (kind ? " " + kind : ""); }

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
    if(!armed){ armed = true; b.textContent = "اضغط مرة أخرى للتأكيد"; t = setTimeout(function(){ armed = false; b.textContent = label; }, 4000); return; }
    clearTimeout(t); b.disabled = true; action().then(null, function(e){ b.disabled = false; armed = false; b.textContent = label; alert(errText(e)); });
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
        setMsg(msg, "جارٍ الرفع " + (i + 1) + " من " + files.length + "…");
        var fd = new FormData(); fd.append("file", files[i]); fd.append("kind", kind); fd.append("caption", cap.value);
        await api("POST", "/admin/api/gallery", fd); done++;
      }
      setMsg(msg, "تم رفع " + done + (isVid ? " فيديو" : " صورة") + " وظهر في الموقع.", "ok");
      file.value = ""; cap.value = ""; await reload();
    }catch(e){ setMsg(msg, (done ? "تم رفع " + done + " فقط. " : "") + errText(e), "err"); }
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
  function reset(){ editing = null; tag.value = "خبر"; title.value = ""; text.value = ""; file.value = ""; rm.checked = false; rmRow.hidden = true; cancel.hidden = true; save.textContent = "نشر الخبر"; head.textContent = "خبر جديد"; }
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
        rmRow.hidden = !n.asset; cancel.hidden = false; save.textContent = "حفظ التعديل"; head.textContent = "تعديل الخبر"; form.scrollIntoView({behavior:"smooth", block:"start"});
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

var TABS = [["gallery","الصور"],["video","الفيديو"],["news","الأخبار"],["settings","الإعدادات"]];
function draw(){
  var root = document.getElementById("app"); root.innerHTML = "";
  var out = h("button", {type:"button", class:"a-btn ghost", style:"color:#fff;border-color:#fff", text:"خروج", onclick:function(){ sessionStorage.removeItem("zm-admin-session"); ADMIN_TOKEN = ""; start(); }});
  var view = h("a", {class:"a-btn sun", href:"../", target:"_blank", rel:"noopener", style:"text-decoration:none", text:"عرض الموقع"});
  var tabs = h("div", {class:"a-tabs", role:"tablist"});
  TABS.forEach(function(t){
    var b = h("button", {type:"button", role:"tab", "aria-selected":String(tab === t[0]), text:t[1]});
    b.addEventListener("click", function(){ tab = t[0]; draw(); }); tabs.appendChild(b);
  });
  var main = h("div", {class:"a-main"}); fill = null;
  main.appendChild(tab === "video" ? tabMedia("video") : tab === "news" ? tabNews() : tab === "settings" ? tabSettings() : tabMedia("image"));
  root.append(h("div", {class:"a-bar"}, [h("div", {class:"a-top"}, [h("h2", {text:"لوحة تحكم روضة زهرة المدائن"}), h("div", {class:"a-row", style:"margin:0"}, [view, out])]), tabs]), main);
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
      DATA = await api("GET", "/admin/api/content"); draw();
    }catch(e){ ADMIN_TOKEN = ""; sessionStorage.removeItem("zm-admin-session"); go.disabled = false; setMsg(err, errText(e), "err"); }
  });
  root.append(h("div", {class:"a-main", style:"max-width:420px"}, [h("div", {class:"a-card"}, [
    h("h3", {text:"دخول المسؤول"}), h("p", {class:"hint", text:"أدخل بيانات دخول لوحة التحكم التي أُعدّت على الخادم."}),
    h("label", {for:"l-user", text:"اسم المستخدم"}), username,
    h("label", {for:"l-pass", text:"كلمة المرور"}), password,
    h("div", {class:"a-row"}, [go]), err])]));
}
function start(){
  if(!ADMIN_TOKEN){ loginScreen(); return; }
  api("GET", "/admin/api/content").then(function(data){ DATA = data; draw(); }, function(e){
    ADMIN_TOKEN = ""; sessionStorage.removeItem("zm-admin-session"); loginScreen(errText(e));
  });
}
start();
