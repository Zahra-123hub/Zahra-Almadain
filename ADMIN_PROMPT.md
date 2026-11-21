# PROMPT: Die Admin-Oberfläche von „Rawdat Zahrat Al-Madain" (روضة زهرة المدائن)

Dieser Text beschreibt die Admin-Oberfläche (`/admin/`) vollständig: wer sie benutzt, wie sie aufgebaut ist, welche Dateien, Funktionen und Endpunkte dazugehören und welche Regeln bei Änderungen gelten. Er ergänzt `PROJECT_PROMPT.md` (Gesamtprojekt) und `docs/accounting.md` (Buchhaltung im Detail). Lies beide, bevor du an der Admin-Oberfläche arbeitest.

---

## 1. Zweck

Die Admin-Oberfläche ist die Arbeitsfläche der Verwaltung im Browser (`https://zahratalmadain.com/admin/`). Sie hat **zwei Bereiche**, zwischen denen man in der Kopfzeile wechselt:

1. **لوحة التحكم (Dashboard)** – Webseiteninhalte, Konten, Kinder und Berichte, Kontrollzentrale, Besucher, Protokoll, Dateien, Sicherheit, Einstellungen.
2. **المحاسبة (Buchhaltung)** – genau drei Seiten: الإيرادات (Einnahmen), المصروفات (Ausgaben), الملخص الشهري (Monatsübersicht).

Sprache: Arabisch ist Standard (RTL), Englisch umschaltbar. Deutsch gibt es in der Admin-Oberfläche nicht.

---

## 2. Technik

- **Reines HTML/CSS/JavaScript**, kein Framework, kein Build-Schritt. Veröffentlicht über Cloudflare automatisch aus `main` (`Zahra-123hub/Zahra-Almadain`).
- **Backend:** FastAPI auf Render (`https://zahra-123hub-almadain-api.onrender.com`), lokal `http://127.0.0.1:8001`. Die Adresse wählt `API_BASE` in `admin.js` selbst (localhost → lokaler Server).
- **Content-Security-Policy** in `admin/index.html`: nur eigene Skripte, keine Inline-Skripte, `connect-src` nur zum API-Server und localhost. Keine externen Bibliotheken einbinden.
- **Cache:** Jede geänderte Datei bekommt in `admin/index.html` eine neue `?v=`-Nummer, sonst sehen Nutzer die alte Version.

### Dateien (`admin/`)

| Datei | Inhalt |
|---|---|
| `index.html` | Gerüst, CSP, lädt in dieser Reihenfolge: `admin.css`, `skin.css`, `ui.js`, `control.js`, `money.js`, `admin.js` (alle `defer`) |
| `admin.js` (~1.5k Zeilen) | Anmeldung und Modi, Kopfzeile, Menü, Sprache, Helfer (`h`, `request`, `api`, `setMsg`, `errText`, `downloadFile`, `money`, `labelCells`, `localToday`, `MONTHS_AR`, `EN_TEXT`) und alle Dashboard-Tabs |
| `ui.js` | Gemeinsame Bausteine: `uiT`, `uiField`, `uiSelect`, `uiTable`, `uiBadge`, `uiNum`, `uiToast`, `uiWhen`, `uiLogCard` (Protokoll), `uiMonthPicker` (arabische Monatsauswahl) |
| `control.js` | Tab „لوحة المتابعة" (Kontrollzentrale) |
| `money.js` | Bereich „المحاسبة" mit den drei Seiten |
| `admin.css` | Grundstil, Tabellen, Formulare, Karten, Handy-Regeln; am Ende der Block `mn-*` für die Buchhaltung |
| `skin.css` | Portal-Look (dunkelblaue Kopfzeile, Pillen-Menü), gilt mit `body.skin-portal` |

Ladereihenfolge beachten: `ui.js`, `control.js` und `money.js` nutzen Helfer aus `admin.js` erst beim Aufruf (nicht beim Laden). Neue gemeinsame Bausteine gehören nach `ui.js`.

---

## 3. Anmeldung, Sitzungen und Modi

Die Oberfläche liest beim Start Sitzungen aus `sessionStorage` (gesetzt von der Login-Seite `/login/`):

| Schlüssel | Wer |
|---|---|
| `zm-admin-session` | Server-Admin (Login `/api/auth/login`, Benutzer aus `ADMIN_USERNAME`) oder Plattform-Konto mit Rolle `admin` |
| `zm-accountant-session` | Buchhaltung |
| `zm-teacher-session` | Lehrkraft (darf Webseiteninhalte pflegen) |
| `zm-manager-session` | Leitung (nur Buchhaltung) |
| `zm-portals` | Liste der Portale des Kontos (`admin`, `accountant`, `manager`, `teacher`, `parent`) |

Daraus folgen die Modi in `admin.js`:

- **Admin** (keine besonderen Modi): sieht alle Dashboard-Tabs und die Buchhaltung.
- **`TEACHER_MODE`**: nur Bilder, Video, Nachrichten.
- **`ACCOUNTANT_MODE`** (ohne Lehrkraft): nur die Buchhaltung (`MONEY_ONLY`), Menüleiste ausgeblendet (`body.skin-solo`).
- **`BOOKS_MODE`**: Leitung kommt über `../admin/` mit ihrer Manager-Sitzung, sieht nur die Buchhaltung.

Wichtig: Der Browser entscheidet nie über Rechte. Jeder Aufruf wird im Backend erneut geprüft. Ausblenden in der Oberfläche ist nur Komfort.

`request(path, options)` schickt den Bearer-Token mit; bei 401 geht es zurück zum Login. `api(method, url, body)` ist der ältere Helfer für die Webseiteninhalte (`/admin/api/...`).

---

## 4. Kopfzeile (gleich in allen Bereichen und Portalen)

Reihenfolge von rechts nach links:

**Name · Sprache · لوحة التحكم · المحاسبة · بوابة الإدارة · بوابة المعلمات · بوابة أولياء الأمور · تغيير كلمة المرور · عرض الموقع · تسجيل الخروج**

- Der offene Bereich ist gelb (`p-button sun`, `aria-current="page"`), alle anderen umrandet (`outline`).
- „لوحة التحكم" und „المحاسبة" erscheinen nur, wenn das Konto beides darf (`MONEY_ALLOWED && !MONEY_ONLY`).
- Portal-Knöpfe nur für Portale aus `zm-portals`.
- In der Buchhaltung ist die Dashboard-Menüleiste ausgeblendet; die Buchhaltung hat ihre eigene Unterleiste.
- Dieselbe Reihenfolge baut `portal.js` (Funktion `header()`) für Leitungs-, Lehrkräfte- und Elternportal. Änderungen an der Kopfzeile immer an **beiden** Stellen machen.
- `#money` in der Adresse (`../admin/#money`) öffnet direkt die Buchhaltung.

---

## 5. Dashboard-Tabs (`ALL_TABS` in `admin.js`)

| Tab | Funktion | Inhalt | Endpunkte |
|---|---|---|---|
| الصور | `tabMedia("image")` | Bildergalerie der Webseite | `/admin/api/content`, `/admin/api/gallery` |
| الفيديو | `tabMedia("video")` | Videos der Webseite | dto. |
| الأخبار | `tabNews()` | Nachrichten anlegen, löschen | `/admin/api/news` |
| الأطفال والتقارير | `tabChildren()` | Berichte zur Prüfung, Kinder und Lehrkräfte | `/api/admin/platform/reports`, `/children` |
| لوحة المتابعة | `tabControl()` | Kontrollzentrale (Unter-Tabs: Übersicht, Lehrkräfte, Kinder, Aktivität, System, Rechte) | `/api/admin/control/*` |
| حسابات المنصة | `tabAccounts()` | Konten anlegen, Rollen, Freigabe, Passwort zurücksetzen, Registrierungsanträge | `/api/admin/platform/accounts`, `/teacher-accounts`, `/registration-requests` |
| الزوّار | `tabVisitors()` | Besucher der Webseite, Anmeldungen | `/api/admin/platform/visits` |
| سجل النظام | `tabLog()` → `uiLogCard` | Aktivitätsprotokoll aller Bereiche, Filter, Excel-Export | `/api/admin/activity`, `/activity/actors`, `/activity/export.xlsx` |
| الملفات | `tabFiles()` | Private Dateien der Lehrkräfte | `/api/admin/platform/files` |
| الأمان | `tabSecurity()` | Zahlen zu Konten und Anmeldungen (keine Namen, keine Passwörter) | `/api/admin/platform/security` |
| الإعدادات | `tabSettings()` | Einstellungen der Webseite | `/admin/api/settings` |

Webseiteninhalte (Bilder, Video, Nachrichten, Einstellungen) werden über die GitHub-API in `content.json` geschrieben; das Token liegt nur auf dem Server.

**Rechte in der Kontrollzentrale:** Der Admin vergibt Einzelrechte an Konten: `control.view` und `finance.view` (Kontrollzentrale für die Leitung), `books.correct` (Buchhaltung darf ändern und stornieren), `books.export` (Buchhaltung darf PDFs exportieren).

---

## 6. Buchhaltung (`money.js`, Backend `backend/app/money.py`, Präfix `/api/admin/money`)

Details stehen in `docs/accounting.md`. Für die Oberfläche wichtig:

### Aufbau jeder Seite
1. **Kurszeile** (`mnRateBar`): Kurs 1 USD = X SYP, Quelle (automatisch aus dem Netz einmal am Tag oder von der Leitung), Datum; die Leitung hat einen Knopf „تصحيح".
2. **Kennzahlen** (`mnTotals` / `mnTile`): Summe in USD, Summe in SYP (jeweils mit dem tatsächlich in dieser Währung bezahlten Anteil), Anzahl.
3. **Werkzeugleiste** (`mnToolbar`): Monat (`uiMonthPicker`), Kategorie, Suche, eingeklappt „فترة مخصّصة"; Knöpfe „+ neu" und „PDF".
4. **Formular** (`mnFormCard`): erscheint erst auf Knopfdruck, Raster `mn-grid`, Gegenwert in der anderen Währung live (≈).
5. **Tabelle** (`uiTable`): Datum | Beschreibung | Kategorie | USD | SYP | tatsächlich bezahlt (Betrag + „بسعر …") | Aktionen. Aktionen (`mnRowActions`): تعديل, إلغاء (im abgeschlossenen Monat „قيد عكسي"), السجل (Verlauf klappt unter der Zeile auf, `mnHistoryRow`).

### Die drei Seiten
- **الإيرادات:** Einnahmen; darunter „فواتير الأهالي" (Elternrechnungen: Forderung, Zahlung erfassen, signiertes PDF); eingeklappt „فئات الإيرادات" (nur Leitung).
- **المصروفات:** Ausgaben; darunter „رواتب …" (wer ausgezahlt ist, „صرف الراتب"; Gehälter werden am 1. des Folgemonats automatisch gebucht) und PDF der Mitarbeiterliste (nur Leitung).
- **الملخص الشهري:** Monatsleiste (◀ ▶ in Leserichtung, Status, Monat schließen/wieder öffnen, PDF-Bericht), Kennzahlen (Gewinn/Verlust je Währung, Gehälter, offene Rechnungen), Vergleich zum Vormonat, „رصيد الصندوق" (Bestand am Monatsanfang + Einnahmen − Ausgaben = Bestand am Monatsende; Eingabe des Anfangsbestands nur Leitung), Kategorien.

### Rechte (`meta.rights` aus `/api/admin/money/meta`)
| Recht | Leitung / Admin | Buchhaltung |
|---|---|---|
| `record` (erfassen, ansehen) | ja | ja |
| `correct` (Buchungen, Rechnungen, Zahlungen ändern und stornieren) | ja | ja |
| `export` (PDF) | ja | ja |
| `manage` (Kurs, eigener Kurs im Formular, Monatsabschluss, Kategorien, Anfangsbestand, Mitarbeiter-PDF) | ja | ja |

Seit 21.11.2026 (Entscheidung des Inhabers) darf die Rolle Buchhaltung in der Buchhaltung alles. Jede Änderung bleibt mit Name, Zeit und Grund im Verlauf; gelöscht wird nichts. Die Einzelrechte `books.correct` und `books.export` werden dafür nicht mehr gebraucht. Die Mitarbeiterliste selbst (anlegen, ändern) bleibt bei der Leitung.

Die Oberfläche blendet Knöpfe nach `meta.rights` aus; das Backend prüft trotzdem jede Aktion.

### Exporte
Nur **PDF** (signiert, mit Logo, Prüfcode): Einnahmen, Ausgaben, Monatsbericht, Rechnung, Mitarbeiterliste. CSV und XLSX gibt es in der Buchhaltung nicht mehr; nur das Systemprotokoll hat einen Excel-Export.

### Geldregeln, die die Oberfläche nie verletzen darf
- Beträge kommen als Dezimaltext vom Server; `uiNum` formatiert nur, rechnet nie mit Gleitkomma. Die ≈-Vorschau im Formular ist ausdrücklich nur ein Hinweis.
- USD und SYP werden nie zu einer Zahl addiert. Jede Summe steht je Währung; umgerechnete Werte sind als „للمقارنة فقط" gekennzeichnet.
- Nichts wird gelöscht. Es gibt nur „إلغاء" mit Grund (≥ 5 Zeichen) oder Gegenbuchung im abgeschlossenen Monat.

---

## 7. Gestaltung

- **Look:** wie die Portale (`body.skin-portal`): dunkelblaue Kopfzeile mit rundem Logo, Pillen-Menü, Karten mit 18 px Rundung, Gelb (`--sun`) für Hauptaktionen und den aktiven Bereich.
- **Klassen:** `a-card`, `a-row`, `a-field`, `a-btn` (`sun`, `ghost`, `mn-mini`), `a-badge` (`paid`, `due`, `review`, `neutral`), `a-table compact`, `a-kpis`/`mn-tiles`, `a-tabs`/`a-subtabs`, `a-msg` (`err`/`ok`).
- **Knöpfe neben Feldern** stehen auf Höhe der Felder (`.a-row:has(> .a-field){align-items:flex-end}`).
- **RTL:** Zahlen, Daten und Beträge mit `dir:"ltr"`; gemischte Texte mit `dir:"auto"`. Pfeile in Leserichtung (▶ = zurück, ◀ = weiter). Monate immer mit arabischen Namen (`uiMonthPicker`, `MONTHS_AR`), nie das Browser-Feld `type=month`.
- **Handy:** Die Seite darf nie breiter als der Bildschirm werden. Tabellen ohne feste Mindestbreite; unter 900 px werden sie per `labelCells` zu Karten (jede Zelle mit `data-label`). Unter 700 px stapeln sich Filter und Formulare einspaltig.
- **Statusfarben:** Rot nur für echte Probleme (fällig, Verlust), Grün für erledigt, Grau (`neutral`) für normale Zustände wie „مفتوح".

---

## 8. Texte und Sprache

- Texte stehen direkt im Code. In `admin.js` laufen Texte von `h(... {text: ...})` durch `uiText()`; die englische Fassung steht in `EN_TEXT` (Schlüssel = arabischer Satz).
- In `ui.js`, `control.js`, `money.js` immer `uiT(["عربي", "English"])` verwenden.
- Portal-Texte (Kopfzeile der Portale) stehen in `portal-text.js` (Arabisch und Englisch).

---

## 9. So prüfst du eine Änderung

1. `node --check admin/<datei>.js` für jede geänderte Datei.
2. Backend-Tests: `cd backend && python -m unittest discover -s tests` (zuletzt 174 grün).
3. Ansicht im Browser mit Testdaten, ohne echte Datenbank: eigener lokaler Server mit SQLite (wie `backend/dev_server.py`) auf Port 8001, die Seite über `python -m http.server 8000` (Port 8000 ist in `ALLOWED_ORIGINS` erlaubt). Screenshots mit Edge headless (`--headless=new --screenshot`), Desktop (1280 px) und Handy (500 px); prüfen, dass `scrollWidth == clientWidth`.
4. Bei SQLite-Testservern keinen `StaticPool` verwenden, sonst brechen parallele Browser-Anfragen ab.
5. `?v=` in `admin/index.html` (und bei Portaländerungen in `login/`, `teachers/`, `parents/`, `management/`) erhöhen.

Nichts als „getestet" bezeichnen, was nicht wirklich ausgeführt oder angesehen wurde.

---

## 10. Verbindliche Regeln beim Arbeiten

- Erst umsetzen und prüfen, dann lokal committen, dann fragen: „Soll ich pushen?". Pushen nur nach ausdrücklichem „push es".
- Reine Oberflächenänderungen brauchen keinen Render-Deploy. Backend-Änderungen schon; der Besitzer löst „Deploy latest commit" selbst aus.
- Keine Änderung an der echten Neon-Datenbank ohne ausdrückliche Zustimmung und vorherige Sicherung.
- Keine Finanzdaten löschen, keine Rechte nur in der Oberfläche prüfen, keine Zugangsdaten in Code oder Git.
- Kopfzeile, Rechte und Texte immer in Admin-Oberfläche **und** Portalen gleich halten.
- Keine neuen externen Bibliotheken oder CDNs (CSP).
