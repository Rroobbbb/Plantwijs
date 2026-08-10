# verrijk_treeebb_met_sl2020.py
# Doel: de gescrapete TreeEbb-CSV verrijken met de NSR-status uit de Standaardlijst
# van de Nederlandse Flora 2020 (kolommen `nsr_status` en `status_nl`).
#
# Gebruik (vanuit de projectroot, met de venv actief):
#   python scripts/scraper/verrijk_treeebb_met_sl2020.py
#
# Locatie: <projectroot>/scripts/scraper/. In- en uitvoer staan in <projectroot>/data/;
# het script bepaalt de projectroot zelf, dus het werkt vanuit elke map.

import sys
import pandas as pd
import shutil
from pathlib import Path

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
    if nsr in ("1a", "1b"):
        return "inheems"
    if nsr == "2a":
        return "ingeburgerd"
    if nsr == "2b":
        return "exoot"
    return ""


# --- INLEZEN ---
print("Inlezen TreeEbb...")
treeebb = pd.read_csv(
    TREEEBB_PATH,
    sep=None,
    engine="python"
)

print("Inlezen SL2020...")
sl2020 = pd.read_excel(
    SL2020_PATH,
    sheet_name="SL2020"
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

# --- SL2020 VOORBEREIDEN ---
sl2020[SL_NAME_COL] = sl2020[SL_NAME_COL].astype(str).str.strip()
sl2020 = sl2020[sl2020[SL_NAME_COL].apply(is_pure_species)]

sl2020_lookup = (
    sl2020
    .set_index(SL_NAME_COL)[NSR_COL]
    .astype(str)
    .str.strip()
    .to_dict()
)

print(f"SL2020 soorten beschikbaar voor matching: {len(sl2020_lookup)}")

# --- TREEEBB: wetenschappelijke naam = EERSTE KOLOM ---
TREEEBB_NAME_COL = treeebb.columns[0]
print(f"TreeEbb naamkolom gebruikt: {TREEEBB_NAME_COL}")

# --- MATCHEN ---
nsr_values = []
status_values = []
matched = 0

for name in treeebb[TREEEBB_NAME_COL]:
    if is_pure_species(name) and name in sl2020_lookup:
        nsr = sl2020_lookup[name]
        nsr_values.append(nsr)
        status_values.append(status_nl_from_nsr(nsr))
        matched += 1
    else:
        nsr_values.append("")
        status_values.append("")

treeebb["nsr_status"] = nsr_values
treeebb["status_nl"] = status_values

# --- OPSLAAN ---
treeebb.to_csv(TREEEBB_PATH, index=False)
print(f"Klaar. Gematchte soorten: {matched} van {len(treeebb)}")
print("CSV is verrijkt en opgeslagen.")
