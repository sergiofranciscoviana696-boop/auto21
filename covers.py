# -*- coding: utf-8 -*-
"""
Gera capas 1080x1080 por viatura a partir de template/ (bg.png + template.json + fonts/)
e mete-as como 1.a imagem de cada viatura no feed Meta.

Estrutura esperada no repositorio:
  template/template.json
  template/bg.png
  template/overlay.png        (opcional, se template.json o indicar)
  template/fonts/*.ttf        (OpenSans-Bold, -SemiBold, -ExtraBold, -Regular)
  covers/                     (gerado; e publicado no Pages)

Cache: o nome do ficheiro inclui um hash de (versao do template + foto + textos).
So volta a gerar quando algo muda; o nome novo obriga a Meta a ir buscar a imagem outra vez.
"""
import os
import io
import json
import hashlib

from PIL import Image, ImageDraw, ImageFont, ImageOps

TEMPLATE_DIR = "template"
OUT_DIR = "covers"
PUBLIC_BASE = os.environ.get(
    "COVERS_BASE", "https://sergiofranciscoviana696-boop.github.io/auto21/covers/")
TEMPLATE_VERSION = "v1"      # muda isto quando alterares o design para forcar novo render
MIN_PHOTO_W = 800            # abaixo disto a foto fica esbatida -> usa a foto original sem capa

_T = None
_BG = None
_OVERLAY = None
_FONTS = {}


def _load():
    global _T, _BG, _OVERLAY
    if _T is None:
        with open(os.path.join(TEMPLATE_DIR, "template.json"), encoding="utf-8") as f:
            _T = json.load(f)
        _BG = Image.open(os.path.join(TEMPLATE_DIR, "bg.png")).convert("RGB")
        if _T.get("overlay"):
            _OVERLAY = Image.open(os.path.join(TEMPLATE_DIR, _T["overlay"])).convert("RGBA")


def _hex(h):
    return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))


def _font(file, size):
    k = (file, size)
    if k not in _FONTS:
        _FONTS[k] = ImageFont.truetype(os.path.join(TEMPLATE_DIR, "fonts", file), size)
    return _FONTS[k]


def _fit(t, s):
    size = t["size"]
    while True:
        f = _font(t["font_file"], size)
        if f.getlength(s) <= t["w"] or size <= t["min_size"]:
            return f
        size -= 1


# ---------- formatacao dos campos ----------
def fuel_pt(txt):
    t = (txt or "").lower()
    if "plug" in t:
        return "Híbrido Plug-in"
    if "híbrido" in t or "hibrido" in t:
        return "Híbrido"
    if "diesel" in t:
        return "Diesel"
    if "gasolina" in t:
        return "Gasolina"
    if "tric" in t:
        return "Elétrico"
    return ""


def _int(s):
    d = "".join(c for c in str(s or "") if c.isdigit())
    return int(d) if d else 0


def fields(v):
    kms = _int(v.get("kms"))
    return {
        "title": " ".join(x for x in (v.get("marca"), v.get("modelo")) if x),
        "fuel": fuel_pt(v.get("combustivel")),
        "price": "{:,}".format(v["preco"]).replace(",", ".") + " €" if v.get("preco") else "",
        "km": "{:,}".format(kms).replace(",", " ") + " km" if kms else "",
        "year": str(v.get("ano") or ""),
    }


# ---------- render ----------
def render(photo, data):
    _load()
    im = _BG.copy()
    cz = _T["car_zone"]
    ph = ImageOps.fit(photo.convert("RGB"), (cz["w"], cz["h"]),
                      method=Image.LANCZOS, centering=(0.5, 0.5))
    im.paste(ph, (cz["x"], cz["y"]))
    if _OVERLAY is not None:
        im.paste(_OVERLAY, (0, 0), _OVERLAY)
    d = ImageDraw.Draw(im)
    for t in _T["texts"]:
        s = data.get(t["field"]) or ""
        if not s:
            continue
        if t.get("uppercase"):
            s = s.upper()
        f = _fit(t, s)
        ax = {"left": t["x"], "center": t["x"] + t["w"] / 2, "right": t["x"] + t["w"]}[t["align"]]
        ay = {"top": t["y"], "middle": t["y"] + t["h"] / 2, "bottom": t["y"] + t["h"]}[t.get("valign", "middle")]
        anchor = {"left": "l", "center": "m", "right": "r"}[t["align"]] + \
                 {"top": "a", "middle": "m", "bottom": "d"}[t.get("valign", "middle")]
        d.text((ax, ay), s, font=f, fill=_hex(t["color"]), anchor=anchor)
    return im


def _fetch_bytes(url):
    import requests
    r = requests.get(url, timeout=40, headers={"User-Agent": "ValpiFeedBot/1.0"})
    r.raise_for_status()
    return r.content


def attach(recs, fetch=_fetch_bytes):
    """Gera/reutiliza a capa de cada viatura e poe-na como 1.a imagem. Apaga capas orfas."""
    _load()
    os.makedirs(OUT_DIR, exist_ok=True)
    keep, made, reused, skipped = set(), 0, 0, []
    for v in recs:
        if not v.get("images"):
            continue
        photo_url = v["images"][0]
        data = fields(v)
        key = json.dumps([TEMPLATE_VERSION, photo_url, data], sort_keys=True, ensure_ascii=False)
        name = "%s-%s.jpg" % (v["id"], hashlib.sha1(key.encode("utf-8")).hexdigest()[:10])
        path = os.path.join(OUT_DIR, name)
        if os.path.exists(path):
            reused += 1
        else:
            try:
                photo = Image.open(io.BytesIO(fetch(photo_url)))
            except Exception as e:
                print("::warning::capa %s: foto falhou (%s)" % (v["id"], e))
                skipped.append(v["id"])
                continue
            if photo.width < MIN_PHOTO_W:
                skipped.append(v["id"])      # miniatura pequena: fica so a foto original
                continue
            render(photo, data).save(path, "JPEG", quality=88, optimize=True, progressive=True)
            made += 1
        keep.add(name)
        v["images"] = [PUBLIC_BASE + name] + v["images"]
    for f in os.listdir(OUT_DIR):
        if f.endswith(".jpg") and f not in keep:
            os.remove(os.path.join(OUT_DIR, f))
    print("Capas: %d novas | %d reutilizadas | sem capa: %s"
          % (made, reused, ", ".join(skipped) or "nenhuma"))
