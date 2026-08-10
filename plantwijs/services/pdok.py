"""PDOK-service: FGR (WFS), bodem, Gt/GHG/GLG, AHN en GMM (WMS GetFeatureInfo).

Belangrijk: laagnamen worden LAZY opgehaald (bij eerste gebruik), nooit bij import.
Als PDOK onbereikbaar is, vallen we terug op de hardcoded defaults per laag.
"""

from __future__ import annotations

import re
import threading
import urllib.parse
import xml.etree.ElementTree as ET
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import requests

from ..config import (
    AHN_WMS,
    BODEM_WMS,
    FGR_WMS,
    FMT_JSON,
    GMM_WMS,
    GWD_WMS,
    HEADERS,
    PDOK_FGR_WFS,
    TX_WGS84_RD,
    TX_WGS84_WEB,
)


# ───────────────────── HTTP utils
@lru_cache(maxsize=32)
def _get(url: str) -> requests.Response:
    return requests.get(url, headers=HEADERS, timeout=12)


@lru_cache(maxsize=16)
def _capabilities(url: str) -> Optional[ET.Element]:
    try:
        r = _get(f"{url}?service=WMS&request=GetCapabilities")
        r.raise_for_status()
        return ET.fromstring(r.text)
    except Exception as e:
        print("[CAP] fout:", e)
        return None


def _find_layer_name(url: str, want: List[str]) -> Optional[Tuple[str, str]]:
    root = _capabilities(url)
    if root is None:
        return None
    layers = root.findall(".//{*}Layer")
    cand: List[Tuple[str, str]] = []
    for layer in layers:
        name_el = layer.find("{*}Name")
        title_el = layer.find("{*}Title")
        name = (name_el.text if name_el is not None else "")
        title = (title_el.text if title_el is not None else "")
        if not name and not title:
            continue
        cand.append((name, title))
    lwant = [w.lower() for w in want]
    for name, title in cand:
        t = (title or "").lower()
        if any(w in t for w in lwant) and name:
            return name, title
    for name, title in cand:
        n = (name or "").lower()
        if any(w in n for w in lwant) and name:
            return name, title
    for name, title in cand:
        if name:
            return name, title
    return None


# ───────────────────── WMS-laagnamen (lazy + gecachet)
_WMSMETA: Dict[str, Dict[str, str]] = {}
_WMSMETA_LOCK = threading.Lock()


def _resolve_layers() -> Dict[str, Dict[str, str]]:
    """Zoek de WMS-laagnamen op via GetCapabilities; val terug op defaults."""
    meta: Dict[str, Dict[str, str]] = {}
    fgr = _find_layer_name(FGR_WMS, ["fysisch", "fgr"]) or ("fysischgeografischeregios", "FGR")
    bodem = _find_layer_name(BODEM_WMS, ["bodemvlakken", "bodem"]) or ("Bodemvlakken", "Bodemvlakken")
    gt = _find_layer_name(GWD_WMS, ["grondwatertrappen", "gt"]) or ("BRO Grondwaterspiegeldiepte Grondwatertrappen Gt", "Gt")
    ghg = _find_layer_name(GWD_WMS, ["ghg"]) or ("BRO Grondwaterspiegeldiepte GHG", "GHG")
    glg = _find_layer_name(GWD_WMS, ["glg"]) or ("BRO Grondwaterspiegeldiepte GLG", "GLG")
    ahn = _find_layer_name(AHN_WMS, ["dtm_05m", "dtm", "ahn"]) or ("dtm_05m", "AHN hoogte (DTM 0.5m)")
    gmm = _find_layer_name(GMM_WMS, ["geomorfologische", "geomorphological"]) or ("geomorphological_area", "Geomorfologische kaart (GMM)")
    meta["fgr"] = {"url": FGR_WMS, "layer": fgr[0], "title": fgr[1]}
    meta["bodem"] = {"url": BODEM_WMS, "layer": bodem[0], "title": bodem[1]}
    meta["gt"] = {"url": GWD_WMS, "layer": gt[0], "title": gt[1]}
    meta["ghg"] = {"url": GWD_WMS, "layer": ghg[0], "title": ghg[1]}
    meta["glg"] = {"url": GWD_WMS, "layer": glg[0], "title": glg[1]}
    meta["ahn"] = {"url": AHN_WMS, "layer": ahn[0], "title": ahn[1]}
    meta["gmm"] = {"url": GMM_WMS, "layer": gmm[0], "title": gmm[1]}
    return meta


def get_wms_meta() -> Dict[str, Dict[str, str]]:
    """Laagnamen ophalen (één keer per proces). Netwerk pas bij eerste gebruik."""
    global _WMSMETA
    if _WMSMETA:
        return _WMSMETA
    with _WMSMETA_LOCK:
        if _WMSMETA:
            return _WMSMETA
        try:
            meta = _resolve_layers()
        except Exception as e:  # nooit een 500 door een kapotte bron
            print("[WMS] resolve fout, val terug op defaults:", e)
            meta = _fallback_layers()
        _WMSMETA = meta
        print("[WMS] resolved:", meta)
    return _WMSMETA


def _fallback_layers() -> Dict[str, Dict[str, str]]:
    """Hardcoded defaults als PDOK volledig onbereikbaar is."""
    return {
        "fgr": {"url": FGR_WMS, "layer": "fysischgeografischeregios", "title": "FGR"},
        "bodem": {"url": BODEM_WMS, "layer": "Bodemvlakken", "title": "Bodemvlakken"},
        "gt": {"url": GWD_WMS, "layer": "BRO Grondwaterspiegeldiepte Grondwatertrappen Gt", "title": "Gt"},
        "ghg": {"url": GWD_WMS, "layer": "BRO Grondwaterspiegeldiepte GHG", "title": "GHG"},
        "glg": {"url": GWD_WMS, "layer": "BRO Grondwaterspiegeldiepte GLG", "title": "GLG"},
        "ahn": {"url": AHN_WMS, "layer": "dtm_05m", "title": "AHN hoogte (DTM 0.5m)"},
        "gmm": {"url": GMM_WMS, "layer": "geomorphological_area", "title": "Geomorfologische kaart (GMM)"},
    }


# ───────────────────── WFS/WMS helpers
def _wfs(url: str) -> List[dict]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        if "json" not in r.headers.get("Content-Type", "").lower():
            return []
        return (r.json() or {}).get("features", [])
    except Exception:
        return []


_kv_re = re.compile(r"^\s*([A-Za-z0-9_\-\. ]+?)\s*[:=]\s*(.+?)\s*$")


def _parse_kv_text(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for line in (text or "").splitlines():
        m = _kv_re.match(line)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    if not out:
        stripped = re.sub(r"<[^>]+>", "\n", text)
        for line in stripped.splitlines():
            m = _kv_re.match(line)
            if m:
                out[m.group(1).strip()] = m.group(2).strip()
    return out


_DEF_INFO_FORMATS = [
    "application/json",
    "application/geo+json",
    "application/json;subtype=geojson",
    "application/vnd.ogc.gml",
    "text/xml",
    "text/plain",
]


def _wms_getfeatureinfo(base_url: str, layer: str, lat: float, lon: float) -> dict | None:
    cx, cy = TX_WGS84_WEB.transform(lon, lat)
    m = 200.0
    bbox = f"{cx-m},{cy-m},{cx+m},{cy+m}"
    params_base = {
        "service": "WMS", "version": "1.3.0", "request": "GetFeatureInfo",
        "layers": layer, "query_layers": layer, "styles": "",
        "crs": "EPSG:3857", "width": 101, "height": 101, "i": 50, "j": 50,
        "bbox": bbox,
    }
    params_base["feature_count"] = 10
    for fmt in _DEF_INFO_FORMATS:
        params = dict(params_base)
        params["info_format"] = fmt
        try:
            r = requests.get(base_url, params=params, headers=HEADERS, timeout=10)
            if not r.ok:
                continue
            ctype = r.headers.get("Content-Type", "").lower()
            if "json" in ctype:
                data = r.json() or {}
                feats = data.get("features") or []
                if feats:
                    props = feats[0].get("properties") or {}
                    if props:
                        return props
            text = r.text
            if text and fmt in ("text/plain", "text/xml", "application/vnd.ogc.gml"):
                return {"_text": text}
        except Exception:
            continue
    return None


# ───────────────────── PDOK value extractors
def fgr_from_point(lat: float, lon: float) -> str | None:
    x, y = TX_WGS84_RD.transform(lon, lat)
    if not (0 < x < 300_000 and 300_000 < y < 620_000):
        return None
    b = 100
    x1, y1, x2, y2 = round(x-b, 3), round(y-b, 3), round(x+b, 3), round(y+b, 3)
    layer_name = "fysischgeografischeregios:fysischgeografischeregios"
    url_rd = (
        f"{PDOK_FGR_WFS}&request=GetFeature&typenames={layer_name}"
        f"&outputFormat={FMT_JSON}&srsName=EPSG:28992&bbox={x1},{y1},{x2},{y2}&count=1"
    )
    feats = _wfs(url_rd)
    if feats:
        return feats[0].get("properties", {}).get("fgr")
    cql = urllib.parse.quote_plus(f"INTERSECTS(geometry,POINT({lon} {lat}))")
    url_pt = (
        f"{PDOK_FGR_WFS}&request=GetFeature&typenames={layer_name}"
        f"&outputFormat={FMT_JSON}&srsName=EPSG:4326&cql_filter={cql}&count=1"
    )
    feats = _wfs(url_pt)
    if feats:
        return feats[0].get("properties", {}).get("fgr")
    return None


# Termen uit de BRO Bodemkaart → de vier PlantWijs-bodemcategorieën.
# "petgat(en)" en "moerig(e)" zijn veenvarianten: petgaten zijn uitgeveende
# stroken in het laagveen, moerige gronden hebben een veenlaag in het profiel.
_SOIL_TOKENS = {
    "veen": {"veen", "petgat", "moerig"},
    "klei": {"klei", "zware klei", "lichte klei"},
    "leem": {"leem", "loess", "löss", "zavel"},
    "zand": {"zand", "dekzand"},
}

# Sleutel waaronder `bodem_from_bodemkaart` de ruwe kaartterm in de props legt,
# zodat /advies/geo hem als `bodem_detail` kan tonen ("Bodemkaart noemt dit:
# Petgaten") zonder dat de filtering met die ruwe term hoeft te werken.
RUWE_BODEM_KEY = "_bodem_ruw"


# "Leemarm fijn zand" gaat over zand: een 'X-arm'-samenstelling zegt juist dat
# er weinig X in zit en mag dus nooit als bodemcategorie X matchen.
_RE_SOIL_ARM = re.compile(r"\b(?:leem|klei|zand|veen|humus|kalk)arm\w*")


def _soil_from_text(text: str) -> Optional[str]:
    t = _RE_SOIL_ARM.sub(" ", (text or "").lower())
    for soil, keys in _SOIL_TOKENS.items():
        for k in keys:
            if k in t:
                return soil
    return None


def _bodem_resultaat(ruw: str, props: dict) -> Tuple[Optional[str], dict]:
    """(gecanoniseerde categorie of ruwe waarde, props + de ruwe kaartterm)."""
    ruw = str(ruw or "").strip()
    if ruw:
        props[RUWE_BODEM_KEY] = ruw
    return (_soil_from_text(ruw) or ruw or None), props


def bodem_from_bodemkaart(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    """Bodemcategorie voor een punt: (zand|klei|leem|veen of ruwe naam, props).

    De props bevatten onder `RUWE_BODEM_KEY` de kaartterm zoals de BRO
    Bodemkaart hem noemt, ook als die naar een categorie is herleid.
    """
    layer = get_wms_meta().get("bodem", {}).get("layer") or "Bodemvlakken"
    props = _wms_getfeatureinfo(BODEM_WMS, layer, lat, lon) or {}

    for k in (
        "grondsoort", "bodem", "BODEM", "BODEMTYPE", "soil", "bodemtype", "SOILAREA_NAME", "NAAM",
        "first_soilname", "normal_soilprofile_name",
    ):
        if k in props and props[k]:
            return _bodem_resultaat(str(props[k]), props)

    if "_text" in props:
        kv = _parse_kv_text(props["_text"]) or {}
        for k in ("grondsoort", "BODEM", "bodemtype", "BODEMNAAM", "NAAM", "omschrijving",
                  "first_soilname", "normal_soilprofile_name"):
            if k in kv and kv[k]:
                return _bodem_resultaat(str(kv[k]), props)
        so = _soil_from_text(props["_text"]) or None
        return so, props

    return None, props


def ahn_from_wms(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    """
    Haal een AHN-hoogte (DTM) op via de PDOK AHN WMS.
    Retourneert (hoogte_meter, raw_props) waarbij hoogte_meter als string is geformatteerd.
    """
    layer = get_wms_meta().get("ahn", {}).get("layer") or "dtm_05m"
    props = _wms_getfeatureinfo(AHN_WMS, layer, lat, lon) or {}

    def _first_numeric_value(d: dict) -> Optional[float]:
        for v in d.values():
            s = str(v).strip()
            if re.fullmatch(r"-?\d+(\.\d+)?", s):
                try:
                    return float(s)
                except Exception:
                    continue
        return None

    val: Optional[float] = None
    if props:
        val = _first_numeric_value(props)
    if val is None and "_text" in props:
        kv = _parse_kv_text(props.get("_text", "")) or {}
        val = _first_numeric_value(kv)
        if val is None:
            m = re.search(r"(-?\d+(?:\.\d+)?)", str(props.get("_text", "")))
            if m:
                try:
                    val = float(m.group(1))
                except Exception:
                    val = None

    if val is None:
        return None, props
    # Format met 2 decimalen; UI toont dit rechtstreeks
    return f"{val:.2f}", props


def gmm_from_wms(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    """
    Haal een geomorfologische eenheid op via de BRO Geomorfologische kaart (GMM) WMS.
    Retourneert (omschrijving, raw_props), waarbij de omschrijving afkomstig is uit de
    landvormsubgroep-beschrijving (indien beschikbaar).
    """
    layer = get_wms_meta().get("gmm", {}).get("layer") or "geomorphological_area"
    props = _wms_getfeatureinfo(GMM_WMS, layer, lat, lon) or {}

    def _norm_key(k: str) -> str:
        return k.lower().replace("_", "").replace("-", "")

    def _first_from_keys(d: dict, candidates) -> Optional[str]:
        if not d:
            return None
        # maak een lookup van genormaliseerde sleutel → originele sleutel
        kl = {_norm_key(k): k for k in d.keys()}
        for wanted in candidates:
            want_norm = wanted.lower().replace("_", "").replace("-", "")
            for nk, orig in kl.items():
                if want_norm == nk or want_norm in nk:
                    v = d.get(orig)
                    if v is None:
                        continue
                    s = str(v).strip()
                    if not s:
                        continue
                    sl = s.lower()
                    # filter expliciete nietszeggende waarden
                    if sl == "nee":
                        continue
                    if s.lstrip().startswith("<?xml") or "msGMLOutput" in s:
                        continue
                    if sl.startswith("geom50000"):
                        continue
                    return s
        return None

    # Voorkeursvelden volgens BRO-catalogus:
    #   landvormsubgroep_beschrijving / landformsubgroup_description
    # Eventueel uitbreidbaar met andere beschrijvingsvelden indien nodig.
    desc_keys = [
        "landformsubgroup_description",
        "landvormsubgroep_beschrijving",
    ]

    val: Optional[str] = None
    if props:
        val = _first_from_keys(props, desc_keys)

    # Als het in _text staat als key/value, probeer dat ook
    if val is None and "_text" in props:
        kv = _parse_kv_text(props.get("_text", "")) or {}
        val = _first_from_keys(kv, desc_keys)

    if not val:
        return None, props

    sval = str(val).strip()
    sl = sval.lower()
    if not sval or sl == "nee":
        return None, props
    if sval.lstrip().startswith("<?xml") or "msGMLOutput" in sval or sl.startswith("geom50000"):
        return None, props

    return sval, props


# ───────────────────── PDOK value → vochtklasse
GT_ORDINAL_TO_CODE = {
    1: "Ia",  2: "Ib",  3: "IIa", 4: "IIb", 5: "IIc",
    6: "IIIa", 7: "IIIb",
    8: "IVu", 9: "IVc",
    10: "Vao", 11: "Vad", 12: "Vbo", 13: "Vbd",
    14: "VIo", 15: "VId",
    16: "VIIo", 17: "VIId",
    18: "VIIIo", 19: "VIIId",
}


def _gt_pretty(gt: Optional[str]) -> Optional[str]:
    if not gt:
        return None
    s = str(gt).strip()
    if s.isdigit():
        try:
            v = int(float(s.replace(",", ".")))
        except Exception:
            return s
        return GT_ORDINAL_TO_CODE.get(v, s)
    return s.upper()


def _vochtklasse_from_gt_code(gt: Optional[str]) -> Optional[str]:
    if not gt:
        return None
    s = str(gt).strip()
    if s.isdigit():
        try:
            v = int(float(s.replace(",", ".")))
        except Exception:
            return None
        if 1 <= v <= 5:    return "zeer nat"
        if 6 <= v <= 7:    return "nat"
        if 8 <= v <= 13:   return "vochtig"
        if 14 <= v <= 15:  return "droog"
        if 16 <= v <= 19:  return "zeer droog"
        return None
    s_up = s.upper()
    m = re.match(r"^(I{1,3}|IV|V|VI|VII|VIII)", s_up)
    base = m.group(1) if m else s_up
    if base in ("I", "II"): return "zeer nat"
    if base == "III":       return "nat"
    if base in ("IV", "V"): return "vochtig"
    if base == "VI":        return "droog"
    if base in ("VII", "VIII"): return "zeer droog"
    return None


def vocht_from_gwt(lat: float, lon: float) -> Tuple[Optional[str], dict, Optional[str]]:
    meta = get_wms_meta()
    gt_layer = meta.get("gt", {}).get("layer") or "BRO Grondwaterspiegeldiepte Grondwatertrappen Gt"
    props = _wms_getfeatureinfo(GWD_WMS, gt_layer, lat, lon) or {}

    def _first_numeric(d: dict) -> Optional[str]:
        for k, v in d.items():
            ks = str(k).lower()
            if any(w in ks for w in ("value_list", "value", "class", "raster", "pixel", "waarde", "val")):
                s = str(v).strip()
                if re.fullmatch(r"\d+(\.\d+)?", s):
                    return s
        return None

    gt_raw: Optional[str] = None

    for k in ("gt", "grondwatertrap", "GT", "Gt"):
        if k in props and props[k]:
            gt_raw = str(props[k]).strip()
            break

    if not gt_raw and "_text" in props:
        kv = _parse_kv_text(props["_text"])
        for k in ("gt", "grondwatertrap", "GT"):
            if k in kv and kv[k]:
                gt_raw = str(kv[k]).strip()
                break
        if not gt_raw:
            m = re.search(r"\bGT\s*([IVX]+[a-z]?)\b", props["_text"], re.I)
            if m:
                gt_raw = m.group(1).strip()

    if not gt_raw:
        if "value_list" in props and str(props["value_list"]).strip():
            gt_raw = str(props["value_list"]).strip()
        if not gt_raw:
            hint = _first_numeric(props)
            if hint:
                gt_raw = hint

    klass = _vochtklasse_from_gt_code(gt_raw)

    if not klass:
        for key in ("glg", "ghg"):
            lyr = meta.get(key, {}).get("layer")
            if not lyr:
                continue
            p2 = _wms_getfeatureinfo(GWD_WMS, lyr, lat, lon) or {}
            txt = " ".join(str(v) for v in p2.values())
            m = re.search(r"(GLG|GHG)\s*[:=]?\s*(\d{1,3})", txt, re.I)
            depth = int(m.group(2)) if m else None
            if depth is not None:
                if depth < 25:   klass = "zeer nat"
                elif depth < 40: klass = "nat"
                elif depth < 80: klass = "vochtig"
                elif depth < 120: klass = "droog"
                else:            klass = "zeer droog"
                return klass, p2, _gt_pretty(gt_raw)

    return klass, props, _gt_pretty(gt_raw)
