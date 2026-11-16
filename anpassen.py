#!/usr/bin/env python3
"""Feinschliff: Planeintrag am Vortag an Tagestrends, Saison und Anlass anpassen.

Der Jahresplan ist nur Orientierung (Tim, 12.11.2026). Je Beitrag ein Sonnet-Aufruf.
Besteht der neue Text die Regeln nicht, bleibt der Planeintrag.

  python3 anpassen.py <marke> <datum>           # anpassen und in den Plan schreiben
  python3 anpassen.py <marke> <datum> --trocken # nur zeigen
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import social  # noqa: E402

CLAUDE = Path.home() / ".local" / "bin" / "claude"
MODELL = "sonnet"
FELDER_FEST = ("datum", "format", "slug", "woche", "_datei")


def fakten_abschnitt(marke: str) -> str:
    text = (social.SOC / "fakten.md").read_text(encoding="utf-8")
    name = social.MARKEN[marke]["name"]
    teile = re.split(r"\n## ", text)
    for t in teile:
        if t.startswith(name):
            return "## " + t
    return text


def letzte_beitraege(marke: str, datum: str, n: int = 8) -> list[str]:
    vorher = [b for b in social.plan(marke) if b["datum"] < datum]
    return [f"{b['datum']}: {b['titel']}" for b in vorher[-n:]]


def trends_heute() -> list[dict]:
    dateien = sorted((social.SOC / "trends").glob("*.json"))
    if not dateien:
        return []
    return json.loads(dateien[-1].read_text()).get("google_de", [])


def anpassen(marke: str, datum: str, trocken: bool = False) -> str:
    plan = social.plan(marke)
    treffer = [b for b in plan if b["datum"] == datum]
    if not treffer:
        return "kein Beitrag an diesem Tag"
    b = treffer[0]
    if b.get("angepasst"):
        return "schon angepasst"
    vorlage = {k: v for k, v in b.items() if not k.startswith("_")}
    frage = f"""Du baust den Instagram-Beitrag für morgen ({datum}) der Marke {social.MARKEN[marke]['name']}.
Der Jahresplan-Eintrag unten ist nur Orientierung. Prüfe zuerst die heutigen Suchtrends in Deutschland und den Kalender (Saison, Feiertage, Anlässe dieser Woche).
- Passt ein Trend oder Anlass glaubwürdig zur Marke und ihrer Zielgruppe: Baue den Beitrag darauf um (Thema, Titel, Folien, Caption, Story, Bild).
- Passt nichts: Verbessere den Plan-Eintrag nur, wo nötig, oder lass ihn gleich.
Nie einen Trend erzwingen, keine Unglücke, Politik, Krieg, Kriminalfälle oder Personen ausschlachten.

FAKTEN UND VERBOTE DER MARKE (verbindlich):
{fakten_abschnitt(marke)}

REGELN (verbindlich): Schema wie Vorlage. datum, format, slug bleiben unverändert. Karussell 3 bis 6 Folien (Text je max. 280 Zeichen). Titel max. 70 Zeichen. Caption: erste Zeile max. 125 Zeichen mit Suchbegriff, 300 bis 900 Zeichen, genau eine Bitte, kein Link, höchstens 3 deutsche Hashtags in der letzten Zeile, keine Emojis. Nie das Wort „aber“, kein Semikolon, kein Gedankenstrich, keine Dreierketten. bild_prompt auf Englisch, konkretes Motiv ohne Schrift, Zahlen, Etiketten, Bildschirminhalte oder Gesichter in Großaufnahme. Fakten nur, wenn gesichert. Deutsch, natürlich.

LETZTE BEITRÄGE (nicht wiederholen):
{json.dumps(letzte_beitraege(marke, datum), ensure_ascii=False)}

SUCHTRENDS DEUTSCHLAND HEUTE:
{json.dumps(trends_heute(), ensure_ascii=False)[:4000]}

PLAN-EINTRAG (Vorlage):
{json.dumps(vorlage, ensure_ascii=False)}

Antworte NUR mit dem fertigen JSON-Objekt des Beitrags, zusätzlich mit dem Feld "anlass": kurzer Grund (Trend, Anlass oder "Plan")."""
    try:
        r = subprocess.run([str(CLAUDE), "-p", frage, "--model", MODELL, "--output-format", "text",
                            "--allowedTools", ""], capture_output=True, text=True, timeout=600,
                           env={**os.environ, "ANTHROPIC_API_KEY": ""})
        text = r.stdout.strip()
        neu = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except Exception as e:
        return f"Fehler beim Anpassen ({e}), Plan bleibt"
    for k in FELDER_FEST:
        if k in b:
            neu[k] = b[k]
    fehler = social.pruefe_eintrag(neu, datum)
    if fehler:
        return f"neuer Text fällt durch ({'; '.join(fehler[:3])}), Plan bleibt"
    if trocken:
        return json.dumps(neu, ensure_ascii=False, indent=1)
    neu["angepasst"] = time.strftime("%Y-%m-%d %H:%M")
    neu["plan_original"] = {k: v for k, v in vorlage.items() if k != "plan_original"}
    datei = social.SOC / "plaene" / marke / b["_datei"]
    daten = json.loads(datei.read_text(encoding="utf-8"))
    for i, x in enumerate(daten):
        if x["datum"] == datum:
            neu.pop("_datei", None)
            daten[i] = neu
    tmp = datei.with_suffix(".tmp")
    tmp.write_text(json.dumps(daten, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, datei)
    return f"angepasst ({neu.get('anlass', '?')}): {neu['titel']}"


if __name__ == "__main__":
    print(anpassen(sys.argv[1], sys.argv[2], "--trocken" in sys.argv))
