"""PDF-locatierapport (reportlab / platypus).

Bouwt het rapport achter `GET /advies/pdf`. De opzet volgt de eerdere
implementatie van de eigenaar (`Backup/api 202512151837 pdf3.py`): platypus met
eigen stijlen, een kaartuitsnede uit OpenStreetMap-tiles en alleen
standaardfonts (Helvetica), zodat het op elke server werkt.

Inhoud (A4, staand, Nederlands):

1. kop met titel, datum en coördinaten;
2. kaartuitsnede met marker (© OpenStreetMap);
3. "Jouw plek" — het locatieprofiel met bronvermelding per regel;
4. "Jouw landschap" — de verhalen uit de kennislaag;
5. "Wortelruimte" — indicatieve wortelbare diepte;
6. "Wat kun jij doen" — passende beplantingsvormen;
7. "Passende soorten" — soortentabel (max 40 rijen);
8. disclaimer, bronnenlijst en paginanummering.

Robuustheid
-----------
Elke bronlookup (PDOK/BRO/AHN/NSN) en de kennislaag worden **afzonderlijk**
afgevangen: één kapotte of trage bron levert "niet gevonden" in het rapport op,
nooit een exception naar de router. Ook de kaartuitsnede is optioneel; is de
tile-server niet bereikbaar, dan komt er een tekstregel in plaats van de kaart.

Filterlogica
------------
De soortentabel gebruikt dezelfde filterfuncties als `/api/plants` en
`/advies/geo` (`services.dataset._filter_plants_df`). Vocht en bodem komen van
de kaart, tenzij de aanroeper die filters zelf meegeeft; die keuze wint dan.
Licht, beplantingstype, status en invasief werken precies als elders.
"""

from __future__ import annotations

import math
import os
import re
import threading
from datetime import datetime
from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape

import pandas as pd
import requests
import yaml
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (
    CondPageBreak,
    Image as RLImage,
    KeepTogether,
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..config import CONTENT_DIR, VERSION
from .advies import verrijk_advies
from .dataset import _filter_plants_df, ensure_beplantingstype, status_filter_labels
from .nsn import nsn_from_point
from .pdok import (
    ahn_from_wms,
    bodem_from_bodemkaart,
    fgr_from_point,
    gmm_from_wms,
    vocht_from_gwt,
)

# ───────────────────── constanten
BESTANDSNAAM = "beplantingswijzer_rapport.pdf"
TITEL = "Beplantingswijzer — Locatierapport"
MAX_SOORTEN = 40

# Huisstijl (zie static/css/app.css)
C_GROEN = colors.HexColor("#1d5c3f")   # koppen en accentlijnen
C_AMBER = colors.HexColor("#a8632a")   # spaarzaam accent
C_TEKST = colors.HexColor("#1f2937")
C_MUTED = colors.HexColor("#6b7280")
C_LIJN = colors.HexColor("#dcdcd3")
C_ZACHT = colors.HexColor("#f5f4ef")   # warme off-white voor tabelkoppen

MARGE = 18 * mm
PAGINA_BREEDTE = A4[0] - 2 * MARGE

NIET_GEVONDEN = "niet gevonden"

MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli",
           "augustus", "september", "oktober", "november", "december")

# Bron per regel in "Jouw plek" (zelfde namen als de *_bron-velden van /advies/geo)
BRON_LABELS: Dict[str, str] = {
    "fgr": "PDOK — Fysisch-geografische regio's (WFS)",
    "bodem": "BRO Bodemkaart WMS",
    "gwt": "BRO Gt/GLG WMS",
    "ahn": "PDOK AHN WMS (DTM 0,5 m)",
    "gmm": "BRO Geomorfologische kaart (GMM) WMS",
    "nsn": "BKNSN 2023 (Natuurlijk Systeem Nederland)",
}

BRONNENLIJST: Tuple[str, ...] = (
    "PDOK — Fysisch-geografische regio's (WFS), Ministerie van LNV.",
    "BRO Bodemkaart van Nederland 1:50.000 (WMS), via PDOK.",
    "BRO Grondwaterspiegeldiepte — grondwatertrap Gt/GHG/GLG (WMS), via PDOK.",
    "AHN — Actueel Hoogtebestand Nederland, DTM 0,5 m (WMS), via PDOK.",
    "BRO Geomorfologische kaart van Nederland (WMS), via PDOK.",
    "BKNSN 2023 — Basiskaart Natuurlijk Systeem Nederland (Wageningen Environmental Research).",
    "TreeEbb (Boomkwekerij Ebben) — standplaats- en groei-eigenschappen van de soorten.",
    "Standaardlijst van de Nederlandse Flora 2020 (SL2020) — Nederlandse namen en status.",
    "Kaartachtergrond: © OpenStreetMap-bijdragers (ODbL).",
)

STANDAARD_DISCLAIMER = (
    "Indicatief; gebaseerd op kaartinterpretatie op regioschaal. "
    "Lokale situatie kan afwijken."
)
DISCLAIMER_AANVULLING = (
    "De kaartlagen zijn gemaakt voor gebruik op regioschaal: op perceelniveau "
    "kunnen ophoging, vergraving, drainage of bebouwing de werkelijkheid flink "
    "laten afwijken. Gebruik dit rapport als vertrekpunt en controleer de "
    "belangrijkste aannames ter plekke, bijvoorbeeld met een spadesteek en een "
    "blik op wat er in de buurt al goed groeit."
)

# ───────────────────── kaart (OpenStreetMap-tiles)
TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
TILE_HEADERS = {"User-Agent": f"Beplantingswijzer/{VERSION} (locatierapport)"}
TILE_TIMEOUT = 8
KAART_ZOOM = 16
KAART_PX = 512          # uitsnede in pixels (uit een 3×3 mozaïek van 768 px)
KAART_MM = 92           # weergavebreedte in de PDF


def _webmercator_tile_xy(lat: float, lon: float, z: int) -> Tuple[float, float]:
    """Fractionele Web-Mercator-tilecoördinaten van een punt.

    De hele getallen zijn het tilenummer, de decimalen de positie binnen die
    tile. Daarmee kan de marker exact op het punt worden gezet in plaats van
    op het midden van de mozaïek.
    """
    lat_rad = math.radians(max(min(lat, 85.05112878), -85.05112878))
    n = 2 ** z
    x = (lon + 180.0) / 360.0 * n
    y = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return x, y


def _tile_png(z: int, x: int, y: int) -> Optional[bytes]:
    """Eén OSM-tile ophalen; None bij een niet-200 antwoord."""
    r = requests.get(TILE_URL.format(z=z, x=x, y=y),
                     timeout=TILE_TIMEOUT, headers=TILE_HEADERS)
    if r.status_code != 200:
        return None
    return r.content


def _static_map_image(lat: float, lon: float, z: int = KAART_ZOOM,
                      px: int = KAART_PX) -> Optional[BytesIO]:
    """Kaartuitsnede met marker als PNG in een BytesIO, of None bij een fout.

    Er wordt een 3×3-mozaïek van tiles opgebouwd en daaruit een venster van
    `px` bij `px` geknipt dat exact op het punt is gecentreerd. Elke fout
    (netwerk, statuscode, kapotte afbeelding) levert None op; het rapport wordt
    dan zonder kaart gebouwd.
    """
    try:
        fx, fy = _webmercator_tile_xy(lat, lon, z)
        cx, cy = int(math.floor(fx)), int(math.floor(fy))

        mozaiek = Image.new("RGB", (768, 768), (238, 238, 232))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                ruw = _tile_png(z, cx + dx, cy + dy)
                if not ruw:
                    return None
                tile = Image.open(BytesIO(ruw)).convert("RGB")
                if tile.size != (256, 256):
                    tile = tile.resize((256, 256))
                mozaiek.paste(tile, ((dx + 1) * 256, (dy + 1) * 256))

        # positie van het punt binnen het mozaïek
        punt_x = (fx - (cx - 1)) * 256.0
        punt_y = (fy - (cy - 1)) * 256.0
        links = int(round(punt_x - px / 2))
        boven = int(round(punt_y - px / 2))
        links = max(0, min(768 - px, links))
        boven = max(0, min(768 - px, boven))
        img = mozaiek.crop((links, boven, links + px, boven + px))

        mx, my = punt_x - links, punt_y - boven
        try:
            teken = ImageDraw.Draw(img, "RGBA")
            teken.ellipse((mx - 11, my - 9, mx + 11, my + 13), fill=(0, 0, 0, 55))
            teken.ellipse((mx - 10, my - 10, mx + 10, my + 10), fill=(255, 255, 255, 235))
            teken.ellipse((mx - 6, my - 6, mx + 6, my + 6), fill=(29, 92, 63, 255))
            teken.rectangle((0, 0, px - 1, px - 1), outline=(190, 190, 180, 255), width=1)
        except Exception:
            pass  # marker is bijzaak; liever een kaart zonder marker dan geen kaart

        uit = BytesIO()
        img.save(uit, format="PNG", optimize=True)
        uit.seek(0)
        return uit
    except Exception as e:
        print("[REPORT] kaartuitsnede niet beschikbaar:", e)
        return None


# ───────────────────── disclaimer uit de kennislaag
_META_CACHE: Dict[str, Any] = {"meta": None, "mtime": None}
_META_LOCK = threading.Lock()
_CONTEXT_YAML = os.path.join(CONTENT_DIR, "context_descriptions.yaml")


def _context_meta() -> Dict[str, Any]:
    """`meta` uit content/context_descriptions.yaml (gecachet op mtime)."""
    try:
        mtime = os.path.getmtime(_CONTEXT_YAML)
    except OSError:
        mtime = None
    if _META_CACHE["meta"] is not None and _META_CACHE["mtime"] == mtime:
        return _META_CACHE["meta"]

    with _META_LOCK:
        meta: Dict[str, Any] = {}
        if mtime is not None:
            try:
                with open(_CONTEXT_YAML, "r", encoding="utf-8") as f:
                    meta = (yaml.safe_load(f) or {}).get("meta") or {}
            except Exception as e:
                print("[REPORT] meta uit context_descriptions.yaml niet leesbaar:", e)
                meta = {}
        _META_CACHE.update({"meta": meta, "mtime": mtime})
    return _META_CACHE["meta"]


def _disclaimer() -> str:
    tekst = " ".join(str(_context_meta().get("disclaimer") or "").split())
    return tekst or STANDAARD_DISCLAIMER


# ───────────────────── tekst-helpers
def _tekst(waarde: Any) -> str:
    """Ruwe waarde naar één nette regel tekst (leeg blijft leeg)."""
    if waarde is None:
        return ""
    s = " ".join(str(waarde).split())
    return "" if s.lower() in ("", "nan", "none", "—") else s


def _esc(waarde: Any) -> str:
    """Escape voor de mini-HTML van Paragraph."""
    return escape(_tekst(waarde))


def _hoofdletter(waarde: Any) -> str:
    s = _tekst(waarde)
    return s[0].upper() + s[1:] if s else s


def _zinnen(tekst: Any, aantal: int = 2) -> str:
    """De eerste `aantal` zinnen van een tekst (voor compacte blokken)."""
    t = _tekst(tekst)
    if not t:
        return ""
    delen = re.findall(r"[^.!?]+[.!?]?", t)
    kort = "".join(delen[:aantal]).strip()
    return kort or t


def _datum_nl(nu: Optional[datetime] = None) -> str:
    d = nu or datetime.now()
    return f"{d.day} {MAANDEN[d.month - 1]} {d.year}"


# ───────────────────── stijlen
def _stijlen() -> Dict[str, ParagraphStyle]:
    basis = getSampleStyleSheet()
    s: Dict[str, ParagraphStyle] = {}
    s["titel"] = ParagraphStyle(
        "PW_Titel", parent=basis["Title"], fontName="Helvetica-Bold",
        fontSize=21, leading=25, alignment=0, textColor=C_GROEN, spaceAfter=2)
    s["subtitel"] = ParagraphStyle(
        "PW_Subtitel", parent=basis["Normal"], fontName="Helvetica",
        fontSize=10, leading=14, textColor=C_MUTED, spaceAfter=0)
    s["kop"] = ParagraphStyle(
        "PW_Kop", parent=basis["Heading2"], fontName="Helvetica-Bold",
        fontSize=13.5, leading=17, textColor=C_GROEN,
        spaceBefore=13, spaceAfter=5)
    s["subkop"] = ParagraphStyle(
        "PW_Subkop", parent=basis["Heading3"], fontName="Helvetica-Bold",
        fontSize=10.5, leading=14, textColor=C_TEKST,
        spaceBefore=7, spaceAfter=2)
    s["tekst"] = ParagraphStyle(
        "PW_Tekst", parent=basis["Normal"], fontName="Helvetica",
        fontSize=9.5, leading=13.6, textColor=C_TEKST, spaceAfter=4)
    # De bullet komt uit ZapfDingbats: reportlab kent U+2022 niet in de
    # standaard Helvetica-encoding en zou er een leeg vakje van maken.
    s["bullet"] = ParagraphStyle(
        "PW_Bullet", parent=s["tekst"], leftIndent=11, bulletIndent=1,
        bulletFontName="ZapfDingbats", bulletFontSize=4.5,
        bulletColor=C_AMBER, spaceAfter=2.5)
    s["klein"] = ParagraphStyle(
        "PW_Klein", parent=basis["Normal"], fontName="Helvetica",
        fontSize=8.5, leading=11.5, textColor=C_TEKST)
    s["klein_muted"] = ParagraphStyle(
        "PW_KleinMuted", parent=s["klein"], textColor=C_MUTED)
    s["cel"] = ParagraphStyle(
        "PW_Cel", parent=basis["Normal"], fontName="Helvetica",
        fontSize=7.6, leading=9.6, textColor=C_TEKST)
    s["cel_kop"] = ParagraphStyle(
        "PW_CelKop", parent=s["cel"], fontName="Helvetica-Bold", textColor=colors.white)
    s["cel_muted"] = ParagraphStyle(
        "PW_CelMuted", parent=s["cel"], textColor=C_MUTED)
    return s


# ───────────────────── locatieprofiel ophalen
def _veilig(naam: str, fn: Callable[[], Any], leeg: Any) -> Any:
    """Bronlookup uitvoeren; een exception levert de lege waarde op.

    Zelfde afspraak als `/advies/geo`: één kapotte bron mag het rapport
    nooit slopen (docs/API.md).
    """
    try:
        return fn()
    except Exception as e:
        print(f"[REPORT] bron '{naam}' faalde:", e)
        return leeg


def _locatieprofiel(lat: float, lon: float) -> Dict[str, Optional[str]]:
    """FGR, NSN, bodem, Gt/vocht, AHN en GMM voor een punt (elk apart afgevangen)."""
    fgr = _veilig("fgr", lambda: fgr_from_point(lat, lon), None)
    nsn = _veilig("nsn", lambda: nsn_from_point(lat, lon), None)
    bodem, _ = _veilig("bodem", lambda: bodem_from_bodemkaart(lat, lon), (None, {}))
    vocht, _, gt_code = _veilig("gwt", lambda: vocht_from_gwt(lat, lon), (None, {}, None))
    ahn, _ = _veilig("ahn", lambda: ahn_from_wms(lat, lon), (None, {}))
    gmm, _ = _veilig("gmm", lambda: gmm_from_wms(lat, lon), (None, {}))
    return {
        "fgr": _tekst(fgr) or None,
        "nsn": _tekst(nsn) or None,
        "bodem": _tekst(bodem) or None,
        "vocht": _tekst(vocht) or None,
        "gt_code": _tekst(gt_code) or None,
        "ahn": _tekst(ahn) or None,
        "gmm": _tekst(gmm) or None,
    }


def _kennislaag(profiel: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """De kennislaag-velden; faalt die, dan blijft het rapport gewoon staan."""
    try:
        return verrijk_advies(
            fgr=profiel.get("fgr"),
            nsn=profiel.get("nsn"),
            gmm=profiel.get("gmm"),
            bodem=profiel.get("bodem"),
            vocht=profiel.get("vocht"),
            gt_code=profiel.get("gt_code"),
        )
    except Exception as e:
        print("[REPORT] kennislaag faalde:", e)
        return {"landschap": {}, "wortelbare_diepte": None, "aanbevolen_beplanting": []}


# ───────────────────── soortenselectie
# Volgorde in de tabel: inheems eerst, dan ingeburgerd, dan de soorten zonder
# status (het grootste deel van de TreeEbb-set) en pas daarna de exoten. Bij een
# rapport over het eigen landschap zijn dat immers de eerste veertig die tellen.
_STATUS_ORDE = {"inheems": 0, "ingeburgerd": 1, "exoot": 3}


def _soorten(
    profiel: Dict[str, Optional[str]],
    *,
    inheems_only: bool,
    toon_inheems: Optional[bool],
    toon_ingeburgerd: Optional[bool],
    toon_exoot: Optional[bool],
    exclude_invasief: bool,
    licht: List[str],
    vocht: List[str],
    bodem: List[str],
    beplantingstype: List[str],
) -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """Passende soorten, gesorteerd op status (inheems eerst) en naam.

    Vocht en bodem komen van de kaart tenzij ze zijn meegegeven; die keuze
    wint dan. Zonder extra filters is het resultaat dezelfde selectie als
    `/advies/geo`.

    Returns:
        `(dataframe, gebruikte_filters)`.
    """
    vocht_keuze = list(vocht) if vocht else ([profiel["vocht"]] if profiel.get("vocht") else [])
    bodem_keuze = list(bodem) if bodem else ([profiel["bodem"]] if profiel.get("bodem") else [])
    gebruikt = {
        "status": status_filter_labels(
            inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot),
        "licht": list(licht),
        "vocht": vocht_keuze,
        "bodem": bodem_keuze,
        "beplantingstype": list(beplantingstype),
    }

    df = _filter_plants_df(
        "", inheems_only, toon_inheems, toon_ingeburgerd, toon_exoot,
        exclude_invasief, list(licht), vocht_keuze, bodem_keuze,
        list(beplantingstype), "naam", False,
    )
    df = ensure_beplantingstype(df)

    if "status_nl" in df.columns and not df.empty:
        orde = df["status_nl"].astype(str).str.strip().str.lower().map(
            lambda v: _STATUS_ORDE.get(v, 2))
        df = df.assign(_orde=orde).sort_values(
            by=["_orde", "naam"], kind="stable").drop(columns=["_orde"])
    return df, gebruikt


# ───────────────────── bouwstenen voor de story
# Minimale ruimte die onder aan een pagina over moet zijn om een sectie nog te
# beginnen; is er minder, dan start de sectie op de volgende pagina. Genoeg voor
# de kop, de introzin en het begin van de eerste alinea.
SECTIE_RUIMTE = 40 * mm


def _sectie(kop: str, intro: str, s: Dict[str, ParagraphStyle]) -> List[Any]:
    """Sectiekop met introzin, die nooit alleen onder aan een pagina belandt."""
    return [
        CondPageBreak(SECTIE_RUIMTE),
        KeepTogether([Paragraph(_esc(kop), s["kop"]), Paragraph(_esc(intro), s["tekst"])]),
    ]


BULLET = "●"  # ZapfDingbats a71 — een gevulde ronde bullet


def _bullets(regels: List[str], s: Dict[str, ParagraphStyle]) -> List[Paragraph]:
    return [Paragraph(_esc(r), s["bullet"], bulletText=BULLET)
            for r in regels if _tekst(r)]


def _profieltabel(profiel: Dict[str, Optional[str]], s: Dict[str, ParagraphStyle]) -> Table:
    vocht = _tekst(profiel.get("vocht"))
    gt = _tekst(profiel.get("gt_code"))
    if vocht and gt:
        vocht_weergave = f"{_hoofdletter(vocht)} (grondwatertrap {gt})"
    elif vocht:
        vocht_weergave = _hoofdletter(vocht)
    elif gt:
        vocht_weergave = f"grondwatertrap {gt}"
    else:
        vocht_weergave = ""

    ahn = _tekst(profiel.get("ahn"))
    regels = [
        ("Landschapsregio (FGR)", _hoofdletter(profiel.get("fgr")), "fgr"),
        ("Bodem", _hoofdletter(profiel.get("bodem")), "bodem"),
        ("Vochtklasse (Gt)", vocht_weergave, "gwt"),
        ("Hoogte (AHN)", f"{ahn} m t.o.v. NAP" if ahn else "", "ahn"),
        ("Geomorfologie (GMM)", _hoofdletter(profiel.get("gmm")), "gmm"),
        ("Natuurlijk systeem (NSN)", _hoofdletter(profiel.get("nsn")), "nsn"),
    ]

    rijen = [[Paragraph("<b>Kenmerk</b>", s["cel_kop"]),
              Paragraph("<b>Waarde</b>", s["cel_kop"]),
              Paragraph("<b>Bron</b>", s["cel_kop"])]]
    for label, waarde, bron in regels:
        stijl = s["klein"] if waarde else s["klein_muted"]
        rijen.append([
            Paragraph(f"<b>{_esc(label)}</b>", s["klein"]),
            Paragraph(_esc(waarde) or NIET_GEVONDEN, stijl),
            Paragraph(_esc(BRON_LABELS[bron]), s["klein_muted"]),
        ])

    tabel = Table(rijen, colWidths=[42 * mm, 66 * mm, PAGINA_BREEDTE - 108 * mm],
                  repeatRows=1, hAlign="LEFT")
    tabel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), C_GROEN),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, C_LIJN),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tabel


def _landschapsblok(landschap: Dict[str, Any], s: Dict[str, ParagraphStyle]) -> List[Any]:
    """Sectie "Jouw landschap": nsn eerst, dan fgr; gmm/bodem/vocht compact."""
    uit: List[Any] = []
    if not landschap:
        uit.append(Paragraph(
            "Het landschapsverhaal kon niet worden geladen.", s["klein_muted"]))
        return uit

    versterken: List[str] = []
    gezien: set[str] = set()

    for cat in ("nsn", "fgr"):
        blok = landschap.get(cat) or {}
        ontstaan = _tekst(blok.get("ontstaan"))
        titel = _tekst(blok.get("titel"))
        if not (titel or ontstaan):
            continue
        kop = Paragraph(_esc(titel), s["subkop"])
        alinea = Paragraph(_esc(ontstaan), s["tekst"])
        uit.append(KeepTogether([kop, alinea]))
        for v in blok.get("versterken") or []:
            sleutel = _tekst(v).lower()
            if sleutel and sleutel not in gezien:
                gezien.add(sleutel)
                versterken.append(_tekst(v))

    compact: List[Tuple[str, str]] = []
    for cat in ("gmm", "bodem", "vocht"):
        blok = landschap.get(cat) or {}
        titel = _tekst(blok.get("titel"))
        kort = _zinnen(blok.get("ontstaan"), 2)
        if titel and kort:
            compact.append((titel, kort))
    if compact:
        uit.append(Paragraph("Landvorm, bodem en water", s["subkop"]))
        for titel, kort in compact:
            uit.append(Paragraph(f"<b>{_esc(titel)}.</b> {_esc(kort)}", s["tekst"]))

    if versterken:
        uit.append(Paragraph("Zo versterk je dit landschap", s["subkop"]))
        uit.extend(_bullets(versterken[:8], s))
    return uit


def _wortelblok(wortel: Optional[Dict[str, Any]], s: Dict[str, ParagraphStyle]) -> List[Any]:
    if not wortel:
        return [Paragraph(
            "Voor deze plek is te weinig bodem- en grondwaterinformatie beschikbaar om de "
            "wortelbare diepte in te schatten. Graaf een proefgat van ongeveer een meter "
            "diep om te zien hoe diep de wortels hier kunnen komen.", s["tekst"])]

    band = _tekst(wortel.get("band_cm"))
    klasse = _tekst(wortel.get("klasse")).replace("_", " ")
    uit: List[Any] = []
    kop_regels = [
        Paragraph(f'<font size="17" color="#1d5c3f"><b>{_esc(band)} cm</b></font>', s["tekst"]),
        Paragraph(f"indicatieve wortelbare diepte — klasse: {_esc(klasse)}", s["klein_muted"]),
    ]
    kader = Table([[kop_regels]], colWidths=[PAGINA_BREEDTE], hAlign="LEFT")
    kader.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_ZACHT),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, C_AMBER),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    uit.append(kader)
    uit.append(Spacer(1, 4))
    for veld in ("indicatie", "toelichting"):
        tekst = _tekst(wortel.get(veld))
        if tekst:
            uit.append(Paragraph(_esc(tekst), s["tekst"]))
    return uit


def _vormenblok(vormen: List[Dict[str, Any]], s: Dict[str, ParagraphStyle]) -> List[Any]:
    if not vormen:
        return [Paragraph(
            "Er konden voor deze plek geen beplantingsvormen worden bepaald.",
            s["klein_muted"])]
    uit: List[Any] = []
    for vorm in vormen:
        # Alleen de naam en de eerste alinea worden bij elkaar gehouden; de rest
        # mag doorlopen, anders schuift een heel blok naar de volgende pagina.
        alineas = [Paragraph(_esc(_tekst(vorm.get(veld))), s["tekst"])
                   for veld in ("omschrijving", "waarom_hier") if _tekst(vorm.get(veld))]
        kop = Paragraph(_esc(vorm.get("vorm")), s["subkop"])
        uit.append(KeepTogether([kop, alineas[0]] if alineas else [kop]))
        uit.extend(alineas[1:])
        soorten = [_tekst(x) for x in (vorm.get("voorbeeldsoorten") or []) if _tekst(x)]
        if soorten:
            uit.append(Paragraph(
                f'<font color="#6b7280"><b>Voorbeeldsoorten:</b></font> '
                f'{_esc(", ".join(soorten))}', s["klein"]))
        uit.append(Spacer(1, 3))
    return uit


def _soortentabel(df: pd.DataFrame, s: Dict[str, ParagraphStyle]) -> List[Any]:
    if df.empty:
        return [Paragraph(
            "Met deze combinatie van filters bleven er geen soorten over. Zet een filter "
            "ruimer op de website om meer soorten te zien.", s["tekst"])]

    kolommen = [
        ("Naam", "naam", 33),
        ("Wetenschappelijke naam", "wetenschappelijke_naam", 36),
        ("Type", "beplantingstype", 15),
        ("Licht", "standplaats_licht", 25),
        ("Vocht", "vocht", 27),
        ("Hoogte", "hoogte", 18),
        ("Status", "status_nl", 20),
    ]
    breedtes = [b * mm for _, _, b in kolommen]
    breedtes[-1] = PAGINA_BREEDTE - sum(breedtes[:-1])

    rijen: List[List[Any]] = [[Paragraph(f"<b>{_esc(k)}</b>", s["cel_kop"])
                               for k, _, _ in kolommen]]
    for _, r in df.head(MAX_SOORTEN).iterrows():
        cellen = []
        for _, kolom, _b in kolommen:
            waarde = _tekst(r.get(kolom, ""))
            if kolom == "status_nl" and not waarde:
                waarde = "onbekend"
            stijl = s["cel_muted"] if kolom == "wetenschappelijke_naam" else s["cel"]
            cellen.append(Paragraph(_esc(waarde) or "—", stijl))
        rijen.append(cellen)

    tabel = LongTable(rijen, colWidths=breedtes, repeatRows=1, hAlign="LEFT")
    stijl = [
        ("BACKGROUND", (0, 0), (-1, 0), C_GROEN),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, C_LIJN),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    for i in range(2, len(rijen), 2):
        stijl.append(("BACKGROUND", (0, i), (-1, i), C_ZACHT))
    tabel.setStyle(TableStyle(stijl))
    return [tabel]


def _filterzin(gebruikt: Dict[str, List[str]]) -> str:
    labels = {"status": "status", "licht": "licht", "vocht": "vocht",
              "bodem": "bodem", "beplantingstype": "type"}
    delen = [f"{labels[k]}: {', '.join(v)}"
             for k, v in gebruikt.items() if v and k in labels]
    return "; ".join(delen) if delen else "geen"


# ───────────────────── paginanummering
class _GenummerdCanvas(rl_canvas.Canvas):
    """Canvas die "pagina X van Y" kan zetten (tweede pass bij het opslaan)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas: List[dict] = []

    def showPage(self):  # noqa: N802 (reportlab-API)
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        totaal = len(self._paginas)
        for status in self._paginas:
            self.__dict__.update(status)
            self._voettekst(totaal)
            super().showPage()
        super().save()

    def _voettekst(self, totaal: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(C_MUTED)
        self.drawRightString(A4[0] - MARGE, MARGE - 7 * mm,
                             f"pagina {self._pageNumber} van {totaal}")
        self.restoreState()


def _paginadecoratie(canv: rl_canvas.Canvas, doc, subtitel: str) -> None:
    """Kop- en voetregel op elke pagina (het paginanummer komt uit de canvas)."""
    canv.saveState()
    canv.setStrokeColor(C_GROEN)
    canv.setLineWidth(1.6)
    canv.line(MARGE, A4[1] - MARGE + 6 * mm, A4[0] - MARGE, A4[1] - MARGE + 6 * mm)
    canv.setFont("Helvetica-Bold", 7.5)
    canv.setFillColor(C_GROEN)
    canv.drawString(MARGE, A4[1] - MARGE + 8 * mm, "Beplantingswijzer")
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(C_MUTED)
    canv.drawRightString(A4[0] - MARGE, A4[1] - MARGE + 8 * mm, "Locatierapport")

    canv.setStrokeColor(C_LIJN)
    canv.setLineWidth(0.5)
    canv.line(MARGE, MARGE - 4.5 * mm, A4[0] - MARGE, MARGE - 4.5 * mm)
    canv.setFont("Helvetica", 7.5)
    canv.setFillColor(C_MUTED)
    canv.drawString(MARGE, MARGE - 7 * mm, subtitel)
    canv.restoreState()


# ───────────────────── publieke API
def maak_rapport(
    lat: float,
    lon: float,
    *,
    inheems_only: bool = False,
    toon_inheems: Optional[bool] = None,
    toon_ingeburgerd: Optional[bool] = None,
    toon_exoot: Optional[bool] = None,
    exclude_invasief: bool = True,
    licht: Optional[List[str]] = None,
    vocht: Optional[List[str]] = None,
    bodem: Optional[List[str]] = None,
    beplantingstype: Optional[List[str]] = None,
) -> bytes:
    """Bouw het PDF-locatierapport en geef de bytes terug.

    Args:
        lat, lon: WGS84-coördinaten van de plek.
        inheems_only, toon_*, exclude_invasief: statusfilters, zoals /api/plants.
        licht, vocht, bodem, beplantingstype: extra filters op de soortentabel.
            Vocht en bodem overschrijven de kaartwaarde van deze locatie.

    Returns:
        De PDF als bytes. Faalt een bron, dan staat er "niet gevonden" in het
        rapport; er wordt nooit een exception doorgegeven vanwege een bron.
    """
    licht = list(licht or [])
    vocht = list(vocht or [])
    bodem = list(bodem or [])
    beplantingstype = list(beplantingstype or [])

    s = _stijlen()
    profiel = _locatieprofiel(lat, lon)
    kennis = _kennislaag(profiel)
    df, gebruikt = _soorten(
        profiel,
        inheems_only=inheems_only, toon_inheems=toon_inheems,
        toon_ingeburgerd=toon_ingeburgerd, toon_exoot=toon_exoot,
        exclude_invasief=exclude_invasief, licht=licht, vocht=vocht,
        bodem=bodem, beplantingstype=beplantingstype,
    )
    coordinaten = f"{lat:.5f}, {lon:.5f}"

    story: List[Any] = []

    # 1 ── kop
    story.append(Paragraph(_esc(TITEL), s["titel"]))
    story.append(Paragraph(
        f"Opgesteld op {_esc(_datum_nl())} &nbsp;·&nbsp; "
        f"Coördinaten (WGS84): <b>{_esc(coordinaten)}</b>", s["subtitel"]))
    story.append(Spacer(1, 7))

    # 2 ── kaartuitsnede
    kaart = _static_map_image(lat, lon)
    if kaart is not None:
        try:
            story.append(RLImage(kaart, width=KAART_MM * mm, height=KAART_MM * mm,
                                 hAlign="LEFT"))
            story.append(Spacer(1, 2))
            story.append(Paragraph(
                "Kaartuitsnede rond de gekozen plek (zoomniveau 16). "
                "Kaartgegevens © OpenStreetMap-bijdragers.", s["klein_muted"]))
        except Exception as e:
            print("[REPORT] kaart kon niet in de PDF worden geplaatst:", e)
            kaart = None
    if kaart is None:
        story.append(Paragraph(
            "Kaartuitsnede niet beschikbaar: de kaartdienst (OpenStreetMap) was op dit "
            "moment niet bereikbaar. De rest van het rapport is hierdoor niet beïnvloed.",
            s["klein_muted"]))
    story.append(Spacer(1, 4))

    # 3 ── jouw plek
    story.extend(_sectie(
        "Jouw plek",
        "Wat de landelijke kaarten over deze plek zeggen. De waarden zijn afgelezen op "
        "het punt hierboven; per regel staat de bron erbij.", s))
    story.append(_profieltabel(profiel, s))

    # 4 ── jouw landschap
    story.extend(_sectie(
        "Jouw landschap",
        "Hoe dit landschap is ontstaan, en wat je met beplanting kunt doen om het "
        "karakter ervan te versterken.", s))
    story.extend(_landschapsblok(kennis.get("landschap") or {}, s))

    # 5 ── wortelruimte
    story.extend(_sectie(
        "Wortelruimte",
        "Hoe diep wortels hier naar verwachting kunnen komen. Dat bepaalt welke bomen "
        "en struiken op lange termijn goed gedijen.", s))
    story.extend(_wortelblok(kennis.get("wortelbare_diepte"), s))

    # 6 ── wat kun jij doen
    story.extend(_sectie(
        "Wat kun jij doen",
        "Beplantingsvormen die bij dit landschap horen. Kies er één of twee die passen "
        "bij de ruimte die je hebt.", s))
    story.extend(_vormenblok(kennis.get("aanbevolen_beplanting") or [], s))

    # 7 ── passende soorten
    totaal = int(len(df))
    getoond = min(totaal, MAX_SOORTEN)
    story.extend(_sectie(
        "Passende soorten",
        f"{getoond} van de {totaal} soorten die bij deze standplaats passen, inheemse "
        f"soorten eerst. Toegepaste filters — {_filterzin(gebruikt)}.", s))
    story.extend(_soortentabel(df, s))
    story.append(Spacer(1, 3))
    story.append(Paragraph(
        f"Deze tabel toont maximaal {MAX_SOORTEN} soorten. De volledige lijst staat op de "
        "website van Beplantingswijzer en is daar te downloaden via de CSV-export.",
        s["klein_muted"]))

    # 8 ── voetwerk
    story.append(CondPageBreak(SECTIE_RUIMTE))
    story.append(KeepTogether([
        Paragraph(_esc("Over dit rapport"), s["kop"]),
        Paragraph(f"<b>Let op.</b> {_esc(_disclaimer())} {_esc(DISCLAIMER_AANVULLING)}",
                  s["tekst"]),
    ]))
    story.append(Paragraph("Gebruikte bronnen", s["subkop"]))
    story.extend(_bullets(list(BRONNENLIJST), s))

    # ── bouwen
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGE, rightMargin=MARGE,
        topMargin=MARGE, bottomMargin=MARGE,
        title=TITEL, author="Beplantingswijzer",
        subject=f"Locatierapport voor {coordinaten}",
    )
    voettekst = f"Beplantingswijzer — locatierapport {coordinaten} — {_datum_nl()}"

    def _op_pagina(canv, doc_):
        _paginadecoratie(canv, doc_, voettekst)

    doc.build(story, onFirstPage=_op_pagina, onLaterPages=_op_pagina,
              canvasmaker=_GenummerdCanvas)
    return buf.getvalue()
