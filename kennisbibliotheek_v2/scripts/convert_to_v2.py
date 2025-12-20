#!/usr/bin/env python3
"""
Converteer je huidige kennisbibliotheek naar v2 gelaagde structuur.

Dit script:
1. Leest je huidige nsn.yaml, bodem.yaml, gt.yaml, fgr.yaml
2. Splitst elk item naar een apart bestand in de juiste laag
3. Behoudt alle data
"""

import yaml
from pathlib import Path
import sys

def convert_to_v2(old_kb_path: Path, new_kb_path: Path):
    """Converteer oude kennisbibliotheek naar v2."""
    
    print("\n" + "="*70)
    print("CONVERSIE NAAR V2 GELAAGDE STRUCTUUR")
    print("="*70 + "\n")
    
    # Map oude bestanden naar nieuwe directories
    conversies = {
        'nsn.yaml': 'lagen/nsn',
        'bodem.yaml': 'lagen/bodem',
        'gt.yaml': 'lagen/gt',
        'fgr.yaml': 'lagen/fgr',
    }
    
    for old_file, new_dir in conversies.items():
        old_path = old_kb_path / old_file
        new_path = new_kb_path / new_dir
        
        if not old_path.exists():
            print(f"⚠️  Bestand niet gevonden: {old_file} - overslaan")
            continue
        
        print(f"📂 Verwerken: {old_file}")
        
        # Laad het oude bestand
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
        except Exception as e:
            print(f"   ❌ Kon niet laden: {e}")
            continue
        
        # Zoek de items (meestal onder een key zoals 'nsn', 'bodem', etc.)
        # Probeer verschillende structuren
        items = None
        
        # Optie 1: Data zit in een key (bijv. {'nsn': {items}})
        for key in data.keys():
            if isinstance(data[key], dict) and key != 'meta':
                items = data[key]
                print(f"   Gevonden items onder key '{key}': {len(items)}")
                break
        
        # Optie 2: Data zit direct in root (bijv. {item1: {}, item2: {}})
        if items is None and isinstance(data, dict):
            items = data
            print(f"   Gevonden items in root: {len(items)}")
        
        if not items:
            print(f"   ⚠️  Geen items gevonden in {old_file}")
            continue
        
        # Splits elk item naar eigen bestand
        count_success = 0
        count_error = 0
        
        for item_key, item_data in items.items():
            if item_key == 'meta' or not isinstance(item_data, dict):
                continue  # Skip meta en niet-dict items
            
            # Bepaal bestandsnaam
            output_file = new_path / f"{item_key}.yaml"
            
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    yaml.dump(item_data, f, 
                             allow_unicode=True,
                             default_flow_style=False,
                             sort_keys=False,
                             width=100,
                             indent=2)
                count_success += 1
            except Exception as e:
                print(f"   ❌ Fout bij {item_key}: {e}")
                count_error += 1
        
        print(f"   ✅ {count_success} items opgeslagen naar {new_dir}/")
        if count_error > 0:
            print(f"   ⚠️  {count_error} items met fouten")
        print()
    
    print("="*70)
    print("CONVERSIE VOLTOOID!")
    print("="*70 + "\n")

if __name__ == "__main__":
    # Pad naar je oude en nieuwe kennisbibliotheek
    # Pas deze aan naar je situatie
    
    if len(sys.argv) > 1:
        old_kb = Path(sys.argv[1])
    else:
        old_kb = Path.cwd() / "kennisbibliotheek"
    
    if len(sys.argv) > 2:
        new_kb = Path(sys.argv[2])
    else:
        new_kb = Path.cwd() / "kennisbibliotheek_v2"
    
    if not old_kb.exists():
        print(f"❌ Oude kennisbibliotheek niet gevonden: {old_kb}")
        print(f"\nGebruik: python convert_to_v2.py [pad_naar_oude_kb] [pad_naar_nieuwe_kb]")
        sys.exit(1)
    
    if not new_kb.exists():
        print(f"❌ Nieuwe kennisbibliotheek niet gevonden: {new_kb}")
        print(f"   Draai eerst: python setup_v2_structure.py")
        sys.exit(1)
    
    convert_to_v2(old_kb, new_kb)
    
    print("💡 Volgende stappen:")
    print("   1. Check de gegenereerde bestanden in kennisbibliotheek_v2/lagen/")
    print("   2. Pas items aan volgens v2 templates (focus op één aspect)")
    print("   3. Voeg advies-bibliotheken toe (principes, soorten)")
    print("   4. Test de generator!")
