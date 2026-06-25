# MMM Weekly Quiz — Dev-Dokumentation

Wöchentliches Community-Quiz (eine Frage pro ISO-Woche), statisch unter der Katalog-GitHub-Pages-Site.

**Live-URL (nach Deploy):** https://selloa.github.io/mmm-data/quiz/

Die Quiz-Seite nutzt dasselbe dezente Site-Chrome wie die Geburtstagsseite (Header-Nav `Katalog · Tabelle · Geburtstage · Quiz`, Dark-Mode-Toggle, Section-Layout). Gemeinsame Bausteine liegen in [`scripts/site_chrome.py`](../scripts/site_chrome.py).

---

## Architektur (kurz)

| Was | Wo |
|-----|-----|
| Fragen (Quelle) | `quiz/rounds/*.json` — versioniert, von dir kuratiert |
| Vorschlags-Entwürfe | `quiz/suggestions/*.md` — optional, nur Hilfe beim Schreiben |
| Build | `scripts/build_quiz_site.py` (wird von `build_catalog_site.py` mit aufgerufen) |
| Output | `site/quiz/index.html` + `site/quiz/schedule.json` — **gitignored**, nur auf Pages |

Kein Backend, kein Cron. Die Live-Seite zeigt nur, was beim letzten Deploy aus den JSON-Dateien gebaut wurde.

---

## Veröffentlichen

1. Änderungen an `quiz/**` (oder Quiz-Skripte) committen und auf `main` pushen.
2. Workflow [`.github/workflows/deploy-site.yml`](../.github/workflows/deploy-site.yml) baut `python scripts/build_catalog_site.py` und deployt `site/`.
3. Alternativ: GitHub **Actions → Deploy Site → Run workflow** (manuell).

Der Katalog verlinkt das Quiz unter „Zum wöchentlichen MMM-Quiz“.

---

## Monatlicher Workflow (~30–60 Min)

```powershell
# 1. Ideen für den kommenden Monat (optional)
python scripts/quiz_suggest.py --month 2026-08
# → quiz/suggestions/2026-08.md

# 2. Fragen in quiz/rounds/ eintragen (neue Datei oder bestehende erweitern)

# 3. Lokal prüfen
python scripts/build_catalog_site.py
# site/quiz/index.html öffnen, ggf. ?week=2026-W31 testen

# 4. Committen & pushen
```

**Rhythmus:** ca. vier Fragen pro Monat = vier ISO-Wochen (eine Frage pro Woche).

`quiz_suggest.py` schreibt **keine** live Fragen — nur Markdown mit Jubiläen, Staffel-Themen und ENTWURF-Vorschlägen zum Abgreifen.

---

## Neue Fragen anlegen

Alle Dateien in `quiz/rounds/*.json` werden beim Build zusammengeführt. Pro **ISO-Woche** (`YYYY-Wnn`) darf es nur **eine** Frage geben (über alle Dateien hinweg).

### Beispiel `quiz/rounds/2026-08.json`

```json
{
  "meta": {
    "label": "August 2026",
    "theme": "Staffel 8",
    "author": "selloa"
  },
  "rounds": [
    {
      "week": "2026-W31",
      "theme": "Optional: Wochen-Motto",
      "category": "chronik",
      "category_label": "Chronik",
      "question": "Fragetext?",
      "options": [
        "Antwort A",
        "Antwort B",
        "Antwort C",
        "Antwort D"
      ],
      "correct_index": 1,
      "explanation": "Nur für den Spieler nach richtiger Antwort sichtbar.",
      "links": {
        "catalog_id": "EP-071",
        "wiki": "http://wiki.maniac-mansion-mania.de/wiki/…"
      },
      "dev_notes": "Optional, erscheint nicht in der UI"
    }
  ]
}
```

### Felder

| Feld | Pflicht | Hinweis |
|------|---------|---------|
| `week` | ja | Format `2026-W31` |
| `question` | ja | |
| `options` | ja | Genau 4 Strings |
| `correct_index` | ja | 0–3 |
| `category` / `category_label` | ja | z. B. `handlung`, `autoren`, `chronik`, `katalog` |
| `theme` | nein | Wochen-Motto in der UI |
| `explanation` | empfohlen | Nach richtiger Antwort |
| `links.catalog_id` | empfohlen | Muss in `source/mmm_catalog.csv` existieren |
| `links.wiki` | nein | Wiki-Link als Tipp |
| `dev_notes` | nein | Nur für dich (z. B. „Datum verifizieren“) |

### Validierung

Beim Build prüft [`scripts/quiz_lib.py`](../scripts/quiz_lib.py):

- eindeutige Wochen
- 4 Optionen, `correct_index` in Range
- unbekannte `catalog_id` → Build bricht ab (exit 1)

---

## Was passiert, wenn du nichts machst?

| Situation | Ergebnis |
|-----------|----------|
| Kein Push / keine neuen JSON-Einträge | Alte Fragen bleiben online, keine neuen Wochen |
| Aktuelle Woche ohne Eintrag in `schedule.json` | UI: „Für **2026-Wxx** ist noch keine Frage hinterlegt“ + Link zum Katalog + Liste geplanter Wochen |
| `quiz_suggest.py` nicht ausgeführt | Harmlos — nur weniger Schreibhilfe |

Es gibt **keine** automatische Frage-Generierung auf der Live-Seite.

**Pilotstand:** [`rounds/2026-pilot.json`](rounds/2026-pilot.json) deckt **2026-W26–W29** ab. Ab W30 erscheint der leere Zustand, bis du nachlegst.

---

## Lokales Testen

```powershell
python scripts/build_catalog_site.py
```

- `site/quiz/index.html` im Browser öffnen
- Andere Woche erzwingen: `?week=2026-W27`
- Forum-Text und Erklärung erst nach **richtiger** Antwort

---

## Dev Tool (lokal, Copy-Paste)

Zum Kuratieren neuer Runden ohne direktes Schreiben in `quiz/rounds/`:

```powershell
python scripts/quiz_dev_tool.py
# → http://127.0.0.1:8765
```

Das Tool bietet:

- **Übersicht** aller Runden + Lücken (nächste 8 ISO-Wochen), inkl. Fallback-Hinweis
- **Editor** mit Katalog-Picker, Spieler-Vorschau und Validierung gegen `mmm_catalog.csv`
- **Vorschläge** aus `quiz_suggest` (Jubiläen, Autor-Entwürfe) — per Klick ins Formular
- **Copy JSON** (einzelne Runde oder Datei-Skeleton mit `meta`) zum manuellen Einfügen

Es schreibt **nicht** in `quiz/rounds/`. Typischer Ablauf:

```powershell
python scripts/quiz_dev_tool.py
# Browser: Lücke wählen → Vorschlag übernehmen → kuratieren → Validieren → Copy JSON
# In quiz/rounds/YYYY-MM.json einfügen
python scripts/build_catalog_site.py
```

Port ändern: `python scripts/quiz_dev_tool.py --port 9000`

---

## Forum-Text (Spieler)

Nach richtiger Antwort: Button „In Zwischenablage kopieren“. **Keine Lösung** im Text — nur Ich-Perspektive, Woche, Kategorie, Versuchsanzahl, URL.

Beispiel:

```
🧠 MMM Mania Quiz #2026-W26 — Handlung
✅ Erster Versuch!
https://selloa.github.io/mmm-data/quiz/
```

Optional: Checkbox **„Hinweis: Katalog-Korrektur nötig“** fügt hinzu:

```
Ich glaube, das stimmt nicht — der Katalog braucht hier eine Korrektur.
```

---

## Skripte

| Skript | Zweck |
|--------|--------|
| [`scripts/quiz_lib.py`](../scripts/quiz_lib.py) | Laden, Validierung, `schedule.json` |
| [`scripts/build_quiz_site.py`](../scripts/build_quiz_site.py) | HTML + JSON nach `site/quiz/` |
| [`scripts/quiz_suggest.py`](../scripts/quiz_suggest.py) | Monats-Vorschläge → `quiz/suggestions/` |
| [`scripts/quiz_dev_tool.py`](../scripts/quiz_dev_tool.py) | Lokales Dev-UI (`:8765`) — Editor, Validierung, Copy JSON |
| [`scripts/build_catalog_site.py`](../scripts/build_catalog_site.py) | Ruft Quiz-Build am Ende von `main()` auf |

---

## ISO-Wochen ermitteln

Jede Frage braucht die exakte Woche, in der sie live gehen soll (Montag–Sonntag dieselbe Frage).

In PowerShell z. B.:

```powershell
Get-Date -UFormat '%V'   # Kalenderwoche (approximativ; für Produktion ISO-Woche aus Kalender nehmen)
```

Oder im Browser die Quiz-URL ohne `?week=` öffnen — die Seite nutzt dieselbe ISO-Wochen-Logik wie live.
