#!/usr/bin/env python3
"""
Setup script voor kennisbibliotheek v2 in je Plantwijs project.

Dit script maakt de juiste directory structuur aan.
"""

import os
from pathlib import Path

# Basis pad (je draait dit vanuit je Plantwijs directory)
BASE = Path.cwd()
KB_V2 = BASE / "kennisbibliotheek_v2"

print("\n" + "="*70)
print("KENNISBIBLIOTHEEK V2 SETUP")
print("="*70)
print(f"\nCreëren in: {KB_V2}\n")

# Maak alle directories
dirs_to_create = [
    "lagen/nsn",
    "lagen/bodem", 
    "lagen/gt",
    "lagen/fgr",
    "advies/principes",
    "advies/soorten",
    "advies/templates",
    "scripts",
]

for dir_path in dirs_to_create:
    full_path = KB_V2 / dir_path
    full_path.mkdir(parents=True, exist_ok=True)
    print(f"✅ {dir_path}/")

print("\n" + "="*70)
print("DIRECTORY STRUCTUUR AANGEMAAKT!")
print("="*70)

# Toon de structuur
print("\nJe hebt nu:")
print("""
kennisbibliotheek_v2/
├── lagen/
│   ├── nsn/        ← NSN items komen hier (alleen landvorm)
│   ├── bodem/      ← Bodem items komen hier
│   ├── gt/         ← Gt items komen hier
│   └── fgr/        ← FGR items komen hier
│
├── advies/
│   ├── principes/  ← Herbruikbare ontwerpprincipes
│   ├── soorten/    ← Soorten database
│   └── templates/  ← Tekst templates
│
└── scripts/        ← Python scripts (generator etc.)
""")

print("\n💡 Volgende stap: Templates en scripts kopiëren")
print("="*70 + "\n")
