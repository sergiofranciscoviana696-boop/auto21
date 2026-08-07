# -*- coding: utf-8 -*-
"""
Gera o feed XML de stock da Valpi Motor a partir da propria pagina /viaturas.
Uso:  python build_feed.py            (le do site e escreve valpimotor_stock.xml)
      python build_feed.py ficheiro.html   (le de um HTML local, para testes)
Dependencias: requests, beautifulsoup4
"""
import sys
import datetime
from urllib.parse import urljoin
from xml.sax.saxutils import escape
from bs4 import BeautifulSoup

URL = "https://www.valpimotor.pt/viaturas"
BASE = "https://www.valpimotor.pt/site1/"   # <base href> da pagina, para resolver os links
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


def fetch(url=URL):
    import requests  # import tardio: modulo continua importavel sem requests (util p/ testes)
    r = requests.get(url, timeout=30, headers={"User-Agent": "ValpiFeedBot/1.0"})
    r.raise_for_status()
    r.encoding = "utf-8"
    return r.text


def parse_registration(txt):
    """'Out 2025' -> '2025-10' ; '2026' -> '2026' ; '' -> ''"""
    parts = txt.split()
    if len(parts) == 2:
        m = MESES.get(parts[0].strip().lower()[:3])
        if m:
            return "%s-%02d" % (parts[1], m)
        return parts[1]
    if len(parts) == 1 and parts[0].isdigit():
        return parts[0]
    return ""


def parse_html(html):
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

        # URL da ficha (resolve o href relativo; se faltar, constroi pelo padrao)
        link = item.select_one("a.ficha-viatura-v2__box")
        href = link.get("href", "") if link else ""
        if href:
            url = urljoin(BASE, href)
        else:
            url = "https://www.valpimotor.pt/viaturas/%s/%s" % (
                vid, (marca + " " + modelo).strip().replace(" ", "+"))

        # imagem (miniatura principal)
        img = item.select_one("img.ficha-viatura-v2__image__wrapper__img")
        image = (img.get("data-src") or img.get("src") or "").strip() if img else ""

        # estado (Reservado / etc. no campo extra)
        ef = item.select_one(".extra-field")
        estado = ef.get_text(strip=True) if ef else ""

        # mes/ano de matricula (span ao lado do icone ano.svg)
        reg_txt = ""
        for div in item.select(".ficha-viatura-v2__image__content__info div"):
            di = div.find("img")
            if di and "ano.svg" in (di.get("src") or ""):
                sp = div.find("span")
                if sp:
                    reg_txt = sp.get_text(strip=True)
                break
        registration = parse_registration(reg_txt) or d("ano")

        combustivel = d("combustivel2") or FUEL_FALLBACK.get(d("combustivel"), d("combustivel"))
        tipo = d("tipo")
        try:
            preco = int(d("preco") or "0")
        except ValueError:
            preco = 0

        out.append({
            "id": vid, "url": url, "seccao": d("seccao"),
            "marca": marca, "modelo": modelo, "versao": d("versao"),
            "ano": d("ano"), "registration": registration, "kms": d("kms"),
            "combustivel": combustivel, "trans": d("transmissao"),
            "hp": d("hp"), "lugares": d("lugares"),
            "tipo": tipo, "carro": CARROCARIA.get(tipo, tipo),
            "preco": preco, "image": image,
            "estado": "Reservado" if estado == "Reservado" else "Disponível",
        })
    return out


def to_xml(vehicles):
    def e(v):
        return escape(str(v))
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    L = ['<?xml version="1.0" encoding="UTF-8"?>']
    L.append('<vehicles source="valpimotor.pt/viaturas" generated="%s" count="%d">' % (now, len(vehicles)))
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
        if v["preco"] > 0:
            L.append("    <price_eur>%d</price_eur>" % v["preco"])
            L.append("    <price_on_request>false</price_on_request>")
        else:
            L.append("    <price_eur/>")
            L.append("    <price_on_request>true</price_on_request>")
        L.append("    <availability>%s</availability>" % e(v["estado"]))
        L.append("    <image>%s</image>" % e(v["image"]))
        L.append("    <dealer>Valpi Motor Gandra</dealer>")
        L.append("  </vehicle>")
    L.append("</vehicles>")
    return "\n".join(L) + "\n"


def main():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            html = f.read()
    else:
        html = fetch()
    vehicles = parse_html(html)
    if not vehicles:
        raise SystemExit("ERRO: 0 viaturas extraidas — a pagina mudou de estrutura?")
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(to_xml(vehicles))
    print("OK: %d viaturas -> %s" % (len(vehicles), OUT))


if __name__ == "__main__":
    main()
