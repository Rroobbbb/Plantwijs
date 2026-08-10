"""Dataset-service: CSV laden, normaliseren, cachen en filteren."""

from __future__ import annotations

import io
import math
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests

from ..config import DATA_DIR, DATA_PATHS, HEADERS, MIN_DATASET_ROWS, ONLINE_CSV_URLS

# ───────────────────── cache
_CACHE: Dict[str, Any] = {"df": None, "mtime": None, "path": None, "source": None}

# ───────────────────── Nederlandse namen (SL2020)
# Standaardlijst van de Nederlandse Flora 2020: wetenschappelijke naam →
# Nederlandse naam. Bevat alleen de wilde/ingeburgerde Nederlandse flora, dus
# lang niet elke sierboom uit de TreeEbb-set krijgt een Nederlandse naam.
SL2020_XLSX = os.path.join(DATA_DIR, "SL2020 Checklist Flora NL.xlsx")
SL2020_SHEET = "SL2020"
_SL2020_WET_COL = "wetenschappelijke naam"
_SL2020_NL_COL = "nederlandse naam"

_SL_CACHE: Dict[str, Any] = {"map": None, "mtime": None, "path": None}


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

    # Nederlandse namen uit SL2020 (WP2b)
    df = _verrijk_namen(df)

    return df


# ───────────────────── Nederlandse namen koppelen (SL2020)
def _norm_naam(s: Any) -> str:
    """Normaliseer een plantennaam voor vergelijking."""
    t = str(s or "")
    t = t.replace("×", "x").replace("’", "'").replace("‘", "'")
    return " ".join(t.strip().lower().split())


def _sl2020_lookup() -> Dict[str, str]:
    """Wetenschappelijke naam (genormaliseerd) → Nederlandse naam.

    Gecachet met mtime-controle; ontbreekt het bestand, dan is de map leeg en
    blijft de dataset gewoon werken (alleen zonder Nederlandse namen).
    """
    path = SL2020_XLSX
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None

    if _SL_CACHE["map"] is not None and _SL_CACHE["mtime"] == mtime and _SL_CACHE["path"] == path:
        return _SL_CACHE["map"]

    lookup: Dict[str, str] = {}
    if mtime is not None:
        try:
            xl = pd.ExcelFile(path)
            sheets = ([SL2020_SHEET] if SL2020_SHEET in xl.sheet_names else []) + \
                     [s for s in xl.sheet_names if s != SL2020_SHEET]
            for sheet in sheets:
                sl = xl.parse(sheet, dtype=str)
                kol = {str(c).strip().lower(): c for c in sl.columns}
                wet_c, nl_c = kol.get(_SL2020_WET_COL), kol.get(_SL2020_NL_COL)
                if not wet_c or not nl_c:
                    continue
                for wet, nl in zip(sl[wet_c], sl[nl_c]):
                    key = _norm_naam(wet)
                    val = str(nl or "").strip()
                    if key and val and val.lower() != "nan" and key not in lookup:
                        lookup[key] = val
                break
            print(f"[NAMEN] SL2020 geladen: {len(lookup)} wetenschappelijke namen")
        except Exception as e:
            print("[NAMEN] SL2020 kon niet worden gelezen:", e)
            lookup = {}
    else:
        print(f"[NAMEN] SL2020 ontbreekt: {path}")

    _SL_CACHE.update({"map": lookup, "mtime": mtime, "path": path})
    return lookup


def _nl_naam_voor(latin: str, lookup: Dict[str, str]) -> tuple[str, str]:
    """Zoek de Nederlandse naam bij een wetenschappelijke naam.

    Twee strategieën, in deze volgorde:
      a) exacte match op de genormaliseerde volledige naam;
      b) match op de basis (geslacht + soort), waarbij de cultivar wegvalt en
         de hybride-notatie in beide vormen wordt geprobeerd
         ("Populus x canescens" → "populus x canescens" én "populus canescens").

    Returns:
        (nederlandse_naam, rest) — `rest` is het deel van de wetenschappelijke
        naam ná de basis (cultivar, subsp., var.), zodat de weergavenaam
        "Zomereik 'Fastigiata'" kan worden samengesteld. Leeg als er geen
        Nederlandse naam is.
    """
    if not lookup:
        return "", ""
    n = _norm_naam(latin)
    if not n:
        return "", ""
    if n in lookup:
        return lookup[n], ""

    origineel = str(latin).split()
    tokens = n.split()
    # alles vanaf de cultivar tussen enkele aanhalingstekens telt niet mee
    kern = tokens
    for i, t in enumerate(tokens):
        if t.startswith("'"):
            kern = tokens[:i]
            break

    if len(kern) >= 3 and kern[1] == "x":
        basis_lengte = 3
        kandidaten = [f"{kern[0]} x {kern[2]}", f"{kern[0]} {kern[2]}"]
    elif len(kern) >= 2:
        basis_lengte = 2
        kandidaten = [f"{kern[0]} {kern[1]}", f"{kern[0]} x {kern[1]}"]
    else:
        return "", ""

    for kandidaat in kandidaten:
        if kandidaat in lookup:
            rest = " ".join(origineel[basis_lengte:]).strip()
            return lookup[kandidaat], rest
    return "", ""


def _verrijk_namen(df: pd.DataFrame) -> pd.DataFrame:
    """Koppel Nederlandse namen uit SL2020 aan de dataset.

    - `wetenschappelijke_naam`: de Latijnse naam inclusief cultivar (de ruwe
      waarde uit de kolom `naam` van de TreeEbb-CSV).
    - `nederlandse_naam`: de SL2020-naam, of leeg.
    - `naam`: de Nederlandse naam (met cultivar, bijv. "Zomereik 'Fastigiata'")
      als die gevonden is, anders de Latijnse naam.

    Doet niets als de dataset al een kolom `nederlandse_naam` heeft; dan bevat
    `naam` immers al Nederlandse namen.
    """
    if "naam" not in df.columns or "nederlandse_naam" in df.columns:
        return df

    latijn = df["naam"].fillna("").astype(str)
    df = df.copy()
    df["wetenschappelijke_naam"] = latijn

    lookup = _sl2020_lookup()
    nederlands: List[str] = []
    weergave: List[str] = []
    for l in latijn:
        nl, rest = _nl_naam_voor(l, lookup)
        nederlands.append(nl)
        weergave.append(f"{nl} {rest}".strip() if nl else l)
    df["nederlandse_naam"] = nederlands
    df["naam"] = weergave

    gevonden = sum(1 for n in nederlands if n)
    print(f"[NAMEN] Nederlandse naam gekoppeld voor {gevonden}/{len(df)} rijen")
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
        return _verrijk_namen(df)
    except Exception as e:
        print("[ONLINE CSV] fout bij", url, "→", e)
        return None


def get_df() -> pd.DataFrame:
    env_path = os.environ.get("PLANTWIJS_CSV", "").strip()

    # 1) Probeer lokaal (development)
    for path in DATA_PATHS:
        if not os.path.exists(path):
            continue
        m = os.path.getmtime(path)
        if _CACHE["df"] is not None and _CACHE["mtime"] == m and _CACHE["path"] == path:
            return _CACHE["df"].copy()
        df = _load_df(path)
        if len(df) < MIN_DATASET_ROWS and path != env_path:
            print(f"[DATA] overgeslagen (slechts {len(df)} rijen, minimum {MIN_DATASET_ROWS}): {path}")
            continue
        _CACHE.update({"df": df, "mtime": m, "path": path, "source": "local"})
        print(f"[DATA] geladen (lokaal): {path} — {len(df)} rijen, {df.shape[1]} kolommen")
        return _CACHE["df"].copy()

    # 2) Fallback: online CSV (GitHub raw)
    if _CACHE["df"] is not None and _CACHE.get("source") == "online":
        return _CACHE["df"].copy()

    env_url = os.environ.get("PLANTWIJS_ONLINE_CSV_URL", "").strip()
    for url in ONLINE_CSV_URLS:
        df = _fetch_csv_online(url)
        if df is None or df.empty:
            continue
        if len(df) < MIN_DATASET_ROWS and url != env_url:
            print(f"[DATA] online overgeslagen (slechts {len(df)} rijen): {url}")
            continue
        _CACHE.update({"df": df, "mtime": time.time(), "path": url, "source": "online"})
        print(f"[DATA] geladen (online): {url} — {len(df)} rijen, {df.shape[1]} kolommen")
        return _CACHE["df"].copy()

    # 3) Niets gevonden → duidelijke foutmelding
    raise FileNotFoundError(
        "Geen dataset gevonden. Lokaal ontbreekt data/treeebb_planten_allfields.csv "
        "(of het bestand is kleiner dan het minimum) én de online CSV kon niet worden opgehaald."
    )


def clear_cache() -> None:
    """Leeg de dataset-cache; de eerstvolgende get_df() laadt opnieuw."""
    _CACHE.update({"df": None, "mtime": None, "path": None, "source": None})


def dataset_info() -> Dict[str, Any]:
    """Metadata over de geladen dataset (zonder de dataframe zelf)."""
    return {"path": _CACHE.get("path"), "source": _CACHE.get("source")}


# ───────────────────── JSON-cleaner
def _clean(o: Any) -> Any:
    if isinstance(o, float):
        return o if math.isfinite(o) else None
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    try:
        if pd.isna(o):
            return None
    except Exception:
        pass
    return o


# ───────────────────── filtering helpers
def _contains_ci(s: Any, needle: str) -> bool:
    return needle.lower() in str(s or "").lower()


def _split_tokens(cell: Any) -> List[str]:
    return [t.strip().lower()
            for t in re.split(r"[/|;,]+", str(cell or ""))
            if t.strip()]


# Canonieke bodemklasse → alle schrijfwijzen waaronder die klasse in de bronnen
# voorkomt. De TreeEbb-kolom `grondsoorten` kent precies de tokens "zand",
# "zavel", "lichte klei", "zware klei", "lemige grond", "löss", "veen" en
# "alle grondsoorten"; de losse woorden "klei" en "leem" komen daar dus nooit
# in voor. De BRO Bodemkaart levert daarnaast termen als "dekzand",
# "petgat(en)" en "moerig(e)". Zavel (8–25% lutum) is in de Nederlandse
# bodemclassificatie een kleigrond en telt daarom bij klei, niet bij leem.
# `services.pdok` gebruikt dezelfde tabel voor de ruwe kaarttermen, zodat de
# kaartzijde en de soortenfilter niet uiteen kunnen lopen.
SOIL_SYNONYMS: Dict[str, Tuple[str, ...]] = {
    "zand": ("zand", "dekzand"),
    "klei": ("klei", "lichte klei", "zware klei", "zavel"),
    "leem": ("leem", "lemige grond", "löss", "loess"),
    "veen": ("veen", "petgat", "moerig"),
}

_SOIL_CANON = set(SOIL_SYNONYMS)
_RE_ALL = re.compile(r"\balle\s+grondsoorten\b", re.I)

# Losse tokens zijn eenduidig; de volgorde bepaalt alleen welke klasse wint bij
# samengestelde ruwe kaarttermen die als filterkeuze binnenkomen
# ("zandige leem" → leem).
_SOIL_ORDER = ("leem", "zand", "klei", "veen")
_SOIL_RES: Dict[str, re.Pattern] = {
    canon: re.compile(r"\b(?:%s)\b" % "|".join(
        re.escape(s.replace("ö", "o")) for s in sorted(syns, key=len, reverse=True)
    ))
    for canon, syns in SOIL_SYNONYMS.items()
}


def _canon_soil_token(tok: str) -> Optional[str]:
    t = str(tok or "").strip().lower()
    if not t:
        return None
    t = t.replace("ö", "o")
    if _RE_ALL.search(t):
        return "__ALL__"
    for canon in _SOIL_ORDER:
        if _SOIL_RES[canon].search(t):
            return canon
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


def filter_standplaats(
    df: pd.DataFrame,
    vocht: Optional[List[str]] = None,
    bodem: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Filter op vochtklasse en bodem — één implementatie voor de hele app.

    Gebruikt door `/api/plants`, `/export/*`, het PDF-rapport (via
    `_filter_plants_df`) en door `/advies/geo`, zodat dezelfde standplaats
    altijd dezelfde soortenlijst oplevert.

    - **vocht**: exacte tokenvergelijking. De dataset gebruikt precies de vijf
      klassen uit docs/API.md (zeer droog|droog|vochtig|nat|zeer nat) en de
      Gt-afleiding in `services.pdok` levert dezelfde vijf, dus dat volstaat.
    - **bodem**: gecanoniseerde vergelijking via `_match_bodem_row`, op basis
      van `SOIL_SYNONYMS`. De TreeEbb-kolom `grondsoorten` bevat termen als
      "lichte klei" en "zavel" (→ klei) en "lemige grond" en "löss" (→ leem);
      "alle grondsoorten" telt bij elke klasse mee. Een ruwe kaartwaarde die
      niet naar zand/klei/leem/veen te herleiden is (bijvoorbeeld "Bebouwing")
      filtert bewust niet: liever de volledige lijst dan een lege.
    """
    vocht = [v for v in (vocht or []) if str(v or "").strip()]
    bodem = [b for b in (bodem or []) if str(b or "").strip()]
    if vocht:
        df = df[df["vocht"].apply(lambda v: _has_any(v, vocht))]
    if bodem:
        df = df[df.apply(lambda r: _match_bodem_row(r, bodem), axis=1)]
    return df


# ───────────────────── statusfilters (inheems/ingeburgerd/exoot)
# Wat de website standaard aanvinkt (static/js/state.js → defaultFilters()).
RAPPORT_STATUS_DEFAULT = (True, True, False)

STATUS_LABELS = ("inheems", "ingeburgerd", "exoot")


def rapport_status_defaults(
    toon_inheems: Optional[bool],
    toon_ingeburgerd: Optional[bool],
    toon_exoot: Optional[bool],
) -> tuple[Optional[bool], Optional[bool], Optional[bool]]:
    """Site-defaults voor de rapporten (md en PDF).

    Stuurt de aanroeper géén van de drie `toon_*`-parameters mee, dan krijgt
    een rapport dezelfde selectie als de website: inheems en ingeburgerd aan,
    exoot uit. Eén expliciete parameter is genoeg om die default te laten
    vervallen; dan winnen de opgegeven waarden onverkort.

    `format=json` op /advies/geo en /api/plants gebruiken dit bewust níét: daar
    blijft "niets meegegeven" gelijk aan "toon alles" (backwards compatible).
    """
    if toon_inheems is None and toon_ingeburgerd is None and toon_exoot is None:
        return RAPPORT_STATUS_DEFAULT
    return toon_inheems, toon_ingeburgerd, toon_exoot


def status_filter_labels(
    inheems_only: bool,
    toon_inheems: Optional[bool],
    toon_ingeburgerd: Optional[bool],
    toon_exoot: Optional[bool],
) -> List[str]:
    """De statussen die na filtering overblijven, voor vermelding in rapporten.

    Lege lijst betekent: er is niet op status gefilterd (alles blijft staan).
    """
    if inheems_only:
        return ["inheems"]
    keuzes = (toon_inheems, toon_ingeburgerd, toon_exoot)
    if all(k is None for k in keuzes):
        return []
    return [label for label, aan in zip(STATUS_LABELS, keuzes) if aan]


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
        return df.iloc[0:0]

    s = df["status_nl"].astype(str).str.strip().str.lower()
    return df[s.isin({a.lower() for a in allowed})]


def _derive_ptype_row(r: pd.Series) -> str:
    """Leid beplantingstype (boom/heester) af uit de TreeEbb-kolommen."""
    boom_src = str(r.get("beplantingstypes_boomtypen") or "").strip()
    overig_src = str(r.get("beplantingstypes_overige_beplanting") or "").strip()
    types: List[str] = []
    if boom_src:
        types.append("boom")
    if overig_src:
        types.append("heester")
    return " / ".join(types)


def ensure_beplantingstype(df: pd.DataFrame) -> pd.DataFrame:
    """Zorg dat de kolom 'beplantingstype' bestaat (voor de UI)."""
    if "beplantingstype" in df.columns:
        return df
    df = df.copy()
    df["beplantingstype"] = df.apply(_derive_ptype_row, axis=1)
    return df


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

    if q:
        df = df[df.apply(
            lambda r: _contains_ci(r.get("naam"), q) or _contains_ci(r.get("wetenschappelijke_naam"), q),
            axis=1
        )]

    # Afgeleid beplantingstype (boom/heester) + filter
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
    df = filter_standplaats(df, vocht, bodem)

    if sort in df.columns:
        df = df.sort_values(sort, ascending=not desc)

    return df
