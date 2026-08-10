"""Kennisregels: indicatieve wortelbare diepte.

Leest `content/wortelbare_diepte.yaml` en past de daarin beschreven stappen toe:

1. Bepaal de bodemcomponent (textuur/bodemtype) en de Gt-klasse.
2. Kies de bijpassende basisregel (bodem x Gt) → klasse + bandbreedte.
3. Pas een NSN/BKNSN-modifier toe als die relevant is (klasse verschuiven of
   de cm-banden oprekken).
4. Neem de beperkende factoren, maatregelen en de disclaimer op in de
   toelichting.

Alle inhoud komt uit het YAML-bestand: klassen, regels, modifiers en de
klasse-volgorde staan **niet** in deze module. Wat hier wél staat is de
vertaling van ruwe kaartwaarden naar de tokens die het bestand gebruikt
(bijvoorbeeld "Zware klei" → `zware_klei`, "VIo" → `vio`), en dat gebeurt
generiek op basis van de tokens die in het bestand voorkomen.

Het bestand wordt gecachet met een mtime-controle, net als context.py.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ..config import CONTENT_DIR

WORTEL_YAML_PATH = os.path.join(CONTENT_DIR, "wortelbare_diepte.yaml")

_CACHE: Dict[str, Any] = {"data": None, "mtime": None, "path": None}
_LOCK = threading.Lock()

# Romeinse Gt-basis, langste eerst zodat "viii" vóór "vi" en "v" wordt herkend.
_ROMAN_RE = re.compile(r"^(viii|vii|vi|iv|v|iii|ii|i)([a-z]*)$")


# ───────────────────── helpers
def _norm(s: Any) -> str:
    return " ".join(str(s if s is not None else "").strip().lower().split())


def _token(s: Any) -> str:
    """Normaliseer naar de schrijfwijze die het YAML-bestand gebruikt."""
    return _norm(s).replace(" ", "_").replace("-", "_").replace("/", "_")


def _leesbaar(token: Any) -> str:
    return _norm(str(token or "").replace("_", " "))


def _opsomming(tokens: List[Any]) -> str:
    return ", ".join(_leesbaar(t) for t in tokens if str(t or "").strip())


# ───────────────────── laden + cachen
def _data() -> Dict[str, Any]:
    path = WORTEL_YAML_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = None

    if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
        return _CACHE["data"]

    with _LOCK:
        if _CACHE["data"] is not None and _CACHE["mtime"] == mtime and _CACHE["path"] == path:
            return _CACHE["data"]
        data: Dict[str, Any] = {}
        if mtime is None:
            print(f"[WORTEL] ontbreekt: {path}")
        else:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    raw = yaml.safe_load(f) or {}
                data = raw.get("wortelbare_diepte") or {}
            except Exception as e:
                print("[WORTEL] fout bij laden:", e)
                data = {}
        _CACHE.update({"data": data, "mtime": mtime, "path": path})
    return _CACHE["data"]


def reload_cache() -> None:
    with _LOCK:
        _CACHE.update({"data": None, "mtime": None, "path": None})


def _regels() -> List[dict]:
    return list(((_data().get("basisregels_bodem_gt") or {}).get("regels")) or [])


def _klassen() -> Dict[str, dict]:
    return dict(_data().get("klassen") or {})


def _klasse_orde() -> List[str]:
    orde = ((_data().get("nsn_modifiers") or {}).get("klasse_orde")) or []
    return [str(k) for k in orde] or list(_klassen().keys())


def _modifiers() -> List[dict]:
    return list(((_data().get("nsn_modifiers") or {}).get("regels")) or [])


# ───────────────────── invoer → tokens uit het bestand
def _alle_tokens(veld: str) -> List[str]:
    """Alle unieke waarden die in de basisregels onder `veld` voorkomen."""
    uit: List[str] = []
    for r in _regels():
        for t in r.get(veld) or []:
            t = _token(t)
            if t and t not in uit:
                uit.append(t)
    return uit


def bodem_token(bodem: Any) -> Optional[str]:
    """Zet een bodemwaarde om naar een token uit het YAML-bestand.

    Werkt zowel voor de gecanoniseerde categorieën (zand|klei|leem|veen) als
    voor ruwe bodemkaart-omschrijvingen; in dat laatste geval wint het langste
    token dat als tekst in de omschrijving voorkomt (zodat "zware klei" wint
    van "klei").
    """
    tokens = _alle_tokens("bodem")
    if not tokens:
        return None
    t = _token(bodem)
    if not t:
        return None
    if t in tokens:
        return t
    tekst = _norm(bodem)
    kandidaten = [k for k in tokens if _leesbaar(k) and _leesbaar(k) in tekst]
    if kandidaten:
        return max(kandidaten, key=lambda k: len(k))
    return None


def gt_token(gt_code: Any) -> Optional[str]:
    """Zet een Gt-code (bijv. "VIo", "IIIb", "VI") om naar een token uit het bestand."""
    tokens = _alle_tokens("gt")
    if not tokens:
        return None
    t = _token(gt_code)
    if not t:
        return None
    if t in tokens:
        return t
    m = _ROMAN_RE.match(t)
    if not m:
        return None
    basis = m.group(1)
    # Zonder (of met onbekende) letter-suffix: pak het eerste token met dezelfde
    # romeinse basis in bestandsvolgorde.
    for k in tokens:
        mk = _ROMAN_RE.match(k)
        if mk and mk.group(1) == basis:
            return k
    return None


# ───────────────────── basisregel kiezen
def _regel_voor(bodem_t: Optional[str], gt_t: Optional[str]) -> Optional[dict]:
    for r in _regels():
        bodems = [_token(b) for b in (r.get("bodem") or [])]
        gts = [_token(g) for g in (r.get("gt") or [])]
        if bodem_t and gt_t:
            if bodem_t in bodems and gt_t in gts:
                return r
    return None


def _mediane_regel(regels: List[dict]) -> Optional[dict]:
    """Kies uit meerdere kandidaat-regels de middelste klasse.

    Wordt gebruikt als maar één van beide invoerwaarden bekend is (of als de
    combinatie bodem x Gt niet in het bestand staat): niet de gunstigste en
    niet de ongunstigste uitkomst, maar het midden.
    """
    if not regels:
        return None
    orde = _klasse_orde()

    def idx(r: dict) -> int:
        k = str(r.get("klasse") or "")
        return orde.index(k) if k in orde else len(orde)

    gesorteerd = sorted(regels, key=idx)
    return gesorteerd[len(gesorteerd) // 2]


def _regels_met(veld: str, token: str) -> List[dict]:
    return [r for r in _regels() if token in [_token(v) for v in (r.get(veld) or [])]]


# ───────────────────── NSN-modifiers
def _modifier_sleutels(rule: dict) -> Tuple[List[str], List[str]]:
    """Trefwoorden en BKNSN-codes waarmee een modifier-regel herkend wordt.

    - `nsn`-waarden met het voorvoegsel `bknsn_` zijn BKNSN-codes (Rg2, Sw4x, …).
      Die matchen alleen als de aanroeper daadwerkelijk een code meegeeft.
    - Overige `nsn`-waarden leveren hun langste woorddeel als trefwoord
      (`dekzand_dekzandrug` → "dekzandrug").
    - De `toelichting` begint per regel met een lijst labels gescheiden door
      schuine strepen ("Kom/uiterwaard/restgeul/…"); die lijst is de tweede
      bron van trefwoorden. Zo blijven de sleutels in het bestand staan.
    """
    trefwoorden: List[str] = []
    codes: List[str] = []
    for t in rule.get("nsn") or []:
        tok = _token(t)
        if not tok:
            continue
        if tok.startswith("bknsn_"):
            codes.append(tok[len("bknsn_"):])
            continue
        delen = [d for d in tok.split("_") if len(d) >= 3]
        if delen:
            trefwoorden.append(max(delen, key=len))

    toel = _norm(rule.get("toelichting"))
    kop = re.match(r"^([^\s:]+(?:/[^\s:]+)+)", toel)
    if kop:
        for w in kop.group(1).split("/"):
            w = w.strip(" ,.;:")
            if len(w) >= 3:
                trefwoorden.append(w)
    return sorted(set(trefwoorden)), sorted(set(codes))


def _modifier_voor(nsn: Any) -> Optional[dict]:
    """Eerste modifier-regel die bij het NSN-label (of de BKNSN-code) past."""
    n = _norm(nsn)
    if not n:
        return None
    woorden = set(re.split(r"[^a-z0-9]+", n))
    for rule in _modifiers():
        trefwoorden, codes = _modifier_sleutels(rule)
        if any(w and w in n for w in trefwoorden):
            return rule
        if any(c and c in woorden for c in codes):
            return rule
    return None


# ───────────────────── band-rekenwerk
def _split_band(band: Any) -> Optional[Tuple[int, int]]:
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(band or ""))
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def _verschuif(klasse: str, stappen: int) -> str:
    orde = _klasse_orde()
    if klasse not in orde:
        return klasse
    i = orde.index(klasse) + int(stappen)
    i = max(0, min(len(orde) - 1, i))
    return orde[i]


# ───────────────────── publieke API
def bepaal(bodem: Any = None, gt_code: Any = None, nsn: Any = None) -> Optional[dict]:
    """Indicatieve wortelbare diepte voor een locatie.

    Args:
        bodem: bodemcategorie of ruwe bodemkaart-omschrijving (mag None zijn).
        gt_code: grondwatertrap, bijvoorbeeld "VIo" (mag None zijn).
        nsn: NSN/BKNSN-label of -code (optioneel; alleen bijsturend).

    Returns:
        `{klasse, band_cm, indicatie, toelichting}` of None wanneer er te
        weinig invoer is (géén bodem én géén Gt) of het bestand ontbreekt.
    """
    if not _regels() or not _klassen():
        return None

    bodem_t = bodem_token(bodem)
    gt_t = gt_token(gt_code)
    if not bodem_t and not gt_t:
        return None

    # Voor de toelichting: toon de Gt zoals de kaart hem levert ("VIo"), niet het token.
    gt_label = str(gt_code or "").strip() or _leesbaar(gt_t).upper()

    regel = _regel_voor(bodem_t, gt_t)
    grondslag: str
    if regel is not None:
        grondslag = f"bodem ({_leesbaar(bodem_t)}) en grondwatertrap ({gt_label})"
    elif gt_t:
        # Gt is de primaire factor in het bestand; die krijgt voorrang.
        regel = _mediane_regel(_regels_met("gt", gt_t))
        grondslag = f"grondwatertrap ({gt_label})"
        if bodem_t:
            grondslag += f"; de combinatie met bodem ({_leesbaar(bodem_t)}) staat niet in de regels"
    else:
        regel = _mediane_regel(_regels_met("bodem", bodem_t))
        grondslag = f"bodem ({_leesbaar(bodem_t)}); grondwatertrap onbekend"

    if regel is None:
        return None

    klasse = str(regel.get("klasse") or "")
    band = _split_band(regel.get("wortelbare_diepte_cm")) or \
        _split_band((_klassen().get(klasse) or {}).get("band_cm"))
    if band is None:
        return None
    lo, hi = band

    # ── stap 3: NSN/BKNSN-modifier
    mod = _modifier_voor(nsn)
    mod_tekst = ""
    if mod:
        effect = mod.get("effect") or {}
        if effect.get("verschuif_klasse"):
            klasse = _verschuif(klasse, effect["verschuif_klasse"])
            nieuwe_band = _split_band((_klassen().get(klasse) or {}).get("band_cm"))
            if nieuwe_band:
                lo, hi = nieuwe_band
        lo += int(effect.get("min_cm_plus") or 0)
        hi += int(effect.get("max_cm_plus") or 0)
        mod_tekst = str(mod.get("toelichting") or "").strip()

    klasse_info = _klassen().get(klasse) or {}
    indicatie = str(klasse_info.get("indicatie") or "").strip()

    # ── stap 4: toelichting samenstellen
    delen: List[str] = [f"Ingeschat op basis van {grondslag}."]
    factoren = _opsomming(regel.get("beperkende_factoren") or [])
    if factoren:
        delen.append(f"Beperkende factoren: {factoren}.")
    maatregelen = _opsomming(regel.get("maatregelen") or [])
    if maatregelen:
        delen.append(f"Aandachtspunten: {maatregelen}.")
    if mod_tekst:
        delen.append(f"Bijstelling vanuit het natuurlijk systeem: {mod_tekst}")
    opmerking = str((_data().get("meta") or {}).get("opmerking") or "").strip()
    if opmerking:
        delen.append(opmerking)

    return {
        "klasse": klasse,
        "band_cm": f"{lo}-{hi}",
        "indicatie": indicatie,
        "toelichting": " ".join(d for d in delen if d),
    }
