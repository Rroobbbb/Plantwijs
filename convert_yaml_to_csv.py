#!/usr/bin/env python3
"""
YAML Soorten → CSV Converter voor PlantWijs

Dit script converteert de 64 inheemse soorten YAML bestanden
naar een CSV die de API kan gebruiken voor PDF generatie.

Gebruik:
    python convert_yaml_to_csv.py <yaml_folder> <output_csv>
    
Voorbeeld:
    python convert_yaml_to_csv.py kennisbibliotheek_v2/advies/soorten/inheems/ data/inheemse_soorten.csv
"""

import csv
import os
import sys
from pathlib import Path

# Probeer PyYAML te importeren
try:
    import yaml
except ImportError:
    print("PyYAML niet geïnstalleerd. Installeer met: pip install pyyaml")
    sys.exit(1)


def safe_get(d, *keys, default=""):
    """Veilig nested dictionary waarde ophalen."""
    result = d
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result if result is not None else default


def list_to_str(val, sep=" / "):
    """Converteer lijst naar string."""
    if isinstance(val, list):
        return sep.join(str(v) for v in val if v)
    return str(val) if val else ""


def parse_yaml_soort(filepath):
    """Parse een YAML soort bestand naar een platte dictionary."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        if not data:
            return None
        
        # ============================================================
        # MAPPING: YAML structuur → CSV kolommen
        # ============================================================
        
        row = {}
        
        # Basis info
        row['naam'] = safe_get(data, 'titel')
        row['wetenschappelijke_naam'] = safe_get(data, 'wetenschappelijke_naam')
        row['familie'] = safe_get(data, 'familie')
        
        # Type (boom/struik/etc)
        soort_type = safe_get(data, 'type', default='')
        row['type'] = soort_type
        
        # Bepaal beplantingstype op basis van type en hoogte
        hoogte_range = safe_get(data, 'groei', 'hoogte_range', default={})
        hoogte_max = hoogte_range.get('max', 0) if isinstance(hoogte_range, dict) else 0
        
        if soort_type.lower() in ['boom', 'tree']:
            row['beplantingstype'] = 'Boom'
            row['beplantingstypes_boomtypen'] = 'hoogstam bomen'
            row['beplantingstypes_overige_beplanting'] = ''
        elif soort_type.lower() in ['struik', 'heester', 'shrub']:
            if hoogte_max and hoogte_max < 1:
                row['beplantingstype'] = 'Bodembedekker'
            else:
                row['beplantingstype'] = 'Heester'
            row['beplantingstypes_boomtypen'] = ''
            row['beplantingstypes_overige_beplanting'] = 'solitair heesters'
        elif soort_type.lower() in ['klimplant', 'klimmer']:
            row['beplantingstype'] = 'Klimplant'
            row['beplantingstypes_boomtypen'] = ''
            row['beplantingstypes_overige_beplanting'] = 'klimplanten'
        else:
            # Fallback op hoogte
            if hoogte_max:
                if hoogte_max >= 6:
                    row['beplantingstype'] = 'Boom'
                    row['beplantingstypes_boomtypen'] = 'hoogstam bomen'
                    row['beplantingstypes_overige_beplanting'] = ''
                elif hoogte_max >= 1:
                    row['beplantingstype'] = 'Heester'
                    row['beplantingstypes_boomtypen'] = ''
                    row['beplantingstypes_overige_beplanting'] = 'solitair heesters'
                else:
                    row['beplantingstype'] = 'Bodembedekker'
                    row['beplantingstypes_boomtypen'] = ''
                    row['beplantingstypes_overige_beplanting'] = 'bodembedekkers'
            else:
                row['beplantingstype'] = 'Onbekend'
                row['beplantingstypes_boomtypen'] = ''
                row['beplantingstypes_overige_beplanting'] = ''
        
        # Inheems status
        inheems_data = safe_get(data, 'inheems', default={})
        row['status_nl'] = safe_get(inheems_data, 'status_nl', default='inheems')
        row['nsr_status'] = safe_get(inheems_data, 'nsr_status', default='')
        row['inheems'] = 'ja' if row['status_nl'].lower() == 'inheems' else 'nee'
        row['invasief'] = 'nee'  # Alle 64 soorten zijn niet-invasief
        
        # ============================================================
        # STANDPLAATS (cruciaal voor filtering!)
        # ============================================================
        standplaats = safe_get(data, 'standplaats', default={})
        
        # Vocht - afgeleid uit tolerantie scores
        droogte_score = standplaats.get('droogte_tolerantie_score', 5)
        nattigheid_score = standplaats.get('nattigheid_tolerantie_score', 5)
        
        # Converteer scores naar vocht labels
        vocht_labels = []
        if droogte_score and droogte_score >= 7:
            vocht_labels.append('zeer droog')
        if droogte_score and droogte_score >= 5:
            vocht_labels.append('droog')
        vocht_labels.append('vochtig')  # Bijna alle planten
        if nattigheid_score and nattigheid_score >= 6:
            vocht_labels.append('nat')
        if nattigheid_score and nattigheid_score >= 8:
            vocht_labels.append('zeer nat')
        
        row['vocht'] = ' / '.join(vocht_labels)
        row['standplaats_bodemvochtigheid'] = row['vocht']
        
        # Licht
        licht = standplaats.get('licht', [])
        row['standplaats_licht'] = list_to_str(licht)
        row['licht'] = row['standplaats_licht']
        
        # Bodem/Grondsoort
        bodem_voorkeur = standplaats.get('bodemtype_voorkeur', {})
        if isinstance(bodem_voorkeur, dict):
            bodem_types = bodem_voorkeur.get('types', [])
        else:
            bodem_types = []
        row['grondsoorten'] = list_to_str(bodem_types)
        row['standplaats_grondsoort'] = row['grondsoorten']
        
        # Bepaal basis bodemtype voor filtering
        bodem_str = row['grondsoorten'].lower()
        basis_bodem = []
        if 'klei' in bodem_str or 'zavel' in bodem_str:
            basis_bodem.append('klei')
        if 'zand' in bodem_str:
            basis_bodem.append('zand')
        if 'veen' in bodem_str:
            basis_bodem.append('veen')
        if 'leem' in bodem_str or 'löss' in bodem_str or 'loss' in bodem_str:
            basis_bodem.append('leem')
        if 'alle grondsoorten' in bodem_str:
            basis_bodem = ['klei', 'zand', 'veen', 'leem']
        row['bodem'] = ' / '.join(basis_bodem) if basis_bodem else 'alle'
        
        # pH
        ph = standplaats.get('pH_voorkeur', [])
        row['ph_waarde'] = list_to_str(ph)
        row['standplaats_ph_waarde'] = row['ph_waarde']
        
        # Voedselrijkdom
        voedsel = standplaats.get('voedsel_behoefte', [])
        row['voedselrijkdom'] = list_to_str(voedsel)
        row['standplaats_voedselrijkdom'] = row['voedselrijkdom']
        
        # Wind
        wind = standplaats.get('wind_tolerantie', '')
        row['wind'] = wind if isinstance(wind, str) else list_to_str(wind)
        row['standplaats_wind'] = row['wind']
        
        # Extreme condities
        extreme = standplaats.get('extreme_condities', [])
        row['extreme_condities'] = list_to_str(extreme)
        row['standplaats_extreme_condities'] = row['extreme_condities']
        
        # ============================================================
        # GROEI EIGENSCHAPPEN
        # ============================================================
        groei = safe_get(data, 'groei', default={})
        
        row['hoogte'] = safe_get(groei, 'hoogte', default='')
        row['eigenschappen_hoogte'] = row['hoogte']
        
        row['breedte'] = safe_get(groei, 'breedte', default='')
        row['eigenschappen_breedte'] = row['breedte']
        
        row['kroonvorm'] = safe_get(groei, 'kroonvorm', default='')
        row['eigenschappen_kroonvorm'] = row['kroonvorm']
        
        row['kroonstructuur'] = safe_get(groei, 'kroonstructuur', default='')
        row['eigenschappen_kroonstructuur'] = row['kroonstructuur']
        
        row['winterhardheidszone'] = safe_get(groei, 'winterhardheid', default='')
        row['eigenschappen_winterhardheidszone'] = row['winterhardheidszone']
        
        # ============================================================
        # ECOLOGISCHE WAARDE
        # ============================================================
        eco = safe_get(data, 'ecologische_waarde', default={})
        
        biodiv = eco.get('biodiversiteit_treeebb', [])
        row['biodiversiteit'] = list_to_str(biodiv)
        row['standplaats_biodiversiteit'] = row['biodiversiteit']
        
        row['ecowaarde'] = safe_get(eco, 'score', default='')
        row['eco_insecten'] = safe_get(eco, 'insecten', default='')
        row['eco_vogels'] = safe_get(eco, 'vogels', default='')
        
        # ============================================================
        # PRAKTISCH / TOEPASSINGEN
        # ============================================================
        praktisch = safe_get(data, 'praktisch', default={})
        
        toepassingen = praktisch.get('toepassingen', [])
        row['locatie'] = list_to_str(toepassingen)
        row['toepassing_locatie'] = row['locatie']
        
        verharding = praktisch.get('verharding_tolerantie', [])
        row['verharding'] = list_to_str(verharding)
        row['toepassing_verharding'] = row['verharding']
        
        # Functie/beschrijving
        row['functie'] = safe_get(data, 'functie', default='')
        
        # ============================================================
        # BRON
        # ============================================================
        bron = safe_get(data, 'bron', default={})
        row['url'] = safe_get(bron, 'url', default='')
        
        return row
        
    except Exception as e:
        print(f"  ⚠️ Fout bij {filepath}: {e}")
        return None


def convert_folder_to_csv(yaml_folder, output_csv):
    """Converteer alle YAML bestanden in een folder naar één CSV."""
    
    yaml_folder = Path(yaml_folder)
    output_csv = Path(output_csv)
    
    print("\n" + "=" * 70)
    print("YAML → CSV CONVERTER voor PlantWijs")
    print("=" * 70)
    print(f"\nBron:   {yaml_folder}")
    print(f"Output: {output_csv}\n")
    
    # Vind alle YAML bestanden
    yaml_files = list(yaml_folder.glob("*.yaml")) + list(yaml_folder.glob("*.yml"))
    
    if not yaml_files:
        print("❌ Geen YAML bestanden gevonden!")
        return False
    
    print(f"📁 Gevonden: {len(yaml_files)} YAML bestanden\n")
    
    # Parse alle bestanden
    rows = []
    success = 0
    failed = 0
    
    for yf in sorted(yaml_files):
        row = parse_yaml_soort(yf)
        if row:
            rows.append(row)
            success += 1
            print(f"  ✅ {yf.stem}: {row.get('naam', '?')} ({row.get('beplantingstype', '?')})")
        else:
            failed += 1
            print(f"  ❌ {yf.stem}: kon niet worden geparsed")
    
    if not rows:
        print("\n❌ Geen valide soorten gevonden!")
        return False
    
    # Bepaal alle kolommen (union van alle rows)
    all_columns = set()
    for row in rows:
        all_columns.update(row.keys())
    
    # Sorteer kolommen logisch
    priority_cols = [
        'naam', 'wetenschappelijke_naam', 'type', 'beplantingstype', 'familie',
        'status_nl', 'nsr_status', 'inheems', 'invasief',
        'vocht', 'standplaats_bodemvochtigheid', 'licht', 'standplaats_licht',
        'bodem', 'grondsoorten', 'standplaats_grondsoort',
        'ph_waarde', 'voedselrijkdom', 'wind', 'extreme_condities',
        'hoogte', 'breedte', 'kroonvorm', 'kroonstructuur', 'winterhardheidszone',
        'biodiversiteit', 'ecowaarde', 'eco_insecten', 'eco_vogels',
        'locatie', 'verharding', 'functie', 'url'
    ]
    
    # Begin met priority kolommen die bestaan
    columns = [c for c in priority_cols if c in all_columns]
    # Voeg rest toe
    for c in sorted(all_columns):
        if c not in columns:
            columns.append(c)
    
    # Schrijf CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    
    print("\n" + "=" * 70)
    print(f"✅ CONVERSIE VOLTOOID!")
    print("=" * 70)
    print(f"\nSuccesvol: {success} soorten")
    if failed:
        print(f"Gefaald:   {failed} bestanden")
    print(f"\nOutput:    {output_csv}")
    print(f"Kolommen:  {len(columns)}")
    
    # Toon sample
    print("\n📊 Sample data (eerste 3 soorten):")
    for row in rows[:3]:
        print(f"  - {row.get('naam', '?')}: {row.get('beplantingstype', '?')}, "
              f"vocht={row.get('vocht', '?')[:30]}..., bodem={row.get('bodem', '?')}")
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nGebruik: python convert_yaml_to_csv.py <yaml_folder> [output_csv]")
        sys.exit(1)
    
    yaml_folder = sys.argv[1]
    output_csv = sys.argv[2] if len(sys.argv) > 2 else "inheemse_soorten.csv"
    
    success = convert_folder_to_csv(yaml_folder, output_csv)
    sys.exit(0 if success else 1)
