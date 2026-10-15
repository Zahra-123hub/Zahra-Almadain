var DATA = {settings:{}, gallery:[], news:[]}, tab = "gallery", FILE_RE = /^[0-9a-f]{32}\.(jpg|png|webp|gif|mp4|webm)$/;
function up(f){ return FILE_RE.test(f || "") ? f : ""; }
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
/* ===== GitHub-Backend: ersetzt den Server. Schreibt content.json und uploads/ per GitHub-API ins Repository ===== */
var GH = {owner:"Zahra-123hub", repo:"Zahra-Almadain", token:""};
try{ GH = Object.assign(GH, JSON.parse(localStorage.getItem("zm-gh") || "{}")); }catch(e){}
function guessRepo(){
  var m = location.hostname.match(/^([^.]+)\.github\.io$/), p = location.pathname.split("/").filter(Boolean);
  if(m) return {owner: m[1], repo: (p[0] && p[0] !== "admin") ? p[0] : m[1] + ".github.io"};
  return {owner:"", repo:""};
}
function fail(msg, status){ var e = new Error(msg); e.status = status || 400; return e; }
function normalizeRepo(value, owner){
  value = value.trim();
  var m = /^(?:https?:\/\/)?(?:www\.)?github\.com\/([^/]+)\/([^/?#]+)\/?$/i.exec(value);
  if(!m) m = /^([^/]+)\/([^/]+)$/.exec(value);
  if(m){
    if(m[1].toLowerCase() !== owner.toLowerCase()) throw fail("اسم المستخدم في رابط المستودع لا يطابق حساب GitHub.", 400);
    value = m[2];
  }
  value = value.replace(/\.git$/i, "");
  if(!/^[A-Za-z0-9_.-]+$/.test(value)) throw fail("أدخل اسم المستودع فقط، مثل Zahra-Almadain، أو رابط GitHub الكامل.", 400);
  return value;
}
async function gh(method, path, body){
  var r = await fetch("https://api.github.com/repos/" + GH.owner + "/" + GH.repo + "/contents/" + path, {
    method: method,
    headers: {"Authorization": "Bearer " + GH.token, "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    body: body ? JSON.stringify(body) : undefined, cache: "no-store"});
  var j = null; try{ j = await r.json(); }catch(e){}
  if(r.status === 401) throw fail("الرمز (Token) غير صالح أو منتهي. سجّل الدخول من جديد.", 401);
  if(r.status === 403 || r.status === 404 && path === "content.json") throw fail("تعذّر الوصول إلى المستودع. تحقق من الاسم، ومن صلاحية Contents للرمز (قراءة وكتابة).", r.status);
  if(!r.ok){ var e = fail((j && j.message) || "error", r.status); throw e; }
  return j;
}
function b64utf8(str){ var b = new TextEncoder().encode(str), s = ""; for(var i = 0; i < b.length; i += 8192) s += String.fromCharCode.apply(null, b.subarray(i, i + 8192)); return btoa(s); }
function unb64utf8(b64){ var s = atob(b64.replace(/\n/g, "")), b = new Uint8Array(s.length); for(var i = 0; i < s.length; i++) b[i] = s.charCodeAt(i); return new TextDecoder().decode(b); }
function fileB64(blob){ return new Promise(function(res, rej){ var fr = new FileReader(); fr.onload = function(){ res(String(fr.result).split(",")[1]); }; fr.onerror = rej; fr.readAsDataURL(blob); }); }
function rid(n){ var a = new Uint8Array(n); crypto.getRandomValues(a); return Array.prototype.map.call(a, function(x){ return ("0" + x.toString(16)).slice(-2); }).join(""); }
async function readContent(){
  var j = await gh("GET", "content.json"), d = {};
  try{ d = JSON.parse(unb64utf8(j.content)); }catch(e){}
  d.settings = d.settings || {}; d.gallery = d.gallery || []; d.news = d.news || [];
  return {d: d, sha: j.sha};
}
/* ändert content.json: fn(d) verändert die Daten; bei Versionskonflikt (409) einmal neu laden und wiederholen */
async function mutate(fn, msg){
  for(var t = 0; t < 3; t++){
    var c = await readContent(), out = fn(c.d);
    try{ await gh("PUT", "content.json", {message: msg, content: b64utf8(JSON.stringify(c.d, null, 1)), sha: c.sha}); return out; }
    catch(e){ if(e.status !== 409 && e.status !== 422) throw e; }
  }
  throw fail("تعذّر الحفظ بسبب تعارض. أعد المحاولة.", 409);
}
function sniff(u8){
  function eq(a, o){ for(var i = 0; i < a.length; i++) if(u8[o + i] !== a[i]) return false; return true; }
  if(eq([0xff,0xd8,0xff],0)) return ["jpg","image"]; if(eq([0x89,0x50,0x4e,0x47],0)) return ["png","image"];
  if(eq([0x47,0x49,0x46,0x38],0)) return ["gif","image"]; if(eq([0x52,0x49,0x46,0x46],0) && eq([0x57,0x45,0x42,0x50],8)) return ["webp","image"];
  if(eq([0x66,0x74,0x79,0x70],4)) return ["mp4","video"]; if(eq([0x1a,0x45,0xdf,0xa3],0)) return ["webm","video"];
  return [null, null];
}
async function shrink(file, ext){
  try{
    if(ext !== "jpg" && ext !== "png" && ext !== "webp") return file;
    var bmp = await createImageBitmap(file), sc = Math.min(1, 1600 / Math.max(bmp.width, bmp.height));
    var c = document.createElement("canvas"); c.width = Math.max(1, Math.round(bmp.width * sc)); c.height = Math.max(1, Math.round(bmp.height * sc));
    var x = c.getContext("2d"); x.fillStyle = "#fff"; x.fillRect(0, 0, c.width, c.height); x.drawImage(bmp, 0, 0, c.width, c.height);
    var b = await new Promise(function(r){ c.toBlob(r, "image/jpeg", 0.86); });
    return (b && b.size < file.size) ? {blob: b, ext: "jpg"} : file;
  }catch(e){ return file; }
}
var MAX_IMG = 10 * 1024 * 1024, MAX_VID = 25 * 1024 * 1024;
async function uploadFile(file, want){
  var head = new Uint8Array(await file.slice(0, 16).arrayBuffer()), t = sniff(head);
  if(!t[0] || t[1] !== want) throw fail("نوع الملف غير مدعوم.", 400);
  if(file.size > (want === "image" ? MAX_IMG : MAX_VID)) throw fail(want === "image" ? "الصورة كبيرة جداً (الحد 10 ميغابايت)." : "الفيديو كبير جداً (الحد 25 ميغابايت). قصّره أو اضغطه.", 413);
  var blob = file, ext = t[0];
  if(want === "image"){ var s = await shrink(file, ext); if(s && s.blob){ blob = s.blob; ext = s.ext; } }
  var name = rid(16) + "." + ext;
  await gh("PUT", name, {message: "رفع " + name, content: await fileB64(blob)});
  return name;
}
async function delFile(name){
  if(!FILE_RE.test(name || "")) return;
  try{ var j = await gh("GET", name); await gh("DELETE", name, {message: "حذف " + name, sha: j.sha}); }catch(e){}
}
function newsFields(fd){
  var title = String(fd.get("title") || "").trim().slice(0, 120), text = String(fd.get("text") || "").trim().slice(0, 1500);
  if(!title || !text) throw fail("العنوان والنص مطلوبان.", 400);
  return {tag: String(fd.get("tag") || "").trim().slice(0, 30) || "خبر", title: title, text: text};
}
async function api(method, url, body){
  var m = url.replace("/admin/api/", "").split("/"), res = m[0], id = m[1];
  if(res === "content") return (await readContent()).d;
  if(res === "gallery" && method === "POST"){
    var kind = body.get("kind") === "video" ? "video" : "image", f = body.get("file"); if(!f) throw fail("لا يوجد ملف.", 400);
    var name = await uploadFile(f, kind), item = {id: rid(8), kind: kind, asset: name, caption: String(body.get("caption") || "").trim().slice(0, 120), ts: Date.now()};
    await mutate(function(d){ d.gallery.push(item); }, "إضافة إلى المعرض"); return item;
  }
  if(res === "gallery" && method === "PATCH"){ var cap = String(body.caption || "").trim().slice(0, 120); await mutate(function(d){ d.gallery.forEach(function(g){ if(g.id === id) g.caption = cap; }); }, "تعديل تعليق"); return {}; }
  if(res === "gallery" && method === "DELETE"){ var gone = await mutate(function(d){ var g = d.gallery.filter(function(x){ return x.id === id; })[0]; d.gallery = d.gallery.filter(function(x){ return x.id !== id; }); return g; }, "حذف من المعرض"); if(gone) await delFile(gone.asset); return {}; }
  if(res === "news" && method === "POST" && !id){
    var fields = newsFields(body), asset = ""; var nf = body.get("file"); if(nf && nf.size) asset = await uploadFile(nf, "image");
    var ni = Object.assign({id: rid(8), asset: asset, ts: Date.now()}, fields);
    await mutate(function(d){ d.news.push(ni); }, "خبر جديد"); return ni;
  }
  if(res === "news" && method === "POST"){
    var fl = newsFields(body), up2 = body.get("file"), newAsset = null, rem = body.get("remove_image") === "1";
    if(up2 && up2.size) newAsset = await uploadFile(up2, "image");
    var old = await mutate(function(d){ var n = d.news.filter(function(x){ return x.id === id; })[0]; if(!n) return null; var o = n.asset; Object.assign(n, fl); if(newAsset !== null) n.asset = newAsset; else if(rem) n.asset = ""; return o; }, "تعديل خبر");
    if(old && (newAsset !== null || rem)) await delFile(old); return {};
  }
  if(res === "news" && method === "DELETE"){ var gn = await mutate(function(d){ var n = d.news.filter(function(x){ return x.id === id; })[0]; d.news = d.news.filter(function(x){ return x.id !== id; }); return n; }, "حذف خبر"); if(gn) await delFile(gn.asset); return {}; }
  if(res === "settings" && method === "PUT"){
    var j = body, s = {};
    ["announce","phone","hours","facebook","instagram","email"].forEach(function(k){ s[k] = String(j[k] || "").trim().slice(0, k === "announce" || k === "hours" ? 200 : 300); });
    var wa = String(j.whatsapp || "").replace(/\D/g, ""); if(wa && (wa.length < 8 || wa.length > 15)) throw fail("رقم الواتساب غير صالح.", 400); s.whatsapp = wa;
    ["facebook","instagram"].forEach(function(k){ if(s[k] && !/^https:\/\//i.test(s[k])) throw fail("الرابط يجب أن يبدأ بـ https://", 400); });
    s.hideDefaultNews = !!j.hideDefaultNews; s.hideDefaultGallery = !!j.hideDefaultGallery;
    await mutate(function(d){ d.settings = s; }, "تعديل الإعدادات"); return s;
  }
  throw fail("error", 400);
}
function errText(e){
  if(e.message && /[\u0600-\u06FF]/.test(e.message)) return e.message;
  if(e instanceof TypeError) return "تعذّر الاتصال بـ GitHub. تحقق من اتصال الإنترنت ثم حاول مرة أخرى.";
  return "تعذّر تنفيذ العملية. حاول مرة أخرى.";
}
function setMsg(el, text, kind){ el.textContent = text; el.className = "a-msg" + (kind ? " " + kind : ""); }
function twoStep(label, action){
  var b = h("button", {type:"button", class:"a-btn danger", text:label}), armed = false, t;
  b.addEventListener("click", function(){
    if(!armed){ armed = true; b.textContent = "اضغط مرة أخرى للتأكيد"; t = setTimeout(function(){ armed = false; b.textContent = label; }, 4000); return; }
    clearTimeout(t); b.disabled = true; action().then(null, function(){ b.disabled = false; armed = false; b.textContent = label; });
  });
  return b;
}
async function reload(){ DATA = await api("GET", "/admin/api/content"); if(fill) fill(); }
var fill = null;

function tabMedia(kind){
  var isVid = kind === "video", msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  var file = h("input", {type:"file", id:"a-file", accept: isVid ? "video/mp4,video/webm" : "image/jpeg,image/png,image/webp,image/gif"}); if(!isVid) file.multiple = true;
  var cap = h("input", {type:"text", id:"a-cap", maxlength:"120", placeholder:"مثال: يوم الرسم في الروضة"});
  var go = h("button", {type:"button", class:"a-btn sun", text: isVid ? "رفع الفيديو" : "رفع الصور"});
  go.addEventListener("click", async function(){
    var fs = Array.prototype.slice.call(file.files || []);
    if(!fs.length){ setMsg(msg, isVid ? "اختر ملف فيديو أولاً." : "اختر صورة واحدة أو أكثر أولاً.", "err"); return; }
    go.disabled = true; var done = 0;
    try{
      for(var i = 0; i < fs.length; i++){
        setMsg(msg, "جارٍ الرفع " + (i + 1) + " من " + fs.length + "…");
        var fd = new FormData(); fd.append("file", fs[i]); fd.append("kind", kind); fd.append("caption", cap.value);
        await api("POST", "/admin/api/gallery", fd); done++;
      }
      setMsg(msg, "تم رفع " + done + (isVid ? " فيديو" : " صورة") + " وظهر في الموقع.", "ok"); file.value = ""; cap.value = ""; await reload();
    }catch(e){ setMsg(msg, (done ? "تم رفع " + done + " فقط. " : "") + errText(e), "err"); }
    go.disabled = false;
  });
  var form = h("div", {class:"a-card"}, [
    h("h3", {text: isVid ? "رفع فيديو جديد" : "رفع صور جديدة"}),
    h("label", {for:"a-file", text: isVid ? "ملف الفيديو (MP4 أو WebM، حتى 100 ميغابايت)" : "الصور (يمكن اختيار عدة صور، تُصغَّر تلقائياً)"}), file,
    h("label", {for:"a-cap", text:"تعليق يظهر تحت العنصر (اختياري)"}), cap,
    isVid ? h("p", {class:"hint", text:"فيديوهات الهاتف بصيغة MOV لا تعمل. صدّرها بصيغة MP4."}) : null,
    h("div", {class:"a-row"}, [go]), msg]);
  var list = h("div", {class:"a-grid"});
  fill = function(){
    list.innerHTML = "";
    var items = DATA.gallery.filter(function(g){ return isVid ? g.kind === "video" : g.kind !== "video"; }).sort(byNew);
    if(!items.length){ list.appendChild(h("p", {class:"hint", text: isVid ? "لا توجد فيديوهات مرفوعة بعد." : "لا توجد صور مرفوعة بعد."})); return; }
    items.forEach(function(g){
      var m = isVid ? h("video", {src: up(g.asset), controls:"", preload:"metadata"}) : h("img", {src: up(g.asset), alt: sOf(g.caption, 120), loading:"lazy"});
      var ci = h("input", {type:"text", maxlength:"120", value: sOf(g.caption, 120), placeholder:"تعليق", "aria-label":"التعليق"});
      ci.addEventListener("change", function(){ api("PATCH", "/admin/api/gallery/" + g.id, {caption: ci.value}).catch(function(e){ alert(errText(e)); }); });
      list.appendChild(h("div", {class:"a-item"}, [m, h("div", {class:"b"}, [ci, twoStep("حذف", function(){ return api("DELETE", "/admin/api/gallery/" + g.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, h("h3", {text: isVid ? "الفيديوهات المنشورة" : "الصور المنشورة"}), list]);
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
      var img = up(n.asset) ? h("img", {src: up(n.asset), alt:""}) : null;
      var ed = h("button", {type:"button", class:"a-btn ghost", text:"تعديل"});
      ed.addEventListener("click", function(){
        editing = n; tag.value = sOf(n.tag, 30); title.value = sOf(n.title, 120); text.value = sOf(n.text, 1500); file.value = ""; rm.checked = false;
        rmRow.hidden = !n.asset; cancel.hidden = false; save.textContent = "حفظ التعديل"; head.textContent = "تعديل الخبر"; form.scrollIntoView({behavior:"smooth", block:"start"});
      });
      list.appendChild(h("div", {class:"a-news"}, [img, h("div", {class:"t"}, [h("b", {text: sOf(n.title, 120)}), h("span", {text: sOf(n.tag, 30)})]),
        h("div", {class:"a-row", style:"margin:0"}, [ed, twoStep("حذف", function(){ return api("DELETE", "/admin/api/news/" + n.id).then(reload); })])]));
    });
  };
  fill();
  return h("div", {}, [form, list]);
}

function tabSettings(){
  var s = DATA.settings, msg = h("div", {class:"a-msg", role:"status", "aria-live":"polite"});
  function fld(id, label, val, type, ph, hint){ return [h("label", {for:id, text:label}), h("input", {type:type || "text", id:id, value: sOf(val, 300), placeholder: ph || "", maxlength:"300"}), hint ? h("p", {class:"hint", text:hint}) : null]; }
  var F = {
    announce: fld("s-ann", "شريط إعلان أعلى الموقع", s.announce, "text", "مثال: التسجيل مفتوح للعام الدراسي الجديد", "اتركه فارغاً لإخفاء الشريط."),
    phone: fld("s-ph", "رقم الهاتف الظاهر", s.phone, "text", "0993 517 586"),
    whatsapp: fld("s-wa", "رقم الواتساب بالصيغة الدولية، أرقام فقط", s.whatsapp, "text", "963993517586", "مثال: 963993517586"),
    hours: fld("s-hr", "أوقات الدوام", s.hours, "text", "مثال: من الأحد إلى الخميس، 8:00 إلى 13:00"),
    facebook: fld("s-fb", "رابط صفحة فيسبوك", s.facebook, "url", "https://www.facebook.com/…"),
    instagram: fld("s-ig", "رابط صفحة إنستغرام", s.instagram, "url", "https://www.instagram.com/…"),
    email: fld("s-em", "البريد الإلكتروني", s.email, "email", "")
  };
  var hn = h("input", {type:"checkbox"}); hn.checked = !!s.hideDefaultNews;
  var hg = h("input", {type:"checkbox"}); hg.checked = !!s.hideDefaultGallery;
  var save = h("button", {type:"button", class:"a-btn sun", text:"حفظ الإعدادات"});
  save.addEventListener("click", async function(){
    var body = {hideDefaultNews: hn.checked, hideDefaultGallery: hg.checked};
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
  var out = h("button", {type:"button", class:"a-btn ghost", style:"color:#fff;border-color:#fff", text:"خروج", onclick:function(){ try{ localStorage.removeItem("zm-gh"); }catch(e){} GH.token = ""; start(); }});
  var view = h("a", {class:"a-btn sun", href:"./", target:"_blank", rel:"noopener", style:"text-decoration:none", text:"عرض الموقع"});
  var tabs = h("div", {class:"a-tabs", role:"tablist"});
  TABS.forEach(function(t){
    var b = h("button", {type:"button", role:"tab", "aria-selected": String(tab === t[0]), text:t[1]});
    b.addEventListener("click", function(){ tab = t[0]; draw(); }); tabs.appendChild(b);
  });
  var main = h("div", {class:"a-main"}); fill = null;
  main.appendChild(tab === "video" ? tabMedia("video") : tab === "news" ? tabNews() : tab === "settings" ? tabSettings() : tabMedia("image"));
  root.append(h("div", {class:"a-bar"}, [h("div", {class:"a-top"}, [h("h2", {text:"لوحة تحكم روضة زهرة المدائن"}), h("div", {class:"a-row", style:"margin:0"}, [view, out])]), tabs]), main);
}
function loginScreen(msg){
  var root = document.getElementById("app"); root.innerHTML = "";
  var g = guessRepo(), err = h("div", {class:"a-msg err", role:"alert", text: msg || ""});
  var own = h("input", {type:"text", id:"l-o", value: GH.owner || g.owner, autocomplete:"off"}), rp = h("input", {type:"text", id:"l-r", value: GH.repo || g.repo, autocomplete:"off"});
  var tk = h("input", {type:"password", id:"l-t", autocomplete:"off", placeholder:"github_pat_…"});
  rp.placeholder = "Zahra-Almadain أو رابط GitHub";
  var go = h("button", {type:"button", class:"a-btn sun", text:"دخول"});
  go.addEventListener("click", async function(){
    var n = {owner: own.value.trim(), repo:"", token: tk.value.trim()};
    if(!n.owner || !rp.value.trim() || !n.token){ setMsg(err, "املأ كل الحقول.", "err"); return; }
    try{ n.repo = normalizeRepo(rp.value, n.owner); }
    catch(e){ setMsg(err, errText(e), "err"); return; }
    go.disabled = true; var old = GH; GH = n;
    try{ var d = (await readContent()).d; try{ localStorage.setItem("zm-gh", JSON.stringify(GH)); }catch(e){} DATA = d; draw(); }
    catch(e){ GH = old; go.disabled = false; setMsg(err, errText(e), "err"); }
  });
  root.append(h("div", {class:"a-main", style:"max-width:420px"}, [h("div", {class:"a-card"}, [
    h("h3", {text:"دخول المسؤول"}), h("p", {class:"hint", text:"الدخول برمز GitHub الشخصي (Token) الذي يملكه المسؤول فقط."}),
    h("label", {for:"l-o", text:"حساب GitHub (Owner)"}), own, h("label", {for:"l-r", text:"اسم المستودع (Repository)"}), rp,
    h("label", {for:"l-t", text:"الرمز (Token)"}), tk, h("div", {class:"a-row"}, [go]), err])]));
}
function start(){
  if(!GH.token || !GH.owner || !GH.repo){ loginScreen(); return; }
  readContent().then(function(c){ DATA = c.d; draw(); }, function(e){ loginScreen(errText(e)); });
}
start();
