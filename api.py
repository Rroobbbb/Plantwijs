from __future__ import annotations


def build_locatieprofiel(bodem_label, gt_label, ahn_val, fgr_label, nsn_label):
    """Combineert kernconclusies uit bodem, Gt, hoogte en landschap tot één leesbaar profiel."""
    profiel = {}
    # Waterregime
    if gt_label:
        if any(k in gt_label.lower() for k in ["nat", "zeer nat"]):
            profiel["water"] = "overwegend nat"
        elif any(k in gt_label.lower() for k in ["droog", "zeer droog"]):
            profiel["water"] = "overwegend droog"
        else:
            profiel["water"] = "licht vochtig"
    else:
        profiel["water"] = "onbekend"
    # Reliëf
    try:
        h = float(str(ahn_val).replace(",", "."))
        profiel["reliëf"] = "lage ligging met geringe hoogteverschillen" if h < 10 else "hogere ligging"
    except Exception:
        profiel["reliëf"] = "lichte hoogteverschillen"
    # Landschap
    landschap = "open landschap"
    if fgr_label and any(k in fgr_label.lower() for k in ["bos", "zand", "heuvelland"]):
        landschap = "meer besloten landschap"
    profiel["landschap"] = landschap
    # Kernzin
    profiel["samenvatting"] = (
        f"Deze locatie ligt in een {profiel['landschap']} met {profiel['reliëf']} en een {profiel['water']} waterhuishouding."
    )
    return profiel


import re as _re  # local alias for sentence splitting

def _profile_emphasis(profiel: dict) -> dict:
    """Bepaalt accenten voor tekstlengte en prioriteiten o.b.v. het locatieprofiel."""
    water = (profiel.get("water") or "").lower()
    landschap = (profiel.get("landschap") or "").lower()
    reliëf = (profiel.get("reliëf") or "").lower()

    return {
        "water_first": "nat" in water,
        "drought_first": "droog" in water,
        "open_landscape": "open" in landschap,
        "relief_low": ("lage" in reliëf) or ("geringe" in reliëf),
    }

def _prioritize_principles(principles: list, emph: dict) -> list:
    """Herordent ontwerpuitgangspunten zonder ze te beperken in aantal."""
    def score(item):
        title, body = item
        t = (str(title) + " " + str(body)).lower()
        s = 0
        if emph.get("water_first"):
            if any(k in t for k in ["water", "natte", "poel", "wadi", "berging", "laagte", "kwel"]):
                s += 30
            if any(k in t for k in ["draagkracht", "boom", "boomgroep", "zware"]):
                s += 10
        if emph.get("drought_first"):
            if any(k in t for k in ["droogte", "schaduw", "mulch", "bodembedekking", "luwte", "wind", "vasthouden"]):
                s += 30
        if emph.get("open_landscape"):
            if any(k in t for k in ["openheid", "zicht", "lijnen", "kavel", "dijk", "rand", "concentreer"]):
                s += 20
        if any(k in t for k in ["zonering", "microreliëf", "hoog/laag", "nat/droog", "standplaats"]):
            s += 25
        return s
    return sorted(principles, key=score, reverse=True)

def _shorten_if_needed(txt: str, max_sentences: int = 3) -> str:
    """Maakt toelichting compacter door te knippen op zinnen (voor leesbaarheid)."""
    if not txt:
        return txt


def _top_recommendations(df: "pd.DataFrame", profiel: dict, n: int = 5) -> dict:
    """Maakt een kleine, leesbare topselectie per beplantingsgroep uit de al-gefilterde df.
    Gebruikt alleen bestaande kolommen; faalt stil als iets ontbreekt.
    """
    def getcol(*names):
        for nm in names:
            if nm in df.columns:
                return nm
        return None

    col_nl = getcol("naam", "nederlandse_naam")
    col_wet = getcol("wetenschappelijke_naam", "scientific_name")
    col_type = getcol("beplantingstype", "toepassing_locatie", "toepassing")
    col_vocht = getcol("vocht", "standplaats_bodemvochtigheid")
    col_licht = getcol("standplaats_licht", "licht")
    col_bodem = getcol("grondsoorten", "standplaats_grondsoort")

    water = (profiel.get("water") or "").lower()
    focus = "neutraal"
    if "nat" in water:
        focus = "nat"
    elif "droog" in water:
        focus = "droog"

    def score_row(r):
        s = 0
        t = (str(r.get(col_type, "")) if col_type else "").lower()
        v = (str(r.get(col_vocht, "")) if col_vocht else "").lower()
        # focus op waterregime
        if focus == "nat" and any(k in v for k in ["nat", "vochtig"]):
            s += 10
        if focus == "droog" and any(k in v for k in ["droog", "matig droog"]):
            s += 10
        # open landschap: bonus voor windfilter/haag/singel
        if (profiel.get("landschap") or "").lower().find("open") >= 0:
            if any(k in t for k in ["haag", "singel", "struweel", "wind"]):
                s += 4
        # voorkeur voor inheems/ingeburgerd is al gefilterd, maar geef kleine bonus
        st = str(r.get("status_nl","")).lower()
        if st in ["inheems", "ingeburgerd"]:
            s += 2
        return s

    df2 = df.copy()
    if len(df2) == 0:
        return {}

    # sorteer op score + naam
    try:
        df2["_score"] = df2.apply(score_row, axis=1)
        df2 = df2.sort_values(["_score", col_nl] if col_nl else ["_score"], ascending=[False, True] if col_nl else [False])
    except Exception:
        pass

    def pick(group_keywords):
        if not col_type:
            sub = df2
        else:
            mask = df2[col_type].astype(str).str.lower().apply(lambda x: any(k in x for k in group_keywords))
            sub = df2[mask]
        rows=[]
        for _,r in sub.head(n).iterrows():
            nl = str(r.get(col_nl, "")).strip() if col_nl else ""
            wet = str(r.get(col_wet, "")).strip() if col_wet else ""
            if not nl and not wet:
                continue
            label = nl if nl else wet
            if wet and nl:
                label = f"{nl} (<i>{wet}</i>)"
            elif wet:
                label = f"<i>{wet}</i>"
            # mini-redenering
            reason=[]
            if col_vocht:
                vv=str(r.get(col_vocht,"")).strip()
                if vv:
                    reason.append(vv)
            if col_licht:
                ll=str(r.get(col_licht,"")).strip()
                if ll:
                    reason.append(ll)
            if col_bodem:
                bb=str(r.get(col_bodem,"")).strip()
                if bb:
                    reason.append(bb)
            reason_txt = " — " + ", ".join(reason[:3]) if reason else ""
            rows.append(label + reason_txt)
        return rows

    return {
        "bomen": pick(["boom"]),
        "struweel": pick(["struweel", "haag", "heester", "struik", "singel"]),
        "kruiden": pick(["vaste plant", "kruid", "bodembedekker", "gras"]),
    }

    parts = _re.split(r'(?<=[.!?])\s+', str(txt).strip())
    if len(parts) <= max_sentences:
        return str(txt).strip()
    return " ".join(parts[:max_sentences]).strip()




# PlantWijs API — v3.10.0
# VERBETERINGEN:
# - FIX: PDF filtert nu correct op vocht EN bodem geschiktheid
# - FIX: Plantentabel toont correct beplantingstype (Boom/Heester/Bodembedekker)
# - FIX: Vocht/licht kolommen compact weergegeven
# - FIX: Markdown sterretjes worden gestript uit tekst
# - FIX: Dubbele tekst in FGR sectie voorkomen
# - NIEUW: Ondersteunt inheemse_soorten.csv (gegenereerd uit YAML kennisbibliotheek)
# - NIEUW: Sortering op relevantie (beste matches eerst)
# Starten:
#   cd C:/PlantWijs
#   venv/Scripts/uvicorn api:app --reload --port 9000

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
    # NIEUW: Inheemse soorten CSV (gegenereerd uit kennisbibliotheek_v2 YAML bestanden)
    os.path.join(os.path.dirname(__file__), "data", "inheemse_soorten.csv"),
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
    # basis-categorieën (voor filtering / UI)
    "veen": {"veen"},
    "klei": {"klei"},
    "leem": {"leem", "loess", "löss", "zavel"},
    "zand": {"zand", "dekzand"},
}

# Detailniveau voor kennisbibliotheek (bodem.textuur.*)
# Belangrijk: eerst specifieke termen, pas daarna generiek "klei".
_SOIL_DETAIL_ORDER = [
    ("zware_klei", {"zware klei", "komklei", "kom klei", "komklei/kom", "komgebied", "komklei (", "komklei:"}),
    ("lichte_klei", {"lichte klei", "zavelige klei", "oeverwal", "stroomrugklei", "stroomrug", "oeverwal-/stroomrugklei"}),
    ("klei", {"klei", "rivierklei"}),
    ("veen", {"veen", "venig", "moerig"}),
    ("leem", {"leem", "loess", "löss", "zavel"}),
    ("zand", {"zand", "dekzand"}),
]

def _soil_detail_from_text(text: str) -> Optional[str]:
    t = (text or "").lower()
    for soil, keys in _SOIL_DETAIL_ORDER:
        for k in keys:
            if k and k in t:
                return soil
    return None

def _soil_base_from_detail(detail: Optional[str]) -> Optional[str]:
    if not detail:
        return None
    if detail in ("zware_klei", "lichte_klei"):
        return "klei"
    return detail

def _soil_from_text(text: str) -> Optional[str]:
    # Basislabel (zand/klei/leem/veen) — gebruikt voor filtering
    detail = _soil_detail_from_text(text)
    base = _soil_base_from_detail(detail)
    if base in _SOIL_TOKENS:
        return base
    # fallback: oude token-set
    t = (text or "").lower()
    for soil, keys in _SOIL_TOKENS.items():
        for k in keys:
            if k in t:
                return soil
    return None
def bodem_from_bodemkaart(lat: float, lon: float) -> Tuple[Optional[str], dict]:
    layer = _WMSMETA.get("bodem", {}).get("layer") or "Bodemvlakken"
    props = _wms_getfeatureinfo(BODEM_WMS, layer, lat, lon) or {}

    def _handle_value(val: str) -> Tuple[Optional[str], dict]:
        # 1) probeer detail (lichte_klei / zware_klei) voor kennisbibliotheek
        detail = _soil_detail_from_text(val)
        base = _soil_base_from_detail(detail) or _soil_from_text(val)
        if detail and detail != base:
            # bewaar detail voor rapport/kennislookup
            props["_bodem_detail"] = detail
        props["_bodem_raw_label"] = val
        return (base or val), props

    for k in (
        "grondsoort", "bodem", "BODEM", "BODEMTYPE", "soil", "bodemtype", "SOILAREA_NAME", "NAAM",
        "first_soilname", "normal_soilprofile_name",
    ):
        if k in props and props[k]:
            return _handle_value(str(props[k]))

    if "_text" in props:
        kv = _parse_kv_text(props["_text"]) or {}
        for k in ("grondsoort", "BODEM", "bodemtype", "BODEMNAAM", "NAAM", "omschrijving",
                  "first_soilname", "normal_soilprofile_name"):
            if k in kv and kv[k]:
                return _handle_value(str(kv[k]))
        # geen expliciete key → scan tekstblob
        so_detail = _soil_detail_from_text(props["_text"])
        so_base = _soil_base_from_detail(so_detail) or _soil_from_text(props["_text"])
        if so_detail and so_detail != so_base:
            props["_bodem_detail"] = so_detail
        return so_base, props

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
_CONTEXT_PATH = os.environ.get("CONTEXT_DESCRIPTIONS_PATH", "").strip()
if not _CONTEXT_PATH:
    # Prefer split-knowledge dir if present, else fallback to monolithic file
    # Auto-detect kennisbibliotheek_v2, kennisbibliotheek, of fallback naar single file
    def _detect_kb_path():
        """Detecteer automatisch welke kennisbibliotheek beschikbaar is."""
        search_paths = [
            # Root van repository (meest waarschijnlijk bij GitHub deploy)
            Path(__file__).resolve().parent.parent / "kennisbibliotheek_v2",
            Path(__file__).resolve().parent / "kennisbibliotheek_v2",
            Path.cwd() / "kennisbibliotheek_v2",
            # Legacy paden
            Path(__file__).resolve().parent / "Plantwijs" / "kennisbibliotheek_v2",
            Path(__file__).resolve().parent / "kennisbibliotheek",
            Path(__file__).resolve().parent / "Plantwijs" / "kennisbibliotheek",
            Path.cwd() / "kennisbibliotheek",
        ]
        
        print("[STARTUP] Zoek kennisbibliotheek in:")
        for p in search_paths:
            exists = p.exists() and p.is_dir()
            status = "✓ GEVONDEN" if exists else "✗ niet gevonden"
            print(f"  {status}: {p}")
            if exists:
                # Check of er daadwerkelijk bestanden in zitten
                yaml_count = len(list(p.rglob("*.yaml"))) + len(list(p.rglob("*.yml")))
                print(f"    → {yaml_count} YAML bestanden")
                return str(p)
        
        print("[STARTUP] ⚠️  WAARSCHUWING: Geen kennisbibliotheek gevonden!")
        print("[STARTUP] Fallback naar context_descriptions.yaml (oude stijl)")
        return "context_descriptions.yaml"
    
    _CONTEXT_PATH = _detect_kb_path()

def _resolve_context_sources(path: str) -> list[str]:
    """Vind kennisbronnen: óf één context_descriptions.yaml, óf een map met losse YAML's.
    
    V2 UPGRADE: Ondersteunt nu ook submappen (kennisbibliotheek_v2/lagen/bodem/ etc.)
    
    Backwards compatible:
    - Als 'path' een bestaand bestand is → [path]
    - Als 'path' een bestaande map is → alle *.yaml/*.yml/*.json RECURSIEF
    - Als 'path' niet bestaat:
        * zoek context_descriptions.yaml op bekende plekken
        * zoek map 'kennisbibliotheek' of 'kennisbibliotheek_v2'
    """
    p = str(path or "").strip() or "context_descriptions.yaml"
    candidates = [
        Path(p),
        Path.cwd() / p,
        Path(__file__).resolve().parent / p,
        Path(__file__).resolve().parent / "Plantwijs" / p,
    ]
    
    # Helper: laad RECURSIEF alle YAML bestanden uit een directory
    def _load_recursive(directory: Path) -> list[str]:
        """Laad alle YAML bestanden recursief, met slimme filters."""
        files = []
        try:
            for root, dirs, filenames in os.walk(directory):
                # Skip __pycache__, .git, etc.
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__']
                
                root_path = Path(root)
                
                for filename in filenames:
                    # Alleen YAML/JSON bestanden
                    if not filename.lower().endswith(('.yaml', '.yml', '.json')):
                        continue
                    
                    # Skip privé/template bestanden
                    if filename.startswith('_') or filename.startswith('.'):
                        continue
                    
                    # Skip helper bestanden (GT sub-types, validators, etc.)
                    skip_files = {
                        'bodemtypen.yaml', 'eigenschappen.yaml', 'textuur.yaml',
                        'combinatieregels_bodem_gt.yaml', 'droogtestress_indicator.yaml',
                        'ia.yaml', 'ib.yaml', 'iia.yaml', 'iib.yaml', 'iic.yaml',
                        'iiia.yaml', 'iiib.yaml', 'ivc.yaml', 'ivu.yaml',
                        'kernzinnen_samenvatting.yaml', 'toelichting_algemeen.yaml',
                        'validatie_en_waarschuwingen.yaml',
                        'vad.yaml', 'vao.yaml', 'vbd.yaml', 'vbo.yaml', 
                        'vid.yaml', 'viid.yaml', 'viiid.yaml', 'viiio.yaml',
                        'viio.yaml', 'vio.yaml'
                    }
                    if filename in skip_files:
                        continue
                    
                    full_path = root_path / filename
                    files.append(str(full_path))
        except Exception:
            pass
        
        return sorted(files)
    
    # 1) Direct: bestand (backwards compatible)
    for c in candidates:
        try:
            if c.exists() and c.is_file():
                return [str(c)]
        except Exception:
            continue
    
    # 2) Direct: directory (NU MET RECURSIE)
    for c in candidates:
        try:
            if c.exists() and c.is_dir():
                files = _load_recursive(c)
                if files:
                    return files
        except Exception:
            continue
    
    # 3) Fallback: zoek 'kennisbibliotheek_v2' OF 'kennisbibliotheek'
    kb_candidates = [
        Path.cwd() / "kennisbibliotheek_v2",
        Path(__file__).resolve().parent / "kennisbibliotheek_v2",
        Path(__file__).resolve().parent / "Plantwijs" / "kennisbibliotheek_v2",
        Path.cwd() / "kennisbibliotheek",
        Path(__file__).resolve().parent / "kennisbibliotheek",
        Path(__file__).resolve().parent / "Plantwijs" / "kennisbibliotheek",
    ]
    
    for c in kb_candidates:
        try:
            if c.exists() and c.is_dir():
                files = _load_recursive(c)
                if files:
                    return files
        except Exception:
            continue
    
    # 4) Laatste fallback
    return [str(candidates[0])]

def _resolve_context_path(path: str) -> str:
    """Legacy helper: behoudt oude interface (één pad)."""
    srcs = _resolve_context_sources(path)
    return srcs[0] if srcs else str(path or "context_descriptions.yaml")

def _normalize_key(value: str) -> str:
    """Normaliseer key met COMPLETE mappings voor NSN, GT, Bodem, FGR.
    
    Ondersteunt 75+ WMS varianten → kennisbibliotheek bestandsnamen.
    """
    s = str(value or "").strip().lower()
    if not s:
        return ""
    
    # Basis normalisatie
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\(.*?\)", "", s)  # verwijder haakjesinhoud
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    
    # ========================================================================
    # NSN MAPPINGS (40 landvormen) - WMS varianten → bestandsnaam
    # ========================================================================
    nsn_mappings = {
        # Riviergebied varianten
        'kom': 'komgrond',
        'komgrond': 'komgrond',
        'rivierkom': 'komgrond',
        'komgebied': 'komgrond',
        'oeverwal': 'oeverwal',
        'stroomrug': 'oeverwal',
        'oeverwalflank': 'oeverwalflank',
        'kronkelwaard': 'kronkelwaard',
        'overslaggrond': 'overslaggrond',
        'laagterras': 'laagterras',
        'inversierug': 'inversierug',
        
        # Dekzand varianten
        'dekzandrug': 'dekzandrug',
        'dekzandvlakte': 'dekzandvlakte',
        'dekzandkopje': 'dekzandkopje',
        'dekzandwelving': 'dekzandwelving',
        'esdek': 'esdek',
        
        # Beekdal varianten
        'beekdal': 'beekdal',
        'beekdalflank': 'beekdalflank',
        'beekloop': 'beekloop',
        'brongebied': 'brongebied',
        'droog_dal': 'droog_dal',
        'dalwand': 'dalwand',
        
        # Duinen varianten
        'binnenduin': 'binnenduin',
        'duinvallei': 'duinvallei',
        'embryonaal_duin': 'embryonaal_duin',
        'kustduin': 'kustduin',
        'landduinen': 'landduinen',
        'parabool_duin': 'parabool_duin',
        
        # Kust/getijden varianten
        'gorzen': 'gorzen',
        'kweldervlakte': 'kweldervlakte',
        'kwelderwal': 'kwelderwal',
        'getijdengeul': 'getijdengeul',
        'kreekresten': 'kreekresten',
        
        # Veen varianten
        'hoogveenkern': 'hoogveenkern',
        'lagg': 'lagg',
        
        # Löss varianten
        'loss_droog_dal': 'loss_droog_dal',
        'lossdal': 'loss_droog_dal',
        'lossplateau': 'lossplateau',
        
        # Overig
        'hellingvoet': 'hellingvoet',
        'glaciaal_bekken': 'glaciaal_bekken',
        'grubbenlandschap': 'grubbenlandschap',
        'inlaag': 'inlaag',
        'keileemplateau': 'keileemplateau',
        'laagte': 'laagte',
        'pingoruine': 'pingoruine',
    }
    
    # ========================================================================
    # GT MAPPINGS (8 hoofd + 15 sub = 23 types)
    # ========================================================================
    gt_mappings = {
        # Subtypes (romeins + letter) - BELANGRIJKSTE!
        'gt_ia': 'ia', 'ia': 'ia',
        'gt_ib': 'ib', 'ib': 'ib',
        'gt_iia': 'iia', 'iia': 'iia',
        'gt_iib': 'iib', 'iib': 'iib',
        'gt_iic': 'iic', 'iic': 'iic',
        'gt_iiia': 'iiia', 'iiia': 'iiia',
        'gt_iiib': 'iiib', 'iiib': 'iiib',
        'gt_ivc': 'ivc', 'ivc': 'ivc',
        'gt_ivu': 'ivu', 'ivu': 'ivu',
        'gt_vad': 'vad', 'vad': 'vad',
        'gt_vao': 'vao', 'vao': 'vao',
        'gt_vbd': 'vbd', 'vbd': 'vbd',
        'gt_vbo': 'vbo', 'vbo': 'vbo',
        'gt_vid': 'vid', 'vid': 'vid',
        'gt_vio': 'vio', 'vio': 'vio',  # JOUW VOORBEELD!
        'gt_viid': 'viid', 'viid': 'viid',
        'gt_viio': 'viio', 'viio': 'viio',
        'gt_viiid': 'viiid', 'viiid': 'viiid',
        'gt_viiio': 'viiio', 'viiio': 'viiio',
        
        # Hoofdtypen (romeinse cijfers) - fallback
        'gt_i': 'gt_i', 'i': 'gt_i',
        'gt_ii': 'gt_ii', 'ii': 'gt_ii',
        'gt_iii': 'gt_iii', 'iii': 'gt_iii',
        'gt_iv': 'gt_iv', 'iv': 'gt_iv',
        'gt_v': 'gt_v', 'v': 'gt_v',
        'gt_vi': 'gt_vi', 'vi': 'gt_vi',
        'gt_vii': 'gt_vii', 'vii': 'gt_vii',
        'gt_viii': 'gt_viii', 'viii': 'gt_viii',
    }
    
    # ========================================================================
    # BODEM MAPPINGS (12 types + varianten)
    # ========================================================================
    bodem_mappings = {
        # Klei varianten
        'zware_zeeklei': 'zeeklei_zwaar',
        'zeeklei_zwaar': 'zeeklei_zwaar',
        'zeeklei': 'zeeklei_zwaar',  # default naar zwaar
        'lichte_rivierklei': 'rivierklei_licht',
        'rivierklei_licht': 'rivierklei_licht',
        'rivierklei': 'rivierklei_licht',  # default naar licht
        'kleigrond_zware_zeeklei': 'zeeklei_zwaar',
        'kleigrond_lichte_rivierklei': 'rivierklei_licht',
        
        # Zand varianten
        'zandgrond': 'zandgrond_vaaggrond',
        'zandgrond_vaaggrond': 'zandgrond_vaaggrond',
        'vaaggrond': 'zandgrond_vaaggrond',
        'stuifzand': 'stuifzand',
        
        # Veen varianten
        'veen': 'veengrond',
        'veengrond': 'veengrond',
        
        # Löss varianten
        'loss': 'loss',
        'lossgrond': 'loss',
        
        # Leem varianten
        'leem': 'leemgrond',
        'leemgrond': 'leemgrond',
        
        # Overig
        'beekeerdgrond': 'beekeerdgrond',
        'enkeerdgrond': 'enkeerdgrond',
        'kalkrijk': 'kalkrijk',
        'kalkrijke_grond': 'kalkrijk',
        'keileem': 'keileem',
        'podzol': 'podzolgrond',
        'podzolgrond': 'podzolgrond',
    }
    
    # ========================================================================
    # FGR MAPPINGS (9 regio's + varianten)
    # ========================================================================
    fgr_mappings = {
        'rivierengebied': 'rivierengebied',
        'zeekleigebied': 'zeekleigebied',
        'duingebied': 'duingebied',
        'duinen': 'duingebied',  # variant
        'laagveengebied': 'laagveengebied',
        'dekzandgebied': 'dekzandgebied',
        'hogere_zandgronden': 'dekzandgebied',  # ongeveer
        'heuvelland': 'heuvelland',
        'lossgebied': 'lossgebied',
        'ijsselmeergebied': 'ijsselmeergebied',
        'beekdalengebied': 'beekdalengebied',
        'getijdengebied': 'getijdengebied',
        'waddenzee': 'getijdengebied',  # variant
        'waddengebied': 'getijdengebied',  # variant
    }
    
    # ========================================================================
    # APPLY MAPPINGS
    # ========================================================================
    
    # Check alle mappings in volgorde
    if s in nsn_mappings:
        return nsn_mappings[s]
    if s in gt_mappings:
        return gt_mappings[s]
    if s in bodem_mappings:
        return bodem_mappings[s]
    if s in fgr_mappings:
        return fgr_mappings[s]
    
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
    """Laad kennisbibliotheek.

    Ondersteunt:
    - monolithisch context_descriptions.yaml (oude situatie met top-level keys)
    - split-map 'kennisbibliotheek_v2/lagen/' met submappen per categorie (nieuwe situatie)

    V2 STRATEGIE:
    - Bestanden in `/lagen/bodem/` → worden gegroepeerd onder key 'bodem'
    - Bestanden in `/lagen/gt/` → worden gegroepeerd onder key 'gt'
    - etc.
    - Bestandsnaam zonder extensie wordt de sub-key
    - Bijvoorbeeld: lagen/bodem/zandgrond.yaml → merged['bodem']['zandgrond'] = {...}
    """
    def _deep_merge(a: dict, b: dict) -> dict:
        out = dict(a)
        for k, v in (b or {}).items():
            if k in out and isinstance(out[k], dict) and isinstance(v, dict):
                out[k] = _deep_merge(out[k], v)
            else:
                out[k] = v
        return out

    def _load_one(path: str) -> dict:
        try:
            if not path or not os.path.exists(path):
                return {}
            raw = Path(path).read_text(encoding="utf-8", errors="ignore").strip()
            if not raw:
                return {}
            # 1) PyYAML (indien beschikbaar)
            try:
                import yaml  # type: ignore
                data = yaml.safe_load(raw)
                return data if isinstance(data, dict) else {}
            except Exception:
                pass
            # 2) JSON
            try:
                data = json.loads(raw)
                return data if isinstance(data, dict) else {}
            except Exception:
                # 3) minimal YAML subset
                data = _parse_simple_yaml(raw)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    sources = _resolve_context_sources(_CONTEXT_PATH)
    merged: dict = {}
    
    # DEBUG: Tel hoeveel bestanden per categorie
    category_counts = {}
    
    for p in sources:
        d = _load_one(p)
        if not (isinstance(d, dict) and d):
            continue
        
        # Detecteer of dit een v2 bestand is (zonder top-level category key)
        # door te kijken of het pad een /lagen/ submap bevat
        path_obj = Path(p)
        parts = path_obj.parts
        
        # Zoek naar categorie in pad (bodem, gt, fgr, nsn, soorten, principes)
        category = None
        item_name = path_obj.stem  # bestandsnaam zonder extensie
        
        # Check if path contains /lagen/ or /advies/
        if 'lagen' in parts:
            # Find category after 'lagen'
            try:
                lagen_idx = parts.index('lagen')
                if lagen_idx + 1 < len(parts):
                    category = parts[lagen_idx + 1]
            except ValueError:
                pass
        elif 'advies' in parts:
            # advies/principes/ of advies/soorten/
            try:
                advies_idx = parts.index('advies')
                if advies_idx + 1 < len(parts):
                    category = parts[advies_idx + 1]
            except ValueError:
                pass
        
        # Als we een categorie hebben gevonden, groepeer het bestand
        if category:
            # Initialiseer categorie als het nog niet bestaat
            if category not in merged:
                merged[category] = {}
            
            # Voeg bestand toe onder zijn naam
            merged[category][item_name] = d
            
            # DEBUG: Tel
            category_counts[category] = category_counts.get(category, 0) + 1
        else:
            # Oude stijl: direct mergen (heeft waarschijnlijk top-level keys)
            merged = _deep_merge(merged, d)
    
    # DEBUG: Log wat er geladen is (alleen als PLANTWIJS_DEBUG=true)
    if os.getenv("PLANTWIJS_DEBUG", "").lower() == "true":
        print("[CONTEXT] Kennisbibliotheek geladen:")
        for cat in sorted(merged.keys()):
            if isinstance(merged[cat], dict):
                count = len(merged[cat])
                print(f"  {cat}: {count} items")
                if cat == 'gt':
                    # Toon eerste 5 GT keys
                    gt_keys = list(merged[cat].keys())[:10]
                    print(f"    Sample keys: {gt_keys}")
    
    return merged

CONTEXT_DB = _load_context_db()
try:
    _secs = ', '.join([f"{k}({len(v)})" for k,v in (CONTEXT_DB or {}).items() if isinstance(v, dict)])
    print(f"[CONTEXT] geladen: {_secs} uit {_resolve_context_path(_CONTEXT_PATH)}")
except Exception:
    pass




# Centrale bronregistratie (hybride model): bron-id → volledig record
BRONNEN_DB: dict = (CONTEXT_DB or {}).get("bronnen", {}) if isinstance((CONTEXT_DB or {}).get("bronnen", {}), dict) else {}

def _format_bron(rec: Any) -> str:
    """Maak een compacte, leesbare bron-string (voor UI/PDF)."""
    if rec is None:
        return ""
    if isinstance(rec, str):
        return rec.strip()
    if isinstance(rec, dict):
        auteur = str(rec.get("auteur") or rec.get("auteurs") or "").strip()
        jaar = str(rec.get("jaar") or "").strip()
        titel = str(rec.get("titel") or rec.get("name") or "").strip()
        url = str(rec.get("url") or rec.get("link") or "").strip()
        parts = []
        head = " ".join([p for p in [auteur, f"({jaar})" if jaar else ""] if p]).strip()
        if head:
            parts.append(head)
        if titel:
            parts.append(titel)
        if url:
            parts.append(url)
        return ". ".join([p for p in parts if p]).strip()
    return str(rec).strip()

def _resolve_bronnen(items: Any) -> Any:
    """Vervang bron-id's door volledige bronstrings. Laat URLs/tekst ongemoeid."""
    if not items:
        return items
    if isinstance(items, list):
        out = []
        for it in items:
            s = str(it).strip() if isinstance(it, str) else None
            if s and s in BRONNEN_DB:
                out.append(_format_bron(BRONNEN_DB.get(s)))
            else:
                out.append(_format_bron(it) if isinstance(it, dict) else (str(it).strip() if it is not None else ""))
        # verwijder lege items
        return [x for x in out if str(x).strip()]
    # enkelvoud
    if isinstance(items, str) and items.strip() in BRONNEN_DB:
        return _format_bron(BRONNEN_DB.get(items.strip()))
    return items
def _context_lookup(section: str, label: str) -> dict | None:
    sec = (CONTEXT_DB or {}).get(section, {})
    if not isinstance(sec, dict):
        return None

    def _post(info: dict) -> dict:
        out = dict(info)
        for k in list(out.keys()):
            if k == "bronnen" or k.startswith("bronnen_"):
                out[k] = _resolve_bronnen(out.get(k))
        return out

    want_raw = str(label or "").strip()
    if not want_raw:
        return None

    key = _normalize_key(want_raw)

    # 1) Snelle directe match op top-level key (oude situatie)
    if key and key in sec and isinstance(sec[key], dict):
        return _post(sec[key])

    # 2) Fallback: probeer splits ("stroomrug of stroomgordel", "a, b", etc.)
    parts = []
    if want_raw:
        parts = [p.strip() for p in re.split(r"\s*(?:,|/|\bor\b|\bof\b|\ben\b)\s*", want_raw.lower()) if p.strip()]

    # 3) Diepe zoekactie door nested dicts:
    #    - match op (genormaliseerde) key
    #    - match op titel (exact of substring, zodat "Rivierkom" ook "Rg2 | Rivierkom" vindt)
    candidates: list[tuple[int, dict]] = []

    def _score_title(title: str, target_norm: str) -> int | None:
        nt = _normalize_key(title)
        if not nt:
            return None
        if nt == target_norm:
            return 1
        if target_norm and (target_norm in nt or nt in target_norm):
            # hoe dichter bij elkaar qua lengte, hoe beter
            return 10 + abs(len(nt) - len(target_norm))
        return None

    def _dfs(node: Any) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                nk = _normalize_key(k)

                # key-match
                if nk == key and isinstance(v, dict):
                    candidates.append((0, v))

                # titel-match
                if isinstance(v, dict):
                    t = str(v.get("titel", "") or "").strip()
                    sc = _score_title(t, key)
                    if sc is not None:
                        candidates.append((sc, v))

                _dfs(v)

        elif isinstance(node, list):
            for it in node:
                _dfs(it)

    # zoek op hoofdlabel
    _dfs(sec)

    # zoek ook op parts (als die er zijn)
    for p in parts:
        pk = _normalize_key(p)
        if pk and pk != key:
            key2 = pk
            # hergebruik DFS met "tijdelijke" key door score-functie rechtstreeks te gebruiken op title
            def _dfs_part(node: Any) -> None:
                if isinstance(node, dict):
                    for k, v in node.items():
                        nk = _normalize_key(k)
                        if nk == key2 and isinstance(v, dict):
                            candidates.append((2, v))
                        if isinstance(v, dict):
                            t = str(v.get("titel", "") or "").strip()
                            sc = _score_title(t, key2)
                            if sc is not None:
                                candidates.append((20 + sc, v))
                        _dfs_part(v)
                elif isinstance(node, list):
                    for it in node:
                        _dfs_part(it)
            _dfs_part(sec)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0])
    return _post(candidates[0][1])


def _first_sentence(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    parts = re.split(r"(?<=[.!?])\s+", s, maxsplit=1)
    return parts[0].strip()

app = FastAPI(title="PlantWijs API v3.10.0")
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


# ───────────────────── MODERNE RAPPORT GENERATOR V2

def generate_locatierapport_v2(
    lat: float,
    lon: float,
    context_data: dict,  # Van CONTEXT_DB
    plant_df: Any = None,  # Optional DataFrame
) -> bytes:
    """
    Genereert een modern, gebruiksvriendelijk PDF rapport voor bewoners.
    
    Gebruikt de nieuwe kennisbibliotheek_v2 structuur met:
    - FGR (regio karakteristieken + ontwerp uitgangspunten)
    - NSN (landvorm + ontstaansgeschiedenis + ontwerp tips)
    - Bodem (textuur + chemie + fysisch + plantmogelijkheden)
    - GT (waterstand + plantmogelijkheden + seizoensadvies)
    - Principes (ontwerpuitgangspunten)
    
    Args:
        lat: Latitude
        lon: Longitude
        context_data: Dict met keys zoals:
            - 'fgr': {dict van FGR data}
            - 'nsn': {dict van NSN data}
            - 'bodem': {dict van bodem data}
            - 'gt': {dict van GT data}
            - 'principes': {list van principe dicts}
        plant_df: Optional pandas DataFrame met geschikte planten
    
    Returns:
        bytes: PDF content
    """
    
    # ========================================================================
    # 1. EXTRACT DATA UIT CONTEXT
    # ========================================================================
    
    # Safely extract data with None fallback to empty dict
    fgr_data = context_data.get('fgr') or {}
    nsn_data = context_data.get('nsn') or {}
    bodem_data = context_data.get('bodem') or {}
    gt_data = context_data.get('gt') or {}
    principes = context_data.get('principes') or []
    
    # Labels voor display
    fgr_label = fgr_data.get('titel', 'Onbekend')
    nsn_label = nsn_data.get('titel', 'Onbekend')
    bodem_label = bodem_data.get('titel', 'Onbekend')
    gt_label = gt_data.get('titel', 'Onbekend')
    
    # ========================================================================
    # 2. PDF SETUP
    # ========================================================================
    
    buf = BytesIO()
    W, H = A4
    margin = 18 * mm
    
    # Moderne kleuren (aarde tinten)
    C_PRIMARY = colors.HexColor("#2C5F2D")      # Donkergroen
    C_SECONDARY = colors.HexColor("#97BC62")    # Lichtgroen
    C_MUTED = colors.HexColor("#5C6B7A")        # Grijs
    C_LINE = colors.HexColor("#D8DEE4")         # Lichtgrijs
    C_BG = colors.HexColor("#F8FAF5")           # Crème
    C_ACCENT = colors.HexColor("#D4A574")       # Zand/goud
    
    # Styles
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=C_PRIMARY,
        spaceAfter=8
    )
    
    style_subtitle = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=15,
        textColor=C_MUTED,
        spaceAfter=12
    )
    
    style_h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=20,
        textColor=C_PRIMARY,
        spaceBefore=14,
        spaceAfter=8,
        borderPadding=4,
        leftIndent=0
    )
    
    style_h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=C_PRIMARY,
        spaceBefore=10,
        spaceAfter=6
    )
    
    style_body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        textColor=colors.black,
        spaceAfter=8
    )
    
    style_small = ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13,
        textColor=colors.black
    )
    
    style_caption = ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=9,
        leading=12,
        textColor=C_MUTED
    )
    
    style_tip = ParagraphStyle(
        "Tip",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.black,
        leftIndent=15,
        bulletIndent=5,
        spaceAfter=4
    )
    
    # ========================================================================
    # 3. HEADER/FOOTER FUNCTIE
    # ========================================================================
    
    def _on_page(canv: canvas.Canvas, doc):
        """Tekent header en footer op elke pagina."""
        canv.saveState()
        
        # Header balk
        bar_h = 15 * mm
        canv.setFillColor(C_PRIMARY)
        canv.rect(0, H - bar_h, W, bar_h, stroke=0, fill=1)
        
        canv.setFillColor(colors.white)
        canv.setFont("Helvetica-Bold", 11)
        canv.drawString(margin, H - bar_h + 5 * mm, "Beplantingsadvies voor uw locatie")
        
        canv.setFont("Helvetica", 9)
        canv.drawRightString(W - margin, H - bar_h + 5 * mm, 
                           datetime.now().strftime("%d-%m-%Y"))
        
        # Footer lijn + info
        canv.setStrokeColor(C_LINE)
        canv.setLineWidth(0.5)
        canv.line(margin, margin - 3 * mm, W - margin, margin - 3 * mm)
        
        canv.setFillColor(C_MUTED)
        canv.setFont("Helvetica", 8)
        canv.drawString(margin, margin - 7 * mm, 
                       f"Locatie: {lat:.6f}°N, {lon:.6f}°E")
        canv.drawRightString(W - margin, margin - 7 * mm, 
                            f"Pagina {doc.page}")
        
        canv.restoreState()
    
    # ========================================================================
    # 4. DOC SETUP
    # ========================================================================
    
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=23 * mm,
        bottomMargin=18 * mm,
        title="Beplantingsadvies",
        author="Plantwijs"
    )
    
    story: List[Any] = []
    
    # ========================================================================
    # 5. TITELPAGINA
    # ========================================================================
    
    story.append(Paragraph("Beplantingsadvies voor uw locatie", style_title))
    story.append(Paragraph(
        f"Gebaseerd op natuurlijke omstandigheden van uw perceel",
        style_subtitle
    ))
    
    story.append(Spacer(1, 10))
    
    # Locatie samenvatting tabel
    summary_data = [
        [Paragraph("<b>Locatie</b>", style_small), 
         Paragraph(f"{lat:.6f}°N, {lon:.6f}°E", style_small)],
        [Paragraph("<b>Regio</b>", style_small), 
         Paragraph(fgr_label, style_small)],
        [Paragraph("<b>Landvorm</b>", style_small), 
         Paragraph(nsn_label, style_small)],
        [Paragraph("<b>Bodem</b>", style_small), 
         Paragraph(bodem_label, style_small)],
        [Paragraph("<b>Grondwater</b>", style_small), 
         Paragraph(gt_label, style_small)],
    ]
    
    summary_table = Table(summary_data, colWidths=[50*mm, 125*mm])
    summary_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, C_LINE),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, -1), C_BG),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 15))
    
    # ========================================================================
    # 6. KERNSAMENVATTING
    # ========================================================================
    
    story.append(Paragraph("📍 Kernsamenvatting", style_h1))
    
    # Haal duiding op uit alle lagen
    samenvatting_delen = []
    
    # FGR karakterisering
    if fgr_data:
        fgr_karakteristiek = (
            fgr_data.get('geografie', {}).get('karakteristiek', '') or
            fgr_data.get('duiding', {}).get('rapporttekst', '')
        )
        if fgr_karakteristiek:
            # Eerste zin
            eerste_zin = fgr_karakteristiek.split('.')[0] + '.'
            samenvatting_delen.append(eerste_zin)
    
    # Bodem in één zin
    if bodem_data:
        bodem_kwaliteit = bodem_data.get('bodem', {}).get('kwaliteit', '') or \
                         bodem_data.get('chemie', {}).get('voedselrijkdom', {}).get('algemeen', '')
        bodem_pH = bodem_data.get('chemie', {}).get('pH', {}).get('classificatie', '')
        
        if bodem_kwaliteit or bodem_pH:
            bodem_zin = f"De bodem is {bodem_pH.lower() if bodem_pH else ''} " \
                       f"en {bodem_kwaliteit.lower() if bodem_kwaliteit else 'matig'}."
            samenvatting_delen.append(bodem_zin.replace('  ', ' '))
    
    # GT waterstand
    if gt_data:
        gt_cat = gt_data.get('categorie', '')
        if gt_cat:
            samenvatting_delen.append(f"De waterhuishouding is {gt_cat.lower()}.")
    
    # Combineer
    if samenvatting_delen:
        samenvatting = ' '.join(samenvatting_delen)
        story.append(Paragraph(samenvatting, style_body))
    else:
        story.append(Paragraph(
            "Op basis van de kaartgegevens is een passend beplantingsadvies samengesteld.",
            style_body
        ))
    
    story.append(Spacer(1, 10))
    
    # ========================================================================
    # 6.5 KAART
    # ========================================================================
    
    # Voeg kaart toe (zoals oude rapport)
    map_img = _static_map_image(lat, lon, z=16, tiles=2)
    if map_img:
        try:
            rl_map = RLImage(map_img, width=175 * mm, height=90 * mm)
            story.append(rl_map)
            story.append(Paragraph(
                f"<i>Kaart van de locatie ({lat:.5f}°N, {lon:.5f}°E)</i>",
                style_caption
            ))
        except Exception:
            pass  # Skip bij error
    
    story.append(PageBreak())
    
    # ========================================================================
    # 7. UW SITUATIE - DETAIL PER LAAG
    # ========================================================================
    
    story.append(Paragraph("🌍 Uw situatie in detail", style_h1))
    story.append(Paragraph(
        "Hieronder leest u wat de verschillende aspecten van uw locatie betekenen " \
        "voor beplanting. Elk aspect geeft een ander perspectief op dezelfde plek.",
        style_caption
    ))
    story.append(Spacer(1, 8))
    
    # ------------------
    # 7.1 REGIO (FGR)
    # ------------------
    story.append(Paragraph(f"Regio: {fgr_label}", style_h2))
    
    if fgr_data:
        # Helper om markdown te strippen
        def strip_markdown(text):
            if not text:
                return text
            # Verwijder **bold** en *italic* markers
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', str(text))
            text = re.sub(r'\*([^*]+)\*', r'\1', text)
            return text.strip()
        
        # Houd bij welke tekst al getoond is (voorkom duplicatie)
        getoonde_teksten = set()
        
        # 1. Geografie - karakteristiek
        geografie = fgr_data.get('geografie', {})
        if geografie and isinstance(geografie, dict):
            karakteristiek = strip_markdown(geografie.get('karakteristiek', ''))
            if karakteristiek and karakteristiek not in getoonde_teksten:
                story.append(Paragraph(f"<b>Karakteristiek:</b> {karakteristiek}", style_body))
                getoonde_teksten.add(karakteristiek)
        
        # 2. Landschappelijke context
        landschap = fgr_data.get('landschappelijke_context', {})
        if landschap and isinstance(landschap, dict):
            context = strip_markdown(landschap.get('beschrijving', '') or landschap.get('algemeen', ''))
            if context and context not in getoonde_teksten:
                story.append(Paragraph(f"<b>Landschap:</b> {context}", style_body))
                getoonde_teksten.add(context)
        
        # 3. Typische bodems (van FGR, niet van bodemkaart)
        bodem_fgr = fgr_data.get('bodem', {})
        if bodem_fgr and isinstance(bodem_fgr, dict):
            bodem_tekst = strip_markdown(bodem_fgr.get('karakteristiek', '') or bodem_fgr.get('typisch', ''))
            if bodem_tekst and bodem_tekst not in getoonde_teksten:
                story.append(Paragraph(f"<b>Typische bodems:</b> {bodem_tekst}", style_body))
                getoonde_teksten.add(bodem_tekst)
        
        # 4. Betekenis voor erfbeplanting
        beplanting = fgr_data.get('betekenis_voor_erfbeplanting', {})
        if beplanting and isinstance(beplanting, dict):
            algemeen = strip_markdown(beplanting.get('algemeen', '') or beplanting.get('beschrijving', ''))
            if algemeen and algemeen not in getoonde_teksten:
                story.append(Paragraph(f"<b>Voor erfbeplanting:</b> {algemeen}", style_body))
                getoonde_teksten.add(algemeen)
    else:
        story.append(Paragraph("Geen specifieke informatie beschikbaar voor deze regio.", style_caption))
    
    story.append(Spacer(1, 6))
    
    # ------------------
    # 7.2 LANDVORM (NSN)
    # ------------------
    story.append(Paragraph(f"Landvorm: {nsn_label}", style_h2))
    
    if nsn_data:
        # 1. Ontstaansgeschiedenis
        ontstaan = nsn_data.get('ontstaansgeschiedenis', {})
        if ontstaan and isinstance(ontstaan, dict):
            ontstaan_tekst = ontstaan.get('beschrijving', '') or ontstaan.get('proces', '')
            if ontstaan_tekst:
                story.append(Paragraph(f"<b>Hoe ontstond deze landvorm?</b> {ontstaan_tekst}", style_body))
            
            periode = ontstaan.get('periode', '')
            if periode:
                story.append(Paragraph(f"<i>Periode: {periode}</i>", style_caption))
        
        # 2. Landvorm algemeen
        landvorm = nsn_data.get('landvorm', {})
        if landvorm and isinstance(landvorm, dict):
            # Hoogteligging
            hoogte = landvorm.get('hoogteligging', {})
            if hoogte and isinstance(hoogte, dict):
                hoogte_tekst = hoogte.get('beschrijving', '') or hoogte.get('relatief', '')
                if hoogte_tekst:
                    story.append(Paragraph(f"<b>Hoogteligging:</b> {hoogte_tekst}", style_body))
            
            # Positie
            positie = landvorm.get('positie_in_landschap', {})
            if positie and isinstance(positie, dict):
                positie_tekst = positie.get('beschrijving', '')
                if positie_tekst:
                    story.append(Paragraph(f"<b>Positie:</b> {positie_tekst}", style_body))
            
            # Reliëf
            relief = landvorm.get('relief', '')
            if relief:
                story.append(Paragraph(f"<b>Reliëf:</b> {relief}", style_body))
        
        # 3. Hydromorfologie
        hydro = nsn_data.get('hydromorfologie', {})
        if hydro and isinstance(hydro, dict):
            drainage = hydro.get('drainage', '') or hydro.get('waterhuishouding', '')
            if drainage:
                story.append(Paragraph(f"<b>Waterhuishouding:</b> {drainage}", style_body))
        
        # 4. Duiding
        duiding = nsn_data.get('duiding', {})
        if duiding and isinstance(duiding, dict):
            rapporttekst = duiding.get('rapporttekst', '') or duiding.get('beschrijving', '')
            if rapporttekst:
                paragrafen = [p.strip() for p in rapporttekst.split('\n\n') if p.strip()]
                for p in paragrafen[:2]:
                    story.append(Paragraph(p, style_body))
        
        # 5. Betekenis voor erfbeplanting
        beplanting = nsn_data.get('betekenis_voor_erfbeplanting', {})
        if beplanting and isinstance(beplanting, dict):
            algemeen = beplanting.get('algemeen', '') or beplanting.get('beschrijving', '')
            if algemeen:
                story.append(Paragraph(f"<b>Voor erfbeplanting:</b> {algemeen}", style_body))
    else:
        story.append(Paragraph("Geen informatie beschikbaar voor deze landvorm.", style_caption))
    
    story.append(Spacer(1, 6))
    
    # ------------------
    # 7.3 BODEM
    # ------------------
    story.append(Paragraph(f"Bodemtype: {bodem_label}", style_h2))
    
    if bodem_data:
        # Textuur
        textuur = bodem_data.get('textuur', {})
        if textuur:
            textuur_beschr = textuur.get('beschrijving', '')
            if textuur_beschr:
                story.append(Paragraph(
                    f"<b>Hoe voelt de grond aan?</b> {textuur_beschr}",
                    style_body
                ))
        
        # Chemie (pH + voeding)
        chemie = bodem_data.get('chemie', {})
        if chemie:
            pH_info = chemie.get('pH', {})
            voeding_info = chemie.get('voedselrijkdom', {})
            
            chemie_punten = []
            if pH_info:
                chemie_punten.append(
                    f"pH: {pH_info.get('range', '')} ({pH_info.get('classificatie', '')})"
                )
            if voeding_info:
                chemie_punten.append(
                    f"Voeding: {voeding_info.get('algemeen', '')}"
                )
            
            if chemie_punten:
                story.append(Paragraph(
                    "<b>Bodemchemie:</b> " + ", ".join(chemie_punten),
                    style_body
                ))
        
        # Fysisch (doorlatendheid, vocht)
        fysisch = bodem_data.get('fysisch', {})
        if fysisch:
            doorlat = fysisch.get('doorlatendheid', {})
            vocht = fysisch.get('vochtvasthoudend_vermogen', {})
            
            if doorlat or vocht:
                fysisch_tekst = "<b>Watereigenschappen:</b> "
                delen = []
                if doorlat:
                    delen.append(f"Doorlatendheid {doorlat.get('verticaal', '')}")
                if vocht:
                    delen.append(f"Vochtvast {vocht.get('capaciteit', '')}")
                
                story.append(Paragraph(fysisch_tekst + ", ".join(delen).lower(), style_body))
    
    story.append(Spacer(1, 6))
    
    # ------------------
    # 7.4 GRONDWATER (GT)
    # ------------------
    story.append(Paragraph(f"Grondwater: {gt_label}", style_h2))
    
    if gt_data:
        # GHG + GLG
        gws = gt_data.get('grondwaterstand', {})
        if gws:
            ghg = gws.get('gemiddeld_hoogste_grondwaterstand', {})
            glg = gws.get('gemiddeld_laagste_grondwaterstand', {})
            
            if ghg or glg:
                gw_tekst = []
                if ghg:
                    gw_tekst.append(f"Winter: {ghg.get('diepte_cm', '')}")
                if glg:
                    gw_tekst.append(f"Zomer: {glg.get('diepte_cm', '')}")
                
                if gw_tekst:
                    story.append(Paragraph(
                        "<b>Grondwaterstand:</b> " + ", ".join(gw_tekst),
                        style_body
                    ))
        
        # Droogtegevoeligheid
        waterregime = gt_data.get('waterregime', {})
        if waterregime:
            droogte = waterregime.get('droogtegevoeligheid', {})
            if droogte:
                droogte_tekst = droogte.get('beschrijving', '')
                if droogte_tekst:
                    story.append(Paragraph(
                        f"<b>Droogte:</b> {droogte_tekst}",
                        style_body
                    ))
    
    story.append(PageBreak())
    
    # ========================================================================
    # 8. PRAKTISCH ADVIES - WAT TE DOEN?
    # ========================================================================
    
    story.append(Paragraph("🌱 Praktisch beplantingsadvies", style_h1))
    story.append(Paragraph(
        "Op basis van uw bodem, water en landschap zijn hier de belangrijkste aanbevelingen:",
        style_caption
    ))
    story.append(Spacer(1, 8))
    
    # Verzamel alle ontwerp uitgangspunten + praktische tips
    heeft_advies = False
    
    # 1. Van FGR (Regio)
    if fgr_data:
        beplanting_fgr = fgr_data.get('betekenis_voor_erfbeplanting', {})
        
        if beplanting_fgr and isinstance(beplanting_fgr, dict):
            story.append(Paragraph("<b>Regio:</b>", style_h2))
            
            # Ontwerp uitgangspunten
            ontwerp_tips = beplanting_fgr.get('ontwerp_uitgangspunten', [])
            if ontwerp_tips and isinstance(ontwerp_tips, list):
                for tip in ontwerp_tips[:5]:  # Max 5
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            # Algemeen advies
            algemeen = beplanting_fgr.get('algemeen', '') or beplanting_fgr.get('beschrijving', '')
            if algemeen and not ontwerp_tips:
                story.append(Paragraph(algemeen, style_body))
                heeft_advies = True
            
            if heeft_advies:
                story.append(Spacer(1, 6))
    
    # 2. Van NSN (Landvorm)  
    if nsn_data:
        beplanting_nsn = nsn_data.get('betekenis_voor_erfbeplanting', {})
        
        if beplanting_nsn and isinstance(beplanting_nsn, dict):
            story.append(Paragraph("<b>Landvorm:</b>", style_h2))
            
            # Ontwerp uitgangspunten
            ontwerp_tips = beplanting_nsn.get('ontwerp_uitgangspunten', [])
            if ontwerp_tips and isinstance(ontwerp_tips, list):
                for tip in ontwerp_tips[:5]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            # Praktische adviezen
            praktisch = beplanting_nsn.get('praktische_adviezen', [])
            if praktisch and isinstance(praktisch, list):
                for tip in praktisch[:3]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            if heeft_advies:
                story.append(Spacer(1, 6))
    
    # 3. Van Bodem
    if bodem_data:
        beplanting_bodem = bodem_data.get('betekenis_voor_erfbeplanting', {})
        
        if beplanting_bodem and isinstance(beplanting_bodem, dict):
            story.append(Paragraph("<b>Bodem:</b>", style_h2))
            
            # Aandachtspunten
            aandacht = beplanting_bodem.get('aandachtspunten', [])
            if aandacht and isinstance(aandacht, list):
                for tip in aandacht[:5]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            # Praktische tips
            praktisch = beplanting_bodem.get('praktische_tips', [])
            if praktisch and isinstance(praktisch, list):
                for tip in praktisch[:3]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            if heeft_advies:
                story.append(Spacer(1, 6))
        
        # EXTRA: Praktische adviezen top-level
        praktisch_adv = bodem_data.get('praktische_adviezen', {})
        if praktisch_adv and isinstance(praktisch_adv, dict):
            werkbaarheid = praktisch_adv.get('werkbaarheid', [])
            if werkbaarheid and isinstance(werkbaarheid, list):
                if not heeft_advies:
                    story.append(Paragraph("<b>Bodem:</b>", style_h2))
                for tip in werkbaarheid[:3]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
                story.append(Spacer(1, 6))
    
    # 4. Van GT (Water)
    if gt_data:
        beplanting_gt = gt_data.get('betekenis_voor_erfbeplanting', {})
        
        if beplanting_gt and isinstance(beplanting_gt, dict):
            story.append(Paragraph("<b>Water:</b>", style_h2))
            
            # Seizoens aandacht
            seizoen = beplanting_gt.get('seizoens_aandacht', [])
            if seizoen and isinstance(seizoen, list):
                for tip in seizoen[:5]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            # Praktische tips
            praktisch = beplanting_gt.get('praktische_tips', [])
            if praktisch and isinstance(praktisch, list):
                for tip in praktisch[:3]:
                    story.append(Paragraph(f"• {tip}", style_tip))
                heeft_advies = True
            
            if heeft_advies:
                story.append(Spacer(1, 6))
    
    # Fallback als er GEEN advies is
    if not heeft_advies:
        story.append(Paragraph(
            "Plant in voorjaar of najaar, verbeter de bodem met compost, en kies soorten " \
            "die passen bij uw grondwaterstand.",
            style_body
        ))
    
    story.append(Spacer(1, 10))
    
    # ========================================================================
    # 9. GESCHIKTE SOORTEN
    # ========================================================================
    
    story.append(Paragraph("🌳 Welke planten passen hier?", style_h1))
    
    # Van alle lagen: verzamel geschikte soorten
    geschikte_soorten = []
    
    # Bodem plantmogelijkheden
    if bodem_data:
        bodem_soorten = bodem_data.get('plantmogelijkheden', {}).get('geschikte_soorten', [])
        if bodem_soorten:
            geschikte_soorten.extend(bodem_soorten[:5])
    
    # GT plantmogelijkheden
    if gt_data:
        gt_soorten = gt_data.get('plantmogelijkheden', {}).get('zeer_geschikt', [])
        if gt_soorten:
            geschikte_soorten.extend(gt_soorten[:5])
    
    # Render lijst
    if geschikte_soorten:
        story.append(Paragraph(
            "<b>Top aanbevelingen voor uw situatie:</b>",
            style_body
        ))
        
        for soort in geschikte_soorten[:10]:  # Max 10
            # Parse "Soort naam - uitleg"
            if ' - ' in soort:
                naam, uitleg = soort.split(' - ', 1)
                story.append(Paragraph(
                    f"<b>• {naam.strip()}</b> - {uitleg.strip()}",
                    style_tip
                ))
            else:
                story.append(Paragraph(f"• {soort}", style_tip))
        
        story.append(Spacer(1, 8))
    
    # Als er een plant_df is, render UITGEBREIDE tabel
    if plant_df is not None and len(plant_df) > 0:
        story.append(Paragraph(
            "<b>Geschikte soorten voor uw locatie:</b>",
            style_body
        ))
        story.append(Spacer(1, 4))
        
        # ============================================================
        # VERBETERDE KOLOM DETECTIE
        # ============================================================
        
        def get_col(df, *options):
            """Vind eerste bestaande kolom uit opties."""
            for opt in options:
                if opt in df.columns:
                    return opt
            return None
        
        col_naam = get_col(plant_df, 'naam', 'nederlandse_naam')
        col_type = get_col(plant_df, 'beplantingstype', 'type')
        col_vocht = get_col(plant_df, 'vocht', 'standplaats_bodemvochtigheid')
        col_licht = get_col(plant_df, 'standplaats_licht', 'licht')
        
        # Maak tabel header
        tabel_data = [[
            Paragraph("<b>Naam</b>", style_small),
            Paragraph("<b>Type</b>", style_small),
            Paragraph("<b>Vocht</b>", style_small),
            Paragraph("<b>Licht</b>", style_small),
            Paragraph("<b>Hoogte</b>", style_small)
        ]]
        
        col_widths = [55*mm, 25*mm, 35*mm, 35*mm, 20*mm]
        
        for idx, row in plant_df.head(20).iterrows():
            # ============================================================
            # VERBETERDE DATA EXTRACTIE
            # ============================================================
            
            # Naam
            naam = str(row.get(col_naam, '') if col_naam else '').strip()
            if not naam:
                naam = str(row.get('wetenschappelijke_naam', '?')).strip()
            
            # Type - gebruik de al afgeleide beplantingstype kolom
            if col_type and col_type in row.index:
                soort_type = str(row.get(col_type, '')).strip()
                if not soort_type or soort_type.lower() in ('nan', 'none', ''):
                    soort_type = 'Boom'
            else:
                soort_type = 'Boom'
            
            # Vocht - compact maken
            vocht = '-'
            if col_vocht:
                vocht_raw = str(row.get(col_vocht, '') or '').strip()
                if vocht_raw and vocht_raw.lower() not in ('nan', 'none', ''):
                    # Verkort lange waarden
                    vocht_parts = [v.strip() for v in re.split(r'[;/|]+', vocht_raw) if v.strip()]
                    vocht_short = []
                    for v in vocht_parts[:3]:
                        v_lower = v.lower()
                        if 'zeer droog' in v_lower:
                            vocht_short.append('z.droog')
                        elif 'zeer nat' in v_lower:
                            vocht_short.append('z.nat')
                        elif 'droog' in v_lower:
                            vocht_short.append('droog')
                        elif 'nat' in v_lower:
                            vocht_short.append('nat')
                        elif 'vochtig' in v_lower:
                            vocht_short.append('vochtig')
                        else:
                            vocht_short.append(v[:8])
                    vocht = ' / '.join(vocht_short) if vocht_short else '-'
            
            # Licht - compact maken
            licht = '-'
            if col_licht:
                licht_raw = str(row.get(col_licht, '') or '').strip()
                if licht_raw and licht_raw.lower() not in ('nan', 'none', ''):
                    licht_parts = [l.strip() for l in re.split(r'[;/|]+', licht_raw) if l.strip()]
                    licht_short = []
                    for l in licht_parts[:3]:
                        l_lower = l.lower()
                        if 'halfschaduw' in l_lower or 'half' in l_lower:
                            licht_short.append('½schaduw')
                        elif 'schaduw' in l_lower:
                            licht_short.append('schaduw')
                        elif 'zon' in l_lower:
                            licht_short.append('zon')
                        else:
                            licht_short.append(l[:8])
                    licht = ' / '.join(licht_short) if licht_short else '-'
            
            # Hoogte
            hoogte = str(row.get('hoogte', '') or row.get('eigenschappen_hoogte', '') or '').strip()
            if not hoogte or hoogte.lower() in ('nan', 'none', ''):
                hoogte = '-'
            elif len(hoogte) > 12:
                hoogte = hoogte[:12]
            
            # Voeg rij toe
            tabel_data.append([
                naam,
                soort_type,
                vocht,
                licht,
                hoogte
            ])
        
        # Maak tabel
        soorten_tabel = Table(tabel_data, colWidths=col_widths)
        soorten_tabel.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C_SECONDARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 0), (-1, 0), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, C_LINE),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, C_BG]),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        
        story.append(soorten_tabel)
        
        # Legenda en info
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            "<i>Vocht: z.droog=zeer droog, z.nat=zeer nat · Licht: ½schaduw=halfschaduw</i>",
            style_caption
        ))
        
        # Toon hoeveel planten er zijn
        if len(plant_df) > 20:
            story.append(Paragraph(
                f"<i>Getoond: 20 van {len(plant_df)} geschikte soorten voor deze locatie</i>",
                style_caption
            ))
    
    story.append(Spacer(1, 10))
    
    # ========================================================================
    # 10. FOOTER / DISCLAIMER
    # ========================================================================
    
    story.append(PageBreak())
    story.append(Paragraph("ℹ️ Over dit advies", style_h1))
    story.append(Paragraph(
        "Dit advies is gebaseerd op openbare data over bodem, water en landschap. " \
        "Het geeft algemene richtlijnen voor inheemse beplanting die past bij uw locatie.",
        style_body
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Let op:</b> Lokale omstandigheden kunnen afwijken. Bij twijfel of voor " \
        "specifieke vragen kunt u altijd contact opnemen met een hovenier of landschapsarchitect.",
        style_caption
    ))
    
    # ========================================================================
    # 11. BUILD PDF
    # ========================================================================
    
    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    
    return buf.getvalue()

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
# VERBETERDE VERSIE met correcte filtering op vocht/bodem geschiktheid
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
    Genereert een locatierapport als PDF met CORRECTE filtering op geschiktheid.
    
    Verbeteringen t.o.v. oude versie:
    - Filtert planten op vocht-compatibiliteit (natte grond → alleen nat-tolerante planten)
    - Filtert planten op bodem-compatibiliteit (klei → alleen klei-tolerante planten)
    - Correcte beplantingstype afleiding (Boom/Heester/Bodembedekker)
    - Sortering op relevantie (beste matches eerst)
    """
    # ========================================================================
    # 1) HAAL KAARTDATA OP
    # ========================================================================
    
    fgr = fgr_from_point(lat, lon) or "Onbekend"
    nsn_val = nsn_from_point(lat, lon) or ""
    bodem_raw, _props_bodem = bodem_from_bodemkaart(lat, lon)
    vocht_raw, _props_gwt, gt_code = vocht_from_gwt(lat, lon)
    ahn_val, _props_ahn = ahn_from_wms(lat, lon)
    gmm_val, _props_gmm = gmm_from_wms(lat, lon)
    
    # Bepaal filter waarden (UI override of kaartdata)
    filter_bodem = bodem[0] if bodem else bodem_raw
    filter_vocht = vocht[0] if vocht else vocht_raw
    
    # DEBUG logging
    if os.getenv("PLANTWIJS_DEBUG", "").lower() == "true":
        print(f"[PDF] Locatie: {lat}, {lon}")
        print(f"[PDF] FGR: {fgr}, NSN: {nsn_val}")
        print(f"[PDF] Bodem: {bodem_raw} → filter: {filter_bodem}")
        print(f"[PDF] Vocht: {vocht_raw} → filter: {filter_vocht}")
        print(f"[PDF] GT: {gt_code}")
    
    # ========================================================================
    # 2) HAAL CONTEXT DATA OP UIT KENNISBIBLIOTHEEK
    # ========================================================================
    
    context_data = {
        'fgr': _context_lookup('fgr', _normalize_key(fgr)) or {} if fgr and fgr != "Onbekend" else {},
        'nsn': _context_lookup('nsn', _normalize_key(nsn_val)) or {} if nsn_val else {},
        'bodem': _context_lookup('bodem', _normalize_key(filter_bodem or bodem_raw)) or {} if (filter_bodem or bodem_raw) else {},
        'gt': _context_lookup('gt', _normalize_key(gt_code)) or {} if gt_code else {},
    }
    
    # ========================================================================
    # 3) PLANT SELECTIE MET CORRECTE FILTERING
    # ========================================================================
    
    df = get_df()
    original_count = len(df)
    
    # Helper functie voor multi-value matching
    def _has_any_value(cell, choices):
        if not choices:
            return True
        tokens = {t.strip().lower() for t in re.split(r"[;/|]+", str(cell or "")) if t.strip()}
        want = {w.strip().lower() for w in choices if str(w).strip()}
        return bool(tokens & want)
    
    # Filter op status (inheems + ingeburgerd)
    if "status_nl" in df.columns:
        s = df["status_nl"].astype(str).str.lower().str.strip()
        df = df[s.isin(["inheems", "ingeburgerd"])]
    
    # Filter invasief
    if exclude_invasief and "invasief" in df.columns:
        inv = df["invasief"].astype(str).str.lower().str.strip()
        df = df[~inv.isin(["ja", "invasief", "invasieve exoot"])]
    
    # ============================================================
    # KRITIEKE FIX: Filter op VOCHT geschiktheid
    # ============================================================
    
    if filter_vocht and "vocht" in df.columns:
        vocht_lower = filter_vocht.lower()
        
        # Map vocht naar compatible plant voorkeuren
        if "zeer nat" in vocht_lower:
            compatible_vocht = ["nat", "zeer nat", "vochtig"]
        elif "nat" in vocht_lower:
            compatible_vocht = ["nat", "vochtig", "zeer nat"]
        elif "vochtig" in vocht_lower:
            compatible_vocht = ["vochtig", "nat", "droog"]
        elif "zeer droog" in vocht_lower:
            compatible_vocht = ["zeer droog", "droog"]
        elif "droog" in vocht_lower:
            compatible_vocht = ["droog", "zeer droog", "vochtig"]
        else:
            compatible_vocht = []
        
        if compatible_vocht:
            before_vocht = len(df)
            df = df[df["vocht"].apply(lambda v: _has_any_value(v, compatible_vocht))]
            if os.getenv("PLANTWIJS_DEBUG", "").lower() == "true":
                print(f"[PDF] Vocht filter: {before_vocht} → {len(df)} planten")
    
    # ============================================================
    # KRITIEKE FIX: Filter op BODEM geschiktheid
    # ============================================================
    
    if filter_bodem:
        bodem_lower = filter_bodem.lower()
        
        # Bepaal compatible grondsoorten
        if "klei" in bodem_lower or "zavel" in bodem_lower:
            compatible_bodem = ["klei", "zavel", "leem", "zware klei", "lichte klei", "alle"]
        elif "zand" in bodem_lower:
            compatible_bodem = ["zand", "lemig zand", "alle"]
        elif "veen" in bodem_lower:
            compatible_bodem = ["veen", "venig", "alle"]
        elif "leem" in bodem_lower or "löss" in bodem_lower or "loss" in bodem_lower:
            compatible_bodem = ["leem", "löss", "loss", "klei", "zavel", "alle"]
        else:
            compatible_bodem = []
        
        if compatible_bodem:
            def matches_bodem(row):
                bodem_val = str(row.get("bodem", "") or "").lower()
                grond_val = str(row.get("grondsoorten", "") or "").lower()
                combined = bodem_val + " " + grond_val
                # "alle grondsoorten" of "alle" betekent altijd geschikt
                if "alle" in combined:
                    return True
                return any(b in combined for b in compatible_bodem)
            
            before_bodem = len(df)
            df = df[df.apply(matches_bodem, axis=1)]
            if os.getenv("PLANTWIJS_DEBUG", "").lower() == "true":
                print(f"[PDF] Bodem filter: {before_bodem} → {len(df)} planten")
    
    # ============================================================
    # FIX: Voeg beplantingstype kolom toe indien nodig
    # ============================================================
    
    df = df.copy()
    
    if "beplantingstype" not in df.columns:
        def _derive_beplantingstype(row):
            """Bepaal of het een boom, heester of bodembedekker is."""
            # Check expliciete type kolom
            soort_type = str(row.get("type", "") or "").lower()
            if soort_type in ["boom", "tree"]:
                return "Boom"
            elif soort_type in ["struik", "heester", "shrub"]:
                # Kijk naar hoogte voor onderscheid heester/bodembedekker
                hoogte = str(row.get("hoogte", "") or "")
                try:
                    match = re.search(r'(\d+(?:[,\.]\d+)?)', hoogte.replace(',', '.'))
                    if match:
                        h = float(match.group(1))
                        if h < 0.5:
                            return "Bodembedekker"
                except:
                    pass
                return "Heester"
            elif soort_type in ["klimplant", "klimmer"]:
                return "Klimplant"
            
            # Fallback: kijk naar TreeEbb kolommen
            boom_src = str(row.get("beplantingstypes_boomtypen", "") or "").strip()
            overig_src = str(row.get("beplantingstypes_overige_beplanting", "") or "").strip()
            
            if boom_src and not overig_src:
                return "Boom"
            elif overig_src and not boom_src:
                overig_lower = overig_src.lower()
                if any(k in overig_lower for k in ["heester", "struik", "haag"]):
                    return "Heester"
                elif any(k in overig_lower for k in ["bodembedekker", "vaste plant", "kruid"]):
                    return "Bodembedekker"
                else:
                    return "Heester"
            elif boom_src and overig_src:
                return "Boom"
            
            # Laatste fallback: hoogte
            hoogte = str(row.get("hoogte", "") or row.get("eigenschappen_hoogte", "") or "")
            try:
                match = re.search(r'(\d+)', hoogte)
                if match:
                    h = int(match.group(1))
                    if h >= 8:
                        return "Boom"
                    elif h >= 2:
                        return "Heester"
                    else:
                        return "Bodembedekker"
            except:
                pass
            
            return "Boom"  # Default
        
        df["beplantingstype"] = df.apply(_derive_beplantingstype, axis=1)
    
    # ============================================================
    # FIX: Sorteer op relevantie (beste matches eerst)
    # ============================================================
    
    def _score_plant(row):
        """Geef score aan plant op basis van geschiktheid."""
        score = 0
        
        # Bonus voor exacte vocht match
        if filter_vocht and "vocht" in df.columns:
            plant_vocht = str(row.get("vocht", "")).lower()
            if filter_vocht.lower() in plant_vocht:
                score += 10
        
        # Bonus voor exacte bodem match
        if filter_bodem:
            plant_bodem = str(row.get("bodem", "") or "") + " " + str(row.get("grondsoorten", "") or "")
            if filter_bodem.lower() in plant_bodem.lower():
                score += 10
        
        # Bonus voor inheems (vs ingeburgerd)
        status = str(row.get("status_nl", "")).lower()
        if status == "inheems":
            score += 5
        
        # Bonus voor hoge ecologische waarde
        eco = str(row.get("ecowaarde", "") or row.get("biodiversiteit", "") or "")
        if eco:
            score += 3
        
        return score
    
    df["_score"] = df.apply(_score_plant, axis=1)
    df = df.sort_values(["_score", "naam"], ascending=[False, True])
    df = df.drop(columns=["_score"])
    
    # Debug info
    if os.getenv("PLANTWIJS_DEBUG", "").lower() == "true":
        print(f"[PDF] Finale selectie: {len(df)} planten (van {original_count} totaal)")
        if len(df) > 0:
            print(f"[PDF] Top 3: {list(df.head(3)['naam'])}")
    
    # ========================================================================
    # 4) GENEREER MODERNE PDF
    # ========================================================================
    
    pdf_bytes = generate_locatierapport_v2(
        lat=lat,
        lon=lon,
        context_data=context_data,
        plant_df=df.head(50) if len(df) > 0 else None
    )
    
    # ========================================================================
    # 5) RETURN ALS STREAMING RESPONSE
    # ========================================================================
    
    buf = BytesIO(pdf_bytes)
    headers = {"Content-Disposition": f'inline; filename="beplantingsadvies_{lat:.5f}_{lon:.5f}.pdf"'}
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
  <title>PlantWijs v3.10.0</title>
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