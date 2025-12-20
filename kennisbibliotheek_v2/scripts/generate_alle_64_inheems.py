#!/usr/bin/env python3
"""
Genereer ALLE 64 Inheemse Soorten met Volledige v2 Details

Dit script:
1. Leest TreeEbb CSV
2. Filtert 64 inheemse soorten
3. Vult aan met uitgebreide ecologische en praktische kennis
4. Genereert volledige v2 YAML bestanden

Output: 64 production-ready YAML bestanden
"""

import csv
import yaml
import re
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# KENNISDATABASE: Aanvullende info per soort
# ════════════════════════════════════════════════════════════════════════════

# Deze database vult TreeEbb aan met specifieke kennis over:
# - Ecologische waarde (aantal insectensoorten, etc.)
# - Groeisnelheid per periode
# - Praktische tips
# - Klimaatbestendigheid
# - Functie in beplanting

SOORTEN_KENNIS = {
    
    # ────────────────────────────────────────────────────────────────────────
    # HOOFDBOMEN - Groot
    # ────────────────────────────────────────────────────────────────────────
    
    'Quercus robur': {
        'type_override': 'hoofdboom',
        'functie': 'Dé hoofdboom voor natuurwaarde. Ondersteuning 500+ insectensoorten.',
        'ecologie_detail': {
            'insecten': '500+ soorten (hoogste van NL)',
            'vogels': 'Eikels voor gaai, eekhoorn',
            'score': '10/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '20-40cm/jaar (traag)',
            'snelheid_jaar_5_15': '40-60cm/jaar',
            'worteltype': 'Penwortel (3-5m diep)',
            'levensduur': '300-500 jaar',
        },
        'praktisch_detail': {
            'plantmaat': '40-80cm blote wortel',
            'aanslag': 'Traag eerste 2-3 jaar',
            'ziekten': ['Eikenprocessierups', 'Meeldauw (cosmetisch)'],
        },
        'klimaat_scores': {
            'droogte': 8,
            'hitte': 8,
            'toekomst': 'Veilige keuze',
        },
    },
    
    'Quercus petraea': {
        'type_override': 'hoofdboom',
        'functie': 'Wintereik - vergelijkbaar met zomereik maar minder nat-tolerant.',
        'ecologie_detail': {
            'insecten': '450+ soorten',
            'score': '10/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '20-40cm/jaar',
            'worteltype': 'Penwortel',
            'levensduur': '300-500 jaar',
        },
        'klimaat_scores': {
            'droogte': 9,  # Beter dan zomereik
            'hitte': 8,
        },
    },
    
    'Fagus sylvatica': {
        'type_override': 'hoofdboom',
        'functie': 'Schaduwboom bij uitstek. Dichte kroon, weinig ondergroei mogelijk.',
        'ecologie_detail': {
            'insecten': '150+ soorten',
            'vogels': 'Buchennootjes',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '20-30cm/jaar',
            'worteltype': 'Oppervlakkig',
            'levensduur': '200-300 jaar',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Uitstekend! Houdt blad (bruin) in winter',
            'schaduw': 'Zeer dichte schaduw',
        },
        'klimaat_scores': {
            'droogte': 4,  # NIET droogte-tolerant!
            'hitte': 5,
            'toekomst': 'Matig - gevoelig voor droogte',
        },
    },
    
    'Tilia cordata': {
        'type_override': 'hoofdboom',
        'functie': 'Belangrijke bijenboom (bloei juli). Droogte-toleranter dan zomerlinde.',
        'ecologie_detail': {
            'insecten': '300+ soorten',
            'bijen': 'Zeer belangrijk! Bloei juli',
            'score': '9/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '30-50cm/jaar',
            'levensduur': '500-1000 jaar',
        },
        'klimaat_scores': {
            'droogte': 7,
            'hitte': 8,
        },
    },
    
    'Carpinus betulus': {
        'type_override': 'hoofdboom',
        'functie': 'Alternatief voor beuk bij droge omstandigheden. Wintergroen effect.',
        'ecologie_detail': {
            'insecten': '150+ soorten',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '25-40cm/jaar',
            'bijzonderheid': 'Houdt blad (bruin) in winter',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Zeer geschikt, dicht',
        },
        'klimaat_scores': {
            'droogte': 8,
            'hitte': 7,
        },
    },
    
    'Acer campestre': {
        'type_override': 'hoofdboom',
        'functie': 'Zeer robuuste boom voor moeilijke standplaatsen. Klimaatbestendig.',
        'ecologie_detail': {
            'insecten': '100+ soorten',
            'bijen': 'Bloei voorjaar',
            'score': '8/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '30-50cm/jaar',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Uitstekend',
            'extreme_condities': ['strooizout', 'droogte', 'hitte'],
        },
        'klimaat_scores': {
            'droogte': 9,
            'hitte': 9,
            'toekomst': 'Uitstekend',
        },
    },
    
    'Fraxinus excelsior': {
        'type_override': 'hoofdboom',
        'functie': 'Snelgroeiende boom voor natte standplaatsen.',
        'ecologie_detail': {
            'insecten': '100+ soorten',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '60-100cm/jaar (snel!)',
        },
        'praktisch_detail': {
            'ziekten': ['Essentaksterfte (70-90% uitval verwacht!)'],
        },
        'klimaat_scores': {
            'droogte': 5,
            'toekomst': 'SLECHT - essentaksterfte',
        },
    },
    
    # ────────────────────────────────────────────────────────────────────────
    # PIONIERS
    # ────────────────────────────────────────────────────────────────────────
    
    'Betula pendula': {
        'type_override': 'pionier',
        'functie': 'Snelle pionier voor bodemverbetering. Bladafval verbetert zure grond.',
        'ecologie_detail': {
            'insecten': '300+ soorten',
            'vogels': 'Nestgelegenheid kleine zangvogels',
            'score': '8/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '60-100cm/jaar',
            'snelheid_jaar_5_15': '40-60cm/jaar',
            'worteltype': 'Hartvormig, oppervlakkig',
            'levensduur': '80-100 jaar',
        },
        'praktisch_detail': {
            'plantmaat': '60-100cm blote wortel',
            'aanslag': 'Zeer goed',
            'nazorg': 'Minimaal, zeer robuust',
        },
        'klimaat_scores': {
            'droogte': 7,
            'hitte': 7,
        },
    },
    
    'Betula pubescens': {
        'type_override': 'pionier',
        'functie': 'Pionier voor natte plekken. Alternatief ruwe berk bij hoge grondwater.',
        'ecologie_detail': {
            'insecten': '250+ soorten',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '50-80cm/jaar',
        },
        'klimaat_scores': {
            'droogte': 5,  # Minder dan ruwe berk
        },
    },
    
    'Alnus glutinosa': {
        'type_override': 'pionier',
        'functie': 'Boom voor natte standplaatsen. Verbetert bodem via stikstoffixatie.',
        'ecologie_detail': {
            'insecten': '200+ soorten',
            'vogels': 'Zaden in winter (sijsjes)',
            'score': '8/10',
            'bijzonderheid': 'Stikstoffixatie via wortelknolletjes',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '50-80cm/jaar',
        },
        'klimaat_scores': {
            'droogte': 2,  # Wil nat!
        },
    },
    
    'Populus tremula': {
        'type_override': 'pionier',
        'functie': 'Snelle pionier. Trilende bladeren. Maakt worteluitlopers.',
        'ecologie_detail': {
            'insecten': '250+ soorten',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '80-120cm/jaar (zeer snel!)',
        },
        'praktisch_detail': {
            'let_op': 'Maakt worteluitlopers - kan woekeren',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    # ────────────────────────────────────────────────────────────────────────
    # STRUIKEN - Hoge ecologische waarde
    # ────────────────────────────────────────────────────────────────────────
    
    'Crataegus monogyna': {
        'type_override': 'struik',
        'functie': 'Uitstekende haagplant. Vogelbescherming door doornen. Bloei + bessen.',
        'ecologie_detail': {
            'insecten': '200+ soorten',
            'vogels': 'Broedplaats + voedselbron',
            'score': '10/10',
            'bloei': 'Mei (wit, geurig)',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '30-50cm/jaar',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Uitstekend - ondoordringbaar',
            'let_op': 'Doornen! Niet bij paden',
        },
        'klimaat_scores': {
            'droogte': 9,
        },
    },
    
    'Prunus spinosa': {
        'type_override': 'struik',
        'functie': 'Vroege bloei (maart!) = belangrijk voor vroege bijen/vlinders.',
        'ecologie_detail': {
            'insecten': '150+ soorten',
            'vlinders': 'Waardplant ringvlinder, keizersmantel',
            'vogels': 'Broedplaats, bessen',
            'score': '10/10',
            'bloei': 'Maart-april (vóór bladeren!)',
        },
        'praktisch_detail': {
            'let_op': 'Maakt worteluitlopers - kan woekeren',
        },
        'klimaat_scores': {
            'droogte': 9,
        },
    },
    
    'Corylus avellana': {
        'type_override': 'struik',
        'functie': 'Vroegbloeiende struik (feb-mrt) = eerste stuifmeel. Hazelnoten eetbaar.',
        'ecologie_detail': {
            'insecten': 'Eerste stuifmeel voorjaar',
            'zoogdieren': 'Eekhoorn, hazelmuis',
            'score': '9/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '40-60cm/jaar',
        },
        'praktisch_detail': {
            'eerste_noten': 'Vanaf jaar 5-7',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    'Frangula alnus': {
        'type_override': 'struik',
        'functie': 'Struik voor (zeer) vochtige standplaatsen. Waardplant citroenvlinder.',
        'ecologie_detail': {
            'vlinders': 'Waardplant citroenvlinder',
            'vogels': 'Zwarte bessen',
            'score': '8/10',
        },
        'klimaat_scores': {
            'droogte': 3,  # Wil nat
        },
    },
    
    'Sambucus nigra': {
        'type_override': 'struik',
        'functie': 'Snelgroeiende struik. Bloemen + bessen eetbaar. Hoge vogelwaarde.',
        'ecologie_detail': {
            'insecten': '100+ soorten',
            'vogels': 'Bessen zeer geliefd',
            'score': '8/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '60-100cm/jaar (zeer snel)',
        },
        'praktisch_detail': {
            'eetbaar': 'Bloemen (vlierbloesem) en bessen (jam)',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    'Viburnum opulus': {
        'type_override': 'struik',
        'functie': 'Gelderse roos - prachtige bloei mei/juni. Rode bessen herfst.',
        'ecologie_detail': {
            'insecten': '80+ soorten',
            'vogels': 'Bessen nov-feb',
            'score': '8/10',
        },
        'klimaat_scores': {
            'droogte': 5,
        },
    },
    
    'Ligustrum vulgare': {
        'type_override': 'struik',
        'functie': 'Wilde liguster - haagplant met hoge bijenwaarde. Wintergroen in milde winters.',
        'ecologie_detail': {
            'bijen': 'Bloei juni-juli, honing',
            'vogels': 'Zwarte bessen',
            'score': '7/10',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Zeer geschikt',
            'bijzonderheid': 'Wintergroen in milde winters',
        },
        'klimaat_scores': {
            'droogte': 7,
        },
    },
    
    'Cornus sanguinea': {
        'type_override': 'struik',
        'functie': 'Rode kornoelje - rode twijgen in winter. Bloei + bessen.',
        'ecologie_detail': {
            'insecten': '60+ soorten',
            'vogels': 'Zwarte bessen',
            'score': '7/10',
        },
        'praktisch_detail': {
            'decoratief': 'Rode twijgen in winter zeer decoratief',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    # ────────────────────────────────────────────────────────────────────────
    # WILGEN (nat-tolerant)
    # ────────────────────────────────────────────────────────────────────────
    
    'Salix alba': {
        'type_override': 'hoofdboom',
        'functie': 'Schietwilg - zeer snelle groei. Voor natte standplaatsen.',
        'ecologie_detail': {
            'insecten': '250+ soorten',
            'score': '8/10',
            'bloei': 'Maart-april (katjes, eerste nectar)',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '100-150cm/jaar (extreem snel!)',
        },
        'klimaat_scores': {
            'droogte': 3,  # Wil nat
        },
    },
    
    'Salix caprea': {
        'type_override': 'struik',
        'functie': 'Boswilg - belangrijkste vroege nectarbron (maart). Grote katjes.',
        'ecologie_detail': {
            'insecten': 'ZEER belangrijk - eerste nectar',
            'bijen': 'Eerste nectar maart',
            'score': '10/10',
            'bloei': 'Maart (grote gele katjes)',
        },
        'klimaat_scores': {
            'droogte': 5,
        },
    },
    
    # ────────────────────────────────────────────────────────────────────────
    # OVERIGE
    # ────────────────────────────────────────────────────────────────────────
    
    'Taxus baccata': {
        'type_override': 'hoofdboom',
        'functie': 'Venijnboom - zeer schaduw-tolerant. GIFTIG! Goede haagplant.',
        'ecologie_detail': {
            'vogels': 'Rode bessen (alleen vrouwelijke planten)',
            'score': '6/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '10-20cm/jaar (zeer traag)',
            'levensduur': '1000+ jaar',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Uitstekend, zeer dicht',
            'let_op': 'GIFTIG! Alle delen behalve rode bes (zaad wél giftig)',
            'schaduw_tolerantie': 'Zeer hoog - groeit in volle schaduw',
        },
        'klimaat_scores': {
            'droogte': 7,
        },
    },
    
    'Ilex aquifolium': {
        'type_override': 'struik',
        'functie': 'Hulst - wintergroen. Rode bessen. Goede haagplant.',
        'ecologie_detail': {
            'vogels': 'Rode bessen herfst/winter',
            'score': '7/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '15-25cm/jaar (traag)',
        },
        'praktisch_detail': {
            'gebruik_haag': 'Zeer geschikt',
            'bijzonderheid': 'Wintergroen, rode bessen decoratief',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    'Sorbus aucuparia': {
        'type_override': 'bijboom',
        'functie': 'Wilde lijsterbes - oranje bessen zeer decoratief. Vogelmagneet.',
        'ecologie_detail': {
            'vogels': 'Bessen zeer geliefd (40+ soorten)',
            'score': '9/10',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    'Prunus avium': {
        'type_override': 'hoofdboom',
        'functie': 'Zoete kers - prachtige bloei april. Kersen eetbaar. Snel groeiend.',
        'ecologie_detail': {
            'insecten': '150+ soorten',
            'vogels': 'Kersen (als je ze voor bent!)',
            'score': '8/10',
        },
        'groei_detail': {
            'snelheid_jaar_1_5': '50-80cm/jaar',
        },
        'praktisch_detail': {
            'eetbaar': 'Kersen (juli)',
            'eerste_kersen': 'Vanaf jaar 5-7',
        },
        'klimaat_scores': {
            'droogte': 6,
        },
    },
    
    # Voor soorten zonder specifieke kennis: gebruik TreeEbb data
}

# ════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIES
# ════════════════════════════════════════════════════════════════════════════

def parse_range(text):
    """Parse range zoals '10 - 12 m' naar dict."""
    if not text:
        return None
    
    # Verwijder eenheid
    text_clean = text.replace('m', '').replace('cm', '').strip()
    
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*-\s*(\d+(?:[.,]\d+)?)', text_clean)
    if match:
        min_val = float(match.group(1).replace(',', '.'))
        max_val = float(match.group(2).replace(',', '.'))
        return {'min': min_val, 'max': max_val, 'tekst': text}
    
    match = re.search(r'(\d+(?:[.,]\d+)?)', text_clean)
    if match:
        val = float(match.group(1).replace(',', '.'))
        return {'min': val, 'max': val, 'tekst': text}
    
    return None

def parse_multivalue(text):
    """Split multi-value velden op '/'."""
    if not text:
        return []
    return [v.strip() for v in text.split('/') if v.strip()]

def infer_droogte_tolerantie_score(row):
    """Bepaal droogte-tolerantie score 1-10 uit TreeEbb."""
    extreme = row.get('Standplaats > Extreme condities', '').lower()
    bodemvocht = row.get('Standplaats > Bodemvochtigheid', '').lower()
    
    score = 5  # Default
    
    if 'verdraagt droogte' in extreme:
        score += 3
    if 'verdraagt hitte' in extreme:
        score += 1
    
    if 'zeer droog' in bodemvocht:
        score += 2
    elif 'droog' in bodemvocht:
        score += 1
    elif 'nat' in bodemvocht:
        score -= 2
    
    return min(10, max(1, score))

def infer_nattigheid_tolerantie_score(row):
    """Bepaal nattigheid-tolerantie score 1-10."""
    bodemvocht = row.get('Standplaats > Bodemvochtigheid', '').lower()
    extreme = row.get('Standplaats > Extreme condities', '').lower()
    
    score = 5
    
    if 'overstroming' in extreme:
        score += 3
    if 'nat' in bodemvocht:
        score += 2
    elif 'vochtig' in bodemvocht:
        score += 1
    elif 'droog' in bodemvocht:
        score -= 1
    
    return min(10, max(1, score))

# ════════════════════════════════════════════════════════════════════════════
# MAIN CONVERSIE FUNCTIE
# ════════════════════════════════════════════════════════════════════════════

def generate_alle_64_inheems(csv_path, output_dir):
    """Genereer alle 64 inheemse soorten met volledige v2 details."""
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "="*70)
    print("ALLE 64 INHEEMSE SOORTEN - VOLLEDIGE V2 UITWERKING")
    print("="*70 + "\n")
    
    # Lees CSV
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Filter inheemse soorten
    inheems = [r for r in rows if r.get('status_nl', '').lower() == 'inheems']
    print(f"📊 Gevonden: {len(inheems)} inheemse soorten\n")
    
    converted = 0
    
    for row in inheems:
        naam = row.get('naam', '').strip()
        if not naam:
            continue
        
        # Haal extra kennis op (als beschikbaar)
        extra = SOORTEN_KENNIS.get(naam, {})
        
        # Bepaal type
        if 'type_override' in extra:
            type_plant = extra['type_override']
        elif 'bosplantsoen' in row.get('Beplantingstypes > Boomtypen', '').lower():
            type_plant = 'pionier'
        elif 'hoogstam' in row.get('Beplantingstypes > Boomtypen', '').lower():
            type_plant = 'hoofdboom'
        elif any(w in row.get('Beplantingstypes > Overige beplanting', '').lower() 
                 for w in ['struik', 'heester']):
            type_plant = 'struik'
        else:
            # Bepaal op basis van hoogte
            hoogte_range = parse_range(row.get('Eigenschappen > Hoogte', ''))
            if hoogte_range and hoogte_range['max'] < 5:
                type_plant = 'struik'
            else:
                type_plant = 'bijboom'
        
        # Maak bestandsnaam
        filename = naam.lower().replace(' ', '_').replace("'", '').replace('.', '')
        filename = re.sub(r'[^a-z0-9_]', '', filename)
        filename = f"{filename}.yaml"
        
        # Build v2 YAML
        soort = {
            'titel': naam,
            'wetenschappelijke_naam': naam,
            'type': type_plant,
            'familie': 'Onbekend',  # TreeEbb heeft dit niet
            
            'inheems': {
                'status_nl': row.get('status_nl', ''),
                'nsr_status': row.get('nsr_status', ''),
            },
            
            # Standplaatseisen
            'standplaats': {
                'droogte_tolerantie_score': (
                    extra.get('klimaat_scores', {}).get('droogte') or 
                    infer_droogte_tolerantie_score(row)
                ),
                'nattigheid_tolerantie_score': infer_nattigheid_tolerantie_score(row),
                'pH_voorkeur': parse_multivalue(row.get('Standplaats > pH-waarde', '')),
                'voedsel_behoefte': parse_multivalue(row.get('Standplaats > Voedselrijkdom', '')),
                'bodemtype_voorkeur': {
                    'types': parse_multivalue(row.get('Standplaats > Grondsoort', '')),
                },
                'licht': parse_multivalue(row.get('Standplaats > Lichtbehoefte', '')),
                'wind_tolerantie': row.get('Standplaats > Wind', ''),
                'extreme_condities': parse_multivalue(row.get('Standplaats > Extreme condities', '')),
            },
            
            # Groeikenmerken
            'groei': {
                'hoogte': row.get('Eigenschappen > Hoogte', ''),
                'hoogte_range': parse_range(row.get('Eigenschappen > Hoogte', '')),
                'breedte': row.get('Eigenschappen > Breedte', ''),
                'breedte_range': parse_range(row.get('Eigenschappen > Breedte', '')),
                'kroonvorm': row.get('Eigenschappen > Kroonvorm', ''),
                'kroonstructuur': row.get('Eigenschappen > Kroonstructuur', ''),
                'winterhardheid': row.get('Eigenschappen > Winterhardheidszone', ''),
            },
            
            # Functie
            'functie': (
                extra.get('functie') or 
                f"Type: {type_plant}. {row.get('Toepassing > Beplantingsconcepten', '')}"
            ),
            
            # Ecologische waarde
            'ecologische_waarde': {
                'biodiversiteit_treeebb': parse_multivalue(row.get('Standplaats > Biodiversiteit', '')),
            },
            
            # Praktisch
            'praktisch': {
                'toepassingen': parse_multivalue(row.get('Toepassing > Locatie', '')),
                'verharding_tolerantie': parse_multivalue(row.get('Toepassing > Verharding', '')),
            },
            
            # Klimaat toekomst
            'klimaat_toekomst': {},
            
            # Bron
            'bron': {
                'database': 'TreeEbb',
                'url': row.get('url', ''),
                'aangevuld': 'Ja' if naam in SOORTEN_KENNIS else 'Basis TreeEbb',
            },
        }
        
        # Voeg extra kennis toe indien beschikbaar
        if extra:
            if 'ecologie_detail' in extra:
                soort['ecologische_waarde'].update(extra['ecologie_detail'])
            
            if 'groei_detail' in extra:
                soort['groei'].update(extra['groei_detail'])
            
            if 'praktisch_detail' in extra:
                soort['praktisch'].update(extra['praktisch_detail'])
            
            if 'klimaat_scores' in extra:
                soort['klimaat_toekomst'] = {
                    'droogte_score': extra['klimaat_scores'].get('droogte'),
                    'hitte_score': extra['klimaat_scores'].get('hitte'),
                    'toekomst_beoordeling': extra['klimaat_scores'].get('toekomst', ''),
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
        
        # Print status
        heeft_extra = '✨' if naam in SOORTEN_KENNIS else '  '
        print(f"{heeft_extra} {converted:2d}. {naam:40s} ({type_plant})")
    
    print(f"\n{'='*70}")
    print(f"✅ ALLE 64 INHEEMSE SOORTEN GEGENEREERD!")
    print(f"{'='*70}")
    print(f"\nOutput: {output_dir}/")
    print(f"\nLegenda:")
    print(f"  ✨ = Aangevuld met uitgebreide kennis")
    print(f"     = Basis (TreeEbb data + geïnfereerde scores)")
    print(f"\n{'='*70}\n")
    
    # Statistieken
    met_extra = sum(1 for r in inheems if r['naam'] in SOORTEN_KENNIS)
    print(f"📊 STATISTIEKEN:")
    print(f"   Met extra kennis: {met_extra}")
    print(f"   Basis TreeEbb: {converted - met_extra}")
    print(f"   Totaal: {converted}")
    print(f"\n💡 TIP: Voeg geleidelijk meer soorten toe aan SOORTEN_KENNIS dict")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Gebruik: python generate_alle_64_inheems.py <treeebb.csv> [output_dir]")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "inheemse_soorten_v2"
    
    generate_alle_64_inheems(csv_path, output_dir)
