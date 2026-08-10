"""Kennislaag: landschapsverhalen per kaartwaarde.

Leest `content/context_descriptions.yaml` en zet een ruwe kaartwaarde
(bijvoorbeeld "Hogere zandgronden" of "Beekdal zand/leem") om naar het
bijbehorende verhaal.

De matchconventie staat beschreven in `content/README.md` en wordt hier
letterlijk gevolgd:

1. Normaliseer de kaartwaarde (trim, kleine letters, spaties samenvouwen).
2. Lege of ontbrekende waarde  ⇒ direct de fallback-entry.
3. `match_exact` (gelijkheid), eerste treffer wint.
4. `match` (deeltekst) in **bestandsvolgorde**, eerste treffer wint.
   De volgorde in het YAML-bestand is dus betekenisvol.
5. Nog geen treffer ⇒ de fallback-entry (lege `match` én lege `match_exact`).

De YAML wordt in het geheugen gecachet; de mtime wordt bij elke aanroep
gecontroleerd, zodat een gewijzigd bestand zonder herstart wordt opgepakt.
"""

from __future__ import annotations

import os
import threading
from typing import Any, Dict, List, Optional

import yaml

from ..config import CONTENT_DIR

CONTEXT_YAML_PATH = os.path.join(CONTENT_DIR, "context_descriptions.yaml")

# Categorieën uit docs/API.md; de YAML is leidend, dit is alleen de volgorde
# waarin het blok `landschap` wordt opgebouwd.
CATEGORIEEN = ("fgr", "nsn", "gmm", "bodem", "vocht")

_CACHE: Dict[str, Any] = {"data": None, "mtime": None, "path": None}
_LOCK = threading.Lock()


# ───────────────────── normalisatie
def norm(s: Any) -> str:
    """Trim, kleine letters, meervoudige spaties samenvoegen."""
    return " ".join(str(s if s is not None else "").strip().lower().split())


def _as_list(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x) for x in v if str(x or "").strip()]
    s = str(v).strip()
    return [s] if s else []


# ───────────────────── laden + cachen
def _read_yaml(path: str) -> Dict[str, List[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    cats = raw.get("categorieen") or {}
    out: Dict[str, List[dict]] = {}
    for cat, entries in cats.items():
        lijst: List[dict] = []
        for e in entries or []:
            if not isinstance(e, dict):
                continue
            lijst.append({
                "id": str(e.get("id") or ""),
                "match_exact": _as_list(e.get("match_exact")),
                "match": _as_list(e.get("match")),
                "titel": e.get("titel") or "",
                "ontstaan": e.get("ontstaan") or "",
                "versterken": _as_list(e.get("versterken")),
                "bron": e.get("bron") or "",
            })
        out[str(cat)] = lijst
    return out


def _data() -> Dict[str, List[dict]]:
    """Geef de (gecachete) categorieën terug; herlaadt bij gewijzigde mtime."""
    path = CONTEXT_YAML_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None

    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
        return _CACHE["data"]

    with _LOCK:
        # dubbelcheck binnen het slot
        if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
            return _CACHE["data"]
        if mtime is None:
            print(f"[CONTEXT] ontbreekt: {path}")
            data: Dict[str, List[dict]] = {}
        else:
            try:
                data = _read_yaml(path)
            except Exception as e:  # kapotte YAML mag de API nooit slopen
                print("[CONTEXT] fout bij laden:", e)
                data = {}
        _CACHE.update({"data": data, "mtime": mtime, "path": path})
    return _CACHE["data"]


def reload_cache() -> None:
    """Forceer een herlaad bij de eerstvolgende aanroep (voor tests/admin)."""
    with _LOCK:
        _CACHE.update({"data": None, "mtime": None, "path": None})


def categorieen() -> List[str]:
    """Alle categorieën die in het YAML-bestand staan."""
    return list(_data().keys())


def entries(categorie: str) -> List[dict]:
    """Alle entries van een categorie, in bestandsvolgorde."""
    return _data().get(str(categorie or "").strip().lower(), [])


# ───────────────────── matcher (referentie-implementatie uit content/README.md)
def _fallback(lijst: List[dict]) -> Optional[dict]:
    return next((e for e in lijst if not e["match"] and not e["match_exact"]), None)


def zoek(categorie: str, waarde: Any) -> Optional[dict]:
    """Zoek de entry die bij een kaartwaarde hoort.

    Onbekende categorie ⇒ None. Lege waarde ⇒ fallback-entry (of None als de
    categorie geen fallback heeft).
    """
    lijst = entries(categorie)
    if not lijst:
        return None

    fallback = _fallback(lijst)
    v = norm(waarde)
    if not v:
        return fallback

    for e in lijst:
        if any(norm(m) == v for m in e["match_exact"]):
            return e
    for e in lijst:
        for m in e["match"]:
            mn = norm(m)
            if mn and mn in v:
                return e
    return fallback


def entry_id(categorie: str, waarde: Any) -> Optional[str]:
    """Het id van de gematchte entry (sleutel voor `past_bij` in maatregelen.yaml)."""
    e = zoek(categorie, waarde)
    return e["id"] if e else None


def entry_by_id(categorie: str, eid: str) -> Optional[dict]:
    """Zoek een entry op zijn stabiele id."""
    key = str(eid or "").strip().lower()
    if not key:
        return None
    return next((e for e in entries(categorie) if e["id"].lower() == key), None)


def beschrijf(categorie: str, waarde: Any) -> Optional[dict]:
    """Landschapsverhaal voor een kaartwaarde, conform docs/API.md.

    Retourneert `{titel, ontstaan, versterken, bron}` of None als de categorie
    onbekend is (of de categorie geen enkele passende entry kent).
    """
    e = zoek(categorie, waarde)
    if not e:
        return None
    return {
        "titel": e["titel"],
        "ontstaan": e["ontstaan"],
        "versterken": list(e["versterken"]),
        "bron": e["bron"],
    }
