# Politik Basel – tägliches Briefing

Jeden Morgen automatisch: Schlagzeilen zur Politik in Basel-Stadt und Basel-Landschaft,
ohne Duplikate, nach Themen sortiert, plus neue Geschäfte des Grossen Rats BS.
Optional schreibt Claude oben «Das Wichtigste in Kürze».

## Was es macht

1. Holt Meldungen der letzten 24 h über Google-News-Suchfeeds (deckt BaZ, bz, Prime News,
   Bajour, SRF, Telebasel u. a. ab) und neue Grossratsgeschäfte von data.bs.ch.
2. Fasst gleiche Geschichten aus mehreren Medien zu einem Eintrag zusammen.
   **Je mehr Medien berichten, desto weiter oben.**
3. Sortiert nach Themen (Verkehr, Finanzen, Wohnen, …).
4. Optional: KI-Kurzzusammenfassung mit Verweisen auf die Meldungen.
5. Schreibt `docs/index.html` (heute) und `docs/archiv/JJJJ-MM-TT.html` (Archiv).

## Einrichten (einmalig, ca. 10 Minuten)

1. **Branch nach `main` mergen**, damit der Zeitplan läuft (GitHub führt geplante
   Workflows nur auf dem Standard-Branch aus).
2. **GitHub Pages einschalten:** Settings → Pages → Source «Deploy from a branch»,
   Branch `main`, Ordner `/docs`. Dann ist das Briefing unter
   `https://<benutzername>.github.io/<repo>/` erreichbar.
   *Hinweis:* Mit einem Gratis-Konto geht Pages nur bei öffentlichen Repos.
3. **Optional, für die KI-Zusammenfassung:** Settings → Secrets and variables → Actions →
   «New repository secret», Name `ANTHROPIC_API_KEY`, Wert = API-Key von
   console.anthropic.com. Kosten: rund 1–3 USD pro Monat.
4. **Testen:** Actions → «Tägliches Briefing» → «Run workflow».

Danach läuft es jeden Morgen um ca. 05:17 (Winter) bzw. 06:17 (Sommer).

## Anpassen

Alles in `config.py`:
- `GOOGLE_NEWS_QUERIES` – Suchbegriffe (z. B. eigene Dossiers, Organisationen, Namen)
- `DIRECT_FEEDS` – eigene RSS-Feeds
- `TOPICS` – Themen und Stichwörter
- `CLAUDE_MODEL` – Modell für die Zusammenfassung

## Grenzen

- Die KI sieht nur Schlagzeilen und Teaser, **keine ganzen Artikel** (Paywalls).
  Zusammenfassungen vor Weiterverwendung prüfen.
- Google-News-Links führen über eine Weiterleitung zum Originalartikel.
- Basel-Landschaft (Landrat) hat keine bestätigte Open-Data-Schnittstelle, BL kommt
  deshalb nur über die Medien rein.
- Fällt eine Quelle aus, steht das unten im Briefing unter «Quellen mit Problemen».

## Lokal ausführen

```bash
pip install -r requirements.txt
python briefing.py              # echtes Briefing (braucht Internet)
python tests/test_briefing.py   # Offline-Test mit Beispieldaten
```
