#!/usr/bin/env python3
"""Social-Tagesloop: produziert jeden Tag die Instagram-Beiträge der nächsten Tage.

Sparsam: keine KI-Texte, nur lokale Bild-KI (ComfyUI). Optional eine kurze
Sichtprüfung je neuem Bild mit Haiku (rund 1.500 Tokens je Bild).

  python3 tagesloop.py                 # Beiträge der nächsten VORLAUF Tage produzieren
  python3 tagesloop.py --trocken       # nur zeigen, was zu tun wäre
  python3 tagesloop.py --ohne-pruefung # ohne Haiku-Sichtprüfung

Ablauf je Lauf:
1. Beiträge mit Datum heute bis heute+VORLAUF ohne Titelbild suchen.
2. ComfyUI bei Bedarf starten, warten bis genug Speicher frei ist.
3. Bild erzeugen, optional prüfen (bei Fehler neu würfeln, höchstens 3 Versuche).
4. Rendern, ZIP packen, Stand in social/stand.json schreiben.
5. ComfyUI wieder beenden, wenn der Lauf es gestartet hat.
Protokoll: social/tagesloop.log
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import social  # noqa: E402

VORLAUF = 7          # Tage im Voraus, damit Fehltage aufgeholt werden
MAX_VERSUCHE = 3
WARTEN_MAX = 4 * 3600  # höchstens 4 Stunden auf freien Speicher warten
LOG = HIER / "social" / "tagesloop.log"
STAND = HIER / "social" / "stand.json"
SPERRE = HIER / "social" / "tagesloop.pid"
CLAUDE = Path.home() / ".local" / "bin" / "claude"


def log(text: str) -> None:
    zeile = time.strftime("%Y-%m-%d %H:%M:%S ") + text
    print(zeile, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(zeile + "\n")


def speicher_frei() -> tuple[bool, str]:
    try:
        out = subprocess.run(["memory_pressure"], capture_output=True, text=True, timeout=30).stdout
        frei = int(out.strip().splitlines()[-1].split(":")[-1].strip().rstrip("%"))
    except Exception:
        frei = 100
    try:
        ollama = subprocess.run(["ollama", "ps"], capture_output=True, text=True, timeout=30).stdout
        geladen = [z.split()[0] for z in ollama.strip().splitlines()[1:] if z.strip()]
    except Exception:
        geladen = []
    if geladen:
        return False, f"Ollama hält {', '.join(geladen)}"
    if frei < 35:
        return False, f"nur {frei} % Arbeitsspeicher frei"
    if shutil.disk_usage(Path.home()).free < 6 * 1024 ** 3:
        return False, "weniger als 6 GB Platte frei"
    return True, ""


def comfy_starten() -> subprocess.Popen | None:
    """Startet ComfyUI, falls es nicht läuft. Gibt den Prozess zurück, wenn wir ihn gestartet haben."""
    if social.bw.server_da():
        return None
    p = subprocess.Popen(["zsh", str(Path.home() / "ComfyUI" / "start-nsfw.sh")],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(120):
        time.sleep(2)
        if social.bw.server_da():
            return p
    raise RuntimeError("ComfyUI startet nicht")


def sichtpruefung(marke: str, bild: Path, b: dict) -> tuple[bool, str]:
    """Haiku sieht das Bild an. Rückgabe (ok, grund). Bei technischem Fehler gilt das Bild als ok."""
    frage = (
        f"Sieh dir das Bild {bild} an (Read-Werkzeug). Es soll ein Instagram-Titelbild für die Marke "
        f"{social.MARKEN[marke]['name']} sein. Gewünschtes Motiv: {b['bild_prompt']}\n"
        "Prüfe nur diese Fehler: lesbare oder fantasievolle Schrift/Zahlen/Etiketten im Bild, verformte Hände "
        "oder Körper, falsche Tieranatomie, erkennbares Gesicht in Großaufnahme, Freizügiges, Gewalt, Motiv "
        "passt gar nicht. Antworte NUR mit JSON: {\"ok\": true} oder {\"ok\": false, \"grund\": \"…\"}"
    )
    try:
        r = subprocess.run([str(CLAUDE), "-p", frage, "--model", "haiku", "--allowedTools", "Read",
                            "--output-format", "text"], capture_output=True, text=True, timeout=300,
                           env={**os.environ, "ANTHROPIC_API_KEY": ""})
        text = r.stdout.strip()
        start, ende = text.find("{"), text.rfind("}")
        urteil = json.loads(text[start:ende + 1])
        return bool(urteil.get("ok")), str(urteil.get("grund", ""))
    except Exception as e:
        log(f"  Sichtprüfung technisch fehlgeschlagen ({e}), Bild gilt als ok")
        return True, ""


def zip_packen(marke: str, b: dict) -> None:
    ordner = HIER / "beitraege" / marke / social.name(b)
    if not (ordner / "01.jpg").exists():
        return
    ziel = ordner / f"{marke}-{social.name(b)}.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(ordner.iterdir()):
            if f.suffix in (".jpg", ".txt"):
                z.write(f, f.name)


def stand_schreiben() -> None:
    stand = {}
    for marke in social.MARKEN:
        for b in social.plan(marke):
            n = social.name(b)
            fertig = (HIER / "beitraege" / marke / n / "01.jpg").exists()
            stand[f"{marke}/{n}"] = {"datum": b["datum"], "marke": marke, "format": b["format"],
                                     "fertig": fertig}
    alt = json.loads(STAND.read_text()) if STAND.exists() else {}
    for k, v in stand.items():  # gepostet-Vermerke aus dem Poster erhalten
        if k in alt and "gepostet" in alt[k]:
            v["gepostet"] = alt[k]["gepostet"]
    STAND.write_text(json.dumps(stand, ensure_ascii=False, indent=1))


def faellig(heute: date) -> list[tuple[str, dict]]:
    bis = (heute + timedelta(days=VORLAUF)).isoformat()
    liste = []
    for marke in social.MARKEN:
        for b in social.plan(marke):
            if heute.isoformat() <= b["datum"] <= bis and not social.rohpfad(marke, b).exists():
                liste.append((marke, b))
    return sorted(liste, key=lambda x: x[1]["datum"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--ohne-pruefung", action="store_true")
    a = ap.parse_args()

    heute = date.today()
    if not a.trocken:
        # 1. Tagestrends holen (kostenlos), 2. Beiträge für heute und morgen anpassen (Sonnet, je Beitrag ein Aufruf)
        subprocess.run([sys.executable, str(HIER / "trends.py")], capture_output=True, timeout=120)
        import anpassen
        tage = {heute.isoformat(), (heute + timedelta(days=1)).isoformat()}
        for marke in social.MARKEN:
            for b in social.plan(marke):
                if b["datum"] in tage and not social.rohpfad(marke, b).exists() and not b.get("angepasst"):
                    log(f"  Feinschliff {marke} {b['datum']}: {anpassen.anpassen(marke, b['datum'])}")
    offen = faellig(heute)
    log(f"Lauf {heute}: {len(offen)} Beiträge bis {heute + timedelta(days=VORLAUF)} ohne Bild")
    if a.trocken:
        for marke, b in offen:
            print(f"  {b['datum']} {marke}: {b['titel']}")
        return 0
    if not offen:
        stand_schreiben()
        return 0

    if SPERRE.exists():
        try:
            os.kill(int(SPERRE.read_text()), 0)
            log("Ein anderer Lauf läuft noch, Ende")
            return 1
        except (ProcessLookupError, ValueError):
            pass
    SPERRE.write_text(str(os.getpid()))

    gestartet = None
    try:
        t0 = time.time()
        while True:
            ok, grund = speicher_frei()
            if ok:
                break
            if time.time() - t0 > WARTEN_MAX:
                log(f"Abbruch nach 4 Stunden Warten: {grund}")
                return 1
            log(f"Warte 10 Minuten: {grund}")
            time.sleep(600)
        gestartet = comfy_starten()

        for marke, b in offen:
            n = social.name(b)
            for versuch in range(1, MAX_VERSUCHE + 1):
                _erzeuge_einen(marke, b)
                roh = social.rohpfad(marke, b)
                if not roh.exists():
                    log(f"  {marke} {n}: Bild nicht erzeugt (Versuch {versuch})")
                    continue
                if a.ohne_pruefung:
                    break
                gut, grund = sichtpruefung(marke, roh, b)
                if gut:
                    break
                log(f"  {marke} {n}: Sichtprüfung verworfen ({grund}), Versuch {versuch}")
                subprocess.run([sys.executable, str(HIER / "social.py"), "verwerfen", marke, n],
                               capture_output=True)
            if social.rohpfad(marke, b).exists():
                log(f"  {marke} {n}: Bild fertig")
        for marke in {m for m, _ in offen}:
            social.render(marke)
        for marke, b in offen:
            zip_packen(marke, b)
        try:
            social.bw.api("/free", {"unload_models": True, "free_memory": True})
        except Exception:
            pass
    finally:
        if gestartet is not None:
            try:
                os.killpg(os.getpgid(gestartet.pid), signal.SIGTERM)
            except Exception:
                pass
        stand_schreiben()
        SPERRE.unlink(missing_ok=True)
    log("Lauf fertig")
    return 0


def _erzeuge_einen(marke: str, b: dict) -> None:
    """Erzeugt genau das Titelbild eines Beitrags (gleiche Logik wie social.bilder)."""
    m = social.MARKEN[marke]
    n = social.name(b)
    ziel = social.rohpfad(marke, b)
    versuch = len(list((social.SOC / "roh" / marke / "verworfen").glob(f"{n}*.png")))
    seed = 20261111 + social.zlib.crc32(n.encode()) % 100000 + versuch * 7919
    text = social.bw.VORSATZ + b["bild_prompt"] + ", " + m["bild_stil"]
    neg = social.bw.NEG + ", " + m["neg_zusatz"]
    try:
        datei = social.bw.erzeuge(text, neg, seed, *social.bw.ROH["hoch"], 28, 5.0,
                                  prefix=f"social/{marke}/{n}")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(datei), ziel)
        with (social.SOC / "roh" / marke / "protokoll.jsonl").open("a", encoding="utf-8") as p:
            p.write(json.dumps({"zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "bild": n, "seed": seed,
                                "ckpt": social.bw.CKPT, "prompt": text, "lauf": "tagesloop"},
                               ensure_ascii=False) + "\n")
    except Exception as e:
        log(f"  Fehler bei {marke} {n}: {e}")


if __name__ == "__main__":
    sys.exit(main())
