"""Kennislaag samenvoegen tot de additieve velden van /advies/geo.

Levert de blokken `landschap`, `wortelbare_diepte` en `aanbevolen_beplanting`
uit docs/API.md. De inhoud komt uit `content/`:

- `context_descriptions.yaml` via `services.context` (landschapsverhalen);
- `wortelbare_diepte.yaml`   via `services.wortel`   (wortelruimte);
- `maatregelen.yaml`         (catalogus beplantingsvormen).

Scoring van de beplantingsvormen
--------------------------------
Elke vorm heeft in `maatregelen.yaml` een `past_bij` met per categorie
(fgr, nsn, vocht, bodem) een lijst id's uit `context_descriptions.yaml`.
De score van een vorm is de gewogen som van de categorieën waarvan het
gematchte entry-id in die lijst voorkomt (zie `_WEGING`: nsn 3, vocht 2,
fgr 1, bodem 1 — specifieker weegt zwaarder). Vormen met score 0 vallen af;
de rest wordt op score gesorteerd (bij gelijke score telt de volgorde in
het bestand) en afgekapt op vijf.

Blijven er minder dan drie vormen over, dan wordt aangevuld met de meest
**generieke** vormen. Generiek = de vorm die de minste eisen stelt: eerst het
aantal categorieën zonder beperking (lege of ontbrekende lijst betekent
volgens het bestand "geen beperking"), daarna het totale aantal genoemde
waarden, daarna de volgorde in het bestand. Voor de huidige catalogus levert
dat achtereenvolgens: bloemrijke zoom en mantel, houtsingel of erfsingel en
bomenrij of laan — vormen die in vrijwel elk Nederlands landschap kunnen.

Vocht weegt zwaarder dan de andere categorieën
----------------------------------------------
Een vorm die om nat land vraagt hoort niet op een droge stuwwal, ook al klopt
de rest. Daarom geldt bovenop de score:

1. **Uitsluiten.** Heeft een vorm een `past_bij.vocht` én is de vochtklasse van
   de locatie bekend én staat die klasse niet in de lijst, dan valt de vorm af.
   Zo verdwijnt de elzensingel van een droge plek, ook als fgr en bodem wel
   matchen. Blijven er daardoor minder dan `MIN_VORMEN` over, dan wordt pas in
   laatste instantie alsnog met de meest generieke — ook conflicterende —
   vormen aangevuld; het advies bevat liever een iets minder passende vorm dan
   niets (zie `aanbevolen_beplanting_voor_ids`).
2. **Lager rangschikken.** Is de vochtklasse onbekend, dan sluiten we niets uit,
   maar komen vormen mét een vochtvoorkeur bij gelijke score achter vormen
   zónder vochtvoorkeur: hun claim is hier immers niet te controleren. In de
   huidige catalogus noemt elke vorm een vochtvoorkeur, dus die tie-break
   verandert daar (nog) niets; hij is er voor vormen die dat later niet doen.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ..config import CONTENT_DIR
from . import context as ctx
from . import wortel

MAATREGELEN_YAML_PATH = os.path.join(CONTENT_DIR, "maatregelen.yaml")

# Categorieën die meetellen bij de score (de volgorde bepaalt alleen de
# opsomming in `waarom_hier`, niet de score zelf).
SCORE_CATEGORIEEN = ("fgr", "nsn", "bodem", "vocht")

# Hoe een gematchte titel in `waarom_hier` wordt genoemd.
_LABEL_VORM = {"vocht": "de vochtklasse {}"}

MAX_VORMEN = 5
MIN_VORMEN = 3

_CACHE: Dict[str, Any] = {"data": None, "mtime": None, "path": None}
_LOCK = threading.Lock()


# ───────────────────── maatregelen laden + cachen
def _vormen() -> List[dict]:
    path = MAATREGELEN_YAML_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None

    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
        return _CACHE["data"]

    with _LOCK:
        if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
            return _CACHE["data"]
        vormen: List[dict] = []
        if mtime is None:
            print(f"[MAATREGELEN] ontbreekt: {path}")
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                vormen = [v for v in (raw.get("vormen") or []) if isinstance(v, dict)]
            except Exception as e:
                print("[MAATREGELEN] fout bij laden:", e)
                vormen = []
        _CACHE.update({"data": vormen, "mtime": mtime, "path": path})
    return _CACHE["data"]


def reload_cache() -> None:
    with _LOCK:
        _CACHE.update({"data": None, "mtime": None, "path": None})


# ───────────────────── helpers
def _lijst(v: Any) -> List[str]:
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x or "").strip()]
    return [str(v).strip()]


def _eerste_zin(tekst: Any) -> str:
    t = " ".join(str(tekst or "").split())
    if not t:
        return ""
    m = re.search(r"^.*?[.!?](?=\s|$)", t)
    return (m.group(0) if m else t).strip()


def _opsomming(delen: List[str]) -> str:
    delen = [d for d in delen if d]
    if not delen:
        return ""
    if len(delen) == 1:
        return delen[0]
    return ", ".join(delen[:-1]) + " en " + delen[-1]


def _genericiteit(vorm: dict) -> Tuple[int, int]:
    """(aantal categorieën zonder beperking, totaal aantal genoemde waarden)."""
    past = vorm.get("past_bij") or {}
    vrij = 0
    totaal = 0
    for cat in SCORE_CATEGORIEEN:
        waarden = _lijst(past.get(cat))
        if not waarden:
            vrij += 1
        totaal += len(waarden)
    return vrij, totaal


def _vocht_eis(vorm: dict) -> List[str]:
    """De vochtklassen (entry-id's) waar deze vorm om vraagt; leeg = geen eis."""
    return [str(x).strip() for x in _lijst((vorm.get("past_bij") or {}).get("vocht"))]


def _vocht_bekend(ids: Dict[str, Optional[str]]) -> bool:
    eid = ids.get("vocht")
    return bool(eid) and eid != "onbekend"


def _vocht_conflict(vorm: dict, ids: Dict[str, Optional[str]]) -> bool:
    """Sluit deze vorm de vochtklasse van de locatie uit?

    Alleen waar als de vorm een vochtvoorkeur heeft, de vochtklasse van de
    locatie bekend is en die klasse er niet bij staat.
    """
    eis = _vocht_eis(vorm)
    if not eis or not _vocht_bekend(ids):
        return False
    return ids.get("vocht") not in eis


def _vocht_rangorde(vorm: dict, ids: Dict[str, Optional[str]]) -> int:
    """Tie-break bij onbekend vocht: 1 voor vormen mét een vochtvoorkeur."""
    if _vocht_bekend(ids):
        return 0
    return 1 if _vocht_eis(vorm) else 0


# Treffers wegen naar zeggingskracht: NSN is de meest specifieke kaartlaag
# (48 klassen) en vocht de meest onderscheidende standplaatsfactor; fgr en
# bodem zijn grofmazig. Zonder weging verdringen brede allemansvriend-vormen
# de kenmerkende vorm (bv. klein bosje boven elzensingel in een nat beekdal).
_WEGING = {"nsn": 3, "vocht": 2, "fgr": 1, "bodem": 1}


def _score(vorm: dict, ids: Dict[str, Optional[str]]) -> Tuple[int, List[str]]:
    """Gewogen score + de categorieën die de treffer opleverden."""
    past = vorm.get("past_bij") or {}
    treffers: List[str] = []
    score = 0
    for cat in SCORE_CATEGORIEEN:
        eid = ids.get(cat)
        if not eid or eid == "onbekend":
            continue
        if eid in [str(x).strip() for x in _lijst(past.get(cat))]:
            treffers.append(cat)
            score += _WEGING[cat]
    return score, treffers


def _label(cat: str, eid: Optional[str]) -> str:
    e = ctx.entry_by_id(cat, eid) if eid else None
    titel = ((e or {}).get("titel") or "").strip()
    if not titel:
        return ""
    return _LABEL_VORM.get(cat, "{}").format(titel[0].lower() + titel[1:])


def _waarom_hier(vorm: dict, treffers: List[str], ids: Dict[str, Optional[str]]) -> str:
    labels = [_label(cat, ids.get(cat)) for cat in SCORE_CATEGORIEEN if cat in treffers]
    labels = [l for l in labels if l]
    bio = _eerste_zin(vorm.get("biodiversiteit"))
    if labels:
        kop = f"Sluit aan op {_opsomming(labels)}."
    else:
        kop = ("Deze vorm stelt weinig eisen aan de standplaats en past in vrijwel "
               "elk Nederlands landschap.")
    return " ".join(p for p in (kop, bio) if p)


def _vorm_naar_advies(vorm: dict, treffers: List[str], ids: Dict[str, Optional[str]]) -> dict:
    return {
        "vorm": str(vorm.get("naam") or vorm.get("id") or "").strip(),
        "omschrijving": " ".join(str(vorm.get("omschrijving") or "").split()),
        "waarom_hier": _waarom_hier(vorm, treffers, ids),
        "voorbeeldsoorten": _lijst(vorm.get("voorbeeldsoorten")),
    }


# ───────────────────── publieke API
def aanbevolen_beplanting(
    fgr: Any = None,
    nsn: Any = None,
    vocht: Any = None,
    bodem: Any = None,
) -> List[dict]:
    """Passende beplantingsvormen voor deze locatie (max 5, minimaal 3)."""
    ids = {
        "fgr": ctx.entry_id("fgr", fgr),
        "nsn": ctx.entry_id("nsn", nsn),
        "vocht": ctx.entry_id("vocht", vocht),
        "bodem": ctx.entry_id("bodem", bodem),
    }
    return aanbevolen_beplanting_voor_ids(ids)


def aanbevolen_beplanting_voor_ids(ids: Dict[str, Optional[str]]) -> List[dict]:
    vormen = _vormen()
    if not vormen:
        return []

    conflict = {i: _vocht_conflict(v, ids) for i, v in enumerate(vormen)}

    gescoord: List[Tuple[int, int, int, dict, List[str]]] = []
    for i, v in enumerate(vormen):
        if conflict[i]:
            continue  # vraagt om ander vocht dan deze plek heeft
        score, treffers = _score(v, ids)
        if score > 0:
            gescoord.append((score, _vocht_rangorde(v, ids), i, v, treffers))
    # score desc, dan vormen zonder onbewezen vochtclaim, dan bestandsvolgorde
    gescoord.sort(key=lambda t: (-t[0], t[1], t[2]))

    gekozen = [(v, tr) for _s, _r, _i, v, tr in gescoord[:MAX_VORMEN]]

    if len(gekozen) < MIN_VORMEN:
        gekozen_ids = {v.get("id") for v, _ in gekozen}
        generiek = sorted(
            enumerate(vormen),
            key=lambda t: (-_genericiteit(t[1])[0], -_genericiteit(t[1])[1], t[0]),
        )
        # Eerst de generieke vormen die niet met het vocht botsen; alleen als er
        # dan nog te weinig zijn, mogen de conflicterende alsnog aanvullen.
        for negeer_conflict in (False, True):
            for i, v in generiek:
                if len(gekozen) >= MIN_VORMEN:
                    break
                if v.get("id") in gekozen_ids:
                    continue
                if conflict[i] and not negeer_conflict:
                    continue
                gekozen.append((v, []))
                gekozen_ids.add(v.get("id"))

    return [_vorm_naar_advies(v, tr, ids) for v, tr in gekozen]


def landschap(
    fgr: Any = None,
    nsn: Any = None,
    gmm: Any = None,
    bodem: Any = None,
    vocht: Any = None,
) -> Dict[str, Optional[dict]]:
    """Per categorie het landschapsverhaal (of null)."""
    waarden = {"fgr": fgr, "nsn": nsn, "gmm": gmm, "bodem": bodem, "vocht": vocht}
    return {cat: ctx.beschrijf(cat, waarden.get(cat)) for cat in ctx.CATEGORIEEN}


def verrijk_advies(
    fgr: Any = None,
    nsn: Any = None,
    gmm: Any = None,
    bodem: Any = None,
    vocht: Any = None,
    gt_code: Any = None,
) -> Dict[str, Any]:
    """De additieve kennislaag-velden van /advies/geo.

    Returns:
        `{"landschap": {...}, "wortelbare_diepte": {...}|None,
          "aanbevolen_beplanting": [...]}`
    """
    ids = {
        "fgr": ctx.entry_id("fgr", fgr),
        "nsn": ctx.entry_id("nsn", nsn),
        "vocht": ctx.entry_id("vocht", vocht),
        "bodem": ctx.entry_id("bodem", bodem),
    }
    return {
        "landschap": landschap(fgr=fgr, nsn=nsn, gmm=gmm, bodem=bodem, vocht=vocht),
        "wortelbare_diepte": wortel.bepaal(bodem=bodem, gt_code=gt_code, nsn=nsn),
        "aanbevolen_beplanting": aanbevolen_beplanting_voor_ids(ids),
    }
