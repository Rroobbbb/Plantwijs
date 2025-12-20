#!/usr/bin/env python3
"""
TreeEbb → v2 Soorten Converter

Converteert TreeEbb CSV naar v2 YAML soorten-database.
Voegt ontbrekende velden toe die nodig zijn voor filtering.
"""

import csv
import yaml
from pathlib import Path
import re

def parse_range(text):
    """Parse een range zoals '10 - 12 m' naar [10, 12]."""
    if not text:
        return None
    match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)', text)
    if match:
        return [float(match.group(1)), float(match.group(2))]
    match = re.search(r'(\d+(?:\.\d+)?)', text)
    if match:
        val = float(match.group(1))
        return [val, val]
    return None

def parse_multivalue(text):
    """Split multi-value velden op '/'."""
    if not text:
        return []
    return [v.strip() for v in text.split('/')]

def infer_droogte_tolerantie(row):
    """Bepaal droogte-tolerantie score uit TreeEbb data."""
    extreme = row.get('Standplaats > Extreme condities', '')
    bodemvocht = row.get('Standplaats > Bodemvochtigheid', '').lower()
    
    if 'verdraagt droogte' in extreme:
        return 'hoog'
    elif 'zeer droog' in bodemvocht or 'droog' in bodemvocht:
        return 'matig'
    elif 'vochtig' in bodemvocht:
        return 'laag'
    else:
        return 'onbekend'

def infer_nattigheid_tolerantie(row):
    """Bepaal nattigheid-tolerantie uit TreeEbb data."""
    bodemvocht = row.get('Standplaats > Bodemvochtigheid', '').lower()
    extreme = row.get('Standplaats > Extreme condities', '')
    
    if 'overstroming' in extreme:
        return 'zeer hoog'
    elif 'nat' in bodemvocht:
        return 'hoog'
    elif 'vochtig' in bodemvocht:
        return 'matig'
    else:
        return 'laag'

def infer_type(row):
    """Bepaal type (pionier/hoofdboom/struik)."""
    boomtype = row.get('Beplantingstypes > Boomtypen', '').lower()
    overige = row.get('Beplantingstypes > Overige beplanting', '').lower()
    
    if 'bosplantsoen' in boomtype:
        return 'pionier'
    elif 'hoogstam' in boomtype:
        return 'hoofdboom'
    elif 'struik' in overige or 'heester' in overige:
        return 'struik'
    else:
        return 'onbekend'

def infer_groeisnelheid(hoogte_text):
    """Schat groeisnelheid op basis van eindh hoogte."""
    hoogte_range = parse_range(hoogte_text)
    if not hoogte_range:
        return 'onbekend'
    
    max_hoogte = hoogte_range[1]
    
    # Ruwe schatting (zou per soort verfijnd moeten worden)
    if max_hoogte > 20:
        return 'traag'  # Grote bomen groeien meestal traag
    elif max_hoogte > 10:
        return 'matig'
    else:
        return 'snel'

def convert_treeebb_to_v2(csv_path, output_dir):
    """Converteer TreeEbb CSV naar v2 YAML soorten."""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*70)
    print("TREEEBB → V2 SOORTEN CONVERTER")
    print("="*70 + "\n")
    
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"📊 Gevonden: {len(rows)} soorten\n")
    
    converted = 0
    for row in rows:
        naam = row.get('naam', '').strip()
        if not naam:
            continue
        
        # Maak bestandsnaam (lowercase, spaties vervangen)
        filename = naam.lower().replace(' ', '_').replace("'", '').replace('.', '')
        filename = re.sub(r'[^a-z0-9_]', '', filename)
        filename = f"{filename}.yaml"
        
        # Converteer naar v2 formaat
        soort = {
            'titel': naam,
            'wetenschappelijke_naam': naam,  # TreeEbb heeft meestal wetenschappelijke namen
            'type': infer_type(row),
            
            # Standplaatseisen
            'standplaats': {
                'droogte_tolerantie': infer_droogte_tolerantie(row),
                'nattigheid_tolerantie': infer_nattigheid_tolerantie(row),
                'pH_voorkeur': parse_multivalue(row.get('Standplaats > pH-waarde', '')),
                'voedsel_behoefte': parse_multivalue(row.get('Standplaats > Voedselrijkdom', '')),
                'bodemtype_voorkeur': {
                    'beste': parse_multivalue(row.get('Standplaats > Grondsoort', '')),
                },
                'licht': parse_multivalue(row.get('Standplaats > Lichtbehoefte', '')),
                'wind': row.get('Standplaats > Wind', ''),
            },
            
            # Groeikenmerken
            'groei': {
                'hoogte_eindwaarde': row.get('Eigenschappen > Hoogte', ''),
                'hoogte_range': parse_range(row.get('Eigenschappen > Hoogte', '')),
                'breedte_eindwaarde': row.get('Eigenschappen > Breedte', ''),
                'breedte_range': parse_range(row.get('Eigenschappen > Breedte', '')),
                'groeisnelheid_schatting': infer_groeisnelheid(row.get('Eigenschappen > Hoogte', '')),
                'kroonvorm': row.get('Eigenschappen > Kroonvorm', ''),
                'kroonstructuur': row.get('Eigenschappen > Kroonstructuur', ''),
            },
            
            # Functie
            'functie': f"Type: {infer_type(row)}. {row.get('Toepassing > Beplantingsconcepten', '')}",
            
            # Ecologische waarde
            'ecologische_waarde': {
                'biodiversiteit': parse_multivalue(row.get('Standplaats > Biodiversiteit', '')),
            },
            
            # Praktisch
            'praktisch': {
                'winterhardheid': row.get('Eigenschappen > Winterhardheidszone', ''),
                'extreme_condities': parse_multivalue(row.get('Standplaats > Extreme condities', '')),
                'toepassingen': parse_multivalue(row.get('Toepassing > Locatie', '')),
            },
            
            # Inheemse status
            'inheems': {
                'status_nl': row.get('status_nl', ''),
                'nsr_status': row.get('nsr_status', ''),
            },
            
            # Bron
            'bron': {
                'database': 'TreeEbb',
                'url': row.get('url', ''),
                'laatst_bijgewerkt': '2024 (scraped)',
            },
        }
        
        # Sla op
        output_path = output_dir / filename
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(soort, f,
                     allow_unicode=True,
                     default_flow_style=False,
                     sort_keys=False,
                     width=100,
                     indent=2)
        
        converted += 1
        
        if converted % 100 == 0:
            print(f"   ✅ {converted} soorten geconverteerd...")
    
    print(f"\n{'='*70}")
    print(f"✅ CONVERSIE VOLTOOID!")
    print(f"{'='*70}")
    print(f"Geconverteerd: {converted} soorten")
    print(f"Output: {output_dir}")
    print(f"\n💡 LET OP: Dit is een basisconversie.")
    print(f"   Voor belangrijke soorten (top 50) moet je handmatig:")
    print(f"   - Groeisnelheid verfijnen")
    print(f"   - Ecologische waarde uitbreiden")
    print(f"   - Functie beter omschrijven")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Gebruik: python convert_treeebb.py <input.csv> [output_dir]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "soorten_v2"
    
    convert_treeebb_to_v2(csv_path, output_dir)
