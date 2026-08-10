"""Het volledige locatie-advies als Markdown-rapport (WP6).

Doel: een AI-agent of een mens haalt met één URL-fetch het complete advies op,
in een formaat dat zonder JSON-parser leesbaar is. De input is exact het dict
dat `/advies/geo` als JSON teruggeeft; deze module voegt niets toe en verzint
niets — hij zet alleen om.

Twee regels waar de rest van de module op gebouwd is:

1. **Nooit een kale `None` of `null` in de tekst.** Ontbrekende waarden krijgen
   een Nederlandse uitleg ("niet bepaald"), zodat een lezer weet dat de bron
   niets gaf en niet denkt dat er iets stuk is.
2. **Geen lege secties.** Elke kop krijgt inhoud; als een blok ontbreekt komt er
   een zin die uitlegt waarom, met wat je zonder dat blok kunt doen.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

MAX_SOORTEN = 40

# Waarden die "leeg" betekenen zodra ze als tekst binnenkomen.
_LEEG = {"", "-", "nan", "none", "null", "na", "n.v.t.", "onbekend"}

# Volgorde en labels van de landschapsblokken.
_LANDSCHAP_LABELS = (
    ("fgr", "fysisch-geografische regio"),
    ("nsn", "natuurlijk systeem"),
    ("gmm", "landvorm"),
    ("bodem", "bodem"),
    ("vocht", "vocht"),
)

# Labels bij de bronstatussen uit `bronnen_status`.
_BRON_LABELS = {
    "fgr": "Fysisch-geografische regio's (PDOK)",
    "bodem": "BRO Bodemkaart",
    "gwt": "BRO Grondwaterspiegeldiepte (Gt/GLG)",
    "ahn": "Actueel Hoogtebestand Nederland (AHN)",
    "gmm": "BRO Geomorfologische kaart (GMM)",
    "nsn": "Basiskaart Natuurlijk Systeem Nederland (BKNSN 2023)",
}

_STATUS_UITLEG = {
    "ok": "waarde gevonden",
    "leeg": "bron antwoordde, maar heeft hier geen waarde",
    "fout": "bron was niet bereikbaar",
    "ontbreekt": "bronbestand is op deze server niet geïnstalleerd",
}

_TABEL_KOLOMMEN = (
    ("naam", "Naam"),
    ("wetenschappelijke_naam", "Wetenschappelijke naam"),
    ("beplantingstype", "Type"),
    ("standplaats_licht", "Licht"),
    ("vocht", "Vocht"),
    ("hoogte", "Hoogte"),
    ("status_nl", "Status"),
)

DISCLAIMER = (
    "Dit advies is indicatief en gebaseerd op landelijke kaarten op regioschaal. "
    "De situatie in een tuin of op een erf kan daarvan afwijken door ophoging, "
    "vergraving, verdichting, drainage of bebouwing. Graaf een proefgat voordat je "
    "plant, en controleer altijd de regels van gemeente en waterschap "
    "(vergunningen, herplantplicht, afstand tot de erfgrens)."
)


# ───────────────────── tekst-helpers
def _tekst(waarde: Any, fallback: str = "") -> str:
    """Waarde als nette regel tekst; lege/onbruikbare waarden → `fallback`."""
    if waarde is None:
        return fallback
    if isinstance(waarde, float):
        # NaN is niet gelijk aan zichzelf; verder gewoon netjes afronden.
        if waarde != waarde:
            return fallback
        s = f"{waarde:.6f}".rstrip("0").rstrip(".")
    else:
        s = " ".join(str(waarde).split())
    return fallback if s.lower() in _LEEG else s


def _cel(waarde: Any, fallback: str = "onbekend") -> str:
    """Tekst die veilig in een markdown-tabelcel past."""
    return _tekst(waarde, fallback).replace("|", "\\|")


def _alinea(waarde: Any) -> str:
    return " ".join(str(waarde or "").split())


def _lijst(waarde: Any) -> List[str]:
    if not waarde:
        return []
    if isinstance(waarde, (list, tuple)):
        return [_alinea(x) for x in waarde if _alinea(x)]
    return [_alinea(waarde)]


def _tabel(kop: Iterable[str], rijen: Iterable[Iterable[str]]) -> List[str]:
    kop = list(kop)
    regels = ["| " + " | ".join(kop) + " |",
              "|" + "|".join(["---"] * len(kop)) + "|"]
    regels += ["| " + " | ".join(r) + " |" for r in rijen]
    return regels


def _coord(waarde: Any) -> str:
    try:
        return f"{float(waarde):.5f}"
    except (TypeError, ValueError):
        return ""


# ───────────────────── secties
def _kop_titel(data: Dict[str, Any]) -> str:
    loc = data.get("locatie") or {}
    adres = _tekst(loc.get("adres_gevonden"))
    if adres:
        return adres
    lat, lon = _coord(loc.get("lat")), _coord(loc.get("lon"))
    if lat and lon:
        return f"{lat}, {lon}"
    return "deze locatie"


def _sectie_plek(data: Dict[str, Any]) -> List[str]:
    loc = data.get("locatie") or {}
    lat, lon = _coord(loc.get("lat")), _coord(loc.get("lon"))
    adres = _tekst(loc.get("adres_gevonden"))

    rijen: List[List[str]] = []
    if adres:
        rijen.append(["Adres (gevonden)", _cel(adres), "PDOK Locatieserver"])
    rijen.append([
        "Coördinaten (WGS84)",
        _cel(f"{lat}, {lon}" if lat and lon else "", "niet bepaald"),
        "opgegeven of geocodeerd",
    ])

    velden = (
        ("Fysisch-geografische regio", data.get("fgr"), "FGR (PDOK)"),
        ("Natuurlijk systeem", data.get("nsn"), "BKNSN 2023"),
        ("Landvorm (geomorfologie)", data.get("gmm"), data.get("gmm_bron")),
        ("Bodem", data.get("bodem"), data.get("bodem_bron")),
        ("Vochtklasse", data.get("vocht"), data.get("vocht_bron")),
        ("Grondwatertrap (Gt)", data.get("gt_code"), data.get("vocht_bron")),
        ("Maaiveldhoogte", _hoogte(data.get("ahn")), data.get("ahn_bron")),
    )
    for label, waarde, bron in velden:
        rijen.append([label, _cel(waarde, "niet bepaald"), _cel(bron, "niet beschikbaar")])

    regels = ["## Jouw plek", ""]
    regels += _tabel(["Kenmerk", "Waarde", "Bron"], rijen)
    regels += [
        "",
        "Alle waarden komen uit landelijke kaarten en gelden voor de plek van het "
        "punt hierboven; ze zijn indicatief op regioschaal.",
    ]
    return regels


def _hoogte(ahn: Any) -> str:
    h = _tekst(ahn)
    return f"{h} m t.o.v. NAP" if h else ""


def _sectie_landschap(data: Dict[str, Any]) -> List[str]:
    landschap = data.get("landschap") or {}
    regels = ["## Jouw landschap", ""]

    blokken = 0
    for sleutel, label in _LANDSCHAP_LABELS:
        blok = landschap.get(sleutel)
        if not isinstance(blok, dict):
            continue
        titel = _tekst(blok.get("titel"))
        ontstaan = _alinea(blok.get("ontstaan"))
        versterken = _lijst(blok.get("versterken"))
        if not titel or not (ontstaan or versterken):
            continue
        blokken += 1
        regels += [f"### {titel} ({label})", ""]
        if ontstaan:
            regels += [ontstaan, ""]
        if versterken:
            regels += ["Zo versterk je dit landschap:", ""]
            regels += [f"- {v}" for v in versterken]
            regels += [""]
        bron = _tekst(blok.get("bron"))
        if bron:
            regels += [f"Bron: {bron}", ""]

    if not blokken:
        regels += [
            "Voor deze plek kon geen enkel landschapsverhaal worden samengesteld: "
            "de kaartlagen gaven hier geen waarde. Gebruik de bodem en de vochtklasse "
            "uit de tabel hierboven als basis voor je soortkeuze, en kijk in de "
            "omgeving welke beplantingsvormen er van oudsher voorkomen.",
            "",
        ]
    return regels


def _sectie_wortelruimte(data: Dict[str, Any]) -> List[str]:
    regels = ["## Wortelruimte", ""]
    wortel = data.get("wortelbare_diepte")
    if not isinstance(wortel, dict) or not wortel:
        regels += [
            "De bewortelbare diepte kon hier niet worden ingeschat, omdat de bodem "
            "en/of de grondwatertrap onbekend zijn. Graaf een proefgat van ongeveer "
            "een meter diep: de diepte waarop je grondwater of een storende laag "
            "tegenkomt, is in de praktijk de grens voor de beworteling.",
            "",
        ]
        return regels

    klasse = _tekst(wortel.get("klasse")).replace("_", " ")
    band = _tekst(wortel.get("band_cm"))
    kop_delen = []
    if klasse:
        kop_delen.append(f"**Klasse:** {klasse}")
    if band:
        kop_delen.append(f"**Indicatieve bewortelbare diepte:** {band} cm")
    if kop_delen:
        regels += [" — ".join(kop_delen), ""]

    for veld in ("indicatie", "toelichting"):
        tekst = _alinea(wortel.get(veld))
        if tekst:
            regels += [tekst, ""]
    return regels


def _sectie_doen(data: Dict[str, Any]) -> List[str]:
    regels = ["## Wat kun jij doen", ""]
    vormen = [v for v in (data.get("aanbevolen_beplanting") or []) if isinstance(v, dict)]
    if not vormen:
        regels += [
            "Er konden geen beplantingsvormen worden voorgesteld, omdat er van deze "
            "plek te weinig bekend is. Een houtsingel, een bloemrijke zoom of een "
            "gemengde struweelhaag past in vrijwel elk Nederlands landschap en is "
            "een veilige eerste keuze.",
            "",
        ]
        return regels

    regels += [
        f"Deze {len(vormen)} beplantingsvormen passen bij het landschap en de "
        "omstandigheden van deze plek, op volgorde van hoe goed ze aansluiten.",
        "",
    ]
    for i, vorm in enumerate(vormen, 1):
        naam = _tekst(vorm.get("vorm"), "Beplantingsvorm")
        regels += [f"### {i}. {naam}", ""]
        omschrijving = _alinea(vorm.get("omschrijving"))
        if omschrijving:
            regels += [omschrijving, ""]
        waarom = _alinea(vorm.get("waarom_hier"))
        if waarom:
            regels += [f"**Waarom hier:** {waarom}", ""]
        soorten = _lijst(vorm.get("voorbeeldsoorten"))
        if soorten:
            regels += [f"**Voorbeeldsoorten:** {'; '.join(soorten)}", ""]
    return regels


def _statuszin(statusfilters: Iterable[str]) -> str:
    """Regel die vertelt op welke status (inheems/ingeburgerd/exoot) is gefilterd."""
    labels = [_alinea(s) for s in (statusfilters or []) if _alinea(s)]
    if not labels:
        return ("Toegepast statusfilter: geen — inheemse, ingeburgerde en uitheemse "
                "soorten staan alle in de lijst.")
    if len(labels) == 1:
        opsomming = labels[0]
    else:
        opsomming = ", ".join(labels[:-1]) + " en " + labels[-1]
    return f"Toegepast statusfilter: {opsomming}."


def _sectie_soorten(data: Dict[str, Any], csv_url: str, max_soorten: int,
                    statusfilters: Iterable[str] = ()) -> List[str]:
    regels = ["## Passende soorten", ""]
    rijen = [r for r in (data.get("advies") or []) if isinstance(r, dict)]

    if not rijen:
        regels += [
            "Geen enkele soort uit de Beplantingswijzer-lijst voldeed aan de combinatie "
            "van bodem en vochtklasse van deze plek, in combinatie met de opgegeven "
            "filters. Zet de statusfilters ruimer of raadpleeg de volledige lijst.",
            "",
            _statuszin(statusfilters),
            "",
        ]
        if csv_url:
            regels += [f"Volledige soortenlijst (CSV): {csv_url}", ""]
        return regels

    getoond = rijen[:max_soorten]
    if len(rijen) > len(getoond):
        inleiding = (
            f"{len(rijen)} soorten uit de Beplantingswijzer-lijst passen bij de bodem "
            f"en de vochtklasse van deze plek. Hieronder de eerste {len(getoond)}; "
            "de volledige lijst haal je op als CSV."
        )
    else:
        inleiding = (
            f"{len(rijen)} soorten uit de Beplantingswijzer-lijst passen bij de bodem "
            "en de vochtklasse van deze plek."
        )
    regels += [inleiding, "", _statuszin(statusfilters), ""]

    kop = [label for _sleutel, label in _TABEL_KOLOMMEN]
    tabelrijen = [
        [_cel(rij.get(sleutel), "onbekend") for sleutel, _label in _TABEL_KOLOMMEN]
        for rij in getoond
    ]
    regels += _tabel(kop, tabelrijen)
    regels += [""]
    if csv_url:
        regels += [f"Volledige soortenlijst als CSV: {csv_url}", ""]
    return regels


def _sectie_bronnen(data: Dict[str, Any], basis_url: str, csv_url: str,
                    json_url: str) -> List[str]:
    regels = ["## Bronnen en verantwoording", ""]

    status = data.get("bronnen_status") or {}
    rijen = []
    for sleutel, label in _BRON_LABELS.items():
        waarde = _tekst(status.get(sleutel), "onbekend")
        rijen.append([_cel(label), _cel(waarde), _cel(_STATUS_UITLEG.get(waarde, "geen status"))])
    if rijen:
        regels += ["Status van de geraadpleegde kaartlagen bij deze aanvraag:", ""]
        regels += _tabel(["Bron", "Status", "Betekenis"], rijen)
        regels += [""]

    regels += [
        "De soortenlijst komt uit de Beplantingswijzer-dataset (TreeEbb, aangevuld met de "
        "Nederlandse namen en de status inheems/ingeburgerd/exoot uit de "
        "Standaardlijst 2020).",
        "",
        f"**Disclaimer.** {DISCLAIMER}",
        "",
    ]

    links = []
    if csv_url:
        links.append(f"- Soortenlijst voor deze plek als CSV: {csv_url}")
    if json_url:
        links.append(f"- Ditzelfde advies als JSON: {json_url}")
    if basis_url:
        links.append(f"- Kaart en toelichting op de website: {basis_url}/")
        links.append(f"- Uitleg voor AI-agents en scripts: {basis_url}/llms.txt")
    if links:
        regels += ["Verder:", ""] + links + [""]

    regels += ["Bij overname of citeren graag bronvermelding: Beplantingswijzer.", ""]
    return regels


# ───────────────────── publieke API
def rapport_markdown(
    data: Dict[str, Any],
    *,
    basis_url: str = "",
    csv_url: str = "",
    json_url: str = "",
    max_soorten: int = MAX_SOORTEN,
    statusfilters: Iterable[str] = (),
) -> str:
    """Zet een `/advies/geo`-response om in een volledig Markdown-rapport.

    Args:
        data: het dict dat `/advies/geo` als JSON zou teruggeven.
        basis_url: origin van de server zonder slash, bijv. `https://beplantingswijzer.nl`.
        csv_url: link naar `/export/csv` met dezelfde filters.
        json_url: link naar ditzelfde advies in JSON.
        max_soorten: maximaal aantal rijen in de soortentabel.
        statusfilters: de statussen (inheems/ingeburgerd/exoot) waarop de
            soortenlijst is gefilterd; leeg betekent "niet op status gefilterd".
    """
    basis_url = (basis_url or "").rstrip("/")
    titel = _kop_titel(data)

    regels: List[str] = [
        f"# Beplantingswijzer-advies voor {titel}",
        "",
        "Beplantingsadvies op maat voor één plek in Nederland: hoe dit landschap is "
        "ontstaan, wat de bodem en het grondwater hier doen, welke beplantingsvormen "
        "erbij horen en welke bomen en struiken er passen. Coördinaten in dit rapport "
        "zijn WGS84 (EPSG:4326).",
        "",
    ]
    regels += _sectie_plek(data)
    regels += [""]
    regels += _sectie_landschap(data)
    regels += _sectie_wortelruimte(data)
    regels += _sectie_doen(data)
    regels += _sectie_soorten(data, csv_url, max_soorten, statusfilters)
    regels += _sectie_bronnen(data, basis_url, csv_url, json_url)

    # Dubbele lege regels opruimen zodat de markdown netjes leest.
    uit: List[str] = []
    for regel in regels:
        if regel == "" and uit and uit[-1] == "":
            continue
        uit.append(regel)
    return "\n".join(uit).strip() + "\n"
