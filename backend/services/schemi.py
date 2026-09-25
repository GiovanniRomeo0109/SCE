"""
services/schemi.py — Schemi di cantiere (blocco 5)

Coordinate degli elementi: pixel dell'immagine di sfondo (origine in alto a sinistra).
Con la taratura della scala (m_per_px) le misure diventano metri reali.
Lo schema è INDICATIVO: va rifinito in CAD. Il DXF contiene linee, rettangoli, cerchi e testi
in metri (asse Y verso l'alto, come in CAD); lo sfondo NON entra nel DXF.
"""
import io
import json
import math
import os
import uuid

from database import cartella_schemi

LATO_MAX = 2400                     # px: sfondo sufficiente per leggere la tavola, file leggero
FORMATO_VUOTO = (1600, 1000)        # area di lavoro senza sfondo

# Tavolozza: codice → (etichetta, forma, larghezza e altezza predefinite in metri)
ELEMENTI = {
    "recinzione":        ("Recinzione", "linea", None),
    "ponteggio":         ("Ponteggio", "linea", None),
    "percorso":          ("Viabilità / percorso", "linea", None),
    "accesso_carrabile": ("Accesso carrabile", "simbolo", (5, 1.5)),
    "accesso_pedonale":  ("Accesso pedonale", "simbolo", (1.5, 1.2)),
    "spogliatoio":       ("Baracca spogliatoio", "simbolo", (6, 2.5)),
    "ufficio":           ("Baracca ufficio", "simbolo", (6, 2.5)),
    "refettorio":        ("Baracca refettorio", "simbolo", (6, 2.5)),
    "wc":                ("WC chimico", "simbolo", (1.2, 1.2)),
    "deposito":          ("Deposito materiali", "simbolo", (8, 5)),
    "rifiuti":           ("Deposito rifiuti / cassoni", "simbolo", (6, 2.5)),
    "gru":               ("Gru a torre", "gru", (4, 4)),
    "autogru":           ("Autogru", "simbolo", (10, 3)),
    "betoniera":         ("Betoniera / silos", "simbolo", (3, 3)),
    "quadro":            ("Quadro elettrico", "simbolo", (1, 0.6)),
    "estintore":         ("Estintore", "simbolo", (0.8, 0.8)),
    "primo_soccorso":    ("Cassetta primo soccorso", "simbolo", (0.8, 0.8)),
    "punto_raccolta":    ("Punto di raccolta", "simbolo", (3, 3)),
    "carico_scarico":    ("Zona carico / scarico", "simbolo", (8, 4)),
    "parcheggio":        ("Parcheggio", "simbolo", (5, 2.5)),
    "lavorazione":       ("Area di lavorazione (ferro, legno)", "simbolo", (6, 4)),
    "testo":             ("Etichetta di testo", "testo", None),
}


# ══════════════════════════════════════════════════════════════════════════════
# Sfondo
# ══════════════════════════════════════════════════════════════════════════════

def _salva_png(img, progetto_id: int, vecchio: str = None) -> tuple:
    img = img.convert("RGB")
    img.thumbnail((LATO_MAX, LATO_MAX))
    path = os.path.join(cartella_schemi(progetto_id), f"sfondo_{uuid.uuid4().hex[:12]}.png")
    img.save(path, format="PNG", optimize=True)
    if vecchio and os.path.exists(vecchio) and vecchio != path:
        os.remove(vecchio)
    return path, img.size[0], img.size[1]


def pagine_pdf(contenuto: bytes) -> int:
    import pypdfium2 as pdfium
    return len(pdfium.PdfDocument(contenuto))


def sfondo_da_file(contenuto: bytes, nome_file: str, pagina: int, progetto_id: int, vecchio: str = None) -> tuple:
    """PDF (pagina scelta) o immagine → PNG conservato con lo schema."""
    from PIL import Image
    est = nome_file.lower().rsplit(".", 1)[-1]
    if est == "pdf":
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(contenuto)
        if not 1 <= pagina <= len(pdf):
            raise ValueError(f"Pagina {pagina} inesistente: il PDF ha {len(pdf)} pagine")
        p = pdf[pagina - 1]
        w, h = p.get_size()
        scala = min(LATO_MAX / max(w, h), 4.0)       # tavole grandi: resta nitida senza pesare troppo
        img = p.render(scale=scala).to_pil()
    elif est in ("jpg", "jpeg", "png"):
        img = Image.open(io.BytesIO(contenuto))
    else:
        raise ValueError("Formato non supportato per lo sfondo: usa PDF, JPG o PNG")
    return _salva_png(img, progetto_id, vecchio)


def duplica_sfondo(path: str, progetto_id: int) -> str:
    if not path or not os.path.exists(path):
        return None
    nuovo = os.path.join(cartella_schemi(progetto_id), f"sfondo_{uuid.uuid4().hex[:12]}.png")
    with open(path, "rb") as a, open(nuovo, "wb") as b:
        b.write(a.read())
    return nuovo


# ══════════════════════════════════════════════════════════════════════════════
# DXF
# ══════════════════════════════════════════════════════════════════════════════

COLORI_DXF = {"recinzione": 1, "ponteggio": 5, "percorso": 3, "gru": 6, "testo": 7}   # indici colore AutoCAD


def esporta_dxf(schema: dict) -> bytes:
    import ezdxf
    scala = json.loads(schema["scala_json"]) if schema.get("scala_json") else None
    if not scala or not scala.get("m_per_px"):
        raise ValueError("Per esportare in DXF serve la taratura della scala")
    k = float(scala["m_per_px"])
    h_px = schema.get("sfondo_h") or FORMATO_VUOTO[1]

    def P(x, y):
        return (round(x * k, 4), round((h_px - y) * k, 4))     # metri, asse Y verso l'alto

    doc = ezdxf.new("R2010", setup=True)
    doc.units = ezdxf.units.M
    msp = doc.modelspace()
    doc.layers.add("SCE_AVVISO", color=1)
    msp.add_text("SCHEMA INDICATIVO GENERATO DA SCE - DA RIFINIRE IN CAD",
                 dxfattribs={"layer": "SCE_AVVISO", "height": 0.8}).set_placement(P(0, -40))

    for el in json.loads(schema.get("elementi_json") or "[]"):
        tipo = el.get("tipo", "testo")
        layer = "SCE_" + tipo.upper()
        if layer not in doc.layers:
            doc.layers.add(layer, color=COLORI_DXF.get(tipo, 2))
        att = {"layer": layer}
        nome = el.get("etichetta") or ELEMENTI.get(tipo, (tipo,))[0]
        if tipo in ("recinzione", "ponteggio", "percorso"):
            punti = [P(x, y) for x, y in el.get("punti", [])]
            if len(punti) >= 2:
                msp.add_lwpolyline(punti, dxfattribs=att)
                msp.add_text(nome, dxfattribs={**att, "height": 0.5}).set_placement(punti[0])
        elif tipo == "testo":
            msp.add_text(el.get("testo") or nome, dxfattribs={**att, "height": 0.6}).set_placement(P(el["x"], el["y"]))
        elif tipo == "gru":
            c = P(el["x"], el["y"])
            msp.add_circle(c, radius=0.5 * float(el.get("w", 40)) * k, dxfattribs=att)       # base della gru
            if el.get("raggio_m"):
                msp.add_circle(c, radius=float(el["raggio_m"]), dxfattribs=att)             # raggio d'azione
            msp.add_text(f"{nome} R={el.get('raggio_m', '?')} m", dxfattribs={**att, "height": 0.6}).set_placement(c)
        else:
            cx, cy, w, hh = el["x"], el["y"], float(el.get("w", 40)), float(el.get("h", 30))
            a = math.radians(float(el.get("rot", 0)))
            angoli = []
            for dx, dy in ((-w / 2, -hh / 2), (w / 2, -hh / 2), (w / 2, hh / 2), (-w / 2, hh / 2)):
                x = cx + dx * math.cos(a) - dy * math.sin(a)
                y = cy + dx * math.sin(a) + dy * math.cos(a)
                angoli.append(P(x, y))
            msp.add_lwpolyline(angoli, close=True, dxfattribs=att)
            msp.add_text(nome, dxfattribs={**att, "height": 0.5}).set_placement(P(cx - w / 2, cy - hh / 2 - 8))

    out = io.StringIO()
    doc.write(out)
    return out.getvalue().encode("utf-8")
