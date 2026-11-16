# Jahresplan Instagram · Schema und Regeln

Gilt für alle Plan-Dateien `social/plaene/<marke>/q1.json` bis `q4.json`. Jede Datei ist eine JSON-Liste von Beiträgen, mit genau den Terminen und Formaten aus `gerüst-qN.json` (39 je Quartal, 156 im Jahr). Fakten nur aus `social/fakten.md`, Marke aus `social/marken.json`.

## Felder je Beitrag

```json
{
  "datum": "2026-11-16",            // aus dem Gerüst, nicht ändern
  "format": "karussell",            // aus dem Gerüst: karussell oder einzelbild
  "slug": "truebes-wasser-ursachen",// klein, Bindestriche, eindeutig, max. 50 Zeichen
  "thema": "Trübes Wasser",         // Kurzthema für den Kalender
  "saeule": "wissen",               // wissen | anleitung | frage | produkt | saison
  "titel": "Dein Wasser ist trüb? So findest du die Ursache",  // Titelbild, max. 70 Zeichen, besser unter 50
  "untertitel": "Drei Farben, drei Ursachen",                  // optional, max. 40 Zeichen
  "bild_prompt": "english photo description of the cover image, concrete subject, setting, light", // ENGLISCH, ohne Stilwörter
  "folien": [                       // nur karussell: 3 bis 6 Folien
    {"ueberschrift": "Weiß und milchig", "text": "max. 280 Zeichen, ganze Sätze"}
  ],
  "schluss": {"ueberschrift": "Speicher dir den Beitrag", "text": "Eine Bitte, max. 160 Zeichen"}, // nur karussell
  "caption": "…",                   // siehe Caption-Regeln
  "suchbegriffe": ["trübes wasser", "aquarium"],  // 2 bis 3 deutsche Suchphrasen, die in der Caption stehen
  "alt": "Beschreibung des Titelbilds für Screenreader, 1 bis 2 Sätze",
  "story": {"text": "Frage oder Satz für die Story, max. 60 Zeichen",
            "nachsatz": "optional, max. 50 Zeichen, an die Zuschauer gerichtet",
            "sticker": "Umfrage: Ja / Nein  oder  Frage: …  oder  Quiz: …  oder  Link"}
}
```

## Caption-Regeln (aus Skill ig-caption)

1. **Erste Zeile höchstens 125 Zeichen.** Sie ist der Hook: konkret, mit Zahl, Name oder Ding. Nie eine Begrüßung, nie ein Hashtag oder Emoji am Anfang. Einer der Suchbegriffe steht in diesen ersten 125 Zeichen.
2. Danach 2 bis 5 kurze Absätze mit Leerzeile dazwischen. Gesamt 300 bis 900 Zeichen.
3. **Genau eine Bitte**: speichern, teilen, kommentieren mit einem Wort, oder „Link im Profil“. Nie zwei.
4. **Kein Link**, keine URL, keine Domain in der Caption.
5. **Höchstens 3 Hashtags**, spezifisch und deutsch, in der letzten Zeile. Kein #viral, #fyp, #foryou, #explorepage.
6. Keine Emojis, höchstens eines als Satzzeichen.
7. Keine Gedankenstriche (—), keine geschwungenen Anführungszeichen im Englischstil, kein „…“ als Stilmittel.

## Tims Schreibregeln (gelten für alle Texte, werden geprüft)

- Nie das Wort „aber“. Stattdessen „und“, „gleichzeitig“ oder einen neuen Satz.
- Kein Semikolon, kein Gedankenstrich als Stilmittel.
- Keine Dreierketten.

## Schreibstil (aus Skills ig-human und stop-slop)

- Deutsch, natürlich, wie ein Mensch, der sich auskennt.
- Verboten sind diese Floskeln und Muster:
  - „In der heutigen Zeit“, „Tauche ein“, „Entdecke“, „Egal ob … oder …“, „Mehr als nur“
  - „nicht X, sondern Y“ als Aufhänger
  - Dreierlisten aus Adjektiven
  - „Hier sind 5 Tipps“ ohne Inhalt
  - Fragen, die nur sich selbst beantworten
- Jede Folie trägt eine konkrete Information: Zahl, Handgriff, Name, Grenze. Keine Füllfolie.
- Fakten nur, wenn sie zum Fachgebiet allgemein gesichert sind oder in `fakten.md` stehen. Bei Unsicherheit weglassen. Nichts über das Produkt erfinden: keine Kunden, Zahlen, Bewertungen oder Ergebnisse.

## Bildregeln

- `bild_prompt` auf Englisch, ein konkretes Motiv. Die Marke ergänzt den Stil, deshalb keine Stilwörter.
- Erlaubte Motive stehen bei `motiv_hinweis` in `marken.json`.
- Keine Gesichter in Großaufnahme, keine echten oder berühmten Personen, kein Text im Bild, keine Logos. Kinder nur, wo es nötig ist, und dann nicht als Hauptmotiv. Nichts Freizügiges.
- Das untere Drittel trägt später den Titel, deshalb das Hauptmotiv in die obere Bildhälfte oder mittig setzen.
- Die Motive über das Jahr abwechseln: nicht zehnmal dasselbe.

## Wochenrhythmus und Mischung

| Tag | Format | Rolle |
|---|---|---|
| Montag | Karussell | Wissen oder Anleitung, die man speichert |
| Mittwoch | Einzelbild | Frage, Gedanke, Saison oder eine Zahl. Die Caption trägt den Inhalt (Hook in Zeile 1). |
| Freitag | Karussell | Anleitung, Checkliste, Fehler vermeiden oder Produkt-Einblick |

- Über das Jahr höchstens jeder fünfte Beitrag mit Produktbezug (Säule „produkt“). Der Rest ist reiner Nutzen.
- Saisonthemen stehen in `fakten.md` und gehören in die richtigen Wochen.
- Kein Thema doppelt. Ähnliche Themen frühestens nach 8 Wochen wieder, und dann aus einem anderen Blickwinkel.
- Jede Woche hat eine Story (Feld `story` je Beitrag). Sticker abwechseln: Umfrage, Frage, Quiz, Link.

## Prüfen

`python3 social.py pruefen <marke>` muss ohne Fehler laufen.
