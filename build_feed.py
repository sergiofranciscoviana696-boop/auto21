# -*- coding: utf-8 -*-
"""
Gera DOIS feeds a partir das mesmas fontes (cruzadas por id):
  1) Pagina /viaturas  -> campos estruturados (potencia, lugares, carrocaria, combustivel, preco...)
  2) Feed XML do Meta  -> galeria completa de imagens + cor exterior + transmissao

Saidas:
  valpimotor_stock.xml -> auto.pt (inalterado: so viaturas com galeria completa)
  meta_vehicles.xml    -> catalogo automovel da Meta (formato igual ao do AUTO21,
                          com body_style/fuel_type/drivetrain corretos e custom_label_0)
                          Inclui tambem as viaturas sem galeria, usando a miniatura da pagina.

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
META_OUT = "meta_vehicles.xml"

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

# ---------- Meta ----------
DEALER = {
    "addr1": "Av. Joaquim Ribeiro da Mota 256 Gandra", "city": "Paredes",
    "region": "Porto", "postal_code": "4585-166", "country": "PT",
    "lat": "41.18867484187807", "lng": "-8.442489057671049",
}
META_BODY = {
    "VLP_Htckb": "HATCHBACK", "VLP_Sdn": "SEDAN", "VLP_STW": "WAGON",
    "VLP_SUV": "SUV", "VLP_Ctd": "SMALL_CAR", "VLP_Cbr": "SMALL_CAR",
    "VLP_Mnvl": "MPV", "VLP_TT": "PICKUP",
}
META_MIN_RATIO = 0.5   # nao sobrescreve o feed Meta se cair mais de 50% face ao anterior


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
        # miniatura da listagem (usada so no feed Meta, para carros sem galeria)
        # CONFIRMA: a imagem do cartao tem "imagens_viaturas" no src/data-src?
        thumb = ""
        for im in item.find_all("img"):
            src = im.get("data-src") or im.get("src") or ""
            if "imagens_viaturas" in src:
                thumb = urljoin(BASE, src)
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
            "thumb": thumb,
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
        tr_el = lst.find("transmission")
        trans = (tr_el.text or "").strip() if tr_el is not None and tr_el.text else ""
        out[vid] = {"images": imgs, "color": color, "trans": trans}
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


# ---------- mapeamento Meta ----------
def to_int(s):
    digits = re.sub(r"\D", "", str(s or ""))
    return int(digits) if digits else 0


def meta_body(tipo, seats):
    if seats >= 9:
        return "MINIBUS"
    if tipo == "VLP_Combi":           # "Combi" com menos de 9 lugares (ex.: Tourneo Courier)
        return "MPV"
    if tipo in ("VLM_frg", "VLM_Combi"):
        return "VAN"
    if tipo.startswith("VLM") or tipo == "Caixa Frigorifica":
        return "TRUCK"
    return META_BODY.get(tipo, "OTHER")


def meta_fuel(txt):
    t = (txt or "").lower()
    if "plug" in t:
        return "PLUGIN_HYBRID"
    if "híbrido" in t or "hibrido" in t:
        return "HYBRID"
    if "diesel" in t:
        return "DIESEL"
    if "gasolina" in t:
        return "GASOLINE"
    if "tric" in t:
        return "ELECTRIC"
    return "OTHER"


def meta_trans(txt, fallback=""):
    t = (txt or "").lower()
    if "autom" in t:
        return "AUTOMATIC"
    if "manual" in t:
        return "MANUAL"
    fb = (fallback or "").upper()
    return fb if fb in ("AUTOMATIC", "MANUAL") else "OTHER"


def meta_drivetrain(versao):
    v = (versao or "").lower()
    if re.search(r"4x4|4wd", v):
        return "4X4"
    if re.search(r"quattro|xdrive|4motion|awd|allgrip|4matic", v):
        return "AWD"
    return "FWD"


def meta_date(reg, ano):
    m = re.match(r"(\d{4})(?:-(\d{1,2}))?", reg or "") or re.match(r"(\d{4})", ano or "")
    if not m:
        return ""
    mes = int(m.group(2)) if m.lastindex and m.lastindex >= 2 and m.group(2) else 1
    return "%s-%02d-01" % (m.group(1), mes)


def meta_group(v, seats):
    if v["seccao"] == "VLM" or seats >= 9 or "d-max" in v["modelo"].lower():
        return "comercial"
    return "passageiros"


def to_meta_xml(vehicles):
    def e(x):
        return escape(str(x))
    L = ['<?xml version="1.0" encoding="UTF-8"?>', "<listings>",
         "<title>Valpi Motor - Stock</title>",
         '<link rel="self" href="https://www.valpimotor.pt"/>']
    for v in vehicles:
        seats = to_int(v["lugares"])
        title = " ".join(x for x in (v["marca"], v["modelo"], v["versao"]) if x).strip()
        kms = to_int(v["kms"])
        desc_bits = [title, v["ano"], ("{:,}".format(kms).replace(",", " ") + " km") if kms else "",
                     v["combustivel"], v["trans"]]
        desc = " · ".join(b for b in desc_bits if b)
        L.append("<listing>")
        L.append("<vehicle_id>%s</vehicle_id>" % e(v["id"]))
        L.append("<vehicle_offer_id>%s</vehicle_offer_id>" % e(v["id"]))
        L.append("<title>%s</title>" % e(title))
        L.append("<description>%s</description>" % e(desc))
        L.append("<url>%s</url>" % e(v["url"]))
        L.append("<make>%s</make>" % e(v["marca"]))
        L.append("<model>%s</model>" % e(v["modelo"]))
        L.append("<year>%s</year>" % e(v["ano"]))
        L.append("<mileage><value>%d</value><unit>KM</unit></mileage>" % kms)
        for u in v["images"][:20]:
            L.append("<image><url>%s</url><tag>Exterior</tag></image>" % e(u))
        L.append("<body_style>%s</body_style>" % meta_body(v["tipo"], seats))
        L.append("<fuel_type>%s</fuel_type>" % meta_fuel(v["combustivel"]))
        L.append("<transmission>%s</transmission>" % meta_trans(v["trans"], v.get("trans_fb")))
        L.append("<drivetrain>%s</drivetrain>" % meta_drivetrain(v["versao"]))
        if v.get("color"):
            L.append("<exterior_color>%s</exterior_color>" % e(v["color"]))
        L.append("<condition>EXCELLENT</condition>")
        L.append("<price>%d EUR</price>" % v["preco"])
        L.append('<address format="simple">'
                 '<component name="addr1">%s</component>'
                 '<component name="city">%s</component>'
                 '<component name="region">%s</component>'
                 '<component name="postal_code">%s</component>'
                 '<component name="country">%s</component></address>'
                 % (e(DEALER["addr1"]), e(DEALER["city"]), e(DEALER["region"]),
                    e(DEALER["postal_code"]), e(DEALER["country"])))
        L.append("<latitude>%s</latitude>" % DEALER["lat"])
        L.append("<longitude>%s</longitude>" % DEALER["lng"])
        L.append("<availability>AVAILABLE</availability>")
        dt = meta_date(v["registration"], v["ano"])
        if dt:
            L.append("<date_first_on_lot>%s</date_first_on_lot>" % dt)
        L.append("<state_of_vehicle>USED</state_of_vehicle>")
        L.append("<dealer_id>1</dealer_id>")
        L.append("<custom_label_0>%s</custom_label_0>" % meta_group(v, seats))
        L.append("</listing>")
    L.append("</listings>")
    return "\n".join(L) + "\n"


def previous_count(path, tag):
    if not os.path.exists(path):
        return 0
    with open(path, encoding="utf-8") as f:
        return f.read().count("<%s>" % tag)


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

    # ---------- feed auto.pt (comportamento original) ----------
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

    # valpimotor_stock.xml ja nao tem consumidor (auto.pt nao usa): nunca bloqueia o feed Meta
    if incluidas:
        with open(OUT, "w", encoding="utf-8") as f:
            f.write(to_xml(incluidas))
        print("\nOK: %d viaturas -> %s" % (len(incluidas), OUT))
    else:
        print("::warning::0 viaturas com galeria — %s nao atualizado (verifica o feed do AUTO21)." % OUT)

    # ---------- feed Meta ----------
    meta_recs, so_miniatura = [], []
    for rec in page:
        if rec["estado"] != "Disponível" or rec["preco"] <= 0:
            continue                      # reservados e sem preco nao vao para anuncios
        m = meta.get(rec["id"], {})
        imgs = manual.get(rec["id"]) or m.get("images") or ([rec["thumb"]] if rec.get("thumb") else [])
        if not imgs:
            continue
        if not (manual.get(rec["id"]) or m.get("images")):
            so_miniatura.append(rec["id"])
        meta_recs.append(dict(rec, images=imgs, color=m.get("color", ""), trans_fb=m.get("trans", "")))

    prev = previous_count(META_OUT, "listing")
    if not meta_recs or (prev and len(meta_recs) < prev * META_MIN_RATIO):
        print("::error::Feed Meta NAO atualizado: %d viaturas (anterior %d). Mantive o ficheiro antigo."
              % (len(meta_recs), prev))
        return
    with open(META_OUT, "w", encoding="utf-8") as f:
        f.write(to_meta_xml(meta_recs))
    print("OK: %d viaturas -> %s (so com miniatura: %s)"
          % (len(meta_recs), META_OUT, ", ".join(so_miniatura) or "nenhuma"))


if __name__ == "__main__":
    main()
