"""Geocoding: adres → WGS84-coördinaten via de PDOK Locatieserver.

Alleen het publieke `free`-endpoint van de Locatieserver, zonder sleutel:

    https://api.pdok.nl/bzk/locatieserver/search/v3_1/free?rows=1&q=<adres>

We nemen de beste match (`rows=1`) en lezen daarvan `centroide_ll`, dat de
vorm `POINT(<lon> <lat>)` heeft — let op de volgorde: eerst lengtegraad, dan
breedtegraad. `weergavenaam` is het adres zoals PDOK het teruggeeft
("Loenenseweg 1, 7361 GB Beekbergen").

De service is bewust "stil": elke fout (time-out, HTTP-fout, onbruikbare
JSON, geen match) levert `None` op. De aanroeper vertaalt dat naar een nette
404, precies zoals docs/API.md voorschrijft. Eén kapotte bron mag nooit een
500 opleveren.
"""

from __future__ import annotations

import math
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import requests

from ..config import HEADERS

LOCATIESERVER_FREE = "https://api.pdok.nl/bzk/locatieserver/search/v3_1/free"
TIMEOUT_S = 8

# "POINT(5.98157932 52.14612744)" — ook met extra spaties of wetenschappelijke notatie.
_POINT_RE = re.compile(
    r"POINT\s*\(\s*([-+0-9.eE]+)\s+([-+0-9.eE]+)\s*\)",
    re.IGNORECASE,
)


def parse_point_ll(waarde: Any) -> Optional[Tuple[float, float]]:
    """`POINT(lon lat)` → `(lat, lon)`; None als er niets bruikbaars in staat."""
    m = _POINT_RE.search(str(waarde or ""))
    if not m:
        return None
    try:
        lon = float(m.group(1))
        lat = float(m.group(2))
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat) and math.isfinite(lon)):
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def zoek_adres(adres: str) -> Optional[Dict[str, Any]]:
    """Zoek een Nederlands adres/plaats op.

    Args:
        adres: vrije zoektekst, bijv. "Loenenseweg 1 Beekbergen".

    Returns:
        `{"adres_gevonden": str, "lat": float, "lon": float}` bij een treffer,
        anders `None` (geen match, lege invoer of een bronfout).
    """
    q = " ".join(str(adres or "").split())
    if not q:
        return None

    url = f"{LOCATIESERVER_FREE}?rows=1&q={urllib.parse.quote(q)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
        r.raise_for_status()
        docs = ((r.json() or {}).get("response") or {}).get("docs") or []
    except Exception as e:  # netwerk, HTTP-status, JSON — allemaal gewoon "geen match"
        print("[GEOCODE] lookup faalde voor", q, "→", e)
        return None

    if not docs:
        return None

    doc = docs[0] if isinstance(docs[0], dict) else {}
    punt = parse_point_ll(doc.get("centroide_ll"))
    if punt is None:
        return None

    lat, lon = punt
    naam = " ".join(str(doc.get("weergavenaam") or "").split()) or q
    return {"adres_gevonden": naam, "lat": lat, "lon": lon}
