# normalize_treeebb_csv.py
# Doel: maak TreeEbb CSV consistent voor de UI door multi-waardes te normaliseren naar " / "
# Gebruik (vanuit de projectroot, met de venv actief):
#   python scripts/normalize_treeebb_csv.py                  # pakt data/treeebb_planten_allfields.csv
#   python scripts/normalize_treeebb_csv.py <pad naar csv>   # of een eigen bestand
# Output:
#   hetzelfde bestand (overschreven) + backup .bak ernaast
#
# Locatie: <projectroot>/scripts/. Een relatief pad-argument wordt eerst t.o.v. de
# huidige map geprobeerd en daarna t.o.v. de projectroot.

import sys, shutil, re, pathlib

SEP_RE = re.compile(r"\s*[|/;]+\s*")

# scripts/normalize_treeebb_csv.py ⇒ één niveau omhoog is de projectroot.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "data" / "treeebb_planten_allfields.csv"


def resolve_path(path_str: str) -> pathlib.Path:
    """Zoek het bestand relatief aan de huidige map en anders aan de projectroot."""
    p = pathlib.Path(path_str)
    if p.exists() or p.is_absolute():
        return p
    alt = PROJECT_ROOT / p
    return alt if alt.exists() else p

def norm_cell(s: str) -> str:
    if s is None:
        return ""
    s = str(s)
    # snelle escape voor lege strings
    if not s.strip():
        return ""
    parts = [p.strip() for p in SEP_RE.split(s) if p.strip()]
    # unique keep order
    out = []
    seen = set()
    for p in parts:
        k = p.lower()
        if k not in seen:
            out.append(p)
            seen.add(k)
    return " / ".join(out)

def main(path_str: str):
    path = resolve_path(path_str)
    if not path.exists():
        print(f"BESTAND NIET GEVONDEN: {path}")
        sys.exit(1)

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    print(f"Backup gemaakt: {backup}")

    # We lezen/wrijven simpel tekstmatig; werkt voor ; of , delim, zolang regels niet kapot zijn.
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not text:
        print("Leeg bestand.")
        sys.exit(1)

    # Bepaal delimiter op header
    header = text[0]
    delim = ";" if header.count(";") >= header.count(",") else ","

    # Kolommen die géén multi-waardelijst zijn en dus niet genormaliseerd mogen
    # worden (een URL bevat '/' en zou anders uit elkaar getrokken worden).
    kop_cellen = header.split(delim)
    skip_idx = {i for i, k in enumerate(kop_cellen) if k.strip().lstrip("﻿").lower() in ("naam", "url")}

    out_lines = [header]
    for line in text[1:]:
        # naive split; ok omdat jouw CSV geen quoted separators gebruikt
        cells = line.split(delim)
        cells2 = [c if i in skip_idx else norm_cell(c) for i, c in enumerate(cells)]
        out_lines.append(delim.join(cells2))

    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Genormaliseerd en opgeslagen: {path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Geen bestand opgegeven — gebruik standaard: {DEFAULT_CSV}")
        main(str(DEFAULT_CSV))
    else:
        main(sys.argv[1])
