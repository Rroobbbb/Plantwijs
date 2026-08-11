# verrijk_treeebb_met_sl2020.py
# Doel: de gescrapete TreeEbb-CSV verrijken met herkomstgegevens uit de
# Standaardlijst van de Nederlandse Flora 2020 (SL2020, onderdeel van het
# Nederlands Soortenregister). Vult drie kolommen:
#   - nsr_status   : de SL2020-statuscode voor vóórkomen (1a/1b/2a/2b)
#   - status_nl    : inheems / ingeburgerd / exoot (afgeleid van nsr_status)
#   - indigeniteit : oorspronkelijk inheems / archeofyt / neofyt
#                    (afgeleid van de SL2020-kolom Indigeniteit)
#
# status_nl en indigeniteit zijn twee onafhankelijke assen. status_nl gaat over
# vóórkomen (NSRstatus: is de soort hier ingeburgerd?); indigeniteit over
# herkomst (kwam de soort hier op eigen kracht = inheems, vóór 1500 met de mens
# mee = archeofyt, of later = neofyt?). Een soort kan dus tegelijk 'ingeburgerd'
# en 'archeofyt' zijn. NSRstatus 1a ("native") bundelt inheems én archeofyt én
# een aantal neofyten; daarom is indigeniteit een aparte kolom en niet uit
# status_nl af te leiden. Codes: zie de "Introduction"-sheet van SL2020.
#
# Gebruik (vanuit de projectroot, met de venv actief):
#   python scripts/scraper/verrijk_treeebb_met_sl2020.py
#
# Locatie: <projectroot>/scripts/scraper/. In- en uitvoer staan in <projectroot>/data/;
# het script bepaalt de projectroot zelf, dus het werkt vanuit elke map.

import re
import sys
import shutil
from collections import Counter
from pathlib import Path

import pandas as pd

# --- PADEN ---
# Dit bestand staat in <projectroot>/scripts/scraper/ ⇒ twee niveaus omhoog is de projectroot.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
TREEEBB_PATH = DATA_DIR / "treeebb_planten_allfields.csv"

# SL2020 staat normaal in data/; valt terug op de map bóven het project (oude plek).
SL2020_NAAM = "SL2020 Checklist Flora NL.xlsx"
SL2020_KANDIDATEN = [DATA_DIR / SL2020_NAAM, PROJECT_ROOT.parent / SL2020_NAAM]
SL2020_PATH = next((p for p in SL2020_KANDIDATEN if p.exists()), SL2020_KANDIDATEN[0])

if not TREEEBB_PATH.exists():
    print(f"TreeEbb-CSV niet gevonden: {TREEEBB_PATH}")
    print("Draai eerst scripts/scraper/treeebb_scraper_allfields.py.")
    sys.exit(1)
if not SL2020_PATH.exists():
    print("SL2020-bestand niet gevonden. Gezocht op:")
    for p in SL2020_KANDIDATEN:
        print(f"  - {p}")
    sys.exit(1)

# --- BACKUP ---
backup_path = TREEEBB_PATH.with_suffix(".csv.bak")
shutil.copy2(TREEEBB_PATH, backup_path)
print(f"Backup gemaakt: {backup_path}")

# --- HULPFUNCTIES ---
def is_pure_species(name: str) -> bool:
    """
    Alleen genus + soort toestaan.
    Alles met cultivar, cv., quotes of hybriden uitsluiten.
    """
    if not isinstance(name, str):
        return False

    name = name.strip()

    if any(x in name for x in ["'", "’", "cv.", "CV.", "×", " x "]):
        return False

    parts = name.split()
    return len(parts) == 2


def status_nl_from_nsr(nsr: str) -> str:
    """SL2020 NSRstatus → tool-statusbucket (inheems / ingeburgerd / exoot).

    Dit is een ADVIES-indeling voor de tool, geen zuiver taxonomische. SL2020:
    1a = native, 1b = binnen inheems areaal/incidenteel, 2a = >100 jaar
    ingeburgerd, 2b = 10-100 jaar ingeburgerd.

    2a → ingeburgerd (langdurig deel van de wilde flora). 2b → exoot: dit zijn in
    deze dataset uitsluitend sier- en bosbouwexoten (o.a. hemelboom, vlinderstruik,
    rimpelroos, Japanse berberis — deels invasief), die de tool bewust buiten de
    standaardselectie houdt. Het taxonomische feit dat ze recent zijn ingeburgerd,
    staat in de kolom `indigeniteit` (neofyt); status_nl dient het planteradvies.
    Wijzig 2b dus niet naar 'ingeburgerd' zonder de default-weergave te herzien.
    """
    if nsr in ("1a", "1b"):
        return "inheems"
    if nsr == "2a":
        return "ingeburgerd"
    if nsr == "2b":
        return "exoot"
    return ""


def indigeniteit_nl(code: str) -> str:
    """SL2020-indigeniteitscode → leesbare herkomststatus.

    i  → oorspronkelijk inheems (op eigen kracht hier gekomen)
    ci → oorspronkelijk inheems (wilde populaties uitgestorven, wel ingeburgerd)
    a  → archeofyt (vóór 1500 met de mens meegekomen)
    16..21.1 → neofyt (na 1500 ingeburgerd, per eeuw/periode)
    onbekend/leeg → ""
    """
    c = str(code or "").strip().lower()
    if c in ("i", "ci"):
        return "oorspronkelijk inheems"
    if c == "a":
        return "archeofyt"
    if re.match(r"^\d+(?:\.\d+)?$", c):
        return "neofyt"
    return ""


# TreeEbb-soorten die in SL2020 niet onder hun binomen staan, maar onder een
# aggregaat- (subsectie-) of synoniemnaam. Zonder deze koppeling missen ze hun
# (inheemse) status, want verder matchen we exact op de wetenschappelijke naam.
# Alle drie staan in SL2020 als indigeniteit 'i' (oorspronkelijk inheems). Bron:
# Standaardlijst Nederlandse Flora 2020 (NSR).
#   hondsroos   Rosa canina          → Rosa subsect. Caninae   (Hondsrozen-groep)
#   egelantier  Rosa rubiginosa      → Rosa subsect. Rubigineae (Egelantierrozen-groep)
#   duinroos    Rosa pimpinellifolia → Rosa spinosissima        (synoniem)
SL2020_ALIASES = {
    "Rosa canina": "Rosa subsect. Caninae",
    "Rosa rubiginosa": "Rosa subsect. Rubigineae",
    "Rosa pimpinellifolia": "Rosa spinosissima",
}


# --- INLEZEN ---
# dtype=str + keep_default_na=False + utf-8-sig: lees de CSV karakter-voor-karakter
# getrouw in, zodat alle niet-doelkolommen (o.a. ellenberg_*, hoogte) ongewijzigd
# terugkomen en alleen nsr_status/status_nl/indigeniteit veranderen.
print("Inlezen TreeEbb...")
treeebb = pd.read_csv(
    TREEEBB_PATH,
    sep=",",
    dtype=str,
    keep_default_na=False,
    encoding="utf-8-sig",
)

print("Inlezen SL2020...")
sl2020 = pd.read_excel(
    SL2020_PATH,
    sheet_name="SL2020",
    dtype=str,
)

# --- SL2020 KOLOMNAMEN NORMALISEREN ---
sl2020.columns = (
    sl2020.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
    .str.replace("-", "_")
)

SL_NAME_COL = "wetenschappelijke_naam"
NSR_COL = "nsrstatus"
INDIG_COL = "indigeniteit"

# --- SL2020 VOORBEREIDEN ---
# Lookup over ÁLLE SL2020-rijen (dus ook aggregaten als "Rosa subsect. Caninae"),
# zodat de alias-map ze kan bereiken. Waarde = (nsrstatus, indigeniteit); bij
# dubbele namen wint de eerste. Op de TreeEbb-kant filtert is_pure_species nog
# steeds cultivars/hybriden uit, dus een aggregaatnaam matcht nooit per ongeluk.
sl2020[SL_NAME_COL] = sl2020[SL_NAME_COL].astype(str).str.strip()

sl2020_lookup: dict[str, tuple[str, str]] = {}
for _, _row in sl2020.iterrows():
    _key = str(_row[SL_NAME_COL]).strip()
    if not _key or _key in sl2020_lookup:
        continue
    sl2020_lookup[_key] = (
        str(_row[NSR_COL]).strip(),
        str(_row[INDIG_COL]).strip(),
    )

print(f"SL2020 rijen beschikbaar voor matching: {len(sl2020_lookup)}")

# --- TREEEBB: wetenschappelijke naam = EERSTE KOLOM ---
TREEEBB_NAME_COL = treeebb.columns[0]
print(f"TreeEbb naamkolom gebruikt: {TREEEBB_NAME_COL}")

# --- MATCHEN ---
# Volgorde per TreeEbb-rij: expliciete alias → exact binomen → geen match.
nsr_values = []
status_values = []
indig_values = []
matched = 0

for name in treeebb[TREEEBB_NAME_COL]:
    hit = None
    if name in SL2020_ALIASES:
        hit = sl2020_lookup.get(SL2020_ALIASES[name])
    elif is_pure_species(name) and name in sl2020_lookup:
        hit = sl2020_lookup[name]

    if hit is not None:
        nsr, indig = hit
        nsr_values.append(nsr)
        status_values.append(status_nl_from_nsr(nsr))
        indig_values.append(indigeniteit_nl(indig))
        matched += 1
    else:
        nsr_values.append("")
        status_values.append("")
        indig_values.append("")

treeebb["nsr_status"] = nsr_values
treeebb["status_nl"] = status_values
treeebb["indigeniteit"] = indig_values

# --- OPSLAAN ---
# Zelfde vorm als ingelezen: UTF-8 met BOM (Excel toont "Löss" e.d. correct) en
# CRLF-regeleindes, zodat de diff beperkt blijft tot de drie doelkolommen.
treeebb.to_csv(TREEEBB_PATH, index=False, encoding="utf-8-sig", lineterminator="\r\n")

print(f"Klaar. Gematchte soorten: {matched} van {len(treeebb)}")
_status = Counter(v for v in status_values if v)
_indig = Counter(v for v in indig_values if v)
print("  status_nl : " + ", ".join(f"{k}={v}" for k, v in _status.most_common()))
print("  indigeniteit: " + ", ".join(f"{k}={v}" for k, v in _indig.most_common()))
print("CSV is verrijkt en opgeslagen.")
