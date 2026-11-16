#!/usr/bin/env python3
"""Postet die fertigen Beiträge des Tages über die Instagram Graph API (Content Publishing).

  python3 poster.py --trocken   # zeigt, was heute gepostet würde (Standard, solange nichts eingerichtet ist)
  python3 poster.py             # postet wirklich (nur mit Konto-Konfiguration)

Voraussetzungen je Marke (von Tim einzurichten, siehe social/POSTEN-EINRICHTEN.md):
- Instagram-Business-Konto, verbunden mit einer Facebook-Seite
- Meta-App mit Berechtigung instagram_content_publish, langlebiger Zugriffsschlüssel
- Schlüssel im macOS-Schlüsselbund: Dienst "instagram-<marke>" (security add-generic-password)
- social/konten.json: {"<marke>": {"ig_user_id": "…", "aktiv": true}}
- Öffentliche Bildablage (die API lädt Bilder nur von einer öffentlichen HTTPS-Adresse):
  social/konten.json -> "ablage": {"art": "ssh", "ziel": "user@host:/pfad", "url": "https://…/social"}
Ergebnis je Beitrag wird in social/stand.json unter "gepostet" vermerkt. Protokoll: social/poster.log
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import social  # noqa: E402

API_FACEBOOK = "https://graph.facebook.com/v23.0"
API_INSTAGRAM = "https://graph.instagram.com/v23.0"
API = API_INSTAGRAM  # Standard: Instagram-Login (ohne Facebook-Seite); in konten.json "api": "facebook" umschaltbar
KONTEN = HIER / "social" / "konten.json"
STAND = HIER / "social" / "stand.json"
LOG = HIER / "social" / "poster.log"


def log(text: str) -> None:
    zeile = time.strftime("%Y-%m-%d %H:%M:%S ") + text
    print(zeile, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def schluessel_verlaengern(marke: str) -> None:
    """Instagram-Login-Schlüssel laufen nach 60 Tagen ab. Einmal pro Woche verlängern und im Schlüsselbund ersetzen."""
    merker = HIER / "social" / f".verlaengert-{marke}"
    if merker.exists() and time.time() - merker.stat().st_mtime < 7 * 86400:
        return
    alt = schluessel(marke)
    url = "https://graph.instagram.com/refresh_access_token?" + urllib.parse.urlencode(
        {"grant_type": "ig_refresh_token", "access_token": alt})
    with urllib.request.urlopen(url, timeout=60) as r:
        neu = json.loads(r.read())["access_token"]
    subprocess.run(["security", "add-generic-password", "-U", "-s", f"instagram-{marke}", "-a", "tim", "-w", neu],
                   check=True, capture_output=True)
    merker.touch()
    log(f"{marke}: Schlüssel verlängert")


def schluessel(marke: str) -> str:
    r = subprocess.run(["security", "find-generic-password", "-s", f"instagram-{marke}", "-w"],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"kein Schlüssel instagram-{marke} im Schlüsselbund")
    return r.stdout.strip()


def graph(pfad: str, token: str, daten: dict | None = None) -> dict:
    if daten is None:
        url = f"{API}/{pfad}?{urllib.parse.urlencode({'access_token': token, 'fields': 'status_code'})}"
        req = urllib.request.Request(url)
    else:
        daten = {**daten, "access_token": token}
        req = urllib.request.Request(f"{API}/{pfad}", data=urllib.parse.urlencode(daten).encode(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def warten_fertig(container: str, token: str) -> None:
    for _ in range(30):
        if graph(container, token).get("status_code") == "FINISHED":
            return
        time.sleep(5)
    raise RuntimeError(f"Container {container} wird nicht fertig")


def hochladen(ablage: dict, marke: str, ordner: Path) -> str:
    """Kopiert den Beitragsordner auf die öffentliche Ablage, gibt die Basis-URL zurück."""
    if ablage.get("art") == "github":
        # Lokaler Klon eines öffentlichen Repos, Bilder über raw.githubusercontent.com abrufbar
        klon = Path(ablage["klon"]).expanduser()
        ziel = klon / marke / ordner.name
        ziel.mkdir(parents=True, exist_ok=True)
        for f in ordner.glob("*.jpg"):
            subprocess.run(["cp", str(f), str(ziel / f.name)], check=True)
        subprocess.run(["git", "-C", str(klon), "add", "-A"], check=True)
        subprocess.run(["git", "-C", str(klon), "commit", "-q", "-m", f"{marke} {ordner.name}"], check=False)
        subprocess.run(["git", "-C", str(klon), "push", "-q"], check=True, timeout=300)
        time.sleep(20)  # bis raw.githubusercontent.com die Dateien ausliefert
        return f"https://raw.githubusercontent.com/{ablage['repo']}/main/{marke}/{ordner.name}"
    if ablage.get("art") != "ssh":
        raise RuntimeError("keine öffentliche Ablage eingerichtet")
    ziel = f"{ablage['ziel'].rstrip('/')}/{marke}/{ordner.name}/"
    subprocess.run(["rsync", "-a", "--include=*.jpg", "--exclude=*", f"{ordner}/", ziel], check=True, timeout=300)
    return f"{ablage['url'].rstrip('/')}/{marke}/{ordner.name}"


def posten(marke: str, b: dict, konto: dict, ablage: dict) -> dict:
    global API
    API = API_FACEBOOK if konto.get("api") == "facebook" else API_INSTAGRAM
    if API == API_INSTAGRAM:
        try:
            schluessel_verlaengern(marke)
        except Exception as e:
            log(f"{marke}: Verlängern fehlgeschlagen ({e})")
    token = schluessel(marke)
    uid = konto["ig_user_id"]
    ordner = HIER / "beitraege" / marke / social.name(b)
    basis = hochladen(ablage, marke, ordner)
    caption = (ordner / "caption.txt").read_text(encoding="utf-8").strip()
    alt = (ordner / "alt.txt").read_text(encoding="utf-8").strip()
    folien = sorted(p.name for p in ordner.glob("[0-9][0-9].jpg"))
    if len(folien) > 1:
        kinder = []
        for f in folien:
            c = graph(f"{uid}/media", token, {"image_url": f"{basis}/{f}", "is_carousel_item": "true",
                                               "alt_text": alt if f == "01.jpg" else ""})
            kinder.append(c["id"])
        for c in kinder:
            warten_fertig(c, token)
        haupt = graph(f"{uid}/media", token, {"media_type": "CAROUSEL", "children": ",".join(kinder),
                                              "caption": caption})
    else:
        haupt = graph(f"{uid}/media", token, {"image_url": f"{basis}/01.jpg", "caption": caption,
                                              "alt_text": alt})
    warten_fertig(haupt["id"], token)
    beitrag = graph(f"{uid}/media_publish", token, {"creation_id": haupt["id"]})
    story = graph(f"{uid}/media", token, {"image_url": f"{basis}/story.jpg", "media_type": "STORIES"})
    warten_fertig(story["id"], token)
    story_id = graph(f"{uid}/media_publish", token, {"creation_id": story["id"]})
    return {"zeit": time.strftime("%Y-%m-%d %H:%M"), "beitrag": beitrag.get("id"), "story": story_id.get("id")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--datum", default=date.today().isoformat())
    a = ap.parse_args()
    konten = json.loads(KONTEN.read_text()) if KONTEN.exists() else {}
    stand = json.loads(STAND.read_text()) if STAND.exists() else {}
    heute = a.datum
    for marke in social.MARKEN:
        for b in social.plan(marke):
            if b["datum"] != heute:
                continue
            schluesselname = f"{marke}/{social.name(b)}"
            eintrag = stand.get(schluesselname, {})
            if eintrag.get("gepostet"):
                continue
            fertig = (HIER / "beitraege" / marke / social.name(b) / "01.jpg").exists()
            konto = konten.get(marke, {})
            bereit = fertig and konto.get("aktiv") and konto.get("ig_user_id") and konten.get("ablage")
            if a.trocken or not bereit:
                grund = "Probe" if a.trocken else ("Bild fehlt" if not fertig else "Konto oder Ablage nicht eingerichtet")
                log(f"{marke} {b['datum']} „{b['titel']}“: nicht gepostet ({grund})")
                continue
            try:
                ergebnis = posten(marke, b, konto, konten["ablage"])
                stand.setdefault(schluesselname, {})["gepostet"] = ergebnis
                STAND.write_text(json.dumps(stand, ensure_ascii=False, indent=1))
                log(f"{marke} {b['datum']} gepostet: {ergebnis}")
            except Exception as e:
                log(f"{marke} {b['datum']} FEHLER: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
