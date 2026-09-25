"""
services/schemi_render.py — Disegno lato server di uno schema di cantiere (PNG per il DOCX)

Riproduce ciò che si vede nell'editor: sfondo, recinzione tratteggiata, ponteggio, percorsi,
elementi ruotati con etichetta, gru con raggio d'azione, testi, più la fascia con l'avviso CAD.
"""
import io
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

from services.schemi import ELEMENTI, FORMATO_VUOTO

AVVISO = "Schema indicativo generato con SCE: va rifinito in CAD prima dell'uso definitivo."
COLORI = {"recinzione": (192, 57, 43), "ponteggio": (46, 109, 180), "percorso": (39, 174, 96),
          "gru": (142, 68, 173), "testo": (26, 58, 92)}
ORO = (200, 139, 42)


def _font(dim):
    try:
        return ImageFont.load_default(size=max(8, int(dim)))
    except TypeError:                      # Pillow senza FreeType: font bitmap
        return ImageFont.load_default()


def _tratteggio(d, a, b, colore, larghezza, pieno=18, vuoto=10):
    lung = math.dist(a, b)
    if lung == 0:
        return
    passi = int(lung // (pieno + vuoto)) + 1
    for i in range(passi):
        t0, t1 = i * (pieno + vuoto) / lung, min(1, (i * (pieno + vuoto) + pieno) / lung)
        if t0 >= 1:
            break
        d.line([(a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0),
                (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)], fill=colore, width=larghezza)


def disegna(schema: dict) -> bytes:
    W = schema.get("sfondo_w") or FORMATO_VUOTO[0]
    H = schema.get("sfondo_h") or FORMATO_VUOTO[1]
    path = schema.get("sfondo_path")
    if path and os.path.exists(path):
        base = Image.open(path).convert("RGBA").resize((W, H))
    else:
        base = Image.new("RGBA", (W, H), (255, 255, 255, 255))
        g = ImageDraw.Draw(base)
        for x in range(0, W, 50):
            g.line([(x, 0), (x, H)], fill=(227, 232, 239), width=1)
        for y in range(0, H, 50):
            g.line([(0, y), (W, y)], fill=(227, 232, 239), width=1)

    velo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dv = ImageDraw.Draw(velo)
    d = ImageDraw.Draw(base)
    tratto = max(2, int(W / 500))
    f = _font(max(12, W / 90))
    scala = json.loads(schema["scala_json"]) if schema.get("scala_json") else None
    mpp = (scala or {}).get("m_per_px")
    m2px = (lambda m: m / mpp) if mpp else (lambda m: m * W / 60)

    elementi = json.loads(schema.get("elementi_json") or "[]")
    etichette = []
    for el in elementi:
        tipo = el.get("tipo", "testo")
        c = COLORI.get(tipo, ORO)
        nome = el.get("etichetta") or ELEMENTI.get(tipo, (tipo,))[0]
        if el.get("punti"):
            pts = [tuple(p) for p in el["punti"]]
            for a, b in zip(pts, pts[1:]):
                if tipo == "recinzione":
                    _tratteggio(d, a, b, c, tratto * 2)
                else:
                    d.line([a, b], fill=c, width=tratto * (3 if tipo == "ponteggio" else 2))
            etichette.append((pts[0][0], pts[0][1] - f.size * 1.2, nome, c))
        elif tipo == "testo":
            etichette.append((el["x"], el["y"] - f.size, el.get("testo") or nome, c))
        elif tipo == "gru":
            r = m2px(float(el.get("raggio_m") or 25))
            x, y = el["x"], el["y"]
            for k in range(0, 360, 6):          # cerchio tratteggiato del raggio d'azione
                d.arc([x - r, y - r, x + r, y + r], k, k + 3, fill=c, width=tratto)
            rb = float(el.get("w", 40)) / 2
            dv.ellipse([x - rb, y - rb, x + rb, y + rb], fill=c + (90,), outline=c + (255,), width=tratto)
            etichette.append((x - rb, y - rb - f.size * 1.3, f"{nome} · R {float(el.get('raggio_m') or 25):g} m", c))
        else:
            x, y, w, h = el["x"], el["y"], float(el.get("w", 40)), float(el.get("h", 30))
            a = math.radians(float(el.get("rot", 0)))
            angoli = [(x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
                      for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))]
            dv.polygon(angoli, fill=c + (80,), outline=c + (255,), width=tratto)
            etichette.append((x - w / 2, y + h / 2 + 4, nome, (26, 58, 92)))

    base = Image.alpha_composite(base, velo)
    d = ImageDraw.Draw(base)
    for x, y, testo, c in etichette:
        bb = d.textbbox((x, y), testo, font=f)
        d.rectangle([bb[0] - 3, bb[1] - 2, bb[2] + 3, bb[3] + 2], fill=(255, 255, 255))
        d.text((x, y), testo, fill=c, font=f)

    fascia = max(40, W // 40)
    out = Image.new("RGB", (W, H + fascia), (255, 244, 214))
    out.paste(base.convert("RGB"), (0, 0))
    dt = ImageDraw.Draw(out)
    dt.text((16, H + fascia * 0.25), f"ATTENZIONE: {AVVISO}  —  {schema.get('nome', '')}",
            fill=(138, 75, 0), font=_font(fascia * 0.42))
    buf = io.BytesIO()
    out.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
