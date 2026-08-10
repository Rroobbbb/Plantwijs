"""PlantWijs — paden, environment en constanten.

Dit module doet bewust GEEN netwerk-calls en heeft geen zware imports:
importeren van het package mag nooit PDOK bevragen.
"""

from __future__ import annotations

import os
import tempfile
from typing import List

from pyproj import Transformer

# ───────────────────── versie / app
VERSION = "3.9.7"
# Titel van de OpenAPI-spec en van /docs (zie main.create_app()).
APP_TITLE = "PlantWijs API"

# ───────────────────── paden
# config.py staat in <project>/plantwijs/, dus twee niveaus omhoog is de projectmap.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "out")
STATIC_DIR = os.path.join(BASE_DIR, "static")
CONTENT_DIR = os.path.join(BASE_DIR, "content")

INDEX_HTML = os.path.join(STATIC_DIR, "index.html")   # nieuwe frontend (WP3)
LEGACY_HTML = os.path.join(STATIC_DIR, "legacy.html")  # oude embedded UI

# ───────────────────── HTTP
HEADERS = {"User-Agent": f"plantwijs/{VERSION}"}
FMT_JSON = "application/json;subtype=geojson"

# ───────────────────── NSN (Natuurlijk Systeem Nederland)
NSN_DATA_DIR = DATA_DIR
# Groot bestand: liever niet in Git als losse .geojson. Daarom ondersteunen we ook een ZIP in /data.
NSN_GEOJSON_PATH = os.path.join(NSN_DATA_DIR, "nsn_natuurlijk_systeem.geojson")
NSN_ZIP_PATH = os.path.join(NSN_DATA_DIR, "LBK_BKNSN_2023.zip")  # default; er mag ook een andere .zip in /data staan

NSN_GEOJSON_IS_RD: bool = True  # GeoJSON in RD New (EPSG:28992); op False zetten als je zelf naar WGS84 hebt geprojecteerd

NSN_INDEX_DIR = os.path.join(tempfile.gettempdir(), "plantwijs_nsn")
NSN_INDEX_DB = os.path.join(NSN_INDEX_DIR, "nsn_index.sqlite")

# ───────────────────── PDOK endpoints
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

# ───────────────────── Proj (lokaal, geen netwerk)
TX_WGS84_RD = Transformer.from_crs(4326, 28992, always_xy=True)
TX_WGS84_WEB = Transformer.from_crs(4326, 3857, always_xy=True)

# ───────────────────── Dataset (CSV) — één bron voor lokaal + Render
# Volgorde:
# 1) PLANTWIJS_CSV (optioneel) — absolute of relatieve padnaam
# 2) data/treeebb_planten_allfields.csv (in repo)
# 3) out/treeebb_planten_allfields.csv (optioneel)
# De oude plantwijs_full-exports (82 rijen, aug 2025) staan hier bewust niet
# meer tussen: zo'n bestand laadde anders geruisloos als de echte CSV ontbreekt.
DATA_PATHS: List[str] = [
    os.environ.get("PLANTWIJS_CSV", "").strip(),
    os.path.join(DATA_DIR, "treeebb_planten_allfields.csv"),
    os.path.join(OUT_DIR, "treeebb_planten_allfields.csv"),
]
DATA_PATHS = [p for p in DATA_PATHS if p]

# Ondergrens: bronnen met minder rijen worden overgeslagen (kapot of verouderd
# bestand), behalve als het pad expliciet via PLANTWIJS_CSV is opgegeven.
MIN_DATASET_ROWS = 500

# Online CSV fallback (GitHub raw) — alleen als er lokaal echt niets gevonden wordt
ONLINE_CSV_URLS: List[str] = [
    os.environ.get("PLANTWIJS_ONLINE_CSV_URL", "").strip(),
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/data/treeebb_planten_allfields.csv",
    "https://raw.githubusercontent.com/Rroobbbb/plantwijs/main/out/treeebb_planten_allfields.csv",
]
ONLINE_CSV_URLS = [u for u in ONLINE_CSV_URLS if u]

# ───────────────────── overig
ADMIN_KEY_ENV = "PLANTWIJS_ADMIN_KEY"

NO_STORE_HEADERS = {
    "Cache-Control": "no-store, max-age=0, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}
