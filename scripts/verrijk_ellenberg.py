# verrijk_ellenberg.py
# Doel: de gescrapete TreeEbb-CSV verrijken met Ellenberg-indicatorwaarden
# (kolommen ellenberg_l/f/t/n/r/s) uit de Europese dataset van Tichý et al. (2022).
#
# Bron (volledige citatie):
#   Tichý, L., Axmanová, I., Dengler, J., Guarino, R., Jansen, F., Midolo, G.,
#   Nobis, M.P., Van Meerbeek, K., Aćić, S., Attorre, F., Bergmeier, E., ... &
#   Chytrý, M. (2023). Ellenberg-type indicator values for European vascular
#   plant species. Journal of Vegetation Science, 34(1), e13168.
#   https://doi.org/10.1111/jvs.13168
#   Databestand: data/ellenberg_tichy_2022.xlsx (kopie van het gepubliceerde
#   supplement "Ellenbergh_Tichy_et_al 2022-11-29.xlsx").
#
# Draaivolgorde (na elke nieuwe scrape, vanuit de projectroot):
#   1) .venv\Scripts\python.exe scripts\scraper\treeebb_scraper_allfields.py
#   2) .venv\Scripts\python.exe scripts\scraper\verrijk_treeebb_met_sl2020.py
#   3) .venv\Scripts\python.exe scripts\verrijk_ellenberg.py
# Stap 3 is idempotent: bestaande ellenberg_*-kolommen worden overschreven,
# dus het script mag zo vaak herdraaid worden als je wilt.
#
# Locatie: <projectroot>/scripts/. In- en uitvoer staan in <projectroot>/data/;
# het script bepaalt de projectroot zelf, dus het werkt vanuit elke map.

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

# --- PADEN ---
# Dit bestand staat in <projectroot>/scripts/ ⇒ één niveau omhoog is de projectroot.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
TREEEBB_PATH = DATA_DIR / "treeebb_planten_allfields.csv"

# Ellenberg staat normaal in data/; valt terug op de map bóven het project (oude plek).
ELLENBERG_NAAM = "ellenberg_tichy_2022.xlsx"
ELLENBERG_KANDIDATEN = [
    DATA_DIR / ELLENBERG_NAAM,
    PROJECT_ROOT.parent / ELLENBERG_NAAM,
    PROJECT_ROOT.parent / "Ellenbergh_Tichy_et_al 2022-11-29 (1).xlsx",
]
ELLENBERG_PATH = next((p for p in ELLENBERG_KANDIDATEN if p.exists()), ELLENBERG_KANDIDATEN[0])

# --- SHEET / KOLOMMEN ---
# Het blad Tab-IVs-Tichy-et-al2022 bevat per soort de definitieve (gemiddelde)
# indicatorwaarden voor alle zes factoren. Kop staat over twee rijen:
#   rij 1: (leeg) (leeg) LIGHT TEMPERATURE MOISTURE REACTION NUTRIENTS SALINITY
#   rij 2: SeqID  Taxon  Average Average   Average  Average   Average   Average
# Data begint op rij 3.
ELLENBERG_SHEET = "Tab-IVs-Tichy-et-al2022"

# Ellenberg-factor → kolomnaam in de dataset. Let op: Moisture heet in de app
# `ellenberg_f` (Feuchtigkeit), conform de klassieke Ellenberg-notatie L/T/F/R/N/S.
FACTOR_KOLOM = {
    "LIGHT": "ellenberg_l",
    "MOISTURE": "ellenberg_f",
    "TEMPERATURE": "ellenberg_t",
    "NUTRIENTS": "ellenberg_n",
    "REACTION": "ellenberg_r",
    "SALINITY": "ellenberg_s",
}
KOLOMMEN = ["ellenberg_l", "ellenberg_f", "ellenberg_t", "ellenberg_n", "ellenberg_r", "ellenberg_s"]

# CSV-instellingen: de TreeEbb-CSV is kommagescheiden en heeft een UTF-8 BOM.
CSV_SEP = ","
CSV_ENCODING = "utf-8-sig"


# --- HULPFUNCTIES ---
def norm_naam(naam: object) -> str:
    """Normaliseer een wetenschappelijke naam voor vergelijking.

    Lowercase, hybride-kruisje × → " x ", nette aanhalingstekens → ', en
    dubbele spaties weg. Zelfde aanpak als plantwijs/services/dataset.py.
    """
    t = str(naam or "")
    t = t.replace("×", " x ").replace("’", "'").replace("‘", "'")
    return " ".join(t.strip().lower().split())


def kern_tokens(genormaliseerd: str) -> list:
    """Tokens tot aan de cultivar: "quercus robur 'fastigiata'" → [quercus, robur]."""
    tokens = genormaliseerd.split()
    for i, t in enumerate(tokens):
        if t.startswith("'"):
            return tokens[:i]
    return tokens


def basis_kandidaten(genormaliseerd: str) -> list:
    """Geslacht + soort uit een genormaliseerde naam, hybride-notatie in beide vormen.

    "populus x canescens 'de moffart'" → ["populus x canescens", "populus canescens"]
    "quercus robur 'fastigiata'"       → ["quercus robur", "quercus x robur"]
    """
    kern = kern_tokens(genormaliseerd)
    if len(kern) >= 3 and kern[1] == "x":
        return [f"{kern[0]} x {kern[2]}", f"{kern[0]} {kern[2]}"]
    if len(kern) >= 2:
        return [f"{kern[0]} {kern[1]}", f"{kern[0]} x {kern[1]}"]
    return []


def format_waarde(waarde: object) -> str:
    """Indicatorwaarde → tekst met 1 decimaal; leeg bij 'x' (indifferent) of NA."""
    if waarde is None:
        return ""
    tekst = str(waarde).strip()
    if tekst == "" or tekst.lower() in ("x", "na", "nan", "none"):
        return ""
    try:
        return f"{float(tekst.replace(',', '.')):.1f}"
    except ValueError:
        return ""


def lees_ellenberg(path: Path) -> pd.DataFrame:
    """Lees het blad met de definitieve indicatorwaarden; kolommen: taxon + KOLOMMEN."""
    xl = pd.ExcelFile(path, engine="openpyxl")
    sheets = xl.sheet_names
    sheet = ELLENBERG_SHEET
    if sheet not in sheets:
        sheet = next((s for s in sheets if "iv" in s.lower() and "tab" in s.lower()), "")
        if not sheet:
            print(f"Blad '{ELLENBERG_SHEET}' niet gevonden. Beschikbaar: {', '.join(sheets)}")
            sys.exit(1)
        print(f"Let op: blad '{ELLENBERG_SHEET}' ontbreekt, '{sheet}' gebruikt.")
    print(f"Ellenberg-blad: '{sheet}' (van {len(sheets)} bladen)")

    ruw = xl.parse(sheet, header=None, dtype=object)

    # Kop over twee rijen: rij 0 = factornamen, rij 1 = 'SeqID'/'Taxon'/'Average'.
    factor_rij = [str(v).strip().upper() if v is not None else "" for v in ruw.iloc[0].tolist()]
    label_rij = [str(v).strip().lower() if v is not None else "" for v in ruw.iloc[1].tolist()]

    try:
        taxon_idx = label_rij.index("taxon")
    except ValueError:
        print("Kolom 'Taxon' niet gevonden in de kop van het Ellenberg-blad.")
        sys.exit(1)

    factor_idx = {}
    for i, factor in enumerate(factor_rij):
        if factor in FACTOR_KOLOM and factor not in factor_idx:
            factor_idx[factor] = i
    ontbreekt = [f for f in FACTOR_KOLOM if f not in factor_idx]
    if ontbreekt:
        print(f"Ontbrekende factorkolommen in het Ellenberg-blad: {', '.join(ontbreekt)}")
        sys.exit(1)

    data = ruw.iloc[2:].reset_index(drop=True)
    uit = pd.DataFrame({"taxon": data.iloc[:, taxon_idx].astype(str)})
    for factor, kolom in FACTOR_KOLOM.items():
        uit[kolom] = data.iloc[:, factor_idx[factor]].map(format_waarde)
    uit = uit[uit["taxon"].str.strip().ne("") & uit["taxon"].str.lower().ne("nan")]
    print(f"Ellenberg-soorten ingelezen: {len(uit)}")
    return uit


def bouw_index(ellenberg: pd.DataFrame) -> tuple:
    """Bouw twee lookups: exact op volledige naam, en op geslacht+soort-basis.

    Aggregaten ("Quercus petraea aggr.") komen alleen in de basis-lookup terecht
    als er geen gewone soort met dezelfde basis is.
    """
    exact = {}
    basis = {}
    rijen = []
    for rij in ellenberg.itertuples(index=False):
        waarden = {k: getattr(rij, k) for k in KOLOMMEN}
        if not any(waarden.values()):
            continue  # soort zonder enige waarde levert niets op
        genorm = norm_naam(rij.taxon)
        if not genorm:
            continue
        exact.setdefault(genorm, waarden)
        rijen.append((genorm, waarden))

    # Eerst gewone soorten, daarna aggregaten (die mogen alleen gaten vullen).
    for is_aggr in (False, True):
        for genorm, waarden in rijen:
            if ("aggr." in genorm) != is_aggr:
                continue
            for kandidaat in basis_kandidaten(genorm):
                basis.setdefault(kandidaat, waarden)

    print(f"Lookup opgebouwd: {len(exact)} exacte namen, {len(basis)} basisnamen")
    return exact, basis


def verrijk(treeebb: pd.DataFrame, exact: dict, basis: dict) -> dict:
    """Vul de ellenberg_*-kolommen; geeft de matchtelling per strategie terug."""
    kolomwaarden = {k: [] for k in KOLOMMEN}
    strategieen = []

    for naam in treeebb["naam"].fillna("").astype(str):
        genorm = norm_naam(naam)
        waarden = exact.get(genorm)
        strategie = "exact" if waarden else ""
        if not waarden:
            for kandidaat in basis_kandidaten(genorm):
                waarden = basis.get(kandidaat)
                if waarden:
                    strategie = "basis"
                    break
        for kolom in KOLOMMEN:
            kolomwaarden[kolom].append(waarden.get(kolom, "") if waarden else "")
        strategieen.append(strategie)

    for kolom in KOLOMMEN:
        treeebb[kolom] = kolomwaarden[kolom]

    treeebb["_ellenberg_strategie"] = strategieen
    return {
        "exact": strategieen.count("exact"),
        "basis": strategieen.count("basis"),
        "geen": strategieen.count(""),
    }


def rapport(treeebb: pd.DataFrame, telling: dict) -> None:
    """Print het dekkingsrapport (totaal, per strategie, inheemse subset)."""
    totaal = len(treeebb)
    gematcht = telling["exact"] + telling["basis"]

    def pct(n: int, noemer: int) -> str:
        return f"{(100.0 * n / noemer):.1f}%" if noemer else "n.v.t."

    print("")
    print("--- DEKKING ---")
    print(f"Rijen in TreeEbb          : {totaal}")
    print(f"Gematcht op Ellenberg     : {gematcht} ({pct(gematcht, totaal)})")
    print(f"  - exacte naam           : {telling['exact']} ({pct(telling['exact'], totaal)})")
    print(f"  - geslacht+soort-basis  : {telling['basis']} ({pct(telling['basis'], totaal)})")
    print(f"Geen match                : {telling['geen']} ({pct(telling['geen'], totaal)})")

    for kolom in KOLOMMEN:
        gevuld = int((treeebb[kolom].astype(str) != "").sum())
        print(f"  {kolom:<12}: {gevuld} gevuld ({pct(gevuld, totaal)})")

    if "status_nl" in treeebb.columns:
        inheems = treeebb[treeebb["status_nl"].astype(str).str.strip() == "inheems"]
        if len(inheems):
            raak = int((inheems["_ellenberg_strategie"] != "").sum())
            vocht = int((inheems["ellenberg_f"].astype(str) != "").sum())
            print(f"Inheemse soorten (SL2020) : {raak}/{len(inheems)} gematcht "
                  f"({pct(raak, len(inheems))}), ellenberg_f gevuld: {vocht}")
        else:
            print("Inheemse soorten (SL2020) : geen — draai eerst verrijk_treeebb_met_sl2020.py")
    else:
        print("Kolom status_nl ontbreekt — draai eerst verrijk_treeebb_met_sl2020.py")

    zonder = treeebb.loc[treeebb["_ellenberg_strategie"] == "", "naam"].head(5).tolist()
    if zonder:
        print(f"Voorbeelden zonder match  : {'; '.join(str(n) for n in zonder)}")


def schrijf_csv(treeebb: pd.DataFrame, path: Path) -> None:
    """Schrijf de CSV atomair terug (zelfde separator en encoding)."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    os.close(fd)
    try:
        treeebb.to_csv(tmp, index=False, sep=CSV_SEP, encoding=CSV_ENCODING)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main() -> None:
    if not TREEEBB_PATH.exists():
        print(f"TreeEbb-CSV niet gevonden: {TREEEBB_PATH}")
        print("Draai eerst scripts/scraper/treeebb_scraper_allfields.py.")
        sys.exit(1)
    if not ELLENBERG_PATH.exists():
        print("Ellenberg-bestand niet gevonden. Gezocht op:")
        for p in ELLENBERG_KANDIDATEN:
            print(f"  - {p}")
        sys.exit(1)

    print(f"Projectroot: {PROJECT_ROOT}")
    print(f"Ellenberg  : {ELLENBERG_PATH}")
    print("Inlezen Ellenberg (Tichý et al. 2022)...")
    ellenberg = lees_ellenberg(ELLENBERG_PATH)
    exact, basis = bouw_index(ellenberg)

    # De scraper kan de CSV tijdens deze run overschrijven; dan opnieuw proberen.
    for poging in range(1, 4):
        mtime_voor = TREEEBB_PATH.stat().st_mtime
        print(f"Inlezen TreeEbb... (poging {poging})")
        treeebb = pd.read_csv(
            TREEEBB_PATH, sep=CSV_SEP, dtype=str, keep_default_na=False, encoding=CSV_ENCODING
        )
        if "naam" not in treeebb.columns:
            print(f"Kolom 'naam' ontbreekt in {TREEEBB_PATH}. Gevonden: {list(treeebb.columns)[:5]}")
            sys.exit(1)
        print(f"TreeEbb ingelezen: {len(treeebb)} rijen, {treeebb.shape[1]} kolommen")

        telling = verrijk(treeebb, exact, basis)
        rapport(treeebb, telling)
        treeebb = treeebb.drop(columns=["_ellenberg_strategie"])

        if TREEEBB_PATH.stat().st_mtime != mtime_voor:
            print("")
            print("LET OP: de TreeEbb-CSV is tijdens deze run van buitenaf gewijzigd "
                  "(waarschijnlijk de scraper). Verrijking wordt opnieuw gedaan.")
            continue

        schrijf_csv(treeebb, TREEEBB_PATH)
        print("")
        print(f"Klaar. CSV verrijkt en opgeslagen: {TREEEBB_PATH}")
        return

    print("Gestopt: de TreeEbb-CSV bleef tijdens elke poging veranderen. "
          "Draai dit script opnieuw als de scraper klaar is.")
    sys.exit(1)


if __name__ == "__main__":
    main()
