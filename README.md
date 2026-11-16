# Social-Medien · Instagram-Loop

Dieses Repo enthält den Loop-Teil der Instagram-Produktion für vier Angebote des Rauschwerk Verlags: Hochzeitsfunken, Beckenbuch, Hundefutterpilot und KI-Krimidinner. Der Code stammt aus dem privaten Arbeitsordner `bildwerk` (Stand Commit `f77d533` vom 12.11.2026) und liegt hier als unveränderte Kopie.

## Was der Loop tut

Der Loop hat zwei Teile. `tagesloop.py` läuft nachts. Er holt die Suchtrends des Tages über den öffentlichen Google-Trends-Feed (`trends.py`), schleift die Beiträge für heute und morgen am Plan nach (`anpassen.py`, ein Sonnet-Aufruf je Beitrag), erzeugt fehlende Titelbilder mit einem lokalen ComfyUI (`bildwerk.py`) und lässt jedes neue Bild von Haiku prüfen. Danach rendert `social.py` je Beitrag die Folien samt Story und packt sie als ZIP.

`poster.py` veröffentlicht den Beitrag des Tages samt Story über die offizielle Instagram-API. Er postet nur, wenn ein Konto in `social/konten.json` aktiv ist und ein Zugriffsschlüssel im macOS-Schlüsselbund liegt. Solange das fehlt, schreibt er nur „nicht eingerichtet“ ins Protokoll. Mit `--trocken` zeigt er bloß an, was er posten würde.

Wie Konten, Schlüssel und Bildablage eingerichtet werden, steht in `social/POSTEN-EINRICHTEN.md`. Das Schema der Plan-Dateien steht in `social/PLAN-SCHEMA.md`.

## Dateien

| Datei | Zweck |
|---|---|
| `tagesloop.py` | nächtlicher Lauf: Trends, Feinschliff, Bilder, Rendern |
| `trends.py` | Tagestrends Deutschland aus dem Google-Trends-Feed, ohne Schlüssel |
| `anpassen.py` | Feinschliff eines Planeintrags am Vortag |
| `poster.py` | Veröffentlichen über die Instagram-API |
| `social.py` | Plan lesen und prüfen, Folien und Story rendern |
| `bildwerk.py` | Anbindung an das lokale ComfyUI |
| `social/marken.json` | Farben, Schriften und Bildstil je Marke |
| `social/konten.beispiel.json` | Vorlage für `social/konten.json`, ohne Konto-IDs |
| `social/POSTEN-EINRICHTEN.md` | Anleitung zum Einrichten |
| `social/PLAN-SCHEMA.md` | Felder und Regeln der Plan-Dateien |
| `launchd/*.plist` | Zeitpläne als Vorlage (03:00 Tagesloop, 18:00 Poster) |

## Keine Schlüssel im Repo

Hier liegen keine Zugriffsschlüssel, Tokens, Passwörter oder `.env`-Dateien. Der Instagram-Schlüssel wird zur Laufzeit aus dem macOS-Schlüsselbund gelesen (Dienst `instagram-<marke>`). Die echte `social/konten.json` mit den Instagram-Konto-IDs bleibt lokal und steht in `.gitignore`. Vor dem ersten Commit lief eine Suche nach Schlüsseln, Tokens, Konto-IDs und Mailadressen über alle Dateien ohne Treffer.

## Bewusst nicht enthalten

Nicht im Repo liegen die Redaktionspläne (`social/plaene`), die Produktfakten je Marke (`social/fakten.md`), die Profil-Pakete, die Schriftdateien, die erzeugten Bilder und Beiträge, der Bild-Stapellauf `nachtlauf.py` sowie alle Protokolle und Statusdateien (`*.log`, `stand.json`). Ohne diese Dateien läuft der Code deshalb nicht aus diesem Repo heraus. Er läuft weiter aus dem privaten Arbeitsordner.

## Zeitpläne

Die beiden Plists in `launchd/` sind nur Dateien. Aus diesem Repo wird nichts geladen und kein Zeitplan eingerichtet. Ob der Poster scharf geschaltet wird, entscheidet Tim im Leitauftrag „Social-Loop scharf schalten“.

## Bildablage

`social/POSTEN-EINRICHTEN.md` sieht dieses Repo auch als öffentliche Bildablage vor. Die Instagram-API lädt Bilder nur von einer öffentlichen HTTPS-Adresse. Ist die Ablage in `social/konten.json` eingeschaltet, legt `poster.py` kurz vor dem Posten die Folien eines Beitrags in einem Ordner `<marke>/<datum-slug>/` in einem lokalen Klon dieses Repos ab, schiebt sie hoch und gibt der API die Adresse über `raw.githubusercontent.com`. Die Ablage ist noch nicht eingeschaltet.
