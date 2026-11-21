# PROJEKT-PROMPT: Plattform „Rawdat Zahrat Al-Madain" (روضة زهرة المدائن)

> Stand: 14.11.2026, lokaler Git-Stand `4bc621f` (auf `origin/main` gepusht). Dieses Dokument beschreibt das gesamte Projekt so genau, dass eine KI oder ein neuer Entwickler ohne Vorwissen sicher daran weiterarbeiten kann. Alles hier stammt aus dem tatsächlichen Code und den Tests. Wo etwas nicht verifiziert ist, steht es ausdrücklich dabei.

---

## 0. Deine Rolle und Arbeitsweise

Du bist Senior-Entwickler (Python/FastAPI, Flutter/Dart, Webfrontend ohne Framework) und Buchhaltungs-versiert. Du arbeitest an einem **bestehenden Produktivprojekt** mit echten Familien- und Finanzdaten. Der Besitzer (Ahmad) spricht Deutsch.

1. **Zuerst lesen, dann ändern.** Untersuche Code und Tests, bevor du etwas anfasst. Ersetze funktionierende, getestete Teile nicht ohne nachvollziehbaren Grund.
2. **Bei größeren Vorhaben:** Analyse → kurzes Konzept → Freigabe abwarten → blockweise umsetzen → nach jedem Block Analyse und Tests → ehrlicher Bericht.
3. **Berichte ehrlich:** Was fertig ist, was nicht getestet wurde, was fehlt. Nie behaupten, etwas sei geprüft, wenn es nur kompiliert oder getestet wurde.
4. **Qualität vor Geschwindigkeit.** Bei Geld: nichts raten, alles testen, alles protokollieren.
5. **Nie ungefragt veröffentlichen** (siehe Abschnitt 14). Das ist die wichtigste Regel.

---

## 1. Zweck und Zielgruppen

Digitale Plattform für einen Kindergarten in Syrien. Drei Nutzergruppen sind in der **App** vertreten:
- **Eltern**: sehen veröffentlichte Berichte ihrer Kinder, Beiträge, Mitteilungen, Lernmaterial.
- **Lehrkräfte**: schreiben Berichte, veröffentlichen Beiträge, verwalten Dateien und geben Material für Eltern frei.
- **Leitung**: prüft Berichte, verwaltet das Lernmaterial wie einen Moodle-Kurs.

**Nur auf der Webseite** (nicht in der App nachbauen): **Verwaltung/Admin, Buchhaltung**, Kinder- und Mitarbeiterverwaltung, Konten, Webseiteninhalte, Besucherstatistik.

**Sprachen:** Arabisch (Standard, RTL), Deutsch, Englisch. Die öffentliche Webseite kann Arabisch/Englisch/Deutsch. **Die Admin-Oberfläche kennt nur Arabisch und Englisch** (kein Deutsch). Die App kennt alle drei.

---

## 2. Gesamtarchitektur und Betrieb

| Teil | Technik | Hosting | Veröffentlichung |
|---|---|---|---|
| Webseite (statisch) | HTML/CSS/JS ohne Framework | Cloudflare, Domain `zahratalmadain.com` (`CNAME`) | Push auf `main` des Repos `Zahra-123hub/Zahra-Almadain` → Auto-Deploy (1–2 Minuten, danach Strg+F5) |
| Backend | FastAPI, SQLAlchemy 2, Alembic, Pydantic, httpx, openpyxl, pwdlib[argon2], psycopg3, tzdata | Render (Dienst `zahra-123hub-almadain-api`, Free-Plan, Region Frankfurt) | **Manueller Deploy** bei Render: „Manual Deploy → Deploy latest commit". Start: `alembic upgrade head && uvicorn app.main:app` (Migrationen laufen bei jedem Start) |
| Datenbank | PostgreSQL | Neon (Free) | Verbindung über `DATABASE_URL` (Render-Variable) |
| App „Zahra+" | Flutter/Dart | – | APK über GitHub-Releases (`app-v1.0.x`), Download-Bereich auf der Startseite (`appdl.js`, `app-version.json`) |

Gesundheitscheck: `GET /healthz`. Der Free-Server schläft ein, der erste Aufruf kann bis zu einer Minute dauern (App-Timeout 60 s).

### Server-Umgebungsvariablen (alle aus dem Code)
`DATABASE_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `SESSION_SECRET`, `GITHUB_TOKEN`, `GITHUB_OWNER`, `GITHUB_REPO` (Webseiteninhalte über die GitHub-API), `ALLOWED_ORIGINS`, `SITE_HOSTS`, `RENDER`, `APP_LATEST_VERSION`, `APP_MIN_VERSION`, `APP_ANDROID_URL`, `APP_IOS_URL`, `APP_RELEASED`, `SMTP_HOST/PORT/USER/PASSWORD/FROM`, `ACCOUNTING_WEEK_START` (0 = Montag, Standard), `SYP_RATE_SCALE` (Standard 100), `APP_TIMEZONE` (Standard `Asia/Damascus`, `LOCAL` nur in Tests), `ALLOW_FINANCE_RESET` (nur Testumgebung).

---

## 3. Repository-Karte

```
/                        öffentliche Webseite: index.html, style.css, script.js, content.json, appdl.js, app-version.json,
                         management.js, portal.js, portal-text.js, portal.css, render.yaml, CNAME, README.txt/.md
admin/                   Admin- und Buchhaltungsoberfläche: index.html, admin.js (1.5k Zeilen), money.js (Buchhaltung), ui.js, control.js,
                         admin.css, skin.css
login/ parents/ teachers/ management/   Portale (index.html je Portal; die Logik steckt in portal.js / management.js)
images/                  Logo, Plakat, Icons, app-qr.svg
docs/                    accounting.md, mobile-app.md, portals.md, visitors.md, hosting.txt
backend/
  app/ main.py (3,4k Zeilen), models.py, database.py, security.py, community.py, mobile.py, visits.py,
       money.py (Buchhaltung), people.py (Kinder und Personal), activity.py (Protokoll), actors.py, tables.py (XLSX/CSV),
       staff_export.py, control.py, finance_backup.py (Sicherung der alten Finanztabellen), timeutil.py, manage.py (CLI)
  migrations/versions/ 0001 … 0039   (neueste: 0039_drop_old_finance; 0038_money = neue Buchhaltung; 0030–0035 Sitzungen, Protokoll, Rechte, Personal)
  tests/ base.py (Testbasis ControlsBase), test_money, test_people, test_api, test_community, test_children_admin, test_control,
         test_roles, test_security, test_visits, test_mobile, test_database (+ __init__.py setzt APP_TIMEZONE=LOCAL)
  dev_server.py        lokaler Testserver mit SQLite (Port 8765, dev.db)
  FINANCE_SWITCH.md    Runbook: Sicherung und Entfernen der alten Finanztabellen auf der echten Datenbank
mobile_app/            Flutter-App (siehe Abschnitt 9)
PROJECT_PROMPT.md      dieses Dokument
```

---

## 4. Datenmodell (30 Tabellen, `backend/app/models.py`)

**Konten und Rechte:** `accounts`, `roles`, `permissions`, `portal_sessions` (Bearer-Sitzungen), `login_attempts` (Drosselung), `registration_requests`, `guardian_invitations`.
**Kinder:** `children` (u. a. `display_name`, `class_name`, `is_active`), `child_guardians` (Vater/Mutter, Telefon, E-Mail, verknüpftes Konto), Verknüpfungstabellen Eltern↔Kind (`parent_child_links`, mit `confirmed_at`) und Lehrkraft↔Kind (`teacher_child_links`).
**Inhalte:** `daily_reports` (Titel, Text, `activities`, `meals`, `status` ∈ draft/submitted/published/rejected/archived, `review_note`, `language`, `published_at`), `teacher_posts` (`scope` general|child, `kind` post|material, `child_id`, `hidden`, `position`), `teacher_content` (Dateien, Binärdaten in der DB; `owner_id`, `report_id`, `post_id`, `category`, `media_type`, `byte_size`), `notifications`, `announcements`, `site_visits`, `device_tokens` (Push-Token, noch ungenutzt).
**Buchhaltung (Migration 0038, `money.py`):** `currency_rates` (1 USD = X SYP ab `valid_from`, nur hinzufügen), `income_categories` (vier eingebaute mit `key`: tuition, registration, extra_fees, other_income; weitere durch die Leitung), `invoices` + `invoice_items` (Forderung mit eingefrorenem Kurs, Positionen mit Betrag und Gegenwert), `income_entries` (Einnahme: Betrag, tatsächliche Währung, Kurs, Gegenwert, optional Kind/Zahler/Rechnung, Storno-Spalten, `reverses_id` für Gegenbuchungen), `expense_entries` (Ausgabe mit Kategorie, Empfänger, optional Mitarbeiter + `salary_month`), `month_closings` (abgeschlossen/wiedereröffnet mit Benutzer, Zeit, Grund).
**Personal:** `employees` (Leitung): `employee_no`, Name, Position, Telefon, Eintritt, Austritt, Gehalt + Währung, Notizen, `is_active`.
**Sonstiges:** `account_grants` (Einzelrechte `control.view`, `finance.view`, `books.correct`, `books.export`), `system_checks`, `portal_sessions.active_role` (+ Meta), `fee_audit_log` = Aktivitätsprotokoll aller Bereiche (`domain`, `entity_type`, `before_json`, `after_json`, `reason`), `children.left_on`.
**Alte Finanztabellen** (`fee_charges`, `fee_payments`, `salary_lines`, `accounting_entries`, `entry_receipts`, `exchange_rates`, `cash_openings`, `period_locks`, `cash_counts`, `cash_transactions`, `ledger_cutover`, `step_confirmations`, `fee_charge_lines`): kein Code mehr; Migration 0039 entfernt sie nur, wenn sie leer sind oder eine geprüfte Sicherung vorliegt (siehe `backend/FINANCE_SWITCH.md`).

Geldspalten sind `Numeric(14,2)`, Kurse `Numeric(18,6)`. Geld wird in Python **immer als `Decimal`** gerechnet, Rundung „half up".

---

## 5. Authentifizierung und Sicherheit

- Anmeldung `POST /api/platform/auth/login` (App, Portale) und `POST /api/auth/login` / `/api/auth/entry` (Webseite; liefert `portals`). Antwort enthält `access_token` (Bearer). Abmeldung `POST /auth/logout`, Profil `GET /auth/me` (liefert `id`, `username`, `roles`, `preferred_language`), `PATCH /auth/language`, `POST /auth/change-password`.
- Passwörter: argon2 (`pwdlib`). Mindestlänge 12, keine häufigen Passwörter, nicht den Benutzernamen enthalten.
- **Drosselung** der Anmeldung in der Datenbank (`login_attempts`): nach wiederholten Fehlversuchen HTTP 429 (15-Minuten-Fenster), getrennt nach Adresse und Benutzername. Beim lokalen Testserver wird sie beim Start geleert.
- **Rechte entscheidet ausschließlich der Server.** Prüfungen: `require_platform_role(...)`, `require_any_platform_role(...)`, `require_admin`, `fees_actor/require_fees_user` (accountant oder admin), `require_people_manager` (manager, admin), `require_staff_reader`. Frontends blenden nur aus.
- Zusätzlich gibt es einen „Legacy-Admin" (Anmeldung mit `ADMIN_USERNAME/ADMIN_PASSWORD`), der als Rolle `admin` ohne Konto-ID auftritt.
- Dateien privater Inhalte werden nur mit Token ausgeliefert (kein öffentlicher Link), `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
- Fehlermeldungen und Logs dürfen **keine Tokens oder Passwörter** enthalten.

---

## 6. Rollen

`parent`, `teacher`, `manager` (Leitung), `accountant`, `admin`. Ein Konto kann mehrere Rollen haben, **arbeitet aber pro Sitzung in genau einer aktiven Rolle**: `POST /api/platform/auth/switch-role {role, keep_previous}` gibt eine NEUE Sitzung zurück (die alte endet, außer `keep_previous` – so halten Web-Tabs je Portal ihre eigene Sitzung). Mit `ENFORCE_ACTIVE_ROLE=1` wählen Mehrrollen-Sitzungen zuerst; Standard aus (alte Clients). App: `RoleChooserPage`. Leitungs-Einzelrecht für die Kontrollzentrale vergibt der Admin (`/api/admin/control/grants`).

| Rolle | App | Web |
|---|---|---|
| parent | Eltern-Bereich | Elternportal (läuft weiter, bis die App verifiziert ist) |
| teacher | Lehrkraft-Bereich | Lehrkräfteportal, Webseiteninhalte (Bilder, Video, Nachrichten) |
| manager | Leitungsbereich (Berichtsprüfung, Kurs-Editor) | Verwaltungsportal; Buchhaltung über `../admin/` (Link auf der Startseite) |
| accountant | – (Hinweis „nur Webseite") | Buchhaltung (drei Seiten) |
| admin | – | alles, Konten, Einstellungen, Systemprotokoll |

`GET /api/platform/auth/me` liefert die Rollen; die App leitet daraus `Session.areas` ab (Reihenfolge Leitung, Lehrkraft, Eltern). Mit mehreren Rollen wechselt man im Profil, unter „Mehr" und in der Seitenleiste den Bereich (zuletzt benutzter Bereich in `shared_preferences`, Schlüssel `area`).

---

## 7. Backend: Module und Endpunkte

### 7.1 Plattform (Eltern, Lehrkräfte, Leitung) in `main.py` und Co.
- **Berichte:** Lehrkraft `GET/POST /api/platform/teacher/reports`, `PATCH …/{id}` (Felder `title`, `body`, `activities`, `meals`, `submit_for_review`, `publish_to_parents`), Anhänge `GET …/{id}/attachments`; Hochladen über `POST /api/platform/teacher/content` mit `category=report_attachment` und `report_id` (**höchstens 5 Anhänge**, nur bei Entwurf oder zurückgegeben). Eltern `GET /api/platform/children/{id}/reports` (nur `published`), Anhänge `…/reports/{rid}/attachments` und `…/files/{cid}` (nur eigene Kinder). Leitung `GET /api/platform/review/reports` (liefert zusätzlich `child_name`), `PATCH …/{id}` mit `{"status": "published"|"rejected", "note": "…"}` (Grund max. 500 Zeichen, nur bei Rückgabe gespeichert, bei Veröffentlichung gelöscht), Anhänge `…/attachments`, `…/files/{cid}`.
- **Beiträge:** `POST /api/platform/teacher/posts` (multipart: `scope`, `title`, `body`, `child_id`, `kind`, `files`; **Dateianzahl unbegrenzt**), `GET /teacher/posts`, `DELETE`. Eltern `GET /api/platform/parent/posts` (nur sichtbare: nicht `hidden`; sortiert nach `position`, dann neueste zuerst), Dateien `…/{id}/files/{cid}`.
- **Lehrkraft-Dateien:** `GET/POST /teacher/content`, `DELETE`, Download, `GET /teacher/storage` (250 MB Limit je Lehrkraft). **Freigabe:** `POST /teacher/content/share` verschiebt private Dateien in einen neuen Beitrag `kind=material`.
- **Lernmaterial-Verwaltung (Leitung, `manager` und `admin`):** `GET/POST /api/platform/manager/materials`, `PATCH/DELETE …/{id}` (Titel, Beschreibung, `hidden`), `POST …/{id}/move` (`up`/`down`, nummeriert neu), `POST …/{id}/files`, `PATCH …/files/{fid}` (Umbenennen), `DELETE …/files/{fid}`, `GET …/files/{fid}`.
- **Mitteilungen/Benachrichtigungen:** `GET /notifications` (mit `unread`), `POST /notifications/read-all`, `POST /notifications/{id}/read`, `GET /announcements`. Benachrichtigungsarten u. a. `report_submitted`, `report_published`, `report_returned`, `report_direct`, `post_new`. Der Text wird in der App übersetzt (`n_<kind>`), gespeichert wird nur `kind`, `subject`, `view`.
- **Kinder, Registrierung:** `GET /api/platform/children`, `GET /teacher/children`, Einladungen, Registrierungsanträge mit Einmalcode, Verknüpfungen.
- **App-Hilfen** (`mobile.py`): `GET /api/app/version?version=x` (öffentlich; `update_required`, `update_available`, `latest`, `android_url`, `ios_url`), `POST /api/platform/devices`, `POST …/devices/remove`.
- **Verwaltung/Admin** (`/api/admin/platform/...`, `community.py`): Konten, Status, Passwort zurücksetzen, Kinder, Gruppen, Personen, Statistiken, Dateien aller Lehrkräfte, Sicherheitsübersicht, Mitteilungen, Besucher (`visits.py`).
- **Webseiteninhalte** (`/api/admin/gallery|news|settings|content`): lesen/schreiben `content.json` und Mediendateien über die GitHub-API (Token nur auf dem Server).

### 7.2 Buchhaltung und Personal (nur Web)
- **Buchhaltung** (`money.py`, Präfix `/api/admin/money`, Oberfläche `admin/money.js`): genau drei Seiten – Einnahmen (mit Rechnungen und deren Zahlungen), Ausgaben (mit Gehältern), Monatsübersicht (mit Abschluss). Endpunkte: `/meta`, `/rates` (GET, POST nur Leitung), `/categories`, `/income` (+ `PATCH`, `/void`), `/invoices` (+ `/payments`, `/void`), `/expenses` (+ `PATCH`, `/void`), `/salaries`, `/history/{id}`, `/summary`, `/closings` (+ `/reopen`), `/export/income|expenses|summary.xlsx|csv`. Details: `docs/accounting.md`.
- **Personal und Kinder** (`people.py`, Präfix `/api/admin/people`): `/employees` (lesen: Leitung, Admin, Buchhaltung; ändern: Leitung, Admin), `/employees/export.xlsx|csv?scope=all|active` (nur Leitung/Admin, Telefon/Nr. bleiben Text), `/staff-accounts`, `/children`, `/parent-accounts`. Deaktivieren statt Löschen.
- **Protokoll** (`activity.py`, Präfix `/api/admin/activity`): lesen, Personen, Excel-Export. Admin: alle Bereiche; Leitung: Geldbereich; Buchhaltung: nur eigene Zeilen.
- **Rechte (`money.rights`):** Leitung, Admin und Buchhaltung dürfen in der Buchhaltung alles (seit 21.11.2026): erfassen, ändern, stornieren, Rechnungen bearbeiten, Export, Kurs, Monatsabschluss, Kategorien, Anfangsbestand, Mitarbeiter-PDF. Jede Änderung steht im Verlauf. Die Mitarbeiterliste selbst verwaltet nur die Leitung.

---

## 8. Geschäftsregeln der Inhalte

- **Berichtsablauf:** Entwurf → (Lehrkraft) „zur Prüfung" oder „direkt an Eltern" → Leitung veröffentlicht oder gibt mit Grund zurück → bei Rückgabe wieder bearbeitbar. Eltern sehen nur `published`. Benachrichtigungen an die jeweiligen Gegenparteien.
- **Beitrag:** `scope=general` (alle Eltern) oder `child` (nur Eltern dieses Kindes). `kind=post` erscheint im Tab „Beiträge", `kind=material` im Tab „Lernmaterial".
- **Lernmaterial:** Abschnitt = `TeacherPost` mit `kind=material`. Versteckte (`hidden`) sind für Eltern unsichtbar, auch ihre Dateien (HTTP 404). Reihenfolge über `position`.
- **Dateien:** Typ- und Größenprüfung auf dem Server (Signaturen, Sperrliste ausführbarer Dateien). Berichtsanhänge höchstens 5, Beiträge/Material unbegrenzt.
- **Offline-Verhalten der App:** zuletzt geladene Listen werden pro Konto zwischengespeichert und beim Abmelden gelöscht.

---

## 9. Die App „Zahra+" (Flutter, `mobile_app/`)

**Stand:** Version `1.0.2+3`, Paket `com.zahratalmadain.zahra_app` (Android), `com.zahratalmadain.zahraApp` (iOS), iOS-Ziel 13.0, Android-minSdk effektiv 24 (Android 7.0). Der letzte veröffentlichte APK ist 1.0.2. Ein APK mit dem neuen Design gibt es noch **nicht** (erst nach „final").

### 9.1 Pakete
`http`, `flutter_secure_storage`, `shared_preferences`, `image_picker`, `file_picker`, `path_provider`, `open_filex`, `intl`, `flutter_localizations`, `cupertino_icons`; dev: `flutter_test`, `flutter_lints`, `flutter_launcher_icons`. Schriften lokal: Tajawal (Regular/Medium/Bold) und Inter (Regular/Medium/SemiBold/Bold, Lizenz SIL OFL, `assets/fonts/Inter-LICENSE.txt`). Für iOS `dependency_overrides: image_picker_ios: 0.8.12+2`.

### 9.2 Dateien (`lib/`)
| Datei | Inhalt |
|---|---|
| `main.dart` | `ZahraApp` (MaterialApp, Theme je Sprache, `SessionScope` **oberhalb** des Navigators über `builder`), `_Root` (Ladeschirm / Update-Pflicht / Login / Bereich), `ParentShell`, `TeacherShell`, `ManagementShell` |
| `design/tokens.dart` | `Gap` (4/8/12/16/24/32), `Rad` (10/16/24), `Dur`, `Breakpoints` (wide 840, content 980) |
| `design/shell.dart` | `AdaptiveShell` (Handy: untere Leiste mit höchstens 5 Zielen + „Mehr"; ab 840 px Seitenleiste), `AppHeader` (blauer Kopf mit unten gerundeter Kante; im breiten Fenster an der Seitenleiste eckig), `NotificationBell`, `SubPage`, `AreaSwitcher`, `UpdateHint` |
| `shared/ui.dart` | Theme (`buildTheme(lang)`), `SessionScope`, `Loader` (Skeleton beim Laden, `StateView` bei Fehlern), `StateView`/`EmptyNote`, `Skeleton(List)`, `Pill`, `StatusPill`, `AvatarInitials`, `HeroCard`, `StatTile`, `QuickAction`, `FormSection`, `BottomActionBar`, `FileTile`/`FileTypePlate` (Farbplättchen: PDF rot, Video blau, ZIP gold, Bild grün), `confirmDelete`, `askText`, `confirmLeave`, `ReportFiles`, `openPrivateFile`, `longDate`, `formatDate`, `formatSize` |
| `services/api.dart` | `ApiClient` (Bearer, Timeout 60 s, 401 beendet Sitzung, Fehlerzuordnung `ApiProblem`, `getCached`, `multipart` mit `onProgress`, `bytes`), `UploadFile`, `Cached` |
| `services/session.dart` | `Session` (Token in Secure Storage, Rollen, `areas`, `area`, Sprache, Versionsprüfung), `Area` (parent, teacher, management) |
| `localization/strings.dart` | alle Texte in `ar`/`de`/`en` (Test prüft Vollständigkeit) |
| `models/models.dart` | `Child`, `Report`, `FileInfo`, `Post`, `Notice`, `AppNotification`, `MaterialFile`, `parseList` |
| `features/auth/login_page.dart` | Anmeldung (Marke, Formularkarte, Passwort anzeigen, Fehlerbox, Sprachschalter, Version; ab 840 px zweigeteilt) |
| `features/parents/parent_pages.dart` | Start, Kinder, Berichte, Beiträge, `ParentLearning`, `ReportCard`, `PostCard`, `MaterialSection` (Moodle-Karte, animiert) |
| `features/teachers/teacher_pages.dart` | Start, Kinder, `ReportEditor` (Abschnitte, Aktionsleiste, Rückfrage beim Verlassen, Prozent-Upload), Beiträge, `PostComposer` (Vorschau, Prozent), `TeacherMaterials` (Ankreuzen, Freigabeleiste), `AttachmentPicker` |
| `features/management/management_pages.dart` | `ManagementHome`, `ReviewReports` (Prüfung mit Grund), `CourseEditor` (Abschnitte, Dateien, verbergen, verschieben) |
| `features/common/common_pages.dart` | Benachrichtigungen, Mitteilungskarten, `ProfilePage` (Sprache, Passwort, Bereichswechsel) |

### 9.3 Navigation je Bereich
- **Eltern:** Start · Kinder · Berichte · Lernmaterial · Mehr (Beiträge, Benachrichtigungen, Profil).
- **Lehrkräfte:** Start · Kinder · Berichte · Beiträge · Mehr (Dateien/Materialien, Benachrichtigungen, Profil).
- **Leitung:** Start · Prüfung · Lernmaterial · Mehr (Benachrichtigungen, Profil).
Die Glocke im Kopf zeigt die Zahl ungelesener Benachrichtigungen.

### 9.4 Lokale Speicherung
Secure Storage: `access_token`. `shared_preferences`: `lang`, `area`, `cache:<kontoId>:<pfad>` (Listen), `draft:report:<id|new>` (Berichtsentwurf). Windows: `%APPDATA%\com.zahratalmadain\Zahra+\` bzw. `zahra_app`.

### 9.5 Designsystem
Primär `#16406F` (dominiert), Tief `#0E2E52`, Weich `#EAF1F8`, Akzent Gold `#E8A33D` (sparsam: Zähler, ein Hauptknopf). Status: Entwurf grau `#42536A`, Zur Prüfung orange `#8A5200`, Veröffentlicht grün `#1E7A45`, Zurückgegeben rot `#B3402F`; Rot sonst nur für Fehler und kritische Aktionen. Inter für Deutsch/Englisch, Tajawal für Arabisch (je andere Schrift als Rückfall). Karten Radius 16–24, dezente Ränder, Animationen 150–250 ms. Entwurfsbilder liegen in einem Design-Canvas (Artifact „Zahra+ Redesign-Konzept").

### 9.6 Tests
`mobile_app/test/app_test.dart`: 32 Tests (Texte, Modelle, API-Client, Rollen, Navigation, Zustände, Berichte, Prüfung, Lernmaterial, Upload-Fortschritt, Vorschau).

---

## 10. Webseite und Portale
Portale teilen ein Kontosystem (`/login/`). Nach der Anmeldung liefert `/api/auth/entry` die Liste `portals`. Jedes Portal ist eine Menge von Abschnitten hinter einer Navigationsleiste (`viewShell` in `portal.js`). Die Elternanmeldung auf der Webseite bleibt bestehen, bis die App verifiziert ist. Der App-Download-Bereich liegt direkt auf der Startseite (kein eigener Seitenaufruf), gefüllt aus `app-version.json` durch `appdl.js` (Link, Version, Datum, Größe, SHA-256). Die Seite nennt „Android 7.0 oder neuer". iOS-Link ist leer, bis es einen gibt.

---

## 11. Buchhaltung im Detail

Siehe `docs/accounting.md`. Kurz:
- Jeder Vorgang speichert Betrag, tatsächliche Währung, Kurs und Gegenwert; spätere Kurse ändern nichts. Rundung half up: Dollar → ganze Lira, Lira → Cent.
- **Summen je Währung aus dem tatsächlich in dieser Währung gezahlten Geld** (Einnahmen USD − Ausgaben USD usw.). Der Gegenwert wird angezeigt, aber nie zusätzlich gezählt; die umgerechnete Gesamtsicht erscheint nur „zum Vergleich".
- Rechnung = Forderung; nur eine Zahlung (Einnahme mit `invoice_id`) ist Einnahme. Bezahlt/offen/Status werden berechnet; Überzahlung wird abgelehnt.
- Gehalt = Ausgabe der Kategorie `salaries` mit Mitarbeiter und `salary_month`; pro Person und Monat nur einmal, solange die Zahlung steht.
- Nie löschen: offener Monat → Storno mit Grund; abgeschlossener Monat → Gegenbuchung im offenen Monat. Abschluss/Wiedereröffnung nur Leitung, protokolliert.
- Doppelklick-Schutz (gleiche Buchung innerhalb 30 s), Versionsprüfung beim Ändern (`expected_version`).
- Zeitzone: `app/timeutil.py`, Standard `Asia/Damascus` für Buchungstage und Monate.

---

## 12. Tests und Qualitätstore

- Backend: `cd backend && python -m unittest discover -s tests -t . -q` (zuletzt **157 Tests grün**, nach Entfernen der alten Buchhaltungstests). Tests laufen gegen SQLite im Speicher (`Base.metadata.create_all`), Basis `ControlsBase` mit Konten `acc`, `acc2`, `teacher1`, `parent1`, `mgr0`, Legacy-Admin und einem Kind „Amal".
- App: `flutter analyze` (muss „No issues found!" melden) und `flutter test` (zuletzt **32 Tests grün**).
- Neue Funktion → neuer Test, der den echten Ablauf prüft (nicht nur „Widget vorhanden").
- Migrationen: additiv, Alembic-Revisions-ID höchstens 32 Zeichen, `downgrade()` vorhanden, auf SQLite hoch und runter geprüft (`alembic upgrade head`, `downgrade`, erneut `upgrade`).
- Bestehende Tests dürfen nicht gelöscht oder abgeschwächt werden.

---

## 13. Arbeitsumgebung (Windows) und Stolpersteine

- Flutter 3.47.9 unter `C:\dev\flutter`. Android: `JAVA_HOME=/c/dev/jdk/jdk-17.0.21+9`, `ANDROID_HOME=/c/dev/android`, `PATH=/c/dev/flutter/bin:$PATH`. Release-Signierung aus `~/zahra-signing/key.properties` (**Sicherung des Ordners `C:\Users\ahmad\zahra-signing\` empfohlen**).
- **Windows-Testfenster** (erste Testplattform): `flutter build windows --debug`; Programm `mobile_app/build/windows/x64/runner/Debug/zahra_app.exe`. Standardziel: `https://zahra-123hub-almadain-api.onrender.com`. Lokaler Testserver: `cd backend && python dev_server.py` (Port 8765, Konten `lehrer / Lehrer-Test-2026`, `eltern / Eltern-Test-2026`, `verwaltung / Verwaltung-Test-2026`, `leitung / Leitung-Test-2026`), App dazu mit `--dart-define=API_BASE=http://127.0.0.1:8765` bauen. Beenden des Testservers gezielt über `Get-NetTCPConnection -LocalPort 8765`, nie mit Massen-Kill.
- **Bekannte Eigenheiten:**
  - Nach `flutter test`/`analyze` scheitert der erste Windows-Bau oft an fehlenden `ephemeral`-Dateien (OneDrive-Ordner): ein zweiter Bau klappt.
  - Ein laufendes `zahra_app` blockiert den Bau (vorher beenden).
  - `dart format lib` **nicht** auf das ganze Projekt anwenden (erzeugt Lint-Meldungen `curly_braces_in_flow_control_structures`).
  - Dateien mit CRLF: beim Bearbeiten Zeilenenden erhalten.
  - Skripte mit arabischem Text oder Apostrophen als Datei schreiben, nicht per Heredoc.
  - Lokale `dev.db` hat das alte Schema (kein `create_all`-Update); bei Schemaänderung löschen und neu starten.
  - `SessionScope` darf nicht nur in `home` hängen, sonst crasht jede später geöffnete Seite („Null check operator"). Er steht in `MaterialApp.builder`.
  - Kein `SessionScope.of(context)` in `initState` (stilles Scheitern in Debug): `Future.microtask` verwenden.
  - `PopScope` reagiert erst nach einem Frame auf `canPop`-Änderungen (Tests: nach `enterText` `pump()`).
- iOS lässt sich unter Windows nicht bauen und prüfen. Push-Benachrichtigungen brauchen Firebase-Projekt, APNs-Schlüssel und Service-Account-Schlüssel (nicht vorhanden).
- Android-Mindestversion 7.0: `image_picker_android` verlangt minSdk 24; Flutter setzt literale Werte beim Bauen zurück, daher bleibt es bei 24.

---

## 14. Verbindliche Regeln im Umgang mit dem Besitzer

**Git und Veröffentlichung**
1. Implementieren, testen, **lokal committen**, dann fragen: „Soll ich pushen?". **Push nur nach ausdrücklichem „push es"/„pushe"/„ja pushe mal".** Ein Ja für einen Schritt gilt nicht für den nächsten.
2. Nach Backend-Pushes muss der Besitzer bei Render „Manual Deploy → Deploy latest commit" auslösen (Migrationen laufen beim Start). Bei Frontend-Pushes: Cloudflare 1–2 Minuten, dann Strg+F5.
3. **Kein APK-Build, kein iOS-Release, kein Google-Play-Release, keine GitHub-Release, keine Aktualisierung von `app-version.json`** ohne dass der Besitzer ausdrücklich **„final"** sagt. Alles zuerst im Windows-Testfenster prüfen lassen.
4. **Keine Änderung an der echten Neon-Datenbank** ohne ausdrückliche Freigabe und vorheriges Backup (Neon-Branch). Das betrifft insbesondere die Buchhaltungsübernahme.
5. Commit-Nachrichten enden mit der von der Umgebung vorgegebenen Co-Author-Zeile. Nicht ins Repository gehören: `dev.db`, Signierschlüssel, `mobile_app/windows/` und `.vscode/` (derzeit bewusst unversioniert).

**Datenschutz und Sicherheit**
6. Persönliche Daten (Name, Projekt, E-Mail) nicht an externe Dienste senden.
7. Private Kinderprofile, Berichte und Fotos nie in öffentlichen Webseitendaten ablegen.
8. Tokens/Passwörter nie in Logs oder Fehlermeldungen.

**Finanzdaten (besonders streng)**
9. Entwicklung und Tests nur mit SQLite und Testdaten.
10. Geld nur mit `Decimal`; USD und SYP nie mischen.
11. Nichts Finanzielles wird endgültig gelöscht: Storno mit Grund; geschlossene Monate bleiben unverändert; jede Änderung wird mit Benutzer, Zeit, Vorher, Nachher und Grund protokolliert.
12. Nutzertexte der Buchhaltung auf Arabisch (und wo vorhanden Englisch); die Admin-Oberfläche hat kein Deutsch.

**Frontend-Qualität**
13. Alle sichtbaren Texte der App nur über `strings.dart`, jeder Schlüssel in `ar`, `de`, `en`.
14. Keine erfundenen API-Endpunkte oder Datenfelder; fehlt etwas, die nötige Backend-Erweiterung dokumentieren und vorschlagen.
15. Die App muss alte Android- und iOS-Versionen unterstützen; eine Codebasis für Android, iOS und Windows.
16. Die Admin-Oberfläche nutzt den Helfer `h()` (Texte laufen durch `uiText`/`EN_TEXT`), `request()`, `setMsg()`, `errText()`, `money()` sowie aus `admin/ui.js`: `uiT()`, `uiField()`, `uiSelect()`, `uiTable()`, `uiBadge()`, `uiNum()`, `uiToast()`, `uiWhen()`, `uiLogCard()`.

---

## 15. Aktueller Stand (Momentaufnahme)

- **Gepusht (`origin/main` = `4bc621f`):** Leitungsbereich und Kurs-Editor, Berichts-Erweiterungen (Rückgabegrund, Kindernamen, Anhänge für Leitung und Eltern), Redesign der App, Kassenbuch (Backend, Migration `0029`, Übernahme-Logik, Web-Tab), Zeitzone, Upload-Fortschritt, Beitragsvorschau, Freigabeleiste.
- **Lokal unversioniert:** `mobile_app/windows/`, `.vscode/`, einzelne Metadaten (`.metadata`, `analysis_options.yaml`, `pubspec.lock`).
- **Render:** Der Deploy mit den Migrationen `0027`–`0029` muss vom Besitzer ausgelöst werden. Danach kennt der echte Server den Leitungsbereich. Ohne Deploy zeigt das Windows-Fenster gegen den echten Server nur den alten Stand.
- **Buchhaltung:** Die alte Buchhaltung ist entfernt (Branch `accounting-rewrite`, nicht gepusht). Neue Buchhaltung mit drei Seiten; Sauberer Neustart (alte Daten nur als geprüfte Sicherung).

## 16. Offene Punkte

1. Render-Deploy auslösen und danach den Leitungsbereich mit echten Konten testen (die Rolle `manager` muss auf der Webseite im Verwaltungsbereich angelegt sein).
2. Echte Datenbank: Neon-Snapshot → `python -m app.manage finance-backup --out …` (prüft sich selbst) → Deploy → später `drop-old-finance --backup …`. Nur mit ausdrücklicher Freigabe (siehe `backend/FINANCE_SWITCH.md`).
3. Restliche Redesign-Punkte, die noch nicht im echten Fenster abgenommen sind (Layout im breiten Fenster, Bedienung der neuen Bildschirme).
4. Web: Die drei Buchhaltungsseiten wurden lokal im Browser (Edge headless, Testdaten) angesehen; Klick-Abläufe (Formulare absenden) nur über die API-Tests geprüft.
5. Push-Benachrichtigungen (Firebase), iOS-Build (Mac + Apple-Entwicklerkonto), Google Play.
6. Android-APK 1.0.3 mit neuem Design erst nach „final" (danach `app-version.json` nach Veröffentlichung der Release `app-v1.0.3` aktualisieren).
7. Kleinere offene Entscheidungen: Eltern sehen Berichtsanhänge (umgesetzt), Datum beim Bericht wählen (setzt `created_at` serverseitig, nicht änderbar), alte GitHub-Releases aufräumen, Sicherung der Signierschlüssel.

## 17. Fertigkeits-Checkliste für jede Aufgabe (Definition of Done)

- [ ] Code gelesen und verstanden, betroffene Dateien genannt.
- [ ] Änderungen minimal, funktionierende Teile erhalten.
- [ ] Neue Texte in `ar`, `de`, `en` (App) beziehungsweise Arabisch (+ Englisch) (Admin).
- [ ] Tests ergänzt (Ablauf, Rechte, Fehlerfälle), `flutter analyze` sauber, `flutter test` und Backend-Tests grün.
- [ ] Bei Datenbankänderung: additive Migration mit `downgrade`, auf SQLite hoch/runter geprüft.
- [ ] Windows-Fenster neu gebaut, damit der Besitzer testen kann.
- [ ] Lokal committet. **Nicht gepusht**, bis der Besitzer es ausdrücklich sagt.
- [ ] Bericht: was umgesetzt, welche Dateien, was getestet, was nicht, was offen ist.
