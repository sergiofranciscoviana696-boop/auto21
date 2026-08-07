# -*- coding: utf-8 -*-
"""
Gera o feed XML de stock da Valpi Motor cruzando DUAS fontes por id:
  1) Pagina /viaturas  -> campos estruturados (potencia, lugares, carrocaria, combustivel, preco...)
  2) Feed XML do Meta  -> galeria completa de imagens + cor exterior
Viaturas que nao tenham galeria (nem no Meta, nem no mapa manual) FICAM DE FORA.
Para essas, preenche 'imagens_extra.json' a mao (id -> lista de URLs; a 1a e a capa).

Uso:  python build_feed.py                      (le tudo online)
      python build_feed.py pagina.html          (pagina local + Meta online)
      python build_feed.py pagina.html meta.xml (ambos locais, para testes)
Dependencias: requests, beautifulsoup4
"""
import sys
import os
import re
import json
import datetime
import xml.etree.ElementTree as ET
from urllib.parse import urljoin
from xml.sax.saxutils import escape
from bs4 import BeautifulSoup

PAGE_URL = "https://www.valpimotor.pt/viaturas"
META_URL = "https://auto21.pt/valpi/filesxml/facebook_loja_auto_v2.xml"
BASE = "https://www.valpimotor.pt/site1/"
MAP_FILE = "imagens_extra.json"
OUT = "valpimotor_stock.xml"

MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
         "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}
FUEL_FALLBACK = {"D": "Diesel", "G": "Gasolina", "HPG": "Híbrido Plug-in (Gasolina)"}
CARROCARIA = {
    "VLP_SUV": "SUV", "VLP_Htckb": "Hatchback", "VLP_STW": "Carrinha",
    "VLP_Sdn": "Berlina", "VLP_Combi": "Combi / 9 lugares", "VLP_Mnvl": "Monovolume",
    "VLP_TT": "Todo-o-terreno", "VLP_Ctd": "Citadino", "VLP_Cbr": "Citadino",
    "VLM_frg": "Furgão", "VLM_Combi": "Furgão combi", "VLM_CxBsc": "Caixa basculante",
    "VLM_CxFch": "Caixa fechada", "VLM_CxAbr": "Caixa aberta", "VLM_CxFrg": "Caixa frigorífica",
    "VLM": "Comercial ligeiro", "Caixa Frigorifica": "Caixa frigorífica",
}
SEGMENTO = {"VLP": "Ligeiro de Passageiros", "VLM": "Ligeiro de Mercadorias"}


def fetch(url):
    import requests
    r = requests.get(url, timeout=40, headers={"User-Agent": "ValpiFeedBot/1.0"})
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def parse_registration(txt):
    parts = txt.split()
    if len(parts) == 2:
        m = MESES.get(parts[0].strip().lower()[:3])
        return "%s-%02d" % (parts[1], m) if m else parts[1]
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    return ""


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for item in soup.select("div.isotope-item.view"):
        a = item.attrs

        def d(k):
            return (a.get("data-" + k) or "").strip()

        vid = d("id")
        if not vid:
            continue
        marca, modelo = d("marca"), d("modelo")
        link = item.select_one("a.ficha-viatura-v2__box")
        href = link.get("href", "") if link else ""
        url = urljoin(BASE, href) if href else \
            "https://www.valpimotor.pt/viaturas/%s/%s" % (vid, (marca + " " + modelo).strip().replace(" ", "+"))
        reg_txt = ""
        for div in item.select(".ficha-viatura-v2__image__content__info div"):
            di = div.find("img")
            if di and "ano.svg" in (di.get("src") or ""):
                sp = div.find("span")
                if sp:
                    reg_txt = sp.get_text(strip=True)
                break
        try:
            preco = int(d("preco") or "0")
        except ValueError:
            preco = 0
        tipo = d("tipo")
        out.append({
            "id": vid, "url": url, "seccao": d("seccao"),
            "marca": marca, "modelo": modelo, "versao": d("versao"),
            "ano": d("ano"), "registration": parse_registration(reg_txt) or d("ano"),
            "kms": d("kms"),
            "combustivel": d("combustivel2") or FUEL_FALLBACK.get(d("combustivel"), d("combustivel")),
            "trans": d("transmissao"), "hp": d("hp"), "lugares": d("lugares"),
            "tipo": tipo, "carro": CARROCARIA.get(tipo, tipo), "preco": preco,
            "estado": "Reservado" if (item.select_one(".extra-field") and
                                      item.select_one(".extra-field").get_text(strip=True) == "Reservado")
                      else "Disponível",
        })
    return out


def parse_meta(xml_text):
    xml_text = re.sub(r'^\s*<\?xml.*?\?>', '', xml_text, flags=re.S)
    root = ET.fromstring(xml_text)
    out = {}
    for lst in root.findall("listing"):
        vid_el = lst.find("vehicle_id")
        if vid_el is None or not (vid_el.text or "").strip():
            continue
        vid = vid_el.text.strip()
        imgs = []
        for im in lst.findall("image"):
            u = im.find("url")
            if u is not None and (u.text or "").strip():
                imgs.append(u.text.strip())
        col_el = lst.find("exterior_color")
        color = (col_el.text or "").strip() if col_el is not None and col_el.text else ""
        out[vid] = {"images": imgs, "color": color}
    return out


def load_manual(path=MAP_FILE):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for k, v in data.items():
        if k.startswith("_"):
            continue
        if isinstance(v, list):
            urls = [str(u).strip() for u in v if str(u).strip()]
            if urls:
                out[str(k)] = urls
    return out


def to_xml(vehicles):
    def e(v):
        return escape(str(v))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L = ['<?xml version="1.0" encoding="UTF-8"?>']
    L.append('<vehicles source="valpimotor.pt + feed Meta" generated="%s" count="%d">' % (now, len(vehicles)))
    for v in vehicles:
        L.append("  <vehicle>")
        L.append("    <vehicle_id>%s</vehicle_id>" % e(v["id"]))
        L.append("    <url>%s</url>" % e(v["url"]))
        L.append("    <segment>%s</segment>" % e(SEGMENTO.get(v["seccao"], v["seccao"])))
        L.append("    <make>%s</make>" % e(v["marca"]))
        L.append("    <model>%s</model>" % e(v["modelo"]))
        L.append("    <version>%s</version>" % e(v["versao"]))
        L.append("    <year>%s</year>" % e(v["ano"]))
        L.append("    <registration>%s</registration>" % e(v["registration"]))
        L.append("    <mileage_km>%s</mileage_km>" % e(v["kms"]))
        L.append("    <fuel_type>%s</fuel_type>" % e(v["combustivel"]))
        L.append("    <transmission>%s</transmission>" % e(v["trans"]))
        L.append("    <power_hp>%s</power_hp>" % e(v["hp"]))
        L.append("    <seats>%s</seats>" % e(v["lugares"]))
        L.append("    <body_type>%s</body_type>" % e(v["carro"]))
        L.append("    <body_type_code>%s</body_type_code>" % e(v["tipo"]))
        if v["color"]:
            L.append("    <color>%s</color>" % e(v["color"]))
        if v["preco"] > 0:
            L.append("    <price_eur>%d</price_eur>" % v["preco"])
            L.append("    <price_on_request>false</price_on_request>")
        else:
            L.append("    <price_eur/>")
            L.append("    <price_on_request>true</price_on_request>")
        L.append("    <availability>%s</availability>" % e(v["estado"]))
        L.append("    <cover_image>%s</cover_image>" % e(v["cover"]))
        L.append("    <images>")
        for u in v["images"]:
            L.append("      <image>%s</image>" % e(u))
        L.append("    </images>")
        L.append("    <dealer>Valpi Motor Gandra</dealer>")
        L.append("  </vehicle>")
    L.append("</vehicles>")
    return "\n".join(L) + "\n"


def main():
    args = sys.argv[1:]
    if len(args) >= 2:
        page_html = open(args[0], encoding="utf-8").read()
        meta_xml = open(args[1], encoding="utf-8").read()
    elif len(args) == 1:
        page_html = open(args[0], encoding="utf-8").read()
        meta_xml = fetch(META_URL)
    else:
        page_html = fetch(PAGE_URL)
        meta_xml = fetch(META_URL)

    page = parse_page(page_html)
    if not page:
        raise SystemExit("ERRO: 0 viaturas na pagina — estrutura mudou? Nao publico feed vazio.")
    meta = parse_meta(meta_xml)
    manual = load_manual()

    incluidas, sem_galeria = [], []
    for rec in page:
        vid = rec["id"]
        gallery = manual.get(vid) or meta.get(vid, {}).get("images", [])
        if not gallery:
            sem_galeria.append(rec)
            continue
        rec["images"] = gallery
        rec["cover"] = gallery[0]
        rec["color"] = meta.get(vid, {}).get("color", "")
        incluidas.append(rec)

    print("Na pagina: %d | Com galeria (incluidas): %d | Sem galeria (excluidas): %d"
          % (len(page), len(incluidas), len(sem_galeria)))
    if sem_galeria:
        print("\n>> Viaturas SEM galeria — poe as imagens em %s para entrarem no feed:" % MAP_FILE)
        for r in sem_galeria:
            print("   id %-4s  %s %s %s" % (r["id"], r["marca"], r["modelo"], r["versao"]))

    if not incluidas:
        raise SystemExit("\nERRO: 0 viaturas com galeria. Nao publico feed vazio (verifica o feed Meta / o mapa).")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(to_xml(incluidas))
    print("\nOK: %d viaturas -> %s" % (len(incluidas), OUT))


if __name__ == "__main__":
    main()
