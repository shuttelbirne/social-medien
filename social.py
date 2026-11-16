#!/usr/bin/env python3
"""Social: Jahresplan je Marke -> fertige Instagram-Beiträge.

  python3 social.py pruefen <marke>        Plan prüfen (Pflichtfelder, Längen, Daten)
  python3 social.py bilder  <marke> [max]  fehlende Titelbilder über ComfyUI erzeugen (langsam)
  python3 social.py render  <marke>        Folien, Story, Caption, Alt-Text, Prüfbericht (schnell)
  python3 social.py stand                  Übersicht aller Marken
  python3 social.py verwerfen <marke> <datum-slug>  Fehlbild verwerfen, entsteht neu mit anderem Seed

Plan:     social/plaene/<marke>/*.json  (Liste von Beiträgen, Schema in social/PLAN-SCHEMA.md)
Rohbild:  social/roh/<marke>/<datum>-<slug>.png
Ergebnis: beitraege/<marke>/<datum>-<slug>/
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import time
import zlib
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
import bildwerk as bw  # noqa: E402

SOC = HIER / "social"
FONTS = HIER / "fonts"
MARKEN = json.loads((SOC / "marken.json").read_text(encoding="utf-8"))
SKILLS = Path.home() / ".claude" / "skills"
W, H = 1080, 1350          # Feed 4:5
SW, SH = 1080, 1920        # Story 9:16
RAND = 96
FORMATE = {"karussell", "einzelbild"}


# ---------------------------------------------------------------- Plan

def plan(marke: str) -> list[dict]:
    beitraege = []
    for f in sorted((SOC / "plaene" / marke).glob("q[1-4].json")):
        daten = json.loads(f.read_text(encoding="utf-8"))
        for b in daten:
            b["_datei"] = f.name
            beitraege.append(b)
    beitraege.sort(key=lambda b: b.get("datum", ""))
    return beitraege


def name(b: dict) -> str:
    slug = re.sub(r"[^a-z0-9-]+", "-", b.get("slug", "beitrag").lower()).strip("-")[:50]
    return f"{b['datum']}-{slug}"


def pruefe_eintrag(b: dict, wo: str = "") -> list[str]:
    """Regeln für einen einzelnen Beitrag (ohne Dublettenprüfung)."""
    fehler = []
    if True:
        for feld in ("datum", "slug", "format", "thema", "titel", "bild_prompt", "caption", "alt", "story"):
            if not b.get(feld):
                fehler.append(f"{wo} Feld fehlt: {feld}")
        try:
            date.fromisoformat(b.get("datum", ""))
        except ValueError:
            fehler.append(f"{wo} Datum ungültig")
        if b.get("format") not in FORMATE:
            fehler.append(f"{wo} Format {b.get('format')!r}")
        if b.get("format") == "karussell" and not (3 <= len(b.get("folien", [])) <= 7):
            fehler.append(f"{wo} Karussell braucht 3 bis 7 Folien, hat {len(b.get('folien', []))}")
        if len(b.get("titel", "")) > 70:
            fehler.append(f"{wo} Titel zu lang ({len(b['titel'])} > 70)")
        if len(b.get("caption", "")) > 2200:
            fehler.append(f"{wo} Caption zu lang")
        if b.get("caption", "").count("#") > 5:
            fehler.append(f"{wo} mehr als 5 Hashtags")
        if re.search(r"https?://|www\.", b.get("caption", "")):
            fehler.append(f"{wo} Link in der Caption")
        if "—" in b.get("caption", "") or any("—" in (f.get("text", "") + f.get("ueberschrift", "")) for f in b.get("folien", [])):
            fehler.append(f"{wo} Gedankenstrich (—) im Text")
        alles = " ".join([b.get("titel", ""), b.get("untertitel", ""), b.get("caption", ""),
                          json.dumps(b.get("folien", []), ensure_ascii=False),
                          json.dumps(b.get("schluss", {}), ensure_ascii=False),
                          json.dumps(b.get("story", {}), ensure_ascii=False)])
        if re.search(r"\baber\b", alles, re.IGNORECASE):
            fehler.append(f"{wo} Wort „aber“ (Tims Regel: nie „aber“)")
        if ";" in alles:
            fehler.append(f"{wo} Semikolon (Tims Regel)")
    return fehler


def pruefe_plan(marke: str) -> list[str]:
    fehler, gesehen = [], set()
    for b in plan(marke):
        wo = f"{b.get('_datei')}:{b.get('datum')}"
        fehler += pruefe_eintrag(b, wo)
        n = name(b)
        if n in gesehen:
            fehler.append(f"{wo} doppelt: {n}")
        gesehen.add(n)
    return fehler


# ---------------------------------------------------------------- Bilder

def rohpfad(marke: str, b: dict) -> Path:
    return SOC / "roh" / marke / f"{name(b)}.png"


def bilder(marke: str, maximal: int | None = None) -> int:
    m = MARKEN[marke]
    offen = [b for b in plan(marke) if not rohpfad(marke, b).exists()]
    if maximal:
        offen = offen[:maximal]
    if not offen:
        print(f"{marke}: alle Titelbilder vorhanden")
        return 0
    if not bw.server_da():
        sys.exit("ComfyUI läuft nicht. Start: zsh ~/ComfyUI/start-nsfw.sh")
    neg = bw.NEG + ", " + m["neg_zusatz"]
    print(f"{marke}: {len(offen)} Titelbilder, geschätzt {len(offen) * 95 // 60} Minuten", flush=True)
    fehler = 0
    for i, b in enumerate(offen, 1):
        ziel = rohpfad(marke, b)
        text = bw.VORSATZ + b["bild_prompt"] + ", " + m["bild_stil"]
        versuch = len(list((SOC / "roh" / marke / "verworfen").glob(f"{name(b)}*.png")))
        seed = 20261111 + zlib.crc32(name(b).encode()) % 100000 + versuch * 7919
        t0 = time.time()
        try:
            datei = bw.erzeuge(text, neg, seed, *bw.ROH["hoch"], 28, 5.0, prefix=f"social/{marke}/{name(b)}")
            ziel.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(datei), ziel)
        except Exception as e:
            fehler += 1
            print(f"  FEHLER {name(b)}: {e}", flush=True)
            continue
        with (SOC / "roh" / marke / "protokoll.jsonl").open("a", encoding="utf-8") as p:
            p.write(json.dumps({"zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "bild": name(b), "seed": seed,
                                "ckpt": bw.CKPT, "prompt": text}, ensure_ascii=False) + "\n")
        print(f"  [{i}/{len(offen)}] {name(b)} {time.time() - t0:.0f} s", flush=True)
        if i % 6 == 0:  # Speicher regelmäßig freigeben, sonst wächst der Auslagerungsspeicher
            try:
                bw.api("/free", {"unload_models": True, "free_memory": True})
            except Exception:
                pass
    try:
        bw.api("/free", {"unload_models": True, "free_memory": True})
    except Exception:
        pass
    return fehler


# ---------------------------------------------------------------- Zeichnen

def farbe(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def schrift(spec: list, groesse: int) -> ImageFont.FreeTypeFont:
    datei, gewicht = spec
    f = ImageFont.truetype(str(FONTS / datei), groesse)
    if gewicht:
        try:
            f.set_variation_by_axes([gewicht])
        except Exception:
            pass
    return f


def umbruch(text: str, f: ImageFont.FreeTypeFont, breite: int) -> list[str]:
    zeilen = []
    for absatz in text.split("\n"):
        aktuell = ""
        for wort in absatz.split():
            probe = (aktuell + " " + wort).strip()
            if f.getlength(probe) <= breite:
                aktuell = probe
            else:
                if aktuell:
                    zeilen.append(aktuell)
                aktuell = wort
        zeilen.append(aktuell)
    return zeilen


def textblock(d: ImageDraw.ImageDraw, text: str, spec: list, start: int, mini: int, breite: int,
              hoehe: int, x: int, y: int, fill, zeilenabstand: float = 1.25, ausrichtung: str = "links") -> int:
    """Größte Schrift zwischen start und mini, die in breite x hoehe passt. Gibt die genutzte Höhe zurück.

    Auch die Breite zählt: Ein langes Einzelwort (z. B. „Futtermengen-Rechner“) lief am 12.11.2026
    bei 92 px rechts aus der Folie. Dann wird die Schrift ebenfalls kleiner.
    """
    groesse = start
    while True:
        f = schrift(spec, groesse)
        zeilen = umbruch(text, f, breite)
        zh = int(groesse * zeilenabstand)
        breit = max((f.getlength(z) for z in zeilen), default=0)
        if (len(zeilen) * zh <= hoehe and breit <= breite) or groesse <= mini:
            break
        groesse -= 2
    for i, z in enumerate(zeilen):
        zx = x if ausrichtung == "links" else x + (breite - f.getlength(z)) / 2
        d.text((zx, y + i * zh), z, font=f, fill=fill)
    return len(zeilen) * zh


def titelfolie(roh: Path, m: dict, titel: str, untertitel: str, seiten: int | None) -> Image.Image:
    im = Image.open(roh).convert("RGB")
    im = beschnitt(im, W, H)
    # Verlauf unten für lesbaren Text
    verlauf = Image.new("L", (1, H))
    for yy in range(H):
        verlauf.putpixel((0, yy), int(min(1.0, max(0, (yy - H * 0.32) / (H * 0.42))) ** 1.1 * 225))
    dunkel = Image.new("RGB", (W, H), farbe(m["farben"]["dunkel"]))
    im = Image.composite(dunkel, im, verlauf.resize((W, H)))
    d = ImageDraw.Draw(im)
    weiss = (255, 255, 255)
    y_unten = H - RAND - 40
    h_titel = 330
    textblock(d, titel, m["schrift_titel"], 92, 54, W - 2 * RAND, h_titel, RAND, y_unten - h_titel - 70, weiss, 1.08)
    if untertitel:
        f = schrift(m["schrift_text"], 34)
        hell = max((m["farben"]["zweit"], m["farben"]["akzent"]),
                   key=lambda h: sum(c * w for c, w in zip(farbe(h), (0.299, 0.587, 0.114))))
        d.text((RAND, y_unten - 40), untertitel, font=f, fill=farbe(hell))
    f = schrift(m["schrift_text"], 26)
    d.text((RAND, H - RAND + 10), m["domain"], font=f, fill=(235, 235, 235))
    if seiten:
        hinweis = "wischen »"
        d.text((W - RAND - f.getlength(hinweis), H - RAND + 10), hinweis, font=f, fill=(235, 235, 235))
    return im


def textfolie(m: dict, nr: int, gesamt: int, ueberschrift: str, text: str, schluss: bool = False) -> Image.Image:
    fa = m["farben"]
    grund = farbe(fa["akzent"] if schluss else fa["grund"])
    vorder = farbe("#ffffff" if schluss or _dunkel(fa["grund"]) else fa["text"])
    im = Image.new("RGB", (W, H), grund)
    d = ImageDraw.Draw(im)
    f = schrift(m["schrift_text"], 28)
    d.text((RAND, RAND), f"{nr}/{gesamt}", font=f, fill=vorder)
    d.rectangle((RAND, RAND + 70, RAND + 120, RAND + 78), fill=farbe(fa["zweit"] if not schluss else "#ffffff"))
    # erst messen (unsichtbar), dann senkrecht mittig setzen
    probe = ImageDraw.Draw(Image.new("RGB", (W, H)))
    oben = RAND + 150
    h1 = textblock(probe, ueberschrift, m["schrift_titel"], 76, 46, W - 2 * RAND, 300, RAND, 0, vorder, 1.1)
    rest = H - oben - h1 - 50 - RAND - 60
    h2 = textblock(probe, text, m["schrift_text"], 44, 30, W - 2 * RAND, rest, RAND, 0, vorder, 1.42)
    y = max(oben, (H - (h1 + 50 + h2)) // 2)
    textblock(d, ueberschrift, m["schrift_titel"], 76, 46, W - 2 * RAND, 300, RAND, y, vorder, 1.1)
    textblock(d, text, m["schrift_text"], 44, 30, W - 2 * RAND, rest, RAND, y + h1 + 50, vorder, 1.42)
    f = schrift(m["schrift_text"], 26)
    d.text((RAND, H - RAND + 10), m["domain"], font=f, fill=vorder)
    return im


def story(roh: Path, m: dict, text: str, nachsatz: str) -> Image.Image:
    im = Image.open(roh).convert("RGB")
    im = beschnitt(im, SW, SH).filter(ImageFilter.GaussianBlur(18))
    im = Image.blend(im, Image.new("RGB", (SW, SH), farbe(m["farben"]["dunkel"])), 0.45)
    # Karte mittig, oben und unten 250 px frei (Instagram-Einblendungen)
    karte = Image.open(roh).convert("RGB")
    karte = beschnitt(karte, 840, 840)
    im.paste(karte, (120, 330))
    d = ImageDraw.Draw(im)
    textblock(d, text, m["schrift_titel"], 70, 44, SW - 240, 420, 120, 1210, (255, 255, 255), 1.12, "mitte")
    if nachsatz:
        hell = max((m["farben"]["zweit"], m["farben"]["akzent"]),
                   key=lambda h: sum(c * w for c, w in zip(farbe(h), (0.299, 0.587, 0.114))))
        textblock(d, nachsatz, m["schrift_text"], 34, 28, SW - 240, 120, 120, 1620, farbe(hell), 1.3, "mitte")
    return im


def _dunkel(h: str) -> bool:
    r, g, b = farbe(h)
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def beschnitt(im: Image.Image, bw_: int, bh: int) -> Image.Image:
    w, h = im.size
    soll = bw_ / bh
    if w / h > soll:
        nw = round(h * soll)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = round(w / soll)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    return im.resize((bw_, bh), Image.LANCZOS)


# ---------------------------------------------------------------- Render

def lint(caption: Path, suchbegriffe: list[str]) -> str:
    out = []
    try:
        r = subprocess.run([sys.executable, str(SKILLS / "ig-caption" / "caption.py"), str(caption),
                            "--keywords", ",".join(suchbegriffe)], capture_output=True, text=True, timeout=60)
        out.append(r.stdout.strip())
        r = subprocess.run([sys.executable, str(SKILLS / "ig-human" / "detect.py"), str(caption)],
                           capture_output=True, text=True, timeout=60)
        fp = [z for z in r.stdout.splitlines() if "FINGERPRINT" in z or "invisible" in z]
        out.append("ig-human (nur FINGERPRINT gilt auf Deutsch): " + " | ".join(z.strip() for z in fp))
    except Exception as e:
        out.append(f"Prüfung fehlgeschlagen: {e}")
    return "\n\n".join(out)


def render(marke: str) -> tuple[int, int]:
    m = MARKEN[marke]
    fertig = fehlt = 0
    zeilen = []
    for b in plan(marke):
        roh = rohpfad(marke, b)
        ordner = HIER / "beitraege" / marke / name(b)
        zeilen.append([b["datum"], b["format"], b["thema"], b["titel"], "ja" if roh.exists() else "Bild fehlt",
                       str(ordner.relative_to(HIER))])
        if not roh.exists():
            fehlt += 1
            continue
        ordner.mkdir(parents=True, exist_ok=True)
        for alt in ordner.glob("*.jpg"):
            alt.unlink()
        if b["format"] == "karussell":
            folien = b["folien"]
            gesamt = len(folien) + 2
            titelfolie(roh, m, b["titel"], b.get("untertitel", ""), gesamt).save(ordner / "01.jpg", quality=90)
            for i, f in enumerate(folien, 2):
                textfolie(m, i, gesamt, f["ueberschrift"], f["text"]).save(ordner / f"{i:02d}.jpg", quality=90)
            s = b.get("schluss") or {"ueberschrift": "Mehr dazu", "text": "Link im Profil"}
            textfolie(m, gesamt, gesamt, s["ueberschrift"], s["text"], schluss=True).save(ordner / f"{gesamt:02d}.jpg", quality=90)
        else:
            titelfolie(roh, m, b["titel"], b.get("untertitel", ""), None).save(ordner / "01.jpg", quality=90)
        st = b["story"]
        story(roh, m, st.get("text", b["titel"]), st.get("nachsatz", "")).save(ordner / "story.jpg", quality=90)
        (ordner / "caption.txt").write_text(b["caption"].strip() + "\n", encoding="utf-8")
        (ordner / "alt.txt").write_text(b["alt"].strip() + "\n", encoding="utf-8")
        quiz = ("\nHinweis: Beim Quiz steht die richtige Antwort zuerst. In der App die Reihenfolge mischen "
                "und die richtige markieren.\n") if "quiz" in st.get("sticker", "").lower() else ""
        (ordner / "story.txt").write_text(
            f"Story-Text: {st.get('text', '')}\nSticker: {st.get('sticker', '-')}\n"
            f"Platz für den Sticker: unteres Drittel (unter dem Text)\n{quiz}", encoding="utf-8")
        (ordner / "pruefung.txt").write_text(lint(ordner / "caption.txt", b.get("suchbegriffe", [])) + "\n",
                                             encoding="utf-8")
        fertig += 1
    ziel = HIER / "beitraege" / marke
    ziel.mkdir(parents=True, exist_ok=True)
    with (ziel / "kalender.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["Datum", "Format", "Thema", "Titel", "Bild", "Ordner"])
        w.writerows(zeilen)
    print(f"{marke}: {fertig} Beiträge gerendert, {fehlt} warten auf ihr Titelbild")
    return fertig, fehlt


def stand() -> None:
    for marke in MARKEN:
        p = plan(marke)
        roh = sum(1 for b in p if rohpfad(marke, b).exists())
        ordner = HIER / "beitraege" / marke
        fertig = sum(1 for b in p if (ordner / name(b) / "caption.txt").exists())
        bis = p[-1]["datum"] if p else "-"
        print(f"{marke:18s} geplant {len(p):4d} (bis {bis})  Titelbilder {roh:4d}  fertig {fertig:4d}")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    befehl = sys.argv[1]
    if befehl == "stand":
        stand()
        return 0
    marke = sys.argv[2]
    if marke not in MARKEN:
        sys.exit(f"Unbekannte Marke {marke}; bekannt: {', '.join(MARKEN)}")
    if befehl == "pruefen":
        fehler = pruefe_plan(marke)
        print("\n".join(fehler) or f"{marke}: Plan ohne Fehler ({len(plan(marke))} Beiträge)")
        return 1 if fehler else 0
    if befehl == "bilder":
        return 1 if bilder(marke, int(sys.argv[3]) if len(sys.argv) > 3 else None) else 0
    if befehl == "render":
        render(marke)
        return 0
    if befehl == "verwerfen":  # python3 social.py verwerfen <marke> <datum-slug> [...]
        ablage = SOC / "roh" / marke / "verworfen"
        ablage.mkdir(parents=True, exist_ok=True)
        for n in sys.argv[3:]:
            roh = SOC / "roh" / marke / f"{n}.png"
            if roh.exists():
                nr = len(list(ablage.glob(f"{n}*.png"))) + 1
                shutil.move(str(roh), ablage / f"{n}-{nr}.png")
                shutil.rmtree(HIER / "beitraege" / marke / n, ignore_errors=True)
                print(f"verworfen: {n} (nächster Versuch mit neuem Seed)")
            else:
                print(f"nicht gefunden: {n}")
        return 0
    sys.exit(f"Unbekannter Befehl {befehl}")


if __name__ == "__main__":
    sys.exit(main())
