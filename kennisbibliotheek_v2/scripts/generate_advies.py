#!/usr/bin/env python3
"""
Advies Generator voor Beplantingswijzer

Dit script combineert informatie uit verschillende kennislagen (NSN, Bodem, Gt, FGR)
en genereert een geïntegreerd erfadvies met concrete soortenkeuze.

Gebruik:
    python generate_advies.py --nsn bknsn_dz1 --bodem podzol --gt gt_vii

Output:
    JSON advies met:
    - Context samenvatting
    - Primaire uitdagingen
    - Geschikte soorten (gefilterd)
    - Praktische uitvoering
    - Rapporttekst (geïntegreerd)
"""

import os
import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Any

# ────────────────────────────────────────────────────────────────────────────
# CONFIGURATIE
# ────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent
KB_ROOT = SCRIPT_DIR.parent

LAGEN = {
    'nsn': KB_ROOT / 'lagen' / 'nsn',
    'bodem': KB_ROOT / 'lagen' / 'bodem',
    'gt': KB_ROOT / 'lagen' / 'gt',
    'fgr': KB_ROOT / 'lagen' / 'fgr',
}

ADVIES = {
    'principes': KB_ROOT / 'advies' / 'principes',
    'soorten': KB_ROOT / 'advies' / 'soorten',
    'templates': KB_ROOT / 'advies' / 'templates',
}

# ────────────────────────────────────────────────────────────────────────────
# HELPER FUNCTIES
# ────────────────────────────────────────────────────────────────────────────

def load_yaml(filepath: Path) -> Optional[Dict]:
    """Laad een YAML bestand."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"⚠️  Kon {filepath.name} niet laden: {e}")
        return None

def load_layer(layer_name: str, item_name: str) -> Optional[Dict]:
    """Laad een specifiek item uit een kennislaag."""
    if layer_name not in LAGEN:
        print(f"❌ Onbekende laag: {layer_name}")
        return None
    
    filepath = LAGEN[layer_name] / f"{item_name}.yaml"
    if not filepath.exists():
        print(f"⚠️  Bestand niet gevonden: {filepath}")
        return None
    
    return load_yaml(filepath)

def load_all_soorten() -> Dict[str, Dict]:
    """Laad alle soorten uit de soorten database."""
    soorten = {}
    soorten_dir = ADVIES['soorten']
    
    if not soorten_dir.exists():
        return soorten
    
    for filepath in soorten_dir.glob("*.yaml"):
        data = load_yaml(filepath)
        if data:
            # Gebruik bestandsnaam zonder extensie als key
            key = filepath.stem
            soorten[key] = data
    
    return soorten

def load_all_principes() -> Dict[str, Dict]:
    """Laad alle ontwerpprincipes."""
    principes = {}
    principes_dir = ADVIES['principes']
    
    if not principes_dir.exists():
        return principes
    
    for filepath in principes_dir.glob("*.yaml"):
        data = load_yaml(filepath)
        if data:
            key = filepath.stem
            principes[key] = data
    
    return principes

# ────────────────────────────────────────────────────────────────────────────
# ANALYSE FUNCTIES
# ────────────────────────────────────────────────────────────────────────────

def analyze_context(nsn: Dict, bodem: Dict, gt: Dict, fgr: Optional[Dict]) -> Dict:
    """Analyseer de context en bepaal primaire kenmerken."""
    
    context = {
        'reliëf': None,
        'bodem_textuur': None,
        'bodem_ph': None,
        'bodem_voedselrijk': None,
        'water_regime': None,
        'primaire_uitdagingen': [],
        'secundaire_kenmerken': [],
    }
    
    # NSN: reliëf
    if nsn and 'landvorm' in nsn:
        landvorm = nsn['landvorm']
        if 'positie_in_landschap' in landvorm:
            ligging = landvorm['positie_in_landschap'].get('ligging', '').lower()
            if 'hoog' in ligging:
                context['reliëf'] = 'hoog'
            elif 'laag' in ligging:
                context['reliëf'] = 'laag'
            else:
                context['reliëf'] = 'middel'
    
    # Bodem: textuur, pH, voedselrijk
    if bodem:
        if 'textuur' in bodem:
            context['bodem_textuur'] = bodem['textuur'].get('hoofdtextuur', '').lower()
        
        if 'chemie' in bodem:
            chemie = bodem['chemie']
            
            # pH
            if 'pH' in chemie:
                ph_class = chemie['pH'].get('classificatie', '').lower()
                if 'zuur' in ph_class:
                    context['bodem_ph'] = 'zuur'
                elif 'basisch' in ph_class:
                    context['bodem_ph'] = 'basisch'
                else:
                    context['bodem_ph'] = 'neutraal'
            
            # Voedselrijkdom
            if 'voedselrijkdom' in chemie:
                voedsel = chemie['voedselrijkdom'].get('algemeen', '').lower()
                if 'arm' in voedsel:
                    context['bodem_voedselrijk'] = 'arm'
                elif 'rijk' in voedsel:
                    context['bodem_voedselrijk'] = 'rijk'
                else:
                    context['bodem_voedselrijk'] = 'matig'
    
    # Gt: water regime
    if gt:
        gt_code = gt.get('code', '').upper()
        categorie = gt.get('categorie', '').lower()
        
        if 'zeer droog' in categorie or gt_code in ['VII', 'VIII']:
            context['water_regime'] = 'zeer_droog'
        elif 'droog' in categorie or gt_code == 'VI':
            context['water_regime'] = 'droog'
        elif 'vochtig' in categorie or gt_code in ['IV', 'V']:
            context['water_regime'] = 'vochtig'
        elif 'nat' in categorie or gt_code in ['I', 'II', 'III']:
            context['water_regime'] = 'nat'
    
    # Bepaal primaire uitdagingen op basis van combinatie
    uitdagingen = []
    
    # Droogte
    if context['water_regime'] in ['zeer_droog', 'droog']:
        if context['bodem_textuur'] == 'zand':
            uitdagingen.append({
                'type': 'droogte',
                'ernst': 'zeer_hoog',
                'omschrijving': 'Extreme droogte in zomer door zandgrond en diepe grondwaterstand'
            })
        else:
            uitdagingen.append({
                'type': 'droogte',
                'ernst': 'hoog',
                'omschrijving': 'Droogte in zomer door diepe grondwaterstand'
            })
    
    # Nattigheid
    if context['water_regime'] == 'nat':
        uitdagingen.append({
            'type': 'nattigheid',
            'ernst': 'hoog',
            'omschrijving': 'Natte omstandigheden in winter/voorjaar, beperkte worteldiepte'
        })
    
    # Voedselarmoede
    if context['bodem_voedselrijk'] == 'arm':
        uitdagingen.append({
            'type': 'voedselarmoede',
            'ernst': 'matig' if context['bodem_textuur'] != 'zand' else 'hoog',
            'omschrijving': 'Voedselarme grond, langzame groei'
        })
    
    # Zure pH
    if context['bodem_ph'] == 'zuur':
        uitdagingen.append({
            'type': 'zure_ph',
            'ernst': 'matig',
            'omschrijving': 'Zure grond, niet alle soorten verdragen dit'
        })
    
    context['primaire_uitdagingen'] = uitdagingen
    
    return context

def filter_soorten(soorten: Dict, context: Dict) -> Dict:
    """Filter soorten op basis van context (droogte, pH, voedselrijkdom, etc.)."""
    
    geschikt = {
        'pioniers': [],
        'hoofdbomen': [],
        'bijbomen': [],
        'struiken': [],
    }
    
    for soort_key, soort_data in soorten.items():
        if not isinstance(soort_data, dict):
            continue
        
        # Check of soort geschikt is
        is_geschikt = True
        geschiktheid_score = 0
        
        standplaats = soort_data.get('standplaats', {})
        
        # Check droogte
        if context['water_regime'] in ['zeer_droog', 'droog']:
            droogte_tol = standplaats.get('droogte_tolerantie', '').lower()
            if droogte_tol in ['hoog', 'zeer hoog']:
                geschiktheid_score += 2
            elif droogte_tol == 'matig':
                geschiktheid_score += 1
            else:
                is_geschikt = False  # Niet geschikt voor droogte
        
        # Check nattigheid
        if context['water_regime'] == 'nat':
            nat_tol = standplaats.get('nattigheid_tolerantie', '').lower()
            if nat_tol in ['hoog', 'zeer hoog']:
                geschiktheid_score += 2
            elif nat_tol == 'matig':
                geschiktheid_score += 1
            else:
                is_geschikt = False
        
        # Check pH
        if context['bodem_ph'] == 'zuur':
            ph_pref = standplaats.get('pH_voorkeur', '').lower()
            if 'zuur' in ph_pref:
                geschiktheid_score += 1
            elif 'neutraal' in ph_pref:
                # Neutraal is OK voor zure grond
                pass
            elif 'basisch' in ph_pref or 'kalk' in ph_pref:
                is_geschikt = False
        
        # Check voedselrijkdom
        if context['bodem_voedselrijk'] == 'arm':
            voedsel_behoefte = standplaats.get('voedsel_behoefte', '').lower()
            if 'laag' in voedsel_behoefte or 'arm' in voedsel_behoefte:
                geschiktheid_score += 1
            elif 'hoog' in voedsel_behoefte or 'rijk' in voedsel_behoefte:
                geschiktheid_score -= 1
        
        # Als geschikt, voeg toe aan juiste categorie
        if is_geschikt:
            soort_info = {
                'naam': soort_data.get('titel', soort_key),
                'wetenschappelijk': soort_data.get('wetenschappelijke_naam', ''),
                'functie': soort_data.get('functie', ''),
                'geschiktheid_score': geschiktheid_score,
            }
            
            type_plant = soort_data.get('type', '').lower()
            if 'pionier' in type_plant:
                geschikt['pioniers'].append(soort_info)
            elif 'hoofdboom' in type_plant or type_plant == 'boom':
                geschikt['hoofdbomen'].append(soort_info)
            elif 'bijboom' in type_plant:
                geschikt['bijbomen'].append(soort_info)
            elif 'struik' in type_plant or 'heester' in type_plant:
                geschikt['struiken'].append(soort_info)
    
    # Sorteer elke categorie op geschiktheid
    for cat in geschikt:
        geschikt[cat] = sorted(geschikt[cat], 
                              key=lambda x: x['geschiktheid_score'], 
                              reverse=True)
    
    return geschikt

def select_principes(context: Dict, principes: Dict) -> List[Dict]:
    """Selecteer relevante ontwerpprincipes op basis van context."""
    
    relevant = []
    
    for prin_key, prin_data in principes.items():
        if not isinstance(prin_data, dict):
            continue
        
        # Check of principe relevant is
        is_relevant = False
        relevantie_score = 0
        
        toepassingen = prin_data.get('toepasbaar_bij', [])
        
        # Check relevantie voor uitdagingen
        for uitdaging in context.get('primaire_uitdagingen', []):
            uitdaging_type = uitdaging['type']
            
            if uitdaging_type in toepassingen:
                is_relevant = True
                relevantie_score += uitdaging.get('ernst', 'matig') == 'zeer_hoog' and 3 or 2
        
        # Check algemene relevantie
        if context['water_regime'] in toepassingen:
            is_relevant = True
            relevantie_score += 1
        
        if context['bodem_textuur'] in toepassingen:
            is_relevant = True
            relevantie_score += 1
        
        if is_relevant:
            relevant.append({
                'naam': prin_data.get('titel', prin_key),
                'beschrijving': prin_data.get('beschrijving', ''),
                'waarom': prin_data.get('waarom', ''),
                'hoe': prin_data.get('hoe', ''),
                'relevantie_score': relevantie_score,
            })
    
    # Sorteer op relevantie
    relevant = sorted(relevant, key=lambda x: x['relevantie_score'], reverse=True)
    
    return relevant

# ────────────────────────────────────────────────────────────────────────────
# RAPPORTGENERATIE
# ────────────────────────────────────────────────────────────────────────────

def generate_context_samenvatting(nsn: Dict, bodem: Dict, gt: Dict, context: Dict) -> str:
    """Genereer een leesbare contextsamenvatting."""
    
    delen = []
    
    # NSN
    if nsn:
        nsn_naam = nsn.get('titel', 'Onbekend natuurlijk systeem')
        delen.append(f"- **Landschap**: {nsn_naam}")
    
    # Bodem
    if bodem:
        bodem_naam = bodem.get('titel', 'Onbekende bodem')
        delen.append(f"- **Bodem**: {bodem_naam}")
    
    # Gt
    if gt:
        gt_naam = gt.get('titel', 'Onbekende grondwatertrap')
        delen.append(f"- **Waterhuishouding**: {gt_naam}")
    
    samenvatting = "Deze locatie combineert:\n" + "\n".join(delen)
    
    # Conclusie
    conclusie_delen = []
    
    if context['reliëf']:
        conclusie_delen.append(f"{context['reliëf']} gelegen")
    
    if context['water_regime']:
        water_tekst = {
            'zeer_droog': 'zeer droog',
            'droog': 'droog',
            'vochtig': 'vochtig',
            'nat': 'nat'
        }.get(context['water_regime'], context['water_regime'])
        conclusie_delen.append(water_tekst)
    
    if context['bodem_voedselrijk']:
        voedsel_tekst = {
            'arm': 'voedselarme',
            'matig': 'matig voedselrijke',
            'rijk': 'voedselrijke'
        }.get(context['bodem_voedselrijk'], context['bodem_voedselrijk'])
        conclusie_delen.append(voedsel_tekst)
    
    if conclusie_delen:
        samenvatting += f"\n\n→ Dit is een **{', '.join(conclusie_delen).upper()} STANDPLAATS**"
    
    return samenvatting

def generate_rapporttekst(nsn: Dict, bodem: Dict, gt: Dict, context: Dict, 
                          soorten: Dict, principes: List[Dict]) -> str:
    """Genereer geïntegreerde rapporttekst voor bewoners."""
    
    tekst = []
    
    # Intro
    tekst.append("# Uw Locatie: Advies voor Erfbeplanting\n")
    
    # Context samenvatting
    tekst.append("## Wat voor plek is dit?\n")
    tekst.append(generate_context_samenvatting(nsn, bodem, gt, context))
    tekst.append("")
    
    # Primaire uitdagingen
    if context['primaire_uitdagingen']:
        tekst.append("## De belangrijkste aandachtspunten\n")
        for i, uitdaging in enumerate(context['primaire_uitdagingen'][:3], 1):
            tekst.append(f"**{i}. {uitdaging['omschrijving']}**")
        tekst.append("")
    
    # Top principes
    if principes:
        tekst.append("## Hoe pakt u dit aan?\n")
        for i, principe in enumerate(principes[:3], 1):
            tekst.append(f"### {i}. {principe['naam']}\n")
            if principe.get('waarom'):
                tekst.append(f"*Waarom:* {principe['waarom']}\n")
            if principe.get('hoe'):
                tekst.append(f"*Hoe:* {principe['hoe']}\n")
        tekst.append("")
    
    # Geschikte soorten (top 5 per categorie)
    tekst.append("## Welke soorten passen hier?\n")
    
    if soorten.get('pioniers'):
        tekst.append("### Voor snelle groei en beschutting (pioniers)\n")
        for soort in soorten['pioniers'][:3]:
            tekst.append(f"- **{soort['naam']}** - {soort.get('functie', '')}")
        tekst.append("")
    
    if soorten.get('hoofdbomen'):
        tekst.append("### Voor waarde op lange termijn (hoofdbomen)\n")
        for soort in soorten['hoofdbomen'][:5]:
            tekst.append(f"- **{soort['naam']}** - {soort.get('functie', '')}")
        tekst.append("")
    
    if soorten.get('struiken'):
        tekst.append("### Struiken en heesters\n")
        for soort in soorten['struiken'][:5]:
            tekst.append(f"- **{soort['naam']}** - {soort.get('functie', '')}")
        tekst.append("")
    
    return "\n".join(tekst)

# ────────────────────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────────────────────

def generate_advies(nsn_code: str, bodem_code: str, gt_code: str, 
                   fgr_code: Optional[str] = None) -> Dict:
    """Genereer volledig advies op basis van codes."""
    
    print("\n" + "="*70)
    print("Advies Generator - Beplantingswijzer")
    print("="*70 + "\n")
    
    # Laad lagen
    print("📂 Laden kennislagen...")
    nsn = load_layer('nsn', nsn_code)
    bodem = load_layer('bodem', bodem_code)
    gt = load_layer('gt', gt_code)
    fgr = load_layer('fgr', fgr_code) if fgr_code else None
    
    if not nsn or not bodem or not gt:
        print("❌ Niet alle verplichte lagen konden worden geladen.")
        return {}
    
    print(f"   ✅ NSN: {nsn.get('titel', nsn_code)}")
    print(f"   ✅ Bodem: {bodem.get('titel', bodem_code)}")
    print(f"   ✅ Gt: {gt.get('titel', gt_code)}")
    if fgr:
        print(f"   ✅ FGR: {fgr.get('titel', fgr_code)}")
    print()
    
    # Laad advies-data
    print("📚 Laden advies-bibliotheken...")
    soorten_db = load_all_soorten()
    principes_db = load_all_principes()
    print(f"   Soorten: {len(soorten_db)}")
    print(f"   Principes: {len(principes_db)}")
    print()
    
    # Analyseer context
    print("🔍 Analyseren context...")
    context = analyze_context(nsn, bodem, gt, fgr)
    print(f"   Reliëf: {context['reliëf']}")
    print(f"   Bodem textuur: {context['bodem_textuur']}")
    print(f"   Bodem pH: {context['bodem_ph']}")
    print(f"   Bodem voedselrijk: {context['bodem_voedselrijk']}")
    print(f"   Water regime: {context['water_regime']}")
    print(f"   Primaire uitdagingen: {len(context['primaire_uitdagingen'])}")
    print()
    
    # Filter soorten
    print("🌱 Selecteren geschikte soorten...")
    geschikte_soorten = filter_soorten(soorten_db, context)
    for cat, soorten_list in geschikte_soorten.items():
        print(f"   {cat.capitalize()}: {len(soorten_list)}")
    print()
    
    # Selecteer principes
    print("💡 Selecteren ontwerpprincipes...")
    relevante_principes = select_principes(context, principes_db)
    print(f"   Relevante principes: {len(relevante_principes)}")
    print()
    
    # Genereer rapporttekst
    print("📝 Genereren rapporttekst...")
    rapporttekst = generate_rapporttekst(nsn, bodem, gt, context, 
                                         geschikte_soorten, relevante_principes)
    print("   ✅ Rapporttekst gegenereerd")
    print()
    
    # Combineer alles tot advies
    advies = {
        'metadata': {
            'nsn': nsn_code,
            'bodem': bodem_code,
            'gt': gt_code,
            'fgr': fgr_code,
        },
        'context': context,
        'soorten': geschikte_soorten,
        'principes': relevante_principes,
        'rapporttekst': rapporttekst,
    }
    
    print("="*70)
    print("✅ Advies succesvol gegenereerd!")
    print("="*70 + "\n")
    
    return advies

def main():
    parser = argparse.ArgumentParser(description='Genereer erfadvies o.b.v. kennislagen')
    parser.add_argument('--nsn', required=True, help='NSN code (bijv. bknsn_dz1)')
    parser.add_argument('--bodem', required=True, help='Bodem code (bijv. podzol)')
    parser.add_argument('--gt', required=True, help='Gt code (bijv. gt_vii)')
    parser.add_argument('--fgr', help='FGR code (optioneel)')
    parser.add_argument('--output', '-o', help='Output bestand (JSON)')
    parser.add_argument('--format', choices=['json', 'markdown'], default='json',
                       help='Output formaat')
    
    args = parser.parse_args()
    
    # Genereer advies
    advies = generate_advies(args.nsn, args.bodem, args.gt, args.fgr)
    
    if not advies:
        sys.exit(1)
    
    # Output
    if args.output:
        # Sla op in bestand
        output_path = Path(args.output)
        
        if args.format == 'json':
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(advies, f, ensure_ascii=False, indent=2)
            print(f"💾 Advies opgeslagen: {output_path}")
        
        elif args.format == 'markdown':
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(advies['rapporttekst'])
            print(f"💾 Rapporttekst opgeslagen: {output_path}")
    
    else:
        # Print naar console
        if args.format == 'json':
            print(json.dumps(advies, ensure_ascii=False, indent=2))
        elif args.format == 'markdown':
            print(advies['rapporttekst'])

if __name__ == "__main__":
    main()
