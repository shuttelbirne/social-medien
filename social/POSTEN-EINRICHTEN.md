# Social-Loop einrichten (für Tim)

Der Loop hat zwei Zeitpläne.

| Zeit | Skript | Tokens |
|---|---|---|
| 03:00 | `tagesloop.py` holt die Tagestrends (Google, kostenlos), schleift die Beiträge für heute und morgen nach (Sonnet, ein Aufruf je Beitrag, rund 40 s), erzeugt die Titelbilder mit ComfyUI (wartet, solange Ollama ein Modell hält), lässt jedes neue Bild von Haiku prüfen (bei Fehler bis zu 3 Versuche) und rendert Folien, Story und ZIP. Er holt dabei auch fehlende Bilder der nächsten 7 Tage nach. | rund 10.000 je Beitrag, bei 12 Beiträgen pro Woche also gut 100.000 Tokens pro Woche |
| 18:00 | `poster.py` postet den Beitrag des Tages samt Story über die offizielle Instagram-API. | keine |

## 1. Zeitpläne einschalten (einmal, du selbst)

```
cp ~/Projects/bildwerk/launchd/de.tim.social-*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/de.tim.social-tagesloop.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/de.tim.social-poster.plist
```

Prüfen: `launchctl list | grep social`. Ausschalten: `launchctl bootout gui/$(id -u)/de.tim.social-tagesloop` (für den Poster entsprechend).

Der Poster tut nichts, solange Schritt 2 fehlt. Er schreibt dann nur „nicht eingerichtet“ in `social/poster.log`.

## 2. Posten freischalten (je Konto einmal, du selbst)

1. **Instagram-Konto** anlegen und auf „Business“ stellen (siehe `START.md`).
2. **Facebook-Seite** je Marke anlegen und in den Instagram-Einstellungen verbinden. Die API braucht diese Verbindung.
3. **Meta-App:** unter developers.facebook.com eine App vom Typ „Business“ anlegen und das Produkt „Instagram“ hinzufügen. Berechtigungen: `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`. Für eigene Konten genügt der Entwicklungsmodus, eine App-Prüfung durch Meta ist nicht nötig.
4. **Langlebigen Zugriffsschlüssel** erzeugen (Graph API Explorer, dann auf 60 Tage verlängern oder als System-User-Schlüssel ohne Ablauf) und in den Schlüsselbund legen:
   `security add-generic-password -s instagram-beckenbuch -a tim -w` (fragt den Schlüssel ab, der Name je Marke heißt `instagram-<marke>`).
5. **Instagram-User-ID** je Konto (Graph API Explorer: `me/accounts?fields=instagram_business_account`) in `social/konten.json` eintragen:
   ```json
   {"beckenbuch": {"ig_user_id": "1784…", "aktiv": true},
    "ablage": {"art": "ssh", "ziel": "…", "url": "https://…/social"}}
   ```
6. **Öffentliche Bildablage** (Tim 12.11.: „ja öffentlich bereitstellen“): ein öffentliches GitHub-Repo nur für Bilder. Einmal anlegen:
   ```
   mkdir -p ~/Projects/social-medien && cd ~/Projects/social-medien && git init -q -b main && echo "# Social-Medien" > README.md && git add README.md && git commit -q -m start && gh repo create shuttelbirne/social-medien --public --source=. --push
   ```
   In `social/konten.json`: `"ablage": {"art": "github", "klon": "~/Projects/social-medien", "repo": "shuttelbirne/social-medien"}`. Der Poster legt jeden Beitrag kurz vor dem Posten dort ab.

## 3. Kosten und Schalter

- Trends kostenlos über Google. DataForSEO für Nischentrends kostet rund 1 bis 2 € im Monat und ist aus (`DATAFORSEO_AN` in `trends.py`). Einschalten nur auf dein Ja.
- Ohne Haiku-Prüfung: In der Plist `--ohne-pruefung` anhängen.
- Der Jahresplan ist Orientierung. Jede Anpassung steht im Plan mit `angepasst` und `plan_original`.
- Notion bekommt angepasste Texte und den Status „Veröffentlicht“ nicht automatisch, weil auf dem Mac kein Notion-Schlüssel liegt. Mit einem Notion-Integrationsschlüssel ließe sich das ohne Tokens nachziehen.
