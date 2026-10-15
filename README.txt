ZAHRAT AL-MADAYN: Website + Admin-Seite (kostenlos auf GitHub Pages)

Alle Dateien liegen in diesem einen Ordner:
  index.html     HTML der Website
  style.css      Stylesheet der Website
  script.js      JavaScript der Website
  admin\         Ordner der Admin-Seite
    index.html   HTML der Admin-Seite
    admin.css    Stylesheet der Admin-Seite
    admin.js     JavaScript und GitHub-API-Anbindung der Admin-Seite
  content.json   gespeicherte Inhalte (Bilder, Videos, News, Einstellungen)
  logo.png, poster.jpg, fav.png   Bilder der Website

Die Website wird statisch über GitHub Pages bereitgestellt. Es gibt daher keinen
separaten Server-Backend-Prozess: admin/admin.js kommuniziert direkt im Browser mit
der GitHub-API und benötigt dafür das GitHub-Token des Administrators.

EINRICHTUNG MIT DEM BESTEHENDEN REPOSITORY
1. Im Repository https://github.com/Zahra-123hub/Zahra-Almadain die Dateien aus diesem
   Ordner hochladen: "Add file" > "Upload files" > "Commit changes".
2. Settings > Pages > "Deploy from a branch" > Branch main, Ordner "/ (root)" > Save.
   Nach 1-2 Minuten sollte die Website unter
   https://zahra-123hub.github.io/Zahra-Almadain/ erreichbar sein.
4. Token erstellen: GitHub-Profilbild > Settings > Developer settings > Personal access tokens >
   Fine-grained tokens > Generate new token.
   - Repository access: Only select repositories > dein Repository
   - Permissions > Contents: Read and write
5. Admin-Seite: https://zahra-123hub.github.io/Zahra-Almadain/admin/
   Konto und Repository sind vorausgefüllt. Token dort selbst eingeben.

WICHTIG
- Das Token ist wie ein Passwort. Niemals weitergeben. Auf fremden Geraeten "خروج" druecken.
- Ohne Token kann niemand etwas aendern.
- Aenderungen erscheinen nach 1-2 Minuten auf der Website.
- Bilder bis 10 MB, Videos bis 25 MB. Hochgeladene Dateien landen ebenfalls in diesem Repository.
