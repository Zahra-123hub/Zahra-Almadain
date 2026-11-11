(function () {
  "use strict";
  var API = (/^(localhost|127\.0\.0\.1)$/.test(location.hostname) ? "http://127.0.0.1:8001" : "https://zahra-123hub-almadain-api.onrender.com");

  var T = {
    ar: {},
    de: {
      title: "App des Kindergartens Zahrat Al-Madain",
      lead: "Alles zu Ihrem Kind in der Hosentasche: Tagesberichte, Beiträge, Mitteilungen und Benachrichtigungen.",
      androidNote: "Erfordert Android 7.0 oder neuer.", androidButton: "Für Android herunterladen",
      iosNote: "Erfordert iOS 13 oder neuer. Installation nur über App Store oder TestFlight.", iosButton: "Im Apple Store öffnen",
      soon: "Die App ist bald verfügbar. Wir geben es hier bekannt.",
      version: "Version", released: "Veröffentlicht am", qr: "Code mit dem Handy scannen, um diese Seite zu öffnen.",
      howTitle: "So starten Sie",
      how1: "Installieren Sie die App über den passenden Button für Ihr Telefon.",
      how2: "Melden Sie sich mit den Zugangsdaten der Einrichtung an (dieselben wie auf der Webseite).",
      how3: "Updates kommen über den Store. Ist Ihre Version zu alt, verlangt die App das Update.",
      parents: "Eltern: Nach dem Start der App ersetzt diese Seite den Eltern-Login auf der Webseite. Konten und Kinderdaten bleiben unverändert.",
      teachers: "Lehrkräfte: Sie können weiter die Webseite oder die App nutzen; die Daten sind in beiden dieselben.",
      helpTitle: "Probleme bei der Installation?", help: "Wenden Sie sich an die Leitung der Einrichtung, wir helfen Ihnen.",
      size: "Größe", sha: "Prüfsumme der Datei (SHA-256)",
      unknown: "Bei der Installation fragt das Handy evtl. nach der Erlaubnis für diesen Browser. Das ist normal, da die App nicht aus dem Google Play Store kommt.",
      back: "Zurück zur Webseite des Kindergartens"
    },
    en: {
      title: "Zahrat Al-Madain Kindergarten app",
      lead: "Everything about your child in your pocket: daily reports, posts, notices and notifications.",
      androidNote: "Requires Android 7.0 or newer.", androidButton: "Download for Android",
      iosNote: "Requires iOS 13 or newer. Installation only through the App Store or TestFlight.", iosButton: "Open in the Apple store",
      soon: "The app will be available soon. We will announce it here.",
      version: "Version", released: "Released", qr: "Scan the code with your phone to open this page.",
      howTitle: "How to start",
      how1: "Install the app with the button for your phone.",
      how2: "Sign in with the account details the kindergarten gave you (the same as on the website).",
      how3: "Updates come from the store. If your version is too old, the app asks for the update.",
      parents: "Parents: once the app is launched, this page replaces the parents' sign-in on the website. Accounts and children's data stay as they are.",
      teachers: "Teachers: you can keep using the website or the app; the data is the same in both.",
      helpTitle: "Trouble installing?", help: "Contact the kindergarten office and we will help.",
      size: "Size", sha: "File checksum (SHA-256)",
      unknown: "While installing, your phone may ask to allow this browser to install apps. That is normal because the app does not come from Google Play.",
      back: "Back to the kindergarten website"
    }
  };

  var nodes = Array.prototype.slice.call(document.querySelectorAll("[data-t]"));
  var arabic = {};
  nodes.forEach(function (n) { arabic[n.getAttribute("data-t")] = n.textContent; });
  T.ar = arabic;

  function setLang(code) {
    document.documentElement.lang = code;
    document.documentElement.dir = code === "ar" ? "rtl" : "ltr";
    nodes.forEach(function (n) { n.textContent = T[code][n.getAttribute("data-t")] || arabic[n.getAttribute("data-t")]; });
    Array.prototype.forEach.call(document.querySelectorAll(".lang button"), function (b) {
      b.className = b.getAttribute("data-lang") === code ? "on" : "";
    });
    try { localStorage.setItem("appPageLang", code); } catch (e) {}
  }
  Array.prototype.forEach.call(document.querySelectorAll(".lang button"), function (b) {
    b.addEventListener("click", function () { setLang(b.getAttribute("data-lang")); });
  });
  var saved = "ar";
  try { saved = localStorage.getItem("appPageLang") || ((navigator.language || "").slice(0, 2) === "de" ? "de" : "ar"); } catch (e) {}
  setLang(T[saved] ? saved : "ar");

  // Only what the server really offers is shown: no store link set => "soon", never a made-up download.
  function safeUrl(value) {
    return /^https:\/\//.test(value || "") ? value : "";
  }
  function show(info) {
    if (!info) return;
    if (info.latest) document.getElementById("version").textContent = info.latest;
    if (info.released) document.getElementById("released").textContent = info.released;
    [["android", info.android_url], ["ios", info.ios_url]].forEach(function (pair) {
      var url = safeUrl(pair[1]);
      if (!url) return;
      var link = document.getElementById(pair[0] + "Link");
      link.href = url;
      link.hidden = false;
      document.getElementById(pair[0] + "Soon").hidden = true;
    });
    if (info.android_sha256 && safeUrl(info.android_url)) {
      var box = document.getElementById("androidCheck");
      document.getElementById("androidSha").textContent = info.android_sha256;
      document.getElementById("androidSize").textContent = info.android_size ? (Math.round(info.android_size / 1048576 * 10) / 10) + " MB" : "";
      box.hidden = false;
    }
  }
  // The file next to this page is the main source (it works without the server); the server answer fills what is missing.
  fetch("version.json", {cache: "no-store"}).then(function (r) { return r.ok ? r.json() : null; }).catch(function () { return null; }).then(function (local) {
    show(local);
    return fetch(API + "/api/app/version", {headers: {Accept: "application/json"}}).then(function (r) { return r.ok ? r.json() : null; }).then(function (remote) {
      if (remote && (remote.android_url || remote.ios_url) && !(local && local.android_url)) show(remote);
      else if (remote && remote.ios_url) show({ios_url: remote.ios_url});
    });
  }).catch(function () {});
})();
