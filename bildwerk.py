#!/usr/bin/env python3
"""Bildwerk: Motivlisten je Produkt -> lokales ComfyUI -> fertige Webbilder.

Aufruf:
  python3 bildwerk.py motive/beckenbuch.json            # erzeugen + zuschneiden
  python3 bildwerk.py motive/beckenbuch.json --trocken  # nur zeigen, was passieren würde
  python3 bildwerk.py motive/beckenbuch.json --nur-zuschnitt  # vorhandene Rohbilder neu zuschneiden

Rohbilder:  ausgabe/<produkt>/roh/<motiv>_<n>.png
Webbilder:  ausgabe/<produkt>/web/<motiv>_<n>_<format>.webp
Protokoll:  ausgabe/<produkt>/protokoll.jsonl
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
import zlib
from pathlib import Path

from PIL import Image

HIER = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:8188"
COMFY_OUT = Path.home() / "ComfyUI" / "output"
CKPT = "lustifySDXLNSFW_endgame.safetensors"  # Qualität am 11.11.2026 von Tim abgenommen

# Gilt immer, kann je Motivdatei nur ergänzt werden.
NEG = (
    "nsfw, nude, naked, cleavage, lingerie, erotic, sexy, child, underage, "
    "celebrity, famous person, "
    "anime, manga, cartoon, illustration, drawing, 3d render, cgi, plastic skin, "
    "deformed hands, extra fingers, extra limbs, watermark, text, logo, letters, "
    "signature, blurry, lowres, oversaturated"
)
VORSATZ = "raw photo, photorealistic, "

# Zielformate: (Breite, Höhe, Ausrichtung des Rohbilds)
FORMATE = {
    # Web
    "hero": (1600, 900, "quer"),
    "og": (1200, 630, "quer"),          # auch Facebook-/LinkedIn-Linkvorschau
    "artikel": (1200, 800, "quer"),
    # Instagram
    "insta-feed": (1080, 1350, "hoch"),  # 4:5, nimmt im Feed am meisten Platz ein
    "insta-quadrat": (1080, 1080, "quadrat"),
    "insta-story": (1080, 1920, "story"),  # 9:16, auch Reel-Cover, TikTok, Shorts
    # Sonstige
    "pinterest": (1000, 1500, "hoch"),  # 2:3
}
ROH = {"quer": (1216, 832), "hoch": (896, 1152), "quadrat": (1024, 1024), "story": (768, 1344)}


def api(path: str, data: dict | None = None, timeout: int = 30):
    if data is None:
        req = urllib.request.Request(BASE + path)
    else:
        req = urllib.request.Request(
            BASE + path, data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
        )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return json.loads(raw) if raw else None


def graph(text: str, neg: str, seed: int, w: int, h: int, steps: int, cfg: float,
          prefix: str = "bildwerk/tmp") -> dict:
    return {
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": CKPT}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": w, "height": h, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": text, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": neg, "clip": ["4", 1]}},
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "dpmpp_2m",
            "scheduler": "karras", "denoise": 1.0, "model": ["4", 0],
            "positive": ["6", 0], "negative": ["7", 0], "latent_image": ["5", 0]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": prefix, "images": ["8", 0]}},
    }


def erzeuge(text: str, neg: str, seed: int, w: int, h: int, steps: int, cfg: float,
            prefix: str = "bildwerk/tmp") -> Path:
    out = api("/prompt", {"prompt": graph(text, neg, seed, w, h, steps, cfg, prefix)})
    if out.get("node_errors"):
        raise RuntimeError(f"ComfyUI: {out['node_errors']}")
    pid = out["prompt_id"]
    t0 = time.time()
    while time.time() - t0 < 900:
        time.sleep(2)
        hist = api(f"/history/{pid}") or {}
        if pid not in hist:
            continue
        eintrag = hist[pid]
        bilder = eintrag.get("outputs", {}).get("9", {}).get("images", [])
        if bilder:
            b = bilder[0]
            return COMFY_OUT / b.get("subfolder", "") / b["filename"]
        if eintrag.get("status", {}).get("status_str") == "error":
            raise RuntimeError(json.dumps(eintrag["status"])[:500])
    raise TimeoutError("kein Bild nach 15 Minuten")


def zuschnitt(roh: Path, ziel: Path, breite: int, hoehe: int) -> None:
    """Mittig auf Seitenverhältnis zuschneiden, dann skalieren, als WebP speichern."""
    with Image.open(roh) as im:
        im = im.convert("RGB")
        w, h = im.size
        soll = breite / hoehe
        if w / h > soll:
            neu_w = round(h * soll)
            links = (w - neu_w) // 2
            im = im.crop((links, 0, links + neu_w, h))
        else:
            neu_h = round(w / soll)
            oben = (h - neu_h) // 2
            im = im.crop((0, oben, w, oben + neu_h))
        im = im.resize((breite, hoehe), Image.LANCZOS)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        im.save(ziel, "WEBP", quality=82, method=6)


def server_da() -> bool:
    try:
        api("/system_stats", timeout=3)
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("motivdatei", type=Path)
    ap.add_argument("--trocken", action="store_true")
    ap.add_argument("--nur-zuschnitt", action="store_true")
    a = ap.parse_args()

    spec = json.loads(a.motivdatei.read_text(encoding="utf-8"))
    produkt = spec["produkt"]
    stil = spec.get("stil", "")
    neg = NEG + (", " + spec["neg_zusatz"] if spec.get("neg_zusatz") else "")
    steps = spec.get("steps", 28)
    cfg = spec.get("cfg", 5.0)
    basis = HIER / "ausgabe" / produkt
    protokoll = basis / "protokoll.jsonl"

    auftraege = []
    for m in spec["motive"]:
        formate = m.get("formate", ["og"])
        for f in formate:
            if f not in FORMATE:
                sys.exit(f"Unbekanntes Format {f!r} bei {m['name']}; erlaubt: {', '.join(FORMATE)}")
        # Ein Rohbild je benötigter Ausrichtung
        for ausr in sorted({FORMATE[f][2] for f in formate}):
            for n in range(1, m.get("varianten", 2) + 1):
                auftraege.append((m, ausr, n, [f for f in formate if FORMATE[f][2] == ausr]))

    print(f"{produkt}: {len(auftraege)} Rohbilder, geschätzt {len(auftraege) * 100 // 60} Minuten")
    if a.trocken:
        for m, ausr, n, fs in auftraege:
            print(f"  {m['name']}_{ausr}_{n}: {ROH[ausr][0]}x{ROH[ausr][1]} -> {', '.join(fs)}")
        return 0
    if not a.nur_zuschnitt and not server_da():
        sys.exit("ComfyUI läuft nicht. Start: zsh ~/ComfyUI/start-nsfw.sh")

    fehler = 0
    for m, ausr, n, fs in auftraege:
        name = f"{m['name']}_{ausr}_{n}"
        roh = basis / "roh" / f"{name}.png"
        if not a.nur_zuschnitt and not roh.exists():
            text = VORSATZ + m["prompt"] + (", " + stil if stil else "")
            seed = spec.get("seed", 20261111) + n * 1000 + zlib.crc32(m["name"].encode()) % 997
            t0 = time.time()
            try:
                datei = erzeuge(text, neg, seed, *ROH[ausr], steps, cfg)
            except Exception as e:  # ein Fehlbild hält den Stapel nicht an
                fehler += 1
                print(f"  FEHLER {name}: {e}")
                continue
            roh.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(datei), roh)
            with protokoll.open("a", encoding="utf-8") as p:
                p.write(json.dumps({"zeit": time.strftime("%Y-%m-%d %H:%M:%S"), "bild": name,
                                    "seed": seed, "ckpt": CKPT, "prompt": text,
                                    "sekunden": round(time.time() - t0)}, ensure_ascii=False) + "\n")
            print(f"  {name}: {time.time() - t0:.0f} s")
        if roh.exists():
            for f in fs:
                bw, bh, _ = FORMATE[f]
                zuschnitt(roh, basis / "web" / f"{name}_{f}.webp", bw, bh)

    # Modell entladen, damit der Mac nicht in den Auslagerungsspeicher läuft
    if not a.nur_zuschnitt:
        try:
            api("/free", {"unload_models": True, "free_memory": True})
        except Exception:
            pass
    print(f"fertig: {basis / 'web'}" + (f" ({fehler} Fehler)" if fehler else ""))
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
