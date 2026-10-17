ZAHRAT AL-MADAYN: Website mit Python-Backend

Projektstruktur
  index.html, style.css, script.js       öffentliche Website
  images\                                feste Website-Bilder (Logo, Plakat, Icon)
  admin\index.html                      Admin-Seite
  admin\admin.css, admin\admin.js       Admin-Oberfläche
  backend\app\main.py                   FastAPI-Backend
  backend\requirements.txt               Python-Abhängigkeiten
  render.yaml                           Render-Blueprint
  content.json                          Inhalte und Metadaten

Vom Admin hochgeladene Galerie- und News-Bilder bleiben als verwaltete Dateien im
GitHub-Repository-Hauptverzeichnis; sie werden nicht in images\ abgelegt.

Die Website bleibt auf GitHub Pages. Die Admin-Oberfläche sendet keine GitHub-
Zugangsdaten mehr an den Browser. Das Python-Backend liest und ändert content.json
und Mediendateien über die GitHub-API. Ein Fine-grained GitHub-Token wird nur als
geheime Umgebungsvariable auf Render gespeichert.

Sprachen
- Öffentliche Website: Arabisch als Standardsprache, zusätzlich Englisch und Deutsch.
- Admin-Oberfläche: Arabisch als Standardsprache und Englisch über den Sprachschalter.
  Die Admin-Sprachauswahl wird im Browser gespeichert.

Einrichtung und Veröffentlichung
1. Den Projektstand nach main auf GitHub pushen.
2. Bei render.com anmelden und "New" > "Blueprint" wählen. Das Repository
   Zahra-123hub/Zahra-Almadain verbinden und den Blueprint render.yaml anwenden.
3. Beim Einrichten die abgefragten geheimen Werte setzen:
   - GITHUB_TOKEN: neuer Fine-grained Token für Zahra-Almadain,
     Repository permission Contents: Read and write
   - ADMIN_PASSWORD: ein neues, starkes Passwort für die Admin-Seite
   SESSION_SECRET wird von Render erzeugt. Den Token niemals in den Quellcode,
   in die Website oder in den Chat eintragen.
4. Render veröffentlicht die API unter
   https://zahra-123hub-almadain-api.onrender.com. Falls Render eine andere URL vergibt,
   muss apiBase in script.js und API_BASE in admin/admin.js auf diese URL zeigen.
5. GitHub Pages weiter für main und den Root-Ordner /(root) aktivieren.
6. Website: https://zahra-123hub.github.io/Zahra-Almadain/
   Admin:   https://zahra-123hub.github.io/Zahra-Almadain/admin/
   Admin-Anmeldung: Benutzername admin und das auf Render gesetzte Passwort.

Lokaler Backend-Test
  cd backend
  python -m pip install -r requirements.txt
  $env:GITHUB_TOKEN="DEIN_TOKEN"
  $env:ADMIN_PASSWORD="LOKALES_PASSWORT"
  $env:SESSION_SECRET="EIN_LANGER_ZUFAELLIGER_WERT"
  python -m uvicorn app.main:app --reload --port 8001

Vor dem lokalen Browser-Test API_BASE in script.js und admin/admin.js auf
http://127.0.0.1:8001 setzen. ALLOWED_ORIGINS muss den Ursprung der lokalen
Website enthalten.

Sicherheit
- Den zuvor im Chat offengelegten GitHub-Token widerrufen und einen neuen
  Token direkt als Render-Secret speichern.
- Das Admin-Passwort ist derzeit ein gemeinsames Passwort. Nicht mit anderen
  Personen teilen; individuelle Admin-Konten können später ergänzt werden.
- GitHub-Token und SESSION_SECRET nie veröffentlichen oder committen.
