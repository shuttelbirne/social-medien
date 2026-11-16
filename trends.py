#!/usr/bin/env python3
"""Tagestrends für den Social-Loop holen, ohne KI und ohne Tokens.

Quelle 1 (kostenlos): Google Trends „Trending now“ für Deutschland (RSS).
Quelle 2 (optional, kostenpflichtig, aus bis Tim zustimmt): DataForSEO Google-Trends je Marke.

  python3 trends.py            -> social/trends/<datum>.json
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

HIER = Path(__file__).resolve().parent
ZIEL = HIER / "social" / "trends"
RSS = "https://trends.google.de/trending/rss?geo=DE"
NS = {"ht": "https://trends.google.com/trending/rss"}
DATAFORSEO_AN = False  # erst auf Tims Ja einschalten (Kosten rund 1 bis 2 € im Monat)


def google_rss() -> list[dict]:
    req = urllib.request.Request(RSS, headers={"User-Agent": "Mozilla/5.0 (bildwerk trends)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        root = ET.fromstring(r.read())
    trends = []
    for item in root.iter("item"):
        trends.append({
            "suche": (item.findtext("title") or "").strip(),
            "volumen": (item.findtext("ht:approx_traffic", namespaces=NS) or "").strip(),
            "schlagzeilen": [n.findtext("ht:news_item_title", namespaces=NS) or ""
                             for n in item.findall("ht:news_item", NS)][:3],
        })
    return trends


def main() -> int:
    ZIEL.mkdir(parents=True, exist_ok=True)
    daten = {"datum": date.today().isoformat(), "abgerufen": time.strftime("%Y-%m-%d %H:%M:%S"),
             "google_de": [], "fehler": []}
    try:
        daten["google_de"] = google_rss()
    except Exception as e:
        daten["fehler"].append(f"Google-RSS: {e}")
    datei = ZIEL / f"{daten['datum']}.json"
    datei.write_text(json.dumps(daten, ensure_ascii=False, indent=1))
    print(f"{len(daten['google_de'])} Trends -> {datei}" + (f" (Fehler: {daten['fehler']})" if daten["fehler"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
