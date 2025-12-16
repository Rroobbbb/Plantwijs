
# PlantWijs API — v3.9.7
# - FIX: PDOK Locatieserver → nieuwe endpoint (api.pdok.nl … /search/v3_1) met CORS
# - UI: Kolomtitel opent filter; kolommen tonen/verbergen; sticky header; thema toggle; CSV/XLSX export
# - HTML triple-quoted string correct afgesloten
# Starten:
#   cd C:/PlantWijs
#   venv/Scripts/uvicorn api:app --reload --port 9000

from __future__ import annotations

import io
import math
import os
from pathlib import Path
import re
import time
import unicodedata
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime

# PDF generatie (locatierapport)
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image as RLImage
from PIL import Image

import tempfile  # ← toevoegen
import json
import zipfile
from functools import lru_cache
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pyproj import Transformer

# ───────────────────── PDOK endpoints
HEADERS = {"User-Agent": "plantwijs/3.9.7"}
FMT_JSON = "application/json;subtype=geojson"

NSN_DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
# Groot bestand: liever niet in Git als losse .geojson. Daarom ondersteunen we ook een ZIP in /data.
NSN_GEOJSON_PATH = os.path.join(NSN_DATA_DIR, "nsn_natuurlijk_systeem.geojson")
NSN_ZIP_PATH = os.path.join(NSN_DATA_DIR, "LBK_BKNSN_2023.zip")  # default; er mag ook een andere .zip in /data staan

NSN_GEOJSON_IS_RD: bool = True  # GeoJSON in RD New (EPSG:28992); op False zetten als je zelf naar WGS84 hebt geprojecteerd

# NSN bron-resolutie (geen full in-memory cache; Render 512MB)
_NSN_SOURCE: Optional[Tuple[str, str, Optional[str]]] = None  # ("geojson"|"zip"|"missing", path, membername)

def _resolve_nsn_source() -> Tuple[str, str, Optional[str]]:
    """Bepaal waar NSN-data vandaan komt (losse geojson of zip). Cache alleen metadata."""
    global _NSN_SOURCE
    if _NSN_SOURCE is not None:
        return _NSN_SOURCE

    # 1) Losse geojson (dev)
    if os.path.exists(NSN_GEOJSON_PATH):
        _NSN_SOURCE = ("geojson", NSN_GEOJSON_PATH, None)
        return _NSN_SOURCE

    # 2) ZIP (prod): eerst default, dan elke .zip in data/
    zips: List[str] = []
    if os.path.exists(NSN_ZIP_PATH):
        zips.append(NSN_ZIP_PATH)
    try:
        for fn in os.listdir(NSN_DATA_DIR):
            if fn.lower().endswith(".zip"):
                p = os.path.join(NSN_DATA_DIR, fn)
                if p not in zips:
                    zips.append(p)
    except Exception:
        pass

    for zp in zips:
        try:
            with zipfile.ZipFile(zp, "r") as zf:
                names = zf.namelist()
                geo = [n for n in names if n.lower().endswith(".geojson") or n.lower().endswith(".json")]
                if geo:
                    _NSN_SOURCE = ("zip", zp, geo[0])
                    return _NSN_SOURCE
        except Exception:
            continue

    _NSN_SOURCE = ("missing", "", None)
    return _NSN_SOURCE


# WFS FGR
PDOK_FGR_WFS = (
    "https://service.pdok.nl/ez/fysischgeografischeregios/wfs/v1_0"
    "?service=WFS&version=2.0.0"
)
FGR_WMS = "https://service.pdok.nl/ez/fysischgeografischeregios/wms/v1_0"

# WMS Bodemkaart (BRO)
BODEM_WMS = "https://service.pdok.nl/bzk/bro-bodemkaart/wms/v1_0"

# WMS Grondwaterspiegeldiepte (BRO)
GWD_WMS = "https://service.pdok.nl/bzk/bro-grondwaterspiegeldiepte/wms/v2_0"

# AHN WMS (Actueel Hoogtebestand Nederland, DTM 0.5m)
AHN_WMS = "https://service.pdok.nl/rws/ahn/wms/v1_0"

# BRO Geomorfologische kaart (GMM) WMS
GMM_WMS = "https://service.pdok.nl/bzk/bro-geomorfologischekaart/wms/v2_0"

# ───────────────────── Proj
TX_WGS84_RD = Transformer.from_crs(4326, 28992, always_xy=True)
TX_WGS84_WEB = Transformer.from_crs(4326, 3857, always_xy=True)

# ───────────────────── Dataset (CSV) — één bron voor lokaal + Render
# Volgorde:
# 1) PLANTWIJS_CSV (optioneel) — absolute of relatieve padnaam
# 2) data/treeebb_planten_allfields.csv (in repo)
# 3) out/treeebb_planten_allfields.csv (optioneel)
# 4) legacy fallbacks (oude plantwijs_full bestanden)
DATA_PATHS = [
    os.environ.get("PLANTWIJS_CSV", "").strip(),
    os.path.join(os.path.dirname(__file__), "data", "treeebb_planten_allfields.csv"),
    os.path.join(os.path.dirname(__file__), "out", "treeebb_planten_allfields.csv"),
    os.path.join(os.path.dirname(__file__), "out", "plantwijs_full_semicolon.csv"),
    os.path.join(os.path.dirname(__file__), "out", "plantwijs_full.csv"),
]
DATA_PATHS = [p for p in DATA_PATHS if p]

# Online CSV fallback (GitHub raw) — alleen als er lokaal echt niets gevonden wordt
ONLINE_CSV_URLS = [
    os.environ.get("PLANTWIJS_ONLINE_CSV_URL", "").strip(),
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/data/treeebb_planten_allfields.csv",
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/out/treeebb_planten_allfields.csv",
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/out/plantwijs_full_semicolon.csv",
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/out/plantwijs_full.csv",
]
ONLINE_CSV_URLS = [u for u in ONLINE_CSV_URLS if u]

_CACHE: Dict[str, Any] = {"df": None, "mtime": None, "path": None, "source": None}

def _norm_col(c: object) -> str:
    """Normaliseer kolomnamen: lowercase + alle niet-letters/cijfers naar '_'"""
    s = str(c or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s

def _detect_sep(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(4096)
        return ";" if head.count(";") >= head.count(",") else ","
    except Exception:
        return ";"

def _load_df(path: str) -> pd.DataFrame:
    sep = _detect_sep(path)
    df = pd.read_csv(path, sep=sep, dtype=str, encoding_errors="ignore")
    df.columns = [_norm_col(c) for c in df.columns]

    # standaardnaam-koppelingen
    if "naam" not in df.columns and "nederlandse_naam" in df.columns:
        df = df.rename(columns={"nederlandse_naam": "naam"})

    # Wetenschappelijke naam: indien niet aanwezig proberen af te leiden
    if "wetenschappelijke_naam" not in df.columns:
        for k in ("taxon", "species"):
            if k in df.columns:
                df = df.rename(columns={k: "wetenschappelijke_naam"})
                break

    if "wetenschappelijke_naam" not in df.columns and "url" in df.columns:
        def _slug_to_species(u: str) -> str:
            try:
                slug = str(u or "").rstrip("/").split("/")[-1]
                parts = [p for p in slug.split("-") if p]
                if not parts:
                    return ""
                # vaak: <code>-<genus>-<species>-...
                if len(parts[0]) <= 10:
                    parts = parts[1:] or parts
                if len(parts) >= 2:
                    genus = parts[0].capitalize()
                    species = parts[1].lower()
                    return f"{genus} {species}".strip()
                return parts[0]
            except Exception:
                return ""
        df["wetenschappelijke_naam"] = df["url"].map(_slug_to_species)

    # ── TreeEbb → PlantWijs sleutelkolommen (zodat filters/analyses werken)
    # Na _norm_col worden o.a. "Standplaats > Lichtbehoefte" → "standplaats_lichtbehoefte"
    treeebb_map = {
        "standplaats_lichtbehoefte": "standplaats_licht",
        "standplaats_bodemvochtigheid": "vocht",
        "standplaats_grondsoort": "grondsoorten",
        "eigenschappen_hoogte": "hoogte",
        "eigenschappen_breedte": "breedte",
        "eigenschappen_winterhardheidszone": "winterhardheidszone",
        "toepassing_locatie": "locatie",
        "toepassing_verharding": "verharding",
        "standplaats_ph_waarde": "ph_waarde",
        "standplaats_voedselrijkdom": "voedselrijkdom",
        "standplaats_wind": "wind",
        "standplaats_extreme_condities": "extreme_condities",
        "standplaats_biodiversiteit": "biodiversiteit",
        "eigenschappen_kroonvorm": "kroonvorm",
        "eigenschappen_kroonstructuur": "kroonstructuur",
    }
    for src_col, dst_col in treeebb_map.items():
        if dst_col not in df.columns and src_col in df.columns:
            df[dst_col] = df[src_col]

    # Variants fallback (als namen net anders zijn)
    if "standplaats_licht" not in df.columns:
        for c in df.columns:
            if c.endswith("lichtbehoefte") or c == "lichtbehoefte":
                df["standplaats_licht"] = df[c]
                break
    if "vocht" not in df.columns:
        for c in df.columns:
            if "bodemvochtigheid" in c:
                df["vocht"] = df[c]
                break
    if "grondsoorten" not in df.columns:
        for c in df.columns:
            if c.endswith("grondsoort") or "grondsoort" in c:
                df["grondsoorten"] = df[c]
                break

    # kolommen die UI/filters verwachten altijd aanwezig maken
    for must in ("standplaats_licht", "vocht", "inheems", "invasief"):
        if must not in df.columns:
            df[must] = ""

    return df

def _fetch_csv_online(url: str) -> Optional[pd.DataFrame]:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return None
        text = r.content.decode("utf-8", errors="ignore")
        sep = ";" if text.count(";") >= text.count(",") else ","
        df = pd.read_csv(io.StringIO(text), sep=sep, dtype=str, encoding_errors="ignore")
        df.columns = [_norm_col(c) for c in df.columns]
        if "naam" not in df.columns and "nederlandse_naam" in df.columns:
            df = df.rename(columns={"nederlandse_naam": "naam"})
        if "wetenschappelijke_naam" not in df.columns:
            for k in ("taxon", "species"):
                if k in df.columns:
                    df = df.rename(columns={k: "wetenschappelijke_naam"})
                    break
        for must in ("standplaats_licht", "vocht", "inheems", "invasief"):
            if must not in df.columns:
                df[must] = ""
        return df
    except Exception as e:
        print("[ONLINE CSV] fout bij", url, "→", e)
        return None

def get_df() -> pd.DataFrame:
    # 1) Probeer lokaal (development)
    path = next((p for p in DATA_PATHS if os.path.exists(p)), None)
    if path:
        m = os.path.getmtime(path)
        if _CACHE["df"] is None or _CACHE["mtime"] != m or _CACHE["path"] != path:
            df = _load_df(path)
            _CACHE.update({"df": df, "mtime": m, "path": path, "source": "local"})
            print(f"[DATA] geladen (lokaal): {path} — {len(df)} rijen, {df.shape[1]} kolommen")
        return _CACHE["df"].copy()

    # 2) Fallback: online CSV (GitHub raw)
    if _CACHE["df"] is not None and _CACHE.get("source") == "online":
        return _CACHE["df"].copy()

    for url in ONLINE_CSV_URLS:
        df = _fetch_csv_online(url)
        if df is not None and not df.empty:
            _CACHE.update({"df": df, "mtime": time.time(), "path": url, "source": "online"})
            print(f"[DATA] geladen (online): {url} — {len(df)} rijen, {df.shape[1]} kolommen")
            return _CACHE["df"].copy()

    # 3) Niets gevonden → duidelijke foutmelding
    raise FileNotFoundError(
        "Geen dataset gevonden. Lokaal ontbreekt out/plantwijs_full.csv én online CSV kon niet worden opgehaald."
    )

    # 2) Fallback: online CSV (GitHub raw)
    if _CACHE["df"] is not None and _CACHE.get("source") == "online":
        return _CACHE["df"].copy()

    for url in ONLINE_CSV_URLS:
        df = _fetch_csv_online(url)
        if df is not None and not df.empty:
            _CACHE.update({"df": df, "mtime": time.time(), "path": url, "source": "online"})
            print(f"[DATA] geladen (online): {url} — {len(df)} rijen, {df.shape[1]} kolommen")
            return _CACHE["df"].copy()

    # 3) Niets gevonden → duidelijke foutmelding
    raise FileNotFoundError(
        "Geen dataset gevonden. Lokaal ontbreekt out/plantwijs_full.csv én online CSV kon niet worden opgehaald."
    )

# ──────────────────────────────────────────────────────────────
# PDF/kaart helpers (Beplantingswijzer locatierapport)
def _webmercator_tile_xy(lat: float, lon: float, z: int) -> tuple[int,int]:
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    n = 2 ** z
    x = int((lon + 180.0) / 360.0 * n)
    y = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return x, y

def _static_map_image(lat: float, lon: float, z: int = 17, tiles: int = 2) -> BytesIO | None:
    """
    Rendert een klein kaartje via OSM tiles (server-side).
    - tiles=2 → 2x2 tiles (512x512px)
    Geeft BytesIO terug met PNG of None als ophalen faalt.
    """
    try:
        cx, cy = _webmercator_tile_xy(lat, lon, z)
        half = tiles // 2
        img = Image.new("RGB", (256*tiles, 256*tiles))
        # Respecteer OSM tile usage: low volume (1 PDF per klik)
        headers = {"User-Agent": "Beplantingswijzer/1.0 (Render; locatierapport)"}
        for dx in range(-half, -half+tiles):
            for dy in range(-half, -half+tiles):
                x = cx + dx
                y = cy + dy
                url = f"https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                r = requests.get(url, timeout=10, headers=headers)
                if r.status_code != 200:
                    return None
                tile = Image.open(BytesIO(r.content)).convert("RGB")
                px = (dx + half) * 256
                py = (dy + half) * 256
                img.paste(tile, (px, py))
        out = BytesIO()
        img.save(out, format="PNG", optimize=True)
        out.seek(0)
        return out
    except Exception:
        return None

def _wrap_lines(text: str, max_chars: int = 95) -> list[str]:
    """Simpele wrap op woordgrenzen voor canvas.drawString."""
    if not text:
        return []
    words = str(text).split()
    lines, cur = [], ""
    for w in words:
        if len(cur) + (1 if cur else 0) + len(w) <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


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
    cand: List[Tuple[str,str]] = []
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

# Resolve alle laagnamen één keer bij startup
_WMSMETA: Dict[str, Dict[str, str]] = {}

def _resolve_layers() -> None:
    global _WMSMETA
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
    _WMSMETA = meta
    print("[WMS] resolved:", meta)

_resolve_layers()

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

_SOIL_TOKENS = {
    "veen": {"veen"},
    "klei": {"klei", "zware klei", "lichte klei"},
    "leem": {"leem", "loess", "löss", "zavel"},
    "zand": {"zand", "dekzand"},
}

def _soil_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for soil, keys in _SOIL_TOKENS.items():
        for k in keys:
            if k in t:
                return soil
    return None

def bodem_from_bodemkaart(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    layer = _WMSMETA.get("bodem", {}).get("layer") or "Bodemvlakken"
    props = _wms_getfeatureinfo(BODEM_WMS, layer, lat, lon) or {}

    for k in (
        "grondsoort", "bodem", "BODEM", "BODEMTYPE", "soil", "bodemtype", "SOILAREA_NAME", "NAAM",
        "first_soilname", "normal_soilprofile_name",
    ):
        if k in props and props[k]:
            val = str(props[k])
            return _soil_from_text(val) or val, props

    if "_text" in props:
        kv = _parse_kv_text(props["_text"]) or {}
        for k in ("grondsoort", "BODEM", "bodemtype", "BODEMNAAM", "NAAM", "omschrijving",
                  "first_soilname", "normal_soilprofile_name"):
            if k in kv and kv[k]:
                val = kv[k]
                return _soil_from_text(val) or val, props
        so = _soil_from_text(props["_text"]) or None
        return so, props

    return None, props


def ahn_from_wms(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    """
    Haal een AHN-hoogte (DTM) op via de PDOK AHN WMS.
    Retourneert (hoogte_meter, raw_props) waarbij hoogte_meter als string is geformatteerd.
    """
    layer = _WMSMETA.get("ahn", {}).get("layer") or "dtm_05m"
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
    layer = _WMSMETA.get("gmm", {}).get("layer") or "geomorphological_area"
    props = _wms_getfeatureinfo(GMM_WMS, layer, lat, lon) or {}

    def _norm_key(k: str) -> str:
        return k.lower().replace("_", "").replace("-", "")

    def _first_from_keys(d: dict, candidates) -> Optional[str]:
        if not d:
            return None
        # maak een lookup van genormaliseerde sleutel → originele sleutel
        kl = { _norm_key(k): k for k in d.keys() }
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
    1:"Ia",  2:"Ib",  3:"IIa", 4:"IIb", 5:"IIc",
    6:"IIIa",7:"IIIb",
    8:"IVu", 9:"IVc",
    10:"Vao",11:"Vad",12:"Vbo",13:"Vbd",
    14:"VIo",15:"VId",
    16:"VIIo",17:"VIId",
    18:"VIIIo",19:"VIIId",
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
    if base in ("VII","VIII"): return "zeer droog"
    return None

def vocht_from_gwt(lat: float, lon: float) -> Tuple[Optional[str], dict, Optional[str]]:
    gt_layer = _WMSMETA.get("gt", {}).get("layer") or "BRO Grondwaterspiegeldiepte Grondwatertrappen Gt"
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
            lyr = _WMSMETA.get(key, {}).get("layer")
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
                elif depth < 120:klass = "droog"
                else:            klass = "zeer droog"
                return klass, p2, _gt_pretty(gt_raw)

    return klass, props, _gt_pretty(gt_raw)

# ───────────────────── filtering helpers
def _contains_ci(s: Any, needle: str) -> bool:
    return needle.lower() in str(s or "").lower()

def _split_tokens(cell: Any) -> List[str]:
    return [t.strip().lower()
            for t in re.split(r"[/|;,]+", str(cell or ""))
            if t.strip()]

_SOIL_CANON = {"zand", "klei", "leem", "veen"}
_RE_ALL = re.compile(r"\balle\s+grondsoorten\b", re.I)

def _canon_soil_token(tok: str) -> Optional[str]:
    t = str(tok or "").strip().lower()
    if not t:
        return None
    t = t.replace("ö", "o")
    if _RE_ALL.search(t):
        return "__ALL__"
    if re.search(r"\b(loess|loss|löss|leem|zavel)\b", t):
        return "leem"
    if re.search(r"\bdekzand\b|\bzand\b", t):
        return "zand"
    if re.search(r"\bklei\b", t):
        return "klei"
    if re.search(r"\bveen\b", t):
        return "veen"
    return None

def _ebben_grounds_to_cats(gs: Any) -> set[str]:
    raw = re.split(r"[|/;,]+", str(gs or ""))
    cats: set[str] = set()
    saw_all = False
    for r in raw:
        c = _canon_soil_token(r)
        if c == "__ALL__":
            saw_all = True
        elif c:
            cats.add(c)
    return set(_SOIL_CANON) if saw_all else cats

def _row_bodem_cats(row: pd.Series) -> set[str]:
    cats: set[str] = set()
    if "bodem" in row:
        for t in re.split(r"[|/;]+", str(row.get("bodem") or "")):
            c = _canon_soil_token(t)
            if c and c != "__ALL__":
                cats.add(c)
    cats |= _ebben_grounds_to_cats(row.get("grondsoorten", ""))
    return cats

def _match_bodem_row(row: pd.Series, keuzes: List[str]) -> bool:
    if not keuzes:
        return True
    want = {_canon_soil_token(k) or str(k).strip().lower() for k in keuzes}
    want = {w for w in want if w in _SOIL_CANON}
    if not want:
        return True
    have = _row_bodem_cats(row)
    return bool(have & want)

# ───────────────────── app + cleaners

# --- Kennisdocument: locatiecontext (YAML/JSON) ---
_CONTEXT_PATH = os.environ.get("CONTEXT_DESCRIPTIONS_PATH", "context_descriptions.yaml")

def _resolve_context_path(path: str) -> str:
    """Zoek context_descriptions.yaml robuust (cwd, map van api.py, en optioneel submap Plantwijs)."""
    p = str(path or "").strip() or "context_descriptions.yaml"
    cand = [
        Path(p),
        Path.cwd() / p,
        Path(__file__).resolve().parent / p,
        Path(__file__).resolve().parent / "Plantwijs" / p,
    ]
    for c in cand:
        try:
            if c.exists() and c.is_file():
                return str(c)
        except Exception:
            continue
    return str(cand[0])


def _normalize_key(value: str) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\(.*?\)", "", s)  # verwijder haakjesinhoud
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _parse_simple_yaml(raw: str) -> dict:
    """Best-effort YAML parser voor onze vaste kennisdocument-structuur.

    Waarom: op Render is PyYAML niet altijd geïnstalleerd. Ons kennisdocument gebruikt
    een beperkt YAML-subset: nested mappings via indentatie, folded blocks (>) en
    lijsten met '- item'. Deze parser dekt precies dat en faalt 'soft' ({} bij errors).

    Ondersteund:
    - keys: value
    - nested dicts via indentatie (2 spaties of meer)
    - folded blocks: 'key: >' of literal blocks: 'key: |'
    - lijsten: 'key:' gevolgd door '- ...' regels
    """
    try:
        lines = raw.splitlines()
        # verwijder BOM en trim endspaces
        lines = [ln.replace("\ufeff", "").rstrip("\n\r") for ln in lines]
        root: dict = {}
        stack = [(0, root)]  # (indent, container)
        i = 0

        def current_container(indent: int):
            nonlocal stack
            while stack and indent < stack[-1][0]:
                stack.pop()
            return stack[-1][1] if stack else root

        while i < len(lines):
            line = lines[i]
            if not line.strip() or line.lstrip().startswith("#"):
                i += 1
                continue
            indent = len(line) - len(line.lstrip(" "))
            stripped = line.strip()

            # list item (must attach to last key as list)
            if stripped.startswith("- "):
                # find nearest list container
                cont = current_container(indent)
                if isinstance(cont, list):
                    cont.append(stripped[2:].strip())
                    i += 1
                    continue
                # if container is dict, we cannot place list item without a key
                i += 1
                continue

            # key: value
            if ":" not in stripped:
                i += 1
                continue
            key, rest = stripped.split(":", 1)
            key = key.strip()
            rest = rest.lstrip(" ")

            cont = current_container(indent)
            if not isinstance(cont, dict):
                i += 1
                continue

            # nested mapping start
            if rest == "":
                # peek next non-empty to decide dict vs list
                j = i + 1
                while j < len(lines) and (not lines[j].strip() or lines[j].lstrip().startswith("#")):
                    j += 1
                if j < len(lines):
                    next_ln = lines[j]
                    next_indent = len(next_ln) - len(next_ln.lstrip(" "))
                    next_stripped = next_ln.strip()
                    if next_indent > indent and next_stripped.startswith("- "):
                        new_list: list = []
                        cont[key] = new_list
                        stack.append((indent + 1, new_list))
                    elif next_indent > indent:
                        new_dict: dict = {}
                        cont[key] = new_dict
                        stack.append((indent + 1, new_dict))
                    else:
                        cont[key] = {}
                else:
                    cont[key] = {}
                i += 1
                continue

            # folded or literal block
            if rest in (">", "|", ">|", "|-","|-",">-"):
                block_kind = rest[0]  # '>' or '|'
                block_lines = []
                i += 1
                # collect indented block lines
                while i < len(lines):
                    ln2 = lines[i]
                    if not ln2.strip():
                        block_lines.append("")
                        i += 1
                        continue
                    ind2 = len(ln2) - len(ln2.lstrip(" "))
                    if ind2 <= indent:
                        break
                    block_lines.append(ln2.strip())
                    i += 1
                if block_kind == ">":
                    # folded: join with spaces, preserve paragraph breaks on empty lines
                    out = []
                    para = []
                    for bl in block_lines:
                        if bl == "":
                            if para:
                                out.append(" ".join(para).strip())
                                para = []
                            out.append("")
                        else:
                            para.append(bl)
                    if para:
                        out.append(" ".join(para).strip())
                    text = "\n".join(out).strip()
                else:
                    text = "\n".join(block_lines).strip()
                cont[key] = text
                continue

            # simple scalar
            # strip surrounding quotes if present
            val = rest
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            cont[key] = val
            i += 1

        return root if isinstance(root, dict) else {}
    except Exception:
        return {}

def _load_context_db() -> dict:
    """Laadt context_descriptions.yaml. Ondersteunt:
    - echte YAML (als PyYAML beschikbaar is)
    - JSON (wat ook geldige YAML is)
    Faalt nooit hard: bij problemen wordt {} teruggegeven.
    """
    path = _resolve_context_path(_CONTEXT_PATH)
    try:
        if not os.path.exists(path):
            return {}
        raw = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
        if not raw:
            return {}
        try:
            import yaml  # type: ignore
            data = yaml.safe_load(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            pass
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            # Laatste fallback: parse beperkte YAML-subset zonder extra dependencies
            data = _parse_simple_yaml(raw)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}

CONTEXT_DB = _load_context_db()
try:
    _secs = ', '.join([f"{k}({len(v)})" for k,v in (CONTEXT_DB or {}).items() if isinstance(v, dict)])
    print(f"[CONTEXT] geladen: {_secs} uit {_resolve_context_path(_CONTEXT_PATH)}")
except Exception:
    pass


def _context_lookup(section: str, label: str) -> dict | None:
    sec = (CONTEXT_DB or {}).get(section, {})
    if not isinstance(sec, dict):
        return None
    key = _normalize_key(label)
    if key and key in sec and isinstance(sec[key], dict):
        return sec[key]
    want = str(label or "").strip().lower()
    # fallback: splits zoals 'stroomrug of stroomgordel' / 'stroomrug, oeverwal'
    if want:
        parts = re.split(r"\s*(?:,|/|\bor\b|\bof\b|\ben\b)\s*", want)
        for p in parts:
            pk = _normalize_key(p)
            if pk and pk in sec and isinstance(sec[pk], dict):
                return sec[pk]
    if want:
        for _k, v in sec.items():
            if isinstance(v, dict) and str(v.get("titel", "")).strip().lower() == want:
                return v
    return None

def _first_sentence(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", s, maxsplit=1)
    return parts[0].strip()

app = FastAPI(title="PlantWijs API v3.9.7")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET","POST"], allow_headers=["*"])


@app.on_event("startup")
def _startup_warm_nsn():
    """NSN is groot; op Render laden we dit niet volledig in RAM.

    We controleren de bron en proberen (indien nodig) een snelle on-disk index te bouwen,
    zodat klik-lookups direct snel zijn.
    """
    try:
        kind, path, member = _resolve_nsn_source()
        if kind == "zip":
            print(f"[NSN] bron: ZIP {os.path.basename(path)} :: {member}")
        elif kind == "geojson":
            print(f"[NSN] bron: {os.path.basename(path)}")
        else:
            print("[NSN] bron: niet gevonden (laag/klikinfo NSN uitgeschakeld)")
            return

        # Bouw/valideer index (in /tmp). Kan bij eerste cold start even duren, daarna razendsnel.
        ok = _ensure_nsn_index()
        if ok:
            print("[NSN] index klaar")
        else:
            print("[NSN] index niet beschikbaar; fallback = stream-scan (traag)")
    except Exception as e:
        print("[NSN] startup fout:", e)


def _clean(o: Any) -> Any:
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k:_clean(v) for k,v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    try:
        if pd.isna(o):
            return None
    except Exception:
        pass
    return o

# ───────────────────── API: diagnose/meta
@app.get("/api/wms_meta")
def api_wms_meta():
    return JSONResponse(_clean(_WMSMETA))


@app.get("/api/diag/data")
def api_diag_data():
    df = get_df()
    return JSONResponse(_clean({
        "count": int(len(df)),
        "columns": list(df.columns),
        "source": _CACHE.get("path"),
        "source_type": _CACHE.get("source"),
        "sample": df[["naam","wetenschappelijke_naam"]].head(5).to_dict(orient="records") if "naam" in df.columns else [],
    }))

@app.get("/api/nsn")
def api_nsn():
    """
    Retourneer GeoJSON voor Natuurlijk Systeem Nederland (NSN) als vectorlaag.

    Belangrijk: dit bestand is erg groot. Daarom streamen we de bytes (geen json.load in RAM).
    Bron:
      - data/nsn_natuurlijk_systeem.geojson (dev), of
      - een .zip in data/ met een .geojson erin (prod), bijv. data/LBK_BKNSN_2023.zip
    """
    kind, path, member = _resolve_nsn_source()
    if kind == "missing":
        return JSONResponse({"error": "nsn_source_not_found"}, status_code=404)

    def _iter_bytes():
        try:
            with _open_nsn_bytes() as bf:
                while True:
                    chunk = bf.read(1024 * 1024)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            # Stream errors zijn lastig aan client te melden; loggen is het best wat kan.
            print("[NSN] stream fout:", e)
            return

    return StreamingResponse(_iter_bytes(), media_type=FMT_JSON)



@contextmanager
def _open_nsn_bytes():
    """Open de NSN-geojson als bytes-stream (los bestand of uit ZIP)."""
    kind, path, member = _resolve_nsn_source()
    if kind == "geojson":
        f = open(path, "rb")
        try:
            yield f
        finally:
            try:
                f.close()
            except Exception:
                pass
        return

    if kind == "zip":
        zf = zipfile.ZipFile(path, "r")
        bf = zf.open(member, "r")
        try:
            yield bf
        finally:
            try:
                bf.close()
            except Exception:
                pass
            try:
                zf.close()
            except Exception:
                pass
        return

    raise FileNotFoundError("NSN bron niet gevonden. Voeg een .zip met .geojson toe in PlantWijs/data/.")


def _iter_nsn_features():
    """
    Stream features uit een (grote) GeoJSON FeatureCollection zonder alles in RAM te laden.

    We zoeken de 'features' array en decoderen Feature-objecten één voor één met json.JSONDecoder.raw_decode().
    """
    decoder = json.JSONDecoder()
    with _open_nsn_bytes() as bf:
        tf = io.TextIOWrapper(bf, encoding="utf-8", errors="ignore")
        buf = ""
        in_features = False
        pos = 0

        while True:
            chunk = tf.read(1024 * 256)  # 256KB tekst
            if not chunk:
                break
            buf += chunk

            if not in_features:
                idx = buf.find('"features"')
                if idx == -1:
                    # houd buffer beperkt
                    if len(buf) > 2_000_000:
                        buf = buf[-1_000_000:]
                    continue
                # vind de '[' na "features":
                br = buf.find("[", idx)
                if br == -1:
                    continue
                in_features = True
                pos = br + 1

            # decode features
            while True:
                # skip whitespace/commas
                n = len(buf)
                while pos < n and buf[pos] in " \r\n\t,":
                    pos += 1
                if pos >= n:
                    break
                if buf[pos] == "]":
                    return  # einde array

                try:
                    obj, end = decoder.raw_decode(buf, pos)
                    pos = end
                    if isinstance(obj, dict) and obj.get("type") == "Feature":
                        yield obj
                except json.JSONDecodeError:
                    # niet genoeg data in buffer → lees verder
                    break

            # trim buffer om geheugen laag te houden
            if pos > 1_000_000:
                buf = buf[pos:]
                pos = 0



def _point_in_polygon(px: float, py: float, ring) -> bool:
    """
    Standaard ray‑casting point‑in‑polygon test op basis van de buitenring.
    """
    inside = False
    n = len(ring)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        # Kijk of de horizontale lijn door het segment gaat
        if ((y1 > py) != (y2 > py)):
            x_intersect = (x2 - x1) * (py - y1) / (y2 - y1 + 1e-9) + x1
            if px < x_intersect:
                inside = not inside
    return inside



# ───────────────────── NSN (Natuurlijk Systeem Nederland) — snelle on-disk index
import sqlite3
import zlib
import hashlib
import threading

NSN_INDEX_DIR = os.path.join(tempfile.gettempdir(), "plantwijs_nsn")
NSN_INDEX_DB = os.path.join(NSN_INDEX_DIR, "nsn_index.sqlite")
_NSN_INDEX_LOCK = threading.Lock()

def _nsn_source_signature() -> str:
    """Unieke signature van de NSN-bron zodat we index kunnen hergebruiken."""
    kind, path, member = _resolve_nsn_source()
    if kind == "missing":
        return "missing"
    try:
        st = os.stat(path) if path else None
        mtime = int(st.st_mtime) if st else 0
        size = int(st.st_size) if st else 0
    except Exception:
        mtime = 0
        size = 0
    raw = f"{kind}|{path}|{member or ''}|{mtime}|{size}|RD={int(bool(NSN_GEOJSON_IS_RD))}"
    return hashlib.sha1(raw.encode("utf-8", errors="ignore")).hexdigest()

def _db_connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path, timeout=60)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA temp_store=MEMORY;")
    con.execute("PRAGMA cache_size=-20000;")  # ~20MB cache (negatief = KB)
    return con

def _ensure_nsn_index() -> bool:
    """Zorg dat de NSN index bestaat en bij de huidige bron hoort."""
    kind, _, _ = _resolve_nsn_source()
    if kind == "missing":
        return False

    os.makedirs(NSN_INDEX_DIR, exist_ok=True)
    sig = _nsn_source_signature()

    with _NSN_INDEX_LOCK:
        # snelle check: bestaat DB + meta signature match?
        if os.path.exists(NSN_INDEX_DB):
            try:
                con = _db_connect(NSN_INDEX_DB)
                try:
                    con.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);")
                    row = con.execute("SELECT value FROM meta WHERE key='sig'").fetchone()
                    if row and row[0] == sig:
                        return True
                finally:
                    con.close()
            except Exception:
                pass  # rebuild

        # rebuild
        t0 = time.time()
        try:
            if os.path.exists(NSN_INDEX_DB):
                try:
                    os.remove(NSN_INDEX_DB)
                except Exception:
                    pass
            con = _db_connect(NSN_INDEX_DB)
            try:
                con.execute("CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);")
                con.execute("CREATE TABLE feats(id INTEGER PRIMARY KEY, label TEXT, geom BLOB, bbox_area REAL);")
                # RTree index op bbox
                con.execute("CREATE VIRTUAL TABLE rtree USING rtree(id, minx, maxx, miny, maxy);")

                def _bbox_of_coords(coords) -> tuple[float,float,float,float] | None:
                    minx = miny = float("inf")
                    maxx = maxy = float("-inf")
                    def _acc(ring):
                        nonlocal minx,miny,maxx,maxy
                        for x,y in ring:
                            if x < minx: minx = x
                            if y < miny: miny = y
                            if x > maxx: maxx = x
                            if y > maxy: maxy = y
                    # coords kan Polygon of MultiPolygon structuur hebben
                    if not coords:
                        return None
                    # Polygon: [rings...]
                    if isinstance(coords[0][0], (int,float)):
                        # ring direct
                        _acc(coords)
                    else:
                        # rings of polygons
                        for part in coords:
                            if not part:
                                continue
                            # part kan ring of polygon
                            if part and isinstance(part[0][0], (int,float)):
                                _acc(part)
                            else:
                                # polygon -> rings
                                for ring in part:
                                    if ring:
                                        _acc(ring)
                    if minx == float("inf"):
                        return None
                    return (minx, miny, maxx, maxy)

                def _label_from_props(props: dict) -> str | None:
                    if not props:
                        return None
                    # normaliseer keys
                    norm = {}
                    for k, v in props.items():
                        if k is None:
                            continue
                        kk = str(k).strip().lower()
                        if kk and kk not in norm:
                            norm[kk] = v
                    for k in ("subtype_na", "subtype", "subtype_naam"):
                        v = norm.get(k)
                        if v is not None:
                            s = str(v).strip()
                            if s:
                                return s
                    for k in ("nsn_naam","naam","natuurlijk_systeem"):
                        v = norm.get(k)
                        if v is not None:
                            s = str(v).strip()
                            if s:
                                return s
                    v = norm.get("bknsn_code")
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                    return None

                cur = con.cursor()
                n = 0
                batch = 0
                for ft in _iter_nsn_features():
                    g = (ft or {}).get("geometry") or {}
                    t = g.get("type")
                    coords = g.get("coordinates") or []
                    if not coords:
                        continue
                    bb = None
                    if t == "Polygon":
                        bb = _bbox_of_coords(coords)
                    elif t == "MultiPolygon":
                        bb = _bbox_of_coords(coords)
                    if not bb:
                        continue
                    minx, miny, maxx, maxy = bb
                    bbox_area = float(max(0.0, (maxx-minx)*(maxy-miny)))
                    label = _label_from_props((ft or {}).get("properties") or {})
                    if not label:
                        continue
                    payload = {"type": t, "coordinates": coords}
                    blob = zlib.compress(json.dumps(payload, separators=(",",":")).encode("utf-8"))
                    cur.execute("INSERT INTO feats(label, geom, bbox_area) VALUES (?,?,?)", (label, sqlite3.Binary(blob), bbox_area))
                    fid = cur.lastrowid
                    cur.execute("INSERT INTO rtree(id, minx, maxx, miny, maxy) VALUES (?,?,?,?,?)", (fid, float(minx), float(maxx), float(miny), float(maxy)))
                    n += 1
                    batch += 1
                    if batch >= 500:
                        con.commit()
                        batch = 0
                con.commit()
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('sig',?)", (sig,))
                con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('built_at',?)", (str(int(time.time())),))
                con.commit()
                dt = time.time() - t0
                print(f"[NSN] index gebouwd: {n} features in {dt:.1f}s → {NSN_INDEX_DB}")
                return True
            finally:
                con.close()
        except Exception as e:
            print("[NSN] index build fout:", e)
            return False

def _nsn_lookup_index(px: float, py: float) -> Optional[str]:
    """Zoek NSN-label via on-disk RTree index."""
    if not _ensure_nsn_index():
        return None
    try:
        con = _db_connect(NSN_INDEX_DB)
        try:
            # Kandidaten op bbox (meest specifieke eerst: kleinste bbox_area)
            rows = con.execute(
                "SELECT r.id FROM rtree r JOIN feats f ON f.id=r.id "
                "WHERE r.minx<=? AND r.maxx>=? AND r.miny<=? AND r.maxy>=? "
                "ORDER BY f.bbox_area ASC LIMIT 80",
                (px, px, py, py),
            ).fetchall()
            for (fid,) in rows:
                row = con.execute("SELECT label, geom FROM feats WHERE id=?", (fid,)).fetchone()
                if not row:
                    continue
                label, blob = row
                try:
                    payload = json.loads(zlib.decompress(blob).decode("utf-8", errors="ignore"))
                except Exception:
                    continue
                gtype = payload.get("type")
                coords = payload.get("coordinates") or []

                def _in_poly(poly_coords) -> bool:
                    if not poly_coords:
                        return False
                    outer = poly_coords[0]
                    if not _point_in_polygon(px, py, outer):
                        return False
                    for hole in poly_coords[1:]:
                        if hole and _point_in_polygon(px, py, hole):
                            return False
                    return True

                ok = False
                if gtype == "Polygon":
                    ok = _in_poly(coords)
                elif gtype == "MultiPolygon":
                    for poly in coords:
                        if _in_poly(poly):
                            ok = True
                            break
                if ok:
                    return str(label)
        finally:
            con.close()
    except Exception as e:
        print("[NSN] lookup index fout:", e)
    return None


def nsn_from_point(lat: float, lon: float) -> Optional[str]:
    """Bepaal NSN (Natuurlijk Systeem Nederland) op basis van een klikpunt.

    Snelheid:
      - primair via on-disk RTree index (SQLite in /tmp) → snelle lookups
      - fallback: stream-scan (alleen als index niet kan worden gebouwd)
    """
    kind, _, _ = _resolve_nsn_source()
    if kind == "missing":
        return None

    # Transformeer klikpunt naar zelfde CRS als de GeoJSON
    if NSN_GEOJSON_IS_RD:
        px, py = TX_WGS84_RD.transform(lon, lat)
    else:
        px, py = lon, lat

    # 1) snelle index
    label = _nsn_lookup_index(px, py)
    if label:
        return label

    # 2) fallback: stream door features (langzaam, maar werkt altijd)
    try:
        for ft in _iter_nsn_features():
            g = (ft or {}).get("geometry") or {}
            t = g.get("type")
            coords = g.get("coordinates") or []
            if not coords:
                continue

            props = (ft or {}).get("properties") or {}

            # normaliseer keys
            norm = {}
            for k, v in props.items():
                if k is None:
                    continue
                kk = str(k).strip().lower()
                if kk and kk not in norm:
                    norm[kk] = v

            def _label_from_props() -> Optional[str]:
                for k in ("subtype_na", "subtype", "subtype_naam"):
                    v = norm.get(k)
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                for k in ("nsn_naam", "naam", "natuurlijk_systeem"):
                    v = norm.get(k)
                    if v is not None:
                        s = str(v).strip()
                        if s:
                            return s
                v = norm.get("bknsn_code")
                if v is not None:
                    s = str(v).strip()
                    if s:
                        return s
                return None

            def _test_polygon(poly_coords) -> Optional[str]:
                if not poly_coords:
                    return None
                outer = poly_coords[0]
                if not _point_in_polygon(px, py, outer):
                    return None
                for hole in poly_coords[1:]:
                    if hole and _point_in_polygon(px, py, hole):
                        return None
                return _label_from_props()

            found: Optional[str] = None
            if t == "Polygon":
                found = _test_polygon(coords)
            elif t == "MultiPolygon":
                for poly in coords:
                    found = _test_polygon(poly)
                    if found:
                        break
            if found:
                return found
    except Exception as e:
        print("[NSN] fout bij fallback lookup:", e)

    return None


@app.get("/api/diag/featureinfo")
def api_diag(service: str = Query(..., pattern="^(bodem|gt|ghg|glg|fgr)$"), lat: float = Query(...), lon: float = Query(...)):
    if service == "fgr":
        return JSONResponse({"fgr": fgr_from_point(lat, lon)})
    base = {"bodem": BODEM_WMS, "gt": GWD_WMS, "ghg": GWD_WMS, "glg": GWD_WMS}[service]
    layer = _WMSMETA.get(service, {}).get("layer")
    props = _wms_getfeatureinfo(base, layer, lat, lon)
    return JSONResponse(_clean({"base": base, "layer": layer, "props": props}))

# ───────────────────── filtering core
def _apply_status_nl_filter(
    df: pd.DataFrame,
    inheems_only: bool,
    toon_inheems: Optional[bool],
    toon_ingeburgerd: Optional[bool],
    toon_exoot: Optional[bool],
) -> pd.DataFrame:
    """Filter op status_nl (inheems/ingeburgerd/exoot).

    Belangrijk:
    - Als de UI nog géén status-checkboxes meestuurt (toon_* zijn allemaal None),
      dan filteren we NIET en laten we alles zien (backwards compatible).
    - inheems_only=True forceert altijd alleen 'inheems'.
    - Fallback: als 'status_nl' ontbreekt, gebruiken we legacy kolom 'inheems' (ja/nee).
    """
    # legacy fallback
    if "status_nl" not in df.columns:
        if inheems_only and "inheems" in df.columns:
            return df[df["inheems"].astype(str).str.strip().str.lower() == "ja"]
        return df

    # forceer strikt inheems
    if inheems_only:
        s = df["status_nl"].astype(str).str.strip().str.lower()
        return df[s == "inheems"]

    # Als de UI nog niets meestuurt: niet filteren (toon alles)
    if toon_inheems is None and toon_ingeburgerd is None and toon_exoot is None:
        return df

    allowed = set()
    if toon_inheems:
        allowed.add("inheems")
    if toon_ingeburgerd:
        allowed.add("ingeburgerd")
    if toon_exoot:
        allowed.add("exoot")

    if not allowed:
        # niets aangevinkt -> geen statusfilter toepassen (toon alles)
        return df

    # alle drie aangevinkt -> toon alles (incl. onbekend/leeg)
    if allowed == {"inheems", "ingeburgerd", "exoot"}:
        return df

    s = df["status_nl"].astype(str).str.strip().str.lower()
    return df[s.isin({a.lower() for a in allowed})]

def _filter_plants_df(
    q: str,
    inheems_only: bool,
    toon_inheems: Optional[bool],
    toon_ingeburgerd: Optional[bool],
    toon_exoot: Optional[bool],
    exclude_invasief: bool,
    licht: List[str],
    vocht: List[str],
    bodem: List[str],
    beplantingstype: List[str],
    sort: str,
    desc: bool,
) -> pd.DataFrame:
    df = get_df()

    def _has_any(cell: Any, choices: List[str]) -> bool:
        if not choices:
            return True
        tokens = {
            t.strip().lower()
            for t in re.split(r"[;/|]+", str(cell or ""))
            if t.strip()
        }
        want = {str(w).strip().lower() for w in choices if str(w).strip()}
        return bool(tokens & want)

    if q:
        df = df[df.apply(
            lambda r: _contains_ci(r.get("naam"), q) or _contains_ci(r.get("wetenschappelijke_naam"), q),
            axis=1
        )]

    # Afgeleid beplantingstype (boom/heester) + filter
    def _derive_ptype_row(r: pd.Series) -> str:
        def _clean(v: Any) -> str:
            # NaN/None/lege strings als leeg behandelen
            if v is None:
                return ""
            try:
                if pd.isna(v):
                    return ""
            except Exception:
                pass
            s = str(v).strip()
            if s.lower() in ("nan", "none", "null"):
                return ""
            return s

        boom_src = _clean(r.get("beplantingstypes_boomtypen"))
        overig_src = _clean(r.get("beplantingstypes_overige_beplanting"))

        types: List[str] = []
        if boom_src:
            types.append("boom")
        if overig_src:
            types.append("heester")

        return " / ".join(types)

    if beplantingstype:
        df = df.copy()
        if "beplantingstype" not in df.columns:
            df["beplantingstype"] = df.apply(_derive_ptype_row, axis=1)
        df = df[df["beplantingstype"].apply(lambda v: _has_any(v, beplantingstype))]

    df = _apply_status_nl_filter(df, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot)
    if exclude_invasief and "invasief" in df.columns:
        df = df[(df["invasief"].astype(str).str.lower() != "ja") | (df["invasief"].isna())]

    if licht:
        df = df[df["standplaats_licht"].apply(lambda v: _has_any(v, licht))]
    if vocht:
        df = df[df["vocht"].apply(lambda v: _has_any(v, vocht))]
    if bodem:
        df = df[df.apply(lambda r: _match_bodem_row(r, bodem), axis=1)]

    if sort in df.columns:
        df = df.sort_values(sort, ascending=not desc)

    return df

# ───────────────────── API: data
@app.get("/api/plants")
def api_plants(
    q: str = Query(""),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    beplantingstype: List[str] = Query(default=[]),
    limit: Optional[int] = Query(None),  # genegeerd → geen limiet
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    # Zorg dat beplantingstype kolom bestaat voor UI
    if "beplantingstype" not in df.columns:
        df = df.copy()
        def _pt(r):
            boom_src = str(r.get("beplantingstypes_boomtypen") or "").strip()
            overig_src = str(r.get("beplantingstypes_overige_beplanting") or "").strip()
            types = []
            if boom_src: types.append("boom")
            if overig_src: types.append("heester")
            return " / ".join(types)
        df["beplantingstype"] = df.apply(_pt, axis=1)
    cols = [c for c in (
        "naam","wetenschappelijke_naam","beplantingstype","status_nl","invasief",
        "standplaats_licht","vocht","bodem",
        "ellenberg_l","ellenberg_f","ellenberg_t","ellenberg_n","ellenberg_r","ellenberg_s",
        "ellenberg_l_min","ellenberg_l_max","ellenberg_f_min","ellenberg_f_max",
        "ellenberg_t_min","ellenberg_t_max","ellenberg_n_min","ellenberg_n_max",
        "ellenberg_r_min","ellenberg_r_max","ellenberg_s_min","ellenberg_s_max",
        "hoogte","breedte","winterhardheidszone","grondsoorten","ecowaarde"
    ) if c in df.columns]
    items = df[cols].to_dict(orient="records")
    return JSONResponse(_clean({"count": int(len(df)), "items": items}))

# ───────────────────── API: export
@app.get("/export/csv")
def export_csv(
    q: str = Query(""),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    beplantingstype: List[str] = Query(default=[]),
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    filename = "plantwijs_export.csv"
    return StreamingResponse(iter([buf.getvalue()]),
                             media_type="text/csv",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})

@app.get("/export/xlsx")
def export_xlsx(
    q: str = Query(""),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    beplantingstype: List[str] = Query(default=[]),
    sort: str = Query("naam"),
    desc: bool = Query(False),
):
    df = _filter_plants_df(q, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot, exclude_invasief, licht, vocht, bodem, beplantingstype, sort, desc)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        df.to_excel(xw, index=False, sheet_name="PlantWijs")
    buf.seek(0)
    filename = "plantwijs_export.xlsx"
    return StreamingResponse(buf,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})

# (Optioneel maar handig) Admin-reload endpoint
@app.get("/api/admin/reload")
def api_admin_reload(key: str = Query(...)):
    """Wist de in-memory cache en haalt de remote CSV opnieuw op.
    Beveiligd met een simpele key in env: PLANTWIJS_ADMIN_KEY
    """
    admin_key = os.getenv("PLANTWIJS_ADMIN_KEY", "")
    if not admin_key or key != admin_key:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    try:
        _CACHE.update({"df": None, "mtime": None, "path": None})
        if DATA_URL:
            _download_if_needed(DATA_URL)  # prefetch
        return JSONResponse({"ok": True, "msg": "dataset cache cleared/refreshed"})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

# ───────────────────── API: advies/geo
@app.get("/advies/geo")
def advies_geo(
    lat: float = Query(...),
    lon: float = Query(...),
    inheems_only: bool = Query(False),
    toon_inheems: Optional[bool] = Query(None),
    toon_ingeburgerd: Optional[bool] = Query(None),
    toon_exoot: Optional[bool] = Query(None),
    exclude_invasief: bool = Query(True),
    limit: Optional[int] = Query(None),  # genegeerd
):
    t0 = time.time()
    fgr = fgr_from_point(lat, lon) or "Onbekend"
    nsn_val = nsn_from_point(lat, lon)
    bodem_raw, _props_bodem = bodem_from_bodemkaart(lat, lon)
    vocht_raw, _props_gwt, gt_code = vocht_from_gwt(lat, lon)
    ahn_val, _props_ahn = ahn_from_wms(lat, lon)
    gmm_val, _props_gmm = gmm_from_wms(lat, lon)

    bodem_val = bodem_raw
    vocht_val = vocht_raw

    def _has_any(cell: Any, choices: List[str]) -> bool:
        if not choices:
            return True
        tokens = {t.strip().lower() for t in re.split(r"[;/|]+", str(cell or "")) if t.strip()}
        want = {w.strip().lower() for w in choices if str(w).strip()}
        return bool(tokens & want)

    df = get_df()
    df = _apply_status_nl_filter(df, inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot)
    if exclude_invasief and "invasief" in df.columns:
        df = df[(df["invasief"].astype(str).str.lower() != "ja") | (df["invasief"].isna())]

    if vocht_val:
        df = df[df["vocht"].apply(lambda v: _has_any(v, [vocht_val]))]
    if bodem_val:
        df = df[df.apply(lambda r:
                         _has_any(r.get("bodem", ""), [bodem_val]) or
                         _has_any(r.get("grondsoorten", ""), [bodem_val]),
                         axis=1)]

    cols = [c for c in (
        "naam","wetenschappelijke_naam","inheems","invasief",
        "standplaats_licht","vocht","bodem",
        "ellenberg_l","ellenberg_f","ellenberg_t","ellenberg_n","ellenberg_r","ellenberg_s",
        "hoogte","breedte","winterhardheidszone","grondsoorten","ecowaarde"
    ) if c in df.columns]
    items = df[cols].to_dict(orient="records")

    out = {
        "fgr": fgr,
        "bodem": bodem_val,
        "bodem_bron": "BRO Bodemkaart WMS" if bodem_raw else "onbekend",
        "gt_code": gt_code,
        "vocht": vocht_raw,
        "vocht_bron": "BRO Gt/GLG WMS" if vocht_raw else "onbekend",
        "ahn": ahn_val,
        "ahn_bron": "PDOK AHN WMS (DTM 0.5m)" if ahn_val else "onbekend",
        "gmm": gmm_val,
        "gmm_bron": "BRO Geomorfologische kaart (GMM) WMS" if gmm_val else "onbekend",
        "nsn": nsn_val,
        "advies": items,
        "elapsed_ms": int((time.time()-t0)*1000),
    }
    return JSONResponse(_clean(out))

# ───────────────────── UI

# ───────────────────── API: advies/pdf (download 1 PDF per klik)
@app.get("/advies/pdf")
def advies_pdf(
    lat: float = Query(...),
    lon: float = Query(...),
    # optionele overrides vanuit UI (checkboxes)
    licht: List[str] = Query(default=[]),
    vocht: List[str] = Query(default=[]),
    bodem: List[str] = Query(default=[]),
    exclude_invasief: bool = Query(True),
):
    """
    Genereert een locatierapport als PDF (encyclopedische stijl):
    - Kernsamenvatting bovenaan (scanbaar)
    - Locatiecontext (kaarten) kort
    - Toelichting (encyclopedisch) per kaartlaag met bronnen (indien aanwezig in context_descriptions.yaml)
    - Soortentabel (geschikte soorten)
    """
    # ------------------------
    # 1) Context uit kaarten
    # ------------------------
    fgr = fgr_from_point(lat, lon) or "Onbekend"
    nsn_val = nsn_from_point(lat, lon) or ""
    bodem_raw, _props_bodem = bodem_from_bodemkaart(lat, lon)
    vocht_raw, _props_gwt, gt_code = vocht_from_gwt(lat, lon)
    ahn_val, _props_ahn = ahn_from_wms(lat, lon)
    gmm_val, _props_gmm = gmm_from_wms(lat, lon)

    # Waarden die we tonen + gebruiken voor filtering
    bodem_val = (bodem[0] if bodem else bodem_raw) or ""
    vocht_val = (vocht[0] if vocht else vocht_raw) or ""
    licht_vals = licht[:] if licht else []  # kan leeg zijn

    # ------------------------
    # 2) Plantselectie (zelfde logica als UI)
    # ------------------------
    df = get_df()

    # Alleen inheems + ingeburgerd
    if "status_nl" in df.columns:
        s = df["status_nl"].astype(str).str.lower().str.strip()
        df = df[s.isin(["inheems", "ingeburgerd"])]
    else:
        if "inheems" in df.columns:
            df = df[df["inheems"].astype(str).str.lower().str.strip() == "ja"]

    if exclude_invasief and "invasief" in df.columns:
        inv = df["invasief"].astype(str).str.lower().str.strip()
        df = df[(inv != "ja") | (df["invasief"].isna())]

    # Filters
    if licht_vals and "standplaats_licht" in df.columns:
        df = df[df["standplaats_licht"].apply(lambda v: any(x.strip().lower() in str(v).lower() for x in licht_vals))]
    if vocht_val and "vocht" in df.columns:
        vv = vocht_val.strip().lower()
        df = df[df["vocht"].apply(lambda v: vv in str(v).lower())]

    # Bodem: gebruik dezelfde matchfunctie als de UI
    if bodem_val:
        df = df[df.apply(lambda r: _match_bodem_row(r, [bodem_val]), axis=1)]

    # Sorteer / beperk voor PDF
    if "latin_name" in df.columns:
        df = df.sort_values(by=["latin_name"])
    df_pdf = df.head(2000)

    # ------------------------
    # 3) Kennisitems ophalen
    # ------------------------
    fgr_info = _context_lookup("fgr", fgr)
    gmm_info = _context_lookup("geomorfologie", gmm_val)
    nsn_info = _context_lookup("nsn", nsn_val)
    bodem_info = _context_lookup("bodem", bodem_val or bodem_raw)
    gt_info = _context_lookup("gt", (gt_code or "").lower())

    # ------------------------
    # 3b) Ontwerpprincipes (samenvatting) — optioneel, uit context_descriptions.yaml
    # ------------------------
    def _as_list(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        return []

    def _principes_from_node(node: Any) -> list[str]:
        # Ondersteun schema's:
        # - list[str]
        # - {principes: list[str]}
        # - {regels: list[str]}
        if isinstance(node, dict):
            return _as_list(node.get("principes")) or _as_list(node.get("regels"))
        return _as_list(node)

    ontwerp_bullets: list[str] = []
    try:
        op = (CONTEXT_DB or {}).get("ontwerpprincipes", {})
        if isinstance(op, dict):
            # 1) Algemeen
            ontwerp_bullets += _principes_from_node(op.get("algemeen"))

            # 2) Vochtklasse (op basis van 'vocht_raw' uit BRO/Gt)
            vk = (str(vocht_raw or "").strip().lower() or "")
            vk_map = op.get("vochtklasse", {}) if isinstance(op.get("vochtklasse", {}), dict) else {}
            if vk and isinstance(vk_map, dict):
                ontwerp_bullets += _principes_from_node(vk_map.get(_normalize_key(vk)) or vk_map.get(vk))

            # 3) Bodem (canoniek waar mogelijk)
            bodem_key = (bodem_val or bodem_raw or "").strip()
            bodem_node = op.get("bodem", {}) if isinstance(op.get("bodem", {}), dict) else {}
            if bodem_key and isinstance(bodem_node, dict):
                # probeer eerst canonieke categorie (zand/klei/veen/leem), anders label
                canon = _canon_soil_token(bodem_key) or _canon_soil_token(_normalize_key(bodem_key)) or ""
                if canon and canon in bodem_node:
                    ontwerp_bullets += _principes_from_node(bodem_node.get(canon))
                else:
                    ontwerp_bullets += _principes_from_node(bodem_node.get(_normalize_key(bodem_key)) or bodem_node.get(bodem_key))

            # 4) FGR / Geomorfologie / NSN
            for sec, label in [("fgr", fgr), ("geomorfologie", gmm_val), ("nsn", nsn_val)]:
                sec_node = op.get(sec, {}) if isinstance(op.get(sec, {}), dict) else {}
                if label and isinstance(sec_node, dict):
                    ontwerp_bullets += _principes_from_node(sec_node.get(_normalize_key(label)) or sec_node.get(label))

    except Exception:
        ontwerp_bullets = []

    # Deduplicate, behoud volgorde; en cap voor rapportscanbaarheid
    _seen = set()
    ontwerp_bullets = [b for b in ontwerp_bullets if not (b in _seen or _seen.add(b))]
    ontwerp_bullets = ontwerp_bullets[:7]

    # ------------------------
    # 4) Kernsamenvatting (scanbaar)
    # ------------------------
    kern_zinnen = []
    if fgr and fgr != "Onbekend":
        kern_zinnen.append(f"Deze locatie ligt in het <b>{fgr}</b>.")
    if gmm_val:
        kern_zinnen.append(f"De geomorfologie is <b>{gmm_val}</b>.")
    if nsn_val:
        kern_zinnen.append(f"Het natuurlijke systeem is <b>{nsn_val}</b>.")
    if bodem_val or bodem_raw:
        kern_zinnen.append(f"De bodem is <b>{(bodem_val or bodem_raw)}</b>.")
    if vocht_raw or gt_code:
        kern_zinnen.append(f"De vochttoestand is <b>{(vocht_raw or '—')}</b> (Gt: <b>{(gt_code or '—')}</b>).")
    if ahn_val not in (None, "", "—"):
        kern_zinnen.append(f"De hoogteligging (AHN) is circa <b>{ahn_val}</b> m.")
    advies_snip = _first_sentence(
        (gmm_info or {}).get("betekenis_voor_erfbeplanting", "")
        or (nsn_info or {}).get("betekenis_voor_erfbeplanting", "")
        or (bodem_info or {}).get("beheerimplicaties", "")
        or (bodem_info or {}).get("betekenis_voor_erfbeplanting", "")
    )
    if advies_snip:
        kern_zinnen.append(advies_snip)
    kernsamenvatting = " ".join(kern_zinnen)

    # ------------------------
    # 5) PDF opbouw (modern + encyclopedisch)
    # ------------------------
    buf = BytesIO()

    W, H = A4
    margin = 18 * mm

    # Kleuren
    C_PRIMARY = colors.HexColor("#0F2A43")
    C_MUTED = colors.HexColor("#5C6B7A")
    C_LINE = colors.HexColor("#D8DEE4")
    C_BG = colors.HexColor("#F4F6F8")

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle("PW_Title", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=20, leading=24, textColor=C_PRIMARY, spaceAfter=6)
    style_sub = ParagraphStyle("PW_Sub", parent=styles["Normal"], fontName="Helvetica", fontSize=11, leading=14, textColor=C_MUTED, spaceAfter=10)
    style_h1 = ParagraphStyle("PW_H1", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=14, leading=18, textColor=C_PRIMARY, spaceBefore=10, spaceAfter=6)
    style_h2 = ParagraphStyle("PW_H2", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=C_PRIMARY, spaceBefore=6, spaceAfter=4)
    style_p = ParagraphStyle("PW_P", parent=styles["BodyText"], fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.black, spaceAfter=6)
    style_small = ParagraphStyle("PW_Small", parent=styles["Normal"], fontName="Helvetica", fontSize=9.2, leading=12, textColor=colors.black)
    style_small_muted = ParagraphStyle("PW_SmallMuted", parent=styles["Normal"], fontName="Helvetica", fontSize=9.0, leading=12, textColor=C_MUTED)

    def _safe(s: Any) -> str:
        return (str(s or "").strip())

    def _short(s: Any, n: int = 90) -> str:
        s = _safe(s)
        return s if len(s) <= n else (s[: n - 1] + "…")

    def _on_page(canv: canvas.Canvas, doc):
        canv.saveState()
        bar_h = 14 * mm
        canv.setFillColor(C_PRIMARY)
        canv.rect(0, H - bar_h, W, bar_h, stroke=0, fill=1)
        canv.setFillColor(colors.white)
        canv.setFont("Helvetica-Bold", 10)
        canv.drawString(margin, H - bar_h + 4.2 * mm, "Beplantingswijzer – locatierapport")
        canv.setFont("Helvetica", 9)
        canv.drawRightString(W - margin, H - bar_h + 4.2 * mm, datetime.now().strftime("%Y-%m-%d %H:%M"))

        canv.setStrokeColor(C_LINE)
        canv.setLineWidth(0.5)
        canv.line(margin, margin - 3 * mm, W - margin, margin - 3 * mm)
        canv.setFillColor(C_MUTED)
        canv.setFont("Helvetica", 8)
        canv.drawString(margin, margin - 7 * mm, f"Locatie: {lat:.6f}, {lon:.6f}")
        canv.drawRightString(W - margin, margin - 7 * mm, f"Pagina {doc.page}")
        canv.restoreState()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
        title="Beplantingswijzer – locatierapport",
        author="Beplantingswijzer",
    )
    story: list[Any] = []

    # Titel
    story.append(Paragraph("Beplantingswijzer – locatierapport", style_title))
    story.append(Paragraph(f"Locatie: <b>{lat:.6f}, {lon:.6f}</b>", style_sub))

    # Kernsamenvatting (nieuw)
    story.append(Paragraph("Kernsamenvatting locatie", style_h1))
    story.append(Paragraph(kernsamenvatting or "—", style_p))    # Overzicht blok: kaart + kernwaarden (onder elkaar)
    map_img = _static_map_image(lat, lon, z=17, tiles=2)
    rl_map = None
    if map_img:
        try:
            # Grote kaart op pagina 1
            rl_map = RLImage(map_img, width=180 * mm, height=110 * mm)
        except Exception:
            rl_map = None

    ctx_rows = [
[Paragraph("<b>FGR</b>", style_small_muted), Paragraph(_short(fgr, 120) or "—", style_small)],
        [Paragraph("<b>Geomorfologie (GMM)</b>", style_small_muted), Paragraph(_short(gmm_val, 120) or "—", style_small)],
        [Paragraph("<b>Natuurlijk systeem (NSN)</b>", style_small_muted), Paragraph(_short(nsn_val, 120) or "—", style_small)],
        [Paragraph("<b>Bodem</b>", style_small_muted), Paragraph(_short(bodem_val or bodem_raw, 120) or "—", style_small)],
        [Paragraph("<b>Vochttoestand</b>", style_small_muted), Paragraph(_short(f"{vocht_raw} (Gt: {gt_code or '—'})", 120) if vocht_raw else "—", style_small)],
        [Paragraph("<b>Hoogteligging (AHN)</b>", style_small_muted), Paragraph(_short(ahn_val, 120) if ahn_val not in (None, "", "—") else "—", style_small)],
    ]
    ctx_table = Table(ctx_rows, colWidths=[44 * mm, 76 * mm])
    ctx_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, -1), 0.25, C_LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    # Kaart bovenaan, tabel eronder (pagina 1)
    if rl_map:
        story.append(rl_map)
        story.append(Spacer(1, 6))

    story.append(ctx_table)
    story.append(Spacer(1, 10))

    # Ontwerpuitgangspunten (scanbaar) — komt uit context_descriptions.yaml > ontwerpprincipes
    if ontwerp_bullets:
        story.append(Paragraph("Ontwerpuitgangspunten (samenvatting)", style_h1))
        for i, b in enumerate(ontwerp_bullets, 1):
            story.append(Paragraph(f"<b>{i}.</b> {b}", style_p))
        story.append(Spacer(1, 6))

    # Start de encyclopedische toelichting op een nieuwe pagina
    story.append(PageBreak())

    # Encyclopedische toelichting
    story.append(Paragraph("Toelichting op locatiecontext", style_h1))
    story.append(Paragraph("Onderstaande toelichting geeft de betekenis van de gevonden kaartwaarden en de implicaties voor erf- en landschapsbeplanting.", style_p))
    story.append(Paragraph('De onderstaande toelichting beschrijft dezelfde locatie vanuit verschillende invalshoeken (landschap, vorm, systeem en standplaats). Hierdoor kunnen sommige kenmerken op meerdere plekken terugkomen, telkens met een andere betekenis en schaal.', style_p))

    def _render_section(
        title: str,
        info: dict | None,
        fallback_label: str | None = None,
        category_key: str | None = None,
    ):
        story.append(Paragraph(title, style_h2))
        if not info:
            if fallback_label:
                story.append(Paragraph(f"Geen uitgebreide beschrijving beschikbaar voor: <b>{fallback_label}</b>.", style_small_muted))
            else:
                story.append(Paragraph("Geen uitgebreide beschrijving beschikbaar.", style_small_muted))
            story.append(Spacer(1, 4))
            return

        def add(label: str, key: str):
            val = info.get(key)
            if val:
                story.append(Paragraph(f"<b>{label}.</b> {val}", style_p))

        def _split_paragraphs(text: Any) -> List[str]:
            """Splits een tekst in alinea's (YAML folded blocks of HTML-achtige breaks)."""
            s = str(text or "").strip()
            if not s:
                return []
            # normaliseer HTML breaks naar newlines
            s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
            # split op dubbele newlines
            parts = [p.strip() for p in re.split(r"\n\s*\n+", s) if p.strip()]
            return parts

        # Support meerdere schema's
        add("Kern", "kernsamenenvatting")
        add("Kern", "kernsamenenvatting_kort")
        add("Beschrijving", "beschrijving")
        add("Ontstaansgeschiedenis", "ontstaansgeschiedenis")
        add("Kenmerken", "kenmerken")
        add("Reliëf en vorm", "reliëf_en_vorm")
        add("Systeemwerking", "systeemwerking")
        add("Water en dynamiek", "water_en_dynamiek")
        add("Bodem en water", "bodem_en_water")
        add("Bodem en hydrologie", "bodem_en_hydrologie")
        add("Bodemontwikkeling", "bodemontwikkeling")
        add("Landgebruik en beplanting", "landgebruik_en_beplanting")
        add("Vegetatiestructuur en beplanting", "vegetatiestructuur_en_beplanting")
        add("Beheerimplicaties", "beheerimplicaties")
        add("Betekenis voor erfbeplanting", "betekenis_voor_erfbeplanting")
        add("Betekenis", "betekenis")
        add("Geschikte beplanting", "geschikte_beplanting")

        # Speciaal: na de Gt-toelichting een compacte samenvatting van de 3 alinea's
        # uit 'betekenis_voor_erfbeplanting' (elk gericht op een ander aspect).
        if category_key == "gt":
            betekenis = info.get("betekenis_voor_erfbeplanting")
            paras = _split_paragraphs(betekenis)
            if paras:
                bullets = [_first_sentence(p) for p in paras[:3] if _first_sentence(p)]
                if bullets:
                    story.append(Paragraph("<b>Korte samenvatting (erfbeplanting).</b>", style_p))
                    for i, b in enumerate(bullets, 1):
                        story.append(Paragraph(f"<b>{i}.</b> {b}", style_p))

        bronnen = info.get("bronnen")
        if isinstance(bronnen, list) and bronnen:
            story.append(Paragraph("<b>Bronnen (selectie).</b> " + "; ".join(str(b) for b in bronnen), style_small_muted))

        story.append(Spacer(1, 6))

    _render_section(f"Fysisch Geografische Regio (FGR): {_safe(fgr)}", fgr_info, fgr, category_key="fgr")
    _render_section(f"Geomorfologie (GMM): {_safe(gmm_val)}", gmm_info, gmm_val, category_key="geomorfologie")
    _render_section(f"Natuurlijk systeem (NSN): {_safe(nsn_val)}", nsn_info, nsn_val, category_key="nsn")
    _render_section(f"Bodem: {_safe(bodem_val or bodem_raw)}", bodem_info, (bodem_val or bodem_raw), category_key="bodem")
    _render_section(f"Vochttoestand (Gt): {_safe(gt_code or '—')}", gt_info, (gt_code or "—"), category_key="gt")

    # Planttabel
    story.append(PageBreak())
    story.append(Paragraph("Geschikte soorten (selectie)", style_h1))
    story.append(Paragraph("Overzicht van geschikte bomen/heesters op basis van de gekozen filters en kaartwaarden.", style_p))

    # Kolommen (vaste, begrijpelijke set) — kies de eerste beschikbare bronkolom.
    def _first_col(cands):
        for c in cands:
            if c in df_pdf.columns:
                return c
        return None

    col_wet = _first_col(["wetenschappelijke_naam", "latin_name", "naam"])
    col_nl = _first_col(["naam_nl", "nederlandse_naam"])
    col_status = _first_col(["status_nl", "nsr_status", "status"])
    col_licht = _first_col(["standplaats_licht", "licht"])
    col_vocht = _first_col(["vocht", "standplaats_bodemvochtigheid"])
    col_bodem = _first_col(["grondsoorten", "bodem", "standplaats_grondsoort"])
    col_hoogte = _first_col(["hoogte", "eigenschappen_hoogte"])
    col_breedte = _first_col(["breedte", "eigenschappen_breedte"])

    cols = []
    if col_nl:
        cols.append(("Naam", col_nl, 40 * mm))
    if col_wet:
        cols.append(("Wetenschappelijke naam", col_wet, 48 * mm))
    if col_status:
        cols.append(("Status", col_status, 20 * mm))
    if col_licht:
        cols.append(("Licht", col_licht, 28 * mm))
    if col_vocht:
        cols.append(("Vocht", col_vocht, 26 * mm))
    if col_bodem:
        cols.append(("Bodem", col_bodem, 32 * mm))
    if col_hoogte or col_breedte:
        cols.append(("Maat", "__maat__", 34 * mm))

    header = [Paragraph(f"<b>{h}</b>", style_small) for h, _, _w in cols]
    data = [header]
    for _, row in df_pdf.iterrows():
        row_cells = []
        for _h, k, _w in cols:
            if k == "__maat__":
                h = (str(row.get(col_hoogte, "")) if col_hoogte else "").strip()
                b = (str(row.get(col_breedte, "")) if col_breedte else "").strip()
                maat = " / ".join([x for x in [h, b] if x]) or "—"
                row_cells.append(Paragraph(_short(maat, 60), style_small))
            else:
                row_cells.append(Paragraph(_short(row.get(k, ""), 60) or "—", style_small))
        data.append(row_cells)

    col_widths = [w for _h, _k, w in cols] if cols else [180 * mm]
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), C_PRIMARY),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, C_LINE),
                ("GRID", (0, 0), (-1, -1), 0.25, C_LINE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, C_BG]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(tbl)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)

    headers = {"Content-Disposition": f'inline; filename="beplantingswijzer_locatierapport_{lat:.5f}_{lon:.5f}.pdf"'}
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)



@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = '''
<!doctype html>
<html lang=nl>
<head>
  <meta charset=utf-8>
  <meta name=viewport content="width=device-width, initial-scale=1">
  <title>PlantWijs v3.9.7</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root { --bg:#0b1321; --panel:#0f192e; --muted:#9aa4b2; --fg:#e6edf3; --border:#1c2a42; }
    * { box-sizing:border-box; }
    body { margin:0; font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,Arial; background:var(--bg); color:var(--fg); }
    header { padding:10px 14px; border-bottom:1px solid var(--border); position:sticky; top:0; background:var(--bg); z-index:10; display:flex; gap:10px; align-items:center; justify-content:space-between; }
    header h1 { margin:0; font-size:18px; }
   /* Mobile-first: 1 kolom, map bovenaan, paneel eronder */
.wrap {
  display:grid;
  grid-template-columns:1fr;
  grid-auto-rows:auto;
  gap:12px;
  padding:12px;
  position:relative;
  /* geen geforceerde vaste hoogte op mobiel; laat de pagina scrollen */
  min-height:calc(100vh - 56px);
}

/* Map: op mobiel ~halve viewport hoogte */
#map {
  height:55vh;               /* prettige hoogte op mobiel */
  min-height:320px;          /* zodat het nooit te klein wordt */
  border-radius:12px;
  border:1px solid var(--border);
  box-shadow:0 0 0 1px rgba(255,255,255,.05) inset;
  position:relative;
}

/* Paneel: op mobiel gewoon mee in de flow */
.panel-right {
  height:auto;
  overflow:visible;
}

/* Zoekbalk control: breedte schaalt mee op mobiel */
.pw-search { width:min(92vw, 320px); margin:8px 8px 0 8px; }

/* Vanaf 900px → 2 kolommen en full-height layout zoals desktop */
@media (min-width: 900px) {
  .wrap {
    grid-template-columns:1fr 1fr;
    height:calc(100vh - 56px);
  }
  #map { height:100%; }
  .panel-right { height:100%; overflow:auto; }
  .col-splitter {
    position:absolute;
    top:12px;
    bottom:12px;
    width:6px;
    margin-left:-3px;
    background:rgba(255,255,255,.2);
    border-radius:999px;
    cursor:col-resize;
    z-index:500;
  }
  body.is-resizing {
    cursor:col-resize;
    user-select:none;
  }
}

/* Extra: op hele brede schermen map iets breder dan paneel */
@media (min-width: 1400px) {
  .wrap { grid-template-columns:1.2fr 1fr; }
}

    .panel-right { height:100%; overflow:auto; }
    .muted { color:var(--muted); }

    .leaflet-control.pw-locate { background:transparent; border:0; box-shadow:none; }
    .pw-locate-btn { width:36px; height:36px; border-radius:999px; border:1px solid #1f2c49; background:#0c1730; color:#e6edf3; display:flex; align-items:center; justify-content:center; cursor:pointer; box-shadow:0 2px 6px rgba(0,0,0,.35); }
    .pw-locate-btn:hover { background:#13264a; }

    .legend-inline, #clickInfo {
      width:auto;
      max-width:460px;
      min-width:260px;
    }
.pw-ctl { background:var(--panel); color:var(--fg); border:1px solid var(--border); border-radius:12px; padding:10px; box-shadow:0 2px 12px rgba(0,0,0,.35); width:auto; min-width:260px; max-width:460px; }
    .pw-ctl h3 { margin:0 0 6px; font-size:14px; }
    .pw-ctl .sec { margin-top:8px; }

    /* Zoekbalk (topleft, boven zoom) */
    .pw-search {
      background:var(--panel); color:var(--fg);
      border:1px solid var(--border); border-radius:10px;
      padding:8px; width:260px;
      box-shadow:0 2px 12px rgba(0,0,0,.35);
    }
    .pw-search input {
      width:100%; padding:6px 8px;
      border:1px solid var(--border); border-radius:6px;
      background:transparent; color:inherit;
    }
    .pw-sugg { margin-top:6px; max-height:240px; overflow:auto; }
    .pw-sugg div { padding:6px 8px; border-radius:6px; cursor:pointer; }
    .pw-sugg div:hover { background:rgba(255,255,255,.06); }

    .filters { display:block; margin-bottom:10px; }
    .filters .group { margin:8px 0 0; }
    .filters .title { display:block; font-weight:600; margin-bottom:6px; }
    .checks { display:flex; gap:6px; flex-wrap:wrap; }
    .checks label { display:inline-flex; gap:6px; align-items:center; background:#0c1730; border:1px solid #1f2c49; padding:6px 8px; border-radius:8px; }
    input[type=checkbox] { accent-color:#5aa9ff; }
    .hint { font-size:12px; color:var(--muted); margin-top:4px; }

    .more-toggle { width:100%; margin:10px 0 0; background:#0c1730; border:1px solid #1f2c49; padding:6px 10px; border-radius:8px; display:flex; align-items:center; justify-content:space-between; cursor:pointer; user-select:none; }
    .more-toggle span.arrow { font-size:12px; }
    #moreFilters { display:none; margin-top:8px; }
    #moreFilters.open { display:block; }

    #filterStatus { margin:6px 0 10px; }
    .flag { display:inline-flex; gap:8px; align-items:flex-start; padding:8px 10px; border-radius:8px; border:1px solid; }
    .flag.ok   { color:#38d39f; border-color:rgba(56,211,159,.35); background:rgba(56,211,159,.08); }
    .flag.warn { color:#ff6b6b; border-color:rgba(255,107,107,.35); background:rgba(255,107,107,.08); }
    .flag .icon { line-height:1; }
    .flag .text { color:inherit; }

    .toolbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin:8px 0 10px; }
    .actions { display:flex; gap:8px; flex-wrap:wrap; }
    .btn { background:#0c1730; border:1px solid #1f2c49; color:var(--fg); padding:6px 10px; border-radius:8px; cursor:pointer; }
    .tag-inheems {
      display:inline-block;
      margin-right:4px;
      font-size:11px;
      line-height:1;
      color:#38d39f;
    }
.btn:hover { background:#13264a; }
    .btn-ghost { background:transparent; color:var(--fg); border:1px solid var(--border); padding:6px 10px; border-radius:8px; cursor:pointer; }
    .btn-ghost:hover { background:rgba(255,255,255,.06); }

    table { width:100%; border-collapse:collapse; }
    th, td { padding:8px 10px; border-bottom:1px solid #182742; text-align:left; vertical-align:top; }
    thead th { color:#b0b8c6; position:sticky; top:0; z-index:1; background:var(--panel); }
    th .th-wrap { display:flex; align-items:center; gap:6px; }
    th.col-filter { cursor:pointer; }
    th.col-filter .th-text::after { content:"▾"; font-size:11px; opacity:.65; margin-left:6px; }
    .dropdown { position:fixed; display:none; z-index:9999; background:var(--panel); color:var(--fg); border:1px solid var(--border); border-radius:8px; padding:8px; max-height:260px; overflow:auto; box-shadow:0 6px 24px rgba(0,0,0,.35); min-width:220px; }
    .dropdown.show { display:block; }
    .dropdown h4 { margin:0 0 6px; font-size:13px; }
    .dropdown .opt { display:flex; align-items:center; gap:6px; margin:4px 0; }
    .dropdown .actions { display:flex; gap:6px; margin-top:8px; }
    .dropdown .actions .btn { padding:4px 8px; }

    #colMenu { position:fixed; display:none; z-index:9999; background:var(--panel); color:var(--fg); border:1px solid var(--border); border-radius:8px; padding:8px; box-shadow:0 6px 24px rgba(0,0,0,.35); min-width:240px; }
    #colMenu.show { display:block; }
    #colMenu .opt { display:flex; align-items:center; gap:8px; margin:6px 0; }

    body.light {
      --bg:#f6f8fc; --panel:#ffffff; --muted:#667085; --fg:#111827; --border:#e5e7eb;
    }
    body.light .checks label,
    body.light .more-toggle { background:#f2f4f7; border-color:#e5e7eb; }
    body.light .pw-ctl { background:#ffffff; border-color:#e5e7eb; }
    body.light .pw-locate-btn { background:#f2f4f7; color:#111827; border-color:#e5e7eb; }
    body.light .pw-locate-btn:hover { background:#eaeef3; }
    body.light .btn { background:#f2f4f7; color:#111827; border-color:#e5e7eb; }
    body.light .btn:hover { background:#eaeef3; }
    body.light .btn-ghost { border-color:#e5e7eb; }
    body.light thead th { background:#ffffff; color:#475569; }

    /* Leaflet controls theming (zoom + layers) */
.leaflet-control-zoom,
.leaflet-control-layers {
  background: var(--panel) !important;
  color: var(--fg) !important;
  border: 1px solid var(--border) !important;
  border-radius: 10px;
  box-shadow: 0 2px 12px rgba(0,0,0,.35);
}

/* Zoom knoppen */
.leaflet-bar a,
.leaflet-bar a:focus {
  background: var(--panel) !important;
  color: var(--fg) !important;
  border-bottom: 1px solid var(--border) !important;
  box-shadow: none !important;
}
.leaflet-bar a:last-child { border-bottom: 0 !important; }
.leaflet-bar a:hover { background: #13264a !important; } /* dark hover */
body.light .leaflet-bar a:hover { background: #eaeef3 !important; } /* light hover */

/* Layers control (uitgeklapt) */
.leaflet-control-layers-expanded {
  padding: 8px !important;
}
.leaflet-control-layers-list,
.leaflet-control-layers label {
  color: var(--fg) !important;
}
.leaflet-control-layers-separator {
  border-top-color: var(--border) !important;
}
.leaflet-control-layers-overlays label {
  display: flex; gap: 8px; align-items: center;
}
.leaflet-control-layers-overlays label span {
  flex:1 1 auto;
}
.leaflet-control-layers-overlays label .opacity-slider {
  width:80px;
}
.leaflet-control-layers input.leaflet-control-layers-selector {
  accent-color: #5aa9ff; /* match je overige checkboxes */
}

/* Light mode fine-tuning (schaduw iets subtieler) */
body.light .leaflet-control-zoom,
body.light .leaflet-control-layers {
  box-shadow: 0 2px 12px rgba(0,0,0,.12);
}
/* --- Responsive tuning voor Leaflet controls --- */
.leaflet-control { font-size: 13px; }
.leaflet-control-layers { max-width: 360px; }
.leaflet-control-layers-expanded {
  width: clamp(220px, 80vw, 360px);
  max-height: 45vh;
  overflow: auto;
}

/* Mobiel: compact, niet overlappen */
@media (max-width: 768px) {
  /* randen wat dichter op het scherm */
  .leaflet-top.leaflet-right  { margin-right: 8px; }
  .leaflet-top.leaflet-left   { margin-left:  8px; }
  .leaflet-bottom.leaflet-right,
  .leaflet-bottom.leaflet-left { margin-bottom: 8px; }

  /* kleinere zoomknoppen */
  .leaflet-control-zoom a { width: 32px; height: 32px; line-height: 32px; }

  /* zoekcontrol smaller */
  .pw-search { width: min(92vw, 320px); padding: 6px; }
  .pw-search input { padding: 6px 8px; }

  /* legenda & info compacter */
  .pw-ctl { width: min(70vw, 240px); padding: 8px; }
  .pw-ctl h3 { font-size: 13px; }
  .pw-ctl .sec { font-size: 12px; }
}
/* ——— Mobile layout (≤768px) ——— */
.legend-inline{ display:none; }  /* default verborgen; alleen mobiel tonen */
@media (max-width: 768px){
  .wrap { grid-template-columns: 1fr; height:auto; }
  #map { height: 62vh; }

  /* zoekbalk compacter linksboven */
  .pw-search { width: 210px; padding:6px; border-radius:8px; }
  .pw-search input { padding:5px 7px; font-size:14px; }

  /* verberg de zwevende legenda op de kaart */
  .leaflet-control.pw-ctl { display:none; }

  /* toon de legenda onder de kaart als paneel */
  .legend-inline{ display:block; margin:10px 0 14px; }

  /* wat lucht aan de randen van knoppen */
  .leaflet-control { margin: 8px; }
}
/* Mobiel: verberg de in-kaart legenda (InfoCtl) */
@media (max-width: 768px){
  .leaflet-control.pw-ctl { display: none !important; }
}

  </style>
</head>
<body>
  <header>
    <h1>🌿 PlantWijs</h1>
    <button id="btnTheme" class="btn-ghost" title="Schakel licht/donker">🌓 Thema</button>
  </header>

 <div class="wrap">
  <div id="map"></div>
  <div id="colSplitter" class="col-splitter" aria-hidden="true"></div>

  <!-- Mobiele legenda (staat buiten/onder de kaart); desktop: verborgen -->
  <div id="legendInline" class="panel legend-inline" aria-live="polite">
    <h3>Legenda &amp; info</h3>
    <div id="uiF2" class="muted">Fysisch Geografische Regio's: —</div>
    <div id="uiB2" class="muted">Bodem: —</div>
    <div id="uiG2" class="muted">Gt: —</div>
    <div id="uiH2" class="muted">AHN (m): —</div>
    <div id="uiM2" class="muted">Geomorfologie (GMM): —</div>
    <div id="uiN2" class="muted">Natuurlijk Systeem (NSN): —</div>
  </div>

    <div class="panel panel-right">
      <div class="filters">
        <div class="group">
          <span class="title">Licht</span>
          <div class="checks" id="lichtChecks">
            <label><input type="checkbox" name="licht" value="schaduw"> schaduw</label>
            <label><input type="checkbox" name="licht" value="halfschaduw"> halfschaduw</label>
            <label><input type="checkbox" name="licht" value="zon"> zon</label>
          </div>
          <div class="hint">Selecteer hier het lichtniveau van de locatie voor een duidelijker en beter passend resultaat.</div>
        </div>

        <div id="moreBar" class="more-toggle" title="Meer filters tonen/verbergen">
          <strong>Meer filters en opties</strong><span class="arrow">▾</span>
        </div>

        <div id="moreFilters">
          <div class="group">
            <span class="title">Vocht</span>
            <div class="checks">
              <label><input type="checkbox" name="vocht" value="zeer droog"> zeer droog</label>
              <label><input type="checkbox" name="vocht" value="droog"> droog</label>
              <label><input type="checkbox" name="vocht" value="vochtig"> vochtig</label>
              <label><input type="checkbox" name="vocht" value="nat"> nat</label>
              <label><input type="checkbox" name="vocht" value="zeer nat"> zeer nat</label>
            </div>
            <div class="hint">Wijkt de vochttoestand op de gekozen plek af van wat de kaarten aangeven? Kies hier een waarde om de kaartwaarde te overschrijven.</div>
          </div>

          <div class="group">
            <span class="title">Bodem</span>
            <div class="checks">
              <label><input type="checkbox" name="bodem" value="zand"> zand</label>
              <label><input type="checkbox" name="bodem" value="klei"> klei</label>
              <label><input type="checkbox" name="bodem" value="leem"> leem</label>
              <label><input type="checkbox" name="bodem" value="veen"> veen</label>
            </div>
            <div class="hint">Komt het bodemtype ter plekke niet overeen met de kaart? Selecteer hier een bodem om de kaartwaarde te overschrijven.</div>
          </div>

          <div class="group">
            <span class="title">Status</span>
            <div class="checks">
              <label class="muted"><input id="stInh" type="checkbox" checked> inheems</label>
              <label class="muted"><input id="stIng" type="checkbox" checked> ingeburgerd</label>
              <label class="muted"><input id="stExo" type="checkbox"> exoot</label>
            </div>
          </div>

          <div class="group">
            <span class="title">Beplantingstype</span>
            <div class="checks">
              <label class="muted"><input type="checkbox" name="ptype" value="boom" checked> bomen</label>
              <label class="muted"><input type="checkbox" name="ptype" value="heester" checked> heesters</label>
            </div>
          </div>

          <div class="group">
            <span class="title">Opties</span>
            <div class="checks">
              <label class="muted"><input id="exInv" type="checkbox" checked> sluit invasieve uit</label>
            </div>
          </div>
        </div>
      </div>

      <div class="toolbar">
        <div class="muted" id="count"></div>
        <div class="actions">
          <button id="btnCols" class="btn-ghost" title="Kolommen tonen/verbergen">☰ Kolommen</button>
          <button id="btnCSV" class="btn" title="Exporteer huidige selectie als CSV">⬇️ CSV</button>
          <button id="btnXLSX" class="btn" title="Exporteer huidige selectie als Excel">⬇️ Excel</button>
        </div>
      </div>

      <div id="filterStatus"></div>

      <div id="colMenu"></div>

      <div id="colFilterMenu" class="dropdown"></div>

      <table id="tbl">
        <thead><tr id="theadRow"></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <script>
  const map = L.map('map').setView([52.1, 5.3], 8);
  const isMobile = window.matchMedia('(max-width: 768px)').matches;
// Zoomknoppen linksonder op mobiel
if (isMobile) map.zoomControl.setPosition('bottomleft');

  // ⬇️ NIEUW: simpele mobiele-vlag
  const IS_MOBILE = window.matchMedia('(max-width: 768px)').matches;

    // Zorg dat Leaflet z'n grootte herkent bij layout/rotatie
function fixMapSize(){ setTimeout(()=> map.invalidateSize(), 60); }
window.addEventListener('resize', fixMapSize);
window.addEventListener('orientationchange', fixMapSize);
// eerste keer na opbouwen
setTimeout(fixMapSize, 0);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '&copy; OpenStreetMap' }).addTo(map);

    let overlays = {};
    let ui = { meta:null, ctx:{ vocht:null, bodem:null } };
    window._lastQuery = new URLSearchParams();
    let _lastItems = [];

    const COLS_KEY = 'pw_cols_visible_v3';
    const DEFAULT_COLS = [
      {key:'naam', label:'Naam', filterable:false, visible:true},
      {key:'wetenschappelijke_naam', label:'Wetenschappelijke naam', filterable:false, visible:true},
      {key:'beplantingstype', label:'Beplantingstype', filterable:true, visible:true},
      {key:'standplaats_licht', label:'Licht', filterable:true, visible:true},
      {key:'vocht', label:'Vocht', filterable:true, visible:true},
      {key:'bodem', label:'Bodem', filterable:true, visible:true},
      {key:'hoogte', label:'Hoogte', filterable:false, visible:true},
      {key:'breedte', label:'Breedte', filterable:false, visible:true},
      {key:'winterhardheidszone', label:'WHZ', filterable:true, visible:true},
      {key:'grondsoorten', label:'Grondsoorten', filterable:true, visible:false},
      {key:'status_nl', label:'Status', filterable:true, visible:true},
      {key:'invasief', label:'Invasief', filterable:true, visible:false},
    ];
    let COLS = JSON.parse(localStorage.getItem(COLS_KEY) || 'null') || DEFAULT_COLS;

    const headerFilters = new Map();

    function html(s){ return (s==null?'':String(s)).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;') }
    function getChecked(name){ return Array.from(document.querySelectorAll('input[name="'+name+'"]:checked')).map(x=>x.value) }
    function tokSplit(val){ return String(val??'').split(/[/|;,]+/).map(s=>s.trim()).filter(Boolean); }

    function computeUsage(){
      const chosenL = getChecked('licht');
      const chosenV = getChecked('vocht');
      const chosenB = getChecked('bodem');
      const useL = chosenL.length > 0;
      const useV = chosenV.length > 0 || !!(ui.ctx && ui.ctx.vocht);
      const useB = chosenB.length > 0 || !!(ui.ctx && ui.ctx.bodem);
      return { useL, useV, useB, chosenL, chosenV, chosenB };
    }

    (function themeInit(){
      const key = 'pw_theme';
      const apply = t => { document.body.classList.toggle('light', t === 'light'); };
      const saved = localStorage.getItem(key) || 'dark';
      apply(saved);
      document.getElementById('btnTheme')?.addEventListener('click', ()=>{
        const now = document.body.classList.contains('light') ? 'dark' : 'light';
        localStorage.setItem(key, now); apply(now);
      });
    })();

    const LocateCtl = L.Control.extend({
      options:{ position:'bottomright' },
      onAdd: function() {
        const div = L.DomUtil.create('div', 'leaflet-control pw-locate');
        const btn = L.DomUtil.create('button', 'pw-locate-btn', div);
        btn.type = 'button'; btn.title = 'Mijn locatie'; btn.textContent = '📍';
        L.DomEvent.on(btn, 'click', (e)=>{
          L.DomEvent.stop(e);
          if(!navigator.geolocation){ alert('Geolocatie niet ondersteund.'); return; }
          navigator.geolocation.getCurrentPosition(pos=>{
            const lat = pos.coords.latitude, lon = pos.coords.longitude;
            map.setView([lat,lon], 14);
            if(window._marker) window._marker.remove();
            window._marker = L.marker([lat,lon]).addTo(map);
            map.fire('click', { latlng:{ lat, lng:lon } });
          }, err=>{ alert('Kon locatie niet ophalen'); });
        });
        return div;
      }
    });

    // ───────────────────────────────── PDOK Locatieserver zoek-control (topleft, boven zoom)
    const PDOKSearch = L.Control.extend({
      options: { position: 'topleft' },
      onAdd: function(map) {
        const div = L.DomUtil.create('div', 'pw-search');
        div.innerHTML = `
          <input id="pwSearchInput" type="text" placeholder="Zoek adres of plaats…" autocomplete="off">
          <div id="pwSugg" class="pw-sugg"></div>
        `;
        const inp = div.querySelector('#pwSearchInput');
        const box = div.querySelector('#pwSugg');

        // Officiële nieuwe endpoint met CORS
        const PDOK_BASE = 'https://api.pdok.nl/bzk/locatieserver/search/v3_1';

        // Klein abort/time-out mechanisme zodat oude requests worden afgebroken
        let lastCtrl = null;
        function fetchJSON(url){
          if(lastCtrl) lastCtrl.abort();
          lastCtrl = new AbortController();
          const id = setTimeout(()=> lastCtrl.abort(), 8000);
          return fetch(url, { mode:'cors', headers:{ 'Accept':'application/json' }, signal:lastCtrl.signal })
            .finally(()=> clearTimeout(id))
            .then(r => {
              if(!r.ok) throw new Error('HTTP '+r.status);
              return r.json();
            });
        }

        let t = null;

        function labelFromDoc(d){
          const s = (d.weergavenaam || d.weergaveNaam || '').replace(/, Nederland$/,'');
          return s || (d.type || d.typeGebied || d.bron || '');
        }

        async function suggest(q){
          if(!q || q.length < 3){ box.innerHTML=''; return; }
          try{
            const url = `${PDOK_BASE}/suggest?rows=10&q=${encodeURIComponent(q)}`;
            const j = await fetchJSON(url);
            const docs = (j.response && j.response.docs) ? j.response.docs : [];
            if(!docs.length){ box.innerHTML = `<div class="muted">Geen resultaten</div>`; return; }
            box.innerHTML = docs.map(d=>`<div data-id="${d.id}">${html(labelFromDoc(d))}</div>`).join('');
            box.querySelectorAll('div[data-id]').forEach(el=>{
              el.addEventListener('click', ()=> selectById(el.getAttribute('data-id'), el.textContent));
            });
          }catch(e){
            box.innerHTML = `<div class="muted">Zoeken mislukt</div>`;
            console.error('[PDOK] suggest error', e);
          }
        }

        async function selectById(id, displayText){
          try{
            const url = `${PDOK_BASE}/lookup?id=${encodeURIComponent(id)}`;
            const j = await fetchJSON(url);
            const doc = (j.response && j.response.docs && j.response.docs[0]) ? j.response.docs[0] : null;
            if(doc && doc.centroide_ll){
              const m = /POINT\\(([-0-9.]+)\\s+([-0-9.]+)\\)/.exec(doc.centroide_ll);
              if(m){
                const lon = parseFloat(m[1]), lat = parseFloat(m[2]);
                map.setView([lat,lon], 15);
                if(window._marker) window._marker.remove();
                window._marker = L.marker([lat,lon]).addTo(map);
                map.fire('click', { latlng:{ lat, lng:lon } }); // triggert je advies-flow
                box.innerHTML=''; inp.value = displayText || labelFromDoc(doc);
              }
            }
          }catch(e){
            console.error('[PDOK] lookup error', e);
          }
        }

        async function freeSearch(q){
          if(!q) return;
          try{
            const url = `${PDOK_BASE}/free?rows=1&q=${encodeURIComponent(q)}`;
            const j = await fetchJSON(url);
            const doc = (j.response && j.response.docs && j.response.docs[0]) ? j.response.docs[0] : null;
            if(doc && doc.centroide_ll){
              const m = /POINT\\(([-0-9.]+)\\s+([-0-9.]+)\\)/.exec(doc.centroide_ll);
              if(m){
                const lon = parseFloat(m[1]), lat = parseFloat(m[2]);
                map.setView([lat,lon], 15);
                if(window._marker) window._marker.remove();
                window._marker = L.marker([lat,lon]).addTo(map);
                map.fire('click', { latlng:{ lat, lng:lon } });
                box.innerHTML=''; inp.value = labelFromDoc(doc) || q;
              }
            }else{
              box.innerHTML = `<div class="muted">Geen resultaten</div>`;
            }
          }catch(e){
            console.error('[PDOK] free error', e);
            box.innerHTML = `<div class="muted">Zoekfout</div>`;
          }
        }

        // Typen → suggest (met debounce)
        inp.addEventListener('input', ()=>{
          clearTimeout(t);
          const q = inp.value.trim();
          t = setTimeout(()=> suggest(q), 250);
        });

        // Enter → pak 1e suggestie, anders free search
        inp.addEventListener('keydown', (ev)=>{
          if(ev.key === 'Enter'){
            ev.preventDefault();
            const first = box.querySelector('div[data-id]');
            if(first){ first.click(); }
            else{ freeSearch(inp.value.trim()); }
          }
        });

        // Houd focus (klik in suggesties sluit input niet)
        box.addEventListener('mousedown', e => e.preventDefault());

        // Leaflet: niet de kaart laten pannen bij interactie met deze control
        L.DomEvent.disableClickPropagation(div);

        // Plaats boven de zoomknoppen
        setTimeout(()=>{
          const corner = map._controlCorners && map._controlCorners['topleft'];
          const zoom = map.zoomControl && map.zoomControl.getContainer ? map.zoomControl.getContainer() : (corner?.querySelector('.leaflet-control-zoom'));
          if(corner && zoom && div.parentNode === corner){
            corner.insertBefore(div, zoom);
          }
        }, 0);

        return div;
      }
    });

    map.addControl(new LocateCtl());
    map.addControl(new PDOKSearch());

    const InfoCtl = L.Control.extend({
      onAdd: function() {
        const div = L.DomUtil.create('div', 'pw-ctl');
        div.innerHTML = `
          <h3>Legenda & info</h3>
          <div class="sec" id="clickInfo">
            <div id="uiF" class="muted">Fysisch Geografische Regio's: —</div>
            <div id="uiB" class="muted">Bodem: —</div>
            <div id="uiG" class="muted">Gt: —</div>
            <div id="uiH" class="muted">AHN (m): —</div>
            <div id="uiM" class="muted">Geomorfologie (GMM): —</div>
            <div id="uiN" class="muted">Natuurlijk Systeem (NSN): —</div>
          </div>
          <div class="sec">
            <button id="btnPdf" class="btn" style="width:100%; margin-top:6px;">📄 Locatierapport</button>
            <div class="hint" style="margin-top:6px;">Download een PDF met locatie-uitleg + alle geschikte inheemse/ingeburgerde soorten.</div>
          </div>

        `;
        L.DomEvent.disableClickPropagation(div);
        return div;
      }
    });
    const infoCtl = new InfoCtl({ position: IS_MOBILE ? 'bottomright' : 'topright' }).addTo(map);

    // PDF-knop (onder legenda): download locatierapport
    setTimeout(()=>{
      const btnPdf = document.getElementById('btnPdf');
      if(btnPdf){
        btnPdf.addEventListener('click', (ev)=>{
          ev.preventDefault();
          ev.stopPropagation();
          const ll = window._lastLatLng || (window._marker ? window._marker.getLatLng() : null);
          if(!ll){
            alert('Klik eerst op de kaart om een locatie te kiezen.');
            return;
          }
          const u = new URL(location.origin + '/advies/pdf');
          u.searchParams.set('lat', ll.lat);
          u.searchParams.set('lon', ll.lng);

          // Neem huidige UI-filters mee (als je niets kiest, gebruikt de server kaartwaarden)
          getChecked('licht').forEach(v=>u.searchParams.append('licht', v));
          const vlist = getChecked('vocht');
          if(vlist.length){ u.searchParams.append('vocht', vlist[0]); }
          const blist = getChecked('bodem');
          if(blist.length){ u.searchParams.append('bodem', blist[0]); }

          const inv = document.querySelector('input[name="exclude_invasief"]');
          if(inv){ u.searchParams.set('exclude_invasief', inv.checked ? 'true' : 'false'); }

          window.open(u.toString(), '_blank');
        });
      }
    }, 0);

  function setClickInfo({fgr, bodem, bodem_bron, gt, vocht, ahn, gmm, nsn}) {
  const tF = "Fysisch Geografische Regio's: " + (fgr || '—');
  const tB = 'Bodem: ' + ((bodem || '—') + (bodem_bron ? ` (${bodem_bron})` : ''));
  const tG = 'Gt: ' + (gt || '—') + (vocht ? ` → ${vocht}` : ' (onbekend)');
  const tH = 'AHN (m): ' + ((ahn !== null && ahn !== undefined && ahn !== '') ? ahn : '—');
  const tM = 'Geomorfologie (GMM): ' + ((gmm !== null && gmm !== undefined && gmm !== '') ? gmm : '—');
  const tN = 'Natuurlijk Systeem (NSN): ' + ((nsn !== null && nsn !== undefined && nsn !== '') ? nsn : '—');

  const set = (id, txt) => {
    const el = document.getElementById(id);
    if (el) el.textContent = txt;
  };

  // legenda in de kaart (desktop)
  set('uiF', tF);
  set('uiB', tB);
  set('uiG', tG);
  set('uiH', tH);
  set('uiM', tM);
  set('uiN', tN);

  // mobiele legenda onder de kaart
  set('uiF2', tF);
  set('uiB2', tB);
  set('uiG2', tG);
  set('uiH2', tH);
  set('uiM2', tM);
  set('uiN2', tN);
}

    function initSplitter(){
      if (window.matchMedia('(max-width: 900px)').matches) return;
      const wrap = document.querySelector('.wrap');
      const handle = document.getElementById('colSplitter');
      if (!wrap || !handle) return;

      let dragging = false;

      const applyFromX = (clientX)=>{
        const rect = wrap.getBoundingClientRect();
        let x = clientX - rect.left;
        const min = rect.width * 0.25;
        const max = rect.width * 0.75;
        if (x < min) x = min;
        if (x > max) x = max;
        const pctLeft = (x / rect.width) * 100;
        wrap.style.gridTemplateColumns = pctLeft.toFixed(1) + '% ' + (100 - pctLeft).toFixed(1) + '%';
        handle.style.left = x + 'px';
        if (typeof map !== 'undefined' && map && typeof map.invalidateSize === 'function') {
          map.invalidateSize({animate:false});
        }
      };

      // startpositie iets meer ruimte voor de kaart
      const rect0 = document.querySelector('.wrap').getBoundingClientRect();
      const startX = rect0.width * 0.55;
      wrap.style.gridTemplateColumns = '55% 45%';
      handle.style.left = startX + 'px';
      if (typeof map !== 'undefined' && map && typeof map.invalidateSize === 'function') {
        map.invalidateSize({animate:false});
      }

      handle.addEventListener('mousedown', (e)=>{
        dragging = true;
        document.body.classList.add('is-resizing');
        e.preventDefault();
      });

      window.addEventListener('mouseup', ()=>{
        if (!dragging) return;
        dragging = false;
        document.body.classList.remove('is-resizing');
      });

      window.addEventListener('mousemove', (e)=>{
        if (!dragging) return;
        applyFromX(e.clientX);
      });
    }

async function loadWms(){
      ui.meta = await (await fetch('/api/wms_meta')).json();
      const make = (m, opacity)=> L.tileLayer.wms(m.url, { layers:m.layer, transparent:true, opacity: opacity, version:'1.3.0', crs: L.CRS.EPSG3857 });
      overlays['BRO Bodemkaart (Bodemvlakken)'] = make(ui.meta.bodem, 0.6);
      overlays['BRO Grondwatertrappen (Gt)']    = make(ui.meta.gt,    0.6);
      overlays["Fysisch Geografische Regio's"]  = make(ui.meta.fgr,   0.6).addTo(map);
      overlays['AHN (hoogte, DTM 0.5m)']        = make(ui.meta.ahn,   0.6);
      overlays['BRO Geomorfologische kaart (GMM)'] = make(ui.meta.gmm,   0.6);
const ctlLayers = L.control.layers({}, overlays, { collapsed:true, position:'bottomleft' }).addTo(map);

      function attachOpacityControls() {
        const cont = ctlLayers.getContainer();
        if (!cont) return;
        const labels = cont.querySelectorAll('.leaflet-control-layers-overlays label');
        labels.forEach(label => {
          const span = label.querySelector('span');
          if (!span) return;
          const name = span.textContent.trim();
          const layer = overlays[name];
          if (!layer || typeof layer.setOpacity !== 'function') return;
          if (label.querySelector('.opacity-slider')) return; // voorkom dubbele sliders

          const slider = document.createElement('input');
          slider.type = 'range';
          slider.className = 'opacity-slider';
          slider.min = '0';
          slider.max = '1';
          slider.step = '0.1';
          const startOpacity = (layer.options && typeof layer.options.opacity === 'number') ? layer.options.opacity : 0.6;
          slider.value = String(startOpacity);
          slider.style.marginLeft = '0.5em';
          slider.style.verticalAlign = 'middle';
          slider.title = 'Doorzichtigheid laag';

          slider.addEventListener('input', () => {
            const v = parseFloat(slider.value);
            if (!isNaN(v) && layer.setOpacity) {
              layer.setOpacity(v);
            }
          });

          label.appendChild(slider);
        });
      }

      attachOpacityControls();





      const cont = ctlLayers.getContainer();
      cont.classList.remove('leaflet-control-layers-expanded');
      const baseList = cont.querySelector('.leaflet-control-layers-base'); if(baseList) baseList.remove();
      const sep = cont.querySelector('.leaflet-control-layers-separator'); if(sep) sep.remove();
      const overlaysList = cont.querySelector('.leaflet-control-layers-overlays');
      const title = document.createElement('div');
      title.textContent = 'Kaartlagen';
      title.style.fontWeight = '700'; title.style.fontSize = '15px';
      title.style.margin = '6px 10px'; title.style.color = 'var(--fg)';
      overlaysList.parentNode.insertBefore(title, overlaysList);
    }

    async function fetchList(){
      const url = new URL(location.origin + '/api/plants');

      // Status filters (standaard: inheems + ingeburgerd aan, exoot uit)
      const stInh = document.getElementById('stInh');
      const stIng = document.getElementById('stIng');
      const stExo = document.getElementById('stExo');
      if(stInh) url.searchParams.set('toon_inheems', stInh.checked ? 'true' : 'false');
      if(stIng) url.searchParams.set('toon_ingeburgerd', stIng.checked ? 'true' : 'false');
      if(stExo) url.searchParams.set('toon_exoot', stExo.checked ? 'true' : 'false');

      // Beplantingstype
      const chosenP = getChecked('ptype');
      for (const v of chosenP) url.searchParams.append('beplantingstype', v);

      const inv = document.getElementById('exInv');
      if(inv && inv.checked) url.searchParams.set('exclude_invasief','true');
      const chosenL = getChecked('licht');
      const chosenV = getChecked('vocht');
      const chosenB = getChecked('bodem');

      for (const v of chosenL) url.searchParams.append('licht', v);
      for (const v of chosenV) url.searchParams.append('vocht', v);
      for (const v of chosenB) url.searchParams.append('bodem', v);

      if (!chosenV.length && ui.ctx && ui.ctx.vocht) url.searchParams.append('vocht', ui.ctx.vocht);
      if (!chosenB.length && ui.ctx && ui.ctx.bodem) url.searchParams.append('bodem', ui.ctx.bodem);

      url.searchParams.set('limit','1000');

      window._lastQuery = new URLSearchParams(url.searchParams);

      const r = await fetch(url);
      return r.json();
    }

    function positionPopup(el, anchor){
      const r = anchor.getBoundingClientRect();
      el.style.left = (r.left) + 'px';
      el.style.top  = (r.bottom + 6) + 'px';
    }

    function openColsMenu(anchor){
      const box = document.getElementById('colMenu');
      box.innerHTML = '<h4 style="margin:0 0 6px;font-size:13px;">Kolommen</h4>' +
        COLS.map((c,i)=>`<label class="opt"><input type="checkbox" data-col="${c.key}" ${c.visible?'checked':''}> ${html(c.label)}</label>`).join('') +
        '<div class="actions" style="margin-top:10px;"><button id="colAll" class="btn">Alles</button><button id="colNone" class="btn">Niets</button></div>';
      positionPopup(box, anchor);
      box.classList.add('show');

      box.querySelectorAll('input[type=checkbox]').forEach(chk=>{
        chk.addEventListener('change', (e)=>{
          const key = chk.getAttribute('data-col');
          const idx = COLS.findIndex(c=>c.key===key);
          if(idx>=0){ COLS[idx].visible = !!chk.checked; saveCols(); buildTableHeader(); renderFromCache(); }
        });
      });
      box.querySelector('#colAll').onclick = ()=>{ COLS.forEach(c=>c.visible=true); saveCols(); buildTableHeader(); renderFromCache(); };
      box.querySelector('#colNone').onclick = ()=>{
        COLS.forEach(c=>c.visible=false);
        (COLS.find(c=>c.key==='naam')||{}).visible = true;
        saveCols(); buildTableHeader(); renderFromCache();
      };
    }
    function saveCols(){ localStorage.setItem(COLS_KEY, JSON.stringify(COLS)); }

    function getVisibleCols(){ return COLS.filter(c=>c.visible).map(c=>c.key); }

    function uniqueTokensFor(items, key){
      const set = new Set();
      for(const row of items||[]){
        if(key==='winterhardheidszone'){
          const v = String(row[key]??'').trim();
          if(v) set.add(v);
        }else if(key==='bodem'){
          for(const t of tokSplit(row['bodem'])) set.add(t);
          for(const t of tokSplit(row['grondsoorten'])) set.add(t);
        }else{
          for(const t of tokSplit(row[key])) set.add(t);
        }
      }
      return Array.from(set).sort((a,b)=> a.localeCompare(b,'nl',{numeric:true}));
    }

    function openHeaderFilterMenu(anchor, key, label){
      const menu = document.getElementById('colFilterMenu');
      const current = headerFilters.get(key) || new Set();
      const options = uniqueTokensFor(_lastItems, key);
      const optsHtml = options.map(val=>{
        const checked = current.has(val) ? 'checked' : '';
        return `<label class="opt"><input type="checkbox" data-key="${key}" value="${html(val)}" ${checked}> ${html(val)}</label>`;
      }).join('') || `<div class="muted">Geen waarden beschikbaar</div>`;
      menu.innerHTML = `<h4>${html(label)}</h4>${optsHtml}<div class="actions"><button class="btn" id="cfApply">Toepassen</button><button class="btn-ghost" id="cfClear">Leegmaken</button></div>`;
      positionPopup(menu, anchor);
      menu.classList.add('show');

      menu.querySelector('#cfApply').onclick = ()=>{
        const sel = new Set(Array.from(menu.querySelectorAll('input[type=checkbox]:checked')).map(i=>i.value));
        if(sel.size) headerFilters.set(key, sel); else headerFilters.delete(key);
        menu.classList.remove('show');
        renderFromCache();
      };
      menu.querySelector('#cfClear').onclick = ()=>{
        headerFilters.delete(key);
        menu.classList.remove('show');
        renderFromCache();
      };
    }

    document.addEventListener('click', (e)=>{
      const m1 = document.getElementById('colFilterMenu');
      const m2 = document.getElementById('colMenu');
      if(m1.classList.contains('show') && !m1.contains(e.target) && !e.target.closest('th.col-filter')){
        m1.classList.remove('show');
      }
      if(m2.classList.contains('show') && !m2.contains(e.target) && e.target.id!=='btnCols'){
        m2.classList.remove('show');
      }
    });

    function applyHeaderFilters(items){
      if(!items || !items.length) return items;
      const active = Array.from(headerFilters.entries());
      if(!active.length) return items;
      return items.filter(row=>{
        for(const [key, selSet] of active){
          if(!selSet || !selSet.size) continue;
          if(key==='winterhardheidszone'){
            const v = String(row[key]??'').trim();
            if(!selSet.has(v)) return false;
          }else if(key==='bodem'){
            const toks = new Set([...tokSplit(row['bodem']), ...tokSplit(row['grondsoorten'])].map(s=>s.toLowerCase()));
            const any = Array.from(selSet).some(s=> toks.has(String(s).toLowerCase()));
            if(!any) return false;
          }else{
            const toks = new Set(tokSplit(row[key]).map(s=>s.toLowerCase()));
            const any = Array.from(selSet).some(s=> toks.has(String(s).toLowerCase()));
            if(!any) return false;
          }
        }
        return true;
      });
    }

    function renderRows(items){
      const tb = document.querySelector('#tbl tbody');
      const vis = getVisibleCols();
      tb.innerHTML = items.map(r=>{
        const tds = vis.map(k=>{
          let v = r[k];
          if(k==='bodem' && !v) v = r['grondsoorten'] || '';
          if(k==='naam'){
            const base = html(v||'');
            const isNative = String(r['inheems']||'').trim().toLowerCase() === 'ja';
            const leaf = isNative ? '<span class="tag-inheems" title="inheems">🍃</span> ' : '';
            return `<td>${leaf}${base}</td>`;
          }
          return `<td>${html(v||'')}</td>`;
        }).join('');
        return `<tr>${tds}</tr>`;
      }).join('');
    }

    function updateCountDisplay(n){ document.getElementById('count').textContent = `${n} resultaten`; }

    function setFilterStatus({useLicht, useVocht, useBodem, sourceCtx=null}){
      const box = document.getElementById('filterStatus');
      const missing = [];
      if(!useLicht){
        missing.push("Er is geen lichtniveau geselecteerd; dit filter wordt niet toegepast.");
      }
      if(!useVocht){
        if(sourceCtx && !sourceCtx.vocht && (!sourceCtx.chosenVocht || sourceCtx.chosenVocht.length===0)){
          missing.push("Er is geen grondwatertrap gevonden op de geselecteerde locatie; er wordt niet op vocht gefilterd.");
        }else{
          missing.push("Er is geen vochtklasse geselecteerd; dit filter wordt niet toegepast.");
        }
      }
      if(!useBodem){
        if(sourceCtx && !sourceCtx.bodem && (!sourceCtx.chosenBodem || sourceCtx.chosenBodem.length===0)){
          missing.push("Er is geen bodemtype gevonden op de geselecteerde locatie; er wordt niet op bodem gefilterd.");
        }else{
          missing.push("Er is geen bodemtype geselecteerd; dit filter wordt niet toegepast.");
        }
      }

      if(missing.length===0){
        box.innerHTML = `<div class="flag ok"><span class="icon">✔</span><span class="text">Alle filters actief</span></div>`;
      }else{
        box.innerHTML = `<div class="flag warn"><span class="icon">⚠</span><span class="text">${missing.join("<br>")}</span></div>`;
      }
    }

    async function refresh(){
      const data = await fetchList();
      _lastItems = data.items||[];
      buildTableHeader();

      const filtered = applyHeaderFilters(_lastItems);
      updateCountDisplay(filtered.length);
      renderRows(filtered);

      const u = computeUsage();
      setFilterStatus({
        useLicht: u.useL,
        useVocht: u.useV,
        useBodem: u.useB,
        sourceCtx: {
          vocht: ui.ctx ? ui.ctx.vocht : null,
          bodem: ui.ctx ? ui.ctx.bodem : null,
          chosenVocht: u.chosenV,
          chosenBodem: u.chosenB
        }
      });
    }

    function renderFromCache(){
      const filtered = applyHeaderFilters(_lastItems);
      updateCountDisplay(filtered.length);
      renderRows(filtered);
    }

    // Klik op de kaart → context + lijst
    map.on('click', async (e)=>{
      if(window._marker) window._marker.remove();
      window._marker = L.marker(e.latlng).addTo(map);
      window._lastLatLng = e.latlng;

      // toon direct een korte melding zodat het duidelijk is dat er geladen wordt
      setClickInfo({ fgr:'(laden...)', bodem:null, bodem_bron:null, gt:null, vocht:null, ahn:null, gmm:null, nsn:null });

      const urlCtx = new URL(location.origin + '/advies/geo');
      urlCtx.searchParams.set('lat', e.latlng.lat);
      urlCtx.searchParams.set('lon', e.latlng.lng);
      const stInh = document.getElementById('stInh');
      const stIng = document.getElementById('stIng');
      const stExo = document.getElementById('stExo');
      const inv = document.getElementById('exInv');
      if(stInh) urlCtx.searchParams.set('toon_inheems', stInh.checked ? 'true' : 'false');
      if(stIng) urlCtx.searchParams.set('toon_ingeburgerd', stIng.checked ? 'true' : 'false');
      if(stExo) urlCtx.searchParams.set('toon_exoot', stExo.checked ? 'true' : 'false');
      if(inv) urlCtx.searchParams.set('exclude_invasief', !!inv.checked);

      try{
        const resp = await fetch(urlCtx);
        const j = await resp.json();

        setClickInfo({ fgr:j.fgr, bodem:j.bodem, bodem_bron:j.bodem_bron, gt:j.gt_code, vocht:j.vocht, ahn:j.ahn, gmm:j.gmm, nsn:j.nsn });

        // bewaar context (gebruikt door refresh / filters)
        ui.ctx = { vocht: j.vocht || null, bodem: j.bodem || null };

        refresh();
      } catch(err){
        console?.error && console.error('Fout bij ophalen advies/geo', err);
        setClickInfo({ fgr:'(kon gegevens niet laden)', bodem:null, bodem_bron:null, gt:null, vocht:null, ahn:null, gmm:null, nsn:null });
      }
    });

    // Bouw de kolomkoppen; de titels zelf zijn de filter-triggers
    function buildTableHeader(){
      const tr = document.getElementById('theadRow');
      tr.innerHTML = '';
      for(const c of COLS.filter(c=>c.visible)){
        const th = document.createElement('th');
        if(c.filterable){ th.classList.add('col-filter'); th.dataset.key = c.key; th.dataset.label = c.label; }
        const wrap = document.createElement('div');
        wrap.className = 'th-wrap';
        const lbl = document.createElement('span');
        lbl.className = 'th-text';
        lbl.textContent = c.label;
        wrap.appendChild(lbl);
        th.appendChild(wrap);
        tr.appendChild(th);
      }
    }

    // Klik op kolomtitel → filtermenu
    document.getElementById('theadRow').addEventListener('click', (e)=>{
      const th = e.target.closest('th.col-filter');
      if(!th) return;
      const key = th.dataset.key;
      const label = th.dataset.label || th.textContent.trim();
      openHeaderFilterMenu(th, key, label);
    });

    (function(){
      const bar = document.getElementById('moreBar');
      const box = document.getElementById('moreFilters');
      const arrow = bar.querySelector('.arrow');
      box.classList.remove('open'); box.style.display='none'; arrow.textContent = '▾';
      bar.addEventListener('click', ()=>{
        const open = box.style.display !== 'none';
        if(open){ box.style.display='none'; box.classList.remove('open'); arrow.textContent='▾'; }
        else    { box.style.display='block'; box.classList.add('open'); arrow.textContent='▴'; }
      });
    })();

    function bindFilterEvents(){
      for(const sel of ['input[name="licht"]','input[name="vocht"]','input[name="bodem"]','input[name="ptype"]','#stInh','#stIng','#stExo','#exInv']){
        document.querySelectorAll(sel).forEach(el=> el.addEventListener('change', refresh));
      }
    }
    bindFilterEvents();

    document.getElementById('btnCSV')?.addEventListener('click', ()=>{
      const qp = window._lastQuery ? window._lastQuery.toString() : '';
      const href = '/export/csv' + (qp ? ('?'+qp) : '');
      window.open(href, '_blank');
    });
    document.getElementById('btnXLSX')?.addEventListener('click', ()=>{
      const qp = window._lastQuery ? window._lastQuery.toString() : '';
      const href = '/export/xlsx' + (qp ? ('?'+qp) : '');
      window.open(href, '_blank');
    });

    document.getElementById('btnCols')?.addEventListener('click', (e)=>{
      openColsMenu(e.currentTarget);
    });

    loadWms().then(()=>{ refresh(); initSplitter(); });
  </script>
</body>
</html>
'''
    return HTMLResponse(
        content=html,
        headers={
            "Cache-Control": "no-store, max-age=0, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )