(function () {
  "use strict";
  // The download area of the home page. The data comes from app-version.json (next to the page);
  // a store button only appears when its https link is set, so nothing that does not exist is offered.
  function safeUrl(value) { return /^https:\/\//.test(value || "") ? value : ""; }
  function byId(id) { return document.getElementById(id); }
  fetch("app-version.json", {cache: "no-store"}).then(function (r) { return r.ok ? r.json() : null; }).then(function (info) {
    if (!info) return;
    var android = safeUrl(info.android_url);
    if (android) {
      var link = byId("androidLink");
      link.href = android;
      link.hidden = false;
      byId("androidSoon").hidden = true;
      byId("androidMeta").hidden = false;
      byId("appVersion").textContent = info.latest || "";
      byId("appDate").textContent = info.released || "";
      byId("appSize").textContent = info.android_size ? (Math.round(info.android_size / 1048576 * 10) / 10) + " MB" : "";
      byId("appSha").textContent = info.android_sha256 || "";
    }
    var ios = safeUrl(info.ios_url);
    if (ios) {
      var iosLink = byId("iosLink");
      iosLink.href = ios;
      iosLink.hidden = false;
    }
  }).catch(function () {});
})();
